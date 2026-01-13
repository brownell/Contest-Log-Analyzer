# contest_tools/contest_definitions/__init__.py
#
# Purpose: Defines the ContestDefinition class, responsible for loading and managing
#          contest-specific rules and mappings from JSON files. It handles merging
#          common Cabrillo field definitions with contest-specific overrides.
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

import json
import os
import copy
from typing import Dict, Any, Optional, List

# --- Constants ---
# Name of the common Cabrillo fields JSON file
COMMON_CABRILLO_FIELDS_FILE = '_common_cabrillo_fields.json'

class ContestDefinition:
    """
    Manages and provides access to contest-specific rules and data mappings
    loaded from JSON configuration files. Handles merging common definitions
    with contest-specific overrides.
    """

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @classmethod
    def _deep_merge_dicts(cls, base: Dict, new: Dict) -> Dict:
        base = copy.deepcopy(base)
        for key, value in new.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = cls._deep_merge_dicts(base[key], value)
            else:
                base[key] = value
        return base

    @classmethod
    def from_json(cls, contest_name: str) -> 'ContestDefinition':
        """
        Loads a contest definition from JSON, handling both explicit inheritance
        ("inherits_from") and implicit generic/specific file patterns.
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        def find_and_load(name: str) -> Optional[dict]:
            """Helper to attempt loading a JSON file by its base name."""
            file_path = os.path.join(current_dir, f"{name.lower().replace('-', '_').replace(' ', '_')}.json")
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None

        # Load common fields first as the absolute base
        common_file_path = os.path.join(current_dir, COMMON_CABRILLO_FIELDS_FILE)
        with open(common_file_path, 'r', encoding='utf-8') as f:
            base_data = json.load(f)

        # 1. Attempt to load the specific contest file (e.g., arrl_ss_cw.json)
        contest_data = find_and_load(contest_name)
        
        # 2. If specific fails, attempt to load the generic file (e.g., arrl_ss.json)
        if contest_data is None:
            try:
                generic_name = contest_name.rsplit('-', 1)[0]
                contest_data = find_and_load(generic_name)
            except IndexError:
                pass # No hyphen to split, so no generic name to try

        if contest_data is None:
            raise FileNotFoundError(f"No definition file found for '{contest_name}'")
            
        # 3. Handle explicit inheritance if present
        if "inherits_from" in contest_data:
            parent_data = find_and_load(contest_data["inherits_from"])
            if parent_data:
                # Parent data becomes the new base for the specific data to override
                contest_data = cls._deep_merge_dicts(parent_data, contest_data)

        merged_data = cls._deep_merge_dicts(base_data, contest_data)
        return cls(merged_data)

    @property
    def contest_name(self) -> str:
        return self._data.get('contest_name', 'Unknown Contest')

    @property
    def valid_bands(self) -> List[str]:
        return self._data.get('valid_bands', [
            '160M', '80M', '40M', '20M', '15M', '10M'
        ])

    @property
    def operating_time_rules(self) -> Optional[Dict[str, int]]:
        return self._data.get('operating_time_rules')
        
    @property
    def contest_specific_event_id_resolver(self) -> Optional[str]:
        return self._data.get('contest_specific_event_id_resolver')

    @property
    def multiplier_rules(self) -> List[Dict[str, Any]]:
        return self._data.get('multiplier_rules', [])

    @property
    def mutually_exclusive_mults(self) -> List[List[str]]:
        return self._data.get('mutually_exclusive_mults', [])

    @property
    def excluded_reports(self) -> List[str]:
        return self._data.get('excluded_reports', [])
        
    @property
    def included_reports(self) -> List[str]:
        return self._data.get('included_reports', [])
        
    @property
    def mults_from_zero_point_qsos(self) -> bool:
        return self._data.get('mults_from_zero_point_qsos', True)

    @property
    def enable_adif_export(self) -> bool:
        return self._data.get('enable_adif_export', False)

    @property
    def is_naqp_ruleset(self) -> bool:
        return self._data.get('is_naqp_ruleset', False)

    @property
    def dupe_check_scope(self) -> str:
        return self._data.get('dupe_check_scope', 'per_band')

    @property
    def custom_parser_module(self) -> Optional[str]:
        return self._data.get('custom_parser_module')

    @property
    def custom_multiplier_resolver(self) -> Optional[str]:
        return self._data.get('custom_multiplier_resolver')

    @property
    def custom_adif_exporter(self) -> Optional[str]:
        return self._data.get('custom_adif_exporter')

    @property
    def time_series_calculator(self) -> Optional[str]:
        return self._data.get('time_series_calculator')
        
    @property
    def custom_location_resolver(self) -> Optional[str]:
        return self._data.get('custom_location_resolver')

    @property
    def points_header_label(self) -> Optional[str]:
        return self._data.get('points_header_label')

    @property
    def contest_period(self) -> Optional[Dict[str, str]]:
        return self._data.get('contest_period')

    @property
    def multiplier_report_scope(self) -> str:
        return self._data.get('multiplier_report_scope', 'per_band')

    @property
    def score_formula(self) -> str:
        return self._data.get('score_formula', 'points_times_mults')

    @property
    def scoring_module(self) -> Optional[str]:
        return self._data.get('scoring_module')

    @property
    def cabrillo_version(self) -> str:
        return self._data.get('cabrillo_version', 'Unknown')

    @property
    def header_field_map(self) -> Dict[str, str]:
        return self._data.get('header_field_map', {})

    @property
    def qso_common_fields_regex(self) -> str:
        return self._data.get('qso_common_fields_regex', '')

    @property
    def qso_common_field_names(self) -> list[str]:
        return self._data.get('qso_common_field_names', [])

    @property
    def exchange_parsing_rules(self) -> Dict[str, Dict[str, Any]]:
        return self._data.get('exchange_parsing_rules', {})

    @property
    def default_qso_columns(self) -> list[str]:
        return self._data.get('default_qso_columns', [])

    @property
    def scoring_rules(self) -> Dict[str, Any]:
        return self._data.get('scoring_rules', {})

    def get_exchange_parse_info(self, cabrillo_contest_name: str) -> Optional[Dict[str, Any]]:
        return self.exchange_parsing_rules.get(cabrillo_contest_name)