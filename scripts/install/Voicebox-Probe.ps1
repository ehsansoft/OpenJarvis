[CmdletBinding()]
param(
    [string]$VoiceboxHost = "http://127.0.0.1:17493",
    [string]$OutputRoot = "D:\AI-Control\OpenJarvis\support",
    [string]$InstallRoot = "D:\AI-Tools\OpenJarvis"
)

$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dir = Join-Path $OutputRoot "voicebox-probe-alpha4-$stamp"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

Write-Host "Voicebox probe: $VoiceboxHost" -ForegroundColor Cyan

try {
    $health = Invoke-RestMethod -Uri "$VoiceboxHost/health" -TimeoutSec 8
    $status = Invoke-RestMethod -Uri "$VoiceboxHost/models/status" -TimeoutSec 15
    $profiles = Invoke-RestMethod -Uri "$VoiceboxHost/profiles" -TimeoutSec 10
} catch {
    Write-Host "Voicebox API probe failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Keep the Voicebox desktop app open and verify port 17493."
    exit 2
}

$health | ConvertTo-Json -Depth 12 |
    Set-Content (Join-Path $dir "health.json") -Encoding UTF8
$status | ConvertTo-Json -Depth 20 |
    Set-Content (Join-Path $dir "models-status.json") -Encoding UTF8
$profiles | ConvertTo-Json -Depth 20 |
    Set-Content (Join-Path $dir "profiles.json") -Encoding UTF8

$models = @($status.models)
$downloaded = @($models | Where-Object { $_.downloaded })
$loaded = @($models | Where-Object { $_.loaded })
$profileList = @($profiles)

Write-Host "Registered models: $($models.Count)"
Write-Host "Downloaded:        $($downloaded.Count)"
Write-Host "Loaded:            $($loaded.Count)"
Write-Host "Voice profiles:    $($profileList.Count)"
Write-Host ""

foreach ($model in $models) {
    $name = if ($model.display_name) {
        $model.display_name
    } else {
        $model.model_name
    }
    Write-Host (
        "- {0} downloaded={1} loaded={2} repo={3}" -f
        $name,
        $model.downloaded,
        $model.loaded,
        $model.hf_repo_id
    )
}

$cache = "D:\AI-Control\caches\huggingface\hub"
if (Test-Path $cache) {
    Get-ChildItem $cache -Directory -ErrorAction SilentlyContinue |
        Select-Object Name, FullName, LastWriteTime |
        ConvertTo-Json -Depth 4 |
        Set-Content (Join-Path $dir "hf-cache-folders.json") -Encoding UTF8
}

try {
    $connections = Get-NetTCPConnection -LocalPort 17493 -State Listen -ErrorAction Stop
    $portRows = @()
    $exposed = $false
    foreach ($connection in $connections) {
        $proc = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
        if ($connection.LocalAddress -eq "0.0.0.0" -or $connection.LocalAddress -eq "::") {
            $exposed = $true
        }
        $portRows += [PSCustomObject]@{
            LocalAddress = $connection.LocalAddress
            LocalPort = $connection.LocalPort
            OwningProcess = $connection.OwningProcess
            ProcessName = if ($proc) { $proc.ProcessName } else { "" }
            ProcessPath = if ($proc) { $proc.Path } else { "" }
        }
    }
    $portRows | ConvertTo-Json -Depth 5 |
        Set-Content (Join-Path $dir "port-17493.json") -Encoding UTF8
    if ($exposed) {
        Write-Host ""
        Write-Host "SECURITY WARNING: Voicebox is listening on all interfaces." -ForegroundColor Yellow
        Write-Host "The local Voicebox API has no built-in auth in this version."
        Write-Host "Do not expose TCP 17493 to untrusted networks."
    }
} catch {
    "No listener details found." |
        Set-Content (Join-Path $dir "port-17493.txt") -Encoding UTF8
}

if (Test-Path (Join-Path $InstallRoot ".git")) {
    $uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
    if ($uv) {
        Push-Location $InstallRoot
        try {
            & $uv run python "scripts\install\Check-Voicebox-MCP.py" 2>&1 |
                Set-Content (Join-Path $dir "openjarvis-mcp-discovery.txt") -Encoding UTF8
        } finally {
            Pop-Location
        }
    }
}

$zip = Join-Path $OutputRoot "voicebox-probe-alpha4-$stamp.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $dir "*") -DestinationPath $zip -CompressionLevel Optimal

Write-Host ""
Write-Host "Voicebox alpha.4 probe bundle:" -ForegroundColor Green
Write-Host $zip
