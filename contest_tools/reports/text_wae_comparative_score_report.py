# contest_tools/reports/text_wae_comparative_score_report.py
#
# Purpose: A text report that generates a comparative, interleaved score
#          summary for the WAE contest.
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
from prettytable import PrettyTable
from ..contest_log import ContestLog
from ..contest_definitions import ContestDefinition
from .report_interface import ContestReport
from contest_tools.utils.report_utils import create_output_directory, _sanitize_filename_part, format_text_header, get_cty_metadata, get_standard_title_lines
from ..data_aggregators.wae_stats import WaeStatsAggregator

class Report(ContestReport):
    """
    Generates a comparative, interleaved WAE score summary report.
    """
    report_id: str = "text_wae_comparative_score_report"
    report_name: str = "WAE Comparative Score Report"
    report_type: str = "text"
    is_specialized = True
    supports_multi = True
    supports_pairwise = True
    
    def generate(self, output_path: str, **kwargs) -> str:
        """Generates the report content."""
        all_calls = sorted([log.get_metadata().get('MyCall', 'Unknown') for log in self.logs])
        
        # --- Data Aggregation via DAL ---
        aggregator = WaeStatsAggregator()
        wae_data = aggregator.get_wae_breakdown(self.logs)
        
        # --- Transform DAL output for View ---
        # Structure needed: band_mode_summaries[(band, mode)] = list of dicts {Callsign, QSO Pts, Weighted Mults}
        band_mode_summaries = {}
        modes_present = set()
        
        for call, data in wae_data['logs'].items():
            for row in data['breakdown']:
                key = (row['band'], row['mode'])
                if key not in band_mode_summaries:
                    band_mode_summaries[key] = []
                modes_present.add(row['mode'])
                
                band_mode_summaries[key].append({
                    'Callsign': call,
                    'QSO Pts': row['qso_points'],
                    'Weighted Mults': row['weighted_mults']
                })

        # --- Report Generation using PrettyTable ---
        # Sorting keys based on aggregator's canonical order isn't directly exposed, 
        # so we rely on the internal knowledge or re-sort.
        # The aggregator output for each log is sorted, but the keys of band_mode_summaries need sorting.
        canonical_band_order = [band[1] for band in ContestLog._HAM_BANDS]
        sorted_keys = sorted(band_mode_summaries.keys(), key=lambda x: (
            canonical_band_order.index(x[0]) if x[0] in canonical_band_order else 99, 
            x[1]
        ))

        report_lines = []
        table = PrettyTable()
        table.field_names = ["Callsign", "QSO Pts", "Weighted Mults"]
        
        table.align = 'r'
        table.align['Callsign'] = 'l'

        for key in sorted_keys:
            band, mode = key
            report_lines.append(f"\n--- {band} {mode} ---")
            
            table.clear_rows()
            # Sort rows by callsign
            for row in sorted(band_mode_summaries[key], key=lambda x: x['Callsign']):
                table.add_row([row['Callsign'], f"{row['QSO Pts']:,}", f"{row['Weighted Mults']:,}"])
            report_lines.append(table.get_string())

        # --- TOTALS Section ---
        report_lines.append("\n--- TOTAL ---")
        
        total_table = PrettyTable()
        total_table.field_names = ["Callsign", "On-Time", "QSO Pts", "QTC Pts", "Weighted Mults"]
        total_table.align = 'r'
        total_table.align['Callsign'] = 'l'
        total_table.align['On-Time'] = 'l'
        
        final_scores = {}

        for call in all_calls:
            if call in wae_data['logs']:
                scalars = wae_data['logs'][call]['scalars']
                total_table.add_row([
                    call, 
                    scalars['on_time'], 
                    f"{scalars['total_qso_points']:,}", 
                    f"{scalars['total_qtc_points']:,}", 
                    f"{scalars['total_weighted_mults']:,}"
                ])
                final_scores[call] = scalars['final_score']
        
        report_lines.append(total_table.get_string())
        
        # --- Final Score Summary ---
        final_score_lines = ["", "Final Score Summary", "="*20]
        max_label_width = max(len(f"TOTAL SCORE ({call})") for call in all_calls)
        for call in all_calls:
            label = f"TOTAL SCORE ({call})"
            score_str = f"{final_scores.get(call, 0):,}"
            final_score_lines.append(f"{label:<{max_label_width}} : {score_str}")
        report_lines.extend(final_score_lines)

        # --- Generate Standard Header ---
        title_lines = get_standard_title_lines(self.report_name, self.logs, "All Bands", None, modes_present)
        meta_lines = ["Contest Log Analytics by KD4D", get_cty_metadata(self.logs)]
        # Calculate roughly width from one of the tables or default
        header_block = format_text_header(80, title_lines, meta_lines)
        
        final_report_str = "\n".join(header_block + report_lines) + "\n"
        
        # --- Save to File ---
        create_output_directory(output_path)
        filename_calls = '_'.join([_sanitize_filename_part(c) for c in sorted(all_calls)])
        filename = f"{self.report_id}_{filename_calls}.txt"
        filepath = os.path.join(output_path, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(final_report_str)
        
        return f"Text report saved to: {filepath}"