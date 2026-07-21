param(
    [switch]$RunFullCheck,
    [switch]$VerifyRemote,
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$failures = [System.Collections.Generic.List[string]]::new()
$requiredFiles = @(
    ".github/workflows/windows-quality.yml",
    "README.md",
    "JUDGES.md",
    "PRIVACY.md",
    "TROUBLESHOOTING.md",
    "SIGNING.md",
    "MVP_ACCEPTANCE.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    "uv.lock",
    "docs/BUILD_WEEK_SUBMISSION.md",
    "docs/DEVPOST_DRAFT.md",
    "docs/evidence/performance/2026-07-21.md",
    "resources/models/README.md",
    "scripts/judge_verify.ps1",
    "scripts/diagnose_install.ps1",
    "scripts/profile_safe.ps1",
    "scripts/verify_docs.ps1",
    "scripts/build_release.ps1",
    "scripts/verify_wheel.ps1"
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

$head = Invoke-GitText rev-parse HEAD
$upstream = Invoke-GitText rev-parse --abbrev-ref --symbolic-full-name "@{upstream}"
if ($upstream -ne "origin/main") {
    $failures.Add("Expected upstream origin/main; found '$upstream'.")
}
$upstreamHead = Invoke-GitText rev-parse "@{upstream}"
if ($head -ne $upstreamHead) {
    $failures.Add("Local HEAD does not match the locally recorded upstream revision.")
}

$remote = Invoke-GitText remote get-url origin
if ($remote -notmatch "github\.com[/:]drestaputra/meyes(?:\.git)?$") {
    $failures.Add("Unexpected origin remote: $remote")
}

if ($VerifyRemote) {
    try {
        $remoteLine = Invoke-GitText ls-remote --exit-code origin refs/heads/main
        $remoteHead = ($remoteLine -split "\s+")[0]
        if ($head -ne $remoteHead) {
            $failures.Add("Local HEAD does not match origin/main on the remote server.")
        }
    } catch {
        $failures.Add("Could not verify origin/main on the remote server: $($_.Exception.Message)")
    }
}

$status = Invoke-GitText status --porcelain
if (-not $AllowDirty -and $status) {
    $failures.Add("Worktree is not clean. Commit and push the intended submission revision.")
}

$license = Get-Content -LiteralPath LICENSE -Raw
if ($license -notmatch "MIT License" -or $license -notmatch "drestaputra") {
    $failures.Add("LICENSE does not contain the expected MIT grant and recorded owner.")
}

$readme = Get-Content -LiteralPath README.md -Raw
foreach ($requiredText in @("uv sync --frozen", "Codex", "GPT-5.6", "ENABLE LIVE INPUT")) {
    if ($readme -notmatch [regex]::Escape($requiredText)) {
        $failures.Add("README is missing required evidence text: $requiredText")
    }
}

$devpostDraft = Get-Content -LiteralPath docs/DEVPOST_DRAFT.md -Raw
foreach ($forbiddenText in @("Update this number", "TODO", "TBD", "Untitled")) {
    if ($devpostDraft -match [regex]::Escape($forbiddenText)) {
        $failures.Add("Devpost draft still contains unresolved text: $forbiddenText")
    }
}

$judgeGuide = Get-Content -LiteralPath JUDGES.md -Raw
foreach ($forbiddenText in @("tray controls, or an installer", "a first-run setup flow")) {
    if ($judgeGuide -match [regex]::Escape($forbiddenText) -or
        $devpostDraft -match [regex]::Escape($forbiddenText)) {
        $failures.Add("Submission copy contains a stale implemented-feature claim: $forbiddenText")
    }
}

& "$PSScriptRoot\verify_docs.ps1"
if ($LASTEXITCODE -ne 0) {
    $failures.Add("Documentation verification failed.")
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
Write-Host "Revision: $head"
Write-Host "Origin: $remote"
if ($VerifyRemote) {
    Write-Host "Remote revision parity: passed"
} else {
    Write-Host "Remote revision parity: skipped (use -VerifyRemote)"
}
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
