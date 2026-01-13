# contest_tools/data_aggregators/categorical_stats.py
#
# Purpose: DAL Component to handle aggregation logic related to categorical data
#          such as QSO point breakdowns and set comparisons (unique/common QSOs).
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

from typing import List, Dict, Union, Set, Tuple, Any
import pandas as pd
from contest_tools.utils.report_utils import get_valid_dataframe

# Placeholder type for type hinting only
class ContestLog:
    pass

class CategoricalAggregator:
    """
    DAL Component: Handles aggregation logic related to categorical data
    such as QSO point breakdowns and set comparisons (unique/common QSOs).
    """

    def _apply_filters(self, df: pd.DataFrame, band_filter: str = None, mode_filter: str = None) -> pd.DataFrame:
        """Internal helper to apply optional band and mode filters to a DataFrame."""
        if df.empty:
            return df

        filtered_df = df.copy()

        if band_filter:
            filtered_df = filtered_df[filtered_df['Band'] == band_filter]
        
        if mode_filter:
            # Check the contest Mode (CW/PH), not the Run/S&P status
            if 'Mode' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['Mode'] == mode_filter]

        return filtered_df

    def get_points_breakdown(self, logs: List[ContestLog], band_filter: str = None, mode_filter: str = None) -> Dict:
        """
        Calculates total points and a breakdown of points by QSO point value.
        """
        result: Dict = {"logs": {}}

        for log in logs:
            callsign = log.get_metadata().get('MyCall', 'UNKNOWN_LOG')
            
            # 1. Internal: Get DataFrame via Utility
            df = get_valid_dataframe(log)
            filtered_df = self._apply_filters(df, band_filter, mode_filter)

            if filtered_df.empty:
                result["logs"][callsign] = {
                    "total_points": 0,
                    "total_qsos": 0,
                    "breakdown": {}
                }
                continue

            # 2. Aggregation: Calculate totals and breakdown
            total_points = filtered_df['QSOPoints'].sum()
            total_qsos = len(filtered_df)
            
            breakdown_counts = filtered_df['QSOPoints'].value_counts()
            breakdown = {str(k): int(v) for k, v in breakdown_counts.items()}

            # 3. Final structure assembly
            result["logs"][callsign] = {
                "total_points": int(total_points) if not pd.isna(total_points) else 0,
                "total_qsos": int(total_qsos),
                "breakdown": breakdown
            }
        
        return result

    def _get_qso_mode_counts(self, df: pd.DataFrame) -> Dict[str, int]:
        """Internal helper to categorize QSOs by Run, S&P, or Unknown."""
        if df.empty:
            return {'run': 0, 'sp': 0, 'unk': 0}
        
        # Normalize the 'Run' column
        # Actual values are 'Run', 'S&P', 'Unknown'
        modes = df['Run'].astype(str).str.lower().str.strip()
        
        counts = modes.value_counts().to_dict()
        
        # Map to schematic keys
        # 'run' -> 'run', 's&p' -> 'sp', 'unknown' -> 'unk'
        return {
            'run': counts.get('run', 0),
            'sp': counts.get('s&p', 0),
            'unk': counts.get('unknown', 0)
        }

    def compute_comparison_breakdown(self, log1: ContestLog, log2: ContestLog, band_filter: str = None, mode_filter: str = None, include_dupes: bool = False) -> Dict:
        """
        Compares two logs for unique and common QSOs based on 'Call',
        and provides a breakdown of results by run/S&P mode.
        """
        # 1. Internal: Get DataFrames
        df1_raw = get_valid_dataframe(log1, include_dupes=include_dupes)
        df2_raw = get_valid_dataframe(log2, include_dupes=include_dupes)
        
        df1 = self._apply_filters(df1_raw, band_filter, mode_filter)
        df2 = self._apply_filters(df2_raw, band_filter, mode_filter)
        
        # Dynamic Uniqueness Key
        # If filtering by band/mode, Call is sufficient.
        # If global, we should technically use Call+Band+Mode, but standard practice is often just Call.
        # Following original 'qso_comparison' logic (Source 1630): It uses simple set intersection on 'Call'.
        # We will adhere to that standard.
        uniqueness_cols = ['Call']
            
        set1 = set(df1['Call'].unique())
        set2 = set(df2['Call'].unique())

        common_keys = set1.intersection(set2)
        unique1_keys = set1.difference(set2)
        unique2_keys = set2.difference(set1)
        
        common_calls = common_keys
        unique1_calls = unique1_keys
        unique2_calls = unique2_keys

        # 3. Categorical Breakdown for Unique Sets
        df1_unique = df1[df1['Call'].isin(unique1_calls)].copy()
        df2_unique = df2[df2['Call'].isin(unique2_calls)].copy()
        
        log1_unique_breakdown = self._get_qso_mode_counts(df1_unique)
        log2_unique_breakdown = self._get_qso_mode_counts(df2_unique)

        # 4. Categorical Breakdown for Common Set
        common_breakdown: Dict[str, int] = {'run_both': 0, 'sp_both': 0, 'mixed': 0}
        common_detail = {"log1": {'run': 0, 'sp': 0, 'unk': 0}, "log2": {'run': 0, 'sp': 0, 'unk': 0}}

        if common_calls:
            df_common_1 = df1[df1['Call'].isin(common_calls)].copy()
            df_common_2 = df2[df2['Call'].isin(common_calls)].copy()

            # Merge to align common QSOs and their Run/S&P status
            df_merged = pd.merge(
                df_common_1[['Call', 'Run']].drop_duplicates(subset=['Call']).rename(columns={'Run': 'Run1'}),
                df_common_2[['Call', 'Run']].drop_duplicates(subset=['Call']).rename(columns={'Run': 'Run2'}),
                on='Call',
                how='inner'
            )

            if not df_merged.empty:
                # 'Run' column contains 'Run', 'S&P', 'Unknown'
                # run_both
                common_breakdown['run_both'] = len(df_merged[
                    (df_merged['Run1'] == 'Run') & (df_merged['Run2'] == 'Run')
                ])
                
                # sp_both
                common_breakdown['sp_both'] = len(df_merged[
                    (df_merged['Run1'] == 'S&P') & (df_merged['Run2'] == 'S&P')
                ])
                
                # mixed
                common_breakdown['mixed'] = len(df_merged) - (common_breakdown['run_both'] + common_breakdown['sp_both'])
            
            # Calculate independent detail for the common set (required for text_qso_comparison)
            common_detail["log1"] = self._get_qso_mode_counts(df_common_1)
            common_detail["log2"] = self._get_qso_mode_counts(df_common_2)

        # 5. Metrics
        metrics = {
            "total_1": len(df1),
            "total_2": len(df2),
            "unique_1": len(unique1_keys),
            "unique_2": len(unique2_keys),
            "common_total": len(common_keys)
        }
        
        # 6. Final structure assembly
        return {
            "log1_unique": log1_unique_breakdown,
            "log2_unique": log2_unique_breakdown,
            "common": common_breakdown,
            "common_detail": common_detail,
            "metrics": metrics
        }

    def get_category_breakdown(self, log: ContestLog, category_col: str) -> List[Dict[str, Any]]:
        """
        Generates a breakdown of counts for a specific category column, grouped by Band.
        Returns a list of dictionaries suitable for tabulate (Rows=Band, Cols=Category Values).
        """
        df = get_valid_dataframe(log, include_dupes=False)
        if df.empty or category_col not in df.columns:
            return []

        # Pivot: Index='Band', Columns=category_col, Values=Count
        # This structure matches the expectation of text_continent_breakdown.py 
        # (which expects 'Band' as a key in the row)
        pivot = df.pivot_table(index='Band', columns=category_col, aggfunc='size', fill_value=0)
        
        # Reset index to make 'Band' a column in the records
        pivot = pivot.reset_index()
        
        return pivot.to_dict('records')

    def get_log_summary_stats(self, logs: List[ContestLog], include_dupes: bool = False) -> Dict[str, Any]:
        """
        Generates summary statistics for a list of logs (Total, Dupes, Mode Breakdown).
        Returns a dictionary containing 'rows' (list of dicts) and 'meta' (year, contest_name).
        """
        summary_data = []
        year = "UnknownYear"
        contest_name = "UnknownContest"

        for log in logs:
            metadata = log.get_metadata()
            callsign = metadata.get('MyCall', 'Unknown')
            
            # Get full DF to calculate dupes
            df_full = get_valid_dataframe(log, include_dupes=True)
            dupes = df_full['Dupe'].sum() if 'Dupe' in df_full.columns else 0
            
            # Extract global metadata from the first valid log encountered
            if year == "UnknownYear" and not df_full.empty:
                date_series = df_full['Date'].dropna()
                if not date_series.empty:
                    year = date_series.iloc[0].split('-')[0]
                contest_name = metadata.get('ContestName', 'UnknownContest')
            
            # Filter if required
            df = df_full if include_dupes else df_full[df_full['Dupe'] == False]
            
            mode_counts = self._get_qso_mode_counts(df)
            
            summary_data.append({
                'Callsign': callsign,
                'On-Time': metadata.get('OperatingTime'),
                'Total QSOs': len(df),
                'Dupes': int(dupes),
                'Run': mode_counts['run'],
                'S&P': mode_counts['sp'],
                'Unknown': mode_counts['unk']
            })
            
        return {
            "rows": summary_data,
            "meta": {
                "year": year,
                "contest_name": contest_name
            }
        }

    def get_continent_stats(self, logs: List[ContestLog], include_dupes: bool = False) -> List[Dict[str, Any]]:
        """
        Generates continent statistics for text_continent_summary.py.
        Returns pivot data (Continent x Band) and list of unknown callsigns.
        """
        results = []
        for log in logs:
            metadata = log.get_metadata()
            callsign = metadata.get('MyCall', 'UnknownCall')
            
            df = get_valid_dataframe(log, include_dupes=include_dupes)
            
            if df.empty:
                results.append({'callsign': callsign, 'is_empty': True, 'pivot': {}, 'unknown_calls': []})
                continue
                
            # Identify Unknowns
            unknown_continent_df = df[df['Continent'].isin(['Unknown', None, ''])]
            unique_unknown_calls = sorted(unknown_continent_df['Call'].unique())
            
            # Pivot
            bands = log.contest_definition.valid_bands
            pivot = df.pivot_table(
                index='Continent',
                columns='Band',
                aggfunc='size',
                fill_value=0
            )
            
            # Ensure all bands exist
            for band in bands:
                if band not in pivot.columns:
                    pivot[band] = 0
            
            # Convert to dict {Continent: {Band: Count}}
            pivot_dict = pivot.to_dict(orient='index')
            
            results.append({
                'callsign': callsign,
                'is_empty': False,
                'pivot': pivot_dict,
                'unknown_calls': unique_unknown_calls,
                'bands': bands
            })
            
        return results