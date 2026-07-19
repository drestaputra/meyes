$ErrorActionPreference = 'Stop'

if (-not $env:QT_QPA_PLATFORM) {
    $env:QT_QPA_PLATFORM = 'offscreen'
}

$uv = Get-Command uv -ErrorAction SilentlyContinue

function Invoke-Uv {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    if ($uv) {
        & $uv.Source @Arguments
    } else {
        python -m uv @Arguments
    }
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Invoke-Uv run ruff format --check .
Invoke-Uv run ruff check .
Invoke-Uv run mypy
Invoke-Uv run pytest
