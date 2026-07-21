$ErrorActionPreference = "Stop"
. "$PSScriptRoot\uv_command.ps1"

Invoke-Uv run --frozen ruff format --check .
Invoke-Uv run --frozen ruff check .
Invoke-Uv run --frozen mypy
Invoke-Uv run --frozen pytest
