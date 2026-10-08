@echo off
setlocal
title Finalize Ehsan OpenJarvis Alpha.4.2
powershell.exe -NoProfile -Command "Unblock-File -LiteralPath '%~dp0Finalize-Ehsan-OpenJarvis.ps1'" >nul 2>&1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Finalize-Ehsan-OpenJarvis.ps1" %*
set "ERR=%ERRORLEVEL%"
echo.
if not "%ERR%"=="0" (
  echo Finalization exited with code %ERR%.
) else (
  echo Finalization finished successfully.
)
echo.
pause
exit /b %ERR%
