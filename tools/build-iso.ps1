# Sloth OS telepítő ISO építése helyben, Windowson (Podman Desktop / podman machine, rootful).
# Fejlesztői segéd, nem kerül az image-be. A CI megfelelője: .github/workflows/iso.yml
#
#   powershell -File tools/build-iso.ps1 [-Image ghcr.io/bathorizsolt/sloth-os:latest] [-Output out]
#
# A privát registry-hez a GitHub CLI tokenje kell "read:packages" joggal
# (egyszer: gh auth refresh -h github.com -s read:packages).
param(
    [string]$Image = "ghcr.io/bathorizsolt/sloth-os:latest",
    [string]$Output = "out"
)
# A podman a haladást a hibakimenetre írja; a Windows PowerShell 5.1 ezt hibának venné.
# Ezért nem állunk meg minden hibakimenetre, hanem a programok kilépési kódját nézzük.
$ErrorActionPreference = "Continue"

# A Titanoboa ISO-készítő scriptje rögzített commitról (frissítéskor: a SHA cseréje)
$TitanoboaCommit = "5c457c3d0518bd17e754be0fd98a60d29d26abb4"
$LiveImage = "localhost/sloth-os-live:latest"

# A build a Podman gépen belül fut (podman machine ssh): a Windows-os kliens a build secretet
# rossz útvonalra írná ("/mnt/c/...\podman-build-secret"). A gép a C: meghajtót /mnt/c alatt látja.
function ConvertTo-MachinePath([string]$path) {
    $full = [System.IO.Path]::GetFullPath($path)
    return "/mnt/" + $full.Substring(0, 1).ToLower() + $full.Substring(2).Replace("\", "/")
}
function Invoke-InMachine([string]$command) {
    podman machine ssh $command
}

$repo = Split-Path -Parent $PSScriptRoot
$work = Join-Path ([System.IO.Path]::GetTempPath()) "sloth-iso-build"
New-Item -ItemType Directory -Force $work | Out-Null
$outDir = if ([System.IO.Path]::IsPathRooted($Output)) { $Output } else { Join-Path $repo $Output }
New-Item -ItemType Directory -Force $outDir | Out-Null

# Bejelentkezési adatok a ghcr.io-hoz: csak a build idejére, a munkamappában
$user = (gh api user --jq .login).Trim()
if ($LASTEXITCODE -or -not $user) { throw "A GitHub CLI nincs bejelentkezve (gh auth login)." }
$token = (gh auth token).Trim()
$auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("${user}:${token}"))
$authFile = Join-Path $work "auth.json"
Set-Content -Path $authFile -Encoding ascii -Value "{`"auths`":{`"ghcr.io`":{`"auth`":`"$auth`"}}}"

try {
    Write-Host "== Alap image letöltése: $Image"
    podman pull --authfile $authFile $Image
    if ($LASTEXITCODE) { throw "Az alap image nem tölthető le (read:packages jog kell a tokenhez)." }

    Write-Host "== Élő rendszer építése: $LiveImage"
    $mAuth = ConvertTo-MachinePath $authFile
    Invoke-InMachine ("podman build --pull=never --authfile '$mAuth' " +
        "--secret id=registry-auth,src='$mAuth' --build-arg BASE_IMAGE='$Image' " +
        "-t '$LiveImage' '$(ConvertTo-MachinePath (Join-Path $repo 'iso'))'")
    if ($LASTEXITCODE) { throw "Az élő rendszer építése nem sikerült." }

    Write-Host "== ISO készítése (Titanoboa $($TitanoboaCommit.Substring(0, 7)))"
    $buildIso = Join-Path $work "build_iso.sh"
    Invoke-WebRequest -UseBasicParsing -OutFile $buildIso `
        "https://raw.githubusercontent.com/ublue-os/titanoboa/$TitanoboaCommit/build_iso.sh"
    # --cgroups=disabled: a WSL-es Podman gépen a "pids" cgroup-vezérlő nem érhető el
    # bash -e: a Titanoboa scriptje is álljon meg az első hibánál (a shebang a "bash script" indításnál nem számít)
    Invoke-InMachine ("podman run --rm --cgroups=disabled --cap-add sys_admin --security-opt label=disable " +
        "-v '$(ConvertTo-MachinePath $buildIso):/src/build_iso.sh:ro' " +
        "--mount type=image,source='$LiveImage',dst=/rootfs " +
        "-v '$(ConvertTo-MachinePath $outDir):/output' " +
        "quay.io/fedora/fedora:latest bash -exo pipefail /src/build_iso.sh")
    if ($LASTEXITCODE) { throw "Az ISO készítése nem sikerült." }

    $iso = Get-ChildItem $outDir -Filter *.iso | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $final = Join-Path $outDir "sloth-os.iso"
    if ($iso.FullName -ne $final) { Move-Item -Force $iso.FullName $final }
    $hash = (Get-FileHash -Algorithm SHA256 $final).Hash.ToLower()
    Set-Content -Path "$final.sha256" -Encoding ascii -Value "$hash  sloth-os.iso"
    Write-Host ("== Kész: {0} ({1:N1} GB)" -f $final, ((Get-Item $final).Length / 1GB))
}
finally {
    Remove-Item -Force $authFile -ErrorAction SilentlyContinue
}
