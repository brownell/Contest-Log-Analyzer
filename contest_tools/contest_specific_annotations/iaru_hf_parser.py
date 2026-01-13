# contest_tools/contest_specific_annotations/iaru_hf_parser.py
#
# Purpose: Provides a custom, contest-specific parser for the IARU HF World
#          Championship contest to handle its asymmetric exchange format, which
#          differs based on whether the logger is an HQ or a Zone station.
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
import logging
import os
from typing import Dict, Any, List, Tuple, Optional

from ..contest_definitions import ContestDefinition
from ..cabrillo_parser import parse_qso_common_fields

def _get_logger_type(filepath: str) -> str:
    """
    Performs a pre-scan of the Cabrillo header to determine if the logging
    station is an HQ station or a regular (Zone) station.
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if i > 30: break
                line = line.strip().upper()
                if line.startswith('CATEGORY-STATION:'):
                    if line.split(':', 1)[1].strip() == 'HQ':
                        logging.info("Logger identified as HQ station.")
                        return "HQ"
    except Exception as e:
        logging.warning(f"Could not pre-scan log header to determine logger type: {e}")
    
    logging.info("Logger identified as ZONE station (default).")
    return "ZONE"

def parse_log(filepath: str, contest_definition: ContestDefinition, root_input_dir: str, cty_dat_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Custom parser for the IARU HF World Championship contest.
    """
    log_metadata: Dict[str, Any] = {}
    qso_records: List[Dict[str, Any]] = []
    
    logger_type = _get_logger_type(filepath)

    if logger_type == "ZONE":
        rule_key = "IARU-HF-ZONE-LOGGER"
    else:
        rule_key = "IARU-HF-HQ-LOGGER"
    
    parsing_rule = contest_definition.exchange_parsing_rules.get(rule_key)
    if not parsing_rule:
        raise ValueError(f"Parsing rule '{rule_key}' not found in JSON definition.")
        
    exchange_regex = re.compile(parsing_rule['regex'])
    exchange_groups = parsing_rule['groups']
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    for line in lines:
        cleaned_line = line.replace('\u00a0', ' ').strip()
        line_to_process = cleaned_line.upper() if cleaned_line.upper().startswith('QSO:') else cleaned_line
            
        if line_to_process.startswith('QSO:'):
            common_data = parse_qso_common_fields(line_to_process)
            if not common_data:
                continue
            
            exchange_rest = common_data.pop('ExchangeRest','').strip()

            exchange_match = exchange_regex.match(exchange_rest)
            if exchange_match:
                exchange_data = dict(zip(exchange_groups, exchange_match.groups()))
                common_data.update(exchange_data)
            
            common_data['RawQSO'] = line_to_process
            qso_records.append(common_data)
        
        elif not line_to_process.startswith(('START-OF-LOG', 'END-OF-LOG')):
            for cabrillo_tag, df_key in contest_definition.header_field_map.items():
                if line_to_process.upper().startswith(f"{cabrillo_tag}:"):
                    value = line_to_process[len(f"{cabrillo_tag}:"):].strip()
                    log_metadata[df_key] = value
                    break

    if not qso_records:
        raise ValueError(f"Custom parser found no valid QSO lines in Cabrillo file: {filepath}")

    df = pd.DataFrame(qso_records)
    return df, log_metadata
