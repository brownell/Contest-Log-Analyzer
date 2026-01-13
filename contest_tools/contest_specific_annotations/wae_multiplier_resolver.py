# contest_tools/contest_specific_annotations/wae_multiplier_resolver.py
#
# Purpose: This module provides a custom multiplier resolver for the WAE
#          Contest. It implements the asymmetric multiplier rules for
#          EU vs. non-EU stations and the special call area district logic.
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
import re
from typing import Dict, Any, Optional
from ..contest_definitions import ContestDefinition

# The canonical prefixes used to construct the final multiplier ID.
_CANONICAL_PREFIX_MAP = {
    'K': 'K', 'VE': 'VE', 'VK': 'VK', 'ZL': 'ZL',
    'ZS': 'ZS', 'JA': 'JA', 'BY': 'BY', 'PY': 'PY'
}
# The set of DXCC prefixes that are eligible for this special multiplier.
# Note that callsigns like W1AW have a DXCCPfx of 'K'.
ELIGIBLE_DXCC_PREFIXES = set(_CANONICAL_PREFIX_MAP.keys())


def _get_call_area_district(row: pd.Series) -> Optional[str]:
    """
    Parses a callsign to find the call area district if it's from a
    special country for WAE multipliers.
    """
    call = str(row.get('Call', ''))
    portable_id = str(row.get('portableid', ''))
    dxcc_pfx = str(row.get('DXCCPfx', ''))

    # --- Step 1: Handle high-priority UA9 (Asiatic Russia) case for RA8/9/0 ---
    if dxcc_pfx == 'UA9':
        digit = None
        if len(portable_id) == 1 and portable_id.isdigit():
            digit = portable_id
        else:
            match = re.match(r'[A-Z]+(\d)', call)
            if match:
                digit = match.group(1)
        
        if digit in ['8', '9', '0']:
            return f"UA9{digit}"
        elif digit is not None: # It's a UA9 station but not 8, 9, or 0
            return "UA99" # Fallback rule
        else:
            return None # No digit found

    # --- Step 2: General Eligibility Check for other special prefixes ---
    # A call is only eligible if its DXCC entity prefix is on the special list.
    # This correctly excludes entities like KH6, KL, etc.
    if dxcc_pfx not in ELIGIBLE_DXCC_PREFIXES:
        return None

    # --- Step 3: Determine Canonical Prefix ---
    canonical_prefix = _CANONICAL_PREFIX_MAP.get(dxcc_pfx)

    # --- Step 4: Find Call Area Digit (prioritizing portable suffix) ---
    call_area_digit = None
    if len(portable_id) == 1 and portable_id.isdigit():
        call_area_digit = portable_id
    else:
        # Parse the main callsign for the first digit after letters.
        # This correctly handles VK2004ABC -> 2
        match = re.match(r'[A-Z]+(\d)', call)
        if match:
            call_area_digit = match.group(1)

    # --- Step 5: Construct and Return Multiplier ---
    if call_area_digit:
        return f"{canonical_prefix}{call_area_digit}"
    
    return None


def resolve_multipliers(df: pd.DataFrame, my_location_type: str, root_input_dir: str, contest_def: ContestDefinition) -> pd.DataFrame:
    """
    Resolves multipliers for the WAE Contest based on the logger's location.
    The target columns are read dynamically from the contest definition.
    """
    if df.empty:
        return df

    # --- Dynamically get column names from the JSON blueprint ---
    countries_rule = next((r for r in contest_def.multiplier_rules if r['name'] == 'Countries'), None)
    call_areas_rule = next((r for r in contest_def.multiplier_rules if r['name'] == 'Call Areas'), None)

    if not countries_rule or not call_areas_rule:
        raise ValueError("WAE resolver could not find required multiplier rules in ContestDefinition.")

    m1_col = countries_rule['value_column']
    m1_name_col = countries_rule['name_column']
    m2_col = call_areas_rule['value_column']
    m2_name_col = call_areas_rule['name_column']

    # Pre-initialize columns with a compatible dtype to prevent FutureWarnings
    for col in [m1_col, m1_name_col, m2_col, m2_name_col]:
        if col not in df.columns:
            df[col] = pd.NA
            df[col] = df[col].astype('object')

    # --- Step 1: Apply rules based on logger's location ---
    if my_location_type == 'DX': # Non-EU logger
        # Multipliers are only WAE entities in Europe
        eu_worked_mask = (df['Continent'] == 'EU') & (df['WAEName'].notna())
        df.loc[eu_worked_mask, m1_col] = df.loc[eu_worked_mask, 'DXCCPfx']
        df.loc[eu_worked_mask, m1_name_col] = df.loc[eu_worked_mask, 'DXCCName']

    elif my_location_type == 'EU': # European logger
        # --- Handle *IG9 Special Case First ---
        ig9_mask = (df['WAEPfx'] == '*IG9')
        df.loc[ig9_mask, m1_col] = df.loc[ig9_mask, 'WAEPfx']
        df.loc[ig9_mask, m1_name_col] = df.loc[ig9_mask, 'WAEName']

        # --- Handle all other non-EU WAE Multipliers ---
        normal_non_eu_mask = (
            (df['Continent'] != 'EU') & (df['WAEPfx'] != '*IG9')
        ) & (df['WAEName'].notna())
        
        # 1. Assign DXCC multipliers for non-EU contacts
        df.loc[normal_non_eu_mask, m1_col] = df.loc[normal_non_eu_mask, 'DXCCPfx']
        df.loc[normal_non_eu_mask, m1_name_col] = df.loc[normal_non_eu_mask, 'DXCCName']

        # Filter for QSOs with non-European stations
        non_eu_df = df[df['Continent'] != 'EU'].copy()
        if not non_eu_df.empty:
            districts = non_eu_df.apply(_get_call_area_district, axis=1)
            valid_districts = districts[districts.notna()]
            
            if not valid_districts.empty:
                df.loc[valid_districts.index, m2_col] = valid_districts
                df.loc[valid_districts.index, m2_name_col] = valid_districts
                # Clear the DXCC multiplier where a Call Area multiplier was assigned
                df.loc[valid_districts.index, [m1_col, m1_name_col]] = pd.NA
            
    return df