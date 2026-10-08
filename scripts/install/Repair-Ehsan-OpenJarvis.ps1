[CmdletBinding()]
param(
    [string]$InstallRoot = "D:\AI-Tools\OpenJarvis",
    [string]$StateRoot = "D:\AI-Control\OpenJarvis",
    [string]$Branch = "feature/ehsan-control-plane-foundation"
)

$ErrorActionPreference = "Stop"
$env:OPENJARVIS_HOME = $StateRoot

if (-not (Test-Path (Join-Path $InstallRoot ".git"))) {
    throw "OpenJarvis checkout not found at $InstallRoot."
}

$git = (Get-Command git -ErrorAction SilentlyContinue).Source
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $git) { throw "git is not on PATH." }
if (-not $uv) { throw "uv is not on PATH." }

Push-Location $InstallRoot
try {
    Write-Host "Updating control-plane branch..." -ForegroundColor Cyan
    & $git fetch origin
    & $git switch $Branch
    & $git pull --ff-only origin $Branch
    if ($LASTEXITCODE -ne 0) { throw "git update failed." }

    & $uv python install 3.13
    & $uv sync --python 3.13 --extra dev --extra server --extra desktop
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed." }

    $config = Join-Path $StateRoot "config.toml"
    $preset = Join-Path $InstallRoot "configs\openjarvis\examples\ehsan-control-plane.toml"
    if (-not (Test-Path $config)) { Copy-Item $preset $config }

    $backup = "$config.pre-alpha2-backup"
    if ((Test-Path $config) -and -not (Test-Path $backup)) {
        Copy-Item $config $backup
    }

    $text = Get-Content $config -Raw
    $text = $text.Replace(
        "D:\\AI-Control\\registry",
        (Join-Path $StateRoot "registry").Replace("\", "\\")
    )
    $text = $text.Replace('default_model = "qwen3:4b"', 'default_model = ""')
    $text = $text.Replace('model_code = "qwen3:4b"', 'model_code = "free/code"')
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($config, $text, $utf8NoBom)

    Write-Host "Validating repaired configuration..." -ForegroundColor Cyan
    & $uv run python -c "import pathlib,tomllib,sys; p=pathlib.Path(sys.argv[1]); tomllib.loads(p.read_text(encoding='utf-8-sig')); print('Config TOML OK:', p)" $config
    if ($LASTEXITCODE -ne 0) { throw "Config is still invalid." }

    Write-Host "Running doctor..." -ForegroundColor Cyan
    & $uv run jarvis doctor
    Write-Host "Running machine scan..." -ForegroundColor Cyan
    & $uv run jarvis projects machine-scan
    Write-Host "Reading free model pool..." -ForegroundColor Cyan
    & $uv run jarvis model free

    Write-Host ""
    Write-Host "Repair completed. Run First-Run-Scan.cmd next." -ForegroundColor Green
} finally {
    Pop-Location
}
