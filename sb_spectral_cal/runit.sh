#!/usr/bin/env bash

#curl https://www.nlr.gov/media/docs/libraries/grid/zip/astmg173.zip | bsdtar -xOf- ASTMG173.csv | sed '1s;^;#;' | sed '2s;^;#;' > ISO9845-1.csv
# QEPRO
#python3 sb-spectral-cal.py zero_spectrum_8.0ms_1771787794.8660612.csv shape_spectrum_8ms_1771788187.3208032.csv 7003P2185_HL-3-plus-INT-CAL_int_20250728_VIS.lmp one_spectrum_8.0ms_1771787831.906836.csv cal_cell_spectral_response.csv 134.356 134.217

# 2000pro
python3 sb-spectral-cal.py zero_spectrum_8ms_1771679464.1982841.csv shape_spectrum_8ms_1771673561.7976954.csv 7003P2185_HL-3-plus-INT-CAL_int_20250728_VIS.lmp one_spectrum_8ms_1771679498.2804418.csv cal_cell_spectral_response.csv 134.356 134.217
