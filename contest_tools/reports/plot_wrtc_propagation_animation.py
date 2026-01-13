# contest_tools/reports/plot_wrtc_propagation_animation.py
#
# Purpose: A plot report that generates an animation of the WRTC propagation
#          analysis, creating a side-by-side butterfly chart for each hour of
#          the contest.
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

import os
import logging
from typing import List, Dict, Any
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.colors as pcolors

from ..contest_log import ContestLog
from .report_interface import ContestReport
from contest_tools.utils.report_utils import get_valid_dataframe, create_output_directory, save_debug_data, _sanitize_filename_part
from ..data_aggregators import propagation_aggregator

class Report(ContestReport):
    report_id: str = "wrtc_propagation_animation"
    report_name: str = "WRTC Propagation Animation"
    report_type: str = "animation" # Logic changed: Now produces HTML animation
    is_specialized = True
    supports_pairwise = True

    def generate(self, output_path: str, **kwargs) -> str:
        """
     
        Generates the animation by creating a Plotly figure with frames for each hour.
        """
        if len(self.logs) != 2:
            return f"Report '{self.report_name}' requires exactly two logs."
        log1, log2 = self.logs[0], self.logs[1]

        log_manager = getattr(log1, '_log_manager_ref', None)
        master_index = getattr(log_manager, 'master_time_index', None)
        if master_index is None:
            return "Error: Master time index not available. Cannot generate animation."
        # Fetch calls for filenames
        calls = [log.get_metadata().get('MyCall') for log in self.logs]
        
        # --- Prepare Plotly Animation ---
        # We need:
        # 1. Base Figure (Layout)
        # 2. Frames (Data for each hour)
        
        frames = []
       
        max_qso_count = 10 # Default fallback for axis scaling
        
        # Pre-fetch continent colors to keep them consistent
        # We'll need the union of all continents seen?
        # Or just use a standard map.
        # We'll use a fixed color map based on a standard list to ensure consistency across frames.
        STANDARD_CONTINENTS = ['NA', 'EU', 'AS', 'SA', 'AF', 'OC', 'AN']
        colors_list = pcolors.qualitative.Plotly
        CONTINENT_COLORS = {cont: colors_list[i % len(colors_list)] for i, cont in enumerate(STANDARD_CONTINENTS)}

        bands_ordered = list(reversed(self.logs[0].contest_definition.valid_bands))
        
        # Iterate through hours to build frames
        logging.info(f"Generating animation frames for {len(master_index)} hours...")
        
        for i, timestamp in enumerate(master_index):
            hour_index = i + 1
            prop_data = propagation_aggregator.generate_propagation_data(self.logs, hour_index)
            
            if not prop_data:
                # Create empty frame
                frames.append(go.Frame(data=[], name=str(i)))
      
                continue

            # Extract data
            DATA = prop_data.get('data', {})
            # BANDS, MODES, CALLS should be consistent, but good to be safe
            MODES = ['CW', 'PH'] # Enforce standard order
            
       
            # Build Traces for this Frame
            # We need 4 sets of bars: CW-Log1, CW-Log2, PH-Log1, PH-Log2
            # Plotly animations work best when trace indices match.
            # We'll initialize the figure with all continent traces existing but empty, 
            # and update them in frames.
            # Actually, simplest is to just rebuild the traces for the frame.
            frame_traces = []
            
            for col_idx, mode in enumerate(MODES):
                col = col_idx + 1
                
                # We need to iterate continents in a fixed order to maintain trace stability?
                # Plotly Frames replace data in existing traces.
                # To make this robust, we should probably group by Continent trace?
                # Actually, simpler approach for "Butterfly":
                # For each Mode, we have One Trace per Continent per Log?
                # Or just stack them? 
                # Let's stick to the "Two Traces per Mode per Continent" pattern used in the static plot.
                for continent in STANDARD_CONTINENTS:
                    # Log 1 (Positive)
                    y_vals = bands_ordered
                    x_vals_1 = []
                    for band in bands_ordered:
       
                        val = DATA.get(calls[0], {}).get(mode, {}).get(band, {}).get(continent, 0)
                        x_vals_1.append(val)
                        if val > max_qso_count: max_qso_count = val # Auto-scale tracking

                    
                    frame_traces.append(go.Bar(
                        x=x_vals_1, y=y_vals,
                        orientation='h',
                        name=continent,
                        marker_color=CONTINENT_COLORS.get(continent, 'grey'),
  
                        legendgroup=continent,
                        showlegend=(i==0 and col==1), # Only show legend on first frame? No, base layout handles legend.
                        xaxis=f'x{col}', yaxis=f'y{col}' 
              
                    ))

                    # Log 2 (Negative)
                    x_vals_2 = []
                    for band in bands_ordered:
                        val = DATA.get(calls[1], {}).get(mode, {}).get(band, {}).get(continent, 0)
                        x_vals_2.append(-val)
                        if val > max_qso_count: max_qso_count = val

                    frame_traces.append(go.Bar(
                      
                        x=x_vals_2, y=y_vals,
                        orientation='h',
                        name=continent,
                        marker_color=CONTINENT_COLORS.get(continent, 'grey'),
                        
                        legendgroup=continent,
                        showlegend=False,
                        xaxis=f'x{col}', yaxis=f'y{col}'
                    ))
            
            frames.append(go.Frame(data=frame_traces, name=str(i)))

      
        # --- Build Base Figure ---
        # We need to initialize the figure with the data from the FIRST frame (or empty structures)
        # to set up the grid.
        fig = make_subplots(rows=1, cols=2, subplot_titles=["CW", "PH"], shared_yaxes=True, horizontal_spacing=0.05)
        
        # Add initial traces (empty or from frame 0)
        # We need to ensure the number of traces matches what's in the frames.
        # We added (2 modes * 7 continents * 2 logs) = 28 traces per frame.
        # So we must initialize 28 traces.
        
        for col_idx, mode in enumerate(MODES):
            col = col_idx + 1
            for continent in STANDARD_CONTINENTS:
                # Trace 1: Log 1
                fig.add_trace(go.Bar(
                    x=[0]*len(bands_ordered), y=bands_ordered, 
                    orientation='h',
                    name=continent, marker_color=CONTINENT_COLORS.get(continent, 'grey'),
                    legendgroup=continent, showlegend=(col==1)
                ), row=1, col=col)
                # Trace 2: Log 2
                fig.add_trace(go.Bar(
   
                    x=[0]*len(bands_ordered), y=bands_ordered, orientation='h',
                    name=continent, marker_color=CONTINENT_COLORS.get(continent, 'grey'),
                    legendgroup=continent, showlegend=False
                ), row=1, col=col)

        # --- Layout & Animation Controls ---
      
        # Round up max count for axis range
        axis_limit = (max_qso_count // 10 + 1) * 10
        
        fig.update_layout(
            title_text=f"WRTC Propagation Animation: {calls[0]} vs {calls[1]}",
            barmode='relative',
            height=800,
            xaxis=dict(range=[-axis_limit, axis_limit], title="QSOs"),
    
            xaxis2=dict(range=[-axis_limit, axis_limit], title="QSOs"),
            updatemenus=[dict(
                type="buttons",
                buttons=[
                    dict(label="Play",
                         method="animate",
 
                         args=[None, dict(frame=dict(duration=500, redraw=True), fromcurrent=True)]),
                    dict(label="Pause",
                         method="animate",
                         args=[[None], dict(frame=dict(duration=0, redraw=False), 
                        mode="immediate", transition=dict(duration=0))])
                ]
            )],
            sliders=[dict(
                steps=[dict(method='animate', 
                            args=[[str(k)], dict(mode='immediate', frame=dict(duration=500, redraw=True), transition=dict(duration=0))],
          
                            label=f"{k+1}h") for k in range(len(master_index))], 
                currentvalue=dict(prefix='Hour: ')
            )]
        )
        
        fig.frames = frames

        # --- Save Output ---
        create_output_directory(output_path)
        filename_base = f"{self.report_id}_{_sanitize_filename_part(calls[0])}_vs_{_sanitize_filename_part(calls[1])}"
        filename = f"{filename_base}.html"
        filepath = os.path.join(output_path, filename)
        
        try:
            config = {'toImageButtonOptions': {'filename': filename_base, 'format': 'png'}}
            fig.write_html(filepath, auto_play=False, config=config)
            return f"Animation saved to: {filepath}"
        except Exception as e:
            logging.error(f"Failed to save animation: {e}")
         
        return f"Error generating animation for report '{self.report_name}'."