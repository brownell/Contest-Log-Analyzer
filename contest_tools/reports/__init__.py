# contest_tools/reports/__init__.py
#
# Purpose: This module dynamically discovers and imports all available report
#          generator classes from the other Python files in this directory.
#          It creates the AVAILABLE_REPORTS dictionary, which is used by the main
#          CLI and ReportGenerator to access and run reports.
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

import os
import importlib
import inspect
import logging
from django.core.exceptions import AppRegistryNotReady, ImproperlyConfigured

# Dynamically discover and load all available report classes
AVAILABLE_REPORTS = {}

# Get the directory of the current module
current_dir = os.path.dirname(os.path.abspath(__file__))

# Iterate over all files in the directory
for filename in os.listdir(current_dir):
    # Process only Python files that are not __init__.py itself
    if filename.endswith('.py') and not filename.startswith('__'):
        module_name = filename[:-3]
        
        try:
            # Import the module dynamically
            module = importlib.import_module(f".{module_name}", package='contest_tools.reports')
            
            # Find the 'Report' class within the imported module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if name == 'Report':
                    # Check if the class has the required 'report_id' attribute
                    if hasattr(obj, 'report_id'):
                        report_id = obj.report_id
                        AVAILABLE_REPORTS[report_id] = obj
                    else:
                        logging.warning(f"Report class in {filename} is missing 'report_id' attribute.")
        except ImportError as e:
            if 'matplotlib' in str(e) or 'jinja2' in str(e):
                logging.warning(f"DEBUG TRACE: Skipping legacy report '{filename}': Missing dependency ({e}).")
            else:
                logging.exception(f"Failed to load report from {filename}: {e}")
        except Exception as e:
            # Suppress Django-specific errors when running in CLI mode (no settings configured)
            if "settings are not configured" in str(e) or "Apps aren't loaded yet" in str(e):
                # Only log as warning, do not dump stack
                pass 
            else:
                logging.exception(f"Failed to load report from {filename}: {e}")