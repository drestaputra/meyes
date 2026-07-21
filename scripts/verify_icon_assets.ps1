$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

. "$PSScriptRoot\uv_command.ps1"

Invoke-Uv run --frozen python "$PSScriptRoot\generate_icon_assets.py"
