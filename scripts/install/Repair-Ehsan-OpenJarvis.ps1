[CmdletBinding()]
param(
    [string]$InstallRoot = "D:\AI-Tools\OpenJarvis",
    [string]$StateRoot = "D:\AI-Control\OpenJarvis",
    [string]$ProjectsRoot = "D:\Projects",
    [string]$Branch = "feature/ehsan-control-plane-foundation",
    [string]$VoiceboxHost = "http://127.0.0.1:17493"
)

$ErrorActionPreference = "Stop"
$RepairVersion = "0.1.0-alpha.4"
$env:OPENJARVIS_HOME = $StateRoot

if (-not (Test-Path (Join-Path $InstallRoot ".git"))) {
    throw "OpenJarvis checkout not found at $InstallRoot."
}

$git = (Get-Command git -ErrorAction SilentlyContinue).Source
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $git) { throw "git is not on PATH." }
if (-not $uv) { throw "uv is not on PATH." }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$supportRoot = Join-Path $StateRoot "support"
$runDir = Join-Path $supportRoot "repair-alpha4-$stamp"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

function Run-Capture {
    param(
        [string]$Name,
        [scriptblock]$Command,
        [switch]$AllowFailure
    )
    $path = Join-Path $runDir "$Name.txt"
    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $writer = New-Object System.IO.StreamWriter($path, $false, $utf8)
    try {
        & $Command 2>&1 | ForEach-Object {
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
    }
    if ($code -ne 0 -and -not $AllowFailure) {
        throw "$Name failed with exit code $code."
    }
    return $code
}

Push-Location $InstallRoot
try {
    Run-Capture "01-git-update" {
        & $git fetch origin
        if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
        & $git switch $Branch
        if ($LASTEXITCODE -ne 0) { throw "git switch failed" }
        & $git pull --ff-only origin $Branch
        if ($LASTEXITCODE -ne 0) { throw "git pull failed" }
    } | Out-Null

    Run-Capture "02-uv-sync" {
        & $uv python install 3.13
        if ($LASTEXITCODE -ne 0) { throw "uv python install failed" }
        & $uv sync --python 3.13 --extra dev --extra server --extra desktop
        if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
    } | Out-Null

    $config = Join-Path $StateRoot "config.toml"
    $preset = Join-Path $InstallRoot "configs\openjarvis\examples\ehsan-control-plane.toml"
    if (-not (Test-Path $config)) {
        Copy-Item $preset $config
    }
    $backup = "$config.pre-alpha4-backup"
    if (-not (Test-Path $backup)) {
        Copy-Item $config $backup
    }

    Run-Capture "03-config-upgrade" {
        & $uv run python "scripts\install\Upgrade-Ehsan-Config.py" $config
    } | Out-Null

    Run-Capture "04-config-validate" {
        & $uv run python -c "import pathlib,tomllib,sys; p=pathlib.Path(sys.argv[1]); tomllib.loads(p.read_text(encoding='utf-8-sig')); print('Config TOML OK:', p)" $config
    } | Out-Null

    Run-Capture "05-alpha4-tests" {
        & $uv run pytest tests/core/test_config.py tests/core/test_control_plane_config.py tests/core/test_ehsan_control_plane_upgrade.py tests/engine/test_nararouter.py tests/intelligence/test_free_pool.py tests/projects/test_discovery.py tests/projects/test_inventory.py tests/projects/test_machine_inventory.py tests/projects/test_hygiene.py tests/tools/test_voicebox_status.py tests/speech/test_voicebox_stt.py tests/speech/test_discovery.py tests/mcp/test_transport.py tests/mcp/test_loader.py -q
    } | Out-Null

    Run-Capture "06-doctor" {
        & $uv run jarvis doctor
    } -AllowFailure | Out-Null

    Run-Capture "07-voicebox-scan" {
        & $uv run jarvis projects voicebox-scan --host $VoiceboxHost
    } -AllowFailure | Out-Null

    Run-Capture "08-voicebox-mcp" {
        & $uv run python "scripts\install\Check-Voicebox-MCP.py"
    } -AllowFailure | Out-Null

    Run-Capture "09-machine-scan" {
        & $uv run jarvis projects machine-scan
    } | Out-Null

    Run-Capture "10-free-models" {
        & $uv run jarvis model free
    } | Out-Null

    Run-Capture "11-project-rescan" {
        & $uv run jarvis projects scan $ProjectsRoot --max-depth 5
    } | Out-Null

    $registry = Join-Path $StateRoot "registry"
    if (Test-Path $registry) {
        Get-ChildItem $registry -Filter "*.json" -File -ErrorAction SilentlyContinue |
            ForEach-Object {
                Copy-Item $_.FullName (Join-Path $runDir $_.Name) -Force
            }
    }

    @(
        "RepairVersion=$RepairVersion",
        "Branch=$Branch",
        "Commit=$((& $git rev-parse HEAD).Trim())",
        "VoiceboxHost=$VoiceboxHost",
        "Config=$config",
        "ConfigBackup=$backup"
    ) | Set-Content (Join-Path $runDir "12-repair-summary.txt") -Encoding UTF8
} finally {
    Pop-Location
}

$zip = Join-Path $supportRoot "openjarvis-repair-alpha4-$stamp.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $runDir "*") -DestinationPath $zip -CompressionLevel Optimal

Write-Host ""
Write-Host "Repair alpha.4 completed." -ForegroundColor Green
Write-Host "Support ZIP: $zip"
Write-Host "Next: run First-Run-Scan.cmd with Voicebox open."
