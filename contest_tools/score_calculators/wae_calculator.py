# contest_tools/score_calculators/wae_calculator.py
#
# Purpose: This module provides the complex, contest-specific time-series
#          score calculator for the Worked All Europe (WAE) Contest.
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
import logging
from typing import TYPE_CHECKING

from .calculator_interface import TimeSeriesCalculator

if TYPE_CHECKING:
    from ..contest_log import ContestLog

class WaeCalculator(TimeSeriesCalculator):
    """
    Calculates the time-series score for the WAE contest, handling QSOs,
    QTCs, and weighted multipliers, and providing a breakdown by operating style.
    """
    _BAND_WEIGHTS = {'80M': 4, '40M': 3, '20M': 2, '15M': 2, '10M': 2}
    
    def calculate(self, log: 'ContestLog', df_non_dupes: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates a cumulative, time-series score for a WAE log.
        Score = (Total QSOs + Total QTCs) * Total Weighted Multipliers
        """
        qtcs_df = getattr(log, 'qtcs_df', pd.DataFrame()).copy()
        log_manager = getattr(log, '_log_manager_ref', None)
        master_index = getattr(log_manager, 'master_time_index', None)

        if master_index is None or df_non_dupes.empty:
            return pd.DataFrame()

        # --- Filter out QSOs with "Unknown" multipliers before any calculation ---
        df_for_scoring = df_non_dupes.copy()
        mult_cols = ['Mult1', 'Mult2']
        for col in mult_cols:
            if col in df_for_scoring.columns:
                df_for_scoring = df_for_scoring[df_for_scoring[col] != 'Unknown']

        qsos_df_sorted = df_for_scoring.dropna(subset=['Datetime']).sort_values('Datetime')

        # --- Create a filtered DataFrame containing only QSOs with valid multipliers ---
        df_mults = qsos_df_sorted[qsos_df_sorted[mult_cols].notna().any(axis=1)]

        # --- 1. Calculate Cumulative Contact Counts (QSOs + QTCs) ---
        # Base the QSO count on the df_mults DF, which only contains QSOs with valid multipliers.
        ts_qso_count = pd.Series(1, index=df_mults['Datetime']).resample('h').count().cumsum()
        ts_qso_count = ts_qso_count.reindex(master_index, method='ffill').fillna(0)

        if not qtcs_df.empty:
            logging.info(f"--- WAE QTC Processing ---")
            logging.info(f"Initial QTC records received: {len(qtcs_df)}")
            qtcs_df['Datetime'] = pd.to_datetime(
                qtcs_df['QTC_DATE'] + ' ' + qtcs_df['QTC_TIME'],
                format='%Y-%m-%d %H%M', errors='coerce'
            )
            
            invalid_qtcs = qtcs_df[qtcs_df['Datetime'].isna()]
            if not invalid_qtcs.empty:
                logging.warning(f"Found {len(invalid_qtcs)} QTC records with malformed timestamps that will be dropped:")
                for _, row in invalid_qtcs.iterrows():
                    logging.warning(f"  - Dropped QTC: DATE={row.get('QTC_DATE')} TIME={row.get('QTC_TIME')}")

            if qtcs_df['Datetime'].dt.tz is None:
                qtcs_df['Datetime'] = qtcs_df['Datetime'].dt.tz_localize('UTC')
            
            qtcs_df_sorted = qtcs_df.dropna(subset=['Datetime']).sort_values('Datetime')
            logging.info(f"Valid QTC records after parsing: {len(qtcs_df_sorted)}")
            ts_qtc_count = pd.Series(1, index=qtcs_df_sorted['Datetime']).resample('h').count().cumsum()
            ts_qtc_count = ts_qtc_count.reindex(master_index, method='ffill').fillna(0)
        else:
            ts_qtc_count = pd.Series(0, index=master_index)
        
        ts_contact_total = ts_qso_count + ts_qtc_count

        # --- 2. Calculate Cumulative Weighted Multipliers ---
        new_mults_events = []
        for col in mult_cols:
            if col in df_mults.columns:
                # Drop NaNs for the specific column before finding duplicates
                first_worked = df_mults.dropna(subset=[col]).drop_duplicates(subset=['Band', col], keep='first')
    
                weights = first_worked['Band'].map(self._BAND_WEIGHTS)
                new_mults_ts = pd.Series(weights.values, index=first_worked['Datetime'])
                new_mults_events.append(new_mults_ts)
        
        if new_mults_events:
            combined_mults_ts = pd.concat(new_mults_events)
            hourly_weighted_mults = combined_mults_ts.resample('h').sum()
            ts_weighted_mults = hourly_weighted_mults.cumsum().reindex(master_index, method='ffill').fillna(0)
        else:
            ts_weighted_mults = pd.Series(0, index=master_index)

        # --- 2a. Calculate Cumulative Weighted Multipliers PER BAND ---
        per_band_mult_ts = {}
        bands_in_log = df_mults['Band'].unique()
        
        for band in self._BAND_WEIGHTS.keys():
            if band in bands_in_log:
                df_band_mults = df_mults[df_mults['Band'] == band]
                band_new_mults_events = []
                for col in mult_cols:
                    if col in df_band_mults.columns:
                        first_worked = df_band_mults.dropna(subset=[col]).drop_duplicates(subset=[col], keep='first')
                        weights = pd.Series(self._BAND_WEIGHTS.get(band, 1), index=first_worked.index)
                        band_new_mults_events.append(pd.Series(weights.values, index=first_worked['Datetime']))
                
                if band_new_mults_events:
                    hourly_weighted = pd.concat(band_new_mults_events).resample('h').sum()
                    per_band_mult_ts[f"weighted_mults_{band}"] = hourly_weighted.cumsum().reindex(master_index, method='ffill').fillna(0)

        # --- 3. Calculate Total Score ---
        ts_total_score = ts_contact_total * ts_weighted_mults
        
        
        # --- 4. Apportion Score by Operating Style (Run vs. S&P) ---
        is_run = qsos_df_sorted['Run'] == 'Run'
        is_sp_unk = ~is_run
        
        run_qso_count = qsos_df_sorted[is_run].set_index('Datetime')['Call'].resample('h').count().cumsum()
        sp_unk_qso_count = qsos_df_sorted[is_sp_unk].set_index('Datetime')['Call'].resample('h').count().cumsum()

        run_qso_count = run_qso_count.reindex(master_index, method='ffill').fillna(0)
        sp_unk_qso_count = sp_unk_qso_count.reindex(master_index, method='ffill').fillna(0)
        total_qso_count = run_qso_count + sp_unk_qso_count

        # Calculate ratios, handling division by zero
        run_ratio = (run_qso_count / total_qso_count).fillna(0)
        sp_unk_ratio = (sp_unk_qso_count / total_qso_count).fillna(0)

        # Apportion the total score
        ts_run_score = ts_total_score * run_ratio
        ts_sp_unk_score = ts_total_score * sp_unk_ratio

        # --- 5. Assemble Final DataFrame ---
        result_df = pd.DataFrame({
            'ts_qso_count': ts_qso_count,
            'ts_qtc_count': ts_qtc_count,
            'run_qso_count': run_qso_count,
            'sp_unk_qso_count': sp_unk_qso_count,
            'run_score': ts_run_score,
            'sp_unk_score': ts_sp_unk_score,
            'score': ts_total_score,
            'weighted_mults': ts_weighted_mults
        })

        # Add the per-band multiplier time-series to the final result
        for col_name, series in per_band_mult_ts.items():
            result_df[col_name] = series

        # --- Final Diagnostic Logging ("After" Snapshot) ---
#        logging.info(f"Final WAE time-series DataFrame:\n{result_df.to_string()}")

        return result_df.astype(int)