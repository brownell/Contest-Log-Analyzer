# contest_tools/constants.py
#
# Purpose: A central module to store project-wide, static constants
#          to prevent circular dependencies and improve maintainability.
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

HAM_BANDS = [
    ('1.8 MHz', '160M'), ('3.5 MHz', '80M'), ('7 MHz', '40M'),
    ('14 MHz', '20M'), ('21 MHz', '15M'), ('28 MHz', '10M'),
    ('50 MHz', '6M'), ('144 MHz', '2M'), ('222 MHz', '1.25M'),
    ('432 MHz', '70CM'), ('902 MHz', '33CM'), ('1.2 GHz', '23CM'),
    ('2.3 GHz', '13CM'), ('3.4 GHz', '9CM'), ('5.7 GHz', '6CM'),
    ('10 GHz', '3CM'), ('24 GHz', '1.25CM'), ('47 GHz', '6MM'),
    ('77 GHz', '4MM'), ('122 GHz', '2.5MM'), ('134 GHz', '2MM'),
    ('241 GHz', '1MM'), ('LIGHT', 'LIGHT')
]
