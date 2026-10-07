@echo off
setlocal
title MaxxedBeats uninstaller

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
if errorlevel 1 (
    echo.
    echo Uninstall stopped. Follow the message above; unmarked folders are never removed.
)
echo.
pause
