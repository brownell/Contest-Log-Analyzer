# contest_tools/log_manager.py
#
# Purpose: Defines the LogManager class, which is responsible for orchestrating
#          the loading, processing, and management of one or more ContestLog
#          instances.
#          It serves as the primary entry point for the core
#          analysis engine.
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
# - Added performance profiling instrumentation when CLA_PROFILE=1.
# [0.141.0-Beta] - 2025-12-29
# - Implemented strict, case-insensitive alphabetical sorting of logs in
#   load_log_batch to ensure deterministic processing order.
#
# [0.131.1-Beta] - 2025-12-23
# - Refactored pre-flight validation to check every log for duplicate callsigns
#   and missing QSO data.
# - Updated consistency checks to enforce matching Contest, Year, and Event ID.
# - Updated `_get_first_qso_date_from_log` to return None on failure/empty,
#   allowing for safer CTY date resolution.
#
# [0.113.1-Beta] - 2025-12-14
# - Enforced strict lowercase standards for report directory creation to ensure
#   cross-platform compatibility (Linux/Windows).
#
# [0.91.6-Beta] - 2025-12-10
# - Removed the "Hourly ADIF Debug File Generation" block from finalize_loading
#   to disable the creation of partial ADIF files in the Debug/ directory.
#
# [0.91.5-Beta] - 2025-10-09
# - Removed obsolete warning suppression logic for hourly ADIF files and
#   updated the `export_to_adif` call to pass a new context parameter.
#
# [0.91.3-Beta] - 2025-10-09
# - No functional changes. Synchronizing version number with `__init__.py`
#   for a consolidated bugfix release.
#
# [0.91.2-Beta] - 2025-10-09
# - Fixed latent bug in _create_master_time_index by changing ceil('h')
#   to floor('h') to prevent creation of an extra, empty hour.
#
# [0.91.1-Beta] - 2025-10-09
# - Fixed regression by restoring the implicit generic/specific file loading
#   logic as a fallback for definitions that do not use "inherits_from".
#
# [0.91.0-Beta] - 2025-10-09
# - Added logic to `load_log_batch` to handle the `--wrtc` flag, allowing
#   IARU-HF logs to be scored with a specific WRTC ruleset.
#
# [0.90.8-Beta] - 2025-10-06
# - Added Excel-compatible text formatting to the `QTC_GRP` column in the WAE QTC CSV export.
#
# [0.90.7-Beta] - 2025-10-06
# - Added logic to `finalize_loading` to export a `_qtcs.csv` file for WAE logs.
#
# [0.90.6-Beta] - 2025-10-05
# - Added logic to `finalize_loading` to generate hourly ADIF debug files when `--debug-data` is enabled.
#
# [0.90.0-Beta] - 2025-10-01
# Set new baseline version for release.

import pandas as pd
from typing import List, Optional, Set
from .contest_log import ContestLog
from .utils.cty_manager import CtyManager
from .core_annotations import CtyLookup, BandAllocator
from .utils.profiler import profile_section, ProfileContext
import os
import importlib
from datetime import datetime
import logging

class LogManager:
    """
    Manages the loading and processing of one or more contest logs.
    """

    def __init__(self):
        self.logs = []
        self.master_time_index = None

    @profile_section("Log Batch Loading (Total)")
    def load_log_batch(self, log_filepaths: List[str], root_input_dir: str, cty_specifier: str, wrtc_year: int = None):
        """
        Performs validation on log files (duplicates, consistency, empty checks), selects a single
        CTY file, and then loads and processes all logs.
        """
        # --- 1. Pre-flight Validation Phase ---
        if log_filepaths:
            with ProfileContext("Pre-flight Validation"):
                logging.info("Performing pre-flight validation on logs...")
                header_data = []
                seen_calls: Set[str] = set()

                for path in log_filepaths:
                    call = self._get_callsign_from_header(path)
                    
                    # Check for duplicate callsigns
                    if call in seen_calls:
                        raise ValueError(f"Duplicate log callsign '{call}' detected in cabrillo header of '{os.path.basename(path)}'. Each log must be from a unique station.")
                    seen_calls.add(call)

                    base_contest = self._get_contest_name_from_header(path)
                    if wrtc_year and base_contest == 'IARU-HF':
                        effective_contest = f"WRTC-{wrtc_year}"
                    else:
                        effective_contest = base_contest

                    date = self._get_first_qso_date_from_log(path)
                    if date is None:
                        raise ValueError(f"Log file '{os.path.basename(path)}' contains no valid QSO records.")

                    # Minimal setup to resolve event ID
                    temp_log = ContestLog(contest_name=effective_contest, cabrillo_filepath=None, root_input_dir=root_input_dir, cty_dat_path=None)
                    temp_log.get_processed_data()['Datetime'] = pd.Series([date]) 
                    event_id = self._get_event_id(temp_log)
                    
                    header_data.append({'call': call, 'contest': effective_contest, 'date': date, 'event_id': event_id, 'filename': os.path.basename(path)})

                # Consistency Checks
                if len(header_data) > 1:
                    first = header_data[0]
                    first_year = first['date'].year

                    for other in header_data[1:]:
                        # Contest Name (Includes Mode for single-mode contests)
                        if other['contest'] != first['contest']:
                            raise ValueError(f"Contest Mismatch: '{other['filename']}' is '{other['contest']}', but '{first['filename']}' is '{first['contest']}'.")
                        
                        # Year
                        if other['date'].year != first_year:
                            raise ValueError(f"Year Mismatch: '{other['filename']}' is from {other['date'].year}, but '{first['filename']}' is from {first_year}.")

                        # Event ID (e.g. NAQP Jan vs Aug)
                        if other['event_id'] != first['event_id']:
                            raise ValueError(f"Event Mismatch: '{other['filename']}' is event '{other['event_id']}', but '{first['filename']}' is '{first['event_id']}'.")

                logging.info("Validation successful.")

        # --- 2. Single CTY File Selection ---
        with ProfileContext("CTY File Resolution"):
            logging.info("Resolving CTY file for batch...")
            cty_manager = CtyManager(root_input_dir)
            
            if cty_specifier in ['before', 'after']:
                all_dates = [self._get_first_qso_date_from_log(path) for path in log_filepaths]
                # Filter None to be safe (though validation guarantees validity)
                valid_dates = [d for d in all_dates if d is not None]
                
                if not valid_dates:
                    target_date = pd.Timestamp.now(tz='UTC')
                else:
                    target_date = min(valid_dates) if cty_specifier == 'before' else max(valid_dates)
            else:
                # If a specific filename is given, we need a date for the sync check.
                # We'll just use the first log's date as it's a reasonable proxy.
                target_date = self._get_first_qso_date_from_log(log_filepaths[0]) or pd.Timestamp.now(tz='UTC')

            # Conditionally update the index based on the determined target date
            cty_manager.sync_index(contest_date=target_date)

            if cty_specifier in ['before', 'after']:
                cty_dat_path, cty_file_info = cty_manager.find_cty_file_by_date(target_date, cty_specifier)
            else:
                cty_dat_path, cty_file_info = cty_manager.find_cty_file_by_name(cty_specifier)
            
            if not cty_dat_path:
                raise FileNotFoundError(f"Could not find a suitable CTY.DAT file for specifier '{cty_specifier}'.")
            logging.info(f"Using CTY file for all logs: {os.path.basename(cty_dat_path)} (Date: {cty_file_info.get('date')})")

        # --- 2.5. Create Shared Instances (Performance Optimization) ---
        # Create shared CTY lookup and BandAllocator instances to avoid reloading from disk for each log
        shared_cty_lookup = CtyLookup(cty_dat_path=cty_dat_path)
        shared_band_allocator = BandAllocator(root_input_dir)

        # --- 3. Full Log Loading Phase ---
        for path in log_filepaths:
            try:
                with ProfileContext(f"Individual Log Loading - {os.path.basename(path)}"):
                    logging.info(f"Loading log: {path}...")
                    base_contest_name = self._get_contest_name_from_header(path)
                    if not base_contest_name:
                        logging.warning(f"  - Could not determine contest name from file header. Skipping.")
                        continue

                    if wrtc_year and base_contest_name == 'IARU-HF':
                        contest_name = f"WRTC-{wrtc_year}"
                        logging.info(f"  --wrtc flag is set. Scoring as '{contest_name}'.")
                    else:
                        contest_name = base_contest_name

                    log = ContestLog(contest_name=contest_name, cabrillo_filepath=path, root_input_dir=root_input_dir, 
                                   cty_dat_path=cty_dat_path, shared_cty_lookup=shared_cty_lookup, 
                                   shared_band_allocator=shared_band_allocator)
                    setattr(log, '_log_manager_ref', self)
                    log.apply_annotations()
                    
                    self.logs.append(log)
                    logging.info(f"Successfully loaded and processed log for {log.get_metadata().get('MyCall', 'Unknown')}.")

            except Exception as e:
                logging.error(f"Error loading log {path}: {e}")

        # --- 4. Enforce Deterministic Order (Alphabetical by Callsign) ---
        # This ensures that Log 1, Log 2, etc. are consistent regardless of upload order.
        self.logs.sort(key=lambda x: str(x.get_metadata().get('MyCall', 'Unknown')).upper())

    @profile_section("Finalize Loading (Total)")
    def finalize_loading(self, root_reports_dir: str, debug_data: bool = False):
        """
        Should be called after all logs are loaded to perform final,
        cross-log processing steps like creating the master time index and
        saving the processed data files.
        """
        if not self.logs:
            return

        self._create_master_time_index()

        # --- Pre-calculate Time-Series Scores ---
        # This must be done after the master time index is created but before
        # any reports are generated.
        with ProfileContext("Time-Series Score Pre-calculation"):
            logging.info("Pre-calculating time-series scores for all logs...")
            for log in self.logs:
                log._pre_calculate_time_series_score()

        if not self.logs:
            return
            
        # The root directory is now passed in as a parameter.
        root_dir = root_reports_dir
        first_log = self.logs[0]
        contest_name = first_log.get_metadata().get('ContestName', 'UnknownContest').replace(' ', '_').lower()
        
        df_first_log = first_log.get_processed_data()
        year = df_first_log['Date'].dropna().iloc[0].split('-')[0] if not df_first_log.empty and not df_first_log['Date'].dropna().empty else "UnknownYear"

        event_id = self._get_event_id(first_log).lower()
        for log in self.logs:
            log.metadata['EventID'] = event_id
        
        all_calls = sorted([log.get_metadata().get('MyCall', f'Log{i+1}').lower() for i, log in enumerate(self.logs)])
        callsign_combo_id = '_'.join(all_calls)

        output_dir = os.path.join(root_dir, 'reports', year, contest_name, event_id, callsign_combo_id)
        os.makedirs(output_dir, exist_ok=True)
        
        for log in self.logs:
            base_filename = os.path.splitext(os.path.basename(log.filepath))[0]
            
            # --- CSV Export ---
            output_filename = f"{base_filename}_processed.csv"
            output_filepath = os.path.join(output_dir, output_filename)
            log.export_to_csv(output_filepath)

            # --- WAE QTC Data Export ---
            if log.contest_definition.contest_name.startswith('WAE'):
                qtcs_df = getattr(log, 'qtcs_df', pd.DataFrame())
                if not qtcs_df.empty:
                    qtcs_filename = f"{base_filename}_qtcs.csv"
                    qtcs_filepath = os.path.join(output_dir, qtcs_filename)
                    # Format QTC_GRP to prevent Excel from auto-formatting as a date
                    qtcs_df['QTC_GRP'] = '="' + qtcs_df['QTC_GRP'].astype(str) + '"'
                    qtcs_df.to_csv(qtcs_filepath, index=False, na_rep='')
                    logging.info(f"WAE QTC data saved to: {qtcs_filepath}")

            # --- ADIF Export (if enabled for this contest) ---
            if getattr(log.contest_definition, 'enable_adif_export', False):
                adif_filename = f"{base_filename}_N1MMADIF.adi"
                adif_filepath = os.path.join(output_dir, adif_filename)
                
                # Use custom exporter if defined, otherwise fall back to generic
                if custom_exporter_name := getattr(log.contest_definition, 'custom_adif_exporter', None):
                    try:
                        exporter_module = importlib.import_module(f"contest_tools.adif_exporters.{custom_exporter_name}")
                        exporter_module.export_log(log, adif_filepath)
                    except Exception as e:
                        logging.error(f"Could not run custom ADIF exporter '{custom_exporter_name}': {e}")
                else:
                    # Fallback to the generic method in ContestLog
                    log.export_to_adif(adif_filepath)


    def _get_event_id(self, log: ContestLog) -> str:
        """
        Determines the unique event ID for a contest.
        """
        resolver_name = log.contest_definition.contest_specific_event_id_resolver
        if resolver_name:
            try:
                # Check if there's any data to get a timestamp from
                if log.get_processed_data().empty or 'Datetime' not in log.get_processed_data().columns:
                    return "NoQSOData"
                
                first_qso_time = log.get_processed_data()['Datetime'].iloc[0]
                if pd.isna(first_qso_time):
                    return "InvalidTime"

                resolver_module = importlib.import_module(f"contest_tools.event_resolvers.{resolver_name}")
                return resolver_module.resolve_event_id(first_qso_time)
            except (ImportError, AttributeError, IndexError) as e:
                logging.warning(f"Could not run event ID resolver '{resolver_name}': {e}")
                return "UnknownEvent"
        else:
            return ""

    @profile_section("Master Time Index Creation")
    def _create_master_time_index(self):
        """
        Creates a master time index from all logs.
        """
        logging.info("Creating master time index...")
        if len(self.logs) < 1:
            return
        
        all_datetimes = pd.concat([log.get_processed_data()['Datetime'] for log in self.logs if not log.get_processed_data().empty])
        if all_datetimes.empty or all_datetimes.isna().all():
            logging.info("  - No valid QSO datetimes found. Skipping master time index creation.")
            return

        min_time = all_datetimes.min().floor('h')
        max_time = all_datetimes.max().floor('h')
        
        # Calculate the number of hourly periods from the actual min/max times
        periods = int((max_time - min_time).total_seconds() / 3600) + 1
        self.master_time_index = pd.date_range(start=min_time, periods=periods, freq='h', tz='UTC')
        logging.info("Master time index created.")


    def _get_first_qso_date_from_log(self, filepath: str) -> Optional[pd.Timestamp]:
        """Reads the first QSO line to determine the contest date."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.upper().startswith('QSO:'):
                        parts = line.split()
                        date_str = parts[3]
                        return pd.to_datetime(date_str).tz_localize('UTC')
        except Exception:
            return None
        return None

    def _get_contest_name_from_header(self, filepath: str) -> str:
        """
        Reads just the CONTEST: line from a Cabrillo file.
        """
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.upper().startswith('CONTEST:'):
                        return line.split(':', 1)[1].strip()
        except Exception as e:
            logging.warning(f"Could not read contest name from {filepath}: {e}")
        return ""

    def _get_callsign_from_header(self, filepath: str) -> str:
        """
        Reads just the CALLSIGN: line from a Cabrillo file.
        """
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.upper().startswith('CALLSIGN:'):
                        return line.split(':', 1)[1].strip()
        except Exception as e:
            logging.warning(f"Could not read callsign from {filepath}: {e}")
        return "Unknown"

    def get_logs(self):
        return self.logs