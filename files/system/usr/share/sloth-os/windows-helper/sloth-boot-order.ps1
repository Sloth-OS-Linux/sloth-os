# Sloth OS: a rendszerindítási sorrend védelme Windows mellett (a Windows oldalán fut).
#
# Egy nagyobb Windows-frissítés a „Windows Boot Manager”-t a rendszerindítási sorrend elejére teszi, és a
# gép utána a Sloth OS menüje nélkül, egyből a Windowst indítja. Ez a segéd minden Windows-induláskor (ütemezett
# feladat, rendszerjogokkal) visszateszi a Sloth OS-t az első helyre. Csak akkor nyúl a sorrendhez, ha az
# első helyen a Windows Boot Manager áll (egy előre tett pendrive-ot vagy más beállítást békén hagy), és
# van „Sloth OS” bejegyzés. A Windows maga is ugyanúgy indítható a Sloth OS menüjéből.
# A Sloth OS oldalán ugyanezt a sloth-boot-order.service végzi (a Sloth OS következő indulásakor).
#
#   Sloth-OS-boot.cmd                    telepítés (egyszer, dupla kattintással; rendszergazdai jóváhagyás kell)
#   sloth-boot-order.ps1 -Uninstall      eltávolítás
#   sloth-boot-order.ps1 -Run            maga a javítás (ezt futtatja az ütemezett feladat)
#
# A bcdedit kimenete a Windows nyelvén van, ezért csak a GUID-okra és a „Sloth OS” névre támaszkodunk.
param([switch]$Install, [switch]$Uninstall, [switch]$Run)

$ErrorActionPreference = "Stop"
$Dir = Join-Path $env:ProgramData "SlothOS"
$Log = Join-Path $Dir "boot-order.log"
$TaskName = "Sloth OS boot order"
$Ours = "Sloth OS"

function Write-Log([string]$text) {
    New-Item -ItemType Directory -Force $Dir | Out-Null
    Add-Content -Path $Log -Value ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $text) -Encoding UTF8
}

function Get-Text([string]$key) {
    # A szövegek a Windows nyelvén (strings.json, a Sloth OS 50 nyelve); ha nincs, angolul
    $file = Join-Path $PSScriptRoot "strings.json"
    if (-not (Test-Path $file)) { $file = Join-Path $Dir "strings.json" }
    try {
        $all = Get-Content -Raw -Encoding UTF8 $file | ConvertFrom-Json
        $culture = (Get-UICulture).Name.Replace("-", "_")
        foreach ($code in @($culture, $culture.Split("_")[0], "en")) {
            $lang = $all.$code
            if ($lang -and $lang.$key) { return $lang.$key }
        }
    } catch { }
    return $key
}

function Show-Message([string]$text, [string]$icon = "Information") {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($text, "Sloth OS", "OK", $icon) | Out-Null
}

function Get-FirmwareEntries {
    # Blokkok üres sorokkal elválasztva; minden blokkban az azonosító (GUID vagy {bootmgr}) és a leírás
    $text = (bcdedit /enum firmware) -join "`n"
    $blocks = $text -split "`n\s*`n"
    $entries = @()
    foreach ($b in $blocks) {
        $id = [regex]::Match($b, "\{[0-9a-fA-F-]{36}\}|\{bootmgr\}|\{fwbootmgr\}").Value
        if ($id) { $entries += [pscustomobject]@{ Id = $id.ToLower(); Text = $b } }
    }
    return $entries
}

function Repair-BootOrder {
    $entries = Get-FirmwareEntries
    $ours = $entries | Where-Object { $_.Id -match "^\{[0-9a-f-]{36}\}$" -and $_.Text -match [regex]::Escape($Ours) } |
        Select-Object -First 1
    $fw = $entries | Where-Object { $_.Id -eq "{fwbootmgr}" } | Select-Object -First 1
    if (-not $ours -or -not $fw) { return "no-entry" }
    # A firmware sorrendje: a {fwbootmgr} blokk azonosítói a saját azonosítója után, sorban
    $order = [regex]::Matches($fw.Text, "\{[0-9a-fA-F-]{36}\}|\{bootmgr\}") | ForEach-Object { $_.Value.ToLower() }
    if ($order.Count -eq 0 -or $order[0] -eq $ours.Id) { return "ok" }
    if ($order[0] -ne "{bootmgr}") { return "ok" }  # nem a Windows tette magát előre: békén hagyjuk
    bcdedit /set "{fwbootmgr}" displayorder $ours.Id /addfirst | Out-Null
    Write-Log "A Sloth OS visszakerült az első helyre ($($ours.Id))"
    return "fixed"
}

function Assert-Admin {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        # Újraindítás rendszergazdaként (UAC); a paraméterek változatlanok
        $mode = if ($Uninstall) { "-Uninstall" } elseif ($Run) { "-Run" } else { "-Install" }
        Start-Process powershell.exe -Verb RunAs -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", "`"$PSCommandPath`"", $mode)
        exit
    }
}

if ($Run) {
    try { Repair-BootOrder | Out-Null } catch { Write-Log "Hiba: $_" }
    exit
}

Assert-Admin
try {
    if ($Uninstall) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        Remove-Item -Recurse -Force $Dir -ErrorAction SilentlyContinue
        Show-Message (Get-Text "removed")
        exit
    }
    # Telepítés: a segéd a ProgramData alá, ütemezett feladat minden Windows-induláskor (rendszerjogokkal)
    New-Item -ItemType Directory -Force $Dir | Out-Null
    Copy-Item -Force $PSCommandPath (Join-Path $Dir "sloth-boot-order.ps1")
    $strings = Join-Path $PSScriptRoot "strings.json"
    if (Test-Path $strings) { Copy-Item -Force $strings (Join-Path $Dir "strings.json") }
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument (
        "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"" +
        (Join-Path $Dir "sloth-boot-order.ps1") + "`" -Run")
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    $triggers = @((New-ScheduledTaskTrigger -AtStartup), (New-ScheduledTaskTrigger -Daily -At "12:00"))
    Register-ScheduledTask -TaskName $TaskName -Action $action -Principal $principal -Settings $settings `
        -Trigger $triggers -Force | Out-Null
    $result = Repair-BootOrder
    Write-Log "Telepítve ($result)"
    if ($result -eq "no-entry") {
        Show-Message (Get-Text "no_entry") "Warning"
    } else {
        Show-Message (Get-Text "installed")
    }
} catch {
    Write-Log "Hiba: $_"
    Show-Message ((Get-Text "failed") + "`n`n$_") "Error"
}
