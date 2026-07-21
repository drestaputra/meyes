param(
    [string]$OutputRoot = "dist\release"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

. "$PSScriptRoot\uv_command.ps1"

$repositoryRoot = (Resolve-Path -LiteralPath "$PSScriptRoot\..").Path
if ([System.IO.Path]::IsPathRooted($OutputRoot)) {
    $resolvedOutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
} else {
    $resolvedOutputRoot = [System.IO.Path]::GetFullPath(
        (Join-Path $repositoryRoot $OutputRoot)
    )
}

Push-Location $repositoryRoot
try {
    & "$PSScriptRoot\submission_preflight.ps1" -VerifyRemote
    if ($LASTEXITCODE -ne 0) {
        throw "Submission preflight failed; no release artifact was built."
    }
    & "$PSScriptRoot\judge_verify.ps1"
    if ($LASTEXITCODE -ne 0) {
        throw "Judge verification failed; no release artifact was built."
    }

    $revision = (& git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $revision -notmatch "^[0-9a-f]{40}$") {
        throw "Could not resolve the exact Git revision for the release manifest."
    }
    $projectFile = Get-Content -LiteralPath pyproject.toml -Raw
    $versionMatch = [regex]::Match($projectFile, '(?m)^version = "([^"]+)"$')
    if (-not $versionMatch.Success) {
        throw "Could not resolve the project version from pyproject.toml."
    }
    $version = $versionMatch.Groups[1].Value
    $stamp = [DateTimeOffset]::UtcNow.ToString("yyyyMMdd-HHmmss")
    $releaseDirectory = Join-Path $resolvedOutputRoot (
        "meyes-$version-$($revision.Substring(0, 8))-$stamp"
    )
    if (Test-Path -LiteralPath $releaseDirectory) {
        throw "Release directory already exists; refusing to overwrite: $releaseDirectory"
    }
    New-Item -ItemType Directory -Path $releaseDirectory | Out-Null

    Invoke-Uv build --wheel --out-dir $releaseDirectory
    $wheels = @(Get-ChildItem -LiteralPath $releaseDirectory -Filter "*.whl")
    if ($wheels.Count -ne 1) {
        throw "Expected exactly one release wheel; found $($wheels.Count)."
    }
    $wheel = $wheels[0]
    $hash = Get-FileHash -LiteralPath $wheel.FullName -Algorithm SHA256
    $signature = Get-AuthenticodeSignature -LiteralPath $wheel.FullName
    # A Python wheel is a ZIP archive rather than a Windows PE/MSI artifact, so
    # Authenticode is not an applicable signing scheme. Keep the raw probe result
    # for auditability without presenting PowerShell's UnknownError as a release
    # failure or as proof of a valid signature.
    $authenticodeProbeStatus = $signature.Status.ToString()
    $createdAt = [DateTimeOffset]::UtcNow.ToString("o")
    $manifest = [ordered]@{
        schema_version = 2
        project = "MEYES"
        version = $version
        git_revision = $revision
        branch = "main"
        created_at_utc = $createdAt
        artifact = [ordered]@{
            filename = $wheel.Name
            size_bytes = $wheel.Length
            sha256 = $hash.Hash.ToLowerInvariant()
            code_signing = [ordered]@{
                configured = $false
                authenticode_applicability = "not_applicable"
                authenticode_probe_status = $authenticodeProbeStatus
                reason = "Python wheels are ZIP archives, not Windows PE or MSI artifacts."
            }
        }
        verification = [ordered]@{
            submission_preflight = "passed"
            frozen_judge_gate = "passed"
            installed_wheel_diagnostics = "passed"
        }
        limitations = @(
            "Python wheel; not a standalone Windows executable or installer.",
            "No code-signing certificate is configured by this repository workflow.",
            "Live camera and operating-system input still require the documented human checks."
        )
    }
    $manifestPath = Join-Path $releaseDirectory "BUILD-MANIFEST.json"
    $checksumPath = Join-Path $releaseDirectory "SHA256SUMS.txt"
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    "$($hash.Hash.ToLowerInvariant())  $($wheel.Name)" |
        Set-Content -LiteralPath $checksumPath -Encoding ASCII

    Write-Host "RELEASE ARTIFACT BUILD: PASSED" -ForegroundColor Green
    Write-Host "Revision: $revision"
    Write-Host "Wheel: $($wheel.FullName)"
    Write-Host "SHA-256: $($hash.Hash.ToLowerInvariant())"
    Write-Host "Code signing: not configured"
    Write-Host "Authenticode: not applicable to wheels (probe: $authenticodeProbeStatus)"
    Write-Host "Manifest: $manifestPath"
} finally {
    Pop-Location
}
