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
$InstallerVersion = "0.1.0-alpha.2"

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
    $Preset = Join-Path $InstallRoot "configs\openjarvis\examples\ehsan-control-plane.toml"
    if (-not (Test-Path $ConfigPath)) {
        Copy-Item $Preset $ConfigPath
    } else {
        $backup = "$ConfigPath.pre-alpha2-backup"
        if (-not (Test-Path $backup)) {
            Copy-Item $ConfigPath $backup
        }
    }

    # Normalize paths and repair alpha.1 configs. Windows PowerShell 5.1
    # writes a UTF-8 BOM for Set-Content -Encoding utf8; Python tomllib
    # rejects that BOM. Write UTF-8 without BOM explicitly.
    $Text = Get-Content $ConfigPath -Raw
    $Text = $Text.Replace("D:\\Projects", $ProjectsRoot.Replace("\", "\\"))
    $Text = $Text.Replace(
        "D:\\AI-Control\\registry",
        (Join-Path $StateRoot "registry").Replace("\", "\\")
    )
    $Text = $Text.Replace(
        'default_model = "qwen3:4b"',
        'default_model = ""'
    )
    $Text = $Text.Replace(
        'model_code = "qwen3:4b"',
        'model_code = "free/code"'
    )
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($ConfigPath, $Text, $Utf8NoBom)

    # Validate the exact config the application will load before scans.
    & $UvExe run python -c "import pathlib,tomllib,sys; p=pathlib.Path(sys.argv[1]); tomllib.loads(p.read_text(encoding='utf-8-sig')); print('Config TOML OK:', p)" $ConfigPath
    if ($LASTEXITCODE -ne 0) {
        throw "Config validation failed: $ConfigPath"
    }

    function Run-JarvisChecked {
        param([Parameter(ValueFromRemainingArguments=$true)][string[]]$CommandArgs)
        & $UvExe run jarvis @CommandArgs
        if ($LASTEXITCODE -ne 0) {
            throw "jarvis command failed: $($CommandArgs -join ' ')"
        }
    }
    Run-JarvisChecked projects scan $ProjectsRoot --max-depth 5
    Run-JarvisChecked projects machine-scan
    Run-JarvisChecked model free

    if ($InitialInventory) {
        Run-JarvisChecked projects inventory $InventoryRoot
    }

    if ($InstallScanTask) {
        Run-JarvisChecked projects install-scan-task --root $InventoryRoot --daily-at 03:00
    }

    Write-Host ""
    Write-Host "OpenJarvis control plane $InstallerVersion installed." -ForegroundColor Green
    Write-Host "Install root: $InstallRoot"
    Write-Host "State root:   $StateRoot"
    Write-Host "Projects:     $ProjectsRoot"
    if (Test-Path "C:\wamp64") {
        Write-Host "WampServer:   C:\wamp64 (detected)"
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
