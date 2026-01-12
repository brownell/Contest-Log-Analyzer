# Dockerfile
#
# Purpose: Defines the Docker container image for the Contest Log Analytics
#          Web Application (Phase 3).
#          It sets up a lightweight Python 3.11-slim
#          environment, installs dependencies, and explicitly excludes multimedia
#          libraries (ffmpeg) to enforce architectural constraints.
#
# Author: Gemini AI
# Date: 2025-12-30
# Version: 0.155.2-Beta
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
# [0.155.2-Beta] - 2025-12-30
# - Added provisioning of html2canvas.min.js for client-side capture.
# [0.102.0-Beta] - 2025-12-11
# - Initial creation for Phase 3 (The Web Pathfinder).
# - Configured for Python 3.11-slim with /app PYTHONPATH.

FROM python:3.11-slim

# Prevent Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1
# Prevent Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED 1
# Add the root directory to PYTHONPATH so web_app can import contest_tools
ENV PYTHONPATH /app

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --default-timeout=300 --retries=5 -r requirements.txt

# --- INFRASTRUCTURE: Asset Provisioning ---
# Create directory and download html2canvas.min.js
RUN python -c "import os, urllib.request; \
    target_dir = 'web_app/analyzer/static/js'; \
    os.makedirs(target_dir, exist_ok=True); \
    url = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js'; \
    urllib.request.urlretrieve(url, os.path.join(target_dir, 'html2canvas.min.js')); \
    print(f'Provisioned static assets in {target_dir}')"

COPY . .

CMD ["python", "web_app/manage.py", "runserver", "0.0.0.0:8000"]