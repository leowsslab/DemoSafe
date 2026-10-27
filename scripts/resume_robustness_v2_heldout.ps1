$ErrorActionPreference = 'Stop'
$projectDir = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectDir
$pythonExe = Join-Path $projectDir '.venv/Scripts/python.exe'
# Verify the whole coordinator freeze, including evaluator and shared scoring code.
& $pythonExe -c "import hashlib,json; from pathlib import Path; r=Path.cwd(); f=json.loads((r/'reports/evaluation_v2_source_freeze.json').read_text()); changed=[p for p,h in f['source_sha256'].items() if not (r/p).is_file() or hashlib.sha256((r/p).read_bytes()).hexdigest()!=h]; assert not changed, 'Frozen sources changed: '+repr(changed); print('All frozen source hashes match; proceeding only with the original scoring implementation.')"
if ($LASTEXITCODE -ne 0) { throw 'Source-freeze validation failed. Do not resume under different scoring code.' }
& $pythonExe scripts/generate_robustness_v2.py --verify
if ($LASTEXITCODE -ne 0) { throw 'Frozen dataset validation failed.' }
& $pythonExe scripts/benchmark_robustness_v2.py --split heldout --resume --freeze-note 'Resume after user shutdown pause; all frozen source and dataset hashes verified; complete the two uncompleted clips from frame zero without changing completed evidence.'
if ($LASTEXITCODE -ne 0) { throw 'Heldout continuation did not complete cleanly; preserve the report and inspect the error.' }
& $pythonExe scripts/summarize_robustness_v2.py
if ($LASTEXITCODE -ne 0) { throw 'Summary validation failed.' }
