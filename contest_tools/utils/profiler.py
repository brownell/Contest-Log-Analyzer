# contest_tools/utils/profiler.py
#
# Purpose: Performance profiling utilities for measuring execution time
#          of critical code paths when CLA_PROFILE=1 is set.
#
# Author: Gemini AI
# Date: 2026-01-07
# Version: 0.160.0-Beta
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
# --- Revision History ---
# [0.160.0-Beta] - 2026-01-07
# - Initial creation of performance profiling infrastructure.

import time
import os
import logging
from functools import wraps
from typing import Optional, Callable, Any

def profile_section(section_name: str):
    """
    Decorator to profile execution time of functions when CLA_PROFILE=1.
    
    When the CLA_PROFILE environment variable is set to '1', this decorator
    will log the execution time of the wrapped function. Otherwise, the
    function executes normally without timing overhead.
    
    Args:
        section_name: A descriptive name for the profiled section (e.g., "Log Parsing")
    
    Usage:
        @profile_section("CTY File Resolution")
        def resolve_cty_file(self, date):
            # ... implementation
            pass
    
    Output (when CLA_PROFILE=1):
        ⏱️  [CTY File Resolution] completed in 0.342s
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if os.environ.get('CLA_PROFILE') == '1':
                start = time.perf_counter()
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                logging.info(f"⏱️  [{section_name}] completed in {elapsed:.3f}s")
                return result
            return func(*args, **kwargs)
        return wrapper
    return decorator


class ProfileContext:
    """
    Context manager for profiling code blocks when CLA_PROFILE=1.
    
    Usage:
        with ProfileContext("Heavy Computation"):
            # ... code to profile
            pass
    
    Output (when CLA_PROFILE=1):
        ⏱️  [Heavy Computation] completed in 1.234s
    """
    def __init__(self, section_name: str):
        self.section_name = section_name
        self.start_time: Optional[float] = None
        self.enabled = os.environ.get('CLA_PROFILE') == '1'
    
    def __enter__(self):
        if self.enabled:
            self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.enabled and self.start_time is not None:
            elapsed = time.perf_counter() - self.start_time
            logging.info(f"⏱️  [{self.section_name}] completed in {elapsed:.3f}s")
        return False  # Don't suppress exceptions
