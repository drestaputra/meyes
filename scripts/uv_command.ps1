$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$script:UvExecutable = $null
$script:UvPrefix = @()
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($null -ne $uvCommand) {
    $script:UvExecutable = $uvCommand.Source
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $pythonCommand) {
        & $pythonCommand.Source -c "import uv" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $script:UvExecutable = $pythonCommand.Source
            $script:UvPrefix = @("-m", "uv")
        }
    }
}

if ($null -eq $script:UvExecutable) {
    throw "uv was not found. Install uv and reopen PowerShell, or install the uv Python module."
}

function Invoke-Uv {
    param(
        [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    $prefix = $script:UvPrefix
    & $script:UvExecutable @prefix @Arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "uv command failed with exit code $exitCode."
    }
}
