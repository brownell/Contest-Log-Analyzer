# contest_tools/data_aggregators/multiplier_stats.py
#
# Purpose: Centralizes the calculation logic for multiplier statistics,
#          serving both the 'Multiplier Summary' and 'Missed Multipliers' reports.
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
# [0.127.0-Beta] - 2025-12-17
# - Refactored get_dashboard_matrix_data to get_multiplier_breakdown_data.
# - Implemented hierarchical aggregation (Total -> Band -> Rule) for dashboard.
# [0.126.0-Beta] - 2025-12-17
# - Updated get_dashboard_matrix_data to return raw lists of missed multipliers
#   instead of just counts, enabling detailed tooltips in the dashboard.
# [0.125.0-Beta] - 2025-12-17
# - Updated import to use contest_tools.utils.pivot_utils for calculate_multiplier_pivot.
# [0.124.1-Beta] - 2025-12-17
# - Fixed AttributeError in get_dashboard_matrix_data by accessing correct
#   ComparisonResult attributes (common_count, universe_count).
# [0.124.0-Beta] - 2025-12-17
# - Added get_dashboard_matrix_data for high-level Opportunity Matrix metrics.
# [0.123.0-Beta] - 2025-12-17
# - Refactored get_missed_data to use the centralized ComparativeEngine for set logic.
# [0.93.0] - 2025-11-24
# - Refactored to return JSON-serializable types (Dicts/Lists) instead of
#   Pandas objects, enabling the Data Abstraction Layer.
# [0.93.0] - 2025-11-23
# - Initial creation. Extracted logic from text_multiplier_summary.py and
#   text_missed_multipliers.py.
from typing import List, Dict, Any, Set
import pandas as pd
from ..contest_log import ContestLog
from .comparative_engine import ComparativeEngine
from ..utils.pivot_utils import calculate_multiplier_pivot
from ..utils.json_encoders import NpEncoder
from ..utils.report_utils import determine_activity_status

class MultiplierStatsAggregator:
    def __init__(self, logs: List[ContestLog]):
        if not logs:
            raise ValueError("Aggregator requires at least one log.")
        self.logs = logs
        # Assume all logs share the same definition
        self.contest_def = logs[0].contest_definition

    def get_summary_data(self, mult_name: str, mode_filter: str = None) -> Dict[str, Any]:
        """
        Extracts logic from text_multiplier_summary.py.
        Returns a dictionary containing the pivot table and metadata needed for rendering.
        """
        # --- 1. Filter Data ---
        log_data_to_process = []
        for log in self.logs:
            df = log.get_processed_data()
            if mode_filter:
                filtered_df = df[df['Mode'] == mode_filter].copy()
            else:
                filtered_df = df.copy()
            log_data_to_process.append({'df': filtered_df, 'meta': log.get_metadata()})

        # --- 2. Determine Callsigns ---
        all_dfs = []
        all_calls = []
        
        # Handle Single vs Multi logic
        if len(log_data_to_process) == 1:
            log_data = log_data_to_process[0]
            df = log_data['df'][log_data['df']['Dupe'] == False]
            my_call = log_data['meta'].get('MyCall', 'Unknown')
            all_calls = [my_call]
            all_dfs = [df]
        else:
            for log_data in log_data_to_process:
                df = log_data['df'][log_data['df']['Dupe'] == False].copy()
                if not df.empty:
                    my_call = log_data['meta'].get('MyCall', 'Unknown')
                    df['MyCall'] = my_call
                    all_calls.append(my_call)
                    all_dfs.append(df)
            all_calls.sort()

        # --- 3. Validate Rules ---
        mult_rule = next((r for r in self.contest_def.multiplier_rules if r.get('name', '').lower() == mult_name.lower()), None)
        if not mult_rule or 'value_column' not in mult_rule:
             return {'error': f"Error: Multiplier type '{mult_name}' not found in definition."}
        
        mult_column = mult_rule['value_column']
        
        # --- 4. Combine and Filter Main DF ---
        combined_df = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
        
        if combined_df.empty or mult_column not in combined_df.columns:
             # Return empty structures but sufficient to render "No data" message
             return {
                 'pivot': {}, 
                 'all_calls': all_calls,
                 'mult_column': mult_column,
                 'mult_rule': mult_rule,
                 'combined_df': [],
                 'main_df': [],
                 'bands': self.contest_def.valid_bands
             }

        main_df = combined_df[combined_df[mult_column].notna()]
        main_df = main_df[main_df[mult_column] != 'Unknown']

        if not self.contest_def.mults_from_zero_point_qsos:
            main_df = main_df[main_df['QSOPoints'] > 0]

        # --- 5. Calculate Pivot ---
        is_comparative = len(all_calls) > 1
        pivot = calculate_multiplier_pivot(main_df, mult_column, group_by_call=is_comparative)

        return {
            'pivot': pivot.to_dict(orient='split'),
            'all_calls': all_calls,
            'mult_column': mult_column,
            'mult_rule': mult_rule,
            'combined_df': combined_df.to_dict(orient='records'),
            'main_df': main_df.to_dict(orient='records'),
            'bands': self.contest_def.valid_bands
        }

    def get_missed_data(self, mult_name: str, mode_filter: str = None) -> Dict[str, Any]:
        """
        Extracts logic from text_missed_multipliers.py.
        Returns a dictionary mapping bands to their respective missed/worked sets.
        """
        # --- 1. Setup Rules and Calls ---
        mult_rule = next((r for r in self.contest_def.multiplier_rules if r.get('name', '').lower() == mult_name.lower()), None)
        if not mult_rule or 'value_column' not in mult_rule:
             return {'error': f"Error: Multiplier type '{mult_name}' not found."}

        all_calls = sorted([log.get_metadata().get('MyCall', 'Unknown') for log in self.logs])
        
        # --- 2. Filter Data ---
        log_data_to_process = []
        for log in self.logs:
            df = log.get_processed_data()
            if mode_filter:
                filtered_df = df[df['Mode'] == mode_filter].copy()
            else:
                filtered_df = df.copy()
            log_data_to_process.append({'df': filtered_df, 'meta': log.get_metadata()})

        # --- 3. Determine Bands ---
        bands_to_process = ["All Bands"] if mult_rule.get('totaling_method') == 'once_per_log' else self.contest_def.valid_bands

        full_results = {
            'bands_to_process': bands_to_process,
            'all_calls': all_calls,
            'mult_rule': mult_rule,
            'band_data': {}
        }

        # --- 4. Iterate Bands (Logic from _aggregate_band_data) ---
        mult_column = mult_rule['value_column']
        name_column = mult_rule.get('name_column')

        for band in bands_to_process:
            band_data_map: Dict[str, Dict] = {}
            mult_sets: Dict[str, Set[str]] = {call: set() for call in all_calls}
            prefix_to_name_map = {}

            for log_data in log_data_to_process:
                callsign = log_data['meta'].get('MyCall', 'Unknown')
                df = log_data['df'][log_data['df']['Dupe'] == False].copy()
                if df.empty or mult_column not in df.columns: continue
                
                df_scope = df if band == "All Bands" else df[df['Band'] == band].copy()
                
                df_scope = df_scope[df_scope[mult_column] != 'Unknown']
                df_scope = df_scope[df_scope[mult_column].notna()]
                
                if df_scope.empty: continue
                
                if name_column and name_column in df_scope.columns:
                    name_map_df = df_scope[[mult_column, name_column]].dropna().drop_duplicates()
                    for _, row in name_map_df.iterrows():
                        prefix_to_name_map[row[mult_column]] = row[name_column]

                agg_data = df_scope.groupby(mult_column).agg(
                    QSO_Count=('Call', 'size'), Run_SP_Status=('Run', determine_activity_status))
                
                # Convert DataFrame to Dict (orient='index')
                band_data_map[callsign] = agg_data.to_dict(orient='index')
                mult_sets[callsign].update(agg_data.index)

            # Delegate Set Theory math to the ComparativeEngine
            comparison = ComparativeEngine.compare_logs(mult_sets)
            
            # Reconstruct aggregates from Engine results
            # Universe = Station_Log U Station_Missed (valid for any station)
            union_of_all_mults = set()
            if comparison.station_metrics:
                # Pick any station to reconstruct the universe set
                first_call = next(iter(comparison.station_metrics))
                first_metrics = comparison.station_metrics[first_call]
                union_of_all_mults = mult_sets[first_call].union(first_metrics.missed_items)

            missed_mults_on_band = set()
            for metrics in comparison.station_metrics.values():
                missed_mults_on_band.update(metrics.missed_items)

            full_results['band_data'][band] = {
                "band_data": band_data_map, 
                "mult_sets": {k: sorted(list(v)) for k, v in mult_sets.items()}, 
                "prefix_to_name_map": prefix_to_name_map,
                "union_of_all_mults": sorted(list(union_of_all_mults)), 
                "missed_mults_on_band": sorted(list(missed_mults_on_band))
            }

        return full_results

    def get_multiplier_breakdown_data(self) -> Dict[str, Any]:
        """
        Generates hierarchical metrics for the Multiplier Breakdown table.
        Returns a dictionary with 'totals' and 'bands' for structured rendering.
        """
        all_calls = sorted([log.get_metadata().get('MyCall', 'Unknown') for log in self.logs])
        
        # 1. Collect all raw multiplier sets
        # Structure: sets[log_call] = set of items
        # Items are composite keys: (rule_name, band, value) to ensure uniqueness logic matches scoring
        
        raw_sets = {call: set() for call in all_calls}
        
        # We also need subsets for aggregations
        # subset_keys: 'TOTAL', 'TOTAL_{Rule}', '{Band}', '{Band}_{Rule}'
        subsets = {call: {} for call in all_calls}
        
        # Map to store Run/S&P status for each unique multiplier instance: map[call][composite_key] = status
        mult_status_map = {call: {} for call in all_calls}
        
        valid_bands = self.contest_def.valid_bands
        
        for rule in self.contest_def.multiplier_rules:
            mult_name = rule['name']
            mult_column = rule['value_column']
            method = rule.get('totaling_method', 'sum_by_band')
            
            for log in self.logs:
                call = log.get_metadata().get('MyCall', 'Unknown')
                df = log.get_processed_data()
                
                if df.empty or mult_column not in df.columns: continue
                
                # Filter valid
                valid = df[df[mult_column].notna() & (df[mult_column] != 'Unknown')]
                
                # Pre-calculate status for all multipliers in this scope
                # Status logic: If worked on Run, it's Run. If Mixed, it's Mixed.
                status_series = valid.groupby(mult_column)['Run'].apply(determine_activity_status)

                if method == 'once_per_log':
                    # Scope: Global. Key: (Rule, Value)
                    # Just grab unique values
                    uniques = valid[mult_column].unique()
                    for val in uniques:
                        composite_key = (mult_name, 'All', val)
                        raw_sets[call].add(composite_key)
                        # Store status
                        mult_status_map[call][composite_key] = status_series.get(val, 'Unk')
                        
                        # Populate Subsets
                        # 1. Total
                        subsets[call].setdefault('TOTAL', set()).add(composite_key)
                        # 2. Total_Rule
                        subsets[call].setdefault(f'TOTAL_{mult_name}', set()).add(composite_key)
                        # No band breakdown for once_per_log in this table
                        
                else:
                    # Scope: Per Band. Key: (Rule, Band, Value)
                    grouped = valid.groupby('Band')[mult_column].unique()
                    for band, values in grouped.items():
                        for val in values:
                            composite_key = (mult_name, band, val)
                            raw_sets[call].add(composite_key)
                            # Lookup status for this band/val
                            mult_status_map[call][composite_key] = status_series.get(val, 'Unk')
                            
                            # Populate Subsets
                            # 1. Total (Global Score Sum)
                            subsets[call].setdefault('TOTAL', set()).add(composite_key)
                            # 2. Total_Rule (Global Rule Sum)
                            subsets[call].setdefault(f'TOTAL_{mult_name}', set()).add(composite_key)
                            # 3. Band Total (Sum of all rules on this band)
                            subsets[call].setdefault(band, set()).add(composite_key)
                            # 4. Band_Rule (Specific)
                            subsets[call].setdefault(f'{band}_{mult_name}', set()).add(composite_key)

        # 2. Helper to run comparison and build row
        def build_row(label, set_key, indent=0, is_bold=False):
            # Build dictionary of sets for this specific key across all logs
            sets_to_compare = {}
            for call in all_calls:
                sets_to_compare[call] = subsets[call].get(set_key, set())
            
            comp = ComparativeEngine.compare_logs(sets_to_compare)
            
            # Re-derive common set locally to calculate unique composition
            # Common is intersection of all logs involved
            common_items = set.intersection(*sets_to_compare.values()) if sets_to_compare else set()
            
            is_single_log = len(all_calls) == 1
            
            stations_list = []
            for call in all_calls:
                metrics = comp.station_metrics.get(call)
                if metrics:
                    log_set = sets_to_compare[call]
                    
                    if is_single_log:
                        # For single log: Calculate Run/S&P totals from entire set (not just unique)
                        # This replaces "Common" with Run/S&P breakdown for single log display
                        u_run = 0
                        u_sp = 0
                        u_unk = 0
                        
                        for item in log_set:
                            status = mult_status_map[call].get(item, 'Unk')
                            if status in ['Run', 'Mixed']: u_run += 1
                            elif status == 'S&P': u_sp += 1
                            else: u_unk += 1
                    else:
                        # For multi-log: Unique = Log Set - Common Set
                        unique_items = log_set - common_items
                        
                        u_run = 0
                        u_sp = 0
                        u_unk = 0
                        
                        for item in unique_items:
                            status = mult_status_map[call].get(item, 'Unk')
                            # Map 'Both' to 'Run' or 'S&P'? Usually 'Run' is dominant/preferred, 
                            # but 'Both' implies it was worked multiple times.
                            # Let's map 'Both' to 'Run' as it indicates ability to hold frequency.
                            if status in ['Run', 'Mixed']: u_run += 1
                            elif status == 'S&P': u_sp += 1
                            else: u_unk += 1

                    stations_list.append({
                        'count': metrics.count,
                        'delta': metrics.count - comp.universe_count, # Delta from Par (Total Worked)
                        'unique_run': u_run,
                        'unique_sp': u_sp,
                        'unique_unk': u_unk
                    })
                else:
                    stations_list.append({'count': 0, 'delta': -comp.universe_count, 'unique_run': 0, 'unique_sp': 0, 'unique_unk': 0})

            return {
                'label': label,
                'indent': indent,
                'is_bold': is_bold,
                'total_worked': comp.universe_count,
                'common': comp.common_count,
                'stations': stations_list
            }

        # Helper to inject max_unique for scaling
        def inject_max_unique(row_data):
            # Calculate max unique count across all stations in this row
            max_unique = max((s['unique_run'] + s['unique_sp'] + s['unique_unk']) for s in row_data['stations']) if row_data['stations'] else 1
            row_data['max_unique'] = max_unique if max_unique > 0 else 1 # Avoid division by zero
            return row_data

        # Structured Output
        totals_rows = []
        band_blocks = []
        
        # 3. Build Table Rows
        # A. Grand Total
        totals_rows.append(inject_max_unique(build_row("TOTAL", "TOTAL", indent=0, is_bold=True)))
        
        # B. Global Rule Breakdowns
        for rule in self.contest_def.multiplier_rules:
            r_name = rule['name']
            totals_rows.append(inject_max_unique(build_row(r_name, f"TOTAL_{r_name}", indent=1, is_bold=False)))

        # C. Per Band Breakdowns (only if not once_per_log heavy)
        # Only show bands if there is data
        has_band_data = any(len(subsets[c].get(b, set())) > 0 for c in all_calls for b in valid_bands)
        
        if has_band_data:
            for band in valid_bands:
                # Check if band has activity
                if not any(len(subsets[c].get(band, set())) > 0 for c in all_calls):
                    continue
                
                # Create block for this band
                band_rows = []
                band_rows.append(inject_max_unique(build_row(band, band, indent=0, is_bold=True)))
                
                for rule in self.contest_def.multiplier_rules:
                    if rule.get('totaling_method') == 'once_per_log': continue
                    r_name = rule['name']
                    band_rows.append(inject_max_unique(build_row(r_name, f"{band}_{r_name}", indent=1, is_bold=False)))
                
                band_blocks.append({
                    'label': band,
                    'rows': band_rows
                })

        return {
            'totals': totals_rows,
            'bands': band_blocks
        }