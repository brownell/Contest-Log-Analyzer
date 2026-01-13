# Git Workflow Setup Tools

This directory contains scripts for setting up git workflow tools for Contest Log Analytics.

**Important:** You can run these scripts from **Command Prompt (cmd.exe)** - they will automatically invoke PowerShell if needed to do the actual work. No need to open PowerShell manually.

---

## Quick Setup

### Option 1: From setup.bat (Recommended)
Run from **Command Prompt**:
```batch
cd Contest-Log-Analyzer
setup.bat --setup-git
```

This will:
1. Set up your development environment (env vars, conda)
2. Automatically call the git workflow setup scripts
3. Install pre-commit hooks (if pre-commit is installed)
4. Configure git aliases for clean history viewing

### Option 2: Run Git Workflow Setup Directly
From **Command Prompt**:
```batch
cd Contest-Log-Analyzer
tools\setup_git_workflow.bat
```

This script:
- Automatically detects if PowerShell is available
- Uses PowerShell script for robust setup (if available)
- Falls back to basic batch commands if PowerShell not found
- Works from regular cmd.exe - no PowerShell needed!

### Option 3: Run PowerShell Script Directly (Advanced)
Only if you want to run PowerShell directly:
```powershell
powershell -ExecutionPolicy Bypass -File tools\setup_git_workflow.ps1
```

## What Gets Set Up

### 1. Pre-commit Hooks
- Automatically updates `__git_hash__` in `contest_tools/version.py` before each commit
- Requires: `pip install pre-commit`

### 2. Git Aliases
Sets up convenient aliases for viewing history:
- `git mainlog` - Clean main branch view (recommended for daily use)
- `git recent` - Last 20 commits on main (clean view)
- `git fullhistory` - Full history with all branches
- `git featurelog` - See everything with branch structure
- `git branchdiff` - Show commits in current branch not in main

---

## Tutorial: First Time Setup

### Scenario: New Developer Setup

**Step 1:** Clone the repository
```batch
git clone https://github.com/user/Contest-Log-Analyzer.git
cd Contest-Log-Analyzer
```

**Step 2:** Set up development environment and git workflow
```batch
setup.bat --setup-git
```

This one command will:
- ✅ Configure environment variables
- ✅ Activate conda environment
- ✅ Install pre-commit hooks (if pre-commit installed)
- ✅ Set up git aliases for clean history viewing
- ✅ Verify version.py is working

**Step 3:** Verify it worked
```batch
# Check git aliases
git mainlog

# Check pre-commit hooks (if installed)
pre-commit --version
```

### Scenario: Just Need Git Workflow Tools

If you already have your environment set up and just need git workflow tools:

```batch
tools\setup_git_workflow.bat
```

This will:
- ✅ Install pre-commit hooks
- ✅ Configure git aliases
- ✅ Verify version.py

---

## Use Cases

### Use Case 1: Daily Development
You're working on a feature branch and want to see clean history:
```batch
# View clean main branch history (recommended)
git mainlog

# View recent commits
git recent

# See what's in your branch vs main
git branchdiff
```

### Use Case 2: Setting Up a New Machine
You've cloned the repo on a new computer:
```batch
# One command sets everything up
setup.bat --setup-git

# If you don't have pre-commit yet, install it first:
pip install pre-commit
setup.bat --setup-git
```

### Use Case 3: Collaborator Wants Clean History View
A team member wants to see the git aliases working:
```batch
# They just need to run:
tools\setup_git_workflow.bat

# Now they can use:
git mainlog        # Clean main branch view
git recent         # Recent commits
git fullhistory    # Everything with branches
```

### Use Case 4: Pre-commit Hook Not Working
The git hash isn't updating automatically:
```batch
# Reinstall pre-commit hooks
pre-commit install

# Or run the setup again
tools\setup_git_workflow.bat
```

---

## Manual Setup

If you prefer to set up manually:

### Pre-commit Hooks
```bash
pip install pre-commit
pre-commit install
```

### Git Aliases
```bash
git config alias.mainlog 'log --first-parent --oneline --graph --decorate'
git config alias.recent 'log --first-parent --oneline --graph -20'
git config alias.fullhistory 'log --all --graph --oneline --decorate'
git config alias.featurelog 'log --oneline --graph --all --decorate'
git config alias.branchdiff 'log --oneline --graph main..'
```

## Verification

After setup, verify everything works:

```bash
# Check pre-commit hooks
pre-commit run --all-files

# Check git aliases
git mainlog

# Check version.py
python -c "from contest_tools.version import get_version_string; print(get_version_string())"
```

---

## How It Works (Technical Details)

### Command Prompt → PowerShell Chain

When you run from **Command Prompt** (`cmd.exe`):

```
User types: tools\setup_git_workflow.bat
  ↓
Batch script checks for PowerShell
  ↓
If PowerShell found:
  → Calls: powershell -File tools\setup_git_workflow.ps1
    → PowerShell script does all the work
If PowerShell not found:
  → Falls back to basic batch commands
```

**Key Point:** You don't need PowerShell open - the batch script handles everything!

### What Gets Configured

1. **Pre-commit Hooks** (`.git/hooks/pre-commit`)
   - Automatically updates `__git_hash__` in `version.py` before each commit
   - Runs before every `git commit`

2. **Git Aliases** (stored in `.git/config`)
   - `mainlog` - Clean main branch view using `--first-parent`
   - `recent` - Last 20 commits on main
   - `fullhistory` - Full history with all branches
   - `featurelog` - All branches with structure
   - `branchdiff` - Commits in current branch not in main

3. **Version Management** (`contest_tools/version.py`)
   - Centralized version tracking
   - Git-aware version strings with commit hash
   - Works in production (no git needed if pre-populated)

---

## Troubleshooting

### "PowerShell not found" Warning
**Solution:** This is fine! The script will use basic batch commands instead. For full functionality, PowerShell 5.1+ is recommended (comes with Windows 10/11).

### Pre-commit not found
```batch
pip install pre-commit
pre-commit install
```

Or re-run:
```batch
tools\setup_git_workflow.bat
```

### Git aliases not working
1. Make sure you're in the repository root
2. Check if aliases exist:
   ```batch
   git config --list | findstr alias
   ```
3. Re-run setup:
   ```batch
   tools\setup_git_workflow.bat
   ```

### version.py not importing
1. Make sure you're in the repository root when running Python
2. Check Python path:
   ```batch
   python -c "import sys; sys.path.insert(0, '.'); from contest_tools.version import __version__; print(__version__)"
   ```
3. Verify file exists:
   ```batch
   dir contest_tools\version.py
   ```

### Script runs but nothing happens
- Check if you're in the repository root directory
- Try running with explicit path:
  ```batch
  cd c:\Users\YourUser\Repos\Contest-Log-Analyzer
  tools\setup_git_workflow.bat
  ```

### "Access Denied" or Permission Errors
- Make sure you have write permissions to the repository
- If using a corporate/work computer, you may need admin rights
- Try running Command Prompt "As Administrator"
