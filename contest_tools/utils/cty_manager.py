# contest_tools/utils/cty_manager.py
#
# Purpose: Manages the lifecycle of cty.dat files, including on-demand
#          downloading, caching, and indexing from the official source.
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
import sys
import json
import zipfile
import datetime
import re
import pathlib
import logging
from urllib.parse import urljoin
import pandas as pd
import requests
from bs4 import BeautifulSoup
from contest_tools.core_annotations.get_cty import CtyLookup

class CtyManager:
    """Manages downloading, caching, and finding CTY.DAT files."""

    _BASE_URL = "https://www.country-files.com/"
    _INDEX_FILENAME = "cty_index.json"
    _USER_AGENT = "CTYFileFinder/2.1 (Python)"
    _INDEX_MAX_AGE_HOURS = 24

    def __init__(self, root_input_dir: str):
        self.root_input_path = pathlib.Path(root_input_dir)
        self.cty_root_path = self.root_input_path / "data" / "CTY"
        self.zips_path = self.cty_root_path / "zips"
   
        self.index_path = self.cty_root_path / self._INDEX_FILENAME
        self._setup_directories()
        self.index = self._load_index()

    def _setup_directories(self):
        """Creates the necessary CTY directories if they don't exist."""
        self.cty_root_path.mkdir(parents=True, exist_ok=True)
        self.zips_path.mkdir(exist_ok=True)

    def _build_full_index(self) -> list:
        """
        Performs a full scrape of the website to build the index.
        Uses Sequential Pagination (Page 1, 2, 3...) to traverse history.
        """
        logging.info("Performing initial full build using Sequential Pagination...")
        full_index = []
        page_num = 1
        
        while True:
            if page_num == 1:
                page_url = self._BASE_URL
            else:
                page_url = f"{self._BASE_URL}page/{page_num}/"
                
            logging.info(f"Scanning {page_url} ...")
            
            html_content = self._fetch_index_page(page_url)
            if not html_content:
                logging.info(f"Stopping scan: Page {page_num} could not be fetched or does not exist.")
                break
                
            files_on_page = self._parse_archive_page(html_content)
            
            if files_on_page:
                full_index.extend(files_on_page)
                logging.info(f"Found {len(files_on_page)} files on page {page_num}.")
            else:
                logging.info(f"No CTY files found on page {page_num}.")

            soup = BeautifulSoup(html_content, 'html.parser')
            next_page_link = soup.select_one('.nav-previous a')
            
            if not next_page_link:
                logging.info("No 'Older posts' link found. Reached end of archives.")
                break
                
            page_num += 1
            
            if page_num > 50:
                logging.warning("Safety limit reached (50 pages). Stopping scan.")
                break

        full_index.sort(key=lambda x: x['date'], reverse=True)
        return full_index

    def _update_index_incrementally(self, existing_index: list) -> list:
        """Scrapes for files newer than the latest entry in the provided index."""
        if not existing_index:
            return self._build_full_index()

        latest_date_in_index = existing_index[0]['date']
        logging.info(f"Checking for files newer than {latest_date_in_index}...")
        
        new_files = []
        page_num = 1
        
        while True:
            if page_num == 1:
                page_url = self._BASE_URL
            else:
                page_url = f"{self._BASE_URL}page/{page_num}/"

            html_content = self._fetch_index_page(page_url)
            if not html_content: break
            
            files_on_page = self._parse_archive_page(html_content)
            if not files_on_page: 
                if page_num > 1: break

            should_stop = False
            for file_entry in files_on_page:
                if file_entry['date'] > latest_date_in_index:
                    new_files.append(file_entry)
                else:
                    should_stop = True
                    break
            
            if should_stop: break
            
            soup = BeautifulSoup(html_content, 'html.parser')
            if not soup.select_one('.nav-previous a'):
                break
                
            page_num += 1

        if new_files:
            logging.info(f"Found {len(new_files)} new files.")
            updated_index = new_files + existing_index
            updated_index.sort(key=lambda x: x['date'], reverse=True)
            return updated_index
        else:
            logging.info("No new files found. Index is up to date.")
            return existing_index

    def _fetch_index_page(self, url: str) -> str | None:
        """Fetches the HTML content from an archive page."""
        try:
            headers = {'User-Agent': self._USER_AGENT}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 404: return None
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logging.warning(f"Could not connect to {url}: {e}")
            return None

    def _parse_archive_page(self, html_content: str) -> list:
        """
        Parses the HTML of an archive page to extract CTY file metadata.
        Targets the STANDARD CTY zip (e.g., 'cty-3538.zip').
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        articles = soup.find_all('article')
        if not articles:
            return []

        data = []
        for article in articles:
            time_tag = article.find('time', class_='entry-date')
            if not time_tag or not time_tag.has_attr('datetime'):
                continue
            date_str = time_tag['datetime']

            # Target standard CTY zip: cty-XXXX.zip
            link = article.select_one('a[href*="/cty/download/"][href$=".zip"]')
            if not link:
                continue

            href = link['href']
            filename = os.path.basename(href)

            # Strict filter: Must start with 'cty-' and look like 'cty-1234.zip'
            if not re.match(r'^cty-\d+\.zip$', filename):
                continue

            data.append({
                "date": date_str,
                "url": urljoin(self._BASE_URL, href),
                "filename": filename
            })
        return data

    def _load_index(self) -> list:
        """Loads the local CTY index from a JSON file."""
        if self.index_path.exists():
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
   
            except (json.JSONDecodeError, IOError):
                logging.error(f"Could not read or parse local index file at {self.index_path}")
        return []

    def _save_index(self, data: list):
        """Saves the CTY index data to a JSON file."""
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
       
                json.dump(data, f, indent=2)
            logging.info(f"CTY index successfully saved with {len(data)} entries.")
        except IOError:
            logging.error(f"Could not write to local index file at {self.index_path}")

    def _download_and_unzip(self, file_info: dict) -> pathlib.Path | None:
        """Downloads and unzips the Standard CTY file, extracting cty_wt_mod.dat."""
        zip_filename_str = file_info.get('filename') or file_info.get('zip_name')
        if not zip_filename_str:
            logging.error("CTY index entry is missing a valid filename key.")
            return None

        zip_path = self.zips_path / zip_filename_str
        
        # Download
        try:
            logging.info(f"Downloading {zip_filename_str}...")
            headers = {'User-Agent': self._USER_AGENT}
            response = requests.get(file_info['url'], stream=True, timeout=30, headers=headers)
            response.raise_for_status()
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except requests.exceptions.RequestException as e:
            logging.error(f"Download failed for {file_info['url']}: {e}")
            return None
            
        # Unzip and Find cty_wt_mod.dat
        target_file = 'cty_wt_mod.dat'
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Case-insensitive search for target file
                file_in_zip = next((name for name in zip_ref.namelist() if name.lower() == target_file), None)
                
                if not file_in_zip:
                    logging.error(f"Target file '{target_file}' not found in {zip_path}")
                    logging.info(f"Files available: {zip_ref.namelist()}")
                    return None
               
                year = pd.to_datetime(file_info['date']).year
                target_dir = self.cty_root_path / str(year)
                target_dir.mkdir(exist_ok=True)

                # Rename to cty_wt_mod_{ver}.dat
                version_match = re.search(r'(\d+)', zip_path.stem)
                version_part = version_match.group(1) if version_match else "unknown"
                
                final_filename = f"cty_wt_mod_{version_part}.dat"
                target_path = target_dir / final_filename
                
                # Extract to temp location then rename
                extracted_temp_path_str = zip_ref.extract(file_in_zip, path=target_dir)
                pathlib.Path(extracted_temp_path_str).rename(target_path)

                logging.info(f"Unzipped and renamed to {target_path}")
                return target_path
        except (zipfile.BadZipFile, FileNotFoundError, IOError) as e:
            logging.error(f"Failed to unzip {zip_path}: {e}")
            return None

    def find_cty_file_by_name(self, filename: str) -> tuple[pathlib.Path, dict] | tuple[None, None]:
        """Finds a CTY file by its specific filename (e.g., 'cty-3538.zip')."""
        if filename.lower().endswith('.zip'):
            stem = filename[:-4]
        elif filename.lower().endswith('.dat'):
            stem = filename[:-4]
        else:
            stem = filename

        # Version extraction logic
        version_match = re.search(r'(\d+)', stem)
        version_part = version_match.group(1) if version_match else "unknown"
        
        # Expected target name: cty_wt_mod_{ver}.dat
        dat_filename_str = f"cty_wt_mod_{version_part}.dat"
        
        file_info = next((item for item in self.index
                          if (item.get('filename') or item.get('zip_name', '')).startswith(stem)), None)

        if not file_info:
            logging.error(f"Filename '{filename}' not found in the CTY index.")
            return None, None

        logging.info(f"Searching for {dat_filename_str}, Date: {file_info['date']}")

        try:
            year = pd.to_datetime(file_info['date']).year
            target_dir = self.cty_root_path / str(year)
            target_path = target_dir / dat_filename_str
        except Exception as e:
            logging.error(f"Could not parse date or construct path for '{filename}': {e}")
            return None, None

        if target_path.exists():
            return target_path, file_info

        if file_info:
            unzipped_path = self._download_and_unzip(file_info)
            return (unzipped_path, file_info) if unzipped_path else (None, None)
        else:
            return None, None

    def find_cty_file_by_date(self, contest_date: pd.Timestamp, specifier: str) -> tuple[pathlib.Path, dict] | tuple[None, None]:
        """
        Finds the most appropriate CTY file based on a contest date.
        Uses Hybrid Validation (Header check -> Fallback to Web Date).
        """
        if not self.index:
            logging.error("CTY index is empty. Cannot find file by date.")
            return None, None

        if contest_date.tzinfo is None:
             contest_date = contest_date.tz_localize('UTC')

        for item in self.index:
            try:
                dt_aware = pd.to_datetime(item['date'], errors='coerce')
                item['datetime'] = dt_aware.tz_convert('UTC') if dt_aware.tzinfo else dt_aware.tz_localize('UTC')
            except Exception:
                item['datetime'] = None
        
        valid_entries = [item for item in self.index if item['datetime'] is not None]

        if specifier == 'before':
            candidates = sorted(
                [item for item in valid_entries if item['datetime'] < contest_date],
                key=lambda x: x['datetime'],
                reverse=True
            )
        else: # Default to 'after'
            candidates = sorted(
                [item for item in valid_entries if item['datetime'] > contest_date],
                key=lambda x: x['datetime']
            )

        if not candidates:
            logging.warning(f"No CTY candidates found matching specifier '{specifier}' for date {contest_date}.")
            if valid_entries:
                logging.warning("Falling back to latest available CTY file in index.")
                latest_entry = max(valid_entries, key=lambda x: x['datetime'])
                candidates = [latest_entry]
            else:
                return None, None

        for candidate in candidates:
            path, _ = self.find_cty_file_by_name(candidate.get('filename') or candidate.get('zip_name'))
            
            if not path or not path.exists():
                logging.warning(f"Could not retrieve CTY file for candidate: {candidate.get('filename')}. Trying next.")
                continue

            # Hybrid Validation: Check internal date
            internal_date = CtyLookup.extract_version_date(str(path))
            
            check_date = None
            date_source = ""

            if internal_date:
                if internal_date.tzinfo is None:
                    internal_date = internal_date.tz_localize('UTC')
                check_date = internal_date
                date_source = "Internal Header"
            else:
                # Fallback to Web Index Date
                logging.warning(f"Could not extract internal date from {path}. Falling back to Web Index Date.")
                check_date = candidate['datetime']
                date_source = "Web Index Date"

            is_valid = False
            if specifier == 'before':
                is_valid = check_date < contest_date
            else: # after
                is_valid = check_date > contest_date
            
            if is_valid:
                logging.info(f"Selected CTY file {path.name} via {date_source} ({check_date.date()}) for contest date {contest_date.date()}.")
                return path, candidate
            else:
                logging.warning(f"File {path.name} ({date_source}: {check_date.date()}) failed validation for contest date {contest_date.date()} (Specifier: {specifier}).")
        
        # Fallback
        logging.warning("No candidate passed validation. Returning latest available file from index as fallback.")
        
        if valid_entries:
            latest_entry = max(valid_entries, key=lambda x: x['datetime'])
            path, _ = self.find_cty_file_by_name(latest_entry.get('filename') or latest_entry.get('zip_name'))
            return path, latest_entry
            
        return None, None

    def sync_index(self, contest_date: pd.Timestamp):
        """
        Checks if the CTY index needs to be updated based on the contest date
        and performs an update if required.
        """
        local_index = self._load_index()
        update_needed = False

        if not local_index:
            logging.info("CTY index is empty. Performing initial full build...")
            update_needed = True
            new_index = self._build_full_index()
            if new_index:
          
                self._save_index(new_index)
                self.index = new_index
            else:
                logging.error("Failed to build initial CTY index.")
        else:
            latest_index_date = pd.to_datetime(local_index[0]['date']).tz_convert('UTC')
            if contest_date > latest_index_date:
      
                logging.info(f"Contest date ({contest_date.date()}) is newer than latest index entry ({latest_index_date.date()}). Checking for updates.")
                update_needed = True
                updated_index = self._update_index_incrementally(local_index)
                if len(updated_index) > len(local_index):
                    self._save_index(updated_index)
   
                    self.index = updated_index

        if not update_needed:
            logging.info("CTY index is sufficiently current for this contest.")