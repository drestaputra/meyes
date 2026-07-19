$ErrorActionPreference = 'Stop'

$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    & $uv.Source run meyes
} else {
    python -m uv run meyes
}
