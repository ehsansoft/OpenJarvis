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
$BundleVersion = "0.1.0-alpha.4.1"

if (-not (Test-Path (Join-Path $InstallRoot ".git"))) {
    throw "OpenJarvis is not installed at $InstallRoot."
}

$UvExe = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $UvExe) { throw "uv was not found on PATH." }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$supportRoot = Join-Path $StateRoot "support"
$runDir = Join-Path $supportRoot "first-run-alpha4-$stamp"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

function Run-Capture {
    param(
        [string]$Name,
        [scriptblock]$Command
    )
    $path = Join-Path $runDir "$Name.txt"
    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $writer = New-Object System.IO.StreamWriter($path, $false, $utf8)
    Push-Location $InstallRoot
    try {
        & $Command 2>&1 | ForEach-Object {
            $line = $_.ToString()
            Write-Host $line
            $writer.WriteLine($line)
        }
        # Child native commands can leave a stale LASTEXITCODE in Windows
        # PowerShell 5.1 after scriptblock/pipeline scope transitions.
        # First-run is evidence collection, so successful completion of the
        # scriptblock itself is the reliable signal here.
        $code = 0
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

Run-Capture "01-doctor" {
    & $UvExe run jarvis doctor
} | Out-Null

Run-Capture "02-free-models" {
    & $UvExe run jarvis model free --json
} | Out-Null

Run-Capture "03-voicebox-scan" {
    & $UvExe run jarvis projects voicebox-scan --host "http://127.0.0.1:17493" --json
} | Out-Null

Run-Capture "04-voicebox-mcp" {
    & $UvExe run python "scripts\install\Check-Voicebox-MCP.py"
} | Out-Null

Run-Capture "05-machine-scan" {
    & $UvExe run jarvis projects machine-scan --json
} | Out-Null

Run-Capture "06-projects" {
    & $UvExe run jarvis projects scan $ProjectsRoot --max-depth 5 --json
} | Out-Null

Run-Capture "07-drive-inventory" {
    & $UvExe run jarvis projects inventory $InventoryRoot --json
} | Out-Null

Run-Capture "08-cleanup-scan" {
    & $UvExe run jarvis projects cleanup-scan $InventoryRoot --min-age-days 30 --json
} | Out-Null

if ($IncludeDuplicates) {
    Run-Capture "09-duplicates" {
        & $UvExe run jarvis projects duplicates $InventoryRoot --min-size-mb 10 --max-files 250000 --json
    } | Out-Null
}

$registry = Join-Path $StateRoot "registry"
if (Test-Path $registry) {
    Get-ChildItem $registry -Filter "*.json" -File -ErrorAction SilentlyContinue |
        ForEach-Object {
            Copy-Item $_.FullName (Join-Path $runDir $_.Name) -Force
        }
}

$configPath = Join-Path $StateRoot "config.toml"
$configDiag = Join-Path $runDir "10-config-diagnostics.txt"
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

$voiceboxPort = Join-Path $runDir "11-voicebox-port-17493.txt"
try {
    $connections = Get-NetTCPConnection -LocalPort 17493 -State Listen -ErrorAction Stop
    $lines = @()
    foreach ($connection in $connections) {
        $proc = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
        $lines += "Address=$($connection.LocalAddress) Port=$($connection.LocalPort) PID=$($connection.OwningProcess) Process=$($proc.ProcessName) Path=$($proc.Path)"
    }
    $lines | Set-Content $voiceboxPort -Encoding UTF8
} catch {
    "No listener details found for port 17493." |
        Set-Content $voiceboxPort -Encoding UTF8
}

$systemPath = Join-Path $runDir "12-system-summary.txt"
Push-Location $InstallRoot
try {
    @(
        "BundleVersion=$BundleVersion",
        "Git branch=$((git branch --show-current).Trim())",
        "Git commit=$((git rev-parse HEAD).Trim())",
        "",
        "Git status:"
    ) | Set-Content $systemPath -Encoding UTF8
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

$zip = Join-Path $supportRoot "openjarvis-first-run-alpha4.1-$stamp.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $runDir "*") -DestinationPath $zip -CompressionLevel Optimal

Write-Host ""
Write-Host "Alpha.4.1 support bundle ready:" -ForegroundColor Green
Write-Host $zip
Write-Host ""
Write-Host "It contains no OpenJarvis credential store."
