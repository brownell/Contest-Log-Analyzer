# contest_tools/core_annotations/_core_utils.py
#
# Purpose: A utility module containing shared helper functions used by various
#          core annotation and resolver modules.
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
from typing import Dict, Tuple, Optional, Set, List

class AliasLookup:
    """
    Parses a standard multiplier alias file (e.g., NAQPmults.dat) and provides
    a lookup method to resolve aliases to their official abbreviation and full name.
    """
    def __init__(self, data_dir_path: str, alias_filename: str):
        self.filepath = os.path.join(data_dir_path, alias_filename)
        self._lookup: Dict[str, Tuple[str, str]] = {}
        self._valid_mults: Set[str] = set()
        self.sections: Dict[str, Set[str]] = {}
        self.multiplier_to_category: Dict[str, str] = {}
        self._ambiguous_lookup: Dict[str, List[Tuple[str, str]]] = {}
        self._parse_file()

    def _parse_file(self):
        current_section = "Default"
        section_pattern = re.compile(r'#\s*---\s*(.*?)\s*---')

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    header_match = section_pattern.match(line)
                    if header_match:
                        current_section = header_match.group(1).strip()
                        if current_section not in self.sections:
                            self.sections[current_section] = set()
                        continue

                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split(':')
                    if len(parts) != 2:
                        continue
                        
                    aliases_part, official_part = parts[0], parts[1]
                    aliases = [alias.strip().upper() for alias in aliases_part.split(',')]
                    
                    match = re.match(r'([A-Z0-9]{1,4})\s+\((.*)\)', official_part.strip())
                    if not match:
                        continue
                    
                    official_abbr = match.group(1).upper()
                    full_name = match.group(2)
                    
                    self._valid_mults.add(official_abbr)
                    self.sections.setdefault(current_section, set()).add(official_abbr)
                    self.multiplier_to_category[official_abbr] = current_section

                    for alias in aliases:
                        # Check if this alias creates a new conflict
                        if alias in self._lookup and self._lookup[alias][0] != official_abbr:
                            logging.info(f"Ambiguous alias '{alias}' detected in '{os.path.basename(self.filepath)}'. Storing all possibilities.")
                            
                            # Get original mapping details
                            original_abbr = self._lookup[alias][0]
                            original_category = self.multiplier_to_category.get(original_abbr, 'Default')
                            
                            # Store both possibilities in the ambiguous lookup
                            self._ambiguous_lookup[alias] = [
                                (original_abbr, original_category),
                                (official_abbr, current_section)
                            ]
                            
                            # Remove from the clean (unambiguous) lookup
                            del self._lookup[alias]
                        
                        # If it's already ambiguous, add the new possibility
                        elif alias in self._ambiguous_lookup:
                            new_mapping = (official_abbr, current_section)
                            if new_mapping not in self._ambiguous_lookup[alias]:
                                self._ambiguous_lookup[alias].append(new_mapping)
                        
                        # If it's not in either dictionary, it's a new clean alias
                        elif alias not in self._lookup:
                            self._lookup[alias] = (official_abbr, full_name)

        except FileNotFoundError:
            logging.warning(f"Multiplier alias file not found at {self.filepath}. Alias lookup will be disabled.")
        except Exception as e:
            logging.error(f"Error reading multiplier alias file {self.filepath}: {e}")

    def get_multiplier(self, value: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Looks up an alias and returns the official multiplier abbreviation and full name.
        """
        if not isinstance(value, str):
            return pd.NA, pd.NA
            
        value_upper = value.upper()

        if value_upper in self._ambiguous_lookup:
            return "Unknown", pd.NA
            
        if value_upper in self._lookup:
            return self._lookup[value_upper]
        
        if value_upper in self._valid_mults:
            for abbr, (official_abbr, full_name) in self._lookup.items():
                if value_upper == official_abbr:
                    return official_abbr, full_name

        return pd.NA, pd.NA

    def get_ambiguous_mappings(self, alias: str) -> Optional[List[Tuple[str, str]]]:
        """Returns a list of (official_abbr, category) tuples for an ambiguous alias."""
        return self._ambiguous_lookup.get(alias.upper())

    def get_category(self, multiplier: str) -> Optional[str]:
        """
        Returns the section category for a given official multiplier abbreviation.
        """
        return self.multiplier_to_category.get(multiplier)
