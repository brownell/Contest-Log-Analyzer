# contest_tools/reports/plot_cumulative_difference.py
#
# Purpose: A plot report that generates a cumulative difference graph,
#          comparing two logs, with superimposed lines for Total, Run, S&P, and Unknown.
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
# [Phase 1 (Layout & Data Fix)] - 2025-12-29
# - Converted Pandas Series to lists in Plotly traces to fix serialization bug.
# [Phase 1 (Pathfinder)] - 2025-12-29
# - Added JSON export functionality for web component integration.
# [0.145.0-Beta] - 2025-12-29
# - Removed manual layout overrides (margins) to allow PlotlyStyleManager authoritative control.
# [0.144.1-Beta] - 2025-12-29
# - Implemented "Hard Deck" strategy: Fixed height (800px), autosize=True, disabled 'responsive' config.
# [0.143.3-Beta] - 2025-12-28
# - Implemented "Safety Gap" strategy: Reduced HTML height to 800px to prevent scrollbars.
# [0.143.2-Beta] - 2025-12-28
# - Fixed HTML viewport issue by enforcing fixed height (850px).
# [0.143.1-Beta] - 2025-12-28
# - Updated layout configuration to use the "Legend Belt" strategy (Protocol 1.2.0).
# [0.143.0-Beta] - 2025-12-28
# - Updated to use PlotlyStyleManager Annotation Stack for title rendering.
# - Moved legend to top-left inside plot area to prevent overlap.
# - Restored truncated methods (_orchestrate_plot_generation, generate).
# [0.142.2-Beta] - 2025-12-28
# - Implemented Annotation Stack for precise title spacing control (Protocol 1.2.0).
# - Replaced Plotly standard title with manual layout annotations.
# [0.142.1-Beta] - 2025-12-28
# - Updated title formatting to use span tags with inline styles for better spacing control.
# - Relocated legend to top-left corner inside the plot area to prevent title overlap.
# [0.133.0-Beta] - 2025-12-20
# - Refactored `_generate_single_plot` to use centralized `build_filename` utility.
# - Standardized filename format to match other reports.
# [0.131.0-Beta] - 2025-12-20
# - Refactored to use `get_standard_title_lines` for standardized 3-line headers.
# - Implemented explicit "Smart Scoping" for title generation.
# - Added footer metadata via `get_cty_metadata`.
# [0.118.0-Beta] - 2025-12-15
# - Injected descriptive filename configuration for interactive HTML plot downloads.
# [0.115.0-Beta] - 2025-12-14
# - Consolidated 3-subplot layout into a single chart with superimposed lines
#   (Total, Run, S&P, Unknown) for better readability and vertical resolution.
# [0.114.0-Beta] - 2025-12-14
# - Updated HTML export to use responsive sizing (autosize=True) for dashboard integration.
# - Maintained fixed 1600x900 resolution for PNG exports.
# [0.113.0-Beta] - 2025-12-13
# - Standardized filename generation: removed '_vs_' separator to match Web Dashboard conventions.
# [1.1.2] - 2025-12-14
# - Updated file generation to use `_sanitize_filename_part` for strict lowercase naming.
# [1.1.1] - 2025-12-10
# - Fixed visualization bug: Increased top margin to prevent Main Title/Subplot Title overlap.
# [1.1.0] - 2025-12-10
# - Migrated visualization engine to Plotly (Dual Output: PNG + HTML).
# - Implemented PlotlyStyleManager for standardized styling.
# [1.0.0] - 2025-11-24
# - Refactored to use Data Abstraction Layer (TimeSeriesAggregator).
# - Enabled Run/S&P plots for Points metric via 'run_points' schema.
# [0.90.0-Beta] - 2025-10-01
# - Set new baseline version for release.
from typing import List
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import logging

from ..contest_log import ContestLog
from .report_interface import ContestReport
from contest_tools.utils.report_utils import create_output_directory, get_valid_dataframe, save_debug_data, _sanitize_filename_part, get_cty_metadata, get_standard_title_lines, build_filename
from ..data_aggregators.time_series import TimeSeriesAggregator
from ..styles.plotly_style_manager import PlotlyStyleManager

class Report(ContestReport):
    """
    Generates a single plot showing the cumulative difference in QSOs or Points
    between two logs, with superimposed lines for Total, Run, S&P, and Unknown.
    """
    report_id: str = "cumulative_difference_plots"
    report_name: str = "Cumulative Difference Plots"
    report_type: str = "plot"
    supports_pairwise = True
    
    def _generate_single_plot(self, output_path: str, band_filter: str, mode_filter: str, **kwargs):
        """
        Helper function to generate a single cumulative difference plot.
        Returns a list of generated file paths (PNG and HTML).
        """
        debug_data_flag = kwargs.get("debug_data", False)
        metric = kwargs.get('metric', 'qsos')
        log1, log2 = self.logs[0], self.logs[1]
        call1 = log1.get_metadata().get('MyCall', 'Log1')
        call2 = log2.get_metadata().get('MyCall', 'Log2')
        
        # --- Phase 1 Performance Optimization: Use Cached Aggregator Data ---
        get_cached_ts_data = kwargs.get('_get_cached_ts_data')
        if get_cached_ts_data:
            # Use cached time series data (avoids recreating aggregator and recomputing)
            ts_data = get_cached_ts_data(band_filter=band_filter, mode_filter=mode_filter)
        else:
            # Fallback to old behavior for backward compatibility
            agg = TimeSeriesAggregator([log1, log2])
            ts_data = agg.get_time_series_data(band_filter=band_filter, mode_filter=mode_filter)
        
        time_bins = [pd.Timestamp(t) for t in ts_data['time_bins']]

        # Helper to extract series
        def get_series(call_key, field):
            vals = ts_data['logs'][call_key]['cumulative'][field]
            return pd.Series(vals, index=time_bins)

        if metric == 'points':
            metric_name = log1.contest_definition.points_header_label or "Points"
            
            run1 = get_series(call1, 'run_points')
            sp1 = get_series(call1, 'sp_points')
            unk1 = get_series(call1, 'unknown_points')
            run2 = get_series(call2, 'run_points')
            sp2 = get_series(call2, 'sp_points')
            unk2 = get_series(call2, 'unknown_points')
            
            run_diff = run1 - run2
            sp_diff = sp1 - sp2
            unk_diff = unk1 - unk2
            overall_diff = (run1 + sp1 + unk1) - (run2 + sp2 + unk2)

            debug_df = pd.DataFrame({
                f'run_{call1}': run1, f'sp_{call1}': sp1, f'unk_{call1}': unk1,
                f'run_{call2}': run2, f'sp_{call2}': sp2, f'unk_{call2}': unk2,
                'run_diff': run_diff, 'sp_diff': sp_diff, 'unk_diff': unk_diff,
                'overall_diff': overall_diff
            })
            
        else: # metric == 'qsos'
            metric_name = "QSOs"
            
            run1 = get_series(call1, 'run_qsos')
            sp1 = get_series(call1, 'sp_qsos')
            unk1 = get_series(call1, 'unknown_qsos')
            run2 = get_series(call2, 'run_qsos')
            sp2 = get_series(call2, 'sp_qsos')
            unk2 = get_series(call2, 'unknown_qsos')
            
            run_diff = run1 - run2
            sp_diff = sp1 - sp2
            unk_diff = unk1 - unk2
            overall_diff = (run1 + sp1 + unk1) - (run2 + sp2 + unk2)
            
            debug_df = pd.DataFrame({
                f'run_{call1}': run1, f'sp_{call1}': sp1, f'unk_{call1}': unk1,
                f'run_{call2}': run2, f'sp_{call2}': sp2, f'unk_{call2}': unk2,
                'run_diff': run_diff, 'sp_diff': sp_diff, 'unk_diff': unk_diff,
                'overall_diff': overall_diff
            })
        
        # --- Plotting Preparation ---
        if overall_diff.abs().sum() == 0:
            logging.info(f"Skipping {band_filter} difference plot: no data available for this band.")
            return []

        # Get Standard Colors
        mode_colors = PlotlyStyleManager.get_qso_mode_colors()
        
        # Single Plot
        fig = go.Figure()

        # --- Trace 1: Overall Difference (Black) ---
        fig.add_trace(
            go.Scatter(
                x=overall_diff.index, y=overall_diff.tolist(),
                mode='lines+markers',
                name='Overall',
                line=dict(color='black', width=3),
                marker=dict(size=3)
            )
        )

        # --- Trace 2: Run Difference (Green) ---
        fig.add_trace(
            go.Scatter(
                x=run_diff.index, y=run_diff.tolist(),
                mode='lines+markers',
                name='Run',
                line=dict(color=mode_colors['Run'], width=2),
                marker=dict(size=3)
            )
        )

        # --- Trace 3: S&P Difference (Blue) ---
        fig.add_trace(
            go.Scatter(
                x=sp_diff.index, y=sp_diff.tolist(),
                mode='lines+markers',
                name='S&P',
                line=dict(color=mode_colors['S&P'], width=2),
                marker=dict(size=3)
            )
        )
        
        # --- Trace 4: Unknown Difference (Gray) ---
        fig.add_trace(
            go.Scatter(
                x=unk_diff.index, y=unk_diff.tolist(),
                mode='lines+markers',
                name='Unknown',
                line=dict(color=mode_colors['Mixed/Unk'], width=2, dash='dot'),
                marker=dict(size=3),
                visible='legendonly' if unk_diff.abs().sum() == 0 else True
            )
        )

        # --- Zero Reference Lines ---
        fig.add_hline(y=0, line_width=1, line_color="gray")

        # --- Metadata & Titles ---
        # Smart Scoping: Collect unique modes from all logs
        modes_present = set()
        for log in self.logs:
            df = get_valid_dataframe(log)
            if 'Mode' in df.columns:
                modes_present.update(df['Mode'].dropna().unique())
        
        title_lines = get_standard_title_lines(f"{self.report_name} ({metric_name})", self.logs, band_filter, mode_filter, modes_present)

        footer_text = f"Contest Log Analytics by KD4D\n{get_cty_metadata(self.logs)}"

        # --- Layout Standardization ---
        # Pass list directly to Manager for Annotation Stack generation
        layout = PlotlyStyleManager.get_standard_layout(title_lines, footer_text)
        
        fig.update_layout(layout)
        
        # Base layout properties common to both
        fig.update_layout(
            showlegend=True,
            xaxis_title="Contest Time",
            yaxis_title=f"Cumulative Diff ({metric_name})",
            # Legend Belt: Horizontal, Centered, Just above grid
            legend=dict(orientation="h", x=0.5, y=1.02, xanchor="center", yanchor="bottom", bgcolor="rgba(255,255,255,0.8)", bordercolor="Black", borderwidth=1)
        )

        # --- Saving Files (Dual Output) ---
        base_filename = build_filename(f"{self.report_id}_{metric}", self.logs, band_filter, mode_filter)
        
        # Debug Data
        debug_filename = f"{base_filename}.txt"
        save_debug_data(debug_data_flag, output_path, debug_df, custom_filename=debug_filename)
        
        create_output_directory(output_path)
        
        html_filename = f"{base_filename}.html"
        png_filename = f"{base_filename}.png"
        json_filename = f"{base_filename}.json"
        
        html_path = os.path.join(output_path, html_filename)
        png_path = os.path.join(output_path, png_filename)
        
        generated_files = []
        
        # Save HTML
        try:
            # Fixed Height with responsive width (Hard Deck Strategy)
            fig.update_layout(
                autosize=True,
                height=800
            )
            
            config = {'toImageButtonOptions': {'filename': base_filename, 'format': 'png'}}
            fig.write_html(html_path, include_plotlyjs='cdn', config=config)
            generated_files.append(html_path)
        
        except Exception as e:
            logging.error(f"Failed to save HTML report: {e}")

        # Save JSON (Web Component)
        json_path = os.path.join(output_path, json_filename)
        try:
            fig.write_json(json_path)
            generated_files.append(json_path)
        except Exception as e:
            logging.error(f"Failed to save JSON data: {e}")

        # Save PNG (Requires Kaleido)
        # Disabled for Web Architecture
        # try:
        #     # Fixed Layout for PNG
        #     fig.update_layout(
        #         autosize=False,
        #         width=1600,
        #         height=900
        #     )
        #     fig.write_image(png_path, width=1600, height=900)
        #     generated_files.append(png_path)
        # except Exception as e:
        #     logging.warning(f"Failed to generate static PNG (Kaleido missing?): {e}")

        return generated_files

    def _orchestrate_plot_generation(self, dfs: List[pd.DataFrame], output_path: str, mode_filter: str, **kwargs):
        """Helper to generate the full set of plots for a given data slice."""
        if any(df.empty for df in dfs):
            return []

        bands = self.logs[0].contest_definition.valid_bands
        is_single_band = len(bands) == 1
        bands_to_plot = ['All'] if is_single_band else ['All'] + bands
        
        created_files = []
        
        for band in bands_to_plot:
            try:
                save_path = output_path
                if not is_single_band and band != 'All':
                    if mode_filter:
                        save_path = os.path.join(output_path, mode_filter.lower(), band)
                    else:
                        save_path = os.path.join(output_path, band)
                
                new_files = self._generate_single_plot(
                    output_path=save_path,
                    band_filter=band,
                    mode_filter=mode_filter,
                    **kwargs
                )
                if new_files:
                    created_files.extend(new_files)
            except Exception as e:
                print(f"  - Failed to generate difference plot for {band} (Mode: {mode_filter or 'All'}): {e}")
        
        return created_files

    def generate(self, output_path: str, **kwargs) -> str:
        """
        Orchestrates the generation of all cumulative difference plots, including per-mode breakdowns.
        """
        if len(self.logs) != 2:
            return "Error: The Cumulative Difference Plot report requires exactly two logs."

        log1, log2 = self.logs[0], self.logs[1]
        df1_full = get_valid_dataframe(log1)
        df2_full = get_valid_dataframe(log2)

        if df1_full.empty or df2_full.empty:
            return "Skipping report: At least one log has no valid QSO data."

        all_created_files = []

        # 1. Generate plots for "All Modes"
        all_created_files.extend(
            self._orchestrate_plot_generation(dfs=[df1_full, df2_full], output_path=output_path, mode_filter=None, **kwargs)
        )

        # 2. Generate plots for each mode if applicable
        modes_present = pd.concat([df1_full['Mode'], df2_full['Mode']]).dropna().unique()
        if len(modes_present) > 1:
            for mode in ['CW', 'PH', 'DG']:
                if mode in modes_present:
                    sliced_dfs = [df[df['Mode'] == mode] for df in [df1_full, df2_full]]
                    
                    all_created_files.extend(
                        self._orchestrate_plot_generation(sliced_dfs, output_path, mode_filter=mode, **kwargs)
                    )
        
        if not all_created_files:
            return f"No difference plots were generated for metric '{kwargs.get('metric', 'qsos')}'."

        return f"Cumulative difference plots for {kwargs.get('metric', 'qsos')} saved to relevant subdirectories."