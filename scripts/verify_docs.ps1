param(
    [string]$RepositoryRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$gitCommand = Get-Command git -ErrorAction SilentlyContinue
if ($null -eq $gitCommand) {
    throw "Git was not found. Install Git and reopen PowerShell."
}

if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = (& $gitCommand.Source -C $PSScriptRoot rev-parse --show-toplevel).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($RepositoryRoot)) {
        throw "Could not resolve the repository root."
    }
}

$root = [System.IO.Path]::GetFullPath($RepositoryRoot).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
)
$trackedMarkdown = @(& $gitCommand.Source -C $root ls-files -- "*.md")
if ($LASTEXITCODE -ne 0) {
    throw "Could not enumerate tracked Markdown files."
}

$inlinePattern = [regex]::new(
    '!?' +
    '\[[^\]\r\n]*\]' +
    '\(' +
    '(?<target><[^>\r\n]+>|[^\s)]+)' +
    '(?:\s+(?:"[^"]*"|''[^'']*''|\([^)]*\)))?' +
    '\)'
)
$referencePattern = [regex]::new(
    '^\s*\[[^\]\r\n]+\]:\s*(?<target><[^>\r\n]+>|\S+)',
    [System.Text.RegularExpressions.RegexOptions]::Multiline
)
$failures = [System.Collections.Generic.List[string]]::new()
$checkedLinks = 0

foreach ($relativeFile in $trackedMarkdown) {
    $sourcePath = Join-Path $root $relativeFile
    $sourceDirectory = Split-Path -Parent $sourcePath
    $content = Get-Content -LiteralPath $sourcePath -Raw
    $matches = @($inlinePattern.Matches($content)) + @($referencePattern.Matches($content))

    foreach ($match in $matches) {
        $target = $match.Groups['target'].Value.Trim()
        if ($target.StartsWith('<') -and $target.EndsWith('>')) {
            $target = $target.Substring(1, $target.Length - 2)
        }
        if (
            [string]::IsNullOrWhiteSpace($target) -or
            $target.StartsWith('#') -or
            $target.StartsWith('//') -or
            $target -match '^[A-Za-z][A-Za-z0-9+.-]*:'
        ) {
            continue
        }

        $pathPart = ($target -split '[?#]', 2)[0]
        if ([string]::IsNullOrWhiteSpace($pathPart)) {
            continue
        }

        try {
            $decodedPath = [System.Uri]::UnescapeDataString($pathPart)
            if ([System.IO.Path]::IsPathRooted($decodedPath)) {
                $candidate = [System.IO.Path]::GetFullPath(
                    (Join-Path $root $decodedPath.TrimStart('/', '\'))
                )
            } else {
                $candidate = [System.IO.Path]::GetFullPath(
                    (Join-Path $sourceDirectory $decodedPath)
                )
            }
        } catch {
            $failures.Add("$relativeFile -> '$target' is not a valid local path.")
            continue
        }

        $insideRoot = $candidate.Equals($root, [System.StringComparison]::OrdinalIgnoreCase) -or
            $candidate.StartsWith(
                $root + [System.IO.Path]::DirectorySeparatorChar,
                [System.StringComparison]::OrdinalIgnoreCase
            )
        if (-not $insideRoot) {
            $failures.Add("$relativeFile -> '$target' resolves outside the repository.")
            continue
        }

        $checkedLinks += 1
        if (-not (Test-Path -LiteralPath $candidate)) {
            $failures.Add("$relativeFile -> '$target' does not exist.")
        }
    }
}

if ($failures.Count -gt 0) {
    Write-Host "DOCUMENTATION VERIFICATION: FAILED" -ForegroundColor Red
    foreach ($failure in $failures) {
        Write-Host "- $failure"
    }
    exit 1
}

Write-Host "DOCUMENTATION VERIFICATION: PASSED" -ForegroundColor Green
Write-Host "Tracked Markdown files: $($trackedMarkdown.Count)"
Write-Host "Local link targets checked: $checkedLinks"
