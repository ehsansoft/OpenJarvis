@echo off
setlocal
title Voicebox Local Model Probe
powershell.exe -NoProfile -Command "Unblock-File -LiteralPath '%~dp0Voicebox-Probe.ps1'" >nul 2>&1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Voicebox-Probe.ps1" %*
set "ERR=%ERRORLEVEL%"
echo.
pause
exit /b %ERR%
