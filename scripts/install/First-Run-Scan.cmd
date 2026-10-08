@echo off
setlocal
title Ehsan OpenJarvis First Run Scan
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0First-Run-Scan.ps1" %*
set "ERR=%ERRORLEVEL%"
echo.
if not "%ERR%"=="0" echo First-run scan exited with code %ERR%.
pause
exit /b %ERR%
