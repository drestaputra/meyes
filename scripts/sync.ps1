$ErrorActionPreference = "Stop"
. "$PSScriptRoot\uv_command.ps1"

Invoke-Uv sync --frozen --group dev @args
