# contest_tools/reports/text_multiplier_summary.py
#
# Purpose: A data-driven text report that generates a summary of QSOs for a
#          specific multiplier type (e.g., Countries, Zones).
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
import os
import json
import logging
import hashlib
from ..contest_log import ContestLog
from ..data_aggregators.multiplier_stats import MultiplierStatsAggregator
from .report_interface import ContestReport
from contest_tools.utils.report_utils import format_text_header, get_cty_metadata, get_standard_title_lines, _sanitize_filename_part

class Report(ContestReport):
    """
    Generates a summary of QSOs per multiplier, broken down by band.
    """
    report_id: str = "multiplier_summary"
    report_name: str = "Multiplier Summary"
    report_type: str = "text"
    supports_single = True
    supports_multi = True
    supports_pairwise = True
    
    def generate(self, output_path: str, **kwargs) -> str:
        """
        Generates the report content.
        """
        mult_name = kwargs.get('mult_name')
        mode_filter = kwargs.get('mode_filter')
        
        # --- Use Aggregator for Data Calculation ---
        aggregator = MultiplierStatsAggregator(self.logs)
        result = aggregator.get_summary_data(mult_name, mode_filter)
        
        if 'error' in result:
            return result['error']
            
        pivot = result['pivot']
        all_calls = result['all_calls']
        mult_column = result['mult_column']
        mult_rule = result['mult_rule']
        combined_df = result['combined_df']
        main_df = result['main_df']
        
        contest_def = self.logs[0].contest_definition
        name_column = mult_rule.get('name_column')

        # Check if pivot data exists (handling dict structure)
        # pivot is dict: {'index': [], 'columns': [], 'data': []}
        if not pivot.get('data') and not combined_df:
             mode_str = f" on mode '{mode_filter}'" if mode_filter else ""
             return f"Report '{self.report_name}' for '{mult_name}'{mode_str} skipped as no data was found."
        
        bands = contest_def.valid_bands
        is_single_band = len(bands) == 1
        is_comparative = len(all_calls) > 1

        # --- Reconstruct Data Lookup from JSON 'split' format ---
        pivot_columns = pivot.get('columns', [])
        pivot_index = pivot.get('index', [])
        pivot_data = pivot.get('data', [])
        
        # Map band names to column indices within the data rows
        band_col_map = {b: i for i, b in enumerate(pivot_columns)}
        
        # Create a lookup: key -> row_data
        data_map = {}
        unique_mults = set()
        
        for idx, row_vals in zip(pivot_index, pivot_data):
            # JSON serializes tuples as lists. Convert back for consistent dictionary keys.
            key = tuple(idx) if isinstance(idx, list) else idx
            data_map[key] = row_vals
            
            # Extract distinct multipliers from index
            if is_comparative:
                unique_mults.add(key[0]) # key is (mult, call)
            else:
                unique_mults.add(key)    # key is mult

        sorted_mults = sorted(list(unique_mults))
        
        # --- Header Preparation ---
        modes_present = {mode_filter} if mode_filter else set()
        if not modes_present:
             # Try to derive from logs if not explicit
             for log in self.logs:
                 df = log.get_processed_data()
                 if 'Mode' in df.columns:
                     modes_present.update(df['Mode'].dropna().unique())

        title_lines = get_standard_title_lines(f"{self.report_name}: {mult_name}", self.logs, "All Bands", mode_filter, modes_present)
        meta_lines = ["Contest Log Analytics by KD4D", get_cty_metadata(self.logs)]
        
        report_lines = []

        # --- Gracefully handle cases with no multipliers ---
        if not pivot_data:
            # Default width for empty report
            header_block = format_text_header(80, title_lines, meta_lines)
            report_lines.extend(header_block)
            report_lines.append(f"\n\nNo '{mult_name}' multipliers found to summarize.")
            # --- Save the clean (but empty) report and exit ---
            report_content = "\n".join(report_lines) + "\n"
            os.makedirs(output_path, exist_ok=True)
            filename_calls = '_'.join([_sanitize_filename_part(c) for c in sorted(all_calls)])
            
            mode_suffix = f"_{mode_filter.lower()}" if mode_filter else ""
            filename = f"{self.report_id}_{mult_name.lower().replace('/', '_')}{mode_suffix}_{filename_calls}.txt"
            filepath = os.path.join(output_path, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)
            return f"Text report saved to: {filepath}"
        
        # Name map logic (list based)
        name_map = {}
        if name_column:
             # Simple iteration to build map from list of dicts
             for record in main_df:
                 if record.get(mult_column) and record.get(name_column):
                     name_map[record[mult_column]] = record[name_column]

        # Determine column header
        if mult_name.lower() == 'countries':
            source_type = mult_rule.get('source', 'dxcc').upper()
            first_col_header = source_type
        elif mult_name.lower() == 'prefixes':
            first_col_header = mult_name
        else:
            first_col_header = mult_name[:-1] if mult_name.lower().endswith('s') else mult_name
        
        # Calculate column widths
        max_mult_len = len(first_col_header)
        if sorted_mults:
            for mult in sorted_mults:
                if name_column:
                    full_name = name_map.get(mult, '')
                    display_string = f"{mult} ({full_name})" if full_name else str(mult)
                    max_mult_len = max(max_mult_len, len(display_string))
                else:
                    max_mult_len = max(max_mult_len, len(str(mult)))
        
        max_call_len = 0
        if len(all_calls) > 1:
            max_call_len = max(len(f"  {call}: ") for call in all_calls)

        first_col_width = max(max_mult_len, max_call_len)
        
        header_parts = [f"{b.replace('M',''):>7}" for b in bands]
        if not is_single_band:
            header_parts.append(f"{'Total':>7}")
        table_header = f"{first_col_header:<{first_col_width}}" + "".join(header_parts)
        table_width = len(table_header)
        separator = "-" * table_width
        
        # Generate standard header
        header_block = format_text_header(table_width, title_lines, meta_lines)
        report_lines.extend(header_block)
        report_lines.append("")

        report_lines.append(table_header)
        report_lines.append(separator)

        # Calculate Column Totals (per call) for the footer
        col_totals = {call: {b: 0 for b in bands} for call in all_calls}

        for mult in sorted_mults:
            mult_display = str(mult)
            if name_column:
                mult_full_name = name_map.get(mult, '')
                if mult_full_name: 
                    clean_name = str(mult_full_name).split(';')[0].strip()
                    mult_display = f"{mult} ({clean_name})"

            if not is_comparative:
                # --- Single Log: Render on one line ---
                line = f"{mult_display:<{first_col_width}}"
                call = all_calls[0]
                lookup_key = mult
                row_values = data_map.get(lookup_key, [])
                
                row_total = 0
                for band in bands:
                    val = 0
                    if row_values and band in band_col_map:
                        col_idx = band_col_map[band]
                        val = int(row_values[col_idx])
                    line += f"{val:>7}"
                    row_total += val
                    col_totals[call][band] += val
                
                if not is_single_band:
                    line += f"{row_total:>7}"
                report_lines.append(line)
                
            else:
                # --- Comparative: Render Header + Indented Rows ---
                report_lines.append(f"{mult_display:<{first_col_width}}")
                
                for call in all_calls:
                    lookup_key = (mult, call)
                    # Check if this call/mult combo exists
                    if lookup_key not in data_map:
                        continue
                    
                    row_values = data_map.get(lookup_key, [])
                    row_total = 0
                    line = f"  {call}:".ljust(first_col_width)
                    
                    for band in bands:
                        val = 0
                        if row_values and band in band_col_map:
                            col_idx = band_col_map[band]
                            val = int(row_values[col_idx])
                        
                        line += f"{val:>7}"
                        row_total += val
                        col_totals[call][band] += val 
        
                    if not is_single_band:
                        line += f"{row_total:>7}"
                    report_lines.append(line)

        report_lines.append(separator)
        
        # --- Render Footer ---
        if not is_comparative:
             line = f"{'Total':<{first_col_width}}"
             call = all_calls[0]
             grand_total = 0
             for band in bands:
                val = col_totals[call][band]
                line += f"{val:>7}"
                grand_total += val
             if not is_single_band:
                 line += f"{grand_total:>7}"
             report_lines.append(line)
        else:
            report_lines.append(f"{'Total':<{first_col_width}}")
            for call in all_calls:
                line = f"  {call}:".ljust(first_col_width)
                grand_total = 0
                for band in bands:
                    val = col_totals[call][band]
                    line += f"{val:>7}"
                    grand_total += val
                
                if not is_single_band:
                    line += f"{grand_total:>7}"
                report_lines.append(line)

        # --- Diagnostic Section for "Unknown" Multipliers ---
        unknown_records = [r['Call'] for r in combined_df if r.get(mult_column) == 'Unknown']
        unique_unknown_calls = sorted(list(set(unknown_records)))
        
        if unique_unknown_calls:
            report_lines.append("\n" + "-" * 30)
            report_lines.append(f"Callsigns with unknown {first_col_header}:")
            report_lines.append("-" * 30)
            
            col_width = 12
            num_cols = max(1, table_width // (col_width + 2))
            
            for i in range(0, len(unique_unknown_calls), num_cols):
                line_calls = unique_unknown_calls[i:i+5]
                report_lines.append("  ".join([f"{call:<{col_width}}" for call in line_calls]))

        report_content = "\n".join(report_lines) + "\n"
        
        os.makedirs(output_path, exist_ok=True)
        
        filename_calls = '_'.join([_sanitize_filename_part(c) for c in sorted(all_calls)])
        mode_suffix = f"_{mode_filter.lower()}" if mode_filter else ""
        filename = f"{self.report_id}_{mult_name.lower().replace('/', '_')}{mode_suffix}_{filename_calls}.txt"
        filepath = os.path.join(output_path, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return f"Text report saved to: {filepath}"