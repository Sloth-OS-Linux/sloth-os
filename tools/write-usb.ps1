# Writes the Sloth OS installer ISO to a USB stick on Windows (developer tool, not in the image).
# EVERYTHING on the USB stick is erased. It only writes to a USB disk of at most 256 GB, never to the system disk.
# It needs administrator rights: if it does not have them, the script restarts itself with an approval window (UAC).
#
#   powershell -File tools/write-usb.ps1 [-Iso out\sloth-os.iso] [-Disk <number>]
#
# Without -Disk it picks the only USB disk plugged in (if there are several, it lists them and asks for the number).
# After writing it reads the USB stick back and compares it with the ISO.
param(
    [string]$Iso = "",
    [int]$Disk = -1,
    [string]$Log = ""
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

function Say([string]$text) {
    Write-Host $text
    if ($Log) { Add-Content -Path $Log -Value $text -Encoding utf8 }
}

if (-not $Iso) {
    $latest = Get-ChildItem (Join-Path $repo "out") -Filter *.iso -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) { throw "No ISO in the out folder; give one: -Iso <file>" }
    $Iso = $latest.FullName
}
$Iso = (Resolve-Path $Iso).Path

$usb = @(Get-Disk | Where-Object { $_.BusType -eq "USB" -and -not $_.IsSystem -and -not $_.IsBoot -and $_.Size -le 256GB })
if ($Disk -lt 0) {
    if ($usb.Count -ne 1) {
        $usb | Format-Table Number, FriendlyName, @{n = "GB"; e = { [math]::Round($_.Size / 1GB, 1) } } | Out-String | Write-Host
        throw "It is not clear which USB stick to write to ($($usb.Count) USB disks); give one: -Disk <number>"
    }
    $Disk = $usb[0].Number
}
$target = $usb | Where-Object Number -eq $Disk
if (-not $target) { throw "Disk $Disk is not a USB stick (or it is the system disk, or bigger than 256 GB)" }
$isoSize = (Get-Item $Iso).Length
if ($isoSize -gt $target.Size) { throw "The ISO ($([math]::Round($isoSize / 1GB, 1)) GB) does not fit on the USB stick" }

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    # restarting as administrator; we see the progress through a log file
    $Log = Join-Path ([System.IO.Path]::GetTempPath()) "sloth-write-usb.log"
    Set-Content -Path $Log -Value "" -Encoding utf8
    $shell = (Get-Process -Id $PID).Path
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Iso `"$Iso`" -Disk $Disk -Log `"$Log`""
    $p = Start-Process -FilePath $shell -ArgumentList $argList -Verb RunAs -WindowStyle Hidden -PassThru
    $shown = 0
    while (-not $p.HasExited) {
        Start-Sleep -Seconds 2
        $lines = @(Get-Content $Log -ErrorAction SilentlyContinue)
        $lines | Select-Object -Skip $shown | ForEach-Object { Write-Host $_ }
        $shown = $lines.Count
    }
    @(Get-Content $Log -ErrorAction SilentlyContinue) | Select-Object -Skip $shown | ForEach-Object { Write-Host $_ }
    exit $p.ExitCode
}

try {
    Say "ISO: $Iso ($([math]::Round($isoSize / 1GB, 2)) GB)"
    Say "USB stick: disk $($target.Number), $($target.FriendlyName), $([math]::Round($target.Size / 1GB, 1)) GB - everything on it will be erased"
    # removing the old partitions, so Windows does not keep the volumes locked
    Clear-Disk -Number $Disk -RemoveData -RemoveOEM -Confirm:$false -ErrorAction SilentlyContinue
    Update-Disk -Number $Disk

    $chunk = 4MB
    $buf = New-Object byte[] $chunk
    $src = [System.IO.File]::OpenRead($Iso)
    $dst = New-Object System.IO.FileStream("\\.\PhysicalDrive$Disk", [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::ReadWrite, $chunk, [System.IO.FileOptions]::WriteThrough)
    $done = 0; $last = -1
    while (($n = $src.Read($buf, 0, $chunk)) -gt 0) {
        if ($n % 512) { [Array]::Clear($buf, $n, 512 - $n % 512); $n += 512 - $n % 512 }  # whole sectors
        $dst.Write($buf, 0, $n)
        $done += $n
        $pct = [math]::Floor($done * 100 / $isoSize)
        if ($pct -ne $last -and $pct % 5 -eq 0) { Say "Writing... $pct%"; $last = $pct }
    }
    $dst.Flush(); $dst.Close(); $src.Close()

    Say "Verifying (reading back)..."
    $src = [System.IO.File]::OpenRead($Iso)
    $dst = New-Object System.IO.FileStream("\\.\PhysicalDrive$Disk", [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite, $chunk)
    # SHA-256 of the ISO and of the first (ISO-sized) part of the USB stick
    $hIso = [System.Security.Cryptography.SHA256]::Create()
    $hUsb = [System.Security.Cryptography.SHA256]::Create()
    $buf2 = New-Object byte[] $chunk
    $done = 0; $last = -1
    while (($n = $src.Read($buf, 0, $chunk)) -gt 0) {
        $m = $n + (512 - $n % 512) % 512
        $got = 0
        while ($got -lt $m) {
            $r = $dst.Read($buf2, $got, $m - $got)
            if ($r -le 0) { throw "Reading the USB stick was interrupted" }
            $got += $r
        }
        [void]$hIso.TransformBlock($buf, 0, $n, $null, 0)
        [void]$hUsb.TransformBlock($buf2, 0, $n, $null, 0)
        $done += $n
        $pct = [math]::Floor($done * 100 / $isoSize)
        if ($pct -ne $last -and $pct % 10 -eq 0) { Say "Verifying... $pct%"; $last = $pct }
    }
    [void]$hIso.TransformFinalBlock($buf, 0, 0)
    [void]$hUsb.TransformFinalBlock($buf2, 0, 0)
    if ([BitConverter]::ToString($hIso.Hash) -ne [BitConverter]::ToString($hUsb.Hash)) {
        throw "The USB stick's contents differ from the ISO: a bad USB stick or a write error"
    }
    Say "Verified: SHA-256 $(([BitConverter]::ToString($hIso.Hash) -replace '-', '').ToLower())"
    $dst.Close(); $src.Close()
    Update-Disk -Number $Disk
    Say "Done: the Sloth OS installer can be started from the USB stick."
    exit 0
} catch {
    Say "HIBA: $($_.Exception.Message)"
    exit 1
}
