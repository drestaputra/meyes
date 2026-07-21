param(
    [switch]$KeepArtifacts
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

. "$PSScriptRoot\uv_command.ps1"

$repositoryRoot = (Resolve-Path -LiteralPath "$PSScriptRoot\..").Path
$temporaryRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$artifactRoot = Join-Path $temporaryRoot ("meyes-wheel-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $artifactRoot | Out-Null

try {
    Push-Location $repositoryRoot
    try {
        $distributionDirectory = Join-Path $artifactRoot "dist"
        Invoke-Uv build --wheel --out-dir $distributionDirectory
        $wheels = @(Get-ChildItem -LiteralPath $distributionDirectory -Filter "*.whl")
        if ($wheels.Count -ne 1) {
            throw "Expected exactly one wheel; found $($wheels.Count)."
        }
        $wheel = $wheels[0].FullName

        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $archive = [System.IO.Compression.ZipFile]::OpenRead($wheel)
        try {
            $entries = @($archive.Entries | ForEach-Object FullName)
            $requiredEntries = @(
                "meyes/resources/models/face_landmarker.task",
                "meyes/resources/models/hand_landmarker.task",
                "meyes/resources/models/README.md",
                "meyes/resources/licenses/Apache-2.0.txt",
                "meyes/resources/licenses/THIRD_PARTY_NOTICES.md"
            )
            foreach ($entry in $requiredEntries) {
                if ($entry -notin $entries) {
                    throw "Wheel is missing required asset: $entry"
                }
            }
        } finally {
            $archive.Dispose()
        }

        $environment = Join-Path $artifactRoot "venv"
        Invoke-Uv venv --python 3.11 $environment
        $isolatedPython = Join-Path $environment "Scripts\python.exe"
        Invoke-Uv pip install --python $isolatedPython --no-deps $wheel
        & $isolatedPython -c @"
import hashlib
from meyes.vision.model_paths import face_landmarker_model_path, hand_landmarker_model_path
face = face_landmarker_model_path()
hand = hand_landmarker_model_path()
assert face.stat().st_size == 3_758_596
assert hand.stat().st_size == 7_819_105
assert hashlib.sha256(face.read_bytes()).hexdigest() == '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
assert hashlib.sha256(hand.read_bytes()).hexdigest() == 'fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1'
assert 'site-packages' in str(face)
assert 'site-packages' in str(hand)
print('Installed wheel model integrity: passed')
"@
        if ($LASTEXITCODE -ne 0) {
            throw "Installed wheel model integrity verification failed."
        }

        Write-Host "WHEEL VERIFICATION: PASSED" -ForegroundColor Green
    } finally {
        Pop-Location
    }
} finally {
    if ($KeepArtifacts) {
        Write-Host "Wheel verification artifacts: $artifactRoot"
    } else {
        $resolvedArtifactRoot = [System.IO.Path]::GetFullPath($artifactRoot)
        $expectedPrefix = $temporaryRoot.TrimEnd("\") + "\meyes-wheel-"
        if (-not $resolvedArtifactRoot.StartsWith(
            $expectedPrefix,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Refusing to clean unexpected artifact directory: $resolvedArtifactRoot"
        }
        Remove-Item -LiteralPath $resolvedArtifactRoot -Recurse -Force
    }
}
