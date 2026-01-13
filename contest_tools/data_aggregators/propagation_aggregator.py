# contest_tools/data_aggregators/propagation_aggregator.py
#
# Purpose: This module provides the data aggregator function for the WRTC
#          Propagation by Continent report.
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

import json
import pandas as pd
from typing import List, Dict, Any, Optional

from ..contest_log import ContestLog
from contest_tools.utils.report_utils import get_valid_dataframe
from ..utils.json_encoders import NpEncoder

def generate_propagation_data(logs: List[ContestLog], hour_of_contest: int) -> Optional[Dict[str, Any]]:
    """
    Aggregates QSO data for a specific hour of the contest into a nested
    structure for the WRTC Propagation report.

    Structure:
    Callsign -> Mode -> Band -> Continent -> QSO Count

    Args:
        logs (List[ContestLog]): A list of loaded ContestLog objects.
        hour_of_contest (int): The specific hour (1-based index) of the
                               contest to aggregate data for.

    Returns:
        Optional[Dict[str, Any]]: A dictionary matching the PropagationBreakdownData
                                  structure, or None if no data is available.
    """
    if not logs:
        return None

    log_manager = getattr(logs[0], '_log_manager_ref', None)
    master_index = getattr(log_manager, 'master_time_index', None)

    if master_index is None or hour_of_contest < 1 or hour_of_contest > len(master_index):
        return None

    target_hour_ts = master_index[hour_of_contest - 1]

    all_dfs = []
    for log in logs:
        df = get_valid_dataframe(log, include_dupes=False).copy()
        df['MyCall'] = log.get_metadata().get('MyCall')
        all_dfs.append(df)

    combined_df = pd.concat(all_dfs)
    if combined_df.empty:
        return None

    # Filter for the specific hour
    hourly_df = combined_df[combined_df['Datetime'].dt.floor('h') == target_hour_ts]
    if hourly_df.empty:
        return None

    # Perform the multi-level aggregation
    grouped = hourly_df.groupby(['MyCall', 'Mode', 'Band', 'Continent']).size()
    if grouped.empty:
        return None

    # Convert the multi-index Series to the required nested dictionary
    nested_data = {}
    for (call, mode, band, continent), count in grouped.items():
        nested_data.setdefault(call, {}).setdefault(mode, {}).setdefault(band, {})[continent] = count

    # Build the final data structure
    all_calls = sorted([log.get_metadata().get('MyCall') for log in logs])
    
    result = {
        "title": "WRTC Propagation by Continent (Hourly Snapshot)",
        "calls": all_calls,
        "bands": sorted(list(hourly_df['Band'].unique())),
        "continents": sorted(list(hourly_df['Continent'].unique())),
        "modes": sorted(list(hourly_df['Mode'].unique())),
        "data": nested_data
    }

    # Strict JSON Sanitization:
    # Forces conversion of all NumPy types (int64, etc.) to Python primitives.
    return json.loads(json.dumps(result, cls=NpEncoder))