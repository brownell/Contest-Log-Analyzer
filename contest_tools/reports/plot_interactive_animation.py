# contest_tools/reports/plot_interactive_animation.py
#
# Purpose: Generates an interactive HTML animation dashboard.
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
import os
import logging
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import List, Dict, Any, Tuple
from pathlib import Path

from .report_interface import ContestReport
from contest_tools.utils.report_utils import create_output_directory, _sanitize_filename_part, get_cty_metadata, get_standard_title_lines, get_valid_dataframe
from ..data_aggregators.time_series import TimeSeriesAggregator
from ..data_aggregators.matrix_stats import MatrixAggregator
from ..styles.plotly_style_manager import PlotlyStyleManager

class Report(ContestReport):
    """
    Generates an interactive HTML animation dashboard.
    
    Layout:
    - Top (Row 1, Col 1-2): Racing Bar Chart (Cumulative Score/QSOs).
    - Bottom Left (Row 2, Col 1): Hourly QSO Rate (Grouped by Station, Stacked by Mode).
    - Bottom Right (Row 2, Col 2): Cumulative QSO Rate (Grouped by Station, Stacked by Mode).
    """
    
    report_id: str = "interactive_animation"
    report_name: str = "Interactive Contest Animation"
    report_type: str = "animation"
    is_specialized: bool = False
    supports_multi: bool = True
    supports_single: bool = True

    def _get_mode_color(self, base_hex: str, mode: str) -> str:
        """Calculates color based on mode: Run=Solid, S&P=50% Opacity, Unknown=Light Gray."""
        if mode == 'Unknown':
            return '#d3d3d3'  # Neutral Light Gray
        
        if mode == 'Run':
            return base_hex
            
        # S&P: Manual Hex to RGBA (No matplotlib dependency)
        hex_clean = base_hex.lstrip('#')
        if len(hex_clean) == 3:
            hex_clean = ''.join([c*2 for c in hex_clean])
            
        r = int(hex_clean[0:2], 16)
        g = int(hex_clean[2:4], 16)
        b = int(hex_clean[4:6], 16)
        return f"rgba({r},{g},{b},0.5)"

    def generate(self, output_path: str, **kwargs) -> str:
        """
        Generates the HTML animation.
        """
        create_output_directory(output_path)
        
        # 1. Prepare Data
        data = self._prepare_data(**kwargs)
        
        time_bins = data['time_bins']
        callsigns = data['callsigns']
        
        if not time_bins:
            return "No data available to generate animation."

        # 2. Setup Figure Layout
        fig = make_subplots(
            rows=2, cols=2,
            specs=[[{"colspan": 2}, None], [{}, {}]],
            subplot_titles=("Cumulative Score Progression", "Hourly Rate (By Band & Mode)", "Cumulative QSOs (By Band & Mode)"),
            vertical_spacing=0.15,
            horizontal_spacing=0.1
        )

        # 3. Initialize Base Traces (Frame 0)
        # We create empty traces that will be updated by frames
        
        # --- Pane 1: Racing Bars (Top) ---
        # Initialize with zeros
        fig.add_trace(
            go.Bar(
                x=[0] * len(callsigns),
                y=callsigns,
                orientation='h',
                name='Score',
                marker=dict(color=PlotlyStyleManager._COLOR_PALETTE[:len(callsigns)]),
                text=[0] * len(callsigns),
                textposition='auto',
                showlegend=False
            ),
            row=1, col=1
        )

        # --- Pane 2 & 3: Stacked/Grouped Bars (Bottom) ---
        # Logic: For each Station, we add 3 traces (Run, S&P, Unk) to EACH subplot.
        # They share the X-axis (Bands).
        # We use 'offsetgroup' to group by Call, but stack by Mode within that group.
        bands = data['bands']
        base_palette = PlotlyStyleManager._COLOR_PALETTE
        modes = ['Run', 'S&P', 'Unknown']
        
        for i, call in enumerate(callsigns):
            # Calculate offset to group bars side-by-side
            # This is handled automatically if we assign unique offsetgroups per call
            
            # Assign base color cyclically based on station index
            base_color = base_palette[i % len(base_palette)]
            
            for mode in modes:
                color = self._get_mode_color(base_color, mode)
                
                # Bottom Left: Hourly
                fig.add_trace(
                    go.Bar(
                        name=call,
                        x=bands,
                        y=[0] * len(bands),
                        marker_color=color,
                        legendgroup=call,
                        offsetgroup=call, # Group by Call
                        showlegend=(mode == 'Run'), # Only show legend once per call
                        textposition='none'
                    ),
                    row=2, col=1
                )
                
                # Bottom Right: Cumulative
                fig.add_trace(
                    go.Bar(
                        name=call,
                        x=bands,
                        y=[0] * len(bands),
                        marker_color=color,
                        legendgroup=call,
                        offsetgroup=call,
                        showlegend=False,
                        textposition='none'
                    ),
                    row=2, col=2
                )

        # --- Legend Decoder (Representative Keys) ---
        # Add dummy traces to explain the Color Intensity/Gray logic.
        # We use the first color in the palette (Blue) as the example.
        example_blue = base_palette[0]
        
        decoder_items = [
            ("Mode: Run", self._get_mode_color(example_blue, 'Run')),
            ("Mode: S&P", self._get_mode_color(example_blue, 'S&P')),
            ("Mode: Unknown", self._get_mode_color(example_blue, 'Unknown'))
        ]

        for label, color in decoder_items:
            fig.add_trace(
                go.Bar(
                    x=[None], y=[None],
                    name=label,
                    marker_color=color,
                    showlegend=True,
                ),
                row=1, col=1 # Assign to any subplot, it won't render data
            )

        # 4. Generate Frames
        frames = []
        for t_idx, t_label in enumerate(time_bins):
            frame_data = []
            
            # Update Pane 1: Racing Bars
            scores = [data['ts_data'][call]['score'][t_idx] for call in callsigns]
            # Plotly expects data in order of traces added
            frame_data.append(go.Bar(x=scores, text=scores))
            
            # Update Pane 2 & 3
            for call in callsigns:
                for mode in modes:
                    # Hourly Data
                    y_hourly = [data['matrix_hourly'][call][band][mode][t_idx] for band in bands]
                    frame_data.append(go.Bar(y=y_hourly))
                    
                    # Cumulative Data
                    y_cumul = [data['matrix_cumulative'][call][band][mode][t_idx] for band in bands]
                    frame_data.append(go.Bar(y=y_cumul))

            frames.append(go.Frame(data=frame_data, name=t_label))

        fig.frames = frames

        # 5. Configure Axes and Layout
        
        # Top Pane: Fixed Range based on Max Score
        max_score = max([max(data['ts_data'][c]['score']) for c in callsigns]) if callsigns else 10
        fig.update_xaxes(range=[0, max_score * 1.1], row=1, col=1)
        
        # Bottom Left: Max Hourly Rate
        max_hourly = data['max_stats']['hourly_qsos']
        fig.update_yaxes(title_text="QSOs / Hour", range=[0, max_hourly * 1.1], row=2, col=1)
        
        # Bottom Right: Max Cumulative
        max_cumul = data['max_stats']['cumulative_qsos']
        fig.update_yaxes(title_text="Total QSOs", range=[0, max_cumul * 1.1], row=2, col=2)
        
        # Common X-Axis properties
        fig.update_xaxes(title_text="Band", row=2, col=1)
        fig.update_xaxes(title_text="Band", row=2, col=2)

        # Construct Standard Title
        modes_present = set()
        for log in self.logs:
            df = get_valid_dataframe(log)
            if 'Mode' in df.columns:
                modes_present.update(df['Mode'].dropna().unique())
        
        title_lines = get_standard_title_lines(self.report_name, self.logs, "All Bands", None, modes_present)
        
        # For animation, we can add help text to the title
        final_title = f"{title_lines[0]}<br><sub>{title_lines[1]}<br>{title_lines[2]}</sub>"

        # Animation Settings
        fig.update_layout(
            template="plotly_white",
            height=900,
            # Initial placeholder title, will be updated below
            title_text=final_title,
            barmode='stack', # Enables stacking within offsetgroups
            updatemenus=[{
                "type": "buttons",
                "showactive": False,
                "x": 0.0,
                "y": -0.15,
                "xanchor": "left",
                "yanchor": "top",
                "buttons": [{
                    "label": "Play",
                    "method": "animate",
                    "args": [None, {"frame": {"duration": 1000, "redraw": True}, "fromcurrent": True}]
                }, {
                    "label": "Pause",
                    "method": "animate",
                    "args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}]
                }]
            }, {
                "type": "dropdown",
                "direction": "up",
                "showactive": True,
                "x": 0.15,
                "y": -0.15,
                "xanchor": "left",
                "yanchor": "top",
                "active": 1,
                "buttons": [
                    {"label": "FPS: 0.5", "method": "animate", "args": [None, {"frame": {"duration": 2000, "redraw": True}, "mode": "immediate", "transition": {"duration": 2000}}]},
                    {"label": "FPS: 1",   "method": "animate", "args": [None, {"frame": {"duration": 1000, "redraw": True}, "mode": "immediate", "transition": {"duration": 1000}}]},
                    {"label": "FPS: 2",   "method": "animate", "args": [None, {"frame": {"duration": 500, "redraw": True}, "mode": "immediate", "transition": {"duration": 500}}]},
                    {"label": "FPS: 5",   "method": "animate", "args": [None, {"frame": {"duration": 200, "redraw": True}, "mode": "immediate", "transition": {"duration": 200}}]}
                ]
            }],
            sliders=[{
                "currentvalue": {"prefix": "Time: "},
                "steps": [
                    {"args": [[f.name], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}],
                     "label": f.name[11:16], # Show HH:MM
                     "method": "animate"}
                    for f in frames
                ]
            }]
        )

        # Update Title with Standard Formatting and Footer
        footer_text = f"Contest Log Analytics by KD4D\n{get_cty_metadata(self.logs)}"
        
        # Merge with existing layout properties (since animation has complex layout)
        # We inject footer as annotation manually because we aren't using get_standard_layout here
        fig.update_layout(title_text=final_title)
        fig.add_annotation(
            x=0.5, y=-0.25, # Push footer way down below controls
            xref="paper", yref="paper",
            text=footer_text.replace('\n', '<br>'),
            showarrow=False,
            font=dict(size=12, color="#7f7f7f"),
            align="center",
            valign="top"
        )

        # 6. Save
        sanitized_calls = "_".join([_sanitize_filename_part(c) for c in callsigns])
        filename = f"interactive_animation_{sanitized_calls}.html"
        full_path = os.path.join(output_path, filename)
        
        # Config for Download Filename
        download_filename = f"contest_progress_{sanitized_calls}"
        config = {'toImageButtonOptions': {'filename': download_filename, 'format': 'png'}}
        
        fig.write_html(full_path, auto_play=False, config=config)
        logging.info(f"Generated interactive animation: {full_path}")

        return f"Interactive animation generated: {filename}"

    def _prepare_data(self, **kwargs) -> Dict[str, Any]:
        """
        Aggregates and aligns data from TimeSeries and Matrix aggregators.
        """
        # --- 1. Get Raw Data ---
        # Retrieve authoritative time index from the LogManager of the first log
        # (All logs share the same LogManager instance and time index)
        master_index = None
        if self.logs and hasattr(self.logs[0], '_log_manager_ref'):
            log_manager = self.logs[0]._log_manager_ref
            if log_manager:
                master_index = log_manager.master_time_index

        # --- Phase 1 Performance Optimization: Use Cached Aggregator Data ---
        get_cached_ts_data = kwargs.get('_get_cached_ts_data')
        get_cached_matrix_data = kwargs.get('_get_cached_matrix_data')
        
        if get_cached_ts_data:
            # Use cached time series data (avoids recreating aggregator and recomputing)
            ts_raw = get_cached_ts_data()
        else:
            # Fallback to old behavior for backward compatibility
            ts_agg = TimeSeriesAggregator(self.logs)
            ts_raw = ts_agg.get_time_series_data()
        
        get_cached_stacked_matrix_data = kwargs.get('_get_cached_stacked_matrix_data')
        if get_cached_stacked_matrix_data:
            # Use cached stacked matrix data (avoids recreating aggregator and recomputing)
            matrix_raw = get_cached_stacked_matrix_data(bin_size='60min', mode_filter=None, time_index=master_index)
        else:
            # Fallback to old behavior for backward compatibility
            matrix_agg = MatrixAggregator(self.logs)
            matrix_raw = matrix_agg.get_stacked_matrix_data(bin_size='60min', time_index=master_index)

        callsigns = sorted(list(ts_raw['logs'].keys()))
        time_bins = ts_raw['time_bins']
        bands = matrix_raw['bands']

        # --- 2. Process Time Series (Score) ---
        ts_data = {}
        for call in callsigns:
            log_entry = ts_raw['logs'][call]
            # Prefer Score, fallback to Points, then QSOs
            if any(log_entry['cumulative']['score']):
                metric = log_entry['cumulative']['score']
            elif any(log_entry['cumulative']['points']):
                metric = log_entry['cumulative']['points']
            else:
                metric = log_entry['cumulative']['qsos']
            ts_data[call] = {'score': metric}

        # --- 3. Process Matrix Data (Hourly & Cumulative) ---
        # Matrix Structure: logs -> call -> band -> mode -> [list of ints]
        matrix_hourly = {}
        matrix_cumulative = {}
        
        global_max_hourly = 0
        global_max_cumul = 0

        for call in callsigns:
            matrix_hourly[call] = {}
            matrix_cumulative[call] = {}
            
            # Temporary storage to sum per-band for global max calc
            hourly_sums_per_bin = np.zeros(len(time_bins))
            cumul_sums_per_bin = np.zeros(len(time_bins))

            for band in bands:
                matrix_hourly[call][band] = {}
                matrix_cumulative[call][band] = {}
                
                band_hourly_total = np.zeros(len(time_bins))
                band_cumul_total = np.zeros(len(time_bins))

                for mode in ['Run', 'S&P', 'Unknown']:
                    # Get hourly list (ensure alignment/length matching if necessary, 
                    # but aggregators should share master index logic)
                    
                    raw_list = matrix_raw['logs'][call].get(band, {}).get(mode, [0]*len(time_bins))
                    
                    # Convert to numpy for cumsum
                    arr_hourly = np.array(raw_list)
                    arr_cumul = np.cumsum(arr_hourly)
                    
                    matrix_hourly[call][band][mode] = arr_hourly.tolist()
                    matrix_cumulative[call][band][mode] = arr_cumul.tolist()
                    
                    # Update max trackers
                    band_hourly_total += arr_hourly
                    band_cumul_total += arr_cumul

                # Track global maxes (Stacked height per band)
                global_max_hourly = max(global_max_hourly, np.max(band_hourly_total))
                global_max_cumul = max(global_max_cumul, np.max(band_cumul_total))

        return {
            'time_bins': time_bins,
            'callsigns': callsigns,
            'bands': bands,
            'ts_data': ts_data,
            'matrix_hourly': matrix_hourly,
            'matrix_cumulative': matrix_cumulative,
            'max_stats': {
                'hourly_qsos': int(global_max_hourly),
                'cumulative_qsos': int(global_max_cumul)
            }
        }