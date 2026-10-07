@echo off
setlocal
title MaxxedBeats installer

echo MaxxedBeats will install the music assistant and then offer to set up GitHub Copilot.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 goto failed

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-copilot.ps1"
if errorlevel 1 goto failed

echo.
echo Installation finished. Open SuperCollider and follow the next steps above.
goto done

:failed
echo.
echo Setup did not finish. Follow the message above, fix that item, and double-click this file again.

:done
echo.
pause
