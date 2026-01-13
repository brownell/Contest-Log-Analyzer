# contest_tools/reports/plot_point_rate.py
#
# Purpose: A plot report that generates a point rate graph for all bands
#          and for each individual band.
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

from .base_rate_report import BaseRateReport

class Report(BaseRateReport):
    """
    Generates a series of plots comparing cumulative points: one for all bands
    combined, and one for each individual contest band.
    """
    report_id: str = "point_rate_plots"
    report_name: str = "Point Rate Comparison Plots"
    
    # BaseRateReport configuration
    metric_key: str = "points"
    metric_label: str = "Points"

    def _get_metric_name(self) -> str:
        """Override to check for contest-specific point labels."""
        if self.logs:
             return self.logs[0].contest_definition.points_header_label or self.metric_label
        return self.metric_label