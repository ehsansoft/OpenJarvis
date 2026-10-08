[CmdletBinding()]
param(
    [string]$InstallRoot = "D:\AI-Tools\OpenJarvis",
    [string]$StateRoot = "D:\AI-Control\OpenJarvis",
    [string]$ProjectsRoot = "D:\Projects",
    [string]$Branch = "feature/ehsan-control-plane-foundation",
    [switch]$Cleanup
)

$ErrorActionPreference = "Stop"
$env:OPENJARVIS_HOME = $StateRoot

function Invoke-NativeChecked {
    param(
        [string]$Label,
        [string]$FilePath,
        [string[]]$Arguments
    )
    Write-Host ""
    Write-Host "=== $Label ===" -ForegroundColor Cyan
    & $FilePath @Arguments
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "$Label failed with exit code $code."
    }
}

$git = (Get-Command git -ErrorAction SilentlyContinue).Source
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $git) { throw "git is not on PATH." }
if (-not $uv) { throw "uv is not on PATH." }
if (-not (Test-Path (Join-Path $InstallRoot ".git"))) {
    throw "OpenJarvis is not installed at $InstallRoot."
}

Push-Location $InstallRoot
try {
    Invoke-NativeChecked "git fetch" $git @("fetch", "origin")
    Invoke-NativeChecked "git switch" $git @("switch", $Branch)
    Invoke-NativeChecked "git pull" $git @(
        "pull", "--ff-only", "origin", $Branch
    )
    Invoke-NativeChecked "python 3.13" $uv @(
        "python", "install", "3.13"
    )
    Invoke-NativeChecked "dependency sync" $uv @(
        "sync",
        "--python", "3.13",
        "--extra", "dev",
        "--extra", "server",
        "--extra", "desktop"
    )

    $args = @(
        "run", "python",
        "scripts\install\Finalize-Ehsan-Setup.py",
        "--repo", $InstallRoot,
        "--state", $StateRoot,
        "--projects", $ProjectsRoot
    )
    if ($Cleanup) { $args += "--cleanup" }
    Invoke-NativeChecked "final verification" $uv $args
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "OpenJarvis alpha.4.3 setup is finalized." -ForegroundColor Green
Write-Host "Start server: D:\AI-Tools\OpenJarvis\scripts\install\Start-Ehsan-OpenJarvis.cmd"
Write-Host "Editor API: http://127.0.0.1:8000/router/v1"
Write-Host "Model alias: free/code"
