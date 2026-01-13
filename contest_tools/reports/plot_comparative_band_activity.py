# contest_tools/reports/plot_comparative_band_activity.py
#
# Purpose: A plot report that generates a comparative "butterfly" chart to
#          visualize the band activity of two logs side-by-side using Plotly.
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
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import logging
import math
from typing import List, Dict, Any

from ..contest_log import ContestLog
from .report_interface import ContestReport
from contest_tools.utils.report_utils import get_valid_dataframe, create_output_directory, _sanitize_filename_part, get_cty_metadata, get_standard_title_lines, build_filename
from ..data_aggregators.matrix_stats import MatrixAggregator
from ..styles.plotly_style_manager import PlotlyStyleManager

class Report(ContestReport):
    """
    Generates a comparative "butterfly" chart of band activity for two logs.
    """
    report_id: str = "comparative_band_activity"
    report_name: str = "Comparative Band Activity"
    report_type: str = "plot"
    supports_pairwise = True

    def _get_rounded_axis_limit(self, max_value: float) -> int:
        """Takes a raw maximum value and returns a sensible upper limit."""
        if max_value == 0: return 5
        if max_value <= 45:
            return int(math.ceil(max_value / 5.0)) * 5
        if max_value <= 50: return 50
        if max_value <= 60: return 60
        if max_value <= 75: return 75
        if max_value <= 80: return 80
        if max_value <= 90: return 90
        if max_value <= 100: return 100
        # For larger values, round up to the nearest 25
        return (int(max_value / 25) + 1) * 25

    def _generate_plot_for_slice(self, matrix_data: Dict, log1: ContestLog, log2: ContestLog, output_path: str, mode_filter: str, **kwargs) -> str:
        """Helper function to generate a single plot (PNG+HTML) for a given data slice (DAL-based)."""
        call1 = log1.get_metadata().get('MyCall', 'Log1')
        call2 = log2.get_metadata().get('MyCall', 'Log2')

        # --- 1. Data Preparation (Unpack DAL) ---
        time_bins_str = matrix_data['time_bins']
        all_bands = matrix_data['bands']
        
        if not time_bins_str or not all_bands:
            return f"Skipping {mode_filter or 'combined'} plot: No data in slice."

        time_bins = pd.to_datetime(time_bins_str)
        
        # Convert List[List] to DataFrame for convenient plotting logic
        pivot_dfs = {}
        for call in [call1, call2]:
            qso_grid = matrix_data['logs'][call]['qso_counts']
            # Multiply by 4 to get rate/hr (since data is 15min)
            df_grid = pd.DataFrame(qso_grid, index=all_bands, columns=time_bins) * 4
            pivot_dfs[call] = df_grid

        # --- 2. Visualization Setup ---
        num_bands = len(all_bands)
        # Dynamic height calculation
        plot_height = max(900, 200 * num_bands)
        
        # Create Subplots
        fig = make_subplots(
            rows=num_bands, 
            cols=1, 
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=[f"Band: {b}" for b in all_bands]
        )

        # --- 3. Add Traces ---
        # Log 1 Color: Blue (Palette[0]), Log 2 Color: Red (Palette[3])
        color_log1 = PlotlyStyleManager._COLOR_PALETTE[0]
        color_log2 = PlotlyStyleManager._COLOR_PALETTE[3]

        for i, band in enumerate(all_bands):
            row_idx = i + 1
            
            data1 = pivot_dfs[call1].loc[band]
            data2 = -pivot_dfs[call2].loc[band] # Negative for butterfly effect
            
            band_max_rate = max(data1.max(), data2.abs().max())
            rounded_limit = self._get_rounded_axis_limit(band_max_rate)

            # Trace 1: Log 1 (Positive)
            fig.add_trace(
                go.Bar(
                    x=time_bins,
                    y=data1,
                    name=f"{call1} ({band})",
                    marker_color=color_log1,
                    showlegend=(i == 0), # Only show legend once
                    hovertemplate=f"<b>{call1}</b><br>Time: %{{x}}<br>Rate: %{{y}} /hr<extra></extra>"
                ),
                row=row_idx, col=1
            )

            # Trace 2: Log 2 (Negative, but displayed as absolute in hover)
            fig.add_trace(
                go.Bar(
                    x=time_bins,
                    y=data2,
                    name=f"{call2} ({band})",
                    marker_color=color_log2,
                    showlegend=(i == 0),
                    customdata=data2.abs(), # Pass absolute value for hover
                    hovertemplate=f"<b>{call2}</b><br>Time: %{{x}}<br>Rate: %{{customdata}} /hr<extra></extra>"
                ),
                row=row_idx, col=1
            )

            # Add Zero Line
            fig.add_hline(y=0, line_width=1, line_color="black", row=row_idx, col=1)

            # Formatting Y-Axis
            fig.update_yaxes(
                title_text=band,
                range=[-rounded_limit, rounded_limit],
                tickmode='array',
                tickvals=[-rounded_limit, -rounded_limit/2, 0, rounded_limit/2, rounded_limit],
                ticktext=[str(int(rounded_limit)), str(int(rounded_limit/2)), "0", str(int(rounded_limit/2)), str(int(rounded_limit))],
                row=row_idx, col=1
            )

        # --- 4. Layout & Styling ---
        # Prepare Titles
        modes_present = set()
        for log in [log1, log2]:
            df = get_valid_dataframe(log)
            if 'Mode' in df.columns:
                modes_present.update(df['Mode'].dropna().unique())
        
        title_lines = get_standard_title_lines(self.report_name, [log1, log2], "All Bands", mode_filter, modes_present)
        final_title = f"{title_lines[0]}<br><sub>{title_lines[1]}<br>{title_lines[2]}</sub>"

        footer_text = f"Contest Log Analytics by KD4D\n{get_cty_metadata([log1, log2])}"

        layout_config = PlotlyStyleManager.get_standard_layout(final_title, footer_text)
        fig.update_layout(layout_config)
        
        fig.update_layout(
            margin=dict(t=150), # Increased top margin for 2-line title
            barmode='overlay', # Fix: Force bars to align on centerline
            bargap=0, # Histogram look
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        fig.update_xaxes(title_text="Contest Time (UTC)", row=num_bands, col=1)

        # --- 5. Save Files ---
        filename_base = build_filename(self.report_id, [log1, log2], "All Bands", mode_filter)
        
        filepath_png = os.path.join(output_path, f"{filename_base}.png")
        filepath_html = os.path.join(output_path, f"{filename_base}.html")
        
        results = []
        try:
            # Fixed sizing for PNG (Disabled for Web Architecture)
            # fig.update_layout(
            #     autosize=False,
            #     height=plot_height,
            #     width=1600
            # )
            # Save PNG
            # fig.write_image(filepath_png)
            # results.append(f"Plot saved: {filepath_png}")
            
            # Responsive sizing for HTML
            fig.update_layout(
                autosize=True,
                height=None,
                width=None
            )
            # Save HTML
            config = {'toImageButtonOptions': {'filename': filename_base, 'format': 'png'}}
            fig.write_html(filepath_html, include_plotlyjs='cdn', config=config)
            results.append(f"Interactive plot saved: {filepath_html}")
            
            return "\n".join(results)
        except Exception as e:
            logging.error(f"Error saving butterfly chart for {mode_filter or 'All Modes'}: {e}")
            return f"Error generating report for {mode_filter or 'All Modes'}"

    def generate(self, output_path: str, **kwargs) -> str:
        """Orchestrates the generation of the combined plot and per-mode plots."""
        if len(self.logs) != 2:
            return f"Error: Report '{self.report_name}' requires exactly two logs."
        log1, log2 = self.logs[0], self.logs[1]
        created_files = []

        # --- 1. Generate the main "All Modes" plot ---
        # --- Phase 1 Performance Optimization: Use Cached Aggregator Data ---
        get_cached_matrix_data = kwargs.get('_get_cached_matrix_data')
        if get_cached_matrix_data:
            # Use cached matrix data (avoids recreating aggregator and recomputing)
            matrix_data_all = get_cached_matrix_data(bin_size='15min', mode_filter=None)
        else:
            # Fallback to old behavior for backward compatibility
            aggregator = MatrixAggregator(self.logs)
            matrix_data_all = aggregator.get_matrix_data(bin_size='15min', mode_filter=None)
        
        msg = self._generate_plot_for_slice(matrix_data_all, log1, log2, output_path, mode_filter=None, **kwargs)
        created_files.append(msg)
        
        # --- 2. Generate per-mode plots ---
        # Check modes present in raw data to determine if we need loops
        df1 = get_valid_dataframe(log1, include_dupes=False)
        df2 = get_valid_dataframe(log2, include_dupes=False)
        modes_present = pd.concat([df1['Mode'], df2['Mode']]).dropna().unique()

        modes_to_plot = ['CW', 'PH', 'DG']

        if len(modes_present) > 1:
            for mode in modes_to_plot:
                if mode in modes_present:
                    # Fetch specific DAL slice
                    if get_cached_matrix_data:
                        matrix_data_mode = get_cached_matrix_data(bin_size='15min', mode_filter=mode)
                    else:
                        matrix_data_mode = aggregator.get_matrix_data(bin_size='15min', mode_filter=mode)
                    
                    msg = self._generate_plot_for_slice(matrix_data_mode, log1, log2, output_path, mode_filter=mode, **kwargs)
                    created_files.append(msg)

        return "\n".join(created_files)