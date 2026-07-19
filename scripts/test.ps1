$ErrorActionPreference = 'Stop'

if (-not $env:QT_QPA_PLATFORM) {
    $env:QT_QPA_PLATFORM = 'offscreen'
}

$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    & $uv.Source run pytest @args
} else {
    python -m uv run pytest @args
}
