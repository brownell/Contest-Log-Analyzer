# contest_tools/utils/pivot_utils.py
#
# Purpose: Neutral utility for shared DataFrame manipulation logic to prevent circular imports.
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

def calculate_multiplier_pivot(df: pd.DataFrame, mult_col: str, group_by_call: bool = False) -> pd.DataFrame:
    """
    Creates an authoritative pivot table for a given multiplier column.
    This is the single source of truth for multiplier counting.
    """
    if df.empty or mult_col not in df.columns:
        return pd.DataFrame()
    
    index_cols = [mult_col]
    if group_by_call and 'MyCall' in df.columns:
        index_cols.append('MyCall')
    
    return df.pivot_table(index=index_cols, columns='Band', aggfunc='size', fill_value=0)