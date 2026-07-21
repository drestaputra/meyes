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
                "meyes/resources/icons/meyes.svg",
                "meyes/resources/icons/meyes.ico",
                "meyes/resources/icons/README.md",
                "meyes/resources/licenses/Apache-2.0.txt",
                "meyes/resources/licenses/THIRD_PARTY_NOTICES.md"
            )
            foreach ($entry in $requiredEntries) {
                if ($entry -notin $entries) {
                    throw "Wheel is missing required asset: $entry"
                }
            }
            $iconEntry = $archive.GetEntry("meyes/resources/icons/meyes.svg")
            if ($null -eq $iconEntry -or $iconEntry.Length -ne 524) {
                throw "Wheel application icon has an unexpected size."
            }
            $iconStream = $iconEntry.Open()
            $sha256 = [System.Security.Cryptography.SHA256]::Create()
            try {
                $iconDigest = -join (
                    $sha256.ComputeHash($iconStream) |
                        ForEach-Object { $_.ToString("x2") }
                )
            } finally {
                $sha256.Dispose()
                $iconStream.Dispose()
            }
            if ($iconDigest -ne "ba44e15e0eacf011dbcbf978364cf8f64d2a8d93d477810de54efa86417508a8") {
                throw "Wheel application icon SHA-256 does not match the recorded source asset."
            }
            $windowsIconEntry = $archive.GetEntry("meyes/resources/icons/meyes.ico")
            if ($null -eq $windowsIconEntry -or $windowsIconEntry.Length -ne 19906) {
                throw "Wheel Windows icon has an unexpected size."
            }
            $windowsIconStream = $windowsIconEntry.Open()
            $windowsIconSha256 = [System.Security.Cryptography.SHA256]::Create()
            try {
                $windowsIconDigest = -join (
                    $windowsIconSha256.ComputeHash($windowsIconStream) |
                        ForEach-Object { $_.ToString("x2") }
                )
            } finally {
                $windowsIconSha256.Dispose()
                $windowsIconStream.Dispose()
            }
            if ($windowsIconDigest -ne "64f9ad51118096b8103b8c2cefc7931d3fc4d196e92d59c70968ac8d9a8b48a9") {
                throw "Wheel Windows icon SHA-256 does not match the generated asset."
            }
        } finally {
            $archive.Dispose()
        }

        $environment = Join-Path $artifactRoot "venv"
        Invoke-Uv venv --python 3.11 $environment
        $isolatedPython = Join-Path $environment "Scripts\python.exe"
        Invoke-Uv pip install --python $isolatedPython --no-deps $wheel
        & $isolatedPython -m meyes --version
        if ($LASTEXITCODE -ne 0) {
            throw "Installed wheel version command failed."
        }
        & $isolatedPython -m meyes --diagnose-install
        if ($LASTEXITCODE -ne 0) {
            throw "Installed wheel diagnostics failed."
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
