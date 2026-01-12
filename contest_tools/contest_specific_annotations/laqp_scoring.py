# contest_tools/contest_specific_annotations/naqp_scoring.py
#
# Purpose: Provides contest-specific scoring logic for the NAQP contest.
#
# Author: Gemini AI
# Date: 2025-10-01
# Version: 0.90.0-Beta
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
# --- Revision History ---
# [0.90.0-Beta] - 2025-10-01
# Set new baseline version for release.

import pandas as pd
from typing import Dict, Any

def calculate_points(df: pd.DataFrame, my_call_info: Dict[str, Any]) -> pd.Series:
    """
    Calculates QSO points for an entire DataFrame based on NAQP rules.
    - Each valid (non-dupe) QSO is worth 1 point.
    """
    if df.empty or 'Dupe' not in df.columns:
        return pd.Series(0, index=df.index)

    # Assume 0 points by default
    points = pd.Series(0, index=df.index)
    
    # A valid QSO is any contact that is not a duplicate.
    valid_qso_mask = (df['Dupe'] == False)
    
    # Assign 1 point to all valid QSOs
    points[valid_qso_mask] = 1
        
    return points
