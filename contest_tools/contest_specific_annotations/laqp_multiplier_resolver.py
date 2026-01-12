# contest_tools/contest_specific_annotations/naqp_multiplier_resolver.py
#
# Purpose: Provides contest-specific logic to resolve NAQP multipliers
#          (States/Provinces and North American DXCC entities).
#
# Author: Gemini AI
# Date: 2025-10-01
# Version: 0.90.0-Beta
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
# --- Revision History ---
# [0.90.0-Beta] - 2025-10-01
# Set new baseline version for release.

import pandas as pd
import os
from ..core_annotations._core_utils import AliasLookup
from typing import Optional, Any, Tuple
from ..contest_definitions import ContestDefinition

def _get_naqp_multiplier(row: pd.Series, alias_lookup: AliasLookup) -> Tuple[Any, Any, Any, Any]:
    """
    Applies the NAQP multiplier logic to a single QSO row, returning separate
    values and names for State/Province and NA DXCC multipliers.
    """
    stprov_mult, stprov_name = pd.NA, pd.NA
    nadxcc_mult, nadxcc_name = pd.NA, pd.NA
    
    dxcc_pfx = row.get('DXCCPfx')
    continent = row.get('Continent')
    rcvd_location = row.get('RcvdLocation')

    # 1. Initial Sanity Check
    if pd.isna(dxcc_pfx) or dxcc_pfx == 'Unknown':
        return "Unknown", pd.NA, pd.NA, pd.NA

    # 2. Check for US (including AK/HI) or Canada (State/Province mults)
    if dxcc_pfx in ['K', 'KH6', 'KL', 'VE']:
        mult, name = alias_lookup.get_multiplier(rcvd_location)
        stprov_mult = mult if pd.notna(mult) else "Unknown"
        stprov_name = name if pd.notna(name) else pd.NA

    # 3. Check for Other North American DXCC
    elif continent == 'NA':
        nadxcc_mult = dxcc_pfx
        nadxcc_name = row.get('DXCCName')

    return stprov_mult, stprov_name, nadxcc_mult, nadxcc_name


def resolve_multipliers(df: pd.DataFrame, my_location_type: Optional[str], root_input_dir: str, contest_def: ContestDefinition) -> pd.DataFrame:
    """
    Resolves multipliers for the NAQP contest by identifying the multiplier
    for each QSO and placing it into the appropriate new column.
    """
    if df.empty:
        return df

    # Ensure required columns exist before proceeding
    required_cols = ['DXCCPfx', 'Continent', 'RcvdLocation', 'DXCCName']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(
                f"Cannot resolve NAQP multipliers: DataFrame is missing "
                f"required column '{col}'."
            )

    # Initialize the alias lookup utility for NAQP multipliers.
    data_dir = os.path.join(root_input_dir, 'data')
    alias_lookup = AliasLookup(data_dir, 'NAQPmults.dat')

    # Dynamically get column names from the JSON blueprint
    stprov_rule = next((r for r in contest_def.multiplier_rules if r['name'] == 'STPROV'), {})
    nadxcc_rule = next((r for r in contest_def.multiplier_rules if r['name'] == 'NA DXCC'), {})
    
    stprov_col = stprov_rule.get('value_column', 'Mult_STPROV')
    stprov_name_col = stprov_rule.get('name_column', 'Mult_STPROVName')
    nadxcc_col = nadxcc_rule.get('value_column', 'Mult_NADXCC')
    nadxcc_name_col = nadxcc_rule.get('name_column', 'Mult_NADXCCName')
    target_cols = [stprov_col, stprov_name_col, nadxcc_col, nadxcc_name_col]
    
    df[target_cols] = df.apply(
        _get_naqp_multiplier, axis=1, result_type='expand', alias_lookup=alias_lookup
    )
    
    # Clean up old columns if they exist from previous versions
    cols_to_drop = ['Mult1', 'STPROV_Mult', 'NADXCC_Mult', 'NADXCC_MultName']
    df.drop(columns=[col for col in cols_to_drop if col in df.columns], inplace=True)

    return df
