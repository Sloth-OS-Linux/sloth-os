@echo off
rem Sloth OS boot order helper (Windows side). Run it once (double-click); it asks for administrator approval.
rem Uninstall: sloth-boot-order.ps1 -Uninstall
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sloth-boot-order.ps1" -Install
