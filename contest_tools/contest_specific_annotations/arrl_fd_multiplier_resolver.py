# contest_tools/contest_specific_annotations/arrl_fd_multiplier_resolver.py
#
# Purpose: Provides contest-specific logic to resolve the ARRL/RAC Section
#          from the ARRL Field Day exchange.
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
import os
from typing import Optional, Any, Dict

from ..core_annotations._core_utils import AliasLookup
from ..contest_definitions import ContestDefinition

def _resolve_row(row: pd.Series, alias_lookup: AliasLookup) -> str:
    """Validates the received section for a single QSO row."""
    rcvd_section = row.get('RcvdSection')
    
    if pd.isna(rcvd_section):
        return pd.NA
        
    if rcvd_section.upper() == 'DX':
        return 'DX'
        
    mult_abbr, _ = alias_lookup.get_multiplier(rcvd_section)
    
    return mult_abbr if pd.notna(mult_abbr) else "Unknown"

def resolve_multipliers(df: pd.DataFrame, my_location_type: str, root_input_dir: str, contest_def: ContestDefinition) -> pd.DataFrame:
    """
    Resolves the ARRL/RAC Section for ARRL Field Day QSOs.
    """
    # Dynamically get column name from the JSON blueprint
    mult_rule = next((r for r in contest_def.multiplier_rules if r['name'] == 'Sections'), {})
    mult_col = mult_rule.get('value_column', 'Mult_Section')

    if df.empty or 'RcvdSection' not in df.columns:
        df[mult_col] = pd.NA
        return df

    data_dir = os.path.join(root_input_dir, 'data')
    alias_lookup = AliasLookup(data_dir, 'SweepstakesSections.dat')
    
    df[mult_col] = df.apply(_resolve_row, axis=1, alias_lookup=alias_lookup)
    
    return df
