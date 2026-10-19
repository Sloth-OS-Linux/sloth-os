# Sloth OS telepítő ISO pendrive-ra írása Windowson (fejlesztői segéd, nem kerül az image-be).
# A pendrive MINDEN adata törlődik. Csak USB-s, legfeljebb 256 GB-os lemezre ír, a rendszerlemezre soha.
# Rendszergazdai jog kell hozzá: ha nincs, a script egy jóváhagyó ablakkal (UAC) újraindítja magát.
#
#   powershell -File tools/write-usb.ps1 [-Iso out\sloth-os.iso] [-Disk <szám>]
#
# -Disk nélkül az egyetlen bedugott USB-s lemezt választja (ha több van, kiírja őket, és a számot kéri).
# Írás után visszaolvassa és összeveti a pendrive tartalmát az ISO-val.
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
    if (-not $latest) { throw "Nincs ISO az out mappában; add meg: -Iso <fájl>" }
    $Iso = $latest.FullName
}
$Iso = (Resolve-Path $Iso).Path

$usb = @(Get-Disk | Where-Object { $_.BusType -eq "USB" -and -not $_.IsSystem -and -not $_.IsBoot -and $_.Size -le 256GB })
if ($Disk -lt 0) {
    if ($usb.Count -ne 1) {
        $usb | Format-Table Number, FriendlyName, @{n = "GB"; e = { [math]::Round($_.Size / 1GB, 1) } } | Out-String | Write-Host
        throw "Nem egyértelmű, melyik pendrive-ra írjak ($($usb.Count) USB-s lemez); add meg: -Disk <szám>"
    }
    $Disk = $usb[0].Number
}
$target = $usb | Where-Object Number -eq $Disk
if (-not $target) { throw "A(z) $Disk. lemez nem USB-s pendrive (vagy rendszerlemez, vagy 256 GB-nál nagyobb)" }
$isoSize = (Get-Item $Iso).Length
if ($isoSize -gt $target.Size) { throw "Az ISO ($([math]::Round($isoSize / 1GB, 1)) GB) nem fér el a pendrive-on" }

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    # újraindítás rendszergazdaként; a haladást egy naplófájlon át látjuk
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
    Say "Pendrive: $($target.Number). lemez, $($target.FriendlyName), $([math]::Round($target.Size / 1GB, 1)) GB - minden adata törlődik"
    # a régi partíciók eltávolítása, hogy a Windows ne tartsa zárolva a köteteket
    Clear-Disk -Number $Disk -RemoveData -RemoveOEM -Confirm:$false -ErrorAction SilentlyContinue
    Update-Disk -Number $Disk

    $chunk = 4MB
    $buf = New-Object byte[] $chunk
    $src = [System.IO.File]::OpenRead($Iso)
    $dst = New-Object System.IO.FileStream("\\.\PhysicalDrive$Disk", [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::ReadWrite, $chunk, [System.IO.FileOptions]::WriteThrough)
    $done = 0; $last = -1
    while (($n = $src.Read($buf, 0, $chunk)) -gt 0) {
        if ($n % 512) { [Array]::Clear($buf, $n, 512 - $n % 512); $n += 512 - $n % 512 }  # teljes szektorok
        $dst.Write($buf, 0, $n)
        $done += $n
        $pct = [math]::Floor($done * 100 / $isoSize)
        if ($pct -ne $last -and $pct % 5 -eq 0) { Say "Írás... $pct%"; $last = $pct }
    }
    $dst.Flush(); $dst.Close(); $src.Close()

    Say "Ellenőrzés (visszaolvasás)..."
    $src = [System.IO.File]::OpenRead($Iso)
    $dst = New-Object System.IO.FileStream("\\.\PhysicalDrive$Disk", [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite, $chunk)
    # SHA-256 az ISO-ról és a pendrive első (ISO-méretnyi) részéről
    $hIso = [System.Security.Cryptography.SHA256]::Create()
    $hUsb = [System.Security.Cryptography.SHA256]::Create()
    $buf2 = New-Object byte[] $chunk
    $done = 0; $last = -1
    while (($n = $src.Read($buf, 0, $chunk)) -gt 0) {
        $m = $n + (512 - $n % 512) % 512
        $got = 0
        while ($got -lt $m) {
            $r = $dst.Read($buf2, $got, $m - $got)
            if ($r -le 0) { throw "A pendrive olvasása megszakadt" }
            $got += $r
        }
        [void]$hIso.TransformBlock($buf, 0, $n, $null, 0)
        [void]$hUsb.TransformBlock($buf2, 0, $n, $null, 0)
        $done += $n
        $pct = [math]::Floor($done * 100 / $isoSize)
        if ($pct -ne $last -and $pct % 10 -eq 0) { Say "Ellenőrzés... $pct%"; $last = $pct }
    }
    [void]$hIso.TransformFinalBlock($buf, 0, 0)
    [void]$hUsb.TransformFinalBlock($buf2, 0, 0)
    if ([BitConverter]::ToString($hIso.Hash) -ne [BitConverter]::ToString($hUsb.Hash)) {
        throw "A pendrive tartalma eltér az ISO-tól: rossz pendrive vagy írási hiba"
    }
    Say "Ellenőrizve: SHA-256 $(([BitConverter]::ToString($hIso.Hash) -replace '-', '').ToLower())"
    $dst.Close(); $src.Close()
    Update-Disk -Number $Disk
    Say "Kész: a pendrive-ról indítható a Sloth OS telepítő."
    exit 0
} catch {
    Say "HIBA: $($_.Exception.Message)"
    exit 1
}
