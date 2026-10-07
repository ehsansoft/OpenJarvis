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

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

Require-Command git
Require-Command uv

New-Item -ItemType Directory -Force -Path (Split-Path $InstallRoot) | Out-Null
New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null
New-Item -ItemType Directory -Force -Path $ProjectsRoot | Out-Null

if (-not (Test-Path (Join-Path $InstallRoot ".git"))) {
    git clone --branch $Branch --single-branch $RepoUrl $InstallRoot
} else {
    Push-Location $InstallRoot
    try {
        git fetch origin
        git switch $Branch
        git pull --ff-only origin $Branch
    } finally {
        Pop-Location
    }
}

[Environment]::SetEnvironmentVariable("OPENJARVIS_HOME", $StateRoot, "User")
$env:OPENJARVIS_HOME = $StateRoot

Push-Location $InstallRoot
try {
    uv sync --extra dev --extra server --extra desktop

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
        Set-Content -Path $ConfigPath -Value $Text -Encoding utf8
    }

    uv run jarvis projects scan $ProjectsRoot --max-depth 5
    uv run jarvis model free

    if ($InitialInventory) {
        uv run jarvis projects inventory $InventoryRoot
    }

    if ($InstallScanTask) {
        uv run jarvis projects install-scan-task --root $InventoryRoot --daily-at 03:00
    }

    Write-Host ""
    Write-Host "OpenJarvis control plane installed." -ForegroundColor Green
    Write-Host "Install root: $InstallRoot"
    Write-Host "State root:   $StateRoot"
    Write-Host "Projects:     $ProjectsRoot"
    Write-Host ""
    Write-Host "To enable rotating NaraRouter free models securely:"
    Write-Host "  uv run jarvis model nara-key"
    Write-Host "Then run: uv run jarvis model free"
    Write-Host "Start API: uv run jarvis start"
    Write-Host "Personal API: http://127.0.0.1:8000/v1"
    Write-Host "Editor API:   http://127.0.0.1:8000/router/v1"
    Write-Host "Editor model alias: free/code"
} finally {
    Pop-Location
}
