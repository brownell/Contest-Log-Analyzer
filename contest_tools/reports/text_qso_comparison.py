# contest_tools/reports/text_qso_comparison.py
#
# Purpose: Generates a text-based report that provides a detailed pairwise
#          comparison of QSO counts (Total, Unique, Common) between two logs,
#          broken down by band and Run/S&P status.
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

from .report_interface import ContestReport
from contest_tools.utils.report_utils import create_output_directory, format_text_header, get_cty_metadata, get_standard_title_lines
import pandas as pd
import os
from ..contest_log import ContestLog
from ..data_aggregators.categorical_stats import CategoricalAggregator

class Report(ContestReport):
    report_id: str = "qso_comparison"
    report_name: str = "QSO Comparison Summary"
    report_type: str = "text"
    supports_single = False
    supports_pairwise = True
    supports_multi = False

    def generate(self, output_path: str, **kwargs) -> str:
        create_output_directory(output_path)
        include_dupes = kwargs.get('include_dupes', False)

        if len(self.logs) != 2:
            return f"Report '{self.report_name}' requires exactly two logs for pairwise comparison. Skipping."
        
        log1, log2 = self.logs[0], self.logs[1]
        call1 = log1.get_metadata().get('MyCall', 'Log1')
        call2 = log2.get_metadata().get('MyCall', 'Log2')

        aggregator = CategoricalAggregator()
        # Pre-check global data availability
        global_data = aggregator.compute_comparison_breakdown(log1, log2, include_dupes=include_dupes)
        if global_data['metrics']['total_1'] == 0 or global_data['metrics']['total_2'] == 0:
            return f"Skipping '{self.report_name}': At least one log has no valid QSOs."

        canonical_band_order = [band[1] for band in ContestLog._HAM_BANDS]
        bands = log1.contest_definition.valid_bands # Iterate all valid contest bands
        
        # --- Header Generation ---
        table_width = 86
        modes_present = set(pd.concat([
            pd.Series(list(global_data['log1_unique'].keys())), 
            pd.Series(list(global_data['log2_unique'].keys()))
        ]).unique()) # Simplified mode check based on aggregator keys
        
        title_lines = get_standard_title_lines(self.report_name, self.logs, "All Bands", None, modes_present)
        
        meta_lines = ["Contest Log Analytics by KD4D", get_cty_metadata(self.logs)]
        
        report_lines = []
        report_lines.extend(format_text_header(table_width, title_lines, meta_lines))
        report_lines.append("="*86)
        
        # Initialize accumulators for the grand totals
        # Structure: [Total_QSO, Unique_Total, Common_Total]
        total_qso_1, total_unique_1, total_common_1 = 0, 0, 0
        total_qso_2, total_unique_2, total_common_2 = 0, 0, 0
        
        # Structure: [Run, S&P, Unk] for Unique
        total_run_unique_1, total_sp_unique_1, total_unk_unique_1 = 0, 0, 0
        total_run_unique_2, total_sp_unique_2, total_unk_unique_2 = 0, 0, 0
        
        # Structure: [Run, S&P, Unk] for Common
        total_run_common_1, total_sp_common_1, total_unk_common_1 = 0, 0, 0
        total_run_common_2, total_sp_common_2, total_unk_common_2 = 0, 0, 0

        # Helper to print the table header
        def append_table_header():
            report_lines.append(f"{'':9} {'TOTAL':>8} | {'UNIQUE (Breakdown)':^27} | {'COMMON (Breakdown)':^27}")
            report_lines.append(f"{'Call':<9} {'QSOs':>8} | {'Tot':>6} {'Run':>6} {'S&P':>6} {'Unk':>6} | {'Tot':>6} {'Run':>6} {'S&P':>6} {'Unk':>6}")
            report_lines.append(f"{'-'*9} {'-'*8} | {'-'*27} | {'-'*27}")

        for band in bands:
            # Fetch comparison data for this band via DAL
            data = aggregator.compute_comparison_breakdown(log1, log2, band_filter=band, include_dupes=include_dupes)
            
            # Skip empty bands
            if data['metrics']['total_1'] == 0 and data['metrics']['total_2'] == 0:
                continue

            report_lines.append(f"\n--- {band} ---")
            append_table_header()
            
            # Unpack Common Data
            rc1 = data['common_detail']['log1']['run']
            sc1 = data['common_detail']['log1']['sp']
            uc1 = data['common_detail']['log1']['unk']
            common_count_1 = rc1 + sc1 + uc1

            rc2 = data['common_detail']['log2']['run']
            sc2 = data['common_detail']['log2']['sp']
            uc2 = data['common_detail']['log2']['unk']
            common_count_2 = rc2 + sc2 + uc2
            
            # Unpack Unique Data
            ru1 = data['log1_unique']['run']
            su1 = data['log1_unique']['sp']
            uu1 = data['log1_unique']['unk']
            unique_count_1 = ru1 + su1 + uu1
            total_count_1 = data['metrics']['total_1']
            
            ru2 = data['log2_unique']['run']
            su2 = data['log2_unique']['sp']
            uu2 = data['log2_unique']['unk']
            unique_count_2 = ru2 + su2 + uu2
            total_count_2 = data['metrics']['total_2']
            
            # --- PRINT ROW ---
            # Call | Total | Unique(Tot, Run, SP, Unk) | Common(Tot, Run, SP, Unk)
            report_lines.append(f"{call1:<9} {total_count_1:>8} | {unique_count_1:>6} {ru1:>6} {su1:>6} {uu1:>6} | {common_count_1:>6} {rc1:>6} {sc1:>6} {uc1:>6}")
            report_lines.append(f"{call2:<9} {total_count_2:>8} | {unique_count_2:>6} {ru2:>6} {su2:>6} {uu2:>6} | {common_count_2:>6} {rc2:>6} {sc2:>6} {uc2:>6}")

            # --- ACCUMULATE TOTALS ---
            # Log 1
            total_qso_1 += total_count_1
            total_unique_1 += unique_count_1
            total_common_1 += common_count_1
            total_run_unique_1 += ru1
            total_sp_unique_1 += su1
            total_unk_unique_1 += uu1
            total_run_common_1 += rc1
            total_sp_common_1 += sc1
            total_unk_common_1 += uc1

            # Log 2
            total_qso_2 += total_count_2
            total_unique_2 += unique_count_2
            total_common_2 += common_count_2
            total_run_unique_2 += ru2
            total_sp_unique_2 += su2
            total_unk_unique_2 += uu2
            total_run_common_2 += rc2
            total_sp_common_2 += sc2
            total_unk_common_2 += uc2
        
        # --- TOTALS Section ---
        report_lines.append("\n" + "="*86 + "\n--- GRAND TOTALS ---")
        append_table_header()
        
        report_lines.append(f"{call1:<9} {total_qso_1:>8} | {total_unique_1:>6} {total_run_unique_1:>6} {total_sp_unique_1:>6} {total_unk_unique_1:>6} | {total_common_1:>6} {total_run_common_1:>6} {total_sp_common_1:>6} {total_unk_common_1:>6}")
        report_lines.append(f"{call2:<9} {total_qso_2:>8} | {total_unique_2:>6} {total_run_unique_2:>6} {total_sp_unique_2:>6} {total_unk_unique_2:>6} | {total_common_2:>6} {total_run_common_2:>6} {total_sp_common_2:>6} {total_unk_common_2:>6}")
        
        # Save to file
        output_filename = os.path.join(output_path, f"{self.report_id}_{call1}_vs_{call2}.txt")
        try:
            with open(output_filename, 'w') as f:
                f.write("\n".join(report_lines) + "\n")
            return f"'{self.report_name}' saved to {output_filename}"
        except Exception as e:
            return f"Error generating report '{self.report_name}': {e}"