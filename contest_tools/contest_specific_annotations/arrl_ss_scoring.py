# contest_tools/contest_specific_annotations/arrl_ss_scoring.py
#
# Purpose: Provides contest-specific scoring logic for the ARRL Sweepstakes contest.
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

import pandas as pd
from typing import Dict, Any

def calculate_points(df: pd.DataFrame, my_call_info: Dict[str, Any]) -> pd.Series:
    """
    Calculates QSO points for an entire DataFrame based on ARRL Sweepstakes rules.
    Each valid (non-dupe) QSO is worth 2 points.

    Args:
        df (pd.DataFrame): The DataFrame of QSOs to be scored.
        my_call_info (Dict[str, Any]): Not used for this contest's scoring.

    Returns:
        pd.Series: A Pandas Series containing the calculated points for each QSO.
    """
    # Create a Series of 2s for all rows
    points = pd.Series(2, index=df.index)
    
    # Set points to 0 for any row marked as a dupe
    if 'Dupe' in df.columns:
        points[df['Dupe'] == True] = 0
        
    return points
