@echo off
setlocal
title Repair Ehsan OpenJarvis Control Plane
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Repair-Ehsan-OpenJarvis.ps1" %*
set "ERR=%ERRORLEVEL%"
echo.
if not "%ERR%"=="0" (
  echo Repair exited with code %ERR%.
) else (
  echo Repair finished.
)
echo.
pause
exit /b %ERR%
