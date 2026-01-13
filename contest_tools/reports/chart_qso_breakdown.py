# contest_tools/reports/chart_qso_breakdown.py
#
# Purpose: A chart report that generates a stacked bar chart comparing two logs
#          on common/unique QSOs broken down by Run vs. Search & Pounce (S&P) mode.
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
from typing import List, Dict, Tuple
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from contest_tools.reports.report_interface import ContestReport
from contest_tools.contest_log import ContestLog
from contest_tools.data_aggregators.categorical_stats import CategoricalAggregator
from contest_tools.styles.plotly_style_manager import PlotlyStyleManager
from contest_tools.utils.report_utils import get_valid_dataframe, create_output_directory, _sanitize_filename_part, get_cty_metadata, get_standard_title_lines

class Report(ContestReport):
    """
    Generates a stacked bar chart comparing two logs on common/unique QSOs
    broken down by Run vs. Search & Pounce (S&P) mode.
    """
    report_id = 'qso_breakdown_chart' # Aligned with Interpretation Guide
    report_name = 'QSO Breakdown Chart'
    report_type = 'chart'
    supports_pairwise = True

    def __init__(self, logs: List[ContestLog]):
        super().__init__(logs)
        if len(logs) != 2:
            raise ValueError("ChartQSOBreakdown requires exactly two logs for comparison.")
        self.log1 = logs[0]
        self.log2 = logs[1]
        self.aggregator = CategoricalAggregator()

    def _prepare_data(self, band: str) -> Dict:
        """
        Aggregates data for a specific band using CategoricalAggregator.
        """
        comparison_data = self.aggregator.compute_comparison_breakdown(
            self.log1, 
            self.log2, 
            band_filter=band
        )
        
        categories = [
            f"{self.log1.get_metadata().get('MyCall')}",
            "Common",
            f"{self.log2.get_metadata().get('MyCall')}"
        ]
        
        modes = ['Run', 'S&P', 'Mixed/Unk']
        
        data = {
            'Run': [
                comparison_data['log1_unique']['run'],
                comparison_data['common']['run_both'],
                comparison_data['log2_unique']['run']
            ],
            'S&P': [
                comparison_data['log1_unique']['sp'],
                comparison_data['common']['sp_both'],
                comparison_data['log2_unique']['sp']
            ],
            'Mixed/Unk': [
                comparison_data['log1_unique']['unk'],
                comparison_data['common']['mixed'],
                comparison_data['log2_unique']['unk']
            ]
        }
        
        return {
            'categories': categories,
            'modes': modes,
            'data': data
        }


    def generate(self, output_path: str, **kwargs) -> List[str]:
        """
        Generates the stacked bar chart report and saves it to file(s).
        Returns a list of generated file paths.
        """
        df1 = get_valid_dataframe(self.log1)
        df2 = get_valid_dataframe(self.log2)

        raw_bands = set(df1['Band'].unique()) | set(df2['Band'].unique())
        canonical_band_order = [b[1] for b in ContestLog._HAM_BANDS]
        bands = sorted(raw_bands, key=lambda b: canonical_band_order.index(b) if b in canonical_band_order else -1)

        if not bands:
            return []

        # Grid Calculation
        num_bands = len(bands)
        cols = min(3, num_bands)
        rows = (num_bands + cols - 1) // cols

        fig = make_subplots(
            rows=rows, 
            cols=cols, 
            shared_yaxes=True,
            vertical_spacing=0.15
        )

        colors = PlotlyStyleManager.get_qso_mode_colors()

        for i, band in enumerate(bands):
            # Plotly uses 1-based indexing for rows/cols
            row = (i // cols) + 1
            col = (i % cols) + 1
            
            data_dict = self._prepare_data(band)
            categories = data_dict['categories']
            modes = data_dict['modes']
            data = data_dict['data']
            
            # Show legend only on the first subplot to prevent duplication
            show_legend = (i == 0)

            for mode in modes:
                fig.add_trace(
                    go.Bar(
                        name=mode,
                        x=categories,
                        y=data[mode],
                        marker_color=colors[mode],
                        showlegend=show_legend,
                        legendgroup=mode 
# Groups traces so toggling 'Run' toggles it on all subplots
                    ),
                    row=row, col=col
                )
            fig.update_xaxes(title_text=band, title_standoff=5, row=row, col=col)

        # Standard Layout Application
        modes_present = set(df1['Mode'].dropna().unique()) | set(df2['Mode'].dropna().unique())
        
        title_lines = get_standard_title_lines(self.report_name, self.logs, "All Bands", None, modes_present)

        footer_text = f"Contest Log Analytics by KD4D\n{get_cty_metadata(self.logs)}"
        
        # Use Annotation Stack (List) for precise title spacing control
        layout_config = PlotlyStyleManager.get_standard_layout(title_lines, footer_text)
        fig.update_layout(layout_config)
        
        # Specific Adjustments
        fig.update_layout(
            barmode='stack',
            showlegend=True,
            # Legend Belt: Horizontal, Centered, Just above grid (y=1.02)
            legend=dict(orientation="h", x=0.5, y=1.02, xanchor="center", yanchor="bottom", bgcolor="rgba(255,255,255,0.8)", bordercolor="Black", borderwidth=1)
        )

        create_output_directory(output_path)
        call1 = self.log1.get_metadata().get('MyCall')
        call2 = self.log2.get_metadata().get('MyCall')
        c1_safe = _sanitize_filename_part(call1)
        c2_safe = _sanitize_filename_part(call2)
        base_filename = f"{self.report_id}_{c1_safe}_{c2_safe}"
        
        # --- Save Files ---
        filename_base = base_filename # Re-using calculated base
        
        filepath_html = os.path.join(output_path, f"{filename_base}.html")
        filepath_json = os.path.join(output_path, f"{filename_base}.json")
        
        results = []
        try:
            # 1. Save HTML (Interactive - Fluid)
            # Ensure fluid layout state before locking dimensions for PNG
            fig.update_layout(
                autosize=True,
                height=None,
                width=None
            )
            config = {'toImageButtonOptions': {'filename': filename_base, 'format': 'png'}}
            fig.write_html(filepath_html, include_plotlyjs='cdn', config=config)
            results.append(f"Interactive plot saved: {filepath_html}")

            # 2. Save JSON (Component Data)
            fig.write_json(filepath_json)
            results.append(f"JSON data saved: {filepath_json}")
            
            # 3. Save PNG (Disabled for Web Architecture)
            # try:
            #     # Fixed sizing for PNG
            #     fig.update_layout(
            #         autosize=False,
            #         height=None, # Height was set in layout config
            #         width=1600
            #     )
            #     # fig.write_image(filepath_png)
            # except Exception:
            #     pass
            
        except Exception as e:
            pass

        # Return list of successfully created files (checking existence)
        outputs = []
        if os.path.exists(filepath_html):
            outputs.append(filepath_html)
        if os.path.exists(filepath_json):
            outputs.append(filepath_json)

        return outputs