# contest_tools/contest_specific_annotations/arrl_10_scoring.py
#
# Purpose: Provides contest-specific scoring logic for the ARRL 10 Meter contest.
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
    Calculates QSO points for an entire DataFrame based on ARRL 10 Meter rules.
    - CW contacts are worth 4 points.
    - Phone contacts are worth 2 points.
    - Duplicate contacts are worth 0 points.

    Args:
        df (pd.DataFrame): The DataFrame of QSOs to be scored.
        my_call_info (Dict[str, Any]): Not used for this contest's scoring.

    Returns:
        pd.Series: A Pandas Series containing the calculated points for each QSO.
    """
    # Initialize a Series for points with a default of 0
    points = pd.Series(0, index=df.index)

    # Create boolean masks for each mode
    is_cw = (df['Mode'] == 'CW')
    is_ph = (df['Mode'] == 'PH') | (df['Mode'] == 'SSB')
    is_dupe = (df['Dupe'] == True)

    # Assign points based on mode
    points[is_cw] = 4
    points[is_ph] = 2

    # Overwrite points to 0 for any row marked as a dupe
    points[is_dupe] = 0

    return points
