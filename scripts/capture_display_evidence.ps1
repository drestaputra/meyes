param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

uv run python -m meyes.display_evidence --output $OutputPath
