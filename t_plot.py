#!/usr/bin/env python3

#%% imports
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

#%% load data
# scp labuser@10.56.0.29:/home/labuser/data/grey/testing_1772291718/CH0_1772291718.ai.tsv /tmp/.
# scp labuser@10.56.0.29:/tmp/runlog.txt /tmp/.
tfile = Path("/tmp/runlog.txt")  # terminal data
nskip = 101572  #
pcbdat = pd.read_table(tfile, skiprows=nskip, sep=' = | @ ', comment='#', engine='python', index_col=2, header=None)
pcbdat.drop(columns=0, inplace=True)

pcbdat.columns=("Central PCB RTD",)
pcbdat.index.name = "Run Time at ~1.0 Sun"

logger_file = Path("/tmp/CH0_1772291718.ai.tsv")  # logger data
loggerdat = pd.read_table(logger_file, skiprows=1, sep=None, comment='#', engine='python', index_col=0, header=None)
loggerdat.columns=("HVAC air",)
loggerdat.index.name = "Run Time at ~1.0 Sun"

#%% make plot
plotdat = pd.concat([pcbdat, loggerdat])
plotdat.sort_index(inplace=True)
plotdat.interpolate(method='index', inplace=True, limit_direction='both')
plotdat.index = pd.to_timedelta(plotdat.index, unit='s')
plotdat.index = plotdat.index.round('1Min')
plotdat.plot(grid=True, ylabel="Temperature [°C]", title="Prototype Four Channel Light Source Thermals", secondary_y=("HVAC air",))

# %%
plt.show()
# %%
