# web_app/config/settings.py
#
# Purpose: Django settings for the Contest Log Analyzer Web App.
#          It configures the web application for a stateless, containerized
#          environment and explicitly integrates the 'contest_tools' template
#          directory to ensure a Shared Presentation Layer (ADR-007).
#
# Author: Gemini AI
# Date: 2025-12-13
# Version: 0.105.3-Beta
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
# [0.105.3-Beta] - 2025-12-13
# - Explicitly set X_FRAME_OPTIONS to 'SAMEORIGIN' to allow Sub-Page Views (iframe).
# [0.105.2-Beta] - 2025-12-13
# - Added 'django.template.context_processors.media' to TEMPLATES context_processors.
# [0.105.1-Beta] - 2025-12-13
# - Added MEDIA_ROOT and MEDIA_URL configurations for session storage.
# [0.104.1-Beta] - 2025-12-12
# - Added 'django.contrib.humanize' to INSTALLED_APPS to support template filters.
# [0.103.0-Beta] - 2025-12-12
# - Registered 'web_app.analyzer' app.
# [0.102.0-Beta] - 2025-12-11
# - Initial creation for Phase 3.
# - Implemented ADR-007: Mapped TEMPLATES to ../contest_tools/templates.
from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# BASE_DIR is 'web_app/'
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-dev-key-change-me')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool(os.environ.get('DEBUG', False))

ALLOWED_HOSTS = ['*']

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'web_app.analyzer',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            # ADR-007: Shared Presentation Layer.
            # Points to the existing CLI templates directory to ensure
            # CLI and Web App use identical rendering logic.
            BASE_DIR.parent / 'contest_tools' / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# Use SQLite for session management in this stateless architecture.
# The analysis engine does not use this database.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = []

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (Reports/Sessions)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Security: Allow iframes from the same origin (Required for Sub-Page Views)
X_FRAME_OPTIONS = 'SAMEORIGIN'

# Logging Configuration
# When CLA_PROFILE=1 is set (via docker-compose.yml), enable INFO level logging
# to display performance profiling messages from contest_tools.utils.profiler
CLA_PROFILE_ENABLED = os.environ.get('CLA_PROFILE') == '1'
LOG_LEVEL = 'INFO' if CLA_PROFILE_ENABLED else 'WARNING'

# Diagnostic: Print profiling status at startup (helps verify env var is being read)
if CLA_PROFILE_ENABLED:
    print("✅ Performance profiling ENABLED (CLA_PROFILE=1 detected)")
else:
    print("ℹ️  Performance profiling DISABLED (set CLA_PROFILE=1 in docker-compose.yml to enable)")

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(levelname)s: (%(name)s) %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'contest_tools': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'web_app': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}