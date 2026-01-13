# contest_tools/reports/text_multiplier_breakdown.py
#
# Purpose: Specialized text report for multiplier breakdown (Group Par).
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

import os
from .report_interface import ContestReport
from ..data_aggregators.multiplier_stats import MultiplierStatsAggregator
from contest_tools.utils.report_utils import _sanitize_filename_part, format_text_header, get_cty_metadata, get_standard_title_lines

class Report(ContestReport):
    report_id = "text_multiplier_breakdown"
    report_name = "Multiplier Breakdown (Text)"
    is_specialized = False
    supports_multi = True
    supports_single = True

    def generate(self, output_path: str, **kwargs) -> str:
        # 1. Aggregate Data
        mult_agg = MultiplierStatsAggregator(self.logs)
        data = mult_agg.get_multiplier_breakdown_data()
        
    
        # 2. Setup Headers
        # Identify callsigns from logs to ensure alignment
        all_calls = sorted([log.get_metadata().get('MyCall', 'Unknown') for log in self.logs])
        
        # Metadata
        first_log = self.logs[0]
        metadata = first_log.get_metadata()
        contest_name = metadata.get('ContestName', 'Unknown')
        event_id = metadata.get('EventID', '')
    
        df = first_log.get_processed_data()
        year = df['Date'].dropna().iloc[0].split('-')[0] if not df.empty else "----"
            
        # 3. Build Text Content
        lines = []
        
        # Title
        # Smart scoping for title
        
        modes_present = set()
        for log in self.logs:
            df = log.get_processed_data()
            if 'Mode' in df.columns:
                modes_present.update(df['Mode'].dropna().unique())
                
        title_lines = get_standard_title_lines(
            "Multiplier Breakdown (Group Par)", 
            self.logs, 
            "All Bands", 
            None, 
            modes_present
        )
        meta_lines = ["Contest Log Analytics by KD4D", get_cty_metadata(self.logs)]
        
        # Helper to format a row
    
        # Layout: Scope (25), Total (8), Common (8), Call1 (30), Call2 (30)...
        def format_row(label, total, common, station_dict, indent=0):
            prefix = " " * (indent * 2)
            lbl = f"{prefix}{label}"
            
            # Base columns
            row_str = f"{lbl:<25} {total:>8} {common:>8}"
            
            # Station columns
            # Re-implement row formatter to handle list input correctly
            # The previous code assumed station_dict was a dict.
            for i, call in enumerate(all_calls):
                stats = station_dict[i] # station_dict is actually a list here
                
                # Verbose Breakdown: "972 [Run:60 S&P:25 Unk:5] -39"
                count_part = f"{stats['count']}"
              
  
                u_run = stats.get('unique_run', 0)
                u_sp = stats.get('unique_sp', 0)
                u_unk = stats.get('unique_unk', 0)
                
                # Only show breakdown if there are uniques
                total_unique = u_run + u_sp + u_unk
                if total_unique > 0:
                    breakdown = f"[Run:{u_run} S&P:{u_sp} Unk:{u_unk}]"
                else:
                    breakdown = "[Par]"
                
                delta = stats.get('delta', 0)
                # Display absolute value for "Missed" (Positive Deficit)
                delta_part = f"{abs(delta)}" if delta != 0 else "0"
                
                # Align: Count (5) + Breakdown (24) + Missed (6) ~= 35 chars
                col_text = f"{count_part:>5} {breakdown:<24} {delta_part:>6}"
                row_str += f" {col_text}"
            return row_str

        # Header Rows
        # Row 1: Callsigns
        header_row1 = f"{'Scope':<25} {'Total':>8} {'Common':>8}"
        # Row 2: Column Labels (Wrkd, Uniques, Missed)
        header_row2 = f"{'':<25} {'':>8} {'':>8}"

        for call in all_calls:
            # Center alignment (~37 chars to fit data block)
            header_row1 += f" {call:^37}"
            # Sub-headers aligned with data columns: Wrkd(5) Uniques(24) Missed(6)
            header_row2 += f" {'Wrkd':>5} {'Uniques':<24} {'Missed':>6}"
        
        table_width = len(header_row1)
        
        # Generate header with dynamic width
        header_block = format_text_header(table_width, title_lines, meta_lines)
        lines.extend(header_block)
        lines.append("")
        
        lines.append(header_row1)
        lines.append(header_row2)
        lines.append("-" * len(header_row1))
        
        # Process Totals
        for row in data['totals']:
            lines.append(format_row(
                row['label'], 
                row['total_worked'], 
                row['common'], 
                row['stations'], 
                row.get('indent', 0)
            ))
            
        lines.append("")
        lines.append("-" * len(header_row1))
        lines.append("Band Breakdown")
        lines.append("-" * len(header_row1))
        
        # Process Bands
        for block in data['bands']:
            # Band Header
            for row in block['rows']:
                lines.append(format_row(
                    row['label'], 
                    row['total_worked'], 
                    row['common'], 
                    row['stations'], 
                    row.get('indent', 0)
                ))
 
            lines.append("")

        content = "\n".join(lines)
        
        # 4. Save File
        # text_multiplier_breakdown_{callsigns}.txt using utility
        combo_id = "_".join([_sanitize_filename_part(c) for c in all_calls])
        filename = f"text_multiplier_breakdown_{combo_id}.txt"
        
        # Use output_path provided by interface
    
        os.makedirs(output_path, exist_ok=True)
        
        filepath = os.path.join(output_path, filename)
        with open(filepath, 'w') as f:
            f.write(content)
            
        return f"Report saved to {filepath}"