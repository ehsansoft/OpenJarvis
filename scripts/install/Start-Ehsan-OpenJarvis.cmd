@echo off
setlocal
set "REPO=D:\AI-Tools\OpenJarvis"
set "OPENJARVIS_HOME=D:\AI-Control\OpenJarvis"
if not exist "%REPO%\.git" (
  echo OpenJarvis is not installed at %REPO%.
  echo Run Install-Ehsan-OpenJarvis.cmd first.
  pause
  exit /b 1
)
cd /d "%REPO%"
title Ehsan OpenJarvis Control Plane
uv run jarvis serve --host 127.0.0.1 --port 8000
pause
