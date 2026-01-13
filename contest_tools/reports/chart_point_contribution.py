# contest_tools/reports/chart_point_contribution.py
#
# Purpose: A chart report that generates a breakdown of total points by QSO
#          point value, presented as a series of pie charts per band for a SINGLE log.
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
from typing import List, Dict
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from contest_tools.reports.report_interface import ContestReport
from contest_tools.contest_log import ContestLog
from contest_tools.data_aggregators.categorical_stats import CategoricalAggregator
from contest_tools.styles.plotly_style_manager import PlotlyStyleManager
from contest_tools.utils.report_utils import get_valid_dataframe, create_output_directory, get_cty_metadata, get_standard_title_lines

class Report(ContestReport):
    """
    Generates a series of pie charts showing the breakdown of QSO points
    (1-point, 3-point, etc.) for each band in a single log using Plotly.
    """
    report_id = 'chart_point_contribution_single'
    report_name = 'Point Contribution Breakdown (Single Log)'
    report_type = 'chart'
    supports_single = True

    def __init__(self, logs: List[ContestLog]):
        super().__init__(logs)
        self.aggregator = CategoricalAggregator()

    def generate(self, output_path: str, **kwargs) -> List[str]:
        # 1. Validation and Setup
        if not self.logs or get_valid_dataframe(self.logs[0]).empty:
            return []

        df = get_valid_dataframe(self.logs[0])
        bands = sorted(df['Band'].unique())

        if not bands:
            return []

        callsign = self.logs[0].get_metadata().get('MyCall', 'Unknown')

        # 2. Data Pre-Fetching & Title Generation
        # We need to fetch data first to generate dynamic titles for the subplots
        band_data_map = {}
        subplot_titles = []

        for band in bands:
            agg_result = self.aggregator.get_points_breakdown(self.logs, band_filter=band)
            # Single log report, extract first log result
            log_data = list(agg_result['logs'].values())[0]
            band_data_map[band] = log_data
            
            total_points = log_data['total_points']
            subplot_titles.append(f"{band} Band Points (Total: {total_points:.0f})")

        # 3. Layout Configuration
        num_bands = len(bands)
        cols = min(4, num_bands)
        rows = (num_bands + cols - 1) // cols

        # Dynamic Sizing: Calculate strict dimensions to prevent PNG overlap
        # Plotly default autosizing often fails for multi-row pie charts in static export
        PIXELS_PER_CHART = 400
        fig_width = cols * PIXELS_PER_CHART
        fig_height = rows * PIXELS_PER_CHART

        # Plotly requires 'domain' type for Pie charts
        specs = [[{'type': 'domain'} for _ in range(cols)] for _ in range(rows)]

        fig = make_subplots(
            rows=rows, 
            cols=cols, 
            subplot_titles=subplot_titles,
            specs=specs,
            vertical_spacing=0.1  # Increased spacing to clear titles
        )

        # 4. Trace Generation
        for i, band in enumerate(bands):
            row = (i // cols) + 1
            col = (i % cols) + 1
            
            log_data = band_data_map[band]
            point_breakdown = log_data['breakdown']

            if not point_breakdown:
                # Add an empty annotation if no data (though aggregation usually handles this)
                fig.add_annotation(
                    text="No Data", 
                    xref=f"x{i+1}", yref=f"y{i+1}",
                    showarrow=False,
                    row=row, col=col
                )
                continue

            # Sort by point value (descending frequency or value)
            # Logic: Sort by frequency descending for visual clarity
            sorted_items = sorted(point_breakdown.items(), key=lambda item: item[1], reverse=True)
            
            sizes = [item[1] for item in sorted_items]
            # Key is the point value (e.g., '1', '3')
            point_keys = [item[0] for item in sorted_items]
            labels = [f"{k} Point" for k in point_keys]

            # Consistent Coloring
            color_map = PlotlyStyleManager.get_point_color_map(point_keys)
            colors = [color_map[k] for k in point_keys]

            trace = go.Pie(
                labels=labels,
                values=sizes,
                marker=dict(colors=colors, line=dict(color='#000000', width=1)),
                textinfo='percent+label',
                hoverinfo='label+value+percent',
                name=f"{band} Band"
            )
            
            fig.add_trace(trace, row=row, col=col)

        # 5. Styling and Output
        modes_present = set(df['Mode'].dropna().unique())
        title_lines = get_standard_title_lines(self.report_name, self.logs, "All Bands", None, modes_present)
        final_title = f"{title_lines[0]}<br><sub>{title_lines[1]}<br>{title_lines[2]}</sub>"

        footer_text = f"Contest Log Analytics by KD4D\n{get_cty_metadata(self.logs)}"

        layout_config = PlotlyStyleManager.get_standard_layout(final_title, footer_text)
        
        # Merge dynamic size into standard layout
        layout_config.update({
            'width': fig_width, 
            'height': fig_height
        })
        
        fig.update_layout(layout_config)
        
        # Ensure titles don't overlap with pies
        fig.update_annotations(font_size=14, yshift=10)

        create_output_directory(output_path)
        
        base_filename = f"{self.report_id}_{callsign}"
        png_file = os.path.join(output_path, f"{base_filename}.png")
        html_file = os.path.join(output_path, f"{base_filename}.html")
        
        # Save Dual Outputs
        # PNG Generation disabled for Web Architecture
        # fig.write_image(png_file)
        
        config = {'toImageButtonOptions': {'filename': base_filename, 'format': 'png'}}
        fig.write_html(html_file, config=config)

        return [png_file, html_file]