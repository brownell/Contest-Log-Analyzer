# contest_tools/contest_specific_annotations/cq_160_parser.py
#
# Purpose: This module provides a custom parser for the CQ 160-Meter Contest,
#          which has a complex exchange format that can include a state,
#          province, or "DX".
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
from typing import Dict, Any, List, Tuple
import os
import logging

from ..contest_definitions import ContestDefinition
from ..cabrillo_parser import parse_qso_common_fields

def parse_log(filepath: str, contest_definition: ContestDefinition, root_input_dir: str, cty_dat_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Custom parser for the CQ 160-Meter Contest.
    """
    log_metadata: Dict[str, Any] = {}
    qso_records: List[Dict[str, Any]] = []

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        raise ValueError(f"Error reading Cabrillo file {filepath}: {e}")

    # --- Pre-scan header to determine the specific contest ID (e.g., CQ-160-CW) ---
    contest_id_from_header = ''
    for line in lines[:30]: # Check first 30 lines for the header
        if line.upper().startswith('CONTEST:'):
            contest_id_from_header = line.split(':', 1)[1].strip()
            log_metadata['ContestName'] = contest_id_from_header
            break
    
    if not contest_id_from_header:
        raise ValueError("CONTEST: tag not found in Cabrillo header.")

    rules_for_contest = contest_definition.exchange_parsing_rules.get(contest_id_from_header, [])
    if not isinstance(rules_for_contest, list):
        rules_for_contest = [rules_for_contest]

    for line in lines:
        cleaned_line = line.replace('\u00a0', ' ').strip()
        line_to_process = cleaned_line.upper() if cleaned_line.upper().startswith('QSO:') else cleaned_line
        
        if not line_to_process:
            continue
        elif line_to_process.startswith('END-OF-LOG:'):
            break
        elif line_to_process.startswith('QSO:'):
            common_data = parse_qso_common_fields(line_to_process)
            if not common_data:
                continue

            exchange_rest = common_data.pop('ExchangeRest', '').strip()
            
            for rule_info in rules_for_contest:
                exchange_match = re.match(rule_info['regex'], exchange_rest)
                if exchange_match:
                    exchange_data = dict(zip(rule_info['groups'], exchange_match.groups()))
                    common_data.update(exchange_data)
                    common_data['RawQSO'] = line_to_process
                    qso_records.append(common_data)
                    break
        
        elif not line_to_process.startswith('START-OF-LOG:'):
            for cabrillo_tag, df_key in contest_definition.header_field_map.items():
                if line_to_process.startswith(f"{cabrillo_tag}:"):
                    value = line_to_process[len(f"{cabrillo_tag}:"):].strip()
                    log_metadata[df_key] = value
                    break

    if not qso_records:
        raise ValueError(f"No valid QSO lines found in Cabrillo file: {filepath}")
    
    df = pd.DataFrame(qso_records)
    return df, log_metadata
