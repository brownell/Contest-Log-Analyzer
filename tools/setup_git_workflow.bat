@echo off
REM tools/setup_git_workflow.bat
REM
REM Purpose: Setup git workflow tools (pre-commit hooks and git aliases) for Contest Log Analytics.
REM          Can be run standalone or invoked from setup.bat.
REM
REM Copyright (c) 2025 Mark Bailey, KD4D
REM Contact: kd4d@kd4d.org
REM
REM License: Mozilla Public License, v. 2.0
REM          (https://www.mozilla.org/MPL/2.0/)

echo Setting up Git Workflow Tools for Contest Log Analytics...
echo.

REM Get absolute path to PowerShell script before changing directory
for %%I in ("%~dp0setup_git_workflow.ps1") do set "PS_SCRIPT=%%~fI"

REM Change to repo root
cd /d "%~dp0\.."

REM Check if PowerShell is available (preferred method on Windows)
where powershell.exe >nul 2>&1
if %errorlevel% equ 0 (
    REM Use PowerShell script (more robust)
    cd /d "%~dp0"
    powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%PS_SCRIPT%"
    cd /d "%~dp0\.."
    goto :end
)

REM Fallback to basic batch commands if PowerShell not available
echo Warning: PowerShell not found. Using basic batch commands...
echo.

REM Step 1: Setup Pre-commit Hooks
echo Step 1: Installing pre-commit hooks...
pre-commit --version >nul 2>&1
if %errorlevel% equ 0 (
    pre-commit install
    echo   Pre-commit hooks installed
) else (
    echo   pre-commit is not installed
    echo   Install it with: pip install pre-commit
)
echo.

REM Step 2: Setup Git Aliases
echo Step 2: Setting up git aliases...
git config alias.mainlog "log --first-parent --oneline --graph --decorate"
git config alias.fullhistory "log --all --graph --oneline --decorate"
git config alias.featurelog "log --oneline --graph --all --decorate"
git config alias.recent "log --first-parent --oneline --graph -20"
git config alias.branchdiff "log --oneline --graph main.."
echo   Git aliases configured
echo.

echo Setup complete!
echo Use 'git mainlog' to see clean main branch history

:end
