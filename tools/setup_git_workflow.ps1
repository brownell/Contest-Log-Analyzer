# tools/setup_git_workflow.ps1
#
# Purpose: Setup git workflow tools (pre-commit hooks and git aliases) for Contest Log Analytics.
#          Can be run standalone or invoked from setup.bat.
#
# Copyright (c) 2025 Mark Bailey, KD4D
# Contact: kd4d@kd4d.org
#
# License: Mozilla Public License, v. 2.0
#          (https://www.mozilla.org/MPL/2.0/)

param(
    [switch]$SkipHooks,
    [switch]$SkipAliases
)

$ErrorActionPreference = "Continue"

# Get script directory - handle case where $PSScriptRoot might not be set
if ($PSScriptRoot) {
    $scriptDir = $PSScriptRoot
} elseif ($PSCommandPath) {
    $scriptDir = Split-Path -Parent $PSCommandPath
} else {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)

Write-Host "Setting up Git Workflow Tools for Contest Log Analytics..." -ForegroundColor Cyan
Write-Host ""

# Step 1: Setup Pre-commit Hooks
if ($SkipHooks) {
    Write-Host "Step 1: Skipped (--SkipHooks)" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "Step 1: Installing pre-commit hooks..." -ForegroundColor Yellow
    $precommitAvailable = $false
    try {
        $null = pre-commit --version 2>&1 | Out-Null
        $precommitAvailable = $?
    } catch {
        $precommitAvailable = $false
    }
    
    if (-not $precommitAvailable) {
        Write-Host "  [X] pre-commit is not installed" -ForegroundColor Red
        Write-Host "    Install it with: pip install pre-commit" -ForegroundColor Yellow
        Write-Host "    Then run this script again." -ForegroundColor Yellow
    } else {
        Write-Host "  [OK] pre-commit is installed" -ForegroundColor Green
        Set-Location $repoRoot
        try {
            $null = pre-commit install 2>&1 | Out-Null
            $installSuccess = $?
            if ($installSuccess) {
                Write-Host "  [OK] Pre-commit hooks installed successfully" -ForegroundColor Green
            } else {
                Write-Host "  WARNING: pre-commit install had issues" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "  WARNING: pre-commit install had issues" -ForegroundColor Yellow
        }
    }
    Write-Host ""
}

# Step 2: Setup Git Aliases
if (-not $SkipAliases) {
    Write-Host "Step 2: Setting up git aliases..." -ForegroundColor Yellow
    git config alias.mainlog 'log --first-parent --oneline --graph --decorate'
    Write-Host "  [OK] mainlog alias configured" -ForegroundColor Green
    git config alias.fullhistory 'log --all --graph --oneline --decorate'
    Write-Host "  [OK] fullhistory alias configured" -ForegroundColor Green
    git config alias.featurelog 'log --oneline --graph --all --decorate'
    Write-Host "  [OK] featurelog alias configured" -ForegroundColor Green
    git config alias.recent 'log --first-parent --oneline --graph -20'
    Write-Host "  [OK] recent alias configured" -ForegroundColor Green
    git config alias.branchdiff 'log --oneline --graph main..'
    Write-Host "  [OK] branchdiff alias configured" -ForegroundColor Green
    Write-Host "  [OK] Git aliases configured successfully" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "Step 2: Skipped (--SkipAliases)" -ForegroundColor Gray
    Write-Host ""
}

# Step 3: Verify version.py exists
Write-Host "Step 3: Verifying version.py..." -ForegroundColor Yellow
$versionFile = Join-Path $repoRoot "contest_tools\version.py"
if (-not (Test-Path $versionFile)) {
    Write-Host "  [X] version.py not found at expected location: $versionFile" -ForegroundColor Red
} else {
    Write-Host "  [OK] version.py exists" -ForegroundColor Green
    Set-Location $repoRoot
    try {
        $pythonCmd = 'import sys; sys.path.insert(0, "."); from contest_tools.version import __version__, get_version_string; print(get_version_string())'
        $versionCheck = python -c $pythonCmd 2>&1
        $pythonResult = $?
        if ($pythonResult -and $versionCheck) {
            Write-Host "  [OK] version.py is functional: $versionCheck" -ForegroundColor Green
        } elseif (-not $pythonResult) {
            Write-Host "  WARNING: Could not test version.py import (Python may not be available)" -ForegroundColor Yellow
        } else {
            Write-Host "  WARNING: version.py exists but may have issues importing" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  WARNING: Could not test version.py import (Python may not be available)" -ForegroundColor Yellow
    }
}
Write-Host ""

# Summary
Write-Host "Setup Summary:" -ForegroundColor Cyan
Write-Host "  * Pre-commit hooks:" $(if (-not $SkipHooks) { "Configured" } else { "Skipped" })
Write-Host "  * Git aliases:" $(if (-not $SkipAliases) { "Configured" } else { "Skipped" })
Write-Host "  * Version management: Ready" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Use 'git mainlog' to see clean main branch history" -ForegroundColor White
Write-Host "  2. Pre-commit hooks will auto-update git hash in version.py" -ForegroundColor White
Write-Host "  3. See Docs/Contributing.md and Docs/AI_AGENT_RULES.md for workflow details" -ForegroundColor White
Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
