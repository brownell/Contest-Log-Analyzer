# contest_tools/reports/plot_comparative_run_sp.py
#
# Purpose: A plot report that generates a "paired timeline" chart, visualizing
#          the operating style (Run, S&P, or Mixed) of two operators over time.
#
# Author: Gemini AI
# Date: 2026-01-05
# Version: 0.159.0-Beta
#
# Copyright (c) 2025 Mark Bailey, KD4D
# Contact: kd4d@kd4d.org
#
# License: Mozilla Public License, v. 2.0
#          (https://www.mozilla.org/MPL/2.0/)
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0.
# If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# --- Revision History ---
# [0.159.0-Beta] - 2026-01-05
# - Disabled PNG generation logic (Kaleido dependency removal) for Web Architecture.
# [0.151.1-Beta] - 2026-01-01
# - Repair import path for report_utils to fix circular dependency.
# [0.151.0-Beta] - 2026-01-01
# - Refactored imports to use `contest_tools.utils.report_utils` to break circular dependency.
# [1.3.1-Beta] - 2025-12-20
# - Refactored to use `get_standard_title_lines` for standardized 3-line headers.
# - Implemented explicit "Smart Scoping" for title generation.
# - Added footer metadata via `get_cty_metadata`.
# [1.3.0] - 2025-12-15
# - Injected descriptive filename configuration for interactive HTML plot downloads.
# [1.2.0] - 2025-12-10
# - Added CLI entry point (argparse) for standalone execution.
# - Updated documentation to reflect CLI usage.
# [1.1.1] - 2025-12-10
# - Fixed Legend Visibility Bug: Replaced opacity=0 hack with empty-data traces to ensure
#   legend markers remain visible.
# [1.1.0] - 2025-12-10
# - Migrated visualization engine from Matplotlib to Plotly (Phase 2).
# - Implemented Discrete Heatmap strategy for timeline visualization.
# - Added HTML export capability.
# [1.0.0] - 2025-11-24
# - Refactored to use MatrixAggregator (DAL).
# [0.90.0-Beta] - 2025-10-01
# - Set new baseline version for release.
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import math
import argparse
import sys
from typing import List, Dict, Any

from ..contest_log import ContestLog
from .report_interface import ContestReport
from contest_tools.utils.report_utils import get_valid_dataframe, create_output_directory, save_debug_data, get_cty_metadata, get_standard_title_lines
from ..data_aggregators.matrix_stats import MatrixAggregator
from ..styles.plotly_style_manager import PlotlyStyleManager

class Report(ContestReport):
    """
    Generates a "paired timeline" chart to visualize Run/S&P activity.
    """
    report_id: str = "comparative_run_sp_timeline"
    report_name: str = "Comparative Activity Timeline (Run/S&P)"
    report_type: str = "plot"
    supports_pairwise = True

    def _generate_plot_for_page(self, matrix_data: Dict, log1_meta: Dict, log2_meta: Dict, bands_on_page: List[str], output_path: str, page_title_suffix: str, page_file_suffix: str, mode_filter: str, **kwargs):
        """Helper to generate a single plot page using Matrix Data."""
        call1 = log1_meta.get('MyCall', 'Log1')
        call2 = log2_meta.get('MyCall', 'Log2')
        debug_data_flag = kwargs.get("debug_data", False)
        
        # Unpack Matrix Data
        time_bins_str = matrix_data['time_bins']
        time_bins = pd.to_datetime(time_bins_str)
        all_bands = matrix_data['bands']
        
        # --- Map Styles to Integers for Heatmap ---
        # 0=Inactive (NaN), 1=Run, 2=S&P, 3=Mixed
        STYLE_MAP = {'Run': 1, 'S&P': 2, 'Mixed': 3, 'Inactive': np.nan}
        
        # Get standard colors
        mode_colors = PlotlyStyleManager.get_qso_mode_colors()
        
        # Colors:
        c_run = mode_colors['Run']
        c_sp = mode_colors['S&P']
        c_mix = mode_colors['Mixed/Unk']
        
        # Discrete scale for values 1, 2, 3
        # We define a hard-edged colorscale for the heatmap
        colorscale = [
            [0.0, c_run],   [0.33, c_run],   # 1 maps here (conceptually)
            [0.33, c_sp],   [0.66, c_sp],    # 2 maps here
            [0.66, c_mix],  [1.0, c_mix]     # 3 maps here
        ]

        # --- Create Subplots ---
        # One row per band
        fig = make_subplots(
            rows=len(bands_on_page),
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=[f"Band: {b}" for b in bands_on_page]
        )

        plot_data_for_debug = {}

        for i, band in enumerate(bands_on_page):
            row_idx = i + 1
            plot_data_for_debug[band] = {call1: {}, call2: {}}

            # --- Prepare Data Vectors ---
            # Retrieve pre-calculated grid from Aggregator
            try:
                band_idx = all_bands.index(band)
                row1_raw = matrix_data['logs'][call1]['activity_status'][band_idx]
                row2_raw = matrix_data['logs'][call2]['activity_status'][band_idx]
            except (ValueError, KeyError):
                row1_raw = ['Inactive'] * len(time_bins)
                row2_raw = ['Inactive'] * len(time_bins)

            # Convert to integers for Heatmap
            row1_ints = [STYLE_MAP.get(x, np.nan) for x in row1_raw]
            row2_ints = [STYLE_MAP.get(x, np.nan) for x in row2_raw]

            # Construct Z Matrix
            # Row 0 (Bottom) = Log2 (call2)
            # Row 1 (Top)    = Log1 (call1)
            z_matrix = [row2_ints, row1_ints]

            # Collect Debug Data
            for j, ts in enumerate(time_bins):
                ts_iso = ts.isoformat()
                if row1_raw[j] != 'Inactive':
                    plot_data_for_debug[band][call1][ts_iso] = row1_raw[j]
                if row2_raw[j] != 'Inactive':
                    plot_data_for_debug[band][call2][ts_iso] = row2_raw[j]

            # --- Add Heatmap Trace ---
            fig.add_trace(
                go.Heatmap(
                    x=time_bins,
                    y=[call2, call1], # y[0] matches z[0] (Log2)
                    z=z_matrix,
                    colorscale=colorscale,
                    zmin=0.5, # Ensure 1 falls in first bin
                    zmax=3.5, # Ensure 3 falls in last bin
                    showscale=False,
                    xgap=0,
                    ygap=2, # Visual separation between operator lanes
                    hoverongaps=False,
                    hovertemplate="%{y}<br>%{x}<br>Status: %{text}<extra></extra>",
                    text=[[row2_raw, row1_raw]] # Hover text needs to match Z structure (list of lists)
                ),
                row=row_idx, col=1
            )
            
            # Note: fig.data[-1].text assignment above might be interpreted as a single list if not careful.
            # Heatmap text argument expects a 2D array if z is 2D.
            # Passing list of lists directly in constructor usually works.
            # --- Y-Axis Correction ---
            # Force the Y-axis to display the callsigns as categories, not numbers
            fig.update_yaxes(type='category', categoryorder='array', categoryarray=[call2, call1], row=row_idx, col=1)

        # --- Add Dummy Traces for Legend ---
        # Strategy: Add traces with no data (None) so they appear in legend but not on plot.
        # This avoids the opacity=0 issue where the legend icon also becomes invisible.
        for label, color, val in [('Run', c_run, 1), ('S&P', c_sp, 2), ('Mixed', c_mix, 3)]:
            fig.add_trace(
                go.Scatter(
                    x=[None], 
                    y=[None],
                    mode='markers',
                    marker=dict(size=10, color=color, symbol='square'),
                    name=label,
                    showlegend=True
                ),
                row=1, col=1
            )

        # --- Formatting ---
        modes_present = set()
        for log in self.logs:
            df = get_valid_dataframe(log)
            if 'Mode' in df.columns:
                modes_present.update(df['Mode'].dropna().unique())
        
        title_lines = get_standard_title_lines(f"{self.report_name}{page_title_suffix}", self.logs, "All Bands", mode_filter, modes_present)
        final_title = f"{title_lines[0]}<br><sub>{title_lines[1]}<br>{title_lines[2]}</sub>"

        footer_text = f"Contest Log Analytics by KD4D\n{get_cty_metadata(self.logs)}"
        
        # Apply standard layout
        layout_cfg = PlotlyStyleManager.get_standard_layout(final_title, footer_text)
        
        # Customize for this specific report
        fig.update_layout(layout_cfg)
        
        fig.update_layout(
            height=max(600, 200 * len(bands_on_page)),
            width=1600,
            margin=dict(t=140), # ADR-008 Override
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        # --- Save Files ---
        mode_filename_str = f"_{mode_filter.lower()}" if mode_filter else ""
        base_filename = f"{self.report_id}{mode_filename_str}_{call1}_vs_{call2}{page_file_suffix}"
        
        html_path = os.path.join(output_path, f"{base_filename}.html")
        png_path = os.path.join(output_path, f"{base_filename}.png")
        
        debug_filename = f"{base_filename}.json"
        save_debug_data(debug_data_flag, output_path, plot_data_for_debug, custom_filename=debug_filename)
        
        config = {'toImageButtonOptions': {'filename': base_filename, 'format': 'png'}}
        fig.write_html(html_path, config=config)
        # PNG Generation disabled for Web Architecture
        # fig.write_image(png_path)
        
        return html_path # Return HTML as primary interactive artifact

    def generate(self, output_path: str, **kwargs) -> str:
        """Orchestrates the generation of the combined plot and per-mode plots."""
        if len(self.logs) != 2:
            return f"Error: Report '{self.report_name}' requires exactly two logs."
        BANDS_PER_PAGE = 8
        log1, log2 = self.logs[0], self.logs[1]
        created_files = []

        # --- Phase 1 Performance Optimization: Use Cached Aggregator Data ---
        get_cached_matrix_data = kwargs.get('_get_cached_matrix_data')
        if get_cached_matrix_data:
            # Use cached matrix data (avoids recreating aggregator and recomputing)
            aggregator = None  # Not needed when using cache
        else:
            # Fallback to old behavior for backward compatibility
            aggregator = MatrixAggregator(self.logs)

        # --- 1. Generate the main "All Modes" plot ---
        if get_cached_matrix_data:
            matrix_data_all = get_cached_matrix_data(bin_size='15min', mode_filter=None)
        else:
            matrix_data_all = aggregator.get_matrix_data(bin_size='15min', mode_filter=None)
        
        filepath = self._run_plot_for_slice(matrix_data_all, log1, log2, output_path, BANDS_PER_PAGE, mode_filter=None, **kwargs)
        if filepath:
            created_files.append(filepath)
            created_files.append(filepath.replace('.html', '.png'))
        
        # --- 2. Generate per-mode plots if necessary ---
        df1 = get_valid_dataframe(log1, include_dupes=False)
        df2 = get_valid_dataframe(log2, include_dupes=False)
        modes_present = pd.concat([df1['Mode'], df2['Mode']]).dropna().unique()

        if len(modes_present) > 1:
            for mode in ['CW', 'PH', 'DG']:
                if mode in modes_present:
                    if get_cached_matrix_data:
                        matrix_data_mode = get_cached_matrix_data(bin_size='15min', mode_filter=mode)
                    else:
                        matrix_data_mode = aggregator.get_matrix_data(bin_size='15min', mode_filter=mode)
                    
                    filepath = self._run_plot_for_slice(matrix_data_mode, log1, log2, output_path, BANDS_PER_PAGE, mode_filter=mode, **kwargs)
                    if filepath:
                        created_files.append(filepath)
                        created_files.append(filepath.replace('.html', '.png'))

        if not created_files:
            return f"Report '{self.report_name}' did not generate any files."
        return f"Report file(s) saved to:\n" + "\n".join([f"  - {fp}" for fp in created_files])

    def _run_plot_for_slice(self, matrix_data, log1, log2, output_path, bands_per_page, mode_filter, **kwargs):
        """Helper to run the paginated plot generation for a specific data slice (DAL-based)."""
        all_bands = matrix_data['bands']
        active_bands = []
        
        call1 = log1.get_metadata().get('MyCall', 'Log1')
        call2 = log2.get_metadata().get('MyCall', 'Log2')

        for i, band in enumerate(all_bands):
            row1 = matrix_data['logs'][call1]['qso_counts'][i]
            row2 = matrix_data['logs'][call2]['qso_counts'][i]
            # Check sum of QSOs to determine activity
            if sum(row1) > 0 or sum(row2) > 0:
                active_bands.append(band)

        if not active_bands:
            return None

        num_pages = math.ceil(len(active_bands) / bands_per_page)
        
        for page_num in range(num_pages):
            start_index = page_num * bands_per_page
            end_index = start_index + bands_per_page
            bands_on_page = active_bands[start_index:end_index]
            
            page_title_suffix = f" (Page {page_num + 1}/{num_pages})" if num_pages > 1 else ""
            page_file_suffix = f"_Page_{page_num + 1}_of_{num_pages}" if num_pages > 1 else ""
            
            return self._generate_plot_for_page(
                matrix_data=matrix_data,
                log1_meta=log1.get_metadata(),
                log2_meta=log2.get_metadata(),
                bands_on_page=bands_on_page,
                output_path=output_path,
                page_title_suffix=page_title_suffix,
                page_file_suffix=page_file_suffix.replace('/', '_'),
                mode_filter=mode_filter,
                **kwargs
            )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Comparative Run/S&P Timeline (Standalone)")
    parser.add_argument("--input", nargs='+', required=True, help="Path to input log files (Requires exactly 2 logs for comparison)")
    parser.add_argument("--output", required=True, help="Directory to save the output report files")
    parser.add_argument("--debug", action="store_true", help="Enable debug data export")

    args = parser.parse_args()

    # Validate input count for comparative report
    if len(args.input) != 2:
        print("Error: Comparative report requires exactly two input log files.", file=sys.stderr)
        sys.exit(1)

    # Ensure output directory exists
    if not os.path.exists(args.output):
        try:
            os.makedirs(args.output)
        except OSError as e:
            print(f"Error creating output directory: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        # Load Logs
        logs = [ContestLog(f) for f in args.input]
        
        # Instantiate and Run Report
        report = Report(logs)
        result = report.generate(output_path=args.output, debug_data=args.debug)
        
        print(result)

    except Exception as e:
        print(f"Execution Error: {e}", file=sys.stderr)
        sys.exit(1)