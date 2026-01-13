# contest_tools/reports/text_continent_breakdown.py
#
# Purpose: A text report that generates a breakdown of QSOs by continent
#          for each band, utilizing the CategoricalAggregator.
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
from tabulate import tabulate
from .report_interface import ContestReport
from ..data_aggregators.categorical_stats import CategoricalAggregator
from contest_tools.utils.report_utils import _sanitize_filename_part, format_text_header, get_cty_metadata, get_standard_title_lines

class Report(ContestReport):
    """
    Generates a text table showing QSO counts per Continent per Band.
    """
    report_id: str = "text_continent_breakdown"
    report_name: str = "Continent Breakdown (Text)"
    report_type: str = "text"
    supports_multi = True
    supports_single = True

    def generate(self, output_path: str, **kwargs) -> str:
        results = []
        
        for log in self.logs:
            callsign = log.get_metadata().get('MyCall', 'Unknown')
            
            # --- 1. Aggregation (DAL) [Stateless] ---
            agg = CategoricalAggregator()
            data = agg.get_category_breakdown(log, 'Continent')
            
            # --- 2. Formatting ---
            # Data comes as a list of dicts suitable for DataFrame/Tabulate
            # Add TOTAL row if not handled by aggregator (Aggregator does not add totals row currently)
            
            if not data:
                results.append(f"Skipping {callsign}: No valid continent data found.")
                continue
            
            # Calculate column totals manually for display
            totals = {k: 0 for k in data[0].keys() if k != 'Band'}
            totals['Band'] = 'TOTAL'
            
            for row in data:
                for k, v in row.items():
                    if k != 'Band' and isinstance(v, (int, float)):
                        totals[k] += v
            
            data.append(totals)
            
            table_string = tabulate(data, headers='keys', tablefmt='psql', showindex="never")
            
            # --- 3. Header Construction ---
            modes_present = set()
            df = log.get_processed_data()
            if 'Mode' in df.columns:
                modes_present.update(df['Mode'].dropna().unique())
            
            # Use utility for standard 3-line title
            title_lines = get_standard_title_lines(self.report_name, [log], "All Bands", None, modes_present)
            
            # Use utility for footer metadata
            meta_lines = ["Contest Log Analytics by KD4D", get_cty_metadata([log])]
            
            # Use utility to format the header block based on table width
            table_width = len(table_string.split('\n')[0])
            header_block = format_text_header(table_width, title_lines, meta_lines)
            
            full_report = "\n".join(header_block + [table_string, "\n"])
            
            # --- 4. Save ---
            filename = f"{self.report_id}_{_sanitize_filename_part(callsign)}.txt"
            filepath = os.path.join(output_path, filename)
            
            try:
                os.makedirs(output_path, exist_ok=True)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(full_report)
                results.append(filepath)
            except Exception as e:
                results.append(f"Error saving {filename}: {e}")

        return "Reports generated:\n" + "\n".join(results)