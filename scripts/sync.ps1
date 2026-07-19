$ErrorActionPreference = 'Stop'

$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    & $uv.Source sync --group dev @args
} else {
    python -m uv sync --group dev @args
}
