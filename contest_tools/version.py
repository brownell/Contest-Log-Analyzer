# contest_tools/version.py
#
# Purpose: Centralized version management for the Contest Log Analytics project.
#          Provides runtime version information derived from git tags or file-based defaults.
#
# Copyright (c) 2025 Mark Bailey, KD4D
# Contact: kd4d@kd4d.org
#
# License: Mozilla Public License, v. 2.0
#          (https://www.mozilla.org/MPL/2.0/)
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import subprocess
import os
from pathlib import Path

def _get_git_version():
    """Get version from git describe, falling back to None if git unavailable."""
    try:
        repo_root = Path(__file__).parent.parent.parent
        # Get the most recent tag + distance (e.g., "v1.0.0" or "v1.0.0-3-gabc1234" or "abc1234")
        describe = subprocess.check_output(
            ['git', 'describe', '--tags', '--dirty', '--always'],
            stderr=subprocess.DEVNULL,
            cwd=repo_root
        ).decode().strip()
        
        # Remove 'v' prefix if present (standardize format)
        if describe.startswith('v'):
            return describe.lstrip('v')
        return describe
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def _get_git_hash():
    """Get current git commit hash."""
    try:
        repo_root = Path(__file__).parent.parent.parent
        return subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            stderr=subprocess.DEVNULL,
            cwd=repo_root
        ).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

# File-based defaults (used if git unavailable, e.g., in packaged distributions)
# These should be updated to match the most recent git tag before release builds
__version__ = "1.0.0-alpha.1"
__git_hash__ = None

# Try to get from git (overrides defaults in development environments)
_git_version = _get_git_version()
_git_hash = _get_git_hash()

if _git_version:
    __version__ = _git_version
if _git_hash:
    __git_hash__ = _git_hash

# Version string for display (includes git hash if available)
def get_version_string():
    """Get formatted version string with git hash for display."""
    if __git_hash__:
        return f"{__version__} (commit {__git_hash__})"
    return __version__
