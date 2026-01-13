# contest_tools/core_annotations/_band_allocator.py
#
# Purpose: This module provides the BandAllocator class, which loads the
#          band_allocations.dat file and provides a method to validate if
#          a given frequency falls within any defined amateur radio band.
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
import logging
import pandas as pd
from typing import List, Tuple

class BandAllocator:
    """
    Manages and validates frequencies against the band_allocations.dat file.
    """
    def __init__(self, root_input_dir: str):
        self._band_ranges: List[Tuple[int, int]] = []
        self._load_allocations(root_input_dir)

    def _load_allocations(self, root_input_dir: str):
        """Loads and parses the band_allocations.dat file."""
        try:
            root_dir = root_input_dir.strip().strip('"').strip("'")
            data_dir = os.path.join(root_dir, 'data')
            dat_filepath = os.path.join(data_dir, 'band_allocations.dat')

            with open(dat_filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split(',')
                    if len(parts) == 3:
                        try:
                            start_khz = int(parts[0])
                            end_khz = int(parts[1])
                            self._band_ranges.append((start_khz, end_khz))
                        except ValueError:
                            logging.warning(f"Could not parse band allocation line: {line}")
            
            logging.info(f"Successfully loaded {len(self._band_ranges)} band allocations.")

        except FileNotFoundError:
            logging.error(f"FATAL: band_allocations.dat not found at '{dat_filepath}'. Frequency validation will not work.")
        except Exception as e:
            logging.error(f"FATAL: An unexpected error occurred loading band_allocations.dat: {e}")

    def is_frequency_valid(self, frequency_khz: float) -> bool:
        """
        Checks if a given frequency in kHz is within any of the loaded band ranges.
        Args:
            frequency_khz (float): The frequency to validate.

        Returns:
            bool: True if the frequency is valid, False otherwise.
        """
        if pd.isna(frequency_khz):
            return False
            
        freq_int = int(frequency_khz)
        
        for start_khz, end_khz in self._band_ranges:
            if start_khz <= freq_int <= end_khz:
                return True
        
        return False
