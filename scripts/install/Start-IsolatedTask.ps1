# Start-IsolatedTask.ps1 - FIX: run long jobs detached from agent shells
# (survives opencode/server restarts; logs to support\isolated-tasks).
# Usage: .\Start-IsolatedTask.ps1 -Name fleet-smoke -CommandLine "<powershell command>"
param(
  [Parameter(Mandatory)][string]$Name,
  [Parameter(Mandatory)][string]$CommandLine
)
$ErrorActionPreference = 'Stop'
$dir = 'D:\AI-Control\OpenJarvis\support\isolated-tasks'
New-Item -ItemType Directory -Path $dir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log  = Join-Path $dir "$Name-$stamp.log"
$ps1  = Join-Path $dir "$Name-run.ps1"
$lines = @(
  "param()"
  "`$ErrorActionPreference = 'Continue'"
  "Invoke-Expression @'"
  $CommandLine
  "'@ *>&1 | Tee-Object -FilePath '$log'"
)
$lines | Set-Content $ps1 -Encoding UTF8
$tn = "Jarvis-$Name"
schtasks /create /tn $tn /tr "powershell -NoProfile -ExecutionPolicy Bypass -File `"$ps1`"" /sc once /st 23:59 /f | Out-Null
schtasks /run /tn $tn | Out-Null
"isolated task '$tn' launched; log: $log"
