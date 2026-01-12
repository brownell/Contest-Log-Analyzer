# contest_tools/reports/chart_comparative_activity_butterfly.py
#
# Purpose: Generates a comparative 'Butterfly' chart (stacked diverging bars)
#          visualizing Run vs S&P activity for two stations per band.
#
# Author: Gemini AI
# Date: 2026-01-06
# Version: 0.159.8-Beta
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
# [0.159.8-Beta] - 2026-01-06
# - Surgical Update: Added JSON artifact generation (fig.write_json) to support
#   web component rendering in dashboard.
# [0.159.7-Beta] - 2026-01-06
# - Surgical Update: Implemented N+1 Row "Header Row" Architecture for clean Legend/Title separation.
# - Refactored layout to use 'relative' barmode for correct stacking.
# - Updated Y-axis scaling to account for full stack height (Run+S&P+Unk).
# - Added dynamic row height calculation (Header=15%).
# [0.159.6-Beta] - 2026-01-06
# - Surgical Update: Removed manual footer offset and relocated legend to Top-Right (Legend Belt) to match standard layout.
# [0.159.5-Beta] - 2026-01-06
# - Refactored layout to "Top-Bottom Split" pattern: Footer shifted deep (-130), Legend moved to bottom center (-0.15).
# [0.159.4-Beta] - 2026-01-06
# - Updated footer to use standard dynamic metadata (CTY version).
# - Relocated legend to top-right (The Legend Belt) to prevent title overlap.
# [0.159.3-Beta] - 2026-01-06
# - Refactored layout application to strictly use PlotlyStyleManager for standardization.
# - Fixed layout bug where standard layout annotations were overwriting subplot titles (added safe injection loop).
# - Updated legend positioning to y=1.08 (centered) to prevent overlap with top subplot.
# - Enforced barmode='overlay' and bargap=0 for correct histogram-style visualization.
# [0.159.2-Beta] - 2026-01-05
# - Standardized filename generation: removed '_vs_' separator to match Web Dashboard conventions
#   and alignment with other comparative reports.
# [0.159.1-Beta] - 2026-01-05
# - Configured Plotly ModeBar 'Camera' button to download PNGs with descriptive filenames.
# [0.158.0-Beta] - 2026-01-05
# - Removed PNG generation (fig.write_image) to resolve Kaleido dependency issues in web container.
# [0.157.0-Beta] - 2026-01-04
# - Refactored to use Plotly for visualization, removing Matplotlib dependency.
# [0.151.1-Beta] - 2026-01-01
# - Repair import path for report_utils to fix circular dependency.
# [0.151.0-Beta] - 2026-01-01
# - Refactored imports to use `contest_tools.utils.report_utils` to break circular dependency.
# [1.0.2] - 2025-12-06
# - Fixed output directory pathing issue where charts were saved to a nested
#   'charts/charts' directory.
#   Now saves directly to the provided output_path.
# [1.0.1] - 2025-12-06
# - Updated color palette to Blue (S&P) / Green (Run) / Grey (Unknown) to match
#   standard breakdown charts.
# [1.0.0] - 2025-12-06
# - Initial creation implementing the Stacked Butterfly Chart.

import os
import logging
import math
from typing import List, Dict, Any, Optional
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..contest_log import ContestLog
from .report_interface import ContestReport
from ..data_aggregators.matrix_stats import MatrixAggregator
from contest_tools.utils.report_utils import create_output_directory, _sanitize_filename_part, get_cty_metadata, get_standard_title_lines, get_valid_dataframe
from ..styles.plotly_style_manager import PlotlyStyleManager

class Report(ContestReport):
    report_id = "chart_comparative_activity_butterfly"
    report_name = "Comparative Activity Butterfly Chart"
    report_type = "chart"
    supports_single = False
    supports_pairwise = True
    supports_multi = False

    def __init__(self, logs: List[ContestLog]):
        super().__init__(logs)
        
        # Load authoritative colors from StyleManager
        style_colors = PlotlyStyleManager.get_qso_mode_colors()
        self.COLORS = {
            'Run': style_colors.get('Run', '#2ca02c'),
            'S&P': style_colors.get('S&P', '#1f77b4'),
            'Unknown': style_colors.get('Mixed/Unk', '#7f7f7f')
        }

    def generate(self, output_path: str, **kwargs) -> str:
        if len(self.logs) != 2:
            return "Skipping: Butterfly chart requires exactly 2 logs."

        call1 = self.logs[0].get_metadata().get('MyCall', 'LOG1')
        call2 = self.logs[1].get_metadata().get('MyCall', 'LOG2')

        # 1. Fetch Data
        # --- Phase 1 Performance Optimization: Use Cached Aggregator Data ---
        get_cached_stacked_matrix_data = kwargs.get('_get_cached_stacked_matrix_data')
        if get_cached_stacked_matrix_data:
            # Use cached stacked matrix data (avoids recreating aggregator and recomputing)
            data = get_cached_stacked_matrix_data(bin_size='60min', mode_filter=None)
        else:
            # Fallback to old behavior for backward compatibility
            aggregator = MatrixAggregator(self.logs)
            data = aggregator.get_stacked_matrix_data(bin_size='60min')
        
        bands = data.get('bands', [])
        time_bins = data.get('time_bins', [])
        
        if not bands or not time_bins:
            return "No data available to plot."

        # 2. Setup Output
        charts_dir = output_path
        create_output_directory(charts_dir)

        # 3. Generate Plot
        try:
            filename_base = f"chart_comparative_activity_butterfly_{_sanitize_filename_part(call1)}_{_sanitize_filename_part(call2)}"
            
            # Create the figure
            fig = self._create_figure(data, time_bins, bands, call1, call2)
            
            generated_files = []

            # 1. Save JSON (Web Component Artifact)
            json_filename = f"{filename_base}.json"
            json_path = os.path.join(charts_dir, json_filename)
            fig.write_json(json_path)
            generated_files.append(json_filename)

            # Save HTML (Interactive)
            html_filename = f"{filename_base}.html"
            html_path = os.path.join(charts_dir, html_filename)
            config = {'toImageButtonOptions': {'filename': filename_base, 'format': 'png'}}
            fig.write_html(html_path, config=config)
            generated_files.append(html_filename)

            # PNG Generation disabled for Web Architecture (Phase 3)

            return f"Generated {len(generated_files)} butterfly chart(s) in {charts_dir}"

        except Exception as e:
            logging.error(f"Error generating butterfly chart: {e}")
            return f"Failed to generate butterfly chart: {e}"

    def _create_figure(self, data: Dict[str, Any], time_bins: List[Any], 
            bands: List[str], call1: str, call2: str) -> go.Figure:
        
        num_bands = len(bands)
        # [ARCHITECTURE] N+1 Rows: Row 1 = Header, Rows 2..N+1 = Charts
        total_rows = num_bands + 1
        
        # Calculate relative heights: Header=15%, Rest distributed evenly
        header_height = 0.15
        chart_height = (1.0 - header_height) / num_bands
        row_heights = [header_height] + [chart_height] * num_bands

        fig = make_subplots(
            rows=total_rows, 
            cols=1, 
            shared_xaxes=False,  # Don't share - we'll manually link band rows only
            vertical_spacing=0.02,
            row_heights=row_heights,
            subplot_titles=[""] + [f"Band: {b}" for b in bands]
        )

        # --- Row 1: Header & Legend Domain ---
        # Add invisible trace to establish grid
        fig.add_trace(go.Scatter(x=[None], y=[None], showlegend=False, hoverinfo='skip'), row=1, col=1)
        
        # Add Dummy Legend Traces (Order: Run, S&P, Unknown)
        for label in ['Run', 'S&P', 'Unknown']:
             color = self.COLORS[label]
             fig.add_trace(
                go.Bar(
                    x=[None], y=[None],
                    name=label,
                    marker_color=color,
                    showlegend=True,
                ),
                row=1, col=1
            )
        
        # Hide axes for Header Row
        fig.update_xaxes(visible=False, row=1, col=1)
        fig.update_yaxes(visible=False, row=1, col=1)

        # --- Rows 2..N+1: Charts ---
        for i, band in enumerate(bands):
            row_idx = i + 2
            
            # --- Log 1 (Positive) ---
            # Order: Run, S&P, Unknown
            l1_run = data['logs'][call1][band]['Run']
            l1_sp = data['logs'][call1][band]['S&P']
            l1_unk = data['logs'][call1][band]['Unknown']

            # Run
            fig.add_trace(go.Bar(
                x=time_bins, y=l1_run,
                name='Run', marker_color=self.COLORS['Run'],
                showlegend=False, hoverinfo='x+y+name'
            ), row=row_idx, col=1)

            # S&P
            fig.add_trace(go.Bar(
                x=time_bins, y=l1_sp,
                name='S&P', marker_color=self.COLORS['S&P'],
                showlegend=False, hoverinfo='x+y+name'
            ), row=row_idx, col=1)

            # Unknown
            fig.add_trace(go.Bar(
                x=time_bins, y=l1_unk,
                name='Unknown', marker_color=self.COLORS['Unknown'],
                showlegend=False, hoverinfo='x+y+name'
            ), row=row_idx, col=1)

            # --- Log 2 (Negative) ---
            # Negate values to stack downwards
            l2_run = [-v for v in data['logs'][call2][band]['Run']]
            l2_sp = [-v for v in data['logs'][call2][band]['S&P']]
            l2_unk = [-v for v in data['logs'][call2][band]['Unknown']]

            # Run
            fig.add_trace(go.Bar(
                x=time_bins, y=l2_run,
                name='Run', marker_color=self.COLORS['Run'],
                showlegend=False, hoverinfo='x+y+name',
                customdata=[abs(v) for v in l2_run],
                hovertemplate='%{x}<br>Run: %{customdata}'
            ), row=row_idx, col=1)

            # S&P
            fig.add_trace(go.Bar(
                x=time_bins, y=l2_sp,
                name='S&P', marker_color=self.COLORS['S&P'],
                showlegend=False, hoverinfo='x+y+name',
                customdata=[abs(v) for v in l2_sp],
                hovertemplate='%{x}<br>S&P: %{customdata}'
            ), row=row_idx, col=1)

            # Unknown
            fig.add_trace(go.Bar(
                x=time_bins, y=l2_unk,
                name='Unknown', marker_color=self.COLORS['Unknown'],
                showlegend=False, hoverinfo='x+y+name',
                customdata=[abs(v) for v in l2_unk],
                hovertemplate='%{x}<br>Unk: %{customdata}'
            ), row=row_idx, col=1)
             
            # Add zero line
            fig.add_hline(y=0, line_width=1, line_color="black", row=row_idx, col=1)
            
            # Formatting Y-Axis (Calculated from stacked sum)
            l1_total = [x+y+z for x,y,z in zip(l1_run, l1_sp, l1_unk)]
            l2_total = [abs(x)+abs(y)+abs(z) for x,y,z in zip(l2_run, l2_sp, l2_unk)]
            band_max = max(max(l1_total), max(l2_total)) if l1_total else 0
            rounded_limit = self._get_rounded_axis_limit(band_max)

            fig.update_yaxes(
                title_text=band,
                range=[-rounded_limit, rounded_limit],
                tickmode='array',
                tickvals=[-rounded_limit, -rounded_limit/2, 0, rounded_limit/2, rounded_limit],
                ticktext=[str(int(rounded_limit)), "", "0", "", str(int(rounded_limit))], # Simplified ticks
                row=row_idx, col=1
            )
            
            # X-Axis configuration
            if i == num_bands - 1:
                # Bottom chart: show labels and title
                # Increased standoff to 40px to prevent crowding with footer
                fig.update_xaxes(title_text="Time (UTC)", title_standoff=40, row=row_idx, col=1)
            else:
                # Other band charts: hide labels but link to bottom axis
                # This synchronizes all band rows (2-7) to share the same x-axis domain
                fig.update_xaxes(matches=f'x{total_rows}', showticklabels=False, row=row_idx, col=1)

        # Layout Updates
        # 3-Line Title Construction
        modes_present = set()
        for log in [self.logs[0], self.logs[1]]:
             df = get_valid_dataframe(log)
             if 'Mode' in df.columns:
                 modes_present.update(df['Mode'].dropna().unique())
        title_lines = get_standard_title_lines(self.report_name, self.logs, "All Bands", None, modes_present)
        
        footer_text = f"Contest Log Analytics by KD4D\n{get_cty_metadata(self.logs)}"
        
        fig.update_layout(
            template="plotly_white",
            barmode='relative', # Fix: Correct stacking for butterfly
            bargap=0, # Histogram look
            margin=dict(t=50, b=180, l=110, r=50), # Increased bottom margin for footer, left for y-axis spacing
            height=max(900, 200 * num_bands + 150),
            width=1200,
            # Legend in Header Row (Top Right)
            legend=dict(
                orientation="h",
                yanchor="top", y=1.0, 
                xanchor="right", x=1.0, 
                bgcolor="rgba(255,255,255,0.9)", 
                bordercolor="Black", borderwidth=1
            )
        )
        
        # Add Title Annotation (Row 1 Left)
        fig.add_annotation(
            text=f"<b>{title_lines[0]}</b><br><sup>{title_lines[1]}</sup>",
            xref="paper", yref="paper",
            x=0, y=1.0,
            xanchor="left", yanchor="top",
            showarrow=False,
            font=dict(size=20)
        )
        
        # Add Footer Annotation (Bottom Center) - Using absolute pixel positioning
        fig.add_annotation(
            text=footer_text.replace('\n', '<br>'),
            xref="paper", yref="paper",
            x=0.5, y=0,
            xanchor="center", yanchor="top",
            showarrow=False,
            font=dict(size=10, color="gray"),
            yshift=-80  # Push 80px below plot area (more space from "Time (UTC)")
        )

        return fig

    def _get_rounded_axis_limit(self, value: float) -> int:
        if value <= 0: return 10
        # Add 10% headroom
        target = value * 1.1
        # Round up to nearest 10
        return math.ceil(target / 10) * 10