# contest_tools/reports/plot_wrtc_propagation.py
#
# Purpose: A plot report that generates a visual prototype for one frame
#          of the proposed WRTC propagation animation.
#          It creates a side-by-side butterfly chart comparing two logs' hourly QSO data,
#          broken down by band, continent, and mode for a single, peak-activity hour.
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
from typing import List, Dict, Any, Optional
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.colors as pcolors

from ..contest_log import ContestLog
from .report_interface import ContestReport
from contest_tools.utils.report_utils import get_valid_dataframe, create_output_directory, save_debug_data, _sanitize_filename_part
from ..data_aggregators import propagation_aggregator

class Report(ContestReport):
    report_id: str = "wrtc_propagation"
    report_name: str = "WRTC Propagation by Continent"
    report_type: str = "plot"
    is_specialized = True
    supports_pairwise = True

    def generate(self, output_path: str, **kwargs) -> str:
        """
        Generates the report by finding the peak activity hour and creating
        a propagation chart for that hour using Plotly.
        """
        if len(self.logs) != 2:
            return f"Report '{self.report_name}' requires exactly two logs."
        log1, log2 = self.logs[0], self.logs[1]
        df1 = get_valid_dataframe(log1, include_dupes=False)
        df2 = get_valid_dataframe(log2, include_dupes=False)

        if df1.empty or df2.empty:
            return f"Skipping '{self.report_name}': At least one log has no valid QSO data."
        # --- Find the hour with the most combined activity ---
        combined_df = pd.concat([df1, df2])
        if combined_df.empty:
            return f"Skipping '{self.report_name}': No combined data."
        hourly_counts = combined_df.set_index('Datetime').resample('h').size()
        if hourly_counts.empty:
            return f"Skipping '{self.report_name}': No hourly data to process."
        peak_hour_timestamp = hourly_counts.idxmax()
        
        log_manager = getattr(log1, '_log_manager_ref', None)
        master_index = getattr(log_manager, 'master_time_index', None)
        if master_index is None:
            return "Error: Master time index not available. Cannot generate report."
        # Find the 1-based index of the peak hour
        try:
            peak_hour_index = master_index.get_loc(peak_hour_timestamp) + 1
        except KeyError:
            logging.warning(f"Peak hour {peak_hour_timestamp} not in master index. Defaulting to hour 1.")
            peak_hour_index = 1
            
        # --- Call the aggregator to get data for the peak hour ---
        propagation_data = propagation_aggregator.generate_propagation_data(self.logs, peak_hour_index)

        if not propagation_data:
            return f"Skipping '{self.report_name}': No data aggregated for the peak activity hour."
        # --- Save debug data ---
        if kwargs.get("debug_data", False):
            all_calls = sorted([log.get_metadata().get('MyCall') for log in self.logs])
            debug_filename = f"{self.report_id}_{'_vs_'.join(all_calls)}.txt"
            save_debug_data(True, output_path, propagation_data, custom_filename=debug_filename)
        
        # --- Generate the plot using Plotly ---
        result_msg = self._create_propagation_chart(propagation_data, peak_hour_index, len(master_index), output_path)
  
        return result_msg

    def _create_propagation_chart(self, propagation_data: Dict, hour_num: int, total_hours: int, output_path: str) -> str:
        """Generates and saves the side-by-side butterfly chart using Plotly."""
        
        # --- Extract data ---
        DATA = propagation_data.get('data', {})
        BANDS = propagation_data.get('bands', [])
        CONTINENTS = propagation_data.get('continents', [])
        MODES = propagation_data.get('modes', [])
        CALLS = propagation_data.get('calls', [])
        
        if not all([DATA, BANDS, CONTINENTS, MODES, CALLS]):
            logging.warning("Propagation data from aggregator is incomplete. Cannot generate plot.")
            return "Failed: Incomplete data."

        # Define Colors for Continents
        # Use Plotly's qualitative colors or mapped viridis
        # Mapping consistent colors to continents
        colors_list = pcolors.qualitative.Plotly
        CONTINENT_COLORS = {cont: colors_list[i % len(colors_list)] for i, cont in enumerate(CONTINENTS)}

        # --- Create Subplots (1 Row, 2 Cols: CW, PH) ---
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=["CW", "PH"],
            shared_yaxes=True,
            horizontal_spacing=0.05
        )

        bands_ordered = list(reversed(self.logs[0].contest_definition.valid_bands))

        # We plot horizontal bars. 
      
        # Log 1 = Positive (Right of axis in standard barh, but here we want butterfly).
        # Standard Butterfly: Log 1 goes Left (Neg?), Log 2 goes Right (Pos?) or vice versa.
        # Original script: Log 1 (Left Pos?), Log 2 (Left Neg?).
        # Let's align with previous report logic: 
        # Log 1 (Call1) -> Positive values
        # Log 2 (Call2) -> Negative values

        for col_idx, mode in enumerate(['CW', 'PH']):
            col = col_idx + 1 # 1-based index
            
            # If mode not present, we skip adding traces but keep subplot
            if mode not in MODES:
                
                continue

            for continent in CONTINENTS:
                # Log 1 Data (Positive)
                y_vals = []
                x_vals = []
                for band in bands_ordered:
          
                    count = DATA.get(CALLS[0], {}).get(mode, {}).get(band, {}).get(continent, 0)
                    y_vals.append(band)
                    x_vals.append(count)
                
                # Add Trace for Log 1
       
                fig.add_trace(go.Bar(
                    y=y_vals,
                    x=x_vals,
                    name=continent,
                    orientation='h',
           
                    marker_color=CONTINENT_COLORS.get(continent, 'grey'),
                    legendgroup=continent,
                    showlegend=(col == 1), # Only show legend once
                    hoverinfo='y+x+name',
                    customdata=[CALLS[0]] * len(x_vals),
 
                    hovertemplate='%{y}: %{x} QSOs (%{customdata}, %{layout.annotations[' + str(col_idx) + '].text})<br>Continent: ' + continent
                ), row=1, col=col)

                # Log 2 Data (Negative)
                y_vals_2 = []
              
                x_vals_2 = []
                for band in bands_ordered:
                    count = DATA.get(CALLS[1], {}).get(mode, {}).get(band, {}).get(continent, 0)
                    y_vals_2.append(band)
                    x_vals_2.append(-count) # Negate for butterfly effect
      
           
                # Add Trace for Log 2
                fig.add_trace(go.Bar(
                    y=y_vals_2,
                    x=x_vals_2,
             
                    name=continent,
                    orientation='h',
                    marker_color=CONTINENT_COLORS.get(continent, 'grey'),
                    legendgroup=continent,
                    showlegend=False,
            
                    hoverinfo='y+x+name',
                    customdata=[CALLS[1]] * len(x_vals_2),
                    # Show absolute value in hover
                    hovertemplate='%{y}: %{x} QSOs (%{customdata}, %{layout.annotations[' + str(col_idx) + '].text})<br>Continent: ' + continent
              
                ), row=1, col=col)

        # --- Layout ---
        metadata = self.logs[0].get_metadata()
        year = get_valid_dataframe(self.logs[0])['Date'].dropna().iloc[0].split('-')[0]
        contest_name = metadata.get('ContestName', '')
        event_id = metadata.get('EventID', '')
        
        title_text = (
            f"{self.report_name} (Hour {hour_num}/{total_hours})<br>"
           
            f"{year} {event_id} {contest_name} - {CALLS[0]} (Right/Pos) vs. {CALLS[1]} (Left/Neg)"
        )

        fig.update_layout(
            title_text=title_text,
            barmode='relative', # Stacks positive and negative
            height=800,
            width=1200,
            yaxis=dict(title="Band"),
          
            xaxis=dict(title="QSO Count"),
            xaxis2=dict(title="QSO Count"),
            legend=dict(title="Continents")
        )

        # Formatting X-axis to show absolute values (simple tickformat 's' removes minus signs often)
        fig.update_xaxes(tickformat='s') 

        # --- Save ---
        create_output_directory(output_path)
        filename_base = f"{self.report_id}_{_sanitize_filename_part(CALLS[0])}_vs_{_sanitize_filename_part(CALLS[1])}"
     
    
        generated_files = []
        
        # HTML
        html_file = f"{filename_base}.html"
        html_path = os.path.join(output_path, html_file)
        config = {'toImageButtonOptions': {'filename': filename_base, 'format': 'png'}}
        fig.write_html(html_path, config=config)
        generated_files.append(html_file)

        # PNG Generation disabled for Web Architecture (Phase 3)

        return f"Report generated: {', '.join(generated_files)}"