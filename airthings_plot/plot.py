#!/usr/bin/env python3

import pandas as pd
import numpy as np
from pathlib import Path

tz_string = "America/Edmonton"

#img_format = "png"
img_format = "svg"


here = Path(__file__).parent
for datafilepath in here.joinpath("data").glob("*.csv"):
    name = datafilepath.name
    x_col = "recorded"
    radon_col = "RADON_SHORT_TERM_AVG Bq/m3"
    raw = pd.read_csv(datafilepath, sep=";", index_col=[x_col])
    raw.index = pd.to_datetime(raw.index, format='ISO8601', utc=True)
    raw = raw.tz_convert(tz_string)

    raw.interpolate(inplace=True)  # TODO: figure out how to operate without interpolation

    # split the radon data
    raw_radon_split = raw.copy()
    raw_radon_split["green"] = raw_radon_split[radon_col]
    raw_radon_split["yellow"] = raw_radon_split[radon_col]
    raw_radon_split["red"] = raw_radon_split[radon_col]
    raw_radon_split.loc[~(raw_radon_split["green"]<100), "green"] = np.nan
    raw_radon_split.loc[~((raw_radon_split["yellow"]>=100) & (raw_radon_split["yellow"]<150)), "yellow"] = np.nan
    raw_radon_split.loc[~(raw_radon_split["red"]>=150), "red"] = np.nan
    raw_radon_split.loc[~(raw_radon_split["green"]<100), "green"] = np.nan
    
    ax = raw_radon_split.plot(y=["green", "yellow", "red"], color=["green", "yellow", "red"], label=["good", "bad", "ugly"], title="Radon in 2808", ylabel=radon_col, xlabel="When", grid=True)
    ax.set_facecolor("silver")
    ax.grid(color='w')
    ax.set_ylim(bottom=0)


    fantimes = []
    fantimes.append({"event": "baseline: sensor @ ground floor office",  "local_time": None, "y":0.9})
    fantimes.append({"event": "pipe install and dinky fan on", "local_time": "2024-10-14T16:00:00.000", "y":0.65})
    fantimes.append({"event": "big fan swapped in",            "local_time": "2024-10-30T21:00:00.000", "y":0.9})
    fantimes.append({"event": "sensor @ basement desk",        "local_time": "2024-11-10T14:00:00.000", "y":0.9})
    fantimes.append({"event": "drilled hole in house",         "local_time": "2025-02-15T14:00:00.000", "y":0.9})
    for fantime in fantimes:
        if fantime["local_time"]:
            fanline_x = pd.to_datetime(fantime["local_time"], utc=False).tz_localize(tz_string)
        else:
            fanline_x = raw.index[0]
        fanline = ax.vlines(fanline_x, ymin=ax.get_ylim()[0], ymax=ax.get_ylim()[1], label="dinky fan", color="black", linestyles='dashed')
        ax.text(fanline_x, fantime["y"], fantime["event"], color='k', ha='right', va='top', rotation=90, transform=ax.get_xaxis_transform())
    #ax.legend()

    plot_file = here.joinpath(f"{name}.{img_format}")
    print(f"Saving file://{plot_file}")
    ax.figure.savefig(plot_file)

