# contest_tools/adif_exporters/wae_adif.py
#
# Purpose: This module provides a custom ADIF exporter for the WAE Contest,
#          generating an output file compatible with N1MM Logger+.
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
import logging
from typing import Dict, Any, List

from ..contest_log import ContestLog

_TIMESTAMP_OFFSET_SECONDS = 2

def export_log(log: ContestLog, output_filepath: str):
    """
    Generates a contest-specific ADIF file for a WAE log.
    """
    df_full = log.get_processed_data()
    if df_full.empty:
        logging.warning(f"No QSOs to export. ADIF file '{output_filepath}' will not be created.")
        return

    df_to_export = df_full.copy()

    # --- Add per-second offset to identical timestamps for N1MM compatibility ---
    if 'Datetime' in df_to_export.columns and not df_to_export.empty:
        while df_to_export['Datetime'].duplicated().any():
            offsets = df_to_export.groupby('Datetime').cumcount()
            time_deltas = pd.to_timedelta(offsets * _TIMESTAMP_OFFSET_SECONDS, unit='s')
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
    adif_records.append(f"<PROGRAMVERSION:1.0.1-Beta\n")
    adif_records.append("<EOH>\n\n")

    for _, row in df_to_export.iterrows():
        record_parts: List[str] = []

        # --- Standard Fields from N1MM Example ---
        record_parts.append(adif_format('CALL', row.get('Call')))
        if pd.notna(row.get('Datetime')):
            record_parts.append(f"<QSO_DATE:8>{row['Datetime'].strftime('%Y%m%d')} ")
            record_parts.append(f"<TIME_ON:6>{row['Datetime'].strftime('%H%M%S')} ")
        record_parts.append(f"<TIME_OFF:6>{row['Datetime'].strftime('%H%M%S')} ")
        record_parts.append(adif_format('BAND', str(row.get('Band')).lower()))
        record_parts.append(adif_format('STATION_CALLSIGN', log.get_metadata().get('MyCall')))
        if pd.notna(row.get('Frequency')):
            freq_in_mhz = row.get('Frequency') / 1000
            freq_mhz = f"{freq_in_mhz:.3f}"
            record_parts.append(adif_format('FREQ', freq_mhz))
            record_parts.append(adif_format('FREQ_RX', freq_mhz))
     
        mode = row.get('Mode')
        if mode in ['PH', 'USB', 'LSB', 'SSB']: mode = 'SSB'
        record_parts.append(adif_format('MODE', mode))
        record_parts.append(adif_format('RST_RCVD', row.get('RST') or row.get('RS')))
        record_parts.append(adif_format('RST_SENT', row.get('SentRST') or row.get('SentRS')))
        record_parts.append(adif_format('CQZ', row.get('CQZone')))
        record_parts.append(adif_format('SRX', row.get('RcvdSerial')))
        record_parts.append(adif_format('STX', row.get('SentSerial')))
        record_parts.append(adif_format('APP_N1MM_CONTINENT', row.get('Continent')))

        # --- WAE Contest-Specific Tag Logic ---
        # 1. Mode-dependent CONTEST_ID
        if mode == 'CW':
            contest_id = 'DARC-WAEDC-CW'
        else: # PH or SSB
            contest_id = 'DARC-WAEDC-SSB'
        record_parts.append(adif_format('CONTEST_ID', contest_id))
        
        # 2. Add literal <APP_N1MM_EXCHANGE1:3>QSO tag
        record_parts.append("<APP_N1MM_EXCHANGE1:3>QSO ")

        # 3. Populate <ARRL_SECT> with multiplier
        mult1 = row.get('Mult1')
        mult2 = row.get('Mult2')
        if pd.notna(mult1):
            record_parts.append(adif_format('ARRL_SECT', mult1))
        elif pd.notna(mult2):
            record_parts.append(adif_format('ARRL_SECT', mult2))
        else:
            record_parts.append(adif_format('ARRL_SECT', 'Unknown'))
        
        # --- APP_CLA Diagnostic Tags ---
        record_parts.append(adif_format('APP_CLA_QSO_POINTS', row.get('QSOPoints')))
        record_parts.append(adif_format('APP_CLA_MULT1', row.get('Mult1')))
        record_parts.append(adif_format('APP_CLA_MULT2', row.get('Mult2')))
        if row.get('Run') == 'Run':
            record_parts.append('<APP_CLA_ISRUNQSO:1>1 ')
            
        adif_records.append("".join(record_parts).strip() + " <EOR>\n")

    # --- Write to File ---
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.writelines(adif_records)
        logging.info(f"Custom WAE ADIF log saved to: {output_filepath}")
    except Exception as e:
        logging.error(f"Error exporting custom WAE ADIF log to '{output_filepath}': {e}")
        raise
