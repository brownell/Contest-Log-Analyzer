# contest_tools/reports/text_rate_sheet_comparison.py
#
# Purpose: A text report that generates a comparative hourly rate sheet for two or more logs.
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
from ..data_aggregators.time_series import TimeSeriesAggregator
from contest_tools.utils.report_utils import _sanitize_filename_part, format_text_header, get_cty_metadata, get_standard_title_lines

class Report(ContestReport):
    """
    Generates a comparative hourly rate sheet for two or more logs.
    """
    report_id: str = "rate_sheet_comparison"
    report_name: str = "Comparative Rate Sheet"
    report_type: str = "text"
    supports_multi = True
    supports_pairwise = True
    
    def generate(self, output_path: str, **kwargs) -> str:
        """
        Generates the report content, saves it to a file, and returns a summary.
        """
        if len(self.logs) < 2:
            return "Error: The Comparative Rate Sheet report requires at least two logs."
        
        all_calls = sorted([log.get_metadata().get('MyCall', 'Unknown') for log in self.logs])
        first_log = self.logs[0]
        contest_def = first_log.contest_definition
        bands = contest_def.valid_bands
        is_single_band = len(bands) == 1
        
        # Data Aggregation
        # --- Phase 1 Performance Optimization: Use Cached Aggregator Data ---
        get_cached_ts_data = kwargs.get('_get_cached_ts_data')
        if get_cached_ts_data:
            # Use cached time series data (avoids recreating aggregator and recomputing)
            ts_data = get_cached_ts_data()
        else:
            # Fallback to old behavior for backward compatibility
            agg = TimeSeriesAggregator(self.logs)
            ts_data = agg.get_time_series_data()
        time_bins = ts_data['time_bins']
        
        # Determine available modes globally across all logs
        global_modes = set()
        for call in all_calls:
            entry = ts_data['logs'].get(call)
            if entry:
                global_modes.update(entry['hourly'].get('by_mode', {}).keys())
        available_modes = sorted(list(global_modes))
        if not available_modes: available_modes = ['QSO']

        report_blocks = []

        # --- BLOCK 1: Overall Summary ---
        # Columns: [Bands...] | [Total] | [Cumul]
        # (Dropping Mode columns in summary for Comparison to save horizontal space)
        
        col_defs = []
        if not is_single_band:
            for b in bands:
                col_defs.append({'key': f'band_{b}', 'header': b.replace('M',''), 'width': 6, 'type': 'band'})
        else:
            # Single band summary: Show Modes instead of "Band" column.
            # This effectively treats the Summary block as a Detailed block for single-band logs.
            for m in available_modes:
                col_defs.append({'key': f'mode_{m}', 'header': m, 'width': 5, 'type': 'mode'})

        # Let's stick to the drill-down: Overall (Band Summary) -> Details (Mode Summary).
        col_defs.append({'key': 'total', 'header': 'Total', 'width': 7, 'type': 'calc'})
        col_defs.append({'key': 'cumul', 'header': 'Cumul', 'width': 8, 'type': 'calc'})

        # --- Extract Metadata from DAL Scalars (Safe Access) ---
        first_call = all_calls[0]
        first_log_scalars = ts_data['logs'].get(first_call, {}).get('scalars', {})
        
        contest_name = first_log_scalars.get('contest_name', 'UnknownContest')
        year = first_log_scalars.get('year', '----')
        
        # Calculate modes present for smart scoping
        modes_present = set(available_modes)

        block1 = self._build_comparison_block(
            title="Overall Summary",
            col_defs=col_defs,
            time_bins=time_bins,
            ts_data=ts_data,
            all_calls=all_calls,
            force_band_context=None
        )
        report_blocks.append(block1)
        
        # --- Generate Standard Header ---
        # Measure width from the first block (separator line is index 3: Title, Blank, Header, Separator)
        block1_lines = block1.split('\n')
        table_width = len(block1_lines[3]) if len(block1_lines) > 3 else 80
        
        title_lines = get_standard_title_lines(self.report_name, self.logs, "All Bands", None, modes_present)
        meta_lines = ["Contest Log Analytics by KD4D", get_cty_metadata(self.logs)]
        
        header_block = format_text_header(table_width, title_lines, meta_lines)
        
        # Prepend header to blocks
        full_content = "\n".join(header_block) + "\n\n" + "\n\n".join(report_blocks) + "\n"

        # --- BLOCKS 2+: Band Details ---
        if not is_single_band:
            for band in bands:
                # Check if this band has ANY data across ANY log
                has_data = False
                for call in all_calls:
                    entry = ts_data['logs'].get(call)
                    if entry and sum(entry['hourly']['by_band'].get(band, [])) > 0:
                        has_data = True
                        break
                
                if not has_data: continue

                # Smart Suppression:
                # Calculate active modes on this band across all logs.
                # If only 1 mode is active (e.g. CW only), skip the detail block to reduce redundancy.
                active_modes_on_band = set()
                for call in all_calls:
                    entry = ts_data['logs'].get(call)
                    if entry:
                        # Keys in by_band_mode are formatted as "{BAND}_{MODE}" (e.g. "20M_CW")
                        for key in entry['hourly'].get('by_band_mode', {}).keys():
                            if key.startswith(f"{band}_"):
                                parts = key.split('_')
                                if len(parts) >= 2:
                                    active_modes_on_band.add(parts[1])
                
                if len(active_modes_on_band) <= 1:
                    continue

                # Detail Cols: [Modes...] | [Total] | [Cumul]
                detail_defs = []
                for m in available_modes:
                    detail_defs.append({'key': f'bm_{band}_{m}', 'header': m, 'width': 5, 'type': 'band_mode'})
                
                detail_defs.append({'key': 'total', 'header': 'Total', 'width': 7, 'type': 'calc'})
                detail_defs.append({'key': 'cumul', 'header': 'Cumul', 'width': 8, 'type': 'calc'})

                block_detail = self._build_comparison_block(
                    title=f"Detail: {band}",
                    col_defs=detail_defs,
                    time_bins=time_bins,
                    ts_data=ts_data,
                    all_calls=all_calls,
                    force_band_context=band
                )
                report_blocks.append(block_detail)

        # --- Output ---
        
        os.makedirs(output_path, exist_ok=True)
        filename_calls = '_'.join([_sanitize_filename_part(c) for c in sorted(all_calls)])
        filename = f"{self.report_id}_{filename_calls}.txt"
        filepath = os.path.join(output_path, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_content)
        
        return f"Text report saved to: {filepath}"

    def _build_comparison_block(self, title, col_defs, time_bins, ts_data, all_calls, force_band_context=None):
        lines = []
        
        # 1. Header Construction
        # Header Format:
        # Time   Call     [Cols...]
        
        prefix_width = 15 # "HHMM   Call   "
        
        header1_parts = [f"{'Hour':<5}", f"{'Call':<7}"]
        for col in col_defs:
            w = col['width']
            header1_parts.append(f"{col['header']:>{w}}")
            
        header1 = " ".join(header1_parts)
        table_width = len(header1)
        separator = "-" * table_width
        
        lines.append(title.center(table_width))
        lines.append("")
        lines.append(header1)
        lines.append(separator)
        
        # 2. State Tracking
        # Need cumulative totals per call
        cumul_trackers = {call: 0 for call in all_calls}
        grand_totals = {call: {col['key']: 0 for col in col_defs} for call in all_calls}

        # 3. Iterate Time
        for i, time_iso in enumerate(time_bins):
            hour_str = time_iso[11:13] + time_iso[14:16]
            
            # Check if this hour has data for ANY call (to skip empty rows)
            # This is slightly more complex in comparison mode.
            # We must pre-calculate row totals for all calls to decide visibility.
            hour_has_data = False
            row_data_cache = {} # Map call -> {col_key: val}
            row_totals_cache = {} # Map call -> total
            
            for call in all_calls:
                row_vals = {}
                row_total = 0
                entry = ts_data['logs'].get(call)
                
                if entry:
                    hourly = entry['hourly']
                    
                    for col in col_defs:
                        key = col['key']
                        ctype = col['type']
                        val = 0
                        
                        if ctype == 'band':
                            b = key.replace('band_', '')
                            data_list = hourly['by_band'].get(b, [])
                            val = data_list[i] if data_list else 0
                        elif ctype == 'mode':
                            lookup = key.replace('mode_', '')
                            data_list = hourly['by_mode'].get(lookup, [])
                            val = data_list[i] if data_list else 0
                        elif ctype == 'band_mode':
                            lookup = key.replace('bm_', '')
                            data_list = hourly['by_band_mode'].get(lookup, [])
                            val = data_list[i] if data_list else 0
                        
                        if ctype != 'calc':
                            row_vals[key] = val
                            # Add to calc
                            row_total += val
                    
                    # If force_band_context is NOT set (Summary), row_total is global hourly qsos
                    # to ensure we capture everything even if cols are restricted?
                    # Actually, if cols are restricted (bands), row_total sum is correct.
                    # Just stick to summing the displayed columns + hidden ones? 
                    # Simpler: Use Aggregator's pre-calculated totals if available?
                    # No, keep it consistent with displayed columns.
                    pass
                else:
                    # Missing log
                    pass
                
                row_data_cache[call] = row_vals
                row_totals_cache[call] = row_total
                if row_total > 0:
                    hour_has_data = True
            
            if not hour_has_data:
                continue
                
            # Print Rows (One per call)
            # Lines format: "HHMM  Call  ..."
            first_call_line = True
            for call in all_calls:
                t_str = hour_str if first_call_line else "     "
                # Let's repeat time for scannability or use " " 
                
                # Update Cumulative
                r_total = row_totals_cache[call]
                cumul_trackers[call] += r_total
                
                line_parts = [f"{t_str:<5}", f"{call:<7}"]
                
                for col in col_defs:
                    key = col['key']
                    w = col['width']
                    ctype = col['type']
                    
                    val = 0
                    if ctype == 'calc':
                        if key == 'total': val = r_total
                        elif key == 'cumul': val = cumul_trackers[call]
                    else:
                        val = row_data_cache[call].get(key, 0)
            
                    grand_totals[call][key] += val
                    if ctype == 'calc' and key == 'cumul':
                        grand_totals[call][key] = val # Keep latest
                        
                    line_parts.append(f"{val:>{w}}")
                    
                lines.append(" ".join(line_parts))

                first_call_line = False
            
            # Optional spacer between hours?
            # lines.append("") 

        lines.append(separator)
        
        # 4. Totals
        lines.append("TOTALS")
        for call in all_calls:
            line_parts = [f"{'':<5}", f"{call:<7}"]
            for col in col_defs:
                key = col['key']
                w = col['width']
                val = grand_totals[call][key]
                line_parts.append(f"{val:>{w}}")
            lines.append(" ".join(line_parts))

        return "\n".join(lines)