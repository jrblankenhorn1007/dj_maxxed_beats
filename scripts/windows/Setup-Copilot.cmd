@echo off
setlocal
title MaxxedBeats Copilot setup

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-copilot.ps1"
if errorlevel 1 (
    echo.
    echo Copilot setup did not finish. Follow the message above and double-click this file again.
)
echo.
pause
