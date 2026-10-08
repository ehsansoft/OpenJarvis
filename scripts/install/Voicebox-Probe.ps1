[CmdletBinding()]
param(
    [string]$VoiceboxHost = "http://127.0.0.1:17493",
    [string]$OutputRoot = "D:\AI-Control\OpenJarvis\support"
)

$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dir = Join-Path $OutputRoot "voicebox-probe-$stamp"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

Write-Host "Voicebox probe: $VoiceboxHost" -ForegroundColor Cyan

try {
    $health = Invoke-RestMethod -Uri "$VoiceboxHost/health" -TimeoutSec 8
    $status = Invoke-RestMethod -Uri "$VoiceboxHost/models/status" -TimeoutSec 15
} catch {
    Write-Host "Voicebox API probe failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Make sure the Voicebox app/backend is running and port 17493 is listening."
    exit 2
}

$health | ConvertTo-Json -Depth 12 | Set-Content (Join-Path $dir "health.json") -Encoding UTF8
$status | ConvertTo-Json -Depth 20 | Set-Content (Join-Path $dir "models-status.json") -Encoding UTF8

$models = @($status.models)
$downloaded = @($models | Where-Object { $_.downloaded })
$loaded = @($models | Where-Object { $_.loaded })

Write-Host "Registered: $($models.Count)"
Write-Host "Downloaded: $($downloaded.Count)"
Write-Host "Loaded:     $($loaded.Count)"
Write-Host ""
foreach ($model in $models) {
    $name = if ($model.display_name) { $model.display_name } else { $model.model_name }
    Write-Host ("- {0} [{1}] downloaded={2} loaded={3}" -f $name, $model.engine, $model.downloaded, $model.loaded)
}

$cache = "D:\AI-Control\caches\huggingface\hub"
if (Test-Path $cache) {
    Get-ChildItem $cache -Directory -ErrorAction SilentlyContinue |
        Select-Object Name, FullName, LastWriteTime |
        ConvertTo-Json -Depth 4 |
        Set-Content (Join-Path $dir "hf-cache-folders.json") -Encoding UTF8
    Write-Host ""
    Write-Host "Detected configured cache: $cache"
}

try {
    Get-NetTCPConnection -LocalPort 17493 -State Listen -ErrorAction Stop |
        Select-Object LocalAddress, LocalPort, OwningProcess |
        Format-List | Out-String |
        Set-Content (Join-Path $dir "port-17493.txt") -Encoding UTF8
} catch {
    "No listener details found." | Set-Content (Join-Path $dir "port-17493.txt") -Encoding UTF8
}

$zip = Join-Path $OutputRoot "voicebox-probe-$stamp.zip"
Compress-Archive -Path (Join-Path $dir "*") -DestinationPath $zip -CompressionLevel Optimal
Write-Host ""
Write-Host "Voicebox probe bundle:" -ForegroundColor Green
Write-Host $zip
