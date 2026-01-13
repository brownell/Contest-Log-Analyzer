# contest_tools/event_resolvers/naqp_event_id_resolver.py
#
# Purpose: A contest-specific event ID resolver for the Louisiana QSQ Party (NAQP)
#          contests. It takes a datetime object and returns a unique, three-letter
#          month abbreviation (e.g., "JAN", "AUG") to be used as a subdirectory name.
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

from datetime import datetime

def resolve_event_id(qso_datetime: datetime) -> str:
    """
    Determines the unique event ID for an NAQP contest based on the month
    of a QSO's datetime.

    Args:
        qso_datetime (datetime): A datetime object from any QSO in the log.

    Returns:
        str: A three-letter, uppercase month abbreviation (e.g., "JAN", "FEB").
    """
    if not isinstance(qso_datetime, datetime):
        # Fallback for unexpected data types
        return "UnknownEvent"
        
    # Return the uppercase, three-letter month abbreviation (e.g., JAN, FEB, AUG)
    return qso_datetime.strftime('%b').upper()
