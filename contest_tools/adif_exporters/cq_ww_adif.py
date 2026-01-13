# contest_tools/adif_exporters/cq_ww_adif.py
#
# Purpose: Provides a contest-specific ADIF exporter for the CQ WW DX
#          contest. It correctly populates the <CQZ> tag from the
#          exchanged zone for N1MM Logger+ compatibility, while preserving
#          the CTY-derived geographical zone in a custom tag for diagnostics.
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
from typing import Dict, Any, List

from ..contest_log import ContestLog

_TIMESTAMP_OFFSET_SECONDS = 2

def export_log(log: ContestLog, output_filepath: str):
    """
    Generates a contest-specific ADIF file for a CQ WW log.
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
        
        rst_rcvd = row.get('RST') if pd.notna(row.get('RST')) else row.get('RS')
        record_parts.append(adif_format('RST_RCVD', rst_rcvd))
        rst_sent = row.get('SentRST') if pd.notna(row.get('SentRST')) else row.get('SentRS')
        record_parts.append(adif_format('RST_SENT', rst_sent))
        
        record_parts.append(adif_format('CONTEST_ID', log.get_metadata().get('ContestName')))
        record_parts.append(adif_format('STATION_CALLSIGN', log.get_metadata().get('MyCall')))
        
        # --- CQ WW Contest-Specific Tag Logic ---
        
        # <CQZ> (Override): Populate with the *exchanged* zone for N1MM.
        record_parts.append(adif_format('CQZ', row.get('Zone')))
        
        # <APP_CLA_CQZ> (Standard): Populate with the *CTY-derived* geographical zone.
        record_parts.append(adif_format('APP_CLA_CQZ', row.get('CQZone')))

        # --- Standard APP_CLA Fields for internal use ---
        record_parts.append(adif_format('APP_CLA_QSO_POINTS', row.get('QSOPoints')))
        record_parts.append(adif_format('APP_CLA_MULT1', row.get('Mult1')))
        record_parts.append(adif_format('APP_CLA_MULT1NAME', row.get('Mult1Name')))
        record_parts.append(adif_format('APP_CLA_MULT2', row.get('Mult2')))

        if row.get('Run') == 'Run':
            record_parts.append('<APP_CLA_ISRUNQSO:1>1 ')
            
        adif_records.append("".join(record_parts).strip() + " <EOR>\n")

    # --- Write to File ---
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.writelines(adif_records)
        logging.info(f"Custom CQ WW ADIF log saved to: {output_filepath}")
    except Exception as e:
        logging.error(f"Error exporting custom CQ WW ADIF log to '{output_filepath}': {e}")
        raise
