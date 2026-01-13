# contest_tools/core_annotations/run_s_p.py
#
# Purpose: This utility infers whether each contact in an amateur radio contest log
#          was made while "Running" (CQing), "Search & Pounce" (S&P), or if the
#          activity rate is too low to be certain ("Unknown").
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

import pandas as pd
from collections import deque
import os
import sys
import traceback
import logging

# --- Constants ---
DEFAULT_RUN_TIME_WINDOW_MINUTES = 10
DEFAULT_FREQ_TOLERANCE_CW = 0.1
DEFAULT_FREQ_TOLERANCE_PH = 0.5
DEFAULT_MIN_QSO_FOR_RUN = 3
RUN_BREAK_QSO_COUNT = 3
RUN_BREAK_TIME_MINUTES = 2
# --- Constants for "Unknown" classification ---
DEFAULT_UNKNOWN_WINDOW_MINUTES = 15
DEFAULT_UNKNOWN_QSO_THRESHOLD = 4


def _get_run_info_from_buffer(base_freq: float, buffer_to_check: deque, min_qso: int, time_threshold: pd.Timedelta, tol: float):
    """
    Helper to check if a given `base_freq` forms a valid run within the `buffer_to_check`.
    """
    relevant_qso_data = []
    for buffered_idx, buffered_time, buffered_freq in buffer_to_check:
        if abs(buffered_freq - base_freq) <= tol:
            relevant_qso_data.append((buffered_idx, buffered_time))

    if len(relevant_qso_data) < min_qso:
        return False, []

    for i in range(len(relevant_qso_data) - 1, min_qso - 2, -1):
        latest_time_in_segment = relevant_qso_data[i][1]
        oldest_time_in_segment = relevant_qso_data[i - (min_qso - 1)][1]
        if (latest_time_in_segment - oldest_time_in_segment) <= time_threshold:
            qualifying_indices = [q[0] for q in relevant_qso_data[i - (min_qso - 1) : i + 1]]
            return True, qualifying_indices
    return False, []

def _evaluate_single_stream_run(
    stream_df_original: pd.DataFrame, 
    datetime_column: str,
    frequency_column: str,
    stream_tolerance: float,
    time_delta_threshold: pd.Timedelta,
    min_qso_for_run: int
):
    """
    Pass 1: Evaluates run status for a single operational stream using a "sticky run" state machine.
    Classifies QSOs as either 'Run' or 'S&P'.
    """
    inferred_run_status = ['S&P'] * len(stream_df_original)
    original_idx_to_list_pos = {idx: i for i, idx in enumerate(stream_df_original.index)}

    active_run_freq = None
    last_qso_on_run_freq_time = None
    off_frequency_qso_count = 0
    potential_new_run_freq = None
    qso_buffer = deque()

    for list_pos, original_df_idx in enumerate(stream_df_original.index):
        current_qso_time = stream_df_original.at[original_df_idx, datetime_column]
        current_qso_freq = stream_df_original.at[original_df_idx, frequency_column]
        
        qso_buffer.append((original_df_idx, current_qso_time, current_qso_freq))
        while qso_buffer and (current_qso_time - qso_buffer[0][1]) > time_delta_threshold:
            qso_buffer.popleft()

        if active_run_freq is not None:
            is_on_run_freq = abs(current_qso_freq - active_run_freq) <= stream_tolerance
            timed_out = (current_qso_time - last_qso_on_run_freq_time) > pd.Timedelta(minutes=RUN_BREAK_TIME_MINUTES)

            if is_on_run_freq and not timed_out:
                inferred_run_status[list_pos] = 'Run'
                last_qso_on_run_freq_time = current_qso_time
                off_frequency_qso_count = 0
                potential_new_run_freq = None
            else:
                inferred_run_status[list_pos] = 'S&P'
                if not is_on_run_freq:
                    if potential_new_run_freq and abs(current_qso_freq - potential_new_run_freq) <= stream_tolerance:
                        off_frequency_qso_count += 1
                    else:
                        potential_new_run_freq = current_qso_freq
                        off_frequency_qso_count = 1
                
                if timed_out or off_frequency_qso_count >= RUN_BREAK_QSO_COUNT:
                    active_run_freq = None
        
        if active_run_freq is None:
            is_new_run, new_run_indices = _get_run_info_from_buffer(
                current_qso_freq, qso_buffer, min_qso_for_run, time_delta_threshold, stream_tolerance
            )
            if is_new_run:
                active_run_freq = current_qso_freq
                last_qso_on_run_freq_time = current_qso_time
                off_frequency_qso_count = 0
                potential_new_run_freq = None
                for idx in new_run_indices:
                    if idx in original_idx_to_list_pos:
                        inferred_run_status[original_idx_to_list_pos[idx]] = 'Run'
            else:
                inferred_run_status[list_pos] = 'S&P'

    return pd.Series(inferred_run_status, index=stream_df_original.index, dtype=str)

def _reclassify_low_rate_periods(df: pd.DataFrame, datetime_column: str, window_minutes: int, threshold: int) -> pd.DataFrame:
    """
    Pass 2: Reclassifies low-rate 'S&P' QSOs to 'Unknown'.
    This function expects a DataFrame for a single stream (band/mode).
    """
    if df.empty or 'Run' not in df.columns:
        return df

    df_sorted = df.sort_values(by=datetime_column)
    sp_qso_indices = df_sorted[df_sorted['Run'] == 'S&P'].index

    window_delta = pd.Timedelta(minutes=window_minutes)

    for idx in sp_qso_indices:
        current_time = df_sorted.loc[idx, datetime_column]
        
        preceding_mask = (df_sorted[datetime_column] >= current_time - window_delta) & \
                         (df_sorted[datetime_column] < current_time)
        preceding_count = preceding_mask.sum()

        following_mask = (df_sorted[datetime_column] > current_time) & \
                         (df_sorted[datetime_column] <= current_time + window_delta)
        following_count = following_mask.sum()

        if preceding_count < threshold and following_count < threshold:
            df_sorted.loc[idx, 'Run'] = 'Unknown'

    return df_sorted.sort_index() 

def process_contest_log_for_run_s_p(
    df: pd.DataFrame,
    my_call_column: str = 'MyCall',
    datetime_column: str = 'Datetime',
    frequency_column: str = 'Frequency',
    mode_column: str = 'Mode',
    band_column: str = 'Band',
    unknown_window_minutes: int = DEFAULT_UNKNOWN_WINDOW_MINUTES,
    unknown_qso_threshold: int = DEFAULT_UNKNOWN_QSO_THRESHOLD
) -> pd.DataFrame:
    """
    Main wrapper function to infer "Run", "S&P", or "Unknown" status for each QSO.
    """
    processed_df = df.copy()
    try:
        required_cols = [my_call_column, datetime_column, frequency_column, mode_column, band_column]
        for col in required_cols:
            if col not in processed_df.columns:
                raise KeyError(f"Missing required column for Run/S&P processing: '{col}'")
        
        processed_df[datetime_column] = pd.to_datetime(processed_df[datetime_column], errors='coerce')
        processed_df[frequency_column] = pd.to_numeric(processed_df[frequency_column], errors='coerce')
        processed_df.dropna(subset=[datetime_column, frequency_column], inplace=True)

        for col in [my_call_column, mode_column, band_column]:
            processed_df[col] = processed_df[col].astype(str)

        if 'Run' in processed_df.columns:
            processed_df.drop(columns=['Run'], inplace=True)

        df_sorted = processed_df.sort_values(by=[datetime_column])
        time_delta_threshold = pd.Timedelta(minutes=DEFAULT_RUN_TIME_WINDOW_MINUTES) + pd.Timedelta(seconds=1)
        
        # --- Pass 1 & 2: Apply logic per stream (MyCall, Band, Mode) ---
        results = []
        for group_name, group_df in df_sorted.groupby([my_call_column, band_column, mode_column], group_keys=False):
            representative_mode = group_name[2]
            stream_tolerance = DEFAULT_FREQ_TOLERANCE_CW if representative_mode.upper() == 'CW' else DEFAULT_FREQ_TOLERANCE_PH
            
            # Pass 1: Classify Run/S&P
            pass1_results = _evaluate_single_stream_run(
                group_df, datetime_column, frequency_column, stream_tolerance,
                time_delta_threshold, DEFAULT_MIN_QSO_FOR_RUN
            )
            group_df_with_run = group_df.copy()
            group_df_with_run['Run'] = pass1_results

            # Pass 2: Reclassify to Unknown
            pass2_results_df = _reclassify_low_rate_periods(
                group_df_with_run, datetime_column, unknown_window_minutes, unknown_qso_threshold
            )
            results.append(pass2_results_df)
        
        if results:
            final_df = pd.concat(results).sort_index()
            return final_df
        else:
            processed_df['Run'] = 'S&P' 
            return processed_df

    except KeyError as e:
        raise KeyError(f"Error during Run/S&P pre-processing: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during Run/S&P processing: {e}")
        traceback.print_exc()
        raise

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_s_p.py <input_csv_file_path>")
        sys.exit(1)

    csv_file_path = sys.argv[1]
    
    try:
        initial_df = pd.read_csv(csv_file_path, sep=',', header=0, dtype=str)
        base_name = os.path.splitext(csv_file_path)[0]
        output_file_path = f"{base_name}_Run.csv"

        processed_df = process_contest_log_for_run_s_p(df=initial_df)
        
        df_for_output = processed_df.copy()
        if 'Datetime' in df_for_output.columns:
             df_for_output['Datetime'] = pd.to_datetime(df_for_output['Datetime']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df_for_output = df_for_output.sort_values(by='Datetime', na_position='last').reset_index(drop=True)
        df_for_output.to_csv(output_file_path, index=False)

        logging.info(f"\n--- Processing Complete ---")
        logging.info(f"Processed CSV file created at: {output_file_path}")
        
        if not processed_df.empty:
            logging.info("\n--- Summary of Inferred Run/S&P/Unknown Counts ---")
            
            summary_table = pd.pivot_table(
                processed_df,
                index='Band',
                columns='Run',
                aggfunc='size',
                fill_value=0
            )
            
            for col in ['Run', 'S&P', 'Unknown']:
                if col not in summary_table.columns:
                    summary_table[col] = 0
            
            summary_table['Total'] = summary_table.sum(axis=1)
            summary_table = summary_table[['Total', 'Run', 'S&P', 'Unknown']]

            summary_table.loc['All Bands'] = summary_table.sum()
            
            print(summary_table.to_string())

    except Exception as e:
        logging.critical(f"Script execution terminated due to an error: {e}")
        sys.exit(1)
