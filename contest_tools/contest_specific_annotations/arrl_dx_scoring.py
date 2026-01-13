# contest_tools/contest_specific_annotations/arrl_dx_scoring.py
#
# Purpose: Provides contest-specific scoring logic for the ARRL DX contest.
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

def _calculate_single_qso_points(row: pd.Series, my_location_type: str) -> int:
    """
    Calculates the point value for a single QSO based on the official ARRL DX rules.
    """
    if row['Dupe']:
        return 0

    worked_dxcc_pfx = row.get('DXCCPfx')
    worked_dxcc_name = row.get('DXCCName')
    
    # Determine worked station's location type based on DXCC entity
    if worked_dxcc_pfx in ['KH6', 'KL7', 'CY9', 'CY0']:
        worked_location_type = "DX"
    elif worked_dxcc_name in ["United States", "Canada"]:
        worked_location_type = "W/VE"
    else:
        worked_location_type = "DX"

    # --- Final Scoring Rules ---
    if my_location_type == "W/VE":
        return 3 if worked_location_type == "DX" else 0
    elif my_location_type == "DX":
        return 3 if worked_location_type == "W/VE" else 0
    
    return 0

def calculate_points(df: pd.DataFrame, my_call_info: Dict[str, Any]) -> pd.Series:
    """
    Calculates QSO points for an entire DataFrame based on ARRL DX rules.
    """
    my_entity_name = my_call_info.get('DXCCName')
    if not my_entity_name:
        raise ValueError("Logger's own DXCC Name must be provided for scoring.")

    my_location_type = "W/VE" if my_entity_name in ["United States", "Canada"] else "DX"

    return df.apply(
        _calculate_single_qso_points, 
        axis=1,
        my_location_type=my_location_type
    )
