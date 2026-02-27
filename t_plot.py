#!/usr/bin/env python3

#%% imports
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

#%% data
tfile = Path("/tmp/runlog.txt")

tdat = pd.read_table(tfile, usecols=(1,), skiprows=4042, sep=' = ', comment='#', engine='python', index_col=None, header=None)
tdat.columns=("Central RTD",)
tdat.index = pd.timedelta_range(start=0, periods=len(tdat), freq="1s")
tdat.index.name = "Run Time at ~1.0 Sun"

gph = tdat.plot(grid=True, ylim=(22, None), ylabel="Temperature [°C]", title="Prototype Four Channel Light Source Thermals")
# %%
plt.show()
# %%
