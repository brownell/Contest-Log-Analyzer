# contest_tools/contest_specific_annotations/iaru_hf_scoring.py
#
# Purpose: Provides contest-specific scoring logic for the IARU HF World
#          Championship contest.
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

def _calculate_qso_points(row: pd.Series, my_continent: str, my_itu_zone: int) -> int:
    """
    Calculates the point value for a single QSO based on IARU HF Championship rules.
    """
    # Rule 0: Dupes are always worth 0 points.
    if row['Dupe']:
        return 0

    # Rule 5.1.2: Contacts with an IARU HQ or IARU official station count one (1) point.
    # This rule takes precedence over location-based scoring.
    if pd.notna(row.get('Mult_HQ')) or pd.notna(row.get('Mult_Official')):
        return 1

    worked_continent = row.get('Continent')
    worked_itu_zone = pd.to_numeric(row.get('Mult_Zone'), errors='coerce')

    # If location data is missing for the worked station, no points can be awarded.
    if pd.isna(worked_continent) or pd.isna(worked_itu_zone):
        return 0
    
    # --- Location-Based Scoring for regular Zone stations ---

    # Rule 5.1.5: Contacts with a different continent and ITU zone count five (5) points.
    if worked_continent != my_continent and worked_itu_zone != my_itu_zone:
        return 5
    
    # Rule 5.1.4: Contacts within your continent but in a different ITU zone count three (3) points.
    if worked_continent == my_continent and worked_itu_zone != my_itu_zone:
        return 3

    # Rule 5.1.1 & 5.1.3: Contacts within your own ITU zone count one (1) point.
    # This applies regardless of continent.
    if worked_itu_zone == my_itu_zone:
        return 1
    
    # Fallback case if no other rule matches.
    return 0


def calculate_points(df: pd.DataFrame, my_call_info: Dict[str, Any]) -> pd.Series:
    """
    Calculates QSO points for an entire DataFrame based on IARU HF Championship rules.
    """
    my_continent = my_call_info.get('Continent')
    my_itu_zone = my_call_info.get('ITUZone')
    
    if not my_continent or pd.isna(my_itu_zone):
        raise ValueError("Logger's Continent and ITU Zone must be provided for scoring.")

    return df.apply(
        _calculate_qso_points,
        axis=1,
        my_continent=my_continent,
        my_itu_zone=int(my_itu_zone)
    )
