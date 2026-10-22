# Builds the Sloth OS installer ISO locally, on Windows (Podman Desktop / podman machine, rootful).
# Developer tool, not in the image. The actual work is done by tools/build-iso.sh, directly in the
# Podman machine's WSL distribution (not through podman machine ssh: that got stuck under heavy load, and this way the
# image to install does not need to be downloaded twice either). The CI equivalent: .github/workflows/iso.yml
#
#   powershell -File tools/build-iso.ps1 [-Image ghcr.io/sloth-os-linux/sloth-os:latest] [-Output out] [-Machine podman-machine-default] [-Squash]
#
# -Squash: no longer supported, the build stops (a squashed image cannot be installed; tools/build-iso.sh, SLOTH_SQUASH).
#
# A private registry needs the GitHub CLI's token with the "read:packages" scope
# (once: gh auth refresh -h github.com -s read:packages).
# Space: about 30 GB is needed on the Podman machine's virtual disk during the build (on the C: drive).
param(
    [string]$Image = "ghcr.io/sloth-os-linux/sloth-os:latest",
    [string]$Output = "out",
    [string]$Machine = "podman-machine-default",
    [switch]$Squash
)
# wsl.exe may also write the progress to the error output; Windows PowerShell 5.1 would take it as an error.
$ErrorActionPreference = "Continue"

# The machine sees the C: drive under /mnt/c
function ConvertTo-MachinePath([string]$path) {
    $full = [System.IO.Path]::GetFullPath($path)
    return "/mnt/" + $full.Substring(0, 1).ToLower() + $full.Substring(2).Replace("\", "/")
}

$repo = Split-Path -Parent $PSScriptRoot
$work = Join-Path ([System.IO.Path]::GetTempPath()) "sloth-iso-build"
New-Item -ItemType Directory -Force $work | Out-Null
$outDir = if ([System.IO.Path]::IsPathRooted($Output)) { $Output } else { Join-Path $repo $Output }
New-Item -ItemType Directory -Force $outDir | Out-Null

# Credentials for ghcr.io: only for the duration of the build, in the work folder
$user = (gh api user --jq .login).Trim()
if ($LASTEXITCODE -or -not $user) { throw "The GitHub CLI is not signed in (gh auth login)." }
$token = (gh auth token).Trim()
$auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("${user}:${token}"))
$authFile = Join-Path $work "auth.json"
Set-Content -Path $authFile -Encoding ascii -Value "{`"auths`":{`"ghcr.io`":{`"auth`":`"$auth`"}}}"

try {
    podman machine start $Machine 2>$null | Out-Null  # fine if it is already running
    # build-iso.sh runs as administrator on the machine; the work folder is on the machine's own (fast) disk
    wsl.exe -d $Machine -u root -- env "SLOTH_REGISTRY_AUTH=$(ConvertTo-MachinePath $authFile)" "SLOTH_SQUASH=$(if ($Squash) { 1 } else { 0 })" `
        bash "$(ConvertTo-MachinePath (Join-Path $repo 'tools/build-iso.sh'))" $Image "$(ConvertTo-MachinePath $outDir)"
    if ($LASTEXITCODE) { throw "Making the ISO failed (details above)." }
    $final = Join-Path $outDir "sloth-os.iso"
    Write-Host ("== Done: {0} ({1:N1} GB)" -f $final, ((Get-Item $final).Length / 1GB))
}
finally {
    Remove-Item -Force $authFile -ErrorAction SilentlyContinue
}
