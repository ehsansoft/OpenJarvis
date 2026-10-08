[CmdletBinding()]
param(
    [string]$InstallRoot = "D:\AI-Tools\OpenJarvis",
    [string]$StateRoot = "D:\AI-Control\OpenJarvis",
    [string]$ProjectsRoot = "D:\Projects",
    [string]$InventoryRoot = "D:\",
    [switch]$IncludeDuplicates
)

$ErrorActionPreference = "Continue"
$env:OPENJARVIS_HOME = $StateRoot

if (-not (Test-Path (Join-Path $InstallRoot ".git"))) {
    throw "OpenJarvis is not installed at $InstallRoot."
}

$UvExe = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $UvExe) { throw "uv was not found on PATH." }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$supportRoot = Join-Path $StateRoot "support"
$runDir = Join-Path $supportRoot "first-run-$stamp"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

function Run-Capture(
    [string]$Name,
    [string[]]$JarvisArgs
) {
    $path = Join-Path $runDir "$Name.txt"
    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $writer = New-Object System.IO.StreamWriter($path, $false, $utf8NoBom)
    Push-Location $InstallRoot
    try {
        & $UvExe run jarvis @JarvisArgs 2>&1 | ForEach-Object {
            $line = $_.ToString()
            Write-Host $line
            $writer.WriteLine($line)
        }
        $code = $LASTEXITCODE
    } catch {
        $line = $_.ToString()
        Write-Host $line -ForegroundColor Red
        $writer.WriteLine($line)
        $code = 1
    } finally {
        $writer.Dispose()
        Pop-Location
    }
    return $code
}

Run-Capture "01-doctor" @("doctor") | Out-Null
Run-Capture "02-free-models" @("model", "free", "--json") | Out-Null
Run-Capture "02a-voicebox-scan" @(
    "projects", "voicebox-scan",
    "--host", "http://127.0.0.1:17493",
    "--json"
) | Out-Null
Run-Capture "03-machine-scan" @("projects", "machine-scan", "--json") | Out-Null
Run-Capture "04-projects" @("projects", "scan", $ProjectsRoot, "--max-depth", "5", "--json") | Out-Null
Run-Capture "05-drive-inventory" @("projects", "inventory", $InventoryRoot, "--json") | Out-Null
Run-Capture "06-cleanup-scan" @("projects", "cleanup-scan", $InventoryRoot, "--min-age-days", "30", "--json") | Out-Null

if ($IncludeDuplicates) {
    Run-Capture "07-duplicates" @("projects", "duplicates", $InventoryRoot, "--min-size-mb", "10", "--max-files", "250000", "--json") | Out-Null
}

$registry = Join-Path $StateRoot "registry"
if (Test-Path $registry) {
    Get-ChildItem $registry -Filter "*.json" -File -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $runDir $_.Name) -Force
    }
}

$configDiag = Join-Path $runDir "07-config-diagnostics.txt"
$configPath = Join-Path $StateRoot "config.toml"
if (Test-Path $configPath) {
    $bytes = [System.IO.File]::ReadAllBytes($configPath)
    $hasBom = (
        $bytes.Length -ge 3 -and
        $bytes[0] -eq 0xEF -and
        $bytes[1] -eq 0xBB -and
        $bytes[2] -eq 0xBF
    )
    $sha = (Get-FileHash $configPath -Algorithm SHA256).Hash
    @(
        "Path: $configPath",
        "Bytes: $($bytes.Length)",
        "UTF8 BOM: $hasBom",
        "SHA256: $sha"
    ) | Set-Content $configDiag -Encoding ASCII
}

$voiceboxPortPath = Join-Path $runDir "07a-voicebox-port-17493.txt"
try {
    $listeners = Get-NetTCPConnection -LocalPort 17493 -State Listen -ErrorAction Stop
    foreach ($listener in $listeners) {
        $proc = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
        "Address=$($listener.LocalAddress) Port=$($listener.LocalPort) PID=$($listener.OwningProcess) Process=$($proc.ProcessName) Path=$($proc.Path)" |
            Add-Content $voiceboxPortPath -Encoding UTF8
    }
} catch {
    "No listener details found for port 17493." | Set-Content $voiceboxPortPath -Encoding UTF8
}

$voiceboxCache = "D:\AI-Control\caches\huggingface\hub"
if (Test-Path $voiceboxCache) {
    Get-ChildItem $voiceboxCache -Directory -ErrorAction SilentlyContinue |
        Select-Object Name, FullName, LastWriteTime |
        ConvertTo-Json -Depth 4 |
        Set-Content (Join-Path $runDir "07b-voicebox-cache-folders.json") -Encoding UTF8
}
$systemPath = Join-Path $runDir "08-system-summary.txt"
Push-Location $InstallRoot
try {
    "Git branch / commit:" | Set-Content $systemPath -Encoding UTF8
    git branch --show-current 2>&1 | Add-Content $systemPath
    git rev-parse HEAD 2>&1 | Add-Content $systemPath
    "" | Add-Content $systemPath
    "Git status:" | Add-Content $systemPath
    git status --short 2>&1 | Add-Content $systemPath
    "" | Add-Content $systemPath
    "Ollama list:" | Add-Content $systemPath
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        ollama list 2>&1 | Add-Content $systemPath
    } else {
        "ollama not on PATH" | Add-Content $systemPath
    }
} finally {
    Pop-Location
}

$zip = Join-Path $supportRoot "openjarvis-first-run-$stamp.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $runDir "*") -DestinationPath $zip -CompressionLevel Optimal

Write-Host ""
Write-Host "First-run bundle ready:" -ForegroundColor Green
Write-Host $zip
Write-Host ""
Write-Host "Attach that ZIP to ChatGPT. It intentionally excludes credentials.toml."
