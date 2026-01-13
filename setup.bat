@echo off
REM setup.bat
REM
REM Purpose: Main setup script for Contest Log Analytics development environment.
REM          Sets environment variables and optionally configures git workflow tools.
REM
REM Copyright (c) 2025 Mark Bailey, KD4D
REM Contact: kd4d@kd4d.org
REM
REM License: Mozilla Public License, v. 2.0
REM          (https://www.mozilla.org/MPL/2.0/)

REM Set environment variables
set CLA_PROFILE=1
set CONTEST_INPUT_DIR=CONTEST_LOGS_REPORTS
set CONTEST_REPORTS_DIR=C:\Users\mbdev\Hamradio\CLA

REM Activate conda environment
call activate cla

REM Optional: Setup Git Workflow Tools
if "%1"=="--setup-git" (
    echo.
    echo Setting up Git Workflow Tools...
    call tools\setup_git_workflow.bat
    goto :end
)

REM Check if git workflow tools are already set up
git config alias.mainlog >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Note: Git workflow tools are not configured.
    echo To set them up, run: setup.bat --setup-git
    echo Or run: tools\setup_git_workflow.bat
)

:end