#!/bin/bash
# tools/setup_git_aliases.sh
#
# Purpose: Setup git aliases for clean history viewing.
#          Run this once to configure git aliases for the repository.
#
# Copyright (c) 2025 Mark Bailey, KD4D
# Contact: kd4d@kd4d.org
#
# License: Mozilla Public License, v. 2.0
#          (https://www.mozilla.org/MPL/2.0/)

echo "Setting up git aliases..."

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

echo "Git aliases configured!"
echo ""
echo "Usage:"
echo "  git mainlog      - Clean main branch view (recommended for daily use)"
echo "  git fullhistory  - Full history with all branches"
echo "  git featurelog   - See everything with branch structure"
echo "  git recent       - Last 20 commits on main (clean view)"
echo "  git branchdiff   - Show commits in current branch not in main"
