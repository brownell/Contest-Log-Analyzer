# contest_tools/utils/log_fetcher.py
#
# Purpose: Scrapes public contest log archives (starting with CQ WW) to provide
#          a searchable index and on-demand file downloading.
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

import requests
from bs4 import BeautifulSoup
import os
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

CQ_WW_BASE_URL = "https://cqww.com/publiclogs/"

def fetch_log_index(year: str, mode: str) -> List[str]:
    """
    Scrapes the CQ WW public log page for a specific year and mode.
    Returns a list of available callsigns (e.g., ['K3LR', 'KC1XX']).
    """
    # Construct URL (e.g. 2015ph for SSB, 2015cw for CW)
    mode_suffix = "ph" if mode == "SSB" else "cw"
    target_url = f"{CQ_WW_BASE_URL}{year}{mode_suffix}/"
    
    try:
        response = requests.get(target_url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # Logs are listed as links in a table: <a href='k3lr.log'>K3LR</a>
        # We look for links ending in .log
        links = soup.find_all('a', href=True)
        callsigns = []
        
        for link in links:
            href = link['href']
            if href.endswith('.log'):
                # Extract callsign from filename (k3lr.log -> k3lr) or text
                call = href[:-4].upper()
                callsigns.append(call)
                
        return sorted(list(set(callsigns)))

    except Exception as e:
        logger.error(f"Failed to fetch log index from {target_url}: {e}")
        return []

def download_logs(callsigns: List[str], year: str, mode: str, output_dir: str) -> List[str]:
    """
    Downloads specific log files for the given callsigns into the output directory.
    Returns a list of full paths to the downloaded files.
    """
    mode_suffix = "ph" if mode == "SSB" else "cw"
    base_url = f"{CQ_WW_BASE_URL}{year}{mode_suffix}/"
    downloaded_paths = []
    
    for call in callsigns:
        filename = f"{call.lower()}.log"
        file_url = f"{base_url}{filename}"
        local_path = os.path.join(output_dir, filename)
        
        try:
            response = requests.get(file_url, timeout=15)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            downloaded_paths.append(local_path)
            logger.info(f"Downloaded: {filename}")
            
        except Exception as e:
            logger.error(f"Failed to download {filename}: {e}")
            
    return downloaded_paths