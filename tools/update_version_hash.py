#!/usr/bin/env python3
# tools/update_version_hash.py
#
# Purpose: Pre-commit hook script to update git hash in version.py.
#          Ensures version.py always reflects the current git commit state.
#
# Copyright (c) 2025 Mark Bailey, KD4D
# Contact: kd4d@kd4d.org
#
# License: Mozilla Public License, v. 2.0
#          (https://www.mozilla.org/MPL/2.0/)

import subprocess
import re
from pathlib import Path
import sys

def update_version_hash():
    """Update git hash in version.py before commit."""
    repo_root = Path(__file__).parent.parent
    version_file = repo_root / 'contest_tools' / 'version.py'
    
    if not version_file.exists():
        print(f"Warning: version.py not found at {version_file}")
        return 0
    
    try:
        # Get current git hash
        git_hash = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=repo_root,
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        # Read current file
        content = version_file.read_text()
        
        # Update git hash line (matches: __git_hash__ = None or __git_hash__ = "abc1234")
        # Pattern matches: __git_hash__ = followed by None or a quoted string
        pattern = r'(__git_hash__\s*=\s*)(?:None|["\'][^"\']*["\'])'
        replacement = f'\\1"{git_hash}"'
        
        new_content = re.sub(pattern, replacement, content)
        
        # Only write if changed
        if new_content != content:
            version_file.write_text(new_content)
            print(f"Updated __git_hash__ to {git_hash} in version.py")
            # Add the file to staging so the hash update is included in commit
            subprocess.run(
                ['git', 'add', str(version_file)],
                cwd=repo_root,
                check=False  # Don't fail if git add fails
            )
        else:
            # Hash already matches, but ensure it's in the commit
            subprocess.run(
                ['git', 'add', str(version_file)],
                cwd=repo_root,
                check=False
            )
        
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Warning: Could not update git hash: {e}")
        return 0  # Don't fail the commit if this fails
    except Exception as e:
        print(f"Warning: Error updating version.py: {e}")
        return 0  # Don't fail the commit

if __name__ == '__main__':
    sys.exit(update_version_hash())
