@echo off
setlocal
title Ehsan OpenJarvis Control Plane Installer
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ehsan-control-plane-windows.ps1" %*
set "ERR=%ERRORLEVEL%"
echo.
if not "%ERR%"=="0" (
  echo Installation exited with code %ERR%.
) else (
  echo Installation finished.
)
echo.
pause
exit /b %ERR%
