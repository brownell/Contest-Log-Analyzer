# tools/setup_git_aliases.ps1
#
# Purpose: Setup git aliases for clean history viewing (Windows PowerShell).
#          Run this once to configure git aliases for the repository.
#
# Copyright (c) 2025 Mark Bailey, KD4D
# Contact: kd4d@kd4d.org
#
# License: Mozilla Public License, v. 2.0
#          (https://www.mozilla.org/MPL/2.0/)

Write-Host "Setting up git aliases..." -ForegroundColor Green

# Main branch history (clean, squash-like view)
git config alias.mainlog 'log --first-parent --oneline --graph --decorate'

# Full history with all branches
git config alias.fullhistory 'log --all --graph --oneline --decorate'

# Feature branch history
git config alias.featurelog 'log --oneline --graph --all --decorate'

# Recent main branch commits only (no merge bubbles)
git config alias.recent 'log --first-parent --oneline --graph -20'

# Show what's in a feature branch vs main
git config alias.branchdiff 'log --oneline --graph main..'

Write-Host "Git aliases configured!" -ForegroundColor Green
Write-Host ""
Write-Host "Usage:" -ForegroundColor Cyan
Write-Host "  git mainlog      - Clean main branch view (recommended for daily use)"
Write-Host "  git fullhistory  - Full history with all branches"
Write-Host "  git featurelog   - See everything with branch structure"
Write-Host "  git recent       - Last 20 commits on main (clean view)"
Write-Host "  git branchdiff   - Show commits in current branch not in main"
