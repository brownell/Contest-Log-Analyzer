# contest_tools/contest_specific_annotations/wae_location_resolver.py
#
# Purpose: A contest-specific location resolver for the WAE contest.
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

from typing import Dict, Any, Optional
import os
from ..core_annotations import CtyLookup

def resolve_location_type(metadata: Dict[str, Any], cty_dat_path: str) -> Optional[str]:
    """
    Determines if the logger is EU or DX for the WAE contest.
    """
    my_call = metadata.get('MyCall')
    if not my_call:
        return None

    cty_lookup = CtyLookup(cty_dat_path=cty_dat_path)
    info = cty_lookup.get_cty_DXCC_WAE(my_call)._asdict()
    
    return "EU" if info.get('Continent') == 'EU' else "DX"
