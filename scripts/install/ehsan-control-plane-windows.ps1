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
        throw "$WingetId installed but $Command is not visible yet. Re-open PowerShell."
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
            throw "uv installation failed. Re-open PowerShell and run installer again."
        }
        $UvExe = $uvCommand.Source
    }
}

New-Item -ItemType Directory -Force -Path (Split-Path $InstallRoot) | Out-Null
New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null
New-Item -ItemType Directory -Force -Path $ProjectsRoot | Out-Null

if (-not (Test-Path (Join-Path $InstallRoot ".git"))) {
    & $GitExe clone --branch $Branch --single-branch $RepoUrl $InstallRoot
} else {
    Push-Location $InstallRoot
    try {
        & $GitExe fetch origin
        & $GitExe switch $Branch
        & $GitExe pull --ff-only origin $Branch
    } finally {
        Pop-Location
    }
}

[Environment]::SetEnvironmentVariable("OPENJARVIS_HOME", $StateRoot, "User")
$env:OPENJARVIS_HOME = $StateRoot

Push-Location $InstallRoot
try {
    & $UvExe python install 3.13
    if ($LASTEXITCODE -ne 0) {
        throw "uv could not install/manage Python 3.13."
    }

    & $UvExe sync --python 3.13 --extra dev --extra server --extra desktop
    if ($LASTEXITCODE -ne 0) {
        throw "uv sync failed."
    }

    $ConfigPath = Join-Path $StateRoot "config.toml"
    if (-not (Test-Path $ConfigPath)) {
        $Preset = Join-Path $InstallRoot "configs\openjarvis\examples\ehsan-control-plane.toml"
        Copy-Item $Preset $ConfigPath
        $Text = Get-Content $ConfigPath -Raw
        $Text = $Text.Replace("D:\\Projects", $ProjectsRoot.Replace("\", "\\"))
        $Text = $Text.Replace(
            "D:\\AI-Control\\registry\\projects.json",
            (Join-Path $StateRoot "registry\projects.json").Replace("\", "\\")
        )
        $Text = $Text.Replace(
            "D:\\AI-Control\\registry\\drive-inventory.json",
            (Join-Path $StateRoot "registry\drive-inventory.json").Replace("\", "\\")
        )
        $Text = $Text.Replace(
            "D:\\AI-Control\\registry\\machine-inventory.json",
            (Join-Path $StateRoot "registry\machine-inventory.json").Replace("\", "\\")
        )
        $Text = $Text.Replace(
            "D:\\AI-Control\\registry\\cleanup-report.json",
            (Join-Path $StateRoot "registry\cleanup-report.json").Replace("\", "\\")
        )
        $Text = $Text.Replace(
            "D:\\AI-Control\\registry\\duplicate-report.json",
            (Join-Path $StateRoot "registry\duplicate-report.json").Replace("\", "\\")
        )
        Set-Content -Path $ConfigPath -Value $Text -Encoding utf8
    }

    & $UvExe run jarvis projects scan $ProjectsRoot --max-depth 5
    & $UvExe run jarvis projects machine-scan
    & $UvExe run jarvis model free

    if ($InitialInventory) {
        & $UvExe run jarvis projects inventory $InventoryRoot
    }

    if ($InstallScanTask) {
        & $UvExe run jarvis projects install-scan-task --root $InventoryRoot --daily-at 03:00
    }

    Write-Host ""
    Write-Host "OpenJarvis control plane installed." -ForegroundColor Green
    Write-Host "Install root: $InstallRoot"
    Write-Host "State root:   $StateRoot"
    Write-Host "Projects:     $ProjectsRoot"
    if (Test-Path "C:\\wamp64") {
        Write-Host "WampServer:   C:\\wamp64 (detected)"
    }
    Write-Host ""
    Write-Host "To enable rotating NaraRouter free models securely:"
    Write-Host "  uv run jarvis model nara-key"
    Write-Host "Then run: uv run jarvis model free"
    Write-Host "Start API: uv run jarvis serve"
    Write-Host "Personal API: http://127.0.0.1:8000/v1"
    Write-Host "Editor API:   http://127.0.0.1:8000/router/v1"
    Write-Host "Editor model alias: free/code"
} finally {
    Pop-Location
}
