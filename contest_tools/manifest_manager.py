# contest_tools/manifest_manager.py
#
# Purpose: This class manages the session-scoped manifest of generated artifacts.
#          It decouples the generation of reports from their discovery by the UI.
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
import json
import logging
import datetime

class ManifestManager:
    """
    Manages a JSON manifest of generated files.
    Allows decoupling of file generation logic from file discovery logic.
    """
    MANIFEST_FILENAME = "session_manifest.json"

    def __init__(self, root_dir):
        """
        Initialize the manager.
        
        Args:
            root_dir (str): The root directory where 
            the manifest file will be stored.
        """
        self.root_dir = root_dir
        self.manifest_path = os.path.join(self.root_dir, self.MANIFEST_FILENAME)
        self.artifacts = []
        
        # Load existing if available (to support incremental updates)
        if os.path.exists(self.manifest_path):
            self.load()

    def add_artifact(self, report_id, relative_path, report_type):
        """
        Registers an artifact.
        
        Args:
            report_id (str): Unique identifier (e.g., 'rate_sheet').
            relative_path (str): Path relative to the manifest location (or session root).
            report_type (str): 'text', 'plot', 'chart', 'animation', etc.
        """
        # Prevent duplicates
        for art in self.artifacts:
            if art['path'] == relative_path:
                return

        artifact = {
            'report_id': report_id,
            'path': relative_path,
            'type': report_type,
            'timestamp': datetime.datetime.now().isoformat()
        }
        self.artifacts.append(artifact)

    def save(self):
        """Writes the artifact list to the JSON file."""
        # Enforce deterministic order by sorting by path to prevent regression noise
        self.artifacts.sort(key=lambda x: x['path'])
        try:
            with open(self.manifest_path, 'w') as f:
                json.dump(self.artifacts, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save manifest to {self.manifest_path}: {e}")

    def load(self):
        """Loads artifacts from the JSON file."""
        try:
            if os.path.exists(self.manifest_path):
                with open(self.manifest_path, 'r') as f:
                    self.artifacts = json.load(f)
            return self.artifacts
        except Exception as e:
            logging.error(f"Failed to load manifest from {self.manifest_path}: {e}")
            return []