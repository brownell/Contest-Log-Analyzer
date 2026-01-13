# contest_tools/styles/mpl_style_manager.py
#
# Purpose: Centralized management of Matplotlib styles and color schemes
#          to ensure consistency across all visual reports.
#
# Copyright (c) 2025 Mark Bailey, KD4D
# Contact: kd4d@kd4d.org
#
# License: Mozilla Public License, v. 2.0
#          (https://www.mozilla.org/MPL/2.0/)
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from typing import Dict, List, Any
import matplotlib.colors as mcolors

class MPLStyleManager:
    """
    Provides standardized color maps and style configurations for
    Matplotlib-based reports.
    """

    # Standard colors for consistency
    _COLOR_PALETTE = list(mcolors.TABLEAU_COLORS.values())

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
            color = MPLStyleManager._COLOR_PALETTE[i % len(MPLStyleManager._COLOR_PALETTE)]
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
            'Run': '#2ca02c',       # Green (tab:green)
            'S&P': '#1f77b4',       # Blue (tab:blue)
            'Mixed/Unk': '#7f7f7f'  # Gray (tab:gray)
        }