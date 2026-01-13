# contest_tools/reports/text_continent_summary.py
#
# Purpose: A text report that generates a summary of QSOs per continent,
#          broken down by band for multiple logs.
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

from typing import List
import pandas as pd
import os
from ..contest_log import ContestLog
from .report_interface import ContestReport
from contest_tools.utils.report_utils import format_text_header, get_cty_metadata, get_standard_title_lines
from ..data_aggregators.categorical_stats import CategoricalAggregator

class Report(ContestReport):
    """
    Generates a summary of QSOs per continent, broken down by band.
    """
    report_id: str = "continent_summary"
    report_name: str = "Continent QSO Summary"
    report_type: str = "text"
    supports_single = True

    def generate(self, output_path: str, **kwargs) -> str:
        """
        Generates the report content.
        """
        include_dupes = kwargs.get('include_dupes', False)
        final_report_messages = []
        
        aggregator = CategoricalAggregator()
        stats_list = aggregator.get_continent_stats(self.logs, include_dupes=include_dupes)

        for log, stats in zip(self.logs, stats_list):
            metadata = log.get_metadata()
            callsign = metadata.get('MyCall', 'UnknownCall')
            
            if stats['is_empty']:
                msg = f"Skipping report for {callsign}: No valid QSOs to report."
                print(msg)
                final_report_messages.append(msg)
                continue

            continent_map = {
                'NA': 'North America', 'SA': 'South America', 'EU': 'Europe',
                'AS': 'Asia', 'AF': 'Africa', 'OC': 'Oceania', 'Unknown': 'Unknown'
            }
            
            bands = stats['bands']
            is_single_band = len(bands) == 1
            pivot_data = stats['pivot']
            unique_unknown_calls = stats['unknown_calls']
            
            # Remap keys from Code to Name for display
            display_data = {}
            for code, row_data in pivot_data.items():
                name = continent_map.get(code, 'Unknown')
                display_data[name] = row_data

            header_parts = [f"{b.replace('M',''):>7}" for b in bands]
            if not is_single_band:
                header_parts.append(f"{'Total':>7}")
            table_header = f"{'Continent':<17}" + "".join(header_parts)
            table_width = len(table_header)
            separator = "-" * table_width
            
            report_lines = []
            
            # --- Standard Header ---
            # For header generation, we can peek at the log since we have it, 
            # or assume all modes if not empty. Let's use log.get_processed_data just for mode set 
            # or pass it from aggregator? 
            # To stay strictly decoupled, we should ideally get modes from aggregator, 
            # but for metadata header generation, accessing log wrapper properties is acceptable in the View Layer.
            df_temp = log.get_processed_data()
            modes_present = set(df_temp['Mode'].dropna().unique()) if not df_temp.empty else set()
            
            title_lines = get_standard_title_lines(self.report_name, [log], "All Bands", None, modes_present)
            meta_lines = ["Contest Log Analytics by KD4D", get_cty_metadata([log])]
            
            header_block = format_text_header(table_width, title_lines, meta_lines)
            report_lines.extend(header_block)

            report_lines.append("")
            report_lines.append(table_header)
            report_lines.append(separator)

            # Calculate column totals
            col_totals = {b: 0 for b in bands}
            grand_total = 0

            for cont_name in sorted(display_data.keys()):
                row_data = display_data[cont_name]
                row_total = 0
                line = f"{cont_name:<17}"
                
                for band in bands:
                    val = row_data.get(band, 0)
                    line += f"{val:>7}"
                    row_total += val
                    col_totals[band] += val
                
                if not is_single_band:
                    line += f"{row_total:>7}"
                    grand_total += row_total
                report_lines.append(line)

            report_lines.append(separator)
            
            total_line = f"{'Total':<17}"
            for band in bands:
                total_line += f"{col_totals[band]:>7}"
            if not is_single_band:
                total_line += f"{grand_total:>7}"
            report_lines.append(total_line)
            
            if unique_unknown_calls:
                report_lines.append("\n" + "-" * 30)
                report_lines.append("Callsigns with 'Unknown' Continent:")
                report_lines.append("-" * 30)
                
                col_width = 12
                num_cols = max(1, table_width // (col_width + 2))
                
                for i in range(0, len(unique_unknown_calls), num_cols):
                    line_calls = unique_unknown_calls[i:i+num_cols]
                    report_lines.append("  ".join([f"{call:<{col_width}}" for call in line_calls]))

            report_content = "\n".join(report_lines) + "\n"
            os.makedirs(output_path, exist_ok=True)
            
            filename = f"{self.report_id}_{callsign}.txt"
            filepath = os.path.join(output_path, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            final_report_messages.append(f"Text report saved to: {filepath}")

        return "\n".join(final_report_messages)