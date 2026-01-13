# contest_tools/styles/plotly_style_manager.py
#
# Purpose: Centralized management of Plotly styles and color schemes
#          to ensure consistency across all interactive visual reports.
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
from typing import Dict, List, Any, Union
import plotly.graph_objects as go

class PlotlyStyleManager:
    """
    Provides standardized color maps and style configurations for
    Plotly-based reports.
    """

    # Standard Tableau 10 Color Palette (Hex)
    # Copied to avoid dependency on matplotlib.colors
    _COLOR_PALETTE = [
        '#1f77b4', # Blue
        '#ff7f7e', # Orange (Corrected typo from source if any, standardizing on Tableau 10)
        '#2ca02c', # Green
        '#d62728', # Red
        '#9467bd', # Purple
        '#8c564b', # Brown
        '#e377c2', # Pink
        '#7f7f7f', # Gray
        '#bcbd22', # Olive
        '#17becf'  # Cyan
    ]

    @staticmethod
    def get_point_color_map(point_values: List[Any]) -> Dict[Any, str]:
        """
        Generates a consistent color map for QSO point values.
        
        Args:
            point_values: A list of unique point values (e.g., [1, 2, 4]).
            
        Returns:
            A dictionary mapping point values to hex color strings.
        """
        # Sort to ensure deterministic color assignment
        sorted_vals = sorted(point_values, key=lambda x: str(x))
        color_map = {}
        
        for i, val in enumerate(sorted_vals):
            # Cycle through palette if more values than colors
            color = PlotlyStyleManager._COLOR_PALETTE[i % len(PlotlyStyleManager._COLOR_PALETTE)]
            color_map[val] = color
            
        return color_map

    @staticmethod
    def get_qso_mode_colors() -> Dict[str, str]:
        """
        Returns the standard color scheme for QSO breakdown modes.

        Returns:
            Dictionary mapping modes ('Run', 'S&P', 'Mixed/Unk') to colors.
        """
        return {
            'Run': '#2ca02c',       # Green
            'S&P': '#1f77b4',       # Blue
            'Mixed/Unk': '#7f7f7f'  # Gray
        }

    @staticmethod
    def get_standard_layout(title: Union[str, List[str]], footer_text: str = None) -> Dict[str, Any]:
        """
        Returns a standard Plotly layout dictionary.

        Args:
            title: The chart title. Can be a string (Legacy) or List[str] (Annotation Stack).
            footer_text: Optional text to display as a footer (e.g., Branding/CTY info).

        Returns:
            A dictionary suitable for passing to fig.update_layout().
        """
        layout = {
            "font": {"family": "Arial, sans-serif"},
            "template": "plotly_white",
            "margin": {"l": 50, "r": 50, "t": 130, "b": 160}, # Increased t/b for headers/footers
            "showlegend": True
        }

        if isinstance(title, list) and len(title) > 0:
            # Annotation Stack Strategy (Pixel-Locked)
            layout["title"] = {"text": ""} # Disable standard title
            
            annotations = [
                # Line 1: Main Header (Bold, Anchored High in Margin)
                # y=1 is top of GRID. yshift=90 pushes it UP to create room for Legend Belt.
                dict(x=0.5, y=1, xref='paper', yref='paper', text=f"<b>{title[0]}</b>", 
                     showarrow=False, font=dict(size=24, family="Arial, sans-serif"), 
                     xanchor='center', yanchor='bottom', yshift=90),
                
                # Lines 2+: Subheader (Normal, Hanging from Header)
                dict(x=0.5, y=1, xref='paper', yref='paper', text="<br>".join(title[1:]),
                     showarrow=False, font=dict(size=16, family="Arial, sans-serif"),
                     xanchor='center', yanchor='top', yshift=90)
            ]
            layout["annotations"] = annotations
        else:
            # Legacy String Behavior
            layout["title"] = {
                "text": str(title),
                "x": 0.5,
                "xanchor": "center",
                "font": {"size": 20, "family": "Arial, sans-serif", "weight": "bold"}
            }

        if footer_text:
            footer_ann = dict(
                x=0.5,
                y=0, # Anchor to bottom of plot area
                yshift=-85, # Push down by fixed pixels (clears axis labels)
                xref="paper",
                yref="paper",
                text=footer_text.replace('\n', '<br>'), # Convert newlines for Plotly
                showarrow=False,
                font=dict(size=12, color="#7f7f7f"),
                align="center",
                valign="top",
                yanchor="top" # Ensure shift pushes down from the anchor
            )
            
            if "annotations" in layout:
                layout["annotations"].append(footer_ann)
            else:
                layout["annotations"] = [footer_ann]
            
        return layout