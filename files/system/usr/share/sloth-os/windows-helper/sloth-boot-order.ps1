# Sloth OS: protecting the boot order next to Windows (runs on the Windows side).
#
# A bigger Windows update puts "Windows Boot Manager" at the front of the boot order, and afterwards the
# machine starts Windows directly, without the Sloth OS menu. On every Windows start (scheduled task, with
# system rights) this helper puts Sloth OS back in first place. It only touches the order if
# Windows Boot Manager is in first place (it leaves a USB stick put first or other settings alone), and
# there is a "Sloth OS" entry. Windows itself can be started from the Sloth OS menu just the same.
# On the Sloth OS side sloth-boot-order.service does the same (at the next Sloth OS start).
#
#   Sloth-OS-boot.cmd                    install (once, with a double-click; needs administrator approval)
#   sloth-boot-order.ps1 -Uninstall      uninstall
#   sloth-boot-order.ps1 -Run            the fix itself (the scheduled task runs this)
#
# bcdedit's output is in Windows' language, so we only rely on the GUIDs and the name "Sloth OS".
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
    # The texts in Windows' language (strings.json, the 50 languages of Sloth OS); English if there is none
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
    # Blocks separated by empty lines; every block has the ID (GUID or {bootmgr}) and the description
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
    # The firmware's order: the IDs of the {fwbootmgr} block after its own ID, in order
    $order = [regex]::Matches($fw.Text, "\{[0-9a-fA-F-]{36}\}|\{bootmgr\}") | ForEach-Object { $_.Value.ToLower() }
    if ($order.Count -eq 0 -or $order[0] -eq $ours.Id) { return "ok" }
    if ($order[0] -ne "{bootmgr}") { return "ok" }  # it was not Windows that put itself first: leave it alone
    bcdedit /set "{fwbootmgr}" displayorder $ours.Id /addfirst | Out-Null
    Write-Log "Sloth OS was put back in first place ($($ours.Id))"
    return "fixed"
}

function Assert-Admin {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        # Restarting as administrator (UAC); the parameters unchanged
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
    # Installing: the helper under ProgramData, a scheduled task on every Windows start (with system rights)
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
    Write-Log "Installed ($result)"
    if ($result -eq "no-entry") {
        Show-Message (Get-Text "no_entry") "Warning"
    } else {
        Show-Message (Get-Text "installed")
    }
} catch {
    Write-Log "Hiba: $_"
    Show-Message ((Get-Text "failed") + "`n`n$_") "Error"
}
