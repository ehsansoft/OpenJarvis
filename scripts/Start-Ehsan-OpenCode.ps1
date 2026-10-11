param(
    [ValidateSet('models', 'chat', 'desktop')][string]$Mode = 'models',
    [string]$Directory = 'D:\AI-Tools\OpenJarvis',
    [string]$Prompt = 'Reply with LOCAL_EDITOR_OK. Do not use tools or read any files.',
    [string]$Model = 'openjarvis/local-code'
)

$ErrorActionPreference = 'Stop'
$appRoot = Join-Path $env:LOCALAPPDATA 'Programs\@opencodedesktop'
$cliPath = Join-Path $appRoot 'resources\opencode-cli.exe'
$desktopPath = Join-Path $appRoot 'OpenCode.exe'
if (-not (Test-Path -LiteralPath $cliPath)) { throw 'Bundled OpenCode CLI not found.' }
if (-not $Model.StartsWith('openjarvis/local-')) {
    throw 'This private development launcher requires an openjarvis/local-* model.'
}

# Process-local transport settings. Preserve remote proxies and the machine PATH.
$previousUpper = $env:NO_PROXY
$previousLower = $env:no_proxy
try {
    $bypass = @($previousUpper, '127.0.0.1', 'localhost', '::1') |
        Where-Object { $_ } | Select-Object -Unique
    $env:NO_PROXY = $bypass -join ','
    $env:no_proxy = $env:NO_PROXY
    if ($Mode -eq 'desktop') {
        Start-Process -FilePath $desktopPath -WindowStyle Hidden -WorkingDirectory $Directory
    } elseif ($Mode -eq 'models') {
        & $cliPath models --standalone
        if ($LASTEXITCODE -ne 0) { throw "OpenCode models failed: $LASTEXITCODE" }
    } else {
        Push-Location -LiteralPath $Directory
        try {
            & $cliPath run --standalone --model $Model --format json $Prompt
            if ($LASTEXITCODE -ne 0) { throw "OpenCode chat failed: $LASTEXITCODE" }
        } finally { Pop-Location }
    }
} finally {
    $env:NO_PROXY = $previousUpper
    $env:no_proxy = $previousLower
}
