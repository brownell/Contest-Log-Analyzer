# contest_tools/contest_specific_annotations/wrtc_multiplier_resolver.py
#
# Purpose: Provides the custom multiplier resolver for the WRTC contest series.
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
from typing import Dict, Any, Optional
from ..contest_definitions import ContestDefinition

def resolve_multipliers(df: pd.DataFrame, my_location_type: str, root_input_dir: str, contest_def: ContestDefinition) -> pd.DataFrame:
    """
    Resolves multipliers for WRTC contests.
    Multipliers: DXCC Countries, HQ Stations, IARU Officials.
    Rule: Counted once per band, regardless of mode.
    """
    if df.empty:
        return df

    # Use the existing IARU resolver to get the base multiplier types
    from . import iaru_hf_multiplier_resolver
    df = iaru_hf_multiplier_resolver.resolve_multipliers(df, my_location_type, root_input_dir, contest_def)

    # The IARU resolver populates 'Mult_Zone', 'Mult_HQ', and 'Mult_Official'.
    # For WRTC, we need DXCC countries instead of zones.
    df['Mult_DXCC'] = df['DXCCPfx']
    df['Mult_DXCCName'] = df['DXCCName']
    
    # Rule 8.2: HQ/Officials do not count for DXCC.
    # We nullify the DXCC multiplier if an HQ or Official multiplier is present.
    hq_or_official_mask = df['Mult_HQ'].notna() | df['Mult_Official'].notna()
    df.loc[hq_or_official_mask, ['Mult_DXCC', 'Mult_DXCCName']] = pd.NA

    return df