# contest_tools/adif_exporters/naqp_adif.py
#
# Purpose: Provides a contest-specific ADIF exporter for the NAQP contests.
#          It generates an ADIF file compatible with N1MM Logger+ by writing
#          the contest exchange to the <STATE> tag.
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
import numpy as np
import os
import logging
from typing import Dict, Any, Set, List

from ..contest_log import ContestLog

_TIMESTAMP_OFFSET_SECONDS = 2

def export_log(log: ContestLog, output_filepath: str):
    """
    Generates a contest-specific ADIF file for a NAQP log.
    """
    df_full = log.get_processed_data()
    if df_full.empty:
        logging.warning(f"No QSOs to export. ADIF file '{output_filepath}' will not be created.")
        return

    # Use a copy to avoid modifying the original DataFrame
    df_to_export = df_full.copy()
    
    # --- Add per-second offset to identical timestamps for N1MM compatibility ---
    if 'Datetime' in df_to_export.columns and not df_to_export.empty:
        # Loop until all timestamps are unique, handling rollovers.
        while df_to_export['Datetime'].duplicated().any():
            offsets = df_to_export.groupby('Datetime').cumcount()
            time_deltas = pd.to_timedelta(offsets * _TIMESTAMP_OFFSET_SECONDS, unit='s')
            # Only apply the offset to the rows that are part of a duplicate group
            df_to_export.loc[df_to_export['Datetime'].duplicated(keep=False), 'Datetime'] += time_deltas
        df_to_export.sort_values(by='Datetime', inplace=True)
    
    def adif_format(tag: str, value: Any) -> str:
        """Helper to format a single ADIF tag."""
        if pd.isna(value) or value == '':
            return ''
        val_str = str(value)
        return f"<{tag}:{len(val_str)}>{val_str} "

    # --- Generate ADIF Content ---
    adif_records: List[str] = []
    adif_records.append("ADIF Export from Contest-Log-Analyzer\n")
    adif_records.append(f"<PROGRAMID:21>Contest-Log-Analytics\n")
    adif_records.append(f"<PROGRAMVERSION:1.0.0-Beta\n")
    adif_records.append("<EOH>\n\n")

    for _, row in df_to_export.iterrows():
        record_parts: List[str] = []
        
        # --- Standard Fields ---
        record_parts.append(adif_format('CALL', row.get('Call')))
        if pd.notna(row.get('Datetime')):
            record_parts.append(f"<QSO_DATE:8>{row['Datetime'].strftime('%Y%m%d')} ")
            record_parts.append(f"<TIME_ON:6>{row['Datetime'].strftime('%H%M%S')} ")
        if pd.notna(row.get('Band')):
            record_parts.append(adif_format('BAND', str(row.get('Band')).lower()))
        
        mode = row.get('Mode')
        if mode in ['PH', 'USB', 'LSB', 'SSB']:
            mode = 'SSB'
        record_parts.append(adif_format('MODE', mode))
        
        # NAQP does not have RST in the exchange
        record_parts.append(adif_format('RST_RCVD', '59' if mode != 'CW' else '599'))
        record_parts.append(adif_format('RST_SENT', '59' if mode != 'CW' else '599'))

        record_parts.append(adif_format('CONTEST_ID', log.get_metadata().get('ContestName')))
        record_parts.append(adif_format('STATION_CALLSIGN', log.get_metadata().get('MyCall')))
        
        # --- NAQP Contest-Specific <STATE> Tag Logic ---
        state_value = None
        if pd.notna(row.get('Mult_STPROV')):
            state_value = row.get('Mult_STPROV')
        elif pd.notna(row.get('Mult_NADXCC')):
            state_value = row.get('Mult_NADXCC')
        elif row.get('Continent') == 'NA':
            logging.warning(f"Could not determine NAQP multiplier for NA station: {row.get('Call')}. Setting STATE tag to 'Unknown'.")
            state_value = "Unknown"
        else:
            state_value = "DX"

        record_parts.append(adif_format('STATE', state_value))

        # --- Standard APP_CLA Fields for internal use ---
        record_parts.append(adif_format('APP_CLA_QSO_POINTS', row.get('QSOPoints')))
        if row.get('Run') == 'Run':
            record_parts.append('<APP_CLA_ISRUNQSO:1>1 ')
        
        adif_records.append("".join(record_parts).strip() + " <EOR>\n")

    # --- Write to File ---
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.writelines(adif_records)
        logging.info(f"Custom NAQP ADIF log saved to: {output_filepath}")
    except Exception as e:
        logging.error(f"Error exporting custom NAQP ADIF log to '{output_filepath}': {e}")
        raise
