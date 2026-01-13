# contest_tools/contest_specific_annotations/arrl_dx_multiplier_resolver.py
#
# Purpose: Provides contest-specific logic to resolve ARRL DX Contest multipliers
#          (States/Provinces) from callsigns or explicit exchange fields.
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
from typing import Dict
from ..contest_definitions import ContestDefinition

def resolve_multipliers(df: pd.DataFrame, my_location_type: str, root_input_dir: str, contest_def: ContestDefinition) -> pd.DataFrame:
    """
    Resolves multipliers for ARRL DX based on the logger's location, prioritizing
    the received exchange over the callsign's prefix according to refined rules.
    """
    if df.empty:
        return df

    data_dir = os.path.join(root_input_dir, 'data')
    lookup = AliasLookup(data_dir, 'ARRLDXmults.dat')

    # Dynamically get column names from the JSON blueprint
    dxcc_rule = next((r for r in contest_def.multiplier_rules if r['name'] == 'DXCC'), {})
    stprov_rule = next((r for r in contest_def.multiplier_rules if r['name'] == 'STPROV'), {})

    dxcc_col = dxcc_rule.get('source_column', 'Mult_DXCC')
    dxcc_name_col = dxcc_rule.get('source_name_column', 'Mult_DXCCName')
    stprov_col = stprov_rule.get('source_column', 'Mult_STPROV')
    stprov_name_col = stprov_rule.get('source_name_column', 'STPROV_MultName')

    # Initialize new columns
    for col in [stprov_col, stprov_name_col, dxcc_col, dxcc_name_col]:
        df[col] = pd.NA
    df['STPROV_IsNewMult'] = 0
    df['DXCC_IsNewMult'] = 0
    
    seen_stprov_per_band = {band: set() for band in df['Band'].unique() if pd.notna(band)}
    seen_dxcc_per_band = {band: set() for band in df['Band'].unique() if pd.notna(band)}
    
    NON_CONTIGUOUS_STATES = {'AK', 'HI'}

    df_sorted = df.sort_values(by='Datetime')

    for idx, row in df_sorted.iterrows():
        band = row.get('Band')
        if not band: continue
             
        dxcc_id = str(row.get('DXCCPfx', ''))
        rcvd_location = row.get('RcvdLocation', '')
        
        # --- Apply rules based on LOGGER's location ---
        if my_location_type == 'DX':
            resolved_stprov = pd.NA
            resolved_stprov_name = pd.NA

            if dxcc_id in ['K', 'VE']:
                resolved_stprov, resolved_stprov_name = lookup.get_multiplier(rcvd_location)
            elif dxcc_id.startswith('K'):
                # Check if the received location is a valid US State/DC
                temp_abbr, _ = lookup.get_multiplier(rcvd_location)
                if pd.notna(temp_abbr):
                    category = lookup.get_category(temp_abbr)
                    if category and 'US States' in category:
                        resolved_stprov, resolved_stprov_name = temp_abbr, _
            
            if pd.notna(resolved_stprov) and resolved_stprov != "Unknown" and resolved_stprov not in NON_CONTIGUOUS_STATES:
                df.loc[idx, stprov_col] = resolved_stprov
                df.loc[idx, stprov_name_col] = resolved_stprov_name
                if resolved_stprov not in seen_stprov_per_band[band]:
                    df.loc[idx, 'STPROV_IsNewMult'] = 1
                    seen_stprov_per_band[band].add(resolved_stprov)
       
        elif my_location_type == 'W/VE':
            worked_dxcc_name = row.get('DXCCName', 'Unknown')
            is_dx_multiplier = worked_dxcc_name not in ["United States", "Canada"]

            if is_dx_multiplier:
                dxcc_mult = row.get('DXCCPfx')
                df.loc[idx, dxcc_col] = dxcc_mult
                df.loc[idx, dxcc_name_col] = worked_dxcc_name
                if pd.notna(dxcc_mult) and dxcc_mult not in seen_dxcc_per_band[band]:
                    df.loc[idx, 'DXCC_IsNewMult'] = 1
                    seen_dxcc_per_band[band].add(dxcc_mult)
    
    return df
