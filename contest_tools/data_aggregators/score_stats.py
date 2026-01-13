# contest_tools/data_aggregators/score_stats.py
#
# Purpose: Centralizes the scoring logic for Score Reports, decoupling them from
#          direct DataFrame access. It handles the hierarchical (Band -> Mode)
#          aggregation and multiplier totaling rules.
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

from typing import List, Dict, Any, Tuple
import pandas as pd
from ..contest_log import ContestLog
from contest_tools.utils.report_utils import get_valid_dataframe
from ..utils.pivot_utils import calculate_multiplier_pivot

class ScoreStatsAggregator:
    """
    DAL Component: Handles scoring aggregation.
    Returns Pure Python Primitives (Dicts/Lists) for Score Reports.
    """

    def __init__(self, logs: List[ContestLog]):
        self.logs = logs

    def get_score_breakdown(self) -> Dict[str, Any]:
        """
        Calculates score details for all logs.
        
        Returns:
            {
                "logs": {
                    "CALLSIGN": {
                        "summary_data": [ ... list of row dicts ... ],
                        "total_summary": { ... totals row dict ... },
                        "final_score": int
                    }
                }
            }
        """
        result = {"logs": {}}

        for log in self.logs:
            callsign = log.get_metadata().get('MyCall', 'UnknownCall')
            
            # Use utility to get safe DF copy (excluding dupes is standard for scoring)
            df_net = get_valid_dataframe(log, include_dupes=False)
            
            if df_net.empty:
                result["logs"][callsign] = {
                    "summary_data": [],
                    "total_summary": {},
                    "final_score": 0
                }
                continue

            summary_data, total_summary, final_score = self._calculate_log_score(log, df_net)
            
            result["logs"][callsign] = {
                "summary_data": summary_data,
                "total_summary": total_summary,
                "final_score": final_score
            }
            
        return result

    def _calculate_log_score(self, log: ContestLog, df_net: pd.DataFrame) -> Tuple[List[Dict], Dict, int]:
        """
        Internal logic migrated from text_score_report.py.
        """
        contest_def = log.contest_definition
        multiplier_rules = contest_def.multiplier_rules
        log_location_type = getattr(log, '_my_location_type', None)

        # If the contest rules require it, filter out zero-point QSOs for all counts
        # (e.g. ARRL DX rules)
        if not contest_def.mults_from_zero_point_qsos:
            df_net = df_net[df_net['QSOPoints'] > 0].copy()

        # --- Pre-computation for TOTAL multiplier calculations ---
        per_band_mult_counts = {}
        
        for rule in multiplier_rules:
            mult_col = rule['value_column']
            if mult_col not in df_net.columns: continue

            df_valid_mults = df_net[df_net[mult_col].notna() & (df_net[mult_col] != 'Unknown')]
            
            if rule.get('totaling_method') == 'once_per_log':
                # Global scope handled in loop
                pass 
            else:
                # Default sum_by_band or per-mode logic usually relies on band buckets first
                pivot = calculate_multiplier_pivot(df_valid_mults, mult_col, group_by_call=False)
                per_band_mult_counts[mult_col] = (pivot > 0).sum(axis=0)

        # --- Hierarchical Band/Mode Summary Calculation ---
        summary_data = []
        
        # Canonical band ordering
        canonical_bands = [b[1] for b in ContestLog._HAM_BANDS]
        present_bands = [b for b in canonical_bands if b in df_net['Band'].unique()]

        for band in present_bands:
            band_df = df_net[df_net['Band'] == band]
            modes_on_band = sorted(band_df['Mode'].unique())

            if len(modes_on_band) > 1:
                # Create 'ALL' summary row (Union of mults on band)
                summary_data.append(self._process_slice(band_df, band, 'ALL', multiplier_rules, log_location_type))
                # Create individual mode rows
                for mode in modes_on_band:
                    mode_df = band_df[band_df['Mode'] == mode]
                    summary_data.append(self._process_slice(mode_df, band, mode, multiplier_rules, log_location_type))
            elif len(modes_on_band) == 1:
                # Single mode
                mode = modes_on_band[0]
                summary_data.append(self._process_slice(band_df, band, mode, multiplier_rules, log_location_type))

        # --- TOTAL Summary Calculation ---
        total_summary = {'Band': 'TOTAL', 'Mode': ''}
        total_summary['QSOs'] = df_net.shape[0]
        total_summary['Points'] = df_net['QSOPoints'].sum()

        total_multiplier_count = 0
        for rule in multiplier_rules:
            mult_name = rule['name']
            mult_col = rule['value_column']

            applies_to = rule.get('applies_to')
            if applies_to and log_location_type and applies_to != log_location_type:
                total_summary[mult_name] = 0
                continue
            
            if mult_col in df_net.columns:
                df_valid_mults = df_net[df_net[mult_col].notna() & (df_net[mult_col] != 'Unknown')]

                if rule.get('totaling_method') == 'once_per_log':
                    total_mults_for_rule = df_valid_mults[mult_col].nunique()
                elif rule.get('totaling_method') == 'once_per_mode':
                    mode_mults = df_valid_mults.groupby('Mode')[mult_col].nunique()
                    total_mults_for_rule = mode_mults.sum()
                elif rule.get('totaling_method') == 'once_per_band_no_mode':
                    band_mults = df_valid_mults.groupby('Band')[mult_col].nunique()
                    total_mults_for_rule = band_mults.sum()
                else: # Default to sum_by_band
                    total_mults_for_rule = per_band_mult_counts.get(mult_col, pd.Series()).sum()
            
            total_summary[mult_name] = total_mults_for_rule
            total_multiplier_count += total_mults_for_rule
            
        total_summary['AVG'] = (total_summary['Points'] / total_summary['QSOs']) if total_summary['QSOs'] > 0 else 0
        
        # --- Final Score ---
        if contest_def.score_formula == 'qsos_times_mults':
            final_score = total_summary['QSOs'] * total_multiplier_count
        elif contest_def.score_formula == 'total_points':
            final_score = total_summary['Points']
        else: # Default to points_times_mults
            final_score = total_summary['Points'] * total_multiplier_count
            
        return summary_data, total_summary, final_score

    def _process_slice(self, slice_df, slice_band, slice_mode, multiplier_rules, log_location_type):
        """Helper to calculate a summary row for a specific data slice."""
        row_summary = {'Band': slice_band, 'Mode': slice_mode}
        row_summary['QSOs'] = len(slice_df)
        row_summary['Points'] = slice_df['QSOPoints'].sum()

        for rule in multiplier_rules:
            m_name = rule['name']
            m_col = rule['value_column']
            applies_to = rule.get('applies_to')

            if applies_to and log_location_type and applies_to != log_location_type:
                row_summary[m_name] = 0
                continue
            
            if m_col not in slice_df.columns:
                row_summary[m_name] = 0
                continue
            
            df_slice_valid = slice_df[slice_df[m_col].notna() & (slice_df[m_col] != 'Unknown')]
            row_summary[m_name] = df_slice_valid[m_col].nunique()

        row_summary['AVG'] = (row_summary['Points'] / row_summary['QSOs']) if row_summary['QSOs'] > 0 else 0
        return row_summary

    def get_diagnostic_stats(self, log: ContestLog) -> Dict[str, Any]:
        """
        Generates diagnostic lists for Unknown and Unassigned multipliers.
        Returns a dictionary keyed by multiplier name containing lists of callsigns.
        """
        contest_def = log.contest_definition
        if getattr(contest_def, 'suppress_blank_mult_warnings', False):
            return {}

        df = get_valid_dataframe(log, include_dupes=True)
        if df.empty:
            return {}

        log_location_type = getattr(log, '_my_location_type', None)
        exclusive_groups = contest_def.mutually_exclusive_mults
        diagnostics = {}

        for rule in contest_def.multiplier_rules:
            applies_to = rule.get('applies_to')
            if applies_to and log_location_type and applies_to != log_location_type:
                continue

            mult_name = rule['name']
            mult_col = rule['value_column']

            if mult_col not in df.columns:
                continue

            # Check for "Unknown"
            unknown_calls = sorted(df[df[mult_col] == 'Unknown']['Call'].unique().tolist())
            if unknown_calls:
                diagnostics[f"unknown_{mult_name}"] = unknown_calls

            # Check for "Unassigned" (NaN)
            df_check = df
            if getattr(contest_def, 'is_naqp_ruleset', False):
                df_check = df[(df['Continent'] == 'NA') | (df['DXCCPfx'] == 'KH6')]
            
            unassigned_df = df_check[df_check[mult_col].isna()]
            
            # Filter mutually exclusive logic
            for group in exclusive_groups:
                if mult_col in group:
                    partner_cols = [p for p in group if p != mult_col and p in df.columns]
                    if partner_cols:
                        indices = unassigned_df.index
                        partner_vals = df.loc[indices, partner_cols].notna().any(axis=1)
                        unassigned_df = unassigned_df.loc[~partner_vals]

            unassigned_calls = sorted(unassigned_df['Call'].unique().tolist())
            if unassigned_calls:
                diagnostics[f"unassigned_{mult_name}"] = unassigned_calls

        return diagnostics