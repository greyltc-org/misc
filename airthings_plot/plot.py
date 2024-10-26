#!/usr/bin/env python3

import pandas as pd
import numpy as np
from pathlib import Path

tz_string = "America/Edmonton"

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
    
    ax = raw_radon_split.plot(y=["green", "yellow", "red"], color=["green", "yellow", "red"], label=["good", "bad", "ugly"], title="Radon in Office", ylabel=radon_col, xlabel="When", grid=True)
    ax.set_facecolor("silver")
    ax.grid(color='w')

    fantime = "2024-10-14T16:00:00.000"
    fanline_x = pd.to_datetime(fantime, utc=False).tz_localize(tz_string)
    fanline = ax.vlines(fanline_x, ymin=ax.get_ylim()[0], ymax=ax.get_ylim()[1], label="dinky fan", color="black", linestyles='dashed')
    ax.text(fanline_x, 0.35, "dinky fan on", color='k', ha='right', va='top', rotation=90, transform=ax.get_xaxis_transform())
    #ax.legend()

    #img_format = "png"
    img_format = "svg"
    plot_file = here.joinpath(f"{name}.{img_format}")
    print(f"Saving file://{plot_file}")
    ax.figure.savefig(plot_file)

