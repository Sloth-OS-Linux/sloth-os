# Sloth OS telepítő ISO építése helyben, Windowson (Podman Desktop / podman machine, rootful).
# Fejlesztői segéd, nem kerül az image-be. A tényleges munkát a tools/build-iso.sh végzi, közvetlenül a
# Podman gép WSL-disztribúciójában (nem podman machine ssh-n át: az nagy terhelésnél elakadt, és így a
# telepítendő image-et sem kell kétszer letölteni). A CI megfelelője: .github/workflows/iso.yml
#
#   powershell -File tools/build-iso.ps1 [-Image ghcr.io/sloth-os-linux/sloth-os:latest] [-Output out] [-Machine podman-machine-default] [-Squash]
#
# -Squash: a telepítendő image rétegeinek összevonása (kisebb ISO; a telepített gép első frissítése a teljes image-et
# letölti). Kiadáshoz; részletek a tools/build-iso.sh elején (SLOTH_SQUASH).
#
# A privát registry-hez a GitHub CLI tokenje kell "read:packages" joggal
# (egyszer: gh auth refresh -h github.com -s read:packages).
# Hely: a Podman gép virtuális lemezén kb. 30 GB kell a build idejére (a C: meghajtón).
param(
    [string]$Image = "ghcr.io/sloth-os-linux/sloth-os:latest",
    [string]$Output = "out",
    [string]$Machine = "podman-machine-default",
    [switch]$Squash
)
# A wsl.exe a haladást a hibakimenetre is írhatja; a Windows PowerShell 5.1 ezt hibának venné.
$ErrorActionPreference = "Continue"

# A gép a C: meghajtót /mnt/c alatt látja
function ConvertTo-MachinePath([string]$path) {
    $full = [System.IO.Path]::GetFullPath($path)
    return "/mnt/" + $full.Substring(0, 1).ToLower() + $full.Substring(2).Replace("\", "/")
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
    podman machine start $Machine 2>$null | Out-Null  # ha már fut, nem baj
    # A build-iso.sh rendszergazdaként fut a gépen; a munkamappa a gép saját (gyors) lemezén van
    wsl.exe -d $Machine -u root -- env "SLOTH_REGISTRY_AUTH=$(ConvertTo-MachinePath $authFile)" "SLOTH_SQUASH=$(if ($Squash) { 1 } else { 0 })" `
        bash "$(ConvertTo-MachinePath (Join-Path $repo 'tools/build-iso.sh'))" $Image "$(ConvertTo-MachinePath $outDir)"
    if ($LASTEXITCODE) { throw "Az ISO készítése nem sikerült (a részletek fent)." }
    $final = Join-Path $outDir "sloth-os.iso"
    Write-Host ("== Kész: {0} ({1:N1} GB)" -f $final, ((Get-Item $final).Length / 1GB))
}
finally {
    Remove-Item -Force $authFile -ErrorAction SilentlyContinue
}
