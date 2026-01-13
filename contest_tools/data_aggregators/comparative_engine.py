# contest_tools/data_aggregators/comparative_engine.py
#
# Purpose: Defines the core logic for comparing sets of multipliers.
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

from dataclasses import dataclass
from typing import Dict, Set

@dataclass
class StationMetrics:
    count: int
    differential: int
    missed: int
    missed_items: Set[str]

@dataclass
class ComparisonResult:
    universe_count: int
    common_count: int
    station_metrics: Dict[str, StationMetrics]

class ComparativeEngine:
    """
    Core logic for comparing sets of multipliers using Set Theory.
    Independent of UI or report format.
    """

    @staticmethod
    def compare_logs(log_multipliers: Dict[str, Set[str]]) -> ComparisonResult:
        """
        Compares multipliers across multiple logs to calculate Universe, Common,
        Differential, and Missed metrics.

        Args:
            log_multipliers: A dictionary mapping Callsign -> Set(MultiplierCodes).

        Returns:
            ComparisonResult object containing integer counts and per-station metrics.
        """
        # 1. Filter out 'Unknown' values explicitly to prevent skewing stats
        filtered_logs: Dict[str, Set[str]] = {}
        for callsign, mults in log_multipliers.items():
            filtered_logs[callsign] = {m for m in mults if m != "Unknown"}

        # Handle empty input gracefully
        if not filtered_logs:
            return ComparisonResult(
                universe_count=0,
                common_count=0,
                station_metrics={}
            )

        # 2. Calculate Universe (Union of all filtered sets: A U B U C)
        universe: Set[str] = set().union(*filtered_logs.values())
        universe_count = len(universe)

        # 3. Calculate Common (Intersection of all filtered sets: A n B n C)
        # Initialize intersection with the first set found
        first_set = next(iter(filtered_logs.values()))
        common: Set[str] = set(first_set)
        for mults in filtered_logs.values():
            common = common.intersection(mults)
        common_count = len(common)

        # 4. Calculate Metrics for each station
        station_metrics: Dict[str, StationMetrics] = {}
        for callsign, mults in filtered_logs.items():
            log_count = len(mults)

            # Differential: Count(Log) - Count(Common)
            # Represents multipliers this station has that exceed the common baseline.
            differential = log_count - common_count

            # Missed: Count(Universe) - Count(Log)
            # Represents multipliers available in the Universe that this station did not work.
            missed_items = universe - mults
            missed_count = len(missed_items)

            station_metrics[callsign] = StationMetrics(
                count=log_count,
                differential=differential,
                missed=missed_count,
                missed_items=missed_items
            )

        return ComparisonResult(
            universe_count=universe_count,
            common_count=common_count,
            station_metrics=station_metrics
        )