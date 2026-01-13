# contest_tools/report_generator.py
#
# Purpose: This class orchestrates the generation of reports.
#          It takes a list of loaded ContestLog objects and user-specified options,
#          then uses the properties of each available report class to determine how to
#          execute it (e.g., single-log, pairwise, multi-log).
#
# Copyright (c) 2025 Mark Bailey, KD4D
# Contact: kd4d@kd4d.org
#
# License: Mozilla Public License, v. 2.0
#          ([https://www.mozilla.org/MPL/2.0/](https://www.mozilla.org/MPL/2.0/))
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0.
# If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import itertools
import importlib
import logging
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple
from .reports import AVAILABLE_REPORTS
from .manifest_manager import ManifestManager
from .utils.report_utils import _sanitize_filename_part
from .utils.profiler import profile_section, ProfileContext
from .data_aggregators.time_series import TimeSeriesAggregator
from .data_aggregators.matrix_stats import MatrixAggregator

class ReportGenerator:
    """
    Handles the logic of selecting, configuring, and running one or more reports.
    """
    def __init__(self, logs, root_output_dir="reports"):
        """
        Initializes the ReportGenerator and creates the unique output directory path.

        Args:
            logs (list): A list of loaded ContestLog objects.
            root_output_dir (str): The root directory for all report output.
        """
        if not logs:
            raise ValueError("ReportGenerator must be initialized with at least one log.")
        self.logs = logs
        
        # --- Define Fully Unique Output Directory Structure ---
        
        first_log = self.logs[0]
        contest_name = first_log.get_metadata().get('ContestName', 'UnknownContest').replace(' ', '_').lower()
        
        df = first_log.get_processed_data()
        year = df['Date'].dropna().iloc[0].split('-')[0] if not df.empty and not df['Date'].dropna().empty else "UnknownYear"

        # --- Get Event ID from Resolver (if defined) ---
        event_id = ""
        resolver_name = first_log.contest_definition.contest_specific_event_id_resolver
        if resolver_name:
            try:
                resolver_module = importlib.import_module(f"contest_tools.event_resolvers.{resolver_name}")
                first_qso_time = df['Datetime'].iloc[0]
                event_id = resolver_module.resolve_event_id(first_qso_time)
            except (ImportError, AttributeError, IndexError) as e:
                logging.warning(f"Could not run event ID resolver '{resolver_name}': {e}")
                event_id = "UnknownEvent"

        # --- Get Callsign Combination ID ---
        all_calls = sorted([log.get_metadata().get('MyCall', f'Log{i+1}') for i, log in enumerate(self.logs)])
        callsign_combo_id = '_'.join([_sanitize_filename_part(c) for c in all_calls])

        # --- Construct Final Path ---
        self.base_output_dir = os.path.join(root_output_dir, 'reports', year, contest_name, event_id.lower(), callsign_combo_id)
        self.text_output_dir = os.path.join(self.base_output_dir, "text")
        self.plots_output_dir = os.path.join(self.base_output_dir, "plots")
        self.charts_output_dir = os.path.join(self.base_output_dir, "charts")
        self.animations_output_dir = os.path.join(self.base_output_dir, "animations")
        
        self.manifest = ManifestManager(self.base_output_dir)
        
        # --- Phase 1 Performance Optimization: Shared Aggregators and Caching ---
        # Create shared aggregator instances once to avoid recreating for each report
        with ProfileContext("ReportGenerator - Aggregator Initialization"):
            self._ts_aggregator = TimeSeriesAggregator(self.logs)
            self._matrix_aggregator = MatrixAggregator(self.logs)
            
            # Cache for time series data (key: (band_filter, mode_filter))
            self._ts_data_cache: Dict[Tuple[Optional[str], Optional[str]], Dict[str, Any]] = {}
            # Cache for matrix data (key: (bin_size, mode_filter, time_index_hash))
            self._matrix_data_cache: Dict[Tuple[str, Optional[str], Optional[str]], Dict[str, Any]] = {}
            # Cache for stacked matrix data (key: (bin_size, mode_filter, time_index_hash))
            self._stacked_matrix_data_cache: Dict[Tuple[str, Optional[str], Optional[str]], Dict[str, Any]] = {}
    
    def _get_cached_ts_data(self, band_filter: Optional[str] = None, mode_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Gets cached time series data or computes and caches it.
        
        Args:
            band_filter: Optional band filter (e.g., '20M')
            mode_filter: Optional mode filter (e.g., 'CW')
        
        Returns:
            Cached or newly computed time series data
        """
        cache_key = (band_filter, mode_filter)
        if cache_key not in self._ts_data_cache:
            self._ts_data_cache[cache_key] = self._ts_aggregator.get_time_series_data(
                band_filter=band_filter, mode_filter=mode_filter
            )
        return self._ts_data_cache[cache_key]
    
    def _get_cached_matrix_data(self, bin_size: str = '15min', mode_filter: Optional[str] = None, 
                                time_index: Optional[pd.DatetimeIndex] = None) -> Dict[str, Any]:
        """
        Gets cached matrix data or computes and caches it.
        
        Args:
            bin_size: Pandas frequency string (default '15min')
            mode_filter: Optional mode filter (e.g., 'CW')
            time_index: Optional pre-calculated DatetimeIndex
        
        Returns:
            Cached or newly computed matrix data
        """
        # Create a hash of time_index for cache key (or None if not provided)
        time_index_hash = None
        if time_index is not None:
            # Use a simple hash based on start, end, and freq
            time_index_hash = f"{time_index[0]}_{time_index[-1]}_{len(time_index)}"
        
        cache_key = (bin_size, mode_filter, time_index_hash)
        if cache_key not in self._matrix_data_cache:
            self._matrix_data_cache[cache_key] = self._matrix_aggregator.get_matrix_data(
                bin_size=bin_size, mode_filter=mode_filter, time_index=time_index
            )
        return self._matrix_data_cache[cache_key]
    
    def _get_cached_stacked_matrix_data(self, bin_size: str = '60min', mode_filter: Optional[str] = None, 
                                         time_index: Optional[pd.DatetimeIndex] = None) -> Dict[str, Any]:
        """
        Gets cached stacked matrix data or computes and caches it.
        
        Args:
            bin_size: Pandas frequency string (default '60min')
            mode_filter: Optional mode filter (e.g., 'CW')
            time_index: Optional pre-calculated DatetimeIndex
        
        Returns:
            Cached or newly computed stacked matrix data
        """
        # Create a hash of time_index for cache key (or None if not provided)
        time_index_hash = None
        if time_index is not None:
            # Use a simple hash based on start, end, and freq
            time_index_hash = f"{time_index[0]}_{time_index[-1]}_{len(time_index)}"
        
        cache_key = (bin_size, mode_filter, time_index_hash)
        if cache_key not in self._stacked_matrix_data_cache:
            self._stacked_matrix_data_cache[cache_key] = self._matrix_aggregator.get_stacked_matrix_data(
                bin_size=bin_size, mode_filter=mode_filter, time_index=time_index
            )
        return self._stacked_matrix_data_cache[cache_key]
    
    def _prepare_report_kwargs(self, logs: List[Any], **base_kwargs) -> Dict[str, Any]:
        """
        Prepares kwargs for report generation, including cached aggregators and data.
        
        Args:
            logs: List of logs for this specific report instance
            **base_kwargs: Base kwargs to pass through
        
        Returns:
            Enhanced kwargs with cached aggregators
        """
        kwargs = base_kwargs.copy()
        
        # Add cached aggregators (reports can use these instead of creating new ones)
        kwargs['_cached_ts_aggregator'] = self._ts_aggregator
        kwargs['_cached_matrix_aggregator'] = self._matrix_aggregator
        
        # Add helper methods to get cached data
        kwargs['_get_cached_ts_data'] = self._get_cached_ts_data
        kwargs['_get_cached_matrix_data'] = self._get_cached_matrix_data
        kwargs['_get_cached_stacked_matrix_data'] = self._get_cached_stacked_matrix_data
        
        return kwargs

    @profile_section("Report Generation (All Reports)")
    def run_reports(self, report_id, **report_kwargs):
        """
        Executes the requested reports based on the report_id and options.
        """
        reports_to_run = []
        report_id_lower = report_id.lower()

        if report_id_lower == 'all':
            reports_to_run = list(AVAILABLE_REPORTS.items())
        elif report_id_lower in ['chart', 'text', 'plot', 'animation', 'html']:
            reports_to_run = [
                (r_id, RClass) for r_id, RClass in AVAILABLE_REPORTS.items()
                if RClass.report_type == report_id_lower
            ]
        elif report_id in AVAILABLE_REPORTS:
            reports_to_run = [(report_id, AVAILABLE_REPORTS[report_id])]
        else:
            logging.error(f"Report '{report_id}' not found.")
            return

        if not reports_to_run:
            logging.warning(f"No reports found for category '{report_id}'.")
            return

        first_log = self.logs[0]
        contest_def = first_log.contest_definition
        included_reports = contest_def.included_reports

        # Filter out excluded reports before iterating
        final_reports_to_run = [
            (r_id, RClass) for r_id, RClass in reports_to_run
            if (
                r_id not in contest_def.excluded_reports and
                (not RClass.is_specialized or r_id in included_reports)
            )
        ]

        def get_all_files(directory):
            """Helper to recursively list all files in the output directory."""
            file_set = set()
            if not os.path.exists(directory):
                return file_set
            for root, dirs, files in os.walk(directory):
                for file in files:
                    # Store path relative to the base output dir
                    rel_path = os.path.relpath(os.path.join(root, file), self.base_output_dir)
                    file_set.add(rel_path)
            return file_set

        # Initial snapshot
        files_before = get_all_files(self.base_output_dir)

        for r_id, ReportClass in final_reports_to_run:
            report_type = ReportClass.report_type
            if report_type == 'text': output_path = self.text_output_dir
            elif report_type == 'plot': output_path = self.plots_output_dir
            elif report_type == 'chart': output_path = self.charts_output_dir
            elif report_type == 'animation': output_path = self.animations_output_dir
            else: output_path = self.base_output_dir

            # --- SYSTEMIC FIX: Scaffold Output Directory ---
            # Ensures the specific report type sub-directory (e.g., /plots) exists
            # before passing it to the plugin. Required for dynamic sessions.
            os.makedirs(output_path, exist_ok=True)

            is_multiplier_report = r_id in ['missed_multipliers', 'multiplier_summary', 'multipliers_by_hour']

            # --- MUTUALLY EXCLUSIVE LOGIC PATHS ---
            if is_multiplier_report:
                # --- Path 1: Multiplier Reports ---
                log_location_type = first_log._my_location_type
                all_rules = contest_def.multiplier_rules
                applicable_rules = [r for r in all_rules if r.get('applies_to') is None or r.get('applies_to') == log_location_type]
                
                mult_rules_to_run = []
                user_spec_mult = report_kwargs.get('mult_name')
                if user_spec_mult:
                    rule = next((r for r in applicable_rules if r.get('name', '').lower() == user_spec_mult.lower()), None)
                    if rule:
                        mult_rules_to_run.append(rule)
                else:
                    mult_rules_to_run = applicable_rules

                modes_to_run = [None] # Default for non-per-mode contests
                if contest_def.multiplier_report_scope == 'per_mode':
                    modes_to_run = pd.concat([log.get_processed_data()['Mode'] for log in self.logs]).dropna().unique()

                logging.info(f"\nGenerating report: '{ReportClass.report_name}'...")
                for mode in modes_to_run:
                    if mode:
                        logging.info(f"--- Analyzing Mode: {mode} ---")
                    
                    for mult_rule in mult_rules_to_run:
                        mult_name = mult_rule.get('name')
                        if not mult_name:
                            continue

                        logging.info(f"  - Generating for: {mult_name}")
                        current_kwargs = report_kwargs.copy()
                        current_kwargs['mult_name'] = mult_name
                        if mode:
                            current_kwargs['mode_filter'] = mode
                        
                        if ReportClass.supports_single:
                            for log in self.logs:
                                instance = ReportClass([log])
                                try:
                                    enhanced_kwargs = self._prepare_report_kwargs([log], **current_kwargs)
                                    result = instance.generate(output_path=output_path, **enhanced_kwargs)
                                    logging.info(result)
                                except Exception as e:
                                    logging.error(f"Error generating '{r_id}': {e}")
                        
                        if ReportClass.supports_multi and len(self.logs) >= 2:
                            # 1. Generate Session Summary (All Logs)
                            instance = ReportClass(self.logs)
                            try:
                                enhanced_kwargs = self._prepare_report_kwargs(self.logs, **current_kwargs)
                                result = instance.generate(output_path=output_path, **enhanced_kwargs)
                                logging.info(result)
                            except Exception as e:
                                logging.error(f"Error generating '{r_id}' (Session): {e}")

                        # 2. Generate Pairwise Comparisons (if > 2 logs)
                        if ReportClass.supports_pairwise and len(self.logs) > 2:
                                for log_pair in itertools.combinations(self.logs, 2):
                                    instance = ReportClass(list(log_pair))
                                    try:
                                        enhanced_kwargs = self._prepare_report_kwargs(list(log_pair), **current_kwargs)
                                        result = instance.generate(output_path=output_path, **enhanced_kwargs)
                                        logging.info(result)
                                    except Exception as e:
                                        logging.error(f"Error generating '{r_id}' (Pair): {e}")
            
            else:
                # --- Path 2: Non-Multiplier Reports ---
                logging.info(f"\nGenerating report: '{ReportClass.report_name}'...")
                
                if ReportClass.supports_multi and len(self.logs) >= 2:
                    instance = ReportClass(self.logs)
                    try:
                        enhanced_kwargs = self._prepare_report_kwargs(self.logs, **report_kwargs)
                        result = instance.generate(output_path=output_path, **enhanced_kwargs)
                        logging.info(result)
                    except Exception as e:
                        logging.error(f"Error generating '{r_id}': {e}")

                if ReportClass.supports_pairwise and len(self.logs) >= 2:
                    for log_pair in itertools.combinations(self.logs, 2):
                        instance = ReportClass(list(log_pair))
                        try:
                            enhanced_kwargs = self._prepare_report_kwargs(list(log_pair), **report_kwargs)
                            result = instance.generate(output_path=output_path, **enhanced_kwargs)
                            logging.info(result)
                        except Exception as e:
                            logging.error(f"Error generating '{r_id}': {e}")

                if ReportClass.supports_single:
                    for log in self.logs:
                        instance = ReportClass([log])
                        try:
                            enhanced_kwargs = self._prepare_report_kwargs([log], **report_kwargs)
                            result = instance.generate(output_path=output_path, **enhanced_kwargs)
                            logging.info(result)
                        except Exception as e:
                            logging.error(f"Error generating '{r_id}': {e}")

            # --- Post-Execution Snapshot ---
            # Detect new files generated by this specific report ID
            files_now = get_all_files(self.base_output_dir)
            new_files = files_now - files_before
            for new_file in new_files:
                self.manifest.add_artifact(r_id, new_file, report_type)
            files_before = files_now # Update baseline
            
        self.manifest.save()