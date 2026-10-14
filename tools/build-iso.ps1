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
$ErrorActionPreference = "Stop"

# A Titanoboa ISO-készítő scriptje rögzített commitról (frissítéskor: a SHA cseréje)
$TitanoboaCommit = "5c457c3d0518bd17e754be0fd98a60d29d26abb4"
$LiveImage = "localhost/sloth-os-live:latest"

$repo = Split-Path -Parent $PSScriptRoot
$work = Join-Path ([System.IO.Path]::GetTempPath()) "sloth-iso-build"
New-Item -ItemType Directory -Force $work | Out-Null
$outDir = if ([System.IO.Path]::IsPathRooted($Output)) { $Output } else { Join-Path $repo $Output }
New-Item -ItemType Directory -Force $outDir | Out-Null

# Bejelentkezési adatok a ghcr.io-hoz: csak a build idejére, a munkamappában
$user = (gh api user --jq .login).Trim()
$token = (gh auth token).Trim()
$auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("${user}:${token}"))
$authFile = Join-Path $work "auth.json"
Set-Content -Path $authFile -Encoding ascii -Value "{`"auths`":{`"ghcr.io`":{`"auth`":`"$auth`"}}}"

try {
    Write-Host "== Alap image letöltése: $Image"
    podman pull --authfile $authFile $Image
    if ($LASTEXITCODE) { throw "Az alap image nem tölthető le (read:packages jog kell a tokenhez)." }

    Write-Host "== Élő rendszer építése: $LiveImage"
    podman build --pull=never --authfile $authFile `
        --secret "id=registry-auth,src=$authFile" `
        --build-arg "BASE_IMAGE=$Image" `
        -t $LiveImage (Join-Path $repo "iso")
    if ($LASTEXITCODE) { throw "Az élő rendszer építése nem sikerült." }

    Write-Host "== ISO készítése (Titanoboa $($TitanoboaCommit.Substring(0, 7)))"
    $buildIso = Join-Path $work "build_iso.sh"
    Invoke-WebRequest -UseBasicParsing -OutFile $buildIso `
        "https://raw.githubusercontent.com/ublue-os/titanoboa/$TitanoboaCommit/build_iso.sh"
    podman run --rm --cap-add sys_admin --security-opt label=disable `
        -v "${buildIso}:/src/build_iso.sh:ro" `
        --mount "type=image,source=$LiveImage,dst=/rootfs" `
        -v "${outDir}:/output" `
        quay.io/fedora/fedora:latest bash /src/build_iso.sh
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
