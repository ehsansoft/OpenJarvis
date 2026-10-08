[CmdletBinding()]
param(
    [string]$InstallRoot = "D:\AI-Tools\OpenJarvis",
    [string]$StateRoot = "D:\AI-Control\OpenJarvis",
    [string]$ProjectsRoot = "D:\Projects",
    [string]$Branch = "feature/ehsan-control-plane-foundation",
    [switch]$Cleanup
)

$ErrorActionPreference = "Stop"
$RepairVersion = "0.1.0-alpha.4.2"
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

if (-not (Test-Path (Join-Path $InstallRoot ".git"))) {
    throw "OpenJarvis checkout not found at $InstallRoot."
}

$gitCommand = Get-Command git -ErrorAction SilentlyContinue
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if (-not $gitCommand) { throw "git is not on PATH." }
if (-not $uvCommand) { throw "uv is not on PATH." }

$git = $gitCommand.Source
$uv = $uvCommand.Source

Push-Location $InstallRoot
try {
    # Do not wrap native Git commands in child scriptblocks/pipelines.
    # Windows PowerShell 5.1 can otherwise surface a stale LASTEXITCODE.
    Invoke-NativeChecked "01-git-fetch" $git @("fetch", "origin")
    Invoke-NativeChecked "02-git-switch" $git @("switch", $Branch)
    Invoke-NativeChecked "03-git-pull" $git @(
        "pull", "--ff-only", "origin", $Branch
    )

    Invoke-NativeChecked "04-python" $uv @("python", "install", "3.13")
    Invoke-NativeChecked "05-sync" $uv @(
        "sync",
        "--python", "3.13",
        "--extra", "dev",
        "--extra", "server",
        "--extra", "desktop"
    )

    $finalizer = Join-Path $InstallRoot "scripts\install\Finalize-Ehsan-Setup.py"
    if (-not (Test-Path $finalizer)) {
        throw "Finalizer not found after update: $finalizer"
    }

    $arguments = @(
        "run", "python", $finalizer,
        "--repo", $InstallRoot,
        "--state", $StateRoot,
        "--projects", $ProjectsRoot
    )
    if ($Cleanup) {
        $arguments += "--cleanup"
    }

    Invoke-NativeChecked "06-finalize" $uv $arguments
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "OpenJarvis $RepairVersion setup finalized." -ForegroundColor Green
Write-Host "Editor API: http://127.0.0.1:8000/router/v1"
Write-Host "Editor model: free/code"
Write-Host "Support bundles: $StateRoot\support"
