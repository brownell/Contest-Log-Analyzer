# contest_tools/contest_specific_annotations/cq_160_multiplier_resolver.py
#
# Purpose: Provides contest-specific logic to resolve CQ 160 contest multipliers
#          (States/Provinces for DX, DXCC for W/VE).
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
import logging
from ..core_annotations._core_utils import AliasLookup
from typing import Optional, Tuple
from ..contest_definitions import ContestDefinition

def resolve_multipliers(df: pd.DataFrame, my_location_type: Optional[str], root_input_dir: str, contest_def: ContestDefinition) -> pd.DataFrame:
    """
    Resolves multipliers for the CQ 160 contest.
    """
    if df.empty:
        return df
        
    # --- Dynamically get column names from the JSON blueprint ---
    try:
        stprov_rule = next((r for r in contest_def.multiplier_rules if r['name'] == 'STPROV'), None)
        dxcc_rule = next((r for r in contest_def.multiplier_rules if r['name'] == 'DXCC'), None)
        if not stprov_rule or not dxcc_rule:
            raise ValueError("Could not find STPROV or DXCC rules in definition.")
            
        stprov_col = stprov_rule['source_column']
        stprov_name_col = stprov_rule['source_name_column']
        dxcc_col = dxcc_rule['source_column']
        dxcc_name_col = dxcc_rule['source_name_column']
    except (AttributeError, KeyError, IndexError, ValueError) as e:
        logging.error(f"Could not extract CQ-160 column names from ContestDefinition: {e}. Aborting resolver.")
        return df

    data_dir = os.path.join(root_input_dir, 'data')
    alias_lookup = AliasLookup(data_dir, 'CQ160mults.dat')

    def get_stprov_mult(row) -> Tuple[Optional[str], Optional[str]]:
        if row.get('DXCCName') in ["United States", "Canada"]:
            location = row.get('RcvdLocation', '')
            mult_abbr, mult_name = alias_lookup.get_multiplier(location)
            return mult_abbr, mult_name
        return pd.NA, pd.NA

    df[[stprov_col, stprov_name_col]] = df.apply(get_stprov_mult, axis=1, result_type='expand')

    df[dxcc_col] = df['DXCCPfx']
    df[dxcc_name_col] = df['DXCCName']

    return df