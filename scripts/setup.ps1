param([string]$PythonExecutable = 'python')
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectDir
& $PythonExecutable -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
& './.venv/Scripts/python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
$sampleCatalog = Join-Path $projectDir 'data/samples/catalog.json'
$sampleVideo = Join-Path $projectDir 'data/samples/demo_workspace.mp4'
if ((Test-Path -LiteralPath $sampleCatalog) -and (Test-Path -LiteralPath $sampleVideo)) {
    Write-Host 'Bundled samples found; preserving the frozen evaluation assets.'
} else {
    & './.venv/Scripts/python.exe' scripts/generate_samples.py --demo-only
    if ($LASTEXITCODE -ne 0) { throw 'Demo sample generation failed.' }
}
