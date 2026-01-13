# contest_tools/contest_specific_annotations/cq_160_scoring.py
#
# Purpose: Provides contest-specific scoring logic for the CQ 160 contest.
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

_DX_POINTS = {
    "inter-continental": 10, # Between continents
    "intra-continental": 5,  # Within same continent, but different country
    "own-country": 2         # Within same country
}

def calculate_points(df: pd.DataFrame, my_call_info: Dict[str, Any]) -> pd.Series:
    """
    Calculates QSO points for an entire DataFrame based on CQ 160 rules.
    """
    if df.empty or 'Dupe' not in df.columns:
        return pd.Series(0, index=df.index)

    # Dupes are always 0 points.
    dupe_mask = df['Dupe'] == True
    
    # QSOs with my own station are always 0 points.
    my_call = my_call_info.get('MyCall', '')
    my_call_mask = df['Call'] == my_call

    # Get my own location info
    my_continent = my_call_info.get('Continent')
    my_dxcc_name = my_call_info.get('DXCCName')
    if not my_continent or not my_dxcc_name:
        raise ValueError("Logger's Continent and DXCC Name must be provided.")

    # Apply rules based on worked station's location
    inter_cont_mask = df['Continent'] != my_continent
    intra_cont_mask = (df['Continent'] == my_continent) & (df['DXCCName'] != my_dxcc_name)
    own_country_mask = df['DXCCName'] == my_dxcc_name
    
    # Calculate points
    points = pd.Series(0, index=df.index)
    points[inter_cont_mask] = _DX_POINTS['inter-continental']
    points[intra_cont_mask] = _DX_POINTS['intra-continental']
    points[own_country_mask] = _DX_POINTS['own-country']

    # Set points for dupes and self-contacts to zero
    points[dupe_mask | my_call_mask] = 0

    return points
