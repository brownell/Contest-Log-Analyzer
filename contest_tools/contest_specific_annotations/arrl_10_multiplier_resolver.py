# contest_tools/contest_specific_annotations/arrl_10_multiplier_resolver.py
#
# Purpose: Provides contest-specific logic to resolve ARRL 10 Meter contest
#          multipliers by parsing the asymmetric received exchange.
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
import re
import logging
from typing import Dict, Any, Tuple

from ..core_annotations._core_utils import AliasLookup
from ..contest_definitions import ContestDefinition

DXCC_TO_CATEGORY = {
    "United States": "US States",
    "Canada": "Canadian Provinces",
    "Mexico": "Mexican States"
}

def _resolve_row(row: pd.Series, alias_lookup: AliasLookup, rules: Dict) -> pd.Series:
    """
    Parses the received exchange and determines the multiplier for a single QSO row,
    now with logic to handle ambiguous aliases based on context.
    """
    # Initialize results for abbreviations and names
    mult_state, mult_ve, mult_xe, mult_dxcc, mult_itu = pd.NA, pd.NA, pd.NA, pd.NA, pd.NA
    mult_statename, mult_vename, mult_xename, mult_dxccname = pd.NA, pd.NA, pd.NA, pd.NA
    rcvd_location, rcvd_serial, rcvd_itu = pd.NA, pd.NA, pd.NA
    
    worked_call = row.get('Call', '')
    worked_dxcc = row.get('DXCCName', 'Unknown')
    rcvd_exchange_full = str(row.get('RcvdExchangeFull', '')).strip()

    # --- Step 1: Determine which parsing rule to use based on station type ---
    rule_key = None
    if worked_call.endswith('/MM'):
        rule_key = "ARRL-10-RCVD-MM"
    elif worked_dxcc in ["United States", "Canada", "Mexico", "Alaska", "Hawaii"]:
        rule_key = "ARRL-10-RCVD-WVE"
    else:
        rule_key = "ARRL-10-RCVD-DX"

    # --- Step 2: Parse the raw exchange string with the selected rule ---
    rule = rules.get(rule_key)
    if rule:
        match = re.match(rule['regex'], rcvd_exchange_full)
        if match:
            parsed_data = dict(zip(rule['groups'], match.groups()))
            rcvd_location = parsed_data.get('RcvdLocation')
            rcvd_serial = parsed_data.get('RcvdSerial')
            rcvd_itu = parsed_data.get('RcvdITU')

    # --- Step 3: Populate the final multiplier columns ---
    if pd.notna(rcvd_itu):
        mult_itu = f"ITU {rcvd_itu}"
    elif pd.notna(rcvd_location):
        # --- Multi-step lookup for State/Province/XE ---
        mult_abbr, full_name = alias_lookup.get_multiplier(rcvd_location)

        if pd.isna(mult_abbr) or mult_abbr == "Unknown":
            mappings = alias_lookup.get_ambiguous_mappings(rcvd_location)
            if mappings:
                target_category = DXCC_TO_CATEGORY.get(worked_dxcc)
                for abbr, category in mappings:
                    if category == target_category:
                        mult_abbr, full_name = alias_lookup.get_multiplier(abbr) # Re-lookup to get full name
                        break
        
        if pd.notna(mult_abbr) and mult_abbr != "Unknown":
            category = alias_lookup.get_category(mult_abbr)
            if category == "US States":
                mult_state = mult_abbr
                mult_statename = full_name
            elif category == "Canadian Provinces":
                mult_ve = mult_abbr
                mult_vename = full_name
            elif category == "Mexican States":
                mult_xe = mult_abbr
                mult_xename = full_name
    else: # Fallback to DXCC for non-W/VE/XE stations
        if worked_dxcc not in ["United States", "Canada", "Mexico", "Alaska", "Hawaii", "Unknown"]:
            mult_dxcc = row.get('DXCCPfx', 'Unknown') # Use Prefix as identifier
            mult_dxccname = worked_dxcc # Use Name as the full name

    return pd.Series([
        rcvd_location, rcvd_serial, rcvd_itu,
        mult_state, mult_statename,
        mult_ve, mult_vename,
        mult_xe, mult_xename,
        mult_dxcc, mult_dxccname,
        mult_itu
    ])


def resolve_multipliers(df: pd.DataFrame, my_location_type: str, root_input_dir: str, contest_def: ContestDefinition) -> pd.DataFrame:
    """
    Resolves multipliers for the ARRL 10 Meter contest.
    """
    if df.empty:
        return df

    # Initialize utilities
    data_dir = os.path.join(root_input_dir, 'data')
    alias_lookup = AliasLookup(data_dir, 'arrl_10_mults.dat')
    rules = contest_def.exchange_parsing_rules

    # Dynamically build the list of target columns from the contest definition
    parsed_cols = ['RcvdLocation', 'RcvdSerial', 'RcvdITU']
    mult_cols = []
    # Note: The order of rules in the JSON matters and must match the return order of _resolve_row
    for rule in contest_def.multiplier_rules:
        if 'value_column' in rule:
            mult_cols.append(rule['value_column'])
        if 'name_column' in rule:
            mult_cols.append(rule['name_column'])
    
    target_cols = parsed_cols + mult_cols
    
    df[target_cols] = df.apply(_resolve_row, axis=1, alias_lookup=alias_lookup, rules=rules)

    return df
