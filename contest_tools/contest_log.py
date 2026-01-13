# contest_tools/contest_log.py
#
# Purpose: Defines the ContestLog class, which manages the ingestion, processing,
#          and analysis of Cabrillo log data. It orchestrates the parsing,
#          data cleaning, and calculation of various contest metrics.
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

from typing import List
import pandas as pd
import numpy as np
from datetime import datetime
from pandas.tseries.offsets import WeekOfMonth
from typing import Dict, Any, Optional, Set, Tuple
import os
import re
import json
import importlib
import logging

# Relative imports from within the contest_tools package
from .cabrillo_parser import parse_cabrillo_file
from .contest_definitions import ContestDefinition
from .core_annotations import CtyLookup, process_dataframe_for_cty_data, process_contest_log_for_run_s_p, BandAllocator
from .utils.profiler import profile_section, ProfileContext

class ContestLog:
    """
    High-level broker class to manage a single amateur radio contest log.
    """
    _ADIF_TIMESTAMP_OFFSET_SECONDS = 2

    _HAM_BANDS = [
        (( 1800.,  2000.), '160M'),
        (( 3500.,  4000.), '80M'),
        (( 7000.,  7300.), '40M'),
        ((10100., 10150.), '30M'),
        ((14000., 14350.), '20M'),
        ((18068., 18168.), '17M'),
        ((21000., 21450.), '15M'),
        ((24890., 24990.), '12M'),
        ((28000., 29700.), '10M'),
        ((50000., 54000.), '6M'),
        ((144000., 148000.), '2M'),
        ((222000., 225000.), '222MHz'),
        ((420000., 450000.), '432MHz'),
        (None, 'SAT') # Satellite has no fixed frequency range
    ]

    @staticmethod
    def _derive_band_from_frequency(frequency_khz: float) -> str:
        if pd.isna(frequency_khz):
            return 'Invalid'
        frequency_int = int(frequency_khz)
        for band_range, band_name in ContestLog._HAM_BANDS:
            if band_range and (band_range[0] <= frequency_int <= band_range[1]):
                return band_name
        return 'Invalid'

    def __init__(self, contest_name: str, cabrillo_filepath: str, root_input_dir: str, cty_dat_path: str, 
                 shared_cty_lookup=None, shared_band_allocator=None):
        self.contest_name = contest_name
        self.qsos_df: pd.DataFrame = pd.DataFrame()
        self.qtcs_df: pd.DataFrame = pd.DataFrame()
        self.time_series_score_df: pd.DataFrame = pd.DataFrame()
        self.metadata: Dict[str, Any] = {}
        self.metadata['ContestName'] = contest_name
        
        self.dupe_sets: Dict[str, Set[Tuple[str, str]]] = {}
        self.filepath = cabrillo_filepath
        self.cty_dat_path = cty_dat_path
    
        self._my_location_type: Optional[str] = None # W/VE or DX
        self._log_manager_ref = None
        
        # Performance optimization: Use shared instances if provided to avoid reloading from disk
        self._shared_cty_lookup = shared_cty_lookup
        self.band_allocator = shared_band_allocator if shared_band_allocator else BandAllocator(root_input_dir)
        
        self.root_input_dir = root_input_dir
        if root_input_dir is None:
            raise ValueError("ContestLog requires a root_input_dir.")

        try:
            self.contest_definition = ContestDefinition.from_json(contest_name)
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Failed to load contest definition for '{contest_name}': {e}")

        if cabrillo_filepath:
            self._ingest_cabrillo_data(cabrillo_filepath)
        
        # Run a custom location resolver if defined for the contest.
        resolver_name = self.contest_definition.custom_location_resolver
        if resolver_name:
            try:
                resolver_module = importlib.import_module(f"contest_tools.contest_specific_annotations.{resolver_name}")
                self._my_location_type = resolver_module.resolve_location_type(self.metadata, self.cty_dat_path)
                logging.info(f"Custom logger location type determined as: '{self._my_location_type}' by {resolver_name}")
            except Exception as e:
                logging.warning(f"Could not run custom location resolver '{resolver_name}': {e}")
        else:
            # Fallback to old generic method for legacy asymmetric contests
            self._determine_own_location_type_legacy()

    def _filter_by_contest_period(self, df: pd.DataFrame, is_qso_df: bool) -> pd.DataFrame:
        """
        Filters a DataFrame (QSOs or QTCs) to include only records within the
        contest's valid time period.
        """
        if df.empty or 'Datetime' not in df.columns:
            return df

        df['Datetime'] = pd.to_datetime(df['Datetime'], errors='coerce', utc=True)
        df.dropna(subset=['Datetime'], inplace=True)
        if df.empty:
            return df

        contest_name = self.contest_definition.contest_name
        log_date = df['Datetime'].iloc[0]
        
        DAY_NAME_TO_INT = {
            'MONDAY': 0, 'TUESDAY': 1, 'WEDNESDAY': 2, 'THURSDAY': 3,
            'FRIDAY': 4, 'SATURDAY': 5, 'SUNDAY': 6
        }

        # --- Special Case: NAQP ---
        if contest_name.startswith("NAQP"):
            mode_from_contest = df['Mode'].iloc[0]
            month = log_date.month
            # (start_weekday, week_of_month [0-indexed], start_time_utc) Saturday is 5
            rules = {
                ('CW', 1): (5, 1, "18:00:00"),   # Jan CW: 2nd Saturday
                ('CW', 8): (5, 0, "18:00:00"),   # Aug CW: 1st Saturday
                ('PH', 1): (5, 2, "18:00:00"),   # Jan SSB: 3rd Saturday
                ('PH', 8): (5, 2, "18:00:00"),   # Aug SSB: 3rd Saturday
                ('RTTY', 2): (5, 3, "18:00:00"), # Feb RTTY: 4th Saturday
                ('RTTY', 7): (5, 1, "18:00:00"), # Jul RTTY: 2nd Saturday
            }
            rule = rules.get((mode_from_contest, month))
            if not rule:
                logging.warning(f"No valid contest period rule found for NAQP-{mode_from_contest} in month {month}.")
                return df # Return unfiltered
            
            first_day_of_month = log_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            start_day = first_day_of_month + WeekOfMonth(week=rule[1], weekday=rule[0])
            start_time = pd.to_datetime(start_day.strftime('%Y-%m-%d') + ' ' + rule[2], utc=True)
            end_time = start_time + pd.Timedelta(hours=12) # NAQP is a 12-hour contest
        else:
            period = self.contest_definition.contest_period
            if not period:
                return df # No period defined, return unfiltered

            start_time_str = period['start_time']
            end_time_str = period['end_time']
            start_weekday = DAY_NAME_TO_INT[period['start_day'].upper()]
            end_weekday = DAY_NAME_TO_INT[period['end_day'].upper()]

            # Find the actual start date by finding the specified weekday relative to the log's date
            days_to_subtract = (log_date.weekday() - start_weekday + 7) % 7
            start_date = log_date - pd.to_timedelta(days_to_subtract, unit='d')
            start_time = pd.to_datetime(start_date.strftime('%Y-%m-%d') + ' ' + start_time_str, utc=True)

            days_to_add = (end_weekday - start_weekday + 7) % 7
            end_date = start_date + pd.to_timedelta(days_to_add, unit='d')
            end_time = pd.to_datetime(end_date.strftime('%Y-%m-%d') + ' ' + end_time_str, utc=True)

        initial_count = len(df)
        # Use < end_time for an exclusive upper bound, which is standard for time ranges.
        df_filtered = df[(df['Datetime'] >= start_time) & (df['Datetime'] < end_time)].copy()
        
        # --- Special Case: ARRL-FIELD-DAY Relative 24-Hour Window ---
        if contest_name == "ARRL-FIELD-DAY" and not df_filtered.empty:
            first_qso_time = df_filtered['Datetime'].min()
            limit_time = first_qso_time + pd.Timedelta(hours=24)
            df_filtered = df_filtered[df_filtered['Datetime'] < limit_time]

        removed_count = initial_count - len(df_filtered)
        if removed_count > 0:
            data_type = "QSOs" if is_qso_df else "QTCs"
            logging.info(f"Filtered out {removed_count} out-of-bounds {data_type} based on contest period.")
            
        return df_filtered

    @profile_section("Cabrillo Data Ingestion")
    def _ingest_cabrillo_data(self, cabrillo_filepath: str):
        custom_parser_name = self.contest_definition.custom_parser_module
        if custom_parser_name:
            try:
                parser_module = importlib.import_module(f"contest_tools.contest_specific_annotations.{custom_parser_name}")
                
                # The custom parser's return signature determines how we unpack
                parser_output = parser_module.parse_log(cabrillo_filepath, self.contest_definition, self.root_input_dir, self.cty_dat_path)
                
                if len(parser_output) == 3:
                    raw_df, self.qtcs_df, metadata = parser_output
                else:
                    raw_df, metadata = parser_output
                    self.qtcs_df = pd.DataFrame() # Ensure it's initialized
                
                logging.info(f"Using custom parser module: '{custom_parser_name}'")
            except Exception as e:
                logging.error(f"Could not run custom parser '{custom_parser_name}': {e}. Halting.")
                raise
        else:
            raw_df, metadata = parse_cabrillo_file(cabrillo_filepath, self.contest_definition)
        
        # Preserve the contest_name from the constructor (e.g., from --wrtc flag)
        # by removing the one parsed from the file header before updating metadata.
        metadata.pop('ContestName', None)
        
        self.metadata.update(metadata)
        
        if raw_df.empty:
            self.qsos_df = pd.DataFrame(columns=self.contest_definition.default_qso_columns)
            return

        # --- Perform frequency validation before further processing ---
        validated_qso_records = []
        rejected_qso_count = 0
        raw_df['Frequency'] = pd.to_numeric(raw_df.get('FrequencyRaw'), errors='coerce')

        for idx, row in raw_df.iterrows():
            freq_val = row['Frequency']
            band_val = row.get('Band')

            # A QSO is valid if it has a valid frequency OR if it has a band but no numeric frequency.
            if (pd.notna(freq_val) and self.band_allocator.is_frequency_valid(freq_val)) or \
               (pd.isna(freq_val) and pd.notna(band_val)):
                validated_qso_records.append(row.to_dict())
            else:
                rejected_qso_count += 1
                if rejected_qso_count <= 20:
                    logging.warning(f"Rejected QSO (invalid frequency): File '{os.path.basename(cabrillo_filepath)}' - Line: {row['RawQSO']}")
        
        if rejected_qso_count > 20:
            suppressed_count = rejected_qso_count - 20
            logging.warning(f"({suppressed_count} additional invalid frequency warnings suppressed for this file.)")

        if not validated_qso_records:
            self.qsos_df = pd.DataFrame(columns=self.contest_definition.default_qso_columns)
            return

        raw_df = pd.DataFrame(validated_qso_records)
        
        raw_df['Datetime'] = pd.to_datetime(
            raw_df.get('DateRaw', '') + ' ' + raw_df.get('TimeRaw', ''),
            format='%Y-%m-%d %H%M',
            errors='coerce'
        ).dt.tz_localize('UTC')
        
        # If a 'Band' column wasn't provided by the parser, create it.
        if 'Band' not in raw_df.columns:
            raw_df['Band'] = pd.NA

        # Handle frequency-derived bands only where a band isn't already specified.
        if 'Frequency' in raw_df.columns:
            # Create a temporary column for bands derived from frequency
            derived_bands = raw_df['Frequency'].apply(self._derive_band_from_frequency)
            
            # Merge the results: use the existing Band value if present, otherwise use the derived one.
            raw_df['Band'] = raw_df['Band'].combine_first(derived_bands)

        raw_df.dropna(subset=['Datetime'], inplace=True)

        # --- Apply Contest Period Filter ---
        raw_df = self._filter_by_contest_period(raw_df, is_qso_df=True)
        if not self.qtcs_df.empty:
            self.qtcs_df = self._filter_by_contest_period(self.qtcs_df, is_qso_df=False)

        if raw_df.empty:
            self.qsos_df = pd.DataFrame(columns=self.contest_definition.default_qso_columns)
            return

        raw_df['Date'] = raw_df['Datetime'].dt.strftime('%Y-%m-%d')
        raw_df['Hour'] = raw_df['Datetime'].dt.strftime('%H')

        for col in ['MyCallRaw', 'Call', 'Mode']:
            if col in raw_df.columns:
                raw_df[col.replace('Raw','')] = raw_df[col].fillna('').astype(str).str.upper()

        # --- Check for non-standard modes ---
        standard_modes = {'CW', 'PH', 'DG'}
        present_modes = set(raw_df['Mode'].dropna().unique())
        non_standard_modes = present_modes - standard_modes
        if non_standard_modes:
            logging.warning(
                f"Non-standard modes found in '{os.path.basename(cabrillo_filepath)}': "
                f"{sorted(list(non_standard_modes))}. These will be processed but may not be "
                "handled correctly by all reports."
            )

        raw_df.drop(columns=['FrequencyRaw', 'DateRaw', 'TimeRaw', 'MyCallRaw', 'RawQSO'], inplace=True, errors='ignore')
        self.qsos_df = raw_df.reindex(columns=self.contest_definition.default_qso_columns)

        self._check_dupes()

    def _check_dupes(self):
        self.qsos_df['Dupe'] = False
        self.dupe_sets.clear()
        
        dupe_scope = self.contest_definition.dupe_check_scope
        
        if dupe_scope == 'all_bands':
            all_bands_dupe_set = set()
            for idx in self.qsos_df.index:
                call = self.qsos_df.loc[idx, 'Call']
                if not call:
                    continue
                if call in all_bands_dupe_set:
                    self.qsos_df.loc[idx, 'Dupe'] = True
                else:
                    all_bands_dupe_set.add(call)
        
        else:
            for band in self.qsos_df['Band'].unique():
                if band == 'Invalid' or not band:
                    continue
                
                self.dupe_sets[band] = set()
                band_indices = self.qsos_df[self.qsos_df['Band'] == band].index
                
                for idx in band_indices:
                    call = self.qsos_df.loc[idx, 'Call']
                    mode = self.qsos_df.loc[idx, 'Mode']
                    
                    if not call or not mode:
                        continue
                    
                    qso_tuple = (call, mode)
                    
                    if qso_tuple in self.dupe_sets[band]:
                        self.qsos_df.loc[idx, 'Dupe'] = True
                    else:
                        self.dupe_sets[band].add(qso_tuple)

    def _calculate_operating_time(self) -> Optional[str]:
        rules = self.contest_definition.operating_time_rules
        if not rules:
            return None

        min_off_time = pd.Timedelta(minutes=rules.get('min_off_time_minutes', 30))
        
        df = self.qsos_df[self.qsos_df['Dupe'] == False].sort_values(by='Datetime')
        
        if len(df) < 2:
            return "00:00"

        total_duration = df['Datetime'].iloc[-1] - df['Datetime'].iloc[0]
        gaps = df['Datetime'].diff()
        off_time_gaps = gaps[gaps > min_off_time]
        total_off_time = off_time_gaps.sum()

        on_time = total_duration - total_off_time

        total_seconds = on_time.total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        on_time_str = f"{hours:02d}:{minutes:02d}"
        
        
        category = self.metadata.get('CategoryOperator', 'SINGLE-OP').upper()
        if 'MULTI' in category:
            max_hours = rules.get('multi_op_max_hours', 48)
        else:
            max_hours = rules.get('single_op_max_hours', 48)

        return f"{on_time_str} of {max_hours}:00 allowed"
        
    def _determine_own_location_type_legacy(self):
        """
        DEPRECATED: Generic method for determining location for ARRL DX.
        This will be replaced by the custom_location_resolver mechanism.
        """
        is_asymmetric = any(rule.get('applies_to') for rule in self.contest_definition.multiplier_rules)
        
        if is_asymmetric:
            my_call = self.metadata.get('MyCall')
            if my_call:
                # Use shared CTY lookup if available (performance optimization)
                cty_lookup = self._shared_cty_lookup if self._shared_cty_lookup else CtyLookup(cty_dat_path=self.cty_dat_path)
                info = cty_lookup.get_cty_DXCC_WAE(my_call)._asdict()
                
                self._my_location_type = "W/VE" if info['DXCCName'] in ["United States", "Canada"] else "DX"
                logging.info(f"LEGACY logger location type determined as: {self._my_location_type}")

    def apply_annotations(self):
        if self.qsos_df.empty:
            logging.warning("No QSOs loaded. Cannot apply annotations.")
            return

        # Pre-cast multiplier columns to 'object' to prevent dtype warnings when
        # string-based multipliers (e.g., from WAE/DXCC) are inserted later.
        for col in ['Mult1', 'Mult1Name', 'Mult2', 'Mult2Name']:
            if col in self.qsos_df.columns:
                self.qsos_df[col] = self.qsos_df[col].astype('object')

        try:
            logging.info("Applying Run/S&P annotation...")
            self.qsos_df = process_contest_log_for_run_s_p(self.qsos_df)
            logging.info("Run/S&P annotation complete.")
        except Exception as e:
            logging.error(f"Error during Run/S&P annotation: {e}. Skipping.")

        try:
            logging.info("Applying Universal DXCC/Zone lookup...")
            # Use shared CTY lookup if available (performance optimization)
            self.qsos_df = process_dataframe_for_cty_data(self.qsos_df, self.cty_dat_path, shared_cty_lookup=self._shared_cty_lookup)
            logging.info("Universal DXCC/Zone lookup complete.")
        except Exception as e:
            logging.error(f"Error during Universal DXCC/Zone lookup: {e}. Skipping.")
        
        self.apply_contest_specific_annotations()
        
        try:
            self.metadata['OperatingTime'] = self._calculate_operating_time()
        except Exception as e:
            logging.error(f"Error during on-time calculation: {e}. Skipping.")
        
    def _pre_calculate_time_series_score(self):
        """
        Dynamically selects and runs the appropriate time-series score calculator.
        """
        calculator_name = self.contest_definition.time_series_calculator
        if not calculator_name:
            calculator_name = "standard_calculator" # Default for all standard contests
            class_name = "StandardCalculator"
        else:
            # Convention: snake_case module -> CamelCase class
            class_name = "".join([part.capitalize() for part in calculator_name.split('_')])

        try:
            logging.info(f"Running time-series score calculator: '{calculator_name}'...")
            module = importlib.import_module(f"contest_tools.score_calculators.{calculator_name}")
            CalculatorClass = getattr(module, class_name)

            # --- Diagnostic Logging ("Before" Snapshot) ---
            df_non_dupes = self.qsos_df[self.qsos_df['Dupe'] == False].copy()


            mult_cols_present = [col for col in ['Mult_STPROV', 'Mult_NADXCC'] if col in df_non_dupes.columns]
 
            
            calculator_instance = CalculatorClass()
            
            self.time_series_score_df = calculator_instance.calculate(self, df_non_dupes)

        except (ImportError, AttributeError) as e:
            logging.exception(f"Failed to load or find score calculator '{class_name}'. See traceback.")
            raise e
        except Exception as e:
            logging.exception(f"An unexpected error occurred in score calculator '{class_name}'. See traceback.")
            raise e

    def apply_contest_specific_annotations(self):
        logging.info("Applying contest-specific annotations (Multipliers & Scoring)...")
        
        resolver_name = self.contest_definition.custom_multiplier_resolver
        if resolver_name:
            try:
                resolver_module = importlib.import_module(f"contest_tools.contest_specific_annotations.{resolver_name}")
                self.qsos_df = resolver_module.resolve_multipliers(self.qsos_df, self._my_location_type, self.root_input_dir, self.contest_definition)
                logging.info(f"Successfully applied '{resolver_name}' multiplier resolver.")
            except Exception as e:
                logging.warning(f"Could not run '{resolver_name}' multiplier resolver: {e}")

        multiplier_rules = self.contest_definition.multiplier_rules
        
        # The generic rules processor is required for the second stage of some multipliers (e.g. CQ-160).
        if multiplier_rules:
            logging.info("Calculating contest multipliers...")
            for rule in multiplier_rules:
                applies_to = rule.get('applies_to')
                if applies_to and self._my_location_type and applies_to != self._my_location_type:
                    continue
 
                
                dest_col = rule.get('value_column')
                dest_name_col = rule.get('name_column')
                
                if not dest_col: continue
 
                if 'source_column' in rule:
                    source_col = rule.get('source_column')
                    if source_col in self.qsos_df.columns:
                        self.qsos_df[dest_col] = self.qsos_df[source_col]
                        
                        if dest_name_col:
                            source_name_col = rule.get('source_name_column', f"{source_col}Name")
                            if source_name_col in self.qsos_df.columns:
                                self.qsos_df[dest_name_col] = self.qsos_df[source_name_col]
                            else:
                                logging.warning(f"Name column '{source_name_col}' not found for source '{source_col}'.")
                    
                    else:
                        logging.warning(f"Source column '{source_col}' not found for multiplier '{rule.get('name')}'.")
 
                elif rule.get('source') == 'wae_dxcc':
                    wae_mask = self.qsos_df['WAEName'].notna() & (self.qsos_df['WAEName'] != '')
                    
                    self.qsos_df.loc[wae_mask, dest_col] = self.qsos_df.loc[wae_mask, 'WAEPfx']
                    self.qsos_df.loc[~wae_mask, dest_col] = self.qsos_df.loc[~wae_mask, 'DXCCPfx']
                    
                    if dest_name_col:
                        self.qsos_df.loc[wae_mask, dest_name_col] = self.qsos_df.loc[wae_mask, 'WAEName']
                        self.qsos_df.loc[~wae_mask, dest_name_col] = self.qsos_df.loc[~wae_mask, 'DXCCName']
                
                elif rule.get('source') == 'calculation_module':
                    try:
                        module_name = rule['module_name']
                        function_name = rule['function_name']
                        
                        module = importlib.import_module(f"contest_tools.contest_specific_annotations.{module_name}")
                        calculation_func = getattr(module, function_name)
                        
                        self.qsos_df[dest_col] = calculation_func(self.qsos_df)
                        logging.info(f"Successfully applied '{function_name}' from '{module_name}'.")
                    except (ImportError, AttributeError, KeyError) as e:
                        logging.warning(f"Could not run calculation module for rule '{rule.get('name')}': {e}")


        
        # --- Scoring Calculation ---
        my_call = self.metadata.get('MyCall')
        if not my_call:
            logging.warning("'MyCall' not found in metadata. Cannot calculate QSO points.")
            self.qsos_df['QSOPoints'] = 0
            return
        
        try:
            cty_lookup = CtyLookup(cty_dat_path=self.cty_dat_path)
            my_call_info = cty_lookup.get_cty_DXCC_WAE(my_call)._asdict()
            my_call_info['MyCall'] = my_call
        except Exception as e:
            logging.warning(f"Could not determine own location for scoring due to CTY error: {e}")
            self.qsos_df['QSOPoints'] = 0
            return

        scoring_module_name = self.contest_definition.scoring_module
        try:
            if not scoring_module_name:
                raise ImportError(f"No 'scoring_module' key found in JSON definition for {self.contest_name}")
            scoring_module = importlib.import_module(f"contest_tools.contest_specific_annotations.{scoring_module_name}")
        except ImportError as e:
            logging.warning(f"Could not load scoring module for contest '{self.contest_name}': {e}. Points will be 0.")
            self.qsos_df['QSOPoints'] = 0
            return

        try:
            self.qsos_df['QSOPoints'] = scoring_module.calculate_points(self.qsos_df, my_call_info)
            logging.info(f"Scoring complete.")
        except Exception as e:
            logging.error(f"Error during {self.contest_name} scoring: {e}")
            self.qsos_df['QSOPoints'] = 0


    def export_to_csv(self, output_filepath: str):
        if self.qsos_df.empty:
            logging.warning(f"No QSOs to export. CSV file '{output_filepath}' will not be created.")
            return

        try:
            df_for_output = self.qsos_df.copy()
            
            if 'Datetime' in df_for_output.columns:
                df_for_output['Datetime'] = df_for_output['Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')

            df_for_output = df_for_output.reindex(columns=self.contest_definition.default_qso_columns)

            for col in df_for_output.columns:
                if pd.api.types.is_integer_dtype(df_for_output[col]) and isinstance(df_for_output[col].dtype, pd.Int64Dtype):
                    df_for_output[col] = df_for_output[col].astype(object)

            # Use the na_rep parameter to handle missing values directly in the CSV output
            df_for_output.to_csv(output_filepath, index=False, na_rep='')
            
            logging.info(f"Processed log saved to: {output_filepath}")
        except Exception as e:
            logging.error(f"Error exporting log to CSV '{output_filepath}': {e}")
            raise

    def export_to_adif(self, output_filepath: str, is_debug_hour: bool = False):
        """Generates a standard ADIF file from the processed log data."""
        if self.qsos_df.empty:
            message = f"No QSOs to export. ADIF file '{output_filepath}' will not be created."
            if is_debug_hour:
                logging.info(message)
            else:
                logging.warning(message)
            return
            
        df_to_export = self.qsos_df.copy()

        # --- Add per-second offset to identical timestamps for N1MM compatibility ---
        if 'Datetime' in df_to_export.columns and not df_to_export.empty:
            # Loop until all timestamps are unique, handling rollovers.
            while df_to_export['Datetime'].duplicated().any():
                offsets = df_to_export.groupby('Datetime').cumcount()
                time_deltas = pd.to_timedelta(offsets * self._ADIF_TIMESTAMP_OFFSET_SECONDS, unit='s')
                # Only apply the offset to the rows that are part of a duplicate group
                df_to_export.loc[df_to_export['Datetime'].duplicated(keep=False), 'Datetime'] += time_deltas
            df_to_export.sort_values(by='Datetime', inplace=True)

        # --- ADIF Helper Functions ---
        def adif_format(tag: str, value: Any) -> str:
            if pd.isna(value) or value == '':
                return ''
            val_str = str(int(value)) if isinstance(value, (float, np.floating, np.integer)) and float(value).is_integer() else str(value)
            return f"<{tag}:{len(val_str)}>{val_str} "

        # --- Generate ADIF Content ---
        adif_records = []
        adif_records.append("ADIF Export from Contest-Log-Analyzer\n")
        adif_records.append(f"<PROGRAMID:21>Contest-Log-Analytics\n")
        adif_records.append(f"<PROGRAMVERSION:10>0.52.7-Beta\n")
        adif_records.append("<EOH>\n\n")

        for _, row in df_to_export.iterrows():
            record = []
            record.append(adif_format('CALL', row.get('Call')))
            
            if pd.notna(row.get('Datetime')):
                record.append(f"<QSO_DATE:8>{row['Datetime'].strftime('%Y%m%d')} ")
                record.append(f"<TIME_ON:6>{row['Datetime'].strftime('%H%M%S')} ")

            if pd.notna(row.get('Band')):
                record.append(adif_format('BAND', str(row.get('Band')).lower()))

            record.append(adif_format('STATION_CALLSIGN', self.metadata.get('MyCall')))
            
            if pd.notna(row.get('Frequency')):
                freq_in_mhz = row.get('Frequency') / 1000
                freq_mhz = f"{freq_in_mhz:.3f}"
                record.append(adif_format('FREQ', freq_mhz))
                record.append(adif_format('FREQ_RX', freq_mhz))

            record.append(adif_format('CONTEST_ID', self.metadata.get('ContestName')))
            
            # Get the mode from the DataFrame row
            mode = row.get('Mode')
            
            
            # Check if the mode is one of the standard phone modes
            if mode in ['PH', 'USB', 'LSB', 'SSB']:
                output_mode = 'SSB'
            else:
                # Otherwise, use the mode as-is (e.g., for CW, DG)
                output_mode = mode
            # Append the formatted ADIF tag to the record
            record.append(adif_format('MODE', output_mode))
            
            rst_rcvd = row.get('RST') if pd.notna(row.get('RST')) else row.get('RS')
            record.append(adif_format('RST_RCVD', rst_rcvd))
            
            rst_sent = row.get('SentRST') if pd.notna(row.get('SentRST')) else row.get('SentRS')
            record.append(adif_format('RST_SENT', rst_sent))
            
            record.append(adif_format('OPERATOR', self.metadata.get('MyCall')))
            record.append(adif_format('CQZ', row.get('CQZone')))
            record.append(adif_format('ITUZ', row.get('ITUZone')))
            
            
            # Add custom CLA tag for CTY-derived CQ Zone for diagnostics
            record.append(adif_format('APP_CLA_CQZ', row.get('CQZone')))
            
            if pd.notna(row.get('RcvdLocation')):
                record.append(adif_format('STATE', row.get('RcvdLocation')))
                record.append(adif_format('ARRL_SECT', row.get('RcvdLocation')))

            # --- Custom CLA Tags ---
            record.append(adif_format('APP_CLA_QSO_POINTS', row.get('QSOPoints')))
            record.append(adif_format('APP_CLA_CONTINENT', row.get('Continent')))
            if row.get('Run') == 'Run': record.append(adif_format('APP_CLA_ISRUNQSO', 1))
            
            mult_value_cols = [c for c in row.index if c.startswith('Mult_') or c in ['Mult1', 'Mult2']]
            for col in mult_value_cols:
                if pd.notna(row.get(col)):
                    record.append(adif_format(f"APP_CLA_{col.upper()}", row.get(col)))

            mult_flag_cols = [c for c in row.index if c.endswith('_IsNewMult')]

            for col in mult_flag_cols:
                if row.get(col) == 1:
                    record.append(adif_format(f"APP_CLA_{col.upper()}", 1))

            adif_records.append("".join(record).strip() + " <EOR>\n")

        # --- Write to File ---
        try:
            with open(output_filepath, 'w', encoding='utf-8') as f:
                f.writelines(adif_records)
            logging.info(f"ADIF log saved to: {output_filepath}")
        except Exception as e:
            logging.error(f"Error exporting log to ADIF '{output_filepath}': {e}")
            raise

    def get_processed_data(self) -> pd.DataFrame:
        return self.qsos_df

    def get_metadata(self) -> Dict[str, Any]:
        return self.metadata