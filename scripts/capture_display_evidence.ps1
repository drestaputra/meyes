param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\uv_command.ps1"

Invoke-Uv run --frozen python -m meyes.display_evidence --output $OutputPath
