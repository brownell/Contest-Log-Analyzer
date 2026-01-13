# contest_tools/reports/text_missed_multipliers.py
#
# Purpose: A data-driven text report that generates a comparative "missed multipliers"
#          summary.
#          This version uses the `prettytable` library for formatting.
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

from typing import List, Dict, Any, Set
import os
import logging
from prettytable import PrettyTable
from ..contest_log import ContestLog
from ..data_aggregators.multiplier_stats import MultiplierStatsAggregator
from .report_interface import ContestReport
from contest_tools.utils.report_utils import _sanitize_filename_part, format_text_header, get_cty_metadata, get_standard_title_lines

class Report(ContestReport):
    """
    Generates a comparative report showing a specific multiplier worked by each
    station on each band, highlighting missed opportunities (prettytable version).
    """
    report_id: str = "missed_multipliers"
    report_name: str = "Missed Multipliers Report"
    report_type: str = "text"
    supports_single = False
    supports_multi = True
    supports_pairwise = True
    
    def _update_column_widths(self, col_widths, aggregated_data, all_calls, first_col_header):
        """Updates the master column width dictionary based on a band's data."""
        max_mult_len = col_widths.get(first_col_header, len(first_col_header))
        
        for mult in aggregated_data['missed_mults_on_band']:
            display_mult = str(mult)
            if aggregated_data['prefix_to_name_map'] and mult in aggregated_data['prefix_to_name_map']:
                clean_name = str(aggregated_data['prefix_to_name_map'][mult]).split(';')[0].strip()
                display_mult = f"{mult} ({clean_name})"
            max_mult_len = max(max_mult_len, len(display_mult))
        col_widths[first_col_header] = max_mult_len

        for call in all_calls:
            max_call_len = col_widths.get(call, len(call))
            if call in aggregated_data['band_data']:
                # data is now a Dict of Dicts
                data_dict = aggregated_data['band_data'][call]
                for mult in aggregated_data['missed_mults_on_band']:
                    if mult in data_dict:
                        stats = data_dict[mult]
                        qso_count = stats.get('QSO_Count', 0)
                        run_sp = stats.get('Run_SP_Status', '')
                        cell_content = f"({run_sp}) {qso_count}"
                        
                        max_call_len = max(max_call_len, len(cell_content))
            col_widths[call] = max_call_len
            
            union_count = len(aggregated_data['union_of_all_mults'])
            
            worked_count = len(aggregated_data['mult_sets'].get(call, []))
            max_worked = max(len(s) for s in aggregated_data['mult_sets'].values()) if aggregated_data['mult_sets'] else 0
            delta = worked_count - max_worked
            col_widths[call] = max(col_widths[call], len(str(worked_count)), len(str(union_count - worked_count)), len(str(delta)))

    def _create_table(self, header_list, width_dict, first_col_align='l'):
        """Helper function to create and configure a PrettyTable object."""
        table = PrettyTable()
        table.field_names = header_list
        table.align[header_list[0]] = first_col_align
        for header in header_list[1:]:
            table.align[header] = 'r'
            table.max_width[header] = width_dict[header]
            table.min_width[header] = width_dict[header]
        table.max_width[header_list[0]] = width_dict[header_list[0]]
        table.min_width[header_list[0]] = width_dict[header_list[0]]
        
        return table

    def _format_table_for_band(self, band, aggregated_data, all_calls, mult_rule, col_widths):
        """Pass 2 helper: Formats and returns the full table string for a single band."""
        if not aggregated_data or not aggregated_data['union_of_all_mults']:
            return f"     (No multipliers found for this scope)"

        raw_name = mult_rule['name']
        if raw_name.lower() in ['countries', 'prefixes']:
            first_col_header = raw_name
        else:
            first_col_header = raw_name[:-1] if raw_name.lower().endswith('s') else raw_name
        first_col_header = first_col_header.capitalize()
    
        headers = [first_col_header] + all_calls
        
        # --- Main Table Generation ---
        main_table = self._create_table(headers, col_widths)
        if aggregated_data['missed_mults_on_band']:
            for mult in aggregated_data['missed_mults_on_band']:
                display_mult = str(mult)
                if aggregated_data['prefix_to_name_map'] and mult in aggregated_data['prefix_to_name_map']:
                    clean_name = str(aggregated_data['prefix_to_name_map'][mult]).split(';')[0].strip()
                    display_mult = f"{mult} ({clean_name})"
                
                row = [display_mult]
                for call in all_calls:
                    cell_content = "0"
                    if call in aggregated_data['band_data']:
                        data_dict = aggregated_data['band_data'][call]
                        if mult in data_dict:
                            stats = data_dict[mult]
                            qso_count = stats.get('QSO_Count', 0)
                            run_sp = stats.get('Run_SP_Status', '')
                            cell_content = f"({run_sp}) {qso_count}"
                    
                    row.append(cell_content)
                
                main_table.add_row(row)
        
        # --- Summary Table Generation ---
        summary_table = self._create_table(headers, col_widths, first_col_align='r')
        total_counts = {call: len(aggregated_data['mult_sets'][call]) for call in all_calls}
        union_count = len(aggregated_data['union_of_all_mults'])
        max_mults = max(total_counts.values()) if total_counts else 0

        worked_row = ["Worked:"] + [str(total_counts.get(call, 0)) for call in all_calls]
        missed_row = ["Missed:"] + [str(union_count - total_counts.get(call, 0)) for call in all_calls]
        
        delta_vals = [total_counts.get(call, 0) - max_mults for call in all_calls]
        delta_row = ["Delta:"] + [str(d) if d != 0 else '' for d in delta_vals]
        summary_table.add_row(worked_row); summary_table.add_row(missed_row); summary_table.add_row(delta_row)
        
        # --- Stitch Tables ---
        if not aggregated_data['missed_mults_on_band']:
            return f"     (No missed {mult_rule['name']} for this scope)"
            
        main_lines = str(main_table).split('\n')
        summary_lines = str(summary_table).split('\n')
        return "\n".join(main_lines[:-1]) + "\n" + "\n".join(summary_lines[2:])

    def generate(self, output_path: str, **kwargs) -> str:
        """Generates the report content."""
        mult_name = kwargs.get('mult_name')
        mode_filter = kwargs.get('mode_filter')
        if not mult_name: return f"Error: 'mult_name' argument is required for '{self.report_name}' report."

        # --- Use Aggregator for Data Calculation ---
        aggregator = MultiplierStatsAggregator(self.logs)
        agg_results = aggregator.get_missed_data(mult_name, mode_filter)
        
        if 'error' in agg_results:
             return agg_results['error']
             
        all_calls = agg_results['all_calls']
        bands_to_process = agg_results['bands_to_process']
        mult_rule = agg_results['mult_rule']
        all_bands_data = agg_results['band_data']
        
        first_log = self.logs[0]
        first_log_def = first_log.contest_definition

        # --- PASS 1: Calculate column widths based on aggregated data ---
        raw_name = mult_rule['name']
        if raw_name.lower() in ['countries', 'prefixes']:
            first_col_header = raw_name
        else:
            first_col_header = raw_name[:-1] if raw_name.lower().endswith('s') else raw_name
        
        first_col_header = first_col_header.capitalize()
        col_widths = {call: len(call) for call in all_calls}
        summary_labels = ["Worked:", "Missed:", "Delta:"]
        col_widths[first_col_header] = max(len(first_col_header), max(len(label) for label in summary_labels))

        for band in bands_to_process:
            aggregated_data = all_bands_data[band]
            if aggregated_data['union_of_all_mults']:
                self._update_column_widths(col_widths, aggregated_data, all_calls, first_col_header)
        
        # --- PASS 2: Generate formatted report ---
        metadata = first_log.get_metadata()
        contest_name = metadata.get('ContestName', 'UnknownContest')
        first_qso_date = first_log.get_processed_data()['Date'].iloc[0] if not first_log.get_processed_data().empty else "----"
        year = first_qso_date.split('-')[0]
        
        dummy_table = self._create_table([first_col_header] + all_calls, col_widths)
        dummy_table.add_row(['' for _ in [first_col_header] + all_calls])
        max_line_width = len(str(dummy_table).split('\n')[0])
        
        # --- Standard Header ---
        modes_present = {mode_filter} if mode_filter else set() # Approximate, or pass empty to let utility handle None
        title_lines = get_standard_title_lines(f"{self.report_name}: {mult_name}", self.logs, agg_results['bands_to_process'][0] if len(bands_to_process)==1 else "All Bands", mode_filter, modes_present)
        meta_lines = ["Contest Log Analytics by KD4D", get_cty_metadata(self.logs)]
        
        report_lines = format_text_header(max_line_width, title_lines, meta_lines)

        for band in bands_to_process:
            band_header_text = f"\n{band.replace('M', '')} Meters Missed Multipliers" if band != "All Bands" else f"\nOverall Missed Multipliers"
            report_lines.append(band_header_text)
            table_string = self._format_table_for_band(band, all_bands_data[band], all_calls, mult_rule, col_widths)
            report_lines.append(table_string)

        report_content = "\n".join(report_lines) + "\n"
        os.makedirs(output_path, exist_ok=True)
        filename_calls = '_'.join([_sanitize_filename_part(c) for c in sorted(all_calls)])
        safe_mult_name = mult_name.lower().replace('/', '_')
        mode_suffix = f"_{mode_filter.lower()}" if mode_filter else ""
        filename = f"{self.report_id}_{safe_mult_name}{mode_suffix}_{filename_calls}.txt"
        filepath = os.path.join(output_path, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f: f.write(report_content)
        return f"Text report saved to: {filepath}"