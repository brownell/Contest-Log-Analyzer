# contest_tools/score_calculators/naqp_calculator.py
#
# Purpose: This module provides the complex, contest-specific time-series
#          score calculator for the Louisiana QSQ Party (NAQP) Contest.
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
from typing import TYPE_CHECKING

from .calculator_interface import TimeSeriesCalculator

if TYPE_CHECKING:
    from ..contest_log import ContestLog

class NaqpCalculator(TimeSeriesCalculator):
    """
    Calculates the time-series score for the NAQP contest, handling the
    unique rule where the set of QSOs for scoring is different from the
    set of QSOs that provide multipliers.
    """
    def calculate(self, log: 'ContestLog', df_non_dupes: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates a cumulative, time-series score for a NAQP log.
        Score = (Total QSOs) * (Total Multipliers)
        """

        log_manager = getattr(log, '_log_manager_ref', None)
        master_index = getattr(log_manager, 'master_time_index', None)

        required_cols = ['QSOPoints', 'Datetime', 'Run', 'Call', 'Continent', 'DXCCPfx']
        if df_non_dupes.empty or not all(c in df_non_dupes.columns for c in required_cols) or master_index is None:
            return pd.DataFrame()

        df_sorted = df_non_dupes.dropna(subset=['Datetime']).sort_values(by='Datetime')
        
        # --- 1. Calculate Cumulative QSO Counts from ALL valid (non-dupe) QSOs ---
        hourly_groups_all = df_sorted.set_index('Datetime').groupby(pd.Grouper(freq='h'))
        cum_qso_ts = hourly_groups_all.size().cumsum().reindex(master_index, method='ffill').fillna(0)
        run_qso_ts = df_sorted[df_sorted['Run'] == 'Run'].set_index('Datetime')['Call'].resample('h').count().cumsum().reindex(master_index, method='ffill').fillna(0)
        sp_unk_qso_ts = cum_qso_ts - run_qso_ts
        
        # --- 2. Create a separate DataFrame for Multiplier-Eligible QSOs ---
        # Per NAQP rules, multipliers are NA stations plus Hawaii (KH6).
        # All other QSOs (DX) count for points but not multipliers.
        df_for_mults = df_sorted[
            (df_sorted['Continent'] == 'NA') | (df_sorted['DXCCPfx'] == 'KH6')
        ].copy()
        
        bands_in_log = sorted(df_for_mults['Band'].unique())
        for band in bands_in_log:
            df_band = df_for_mults[df_for_mults['Band'] == band]
            stprov_mults = df_band['Mult_STPROV'].dropna().unique()
            nadxcc_mults = df_band['Mult_NADXCC'].dropna().unique()
 

        # --- 3. Calculate Cumulative Multipliers from the MULTIPLIER-ELIGIBLE DataFrame ---
        multiplier_columns = sorted(list(set([rule['value_column'] for rule in log.contest_definition.multiplier_rules])))
        for col in multiplier_columns:
            if col in df_for_mults.columns:
                df_for_mults = df_for_mults[df_for_mults[col] != 'Unknown']
        df_for_mults.dropna(subset=multiplier_columns, how='all', inplace=True)
        
        mult_count_ts = pd.Series(0.0, index=master_index)
        per_band_mult_ts_dict = {}
        
        # New, correct algorithm: iterate by band, combine mults, then count uniques.
        for band in bands_in_log:
            df_band = df_for_mults[df_for_mults['Band'] == band]
            if df_band.empty:
                per_band_mult_ts_dict[f"total_mults_{band}"] = pd.Series(0, index=master_index)
                continue

            # Combine all multiplier columns for this band into a single series
            all_mults_on_band = pd.concat([df_band[col] for col in multiplier_columns if col in df_band]).dropna()

            # Find the first time each unique multiplier was worked
            first_worked_events = all_mults_on_band.drop_duplicates(keep='first')
            
            # Create a time series of these new multiplier events
            new_mult_ts = pd.Series(1, index=df_band.loc[first_worked_events.index]['Datetime'])
            band_mult_ts = new_mult_ts.resample('h').count().cumsum().reindex(master_index, method='ffill').fillna(0)
            
            mult_count_ts += band_mult_ts
            per_band_mult_ts_dict[f"total_mults_{band}"] = band_mult_ts

        # --- 4. Calculate Final Score & Apportion by Run/S&P status ---
        final_score_ts = cum_qso_ts * mult_count_ts
        
        # Apportion score based on the ratio of Run vs S&P+Unk QSOs from the full QSO set
        run_ratio = (run_qso_ts / cum_qso_ts).fillna(0)
        sp_unk_ratio = (sp_unk_qso_ts / cum_qso_ts).fillna(0)
        
        run_score_ts = final_score_ts * run_ratio
        sp_unk_score_ts = final_score_ts * sp_unk_ratio

        # --- 5. Assemble Final DataFrame ---
        result_df = pd.DataFrame({
            'run_qso_count': run_qso_ts,
            'sp_unk_qso_count': sp_unk_qso_ts,
            'run_score': run_score_ts,
            'sp_unk_score': sp_unk_score_ts,
            'score': final_score_ts,
            'total_mults': mult_count_ts,
        }, index=master_index)
        
        for col_name, series in per_band_mult_ts_dict.items():
            result_df[col_name] = series

        return result_df.astype(int)