# contest_tools/utils/report_utils.py
#
# Purpose: A utility module providing shared helper functions for the
#          reporting engine.
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

import pandas as pd
try:
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
except ImportError:
    plt = None
    GridSpec = None
import os
import numpy as np
import re
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from ..contest_log import ContestLog
from ..utils.json_encoders import NpEncoder
from ..core_annotations.get_cty import CtyLookup
import datetime

def get_valid_dataframe(log: ContestLog, include_dupes: bool = False) -> pd.DataFrame:
    """Returns a safe copy of the log's DataFrame, excluding dupes unless specified."""
    df = log.get_processed_data()
    df_slice = df if include_dupes else df[df['Dupe'] == False]
    return df_slice.copy()

def create_output_directory(path: str):
    """Creates the output directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)

def _sanitize_filename_part(part: str) -> str:
    """Sanitizes a string to be used as part of a filename."""
    return re.sub(r'[\s/\\:]+', '_', str(part)).lower()

def get_cty_metadata(logs: list) -> str:
    """
    Extracts CTY version info from the first log's CTY path.
    Returns string format: "YYYY-MM-DD CTY-XXXX"
    """
    if not logs: return "CTY File: Unknown"
    
    path = getattr(logs[0], 'cty_dat_path', '')
    if not path or not os.path.exists(path):
        return "CTY File: Unknown"

    version_match = re.search(r'(\d{4})', os.path.basename(path))
    version_str = f"CTY-{version_match.group(1)}" if version_match else "CTY-Unknown"

    date_obj = CtyLookup.extract_version_date(path)
    date_str = date_obj.strftime('%Y-%m-%d') if date_obj else "Unknown Date"

    return f"CTY File: {date_str} {version_str}"

def get_standard_title_lines(report_name: str, logs: list, band_filter: str = None, mode_filter: str = None, modes_present_set: set = None) -> list:
    """
    Generates the standard 3-Line Title components (Name, Context, Scope).
    Applies Smart Scoping logic for modes.
    """
    if not logs: return [report_name, "", ""]
    
    metadata = logs[0].get_metadata()
    df = get_valid_dataframe(logs[0])
    year = df['Date'].dropna().iloc[0].split('-')[0] if not df.empty else "----"
    contest_name = metadata.get('ContestName', '')
    event_id = metadata.get('EventID', '')
    all_calls = sorted([l.get_metadata().get('MyCall', 'Unknown') for l in logs])
    callsign_str = ", ".join(all_calls)
    
    line2 = f"{year} {event_id} {contest_name} - {callsign_str}".strip().replace("   ", " ")

    is_single_band = len(logs[0].contest_definition.valid_bands) == 1
    if band_filter == 'All' or band_filter is None:
        band_text = logs[0].contest_definition.valid_bands[0].replace('M', ' Meters') if is_single_band else "All Bands"
    else:
        band_text = band_filter.replace('M', ' Meters')

    if mode_filter:
        mode_text = f" ({mode_filter})"
    else:
        if modes_present_set and len(modes_present_set) > 1:
            mode_text = " (All Modes)"
        else:
            mode_text = ""
            
    line3 = f"{band_text}{mode_text}"
    
    return [report_name, line2, line3]

def build_filename(report_id: str, logs: list, band_filter: str = None, mode_filter: str = None) -> str:
    """
    Constructs a standardized, sanitized filename for reports.
    Format: {report_id}_{band}_{mode}_{callsigns}
    """
    is_single_band = len(logs[0].contest_definition.valid_bands) == 1
    raw_band = logs[0].contest_definition.valid_bands[0] if is_single_band else (band_filter or 'All')
    filename_band = raw_band.lower().replace('m', '')
    
    mode_suffix = f"_{mode_filter.lower()}" if mode_filter else ""
    
    all_calls = sorted([l.get_metadata().get('MyCall', 'Unknown') for l in logs])
    filename_calls = '_'.join([_sanitize_filename_part(c) for c in all_calls])
    
    return f"{report_id}_{filename_band}{mode_suffix}_{filename_calls}"

def format_text_header(width: int, title_lines: list, metadata_lines: list = None) -> list:
    """
    Generates a text report header with Left-Aligned Titles and Right-Aligned Metadata.
    """
    if metadata_lines is None:
        metadata_lines = ["Contest Log Analytics by KD4D", "CTY File: Unknown"]

    header_output = []
    max_lines = max(len(title_lines), len(metadata_lines))
    
    for i in range(max_lines):
        left = title_lines[i] if i < len(title_lines) else ""
        right = metadata_lines[i] if i < len(metadata_lines) else ""
        padding = width - len(left) - len(right)
        padding = max(padding, 2)
        header_output.append(f"{left}{' ' * padding}{right}")
        
    return header_output

def determine_activity_status(series: pd.Series) -> str:
    """
    Determines the dominant activity type for a set of QSOs.
    Returns: 'Run', 'S&P', 'Mixed', 'Unknown', or 'Inactive'.
    """
    if series.empty:
        return 'Inactive'
    
    modes = set(series.dropna().unique())
    has_run = "Run" in modes
    has_sp = "S&P" in modes
    
    if has_run and has_sp: return "Mixed"
    elif has_run: return "Run"
    elif has_sp: return "S&P"
    return "Unknown"

def _prepare_time_series_data(log1: ContestLog, log2: Optional[ContestLog], metric: str) -> tuple:
    """Prepares time-series data for one or two logs."""
    metrics_map = log1.contest_definition.metrics_map
    metric_col = metrics_map.get(metric)
    
    all_ts = []

    for log in [log1, log2]:
        if log is None:
            all_ts.append(None)
            continue
        
        df = get_valid_dataframe(log).copy()
        
        if metric_col is None:
            ts = pd.Series(1, index=df['Datetime']).cumsum()
        else:
            ts = df.set_index('Datetime')[metric_col].cumsum()
        
        processed_ts = ts.groupby(ts.index).last()
        all_ts.append(processed_ts)

    df1_ts, df2_ts = all_ts

    master_index = log1._log_manager_ref.master_time_index
    if master_index is not None:
        df1_ts = df1_ts.reindex(master_index, method='ffill').fillna(0)
        if df2_ts is not None:
            df2_ts = df2_ts.reindex(master_index, method='ffill').fillna(0)
            
    return df1_ts, df2_ts

def _create_time_series_figure(log: ContestLog, report_name: str) -> tuple:
    """Creates a standard figure and axes for time-series plots."""
    fig, ax = plt.subplots(figsize=(12, 7))
    
    metadata = log.get_metadata()
    year = get_valid_dataframe(log)['Date'].dropna().iloc[0].split('-')[0]
    contest_name = metadata.get('ContestName', '')
    event_id = metadata.get('EventID', '')
    
    title_line1 = f"{event_id} {year} {contest_name}".strip()
    title_line2 = f"{report_name}"
    fig.suptitle(f"{title_line1}\n{title_line2}", fontsize=16, fontweight='bold')
    
    ax.set_xlabel("Contest Time")
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    
    return fig, ax

class DonutChartComponent:
    """A factory class to create and draw a standardized donut chart component."""
    
    def __init__(self, aggregated_data: Dict[str, Any], title: str, radius: float, is_not_to_scale: bool):
        self.aggregated_data = aggregated_data
        self.title = title
        self.radius = radius
        self.is_not_to_scale = is_not_to_scale

    @staticmethod
    def aggregate_data(df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty or 'QSOPoints' not in df.columns:
            return {'point_counts': pd.Series(), 'total_points': 0, 'total_qsos': 0}

        return {
            'point_counts': df['QSOPoints'].value_counts(),
            'total_points': df['QSOPoints'].sum(),
            'total_qsos': len(df)
        }

    def draw_on(self, fig, gridspec):
        subgrid = gridspec.subgridspec(2, 1, height_ratios=[3, 1], hspace=0.3)
        
        ax_pie = fig.add_subplot(subgrid[0])
        ax_table = fig.add_subplot(subgrid[1])
        ax_table.axis('off')
        
        point_counts = self.aggregated_data.get('point_counts', pd.Series())
        total_points = self.aggregated_data.get('total_points', 0)
        total_qsos = self.aggregated_data.get('total_qsos', 0)
        
        labels = [f'{val} Pts' for val in point_counts.index]
        sizes = point_counts.values
        
        colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(point_counts)))

        wedges, texts = ax_pie.pie(
            sizes, labels=labels, autopct=None, startangle=140, 
            radius=self.radius, colors=colors, 
            wedgeprops=dict(width=0.4, edgecolor='w')
        )
        
        ax_pie.set_title(self.title, fontsize=14, fontweight='bold', pad=20)

        if self.is_not_to_scale:
            ax_pie.text(0, -self.radius - 0.3, "*Not to scale", ha='center', va='center', fontsize=10, color='red', alpha=0.7)

        table_data = [
            ["Total QSOs", f"{total_qsos}"],
            ["Total Points", f"{total_points}"],
            ["Avg Pts/QSO", f"{total_points / total_qsos:.2f}" if total_qsos > 0 else "0.00"]
        ]
        table = ax_table.table(cellText=table_data, colWidths=[0.4, 0.2], loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.2, 1.2)

def save_debug_data(debug_flag: bool, output_path: str, data, custom_filename: str = None):
    """Saves the source data for a report to a .txt file if the debug flag is set."""
    if not debug_flag:
        return

    debug_dir = Path(output_path) / "Debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    is_json_content = isinstance(data, dict)
    if custom_filename:
        filename = custom_filename
        if is_json_content and filename.endswith('.txt'):
            filename = filename[:-4] + '.json'
    else:
        filename = "debug_data.json" if is_json_content else "debug_data.txt"

    debug_filepath = debug_dir / filename

    content = ""
    if isinstance(data, pd.DataFrame):
        content = data.to_string()
    elif is_json_content:
        content = json.dumps(data, indent=4, cls=NpEncoder)
    else:
        content = str(data)

    with open(debug_filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        logging.info(f"Debug data saved to {debug_filepath}")