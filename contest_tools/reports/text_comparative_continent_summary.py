# contest_tools/reports/text_comparative_continent_summary.py
#
# Purpose: A text report that generates a side-by-side comparison of QSO counts
#          by continent for two logs.
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

import os
from typing import List, Dict
import pandas as pd

from contest_tools.reports.report_interface import ContestReport
from contest_tools.contest_log import ContestLog
from contest_tools.data_aggregators.categorical_stats import CategoricalAggregator
from contest_tools.utils.report_utils import get_valid_dataframe, create_output_directory, _sanitize_filename_part, format_text_header, get_cty_metadata, get_standard_title_lines

class Report(ContestReport):
    """
    Generates a simple text table comparing continent totals between two logs.
    """
    report_id = 'text_comparative_continent_summary'
    report_name = 'Comparative Continent Summary (Text)'
    report_type = 'text'
    supports_pairwise = True

    def __init__(self, logs: List[ContestLog]):
        super().__init__(logs)
        if len(logs) != 2:
            raise ValueError("Comparative Continent Summary requires exactly two logs.")
        self.aggregator = CategoricalAggregator()

    def generate(self, output_path: str, **kwargs) -> str:
        # 1. Validation
        if not self.logs or any(get_valid_dataframe(log).empty for log in self.logs):
            return "No valid data available for generation."

        # 2. Aggregation
        # We need to manually aggregate because CategoricalAggregator is usually band-specific
        # but here we want totals.
        log1, log2 = self.logs[0], self.logs[1]
        call1 = log1.get_metadata().get('MyCall', 'Log1')
        call2 = log2.get_metadata().get('MyCall', 'Log2')
        
        df1 = get_valid_dataframe(log1)
        df2 = get_valid_dataframe(log2)
        
        # Group by Continent
        if 'Continent' not in df1.columns:
             return "Error: 'Continent' data missing from log processing."

        counts1 = df1['Continent'].value_counts()
        counts2 = df2['Continent'].value_counts()
        
        all_conts = sorted(set(counts1.index) | set(counts2.index))
        
        # 3. Formatting
        lines = []
        lines.append(f"Comparative Continent Summary: {call1} vs {call2}")
        lines.append("=" * 60)
        lines.append(f"{'Continent':<15} | {call1:>10} | {call2:>10} | {'Diff':>10}")
        lines.append("-" * 60)
        
        total1 = 0
        total2 = 0
        
        for cont in all_conts:
            c1 = counts1.get(cont, 0)
            c2 = counts2.get(cont, 0)
            diff = c1 - c2
            
            lines.append(f"{cont:<15} | {c1:10} | {c2:10} | {diff:10}")
            
            total1 += c1
            total2 += c2
            
        lines.append("-" * 60)
        lines.append(f"{'TOTAL':<15} | {total1:10} | {total2:10} | {(total1-total2):10}")
        
        report_text = "\n".join(lines)
        
        # 4. Save
        create_output_directory(output_path)
        base_filename = f"{self.report_id}_{_sanitize_filename_part(call1)}_{_sanitize_filename_part(call2)}.txt"
        file_path = os.path.join(output_path, base_filename)
        
        with open(file_path, 'w') as f:
            f.write(report_text)
            
        return f"Report saved to {file_path}"