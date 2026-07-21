$ErrorActionPreference = "Stop"
. "$PSScriptRoot\uv_command.ps1"

Invoke-Uv run --frozen meyes
