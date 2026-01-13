# contest_tools/contest_specific_annotations/wrtc_2026_scoring.py
#
# Purpose: Provides contest-specific scoring logic for the WRTC 2026 contest.
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
import logging
from typing import Dict, Any

def calculate_points(df: pd.DataFrame, my_call_info: Dict[str, Any]) -> pd.Series:
    """
    Calculates QSO points for an entire DataFrame based on WRTC 2026 rules.
    - QSOs within Europe are worth 2 points.
    - QSOs outside Europe are worth 5 points.
    - This scoring is only valid for stations located in Europe.
    """
    my_continent = my_call_info.get('Continent')
    if not my_continent:
        raise ValueError("Logger's own Continent must be provided for WRTC scoring.")

    # Enforce the Europe-only rule for WRTC 2026
    if my_continent != 'EU':
        logging.warning("WRTC 2026 scoring is only valid for European stations. This log is from a non-EU station and will result in a score of 0.")
        return pd.Series(0, index=df.index)

    def _calculate_qso_points(row: pd.Series) -> int:
        if row['Dupe']:
            return 0

        worked_continent = row.get('Continent')
        if pd.isna(worked_continent) or worked_continent == 'Unknown':
            return 0
        
        if worked_continent == 'EU':
            return 2
        else:
            return 5
            
    return df.apply(_calculate_qso_points, axis=1)