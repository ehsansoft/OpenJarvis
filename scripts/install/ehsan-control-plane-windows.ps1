param(
    [string]$RepoUrl = "https://github.com/ehsansoft/OpenJarvis.git",
    [string]$Branch = "feature/ehsan-control-plane-foundation",
    [string]$InstallRoot = "D:\AI-Tools\OpenJarvis",
    [string]$StateRoot = "D:\AI-Control\OpenJarvis",
    [string]$ProjectsRoot = "D:\Projects",
    [string]$InventoryRoot = "D:\",
    [switch]$InstallScanTask,
    [switch]$InitialInventory
)

$ErrorActionPreference = "Stop"
$InstallerVersion = "0.1.0-alpha.4.1"

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = [Environment]::ExpandEnvironmentVariables("$machine;$user")
}

function Ensure-Tool(
    [string]$Command,
    [string]$WingetId
) {
    $existing = Get-Command $Command -ErrorAction SilentlyContinue
    if ($existing) { return $existing.Source }

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "$Command is required. Install $WingetId and run again."
    }

    Write-Host "Installing $WingetId with winget..." -ForegroundColor Cyan
    & winget install --id $WingetId --silent --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to install $WingetId."
    }
    Refresh-Path

    $resolved = Get-Command $Command -ErrorAction SilentlyContinue
    if (-not $resolved) {
        throw "$WingetId installed but $Command is not visible yet."
    }
    return $resolved.Source
}

$GitExe = Ensure-Tool -Command "git" -WingetId "Git.Git"

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCommand) {
    $UvExe = $uvCommand.Source
} else {
    try {
        $UvExe = Ensure-Tool -Command "uv" -WingetId "astral-sh.uv"
    } catch {
        Write-Host "Winget uv install failed; trying Astral official installer..." -ForegroundColor Yellow
        Invoke-RestMethod -Uri "https://astral.sh/uv/install.ps1" | Invoke-Expression
        $uvDir = Join-Path $env:USERPROFILE ".local\bin"
        if (Test-Path (Join-Path $uvDir "uv.exe")) {
            $env:Path = "$uvDir;$env:Path"
        }
        $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
        if (-not $uvCommand) {
            throw "uv installation failed."
        }
        $UvExe = $uvCommand.Source
    }
}

New-Item -ItemType Directory -Force -Path (Split-Path $InstallRoot) | Out-Null
New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null
New-Item -ItemType Directory -Force -Path $ProjectsRoot | Out-Null

if (-not (Test-Path (Join-Path $InstallRoot ".git"))) {
    & $GitExe clone --branch $Branch --single-branch $RepoUrl $InstallRoot
    if ($LASTEXITCODE -ne 0) { throw "git clone failed." }
} else {
    Push-Location $InstallRoot
    try {
        & $GitExe fetch origin
        & $GitExe switch $Branch
        & $GitExe pull --ff-only origin $Branch
        if ($LASTEXITCODE -ne 0) { throw "git update failed." }
    } finally {
        Pop-Location
    }
}

[Environment]::SetEnvironmentVariable("OPENJARVIS_HOME", $StateRoot, "User")
$env:OPENJARVIS_HOME = $StateRoot

Push-Location $InstallRoot
try {
    & $UvExe python install 3.13
    if ($LASTEXITCODE -ne 0) { throw "Python 3.13 setup failed." }

    & $UvExe sync --python 3.13 --extra dev --extra server --extra desktop --group desktop-native
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed." }

    $ConfigPath = Join-Path $StateRoot "config.toml"
    $Preset = Join-Path $InstallRoot "configs\openjarvis\examples\ehsan-control-plane.toml"
    if (-not (Test-Path $ConfigPath)) {
        Copy-Item $Preset $ConfigPath
    } else {
        $backup = "$ConfigPath.pre-alpha4-backup"
        if (-not (Test-Path $backup)) { Copy-Item $ConfigPath $backup }
    }

    & $UvExe run python "scripts\install\Upgrade-Ehsan-Config.py" $ConfigPath
    if ($LASTEXITCODE -ne 0) { throw "Config migration failed." }

    & $UvExe run python -c "import pathlib,tomllib,sys; p=pathlib.Path(sys.argv[1]); tomllib.loads(p.read_text(encoding='utf-8-sig')); print('Config TOML OK:', p)" $ConfigPath
    if ($LASTEXITCODE -ne 0) { throw "Config validation failed." }

    & $UvExe run jarvis projects scan $ProjectsRoot --max-depth 5
    if ($LASTEXITCODE -ne 0) { throw "Project scan failed." }

    & $UvExe run jarvis projects machine-scan
    if ($LASTEXITCODE -ne 0) { throw "Machine scan failed." }

    Write-Host "Checking optional Voicebox service..." -ForegroundColor Cyan
    & $UvExe run jarvis projects voicebox-scan --host "http://127.0.0.1:17493"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Voicebox is not currently reachable; continuing." -ForegroundColor Yellow
    }

    & $UvExe run jarvis model free
    if ($LASTEXITCODE -ne 0) { throw "Model discovery failed." }

    if ($InitialInventory) {
        & $UvExe run jarvis projects inventory $InventoryRoot
        if ($LASTEXITCODE -ne 0) { throw "Initial drive inventory failed." }
    }

    if ($InstallScanTask) {
        & $UvExe run jarvis projects install-scan-task --root $InventoryRoot --daily-at 03:00
        if ($LASTEXITCODE -ne 0) { throw "Scheduled scan setup failed." }
    }

    Write-Host ""
    Write-Host "OpenJarvis control plane $InstallerVersion installed." -ForegroundColor Green
    Write-Host "Install root: $InstallRoot"
    Write-Host "State root:   $StateRoot"
    Write-Host "Projects:     $ProjectsRoot"
    if (Test-Path "C:\wamp64") {
        Write-Host "WampServer:   C:\wamp64 (detected)"
    }
    Write-Host "Voicebox:     http://127.0.0.1:17493 (optional)"
    Write-Host ""
    Write-Host "Nara free models: uv run jarvis model nara-key"
    Write-Host "Start API:        uv run jarvis serve"
    Write-Host "Editor API:       http://127.0.0.1:8000/router/v1"
    Write-Host "Coding alias:     free/code"
} finally {
    Pop-Location
}
