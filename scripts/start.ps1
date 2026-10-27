param(
    [int]$Port = 8765,
    [switch]$NoBrowser,
    [string]$LaunchInfoPath
)
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path $PSScriptRoot -Parent
$pythonExe = Join-Path $projectDir '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Run scripts/setup.ps1 first. A Python 3.12 environment is required.'
}
Set-Location -LiteralPath $projectDir
$launchArguments = @('scripts/launch.py', '--port', $Port)
if ($NoBrowser) { $launchArguments += '--no-browser' }
if ($LaunchInfoPath) { $launchArguments += @('--launch-info', $LaunchInfoPath) }
& $pythonExe @launchArguments
