$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

. "$PSScriptRoot\uv_command.ps1"

Write-Host "Synchronizing the locked judge environment..."
Invoke-Uv sync --frozen --group dev

Write-Host "Verifying the packaged application entry point..."
Invoke-Uv run --frozen python -c `
    "import meyes; from meyes.__main__ import main; assert callable(main); print('MEYES entry point: passed')"

Write-Host "Running deterministic quality checks..."
& "$PSScriptRoot\check.ps1"

Write-Host "JUDGE SOURCE VERIFICATION: PASSED" -ForegroundColor Green
Write-Host "No camera was opened and no operating-system input was armed by this script."
