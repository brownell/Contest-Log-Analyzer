# contest_tools/reports/report_interface.py
#
# Purpose: Defines the abstract base class for all report generators.
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

from abc import ABC, abstractmethod
from typing import List
from ..contest_log import ContestLog

class ContestReport(ABC):
    """
    Abstract base class for all report generators.
    Ensures that every report has a consistent structure.
    """
    # --- Class attributes defining report metadata and behavior ---
    report_id: str = "abstract_report"
    report_name: str = "Abstract Report"
    report_type: str = "text"
    is_specialized: bool = False # False = Generic (opt-out), True = Specialized (opt-in)
    
    supports_single: bool = False
    supports_pairwise: bool = False
    supports_multi: bool = False

    def __init__(self, logs: List[ContestLog]):
        if not logs:
            raise ValueError("Cannot initialize a report with an empty list of logs.")
        self.logs = logs

    @abstractmethod
    def generate(self, output_path: str, **kwargs) -> str:
        """
        Generates the report content.

        Args:
            output_path (str): The directory where any output files should be saved.
            **kwargs: A dictionary for optional report-specific arguments.
                - include_dupes (bool): If True, include dupes. Defaults to False.
                - mult_name (str): The name of the multiplier to analyze.
                - metric (str): 'qsos' or 'points'.

        Returns:
            str: A summary message confirming the report generation.
        """
        pass