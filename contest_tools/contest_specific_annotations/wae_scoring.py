# contest_tools/contest_specific_annotations/wae_scoring.py
#
# Purpose: This module provides the base QSO scoring logic for the WAE Contest.
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
    Calculates QSO points for an entire DataFrame based on WAE rules.
    - Each valid (non-dupe) QSO between an EU and non-EU station is worth 1 point.
    - Invalid QSOs (EU-EU, non-EU-non-EU) are worth 0 points.
    - Special case: DX stations do not get QSO credit for working *IG9.
    - QTC points are handled separately by the time-series score calculator.
    """
    my_continent = my_call_info.get('Continent')
    if not my_continent:
        raise ValueError("Logger's own Continent must be provided for WAE scoring.")

    is_logger_eu = (my_continent == 'EU')

    def is_qso_valid(row):
        # Dupes are always 0 points
        if row['Dupe']:
            return 0
        
        is_worked_ig9 = row.get('WAEPfx') == '*IG9'
        is_worked_eu = (row['Continent'] == 'EU')
        
        if is_logger_eu:
            # For EU loggers, any non-EU contact (including IG9) is worth 1 point.
            return 1 if not is_worked_eu else 0
        else: # Logger is DX
            # For DX loggers, contact must be with EU, and NOT with IG9.
            if is_worked_eu and not is_worked_ig9:
                return 1
            return 0
            
    return df.apply(is_qso_valid, axis=1)