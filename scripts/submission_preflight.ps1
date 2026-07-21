param(
    [switch]$RunFullCheck,
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$failures = [System.Collections.Generic.List[string]]::new()
$requiredFiles = @(
    "README.md",
    "JUDGES.md",
    "PRIVACY.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    "uv.lock",
    "docs/BUILD_WEEK_SUBMISSION.md",
    "docs/DEVPOST_DRAFT.md",
    "resources/models/README.md"
)

$gitCommand = Get-Command git -ErrorAction SilentlyContinue
if ($null -eq $gitCommand) {
    throw "Git was not found. Install Git and reopen PowerShell."
}

function Invoke-GitText {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    $output = & $gitCommand.Source @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed: git $($Arguments -join ' ')"
    }
    return ($output -join "`n").Trim()
}

foreach ($path in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $failures.Add("Missing required file: $path")
        continue
    }
    try {
        Invoke-GitText ls-files --error-unmatch -- $path | Out-Null
    } catch {
        $failures.Add("Required file is not tracked by Git: $path")
    }
}

$branch = Invoke-GitText branch --show-current
if ($branch -ne "main") {
    $failures.Add("Expected submission branch main; found '$branch'.")
}

$remote = Invoke-GitText remote get-url origin
if ($remote -notmatch "github\.com[/:]drestaputra/meyes(?:\.git)?$") {
    $failures.Add("Unexpected origin remote: $remote")
}

$status = Invoke-GitText status --porcelain
if (-not $AllowDirty -and $status) {
    $failures.Add("Worktree is not clean. Commit and push the intended submission revision.")
}

$license = Get-Content -LiteralPath LICENSE -Raw
if ($license -notmatch "MIT License" -or $license -notmatch "drestaputra") {
    $failures.Add("LICENSE does not contain the expected MIT grant and owner placeholder.")
}

$readme = Get-Content -LiteralPath README.md -Raw
foreach ($requiredText in @("uv sync --frozen", "Codex", "GPT-5.6", "ENABLE LIVE INPUT")) {
    if ($readme -notmatch [regex]::Escape($requiredText)) {
        $failures.Add("README is missing required evidence text: $requiredText")
    }
}

if ($RunFullCheck) {
    & "$PSScriptRoot\check.ps1"
    if ($LASTEXITCODE -ne 0) {
        $failures.Add("Full deterministic check failed.")
    }
}

if ($failures.Count -gt 0) {
    Write-Host "LOCAL SUBMISSION PREFLIGHT: FAILED" -ForegroundColor Red
    foreach ($failure in $failures) {
        Write-Host "- $failure"
    }
    exit 1
}

Write-Host "LOCAL SUBMISSION PREFLIGHT: PASSED" -ForegroundColor Green
Write-Host "Branch: $branch"
Write-Host "Origin: $remote"
Write-Host "Required tracked files: $($requiredFiles.Count)"
if ($AllowDirty) {
    Write-Host "Worktree cleanliness: intentionally skipped for development validation"
} else {
    Write-Host "Worktree cleanliness: passed"
}

Write-Host ""
Write-Host "HUMAN/EXTERNAL BLOCKERS (not validated by this script):" -ForegroundColor Yellow
Write-Host "- entrant eligibility, ownership, rights, team, and category attestations"
Write-Host "- public repository access or both required private judge invitations"
Write-Host "- clean-user live camera and optional guarded OS-output verification"
Write-Host "- public YouTube demo under 3:00 with required English audio/translation"
Write-Host "- /feedback Session ID from the primary project task"
Write-Host "- authenticated Devpost fields and final Submitted state before 17:00 PT"
