# contest_tools/contest_specific_annotations/wae_parser.py
#
# Purpose: This module provides a custom parser for the Worked All Europe (WAE)
#          Contest. It is unique in that it must parse both QSO: and QTC:
#          records from the Cabrillo log.
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

# A robust regex to capture all 10 fields of a QTC line, tolerant of whitespace.
QTC_LINE_RE = re.compile(r"QTC:\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)")
QTC_FIELD_NAMES = [
    'QTC_QRG', 'QTC_MODE', 'QTC_DATE', 'QTC_TIME', 'QTC_CALL_RX', 'QTC_GRP',
    'QTC_CALL_TX', 'QTC_TIME_QSO', 'QTC_CALL_QSO', 'QTC_NR_QSO'
]

def parse_log(filepath: str, contest_definition: ContestDefinition, root_input_dir: str, cty_dat_path: str) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Custom parser for the WAE Contest.
    Returns three values: (qsos_df, qtcs_df, metadata)
    """
    log_metadata: Dict[str, Any] = {}
    qso_records: List[Dict[str, Any]] = []
    qtc_records: List[Dict[str, Any]] = []

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    for line in lines:
        cleaned_line = line.replace('\u00a0', ' ').strip()
        line_to_process = cleaned_line.upper() if cleaned_line.upper().startswith(('QSO:', 'QTC:')) else cleaned_line

        if not line_to_process or line_to_process.startswith(('END-OF-LOG:', 'START-OF-LOG:')):
            continue

        if line_to_process.startswith('QSO:'):
            common_data = parse_qso_common_fields(line_to_process)
            if not common_data:
                continue

            # WAE-specific QSO parsing
            rule_key = contest_definition.contest_name
            rule_info = contest_definition.exchange_parsing_rules.get(rule_key)
            if not rule_info:
                raise ValueError(f"Parsing rule '{rule_key}' not found in JSON definition.")
            
            exchange_regex = re.compile(rule_info['regex'])
            exchange_groups = rule_info['groups']
            exchange_rest = common_data.pop('ExchangeRest', '').strip()
            
            exchange_match = exchange_regex.match(exchange_rest)
            if exchange_match:
                exchange_data = dict(zip(exchange_groups, exchange_match.groups()))
                common_data.update(exchange_data)
                common_data['RawQSO'] = line_to_process
                qso_records.append(common_data)

        elif line_to_process.startswith('QTC:'):
            match = QTC_LINE_RE.match(line_to_process)
            if match:
                qtc_records.append(dict(zip(QTC_FIELD_NAMES, match.groups())))
            else:
                logging.warning(f"Malformed QTC line skipped: {line_to_process}")
        else:
            # It's a header line
            for cabrillo_tag, df_key in contest_definition.header_field_map.items():
                if line_to_process.startswith(f"{cabrillo_tag}:"):
                    value = line_to_process[len(f"{cabrillo_tag}:"):].strip()
                    log_metadata[df_key] = value
                    break

    if not qso_records:
        logging.warning(f"Custom parser found no valid QSO lines in Cabrillo file: {filepath}")
    
    qsos_df = pd.DataFrame(qso_records)
    qtcs_df = pd.DataFrame(qtc_records)
    
    return qsos_df, qtcs_df, log_metadata
