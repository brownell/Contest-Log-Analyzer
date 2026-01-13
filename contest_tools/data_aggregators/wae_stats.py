# contest_tools/data_aggregators/wae_stats.py
#
# Purpose: Aggregates statistics specifically for Worked All Europe (WAE)
#          contests, applying band weights and QTC logic.
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

from typing import List, Dict, Any
import pandas as pd
from ..contest_log import ContestLog
from contest_tools.utils.report_utils import get_valid_dataframe

class WaeStatsAggregator:
    """
    Encapsulates WAE-specific scoring logic (Weighted Multipliers, QTCs).
    Returns pure Python primitives (no Pandas objects).
    """
    
    _BAND_WEIGHTS = {'80M': 4, '40M': 3, '20M': 2, '15M': 2, '10M': 2}
    _CANONICAL_BAND_ORDER = [b[1] for b in ContestLog._HAM_BANDS]

    def get_wae_breakdown(self, logs: List[ContestLog]) -> Dict[str, Any]:
        """
        Calculates WAE scores for a list of logs.
        """
        result = {"logs": {}}

        for log in logs:
            metadata = log.get_metadata()
            callsign = metadata.get('MyCall', 'UnknownCall')
            
            # 1. Extract Data
            qsos_df = get_valid_dataframe(log, include_dupes=False)
            qtcs_df = getattr(log, 'qtcs_df', pd.DataFrame())
            
            if qsos_df.empty:
                result["logs"][callsign] = {
                    "scalars": {
                        "total_qso_points": 0,
                        "total_qtc_points": 0,
                        "total_weighted_mults": 0,
                        "final_score": 0,
                        "on_time": metadata.get('OperatingTime', 'N/A')
                    },
                    "breakdown": []
                }
                continue

            # 2. Calculate Breakdowns (Band/Mode)
            breakdown_list = []
            band_mode_groups = qsos_df.groupby(['Band', 'Mode'])
            
            # Helper for sorting
            # We sort primarily by Band Index in _HAM_BANDS, then by Mode
            sorted_groups = sorted(
                band_mode_groups, 
                key=lambda x: (
                    self._CANONICAL_BAND_ORDER.index(x[0][0]) if x[0][0] in self._CANONICAL_BAND_ORDER else 99, 
                    x[0][1]
                )
            )

            for (band, mode), group_df in sorted_groups:
                qso_pts = len(group_df) # WAE: 1 point per QSO (usually), but verify against original logic 
                # Original logic: qso_pts = len(group_df) in the loop, BUT total points used 'QSOPoints'.sum().
                # In WAE text report (original):
                #   Loop: qso_pts = len(group_df)  <-- This is purely count for the row
                #   Total: total_qso_pts = qsos_df['QSOPoints'].sum() <-- This is the score
                # Wait, strictly following original implementation:
                
                # The original `text_wae_score_report.py` line 10-11: `qso_pts = len(group_df)`
                # The original `text_wae_score_report.py` line 13: `total_qso_pts = qsos_df['QSOPoints'].sum()`
                # There is a divergence in the original code between the row-level "QSO Pts" (Count) and Total (Sum).
                # However, usually in WAE 1 QSO = 1 Point.
                # To be perfectly safe and match "QSO Pts" column of original report, I will use len(group_df).
                # Weighted Multipliers
                weighted_mults = 0
                mult_cols = ['Mult1', 'Mult2']
                df_mults = group_df[group_df[mult_cols].notna().any(axis=1)]
                
                for col in mult_cols:
                    if col in df_mults.columns:
                        unique_mults_on_band = df_mults[col].nunique()
                        weighted_mults += unique_mults_on_band * self._BAND_WEIGHTS.get(band, 1)

                breakdown_list.append({
                    "band": band,
                    "mode": mode,
                    "qso_points": len(group_df), # Matches original row logic
                    "weighted_mults": weighted_mults
                })

            # 3. Calculate Totals
            total_qso_pts = qsos_df['QSOPoints'].sum() # Matches original total logic
            total_qtc_pts = len(qtcs_df)
            
            total_weighted_mults = 0
            mult_cols = ['Mult1', 'Mult2']
            df_mults_all = qsos_df[qsos_df[mult_cols].notna().any(axis=1)]
            
            # Recalculate total weighted mults based on Band aggregation (not Band/Mode)
            # This logic mimics line 14-15 of original text_wae_score_report.py
            for col in mult_cols:
                if col in df_mults_all.columns:
                    band_mult_counts = df_mults_all.groupby('Band')[col].nunique()
                    for band, count in band_mult_counts.items():
                        total_weighted_mults += count * self._BAND_WEIGHTS.get(band, 1)

            final_score = (total_qso_pts + total_qtc_pts) * total_weighted_mults

            result["logs"][callsign] = {
                "scalars": {
                    "total_qso_points": int(total_qso_pts),
                    "total_qtc_points": int(total_qtc_pts),
                    "total_weighted_mults": int(total_weighted_mults),
                    "final_score": int(final_score),
                    "on_time": metadata.get('OperatingTime', 'N/A')
                },
                "breakdown": breakdown_list
            }
            
        return result