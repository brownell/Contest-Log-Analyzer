# contest_tools/reports/text_comparative_score_report.py
#
# Purpose: A text report that generates an interleaved, comparative score
#          summary, broken down by band, for multiple logs.
#          This version serves as a proof-of-concept for using the tabulate library.
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

from typing import List, Set, Dict, Tuple
import pandas as pd
import os
from tabulate import tabulate
from ..contest_log import ContestLog
from ..contest_definitions import ContestDefinition
from .report_interface import ContestReport
from contest_tools.utils.report_utils import _sanitize_filename_part, format_text_header, get_cty_metadata, get_standard_title_lines
from ..data_aggregators.score_stats import ScoreStatsAggregator

class Report(ContestReport):
    """
    Generates a comparative, interleaved score summary report (tabulate version).
    """
    report_id: str = "comparative_score_report"
    report_name: str = "Comparative Score Report"
    report_type: str = "text"
    supports_multi = True
    supports_pairwise = True
    
    def generate(self, output_path: str, **kwargs) -> str:
        """
        Generates the report content.
        """
        all_calls = sorted([log.get_metadata().get('MyCall', 'Unknown') for log in self.logs])
        first_log = self.logs[0]
        contest_def = first_log.contest_definition

        # --- DAL Aggregation ---
        aggregator = ScoreStatsAggregator(self.logs)
        all_scores = aggregator.get_score_breakdown()
        
        # --- Define Column Order and Header Formatting ---
        if contest_def.score_formula == 'total_points':
            mult_names = []
        else:
            mult_names = [rule['name'] for rule in contest_def.multiplier_rules]
            
        col_order = ['Callsign', 'On-Time', 'QSOs'] + mult_names + ['Points', 'AVG']

        # Build total_summaries list for the header and footer sections
        # Format: (total_summary_dict, final_score_int)
        total_summaries = []
        for log in self.logs:
            call = log.get_metadata().get('MyCall', 'Unknown')
            log_data = all_scores['logs'].get(call, {})
            total_summaries.append((log_data.get('total_summary', {}), log_data.get('final_score', 0)))

        has_on_time = any(s[0].get('On-Time') and s[0].get('On-Time') != 'N/A' for s in total_summaries)
        if not has_on_time:
            col_order.remove('On-Time')
        
        header_map = {col: col.replace(' ', '\n') for col in col_order}

        # --- Report Lines List ---
        report_lines = []
        
        # --- Data Aggregation by Band and Mode ---
        band_mode_summaries = {}
        
        for log in self.logs:
            call = log.get_metadata().get('MyCall', 'Unknown')
            log_data = all_scores['logs'].get(call, {})
            
            # summary_data is a list of dicts: {'Band': '10M', 'Mode': 'CW', ...}
            for row in log_data.get('summary_data', []):
                band = row['Band']
                mode = row['Mode']
                
                # We only want specific mode rows, not the 'ALL' summaries
                if mode == 'ALL': continue
                
                key = (band, mode)
                if key not in band_mode_summaries:
                    band_mode_summaries[key] = []
                
                # Convert row to flattened format for this report
                row_copy = row.copy()
                row_copy['Callsign'] = call
                band_mode_summaries[key].append(row_copy)

        # --- Report Generation using tabulate ---
        canonical_band_order = [band[1] for band in ContestLog._HAM_BANDS]
        sorted_keys = sorted(band_mode_summaries.keys(), key=lambda x: (canonical_band_order.index(x[0]), x[1]))

        for key in sorted_keys:
            band, mode = key
            report_lines.append(f"\n--- {band} {mode} ---")
            
            summary_df = pd.DataFrame(band_mode_summaries[key])
            summary_df = summary_df.reindex(columns=col_order)
            
            if 'On-Time' in summary_df.columns:
                summary_df['On-Time'] = summary_df['On-Time'].fillna('')

            summary_df.rename(columns=header_map, inplace=True)
            table_string = tabulate(summary_df, headers='keys', tablefmt='psql', floatfmt=".2f", showindex="never")
            report_lines.append(table_string)

        report_lines.append("\n--- TOTAL ---")
        
        total_summary_list = [s[0] for s in total_summaries]
        # Add callsign to total_summary dicts for display
        for i, s in enumerate(total_summary_list):
               s['Callsign'] = self.logs[i].get_metadata().get('MyCall')
               s['On-Time'] = self.logs[i].get_metadata().get('OperatingTime')

        total_df = pd.DataFrame(total_summary_list)
        total_df = total_df.reindex(columns=col_order)
        total_df.rename(columns=header_map, inplace=True)
        
        total_table_string = tabulate(total_df, headers='keys', tablefmt='psql', floatfmt=".2f", showindex="never")
        report_lines.append(total_table_string)
        
        table_width = len(total_table_string.split('\n')[0])
        report_lines.append("=" * table_width)
        report_lines.append("")
        
        # --- Final Score Formatting with Aligned Colons and Scores ---
        score_labels = [f"TOTAL SCORE ({s[0]['Callsign']})" for s in total_summaries]
        score_values = [f"{s[1]:,.0f}" for s in total_summaries]
        
        max_label_width = max(len(label) for label in score_labels) if score_labels else 0
        max_score_width = max(len(value) for value in score_values) if score_values else 0

        for i in range(len(total_summaries)):
            label = score_labels[i]
            score_str = score_values[i]
            
            padded_label = f"{label:>{max_label_width}}"
            padded_score = f"{score_str:>{max_score_width}}"
            
            line = f"{padded_label} : {padded_score}"
            
            padding = table_width - len(line)
            final_line = " " * padding + line
            report_lines.append(final_line)

        # --- Generate Standard Header ---
        modes_present = set()
        for log in self.logs:
            df = log.get_processed_data()
            if 'Mode' in df.columns:
                modes_present.update(df['Mode'].dropna().unique())

        title_lines = get_standard_title_lines(self.report_name, self.logs, "All Bands", None, modes_present)
        meta_lines = ["Contest Log Analytics by KD4D", get_cty_metadata(self.logs)]
        
        header_block = format_text_header(table_width, title_lines, meta_lines)
        report_lines = header_block + report_lines

        # --- Save to File ---
        report_content = "\n".join(report_lines) + "\n"
        os.makedirs(output_path, exist_ok=True)
        filename_calls = '_'.join([_sanitize_filename_part(c) for c in sorted(all_calls)])
        filename = f"{self.report_id}_{filename_calls}.txt"
        filepath = os.path.join(output_path, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_content)
         
        return f"Text report saved to: {filepath}"