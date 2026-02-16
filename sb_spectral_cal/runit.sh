#!/usr/bin/env bash

#curl https://www.nlr.gov/media/docs/libraries/grid/zip/astmg173.zip | bsdtar -xOf- ASTMG173.csv | tail -n +2 | sed '1s|.*|nm,am0,am15g,am15d[W*m-2*nm-1]|' > ISO9845-1.csv
python3 sb-spectral-cal.py zero_spectrum_60.0ms_1771192958.0030231.csv shape_spectrum_60.0ms_1771193385.5552158.csv 7003P2185_HL-3-plus-INT-CAL_int_20250728_VIS.lmp one_spectrum_60.0ms_1771192978.67205.csv cal_cell_spectral_response.csv 134.356 134.217
