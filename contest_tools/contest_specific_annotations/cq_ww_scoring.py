# contest_tools/contest_specific_annotations/cq_ww_scoring.py
#
# Purpose: Provides contest-specific scoring logic for the CQ WW DX contest.
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

def _calculate_single_qso_points(row: pd.Series, my_continent: str, my_dxcc_name: str) -> int:
    """
    Calculates the point value for a single QSO based on CQ WW rules.
    """
    # Rule 0: Dupes are always worth 0 points.
    if row['Dupe']:
        return 0

    worked_continent = row.get('Continent')
    worked_dxcc_name = row.get('DXCCName')

    # Rule 1 (Most Specific): Contacts between stations in the same country are worth 0 points.
    if worked_dxcc_name == my_dxcc_name:
        return 0
    
    # Rule 2 (Regional Exception): Contacts between stations in different countries within North America are worth 2 points.
    if my_continent == 'NA' and worked_continent == 'NA':
        return 2

    # Rules 3 & 4 Combined (General):
    if worked_continent and worked_continent != my_continent:
        # Different continents are worth 3 points.
        return 3
    else:
        # By elimination, this is a same-continent, different-country contact (1 point),
        # or a QSO with missing data (which will fall through).
        if worked_continent:
            return 1
    
    # Fallback case for any QSOs that slip through (e.g., missing location data).
    return 0


def calculate_points(df: pd.DataFrame, my_call_info: Dict[str, Any]) -> pd.Series:
    """
    Calculates QSO points for an entire DataFrame based on CQ WW DX rules.

    Args:
        df (pd.DataFrame): The DataFrame of QSOs to be scored.
        my_call_info (Dict[str, Any]): A dictionary containing the logger's
                                       own location info ('Continent', 'DXCCName').

    Returns:
        pd.Series: A Pandas Series containing the calculated points for each QSO.
    """
    my_continent = my_call_info.get('Continent')
    my_dxcc_name = my_call_info.get('DXCCName')
    
    if not my_continent or not my_dxcc_name:
        raise ValueError("Logger's Continent and DXCC Name must be provided.")
        
    return df.apply(
        _calculate_single_qso_points,
        axis=1,
        my_continent=my_continent,
        my_dxcc_name=my_dxcc_name
    )
