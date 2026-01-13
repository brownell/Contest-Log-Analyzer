# contest_tools/contest_specific_annotations/_arrl_dx_utils.py
#
# Purpose: Provides shared, contest-specific utilities for the ARRL DX contest,
#          such as the State/Province lookup class.
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

import os
import re
from typing import Dict, Tuple, Set

class StateAndProvinceLookup:
    """
    Parses ARRLDXmults.dat and categorizes multipliers to support rules that
    differentiate between US States/DC and Canadian Provinces.
    """
    def __init__(self, data_dir_path: str):
        self.filepath = os.path.join(data_dir_path, 'ARRLDXmults.dat')
        self._lookup: Dict[str, str] = {}
        self._us_states: Set[str] = set()
        self._ca_provinces: Set[str] = set()
        self._parse_file()

    def _parse_file(self):
        """Parses the .dat file, categorizing multipliers by section."""
        current_category = None
        section_pattern = re.compile(r'#\s*---\s*(.*?)\s*---')

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    header_match = section_pattern.match(line)
                    if header_match:
                        section_name = header_match.group(1).strip()
                        if 'US States' in section_name:
                            current_category = 'US'
                        elif 'Canadian' in section_name:
                            current_category = 'CA'
                        continue

                    if not line or line.startswith('#') or not current_category:
                        continue
                    
                    parts = line.split(':')
                    if len(parts) != 2:
                        continue
                        
                    aliases_part, official_part = parts[0], parts[1]
                    aliases = [alias.strip().upper() for alias in aliases_part.split(',')]
                    
                    match = re.match(r'([A-Z]{2})\s+\((.*)\)', official_part.strip())
                    if not match:
                        continue
                    
                    official_abbr = match.group(1).upper()
                    
                    if current_category == 'US':
                        self._us_states.add(official_abbr)
                    elif current_category == 'CA':
                        self._ca_provinces.add(official_abbr)

                    for alias in aliases:
                        self._lookup[alias] = official_abbr
        except Exception as e:
            print(f"Error reading ARRL DX multiplier file {self.filepath}: {e}")

    def get_multiplier(self, value: str) -> str:
        """Looks up an alias and returns the official abbreviation."""
        if not isinstance(value, str):
            return "Unknown"
        
        value_upper = value.upper()
        if value_upper in self._us_states or value_upper in self._ca_provinces:
            return value_upper
        
        return self._lookup.get(value_upper, "Unknown")

    def is_us_state_or_dc(self, value: str) -> bool:
        """Returns True if the value is a valid US State or DC multiplier."""
        if not isinstance(value, str):
            return False
        
        value_upper = value.upper()
        if value_upper in self._us_states:
            return True
        
        resolved_abbr = self._lookup.get(value_upper)
        return resolved_abbr in self._us_states
