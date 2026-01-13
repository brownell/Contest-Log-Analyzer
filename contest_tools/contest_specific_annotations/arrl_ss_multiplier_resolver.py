# contest_tools/contest_specific_annotations/arrl_ss_multiplier_resolver.py
#
# Purpose: Provides contest-specific logic to resolve ARRL Sweepstakes multipliers
#          (Sections) from the explicit exchange field.
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
from typing import Dict, Tuple, Optional
from ..contest_definitions import ContestDefinition

class SectionAliasLookup:
    """Parses and provides lookups for the SweepstakesSections.dat file."""
    
    def __init__(self, data_dir_path: str):
        self.filepath = os.path.join(data_dir_path, 'SweepstakesSections.dat')
        self._lookup: Dict[str, Tuple[str, str]] = {}
        self._valid_mults: set = set()
        self._parse_file()

    def _parse_file(self):
        try:
             with open(self.filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split(':')
                    if len(parts) != 2:
                        continue
                
                    aliases_part, official_part = parts[0], parts[1]
                    aliases = [alias.strip().upper() for alias in aliases_part.split(',')]
                    
                    match = re.match(r'([A-Z]{2,3})\s+\((.*)\)', official_part.strip())
                    if not match:
                        continue
                    
                    official_abbr = match.group(1).upper()
                    full_name = match.group(2)
                    
                    self._valid_mults.add(official_abbr)
                    for alias in aliases:
                        self._lookup[alias] = (official_abbr, full_name)
        except FileNotFoundError:
            print(f"Warning: Section alias file not found at {self.filepath}. Alias lookup will be disabled.")
        except Exception as e:
            print(f"Error reading section alias file {self.filepath}: {e}")

    def get_section(self, value: str) -> Tuple[str, Optional[str]]:
        """
        Looks up an alias and returns the official section abbreviation and name.
        """
        if not isinstance(value, str):
            return "Unknown", None
            
        value_upper = value.upper()
        
        if value_upper in self._lookup:
            return self._lookup[value_upper]

        if value_upper in self._valid_mults:
            for abbr, (official_abbr, full_name) in self._lookup.items():
                if value_upper == official_abbr:
                    return official_abbr, full_name
        
        return "Unknown", None

def resolve_multipliers(df: pd.DataFrame, my_location_type: Optional[str], root_input_dir: str, contest_def: ContestDefinition) -> pd.DataFrame:
    """
    Resolves the final Section multiplier for ARRL Sweepstakes QSOs.
    """
    # Dynamically get column names from the JSON blueprint
    mult_rule = next((r for r in contest_def.multiplier_rules if r['name'] == 'Sections'), {})
    value_col = mult_rule.get('value_column', 'Mult1')
    name_col = mult_rule.get('name_column', 'Mult1Name')

    if df.empty or 'RcvdLocation' not in df.columns:
        df[value_col] = "Unknown"
        df[name_col] = None
        return df

    data_dir = os.path.join(root_input_dir, 'data')
    alias_lookup = SectionAliasLookup(data_dir)
    
    # Apply the lookup and expand the resulting tuple into two new columns
    df[[value_col, name_col]] = df['RcvdLocation'].apply(
        lambda x: pd.Series(alias_lookup.get_section(x))
    )
    
    # Drop the old intermediate column if it exists
    if 'FinalMultiplier' in df.columns:
        df.drop(columns=['FinalMultiplier'], inplace=True)
        
    return df
