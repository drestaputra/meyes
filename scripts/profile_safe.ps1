$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

. "$PSScriptRoot\uv_command.ps1"

Invoke-Uv run --frozen meyes --profile-safe
