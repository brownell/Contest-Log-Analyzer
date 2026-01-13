# contest_tools/reports/text_score_report.py
#
# Purpose: A text report that generates a detailed score summary for each
#          log, broken down by band.
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

from typing import List, Dict, Set, Tuple
import pandas as pd
import os
import re
import json
import logging
from ..contest_log import ContestLog
from ..contest_definitions import ContestDefinition
from .report_interface import ContestReport
from contest_tools.utils.report_utils import format_text_header, get_cty_metadata, get_valid_dataframe
from ..data_aggregators.score_stats import ScoreStatsAggregator

class Report(ContestReport):
    """
    Generates a detailed score summary report for each log.
    """
    report_id: str = "score_report"
    report_name: str = "Score Summary"
    report_type: str = "text"
    supports_single = True
    
    def generate(self, output_path: str, **kwargs) -> str:
        """
        Generates the report content.
        """
        final_report_messages = []

        for log in self.logs:
            metadata = log.get_metadata()

            callsign = metadata.get('MyCall', 'UnknownCall')
            contest_name = metadata.get('ContestName', 'UnknownContest')

            # Check for valid data via aggregator or metadata, not raw DF
            df_full = get_valid_dataframe(log, include_dupes=True) # Kept only for Year extraction below
            if df_full.empty:
                msg = f"Skipping score report for {callsign}: No QSO data available."
                final_report_messages.append(msg)
                continue

            # --- Data Aggregation (DAL) ---
            aggregator = ScoreStatsAggregator([log])
            all_scores = aggregator.get_score_breakdown()
            log_scores = all_scores["logs"].get(callsign)
            
            summary_data = log_scores['summary_data']
            total_summary = log_scores['total_summary']
            final_score = log_scores['final_score']
            diagnostic_stats = aggregator.get_diagnostic_stats(log)
            
            # --- Formatting ---
            if log.contest_definition.score_formula == 'total_points':
                mult_names = []
            else:
                mult_names = [rule['name'] for rule in log.contest_definition.multiplier_rules]
            
            col_order = ['Band', 'Mode', 'QSOs'] + mult_names + ['Points', 'AVG']
            col_widths = {key: len(str(key)) for key in col_order}

            all_data_for_width = summary_data + [total_summary]
            for row in all_data_for_width:
                for key, value in row.items():
                    if key in col_widths:
                        val_len = len(f"{value:,.0f}") if isinstance(value, (int, float)) and key not in ['AVG'] else len(str(value))
                        if isinstance(value, float) and key == 'AVG':
                            val_len = len(f"{value:.2f}")
                        
                        col_widths[key] = max(col_widths.get(key, 0), val_len)

            year = df_full['Date'].iloc[0].split('-')[0] if not df_full.empty and not df_full['Date'].dropna().empty else "----"
            
            header_parts = [f"{name:>{col_widths[name]}}" for name in col_order]
            header = "  ".join(header_parts)
            table_width = len(header)
            separator = "-" * table_width
            
            # --- New 3-Line Header ---
            title_lines = [
                f"--- {self.report_name} ---",
                f"{year} {contest_name} - {callsign}",
                "All Bands" # Score report is always a summary of all bands
            ]
            
            meta_lines = [
                "Contest Log Analytics by KD4D",
                get_cty_metadata([log])
            ]
            
            report_lines = []
            # Ensure table is at least wide enough for header
            min_header_width = max(len(l) for l in title_lines) + max(len(l) for l in meta_lines) + 5
            final_width = max(table_width, min_header_width)
            
            report_lines.extend(format_text_header(final_width, title_lines, meta_lines))
            
            report_lines.append("")
            on_time_str = metadata.get('OperatingTime')
            if on_time_str:
                report_lines.append(f"Operating Time: {on_time_str}")
            report_lines.append("")
            
            report_lines.append(header)
            report_lines.append(separator)

            # Data is already sorted hierarchically by _calculate_all_scores

            previous_band = None
            for item in summary_data:
                # Add separator between band groups
                current_band = item.get('Band')
                if previous_band is not None and current_band != previous_band:
                     report_lines.append(separator)
                previous_band = current_band

                data_parts = [f"{str(item.get(name, '')):{'>' if name != 'Band' else '<'}{col_widths[name]}}" for name in ['Band', 'Mode']]
                data_parts.append(f"{item.get('QSOs', 0):>{col_widths['QSOs']},.0f}")
                data_parts.extend([f"{item.get(name, 0):>{col_widths[name]},.0f}" for name in mult_names])
                data_parts.extend([
                    f"{item.get('Points', 0):>{col_widths['Points']},.0f}",
                    f"{item.get('AVG', 0):>{col_widths['AVG']}.2f}"
                ])
                report_lines.append("  ".join(data_parts))
            
            report_lines.append(separator)
            
            total_parts = [f"{str(total_summary.get(name, '')):{'>' if name != 'Band' else '<'}{col_widths[name]}}" for name in ['Band', 'Mode']]
            total_parts.append(f"{total_summary.get('QSOs', 0):>{col_widths['QSOs']},.0f}")
            total_parts.extend([f"{total_summary.get(name, 0):>{col_widths[name]},.0f}" for name in mult_names])
            total_parts.extend([
                f"{total_summary.get('Points', 0):>{col_widths['Points']},.0f}",
                f"{total_summary.get('AVG', 0):>{col_widths['AVG']}.2f}"
            ])
            report_lines.append("  ".join(total_parts))
            
            report_lines.append("=" * table_width)
            score_text = f"TOTAL SCORE : {final_score:,.0f}"
            report_lines.append(score_text.rjust(table_width))

            self._add_diagnostic_sections(report_lines, diagnostic_stats, log)

            report_content = "\n".join(report_lines) + "\n"
            os.makedirs(output_path, exist_ok=True)
            filename = f"{self.report_id}_{callsign}.txt"
            filepath = os.path.join(output_path, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            final_report_messages.append(f"Text report saved to: {filepath}")

        return "\n".join(final_report_messages)

    def _add_diagnostic_sections(self, report_lines: List[str], diagnostics: Dict[str, List[str]], log: ContestLog):
        """Appends sections for 'Unknown' and 'Unassigned' multipliers."""
        if not diagnostics:
            return

        contest_def = log.contest_definition
        for rule in contest_def.multiplier_rules:
            mult_name = rule['name']
            
            # --- Check for "Unknown" Multipliers ---
            unknown_calls = diagnostics.get(f"unknown_{mult_name}", [])
            if unknown_calls:
                report_lines.append("\n" + "-" * 40)
                report_lines.append(f"Callsigns with 'Unknown' {mult_name}:")
                report_lines.append("-" * 40)
                for i in range(0, len(unknown_calls), 5):
                    line_calls = unknown_calls[i:i+5]
                    report_lines.append("  ".join([f"{call:<12}" for call in line_calls]))

            # --- Check for "Unassigned" (NaN) Multipliers ---
            unassigned_calls = diagnostics.get(f"unassigned_{mult_name}", [])
            if unassigned_calls:
                report_lines.append("\n" + "-" * 40)
                report_lines.append(f"Callsigns with Unassigned {mult_name}:")
                report_lines.append("-" * 40)
                for i in range(0, len(unassigned_calls), 5):
                    line_calls = unassigned_calls[i:i+5]
                    report_lines.append("  ".join([f"{call:<12}" for call in line_calls]))