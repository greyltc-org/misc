#!/usr/bin/env python3
#%% imports
import pandas as pd
import numpy as np
from typing import Literal

#%% QEPro spectrometer data
# intensity calibration reference measurement
counts_one   = pd.read_table("one_spectrum_8.0ms_1771787831.906836.csv", sep=None, comment='#', engine='python', index_col=0, header=None)  # counts / nm
i_nom = 134.356/1000  # [A] I_sc current value shown on cal. cell's certificate (expected current production under am1.5g)
i_meas = 134.217/1000 # [A] I_sc value measured for cal. cell while collecting the above intensity calibration reference measurement

# spectral shape calibration reference measurement
counts_shape = pd.read_table("shape_spectrum_8ms_1771788187.3208032.csv", sep=None, comment='#', engine='python', index_col=0, header=None)  # counts / nm

# the measurement
counts_meas  = pd.read_table("one_spectrum_8ms_1771788699.5718234.csv", sep=None, comment='#', engine='python', index_col=0, header=None)  # counts / nm

# limit the intensity calibration to data from this range
irradiance_cal_range = (337, 1100)  # eqe data starts at 337nm and the shape scale factor starts to explode past 1100nm

# range over which to plot
am15_compare_plot_range = (300, 1100)

#%% Maya 2000Pro spectrometer data
# intensity calibration reference measurement
counts_one   = pd.read_table("one_spectrum_8ms_1771679498.2804418.csv", sep=None, comment='#', engine='python', index_col=0, header=None)  # counts / nm
i_nom = 134.356/1000  # [A] I_sc current value shown on cal. cell's certificate (expected current production under am1.5g)
i_meas = 134.217/1000 # [A] I_sc value measured for cal. cell while collecting the above intensity calibration reference measurement

# spectral shape calibration reference measurement
counts_shape = pd.read_table("shape_spectrum_8ms_1771673561.7976954.csv", sep=None, comment='#', engine='python', index_col=0, header=None)  # counts / nm

# the measurement
counts_meas  = pd.read_table("one_spectrum_8ms_1771681216.904209.csv", sep=None, comment='#', engine='python', index_col=0, header=None)  # counts / nm

# limit the intensity calibration to data from this range
irradiance_cal_range = (337, 1000)  # eqe data starts at 337nm and the Maya2000Pro shape scale factor starts to explode past 1000nm

# range over which to plot
am15_compare_plot_range = (300, 1000)

#%% Generic data and constants
lamp_shape   = pd.read_table("7003P2185_HL-3-plus-INT-CAL_int_20250728_VIS.lmp",  sep=None, comment='#', engine='python', index_col=0, header=None)  # uW     / nm
sensitivity_file_format:Literal["EQE", "Spectral Sensitivity"] = "Spectral Sensitivity"
cal_sens     = pd.read_table("cal_cell_spectral_response.csv",                    sep=None, comment='#', engine='python', index_col=0, header=None)  # A/W    / nm
cal_sens.index.name = "Wavelength [nm]"
cal_sens.columns = (sensitivity_file_format,)
all_am       = pd.read_table("ISO9845-1.csv",                                     sep=None, comment='#', engine='python', index_col=0, header=None)  # W/m^2  / nm
all_am.index.name = "Wavelength [nm]"
all_am.columns = ("am0", "am15g", "am15d")
am15         = all_am["am15g"]  # W*m-2*nm-1
sqcmpersqm = 100*100  # how many square cms are in a square m

h = 6.62607004081e-34  # [m^2*kg/s] planck constant
c = 299792458  # [m/s] speed of light
hc = h * c  # [J*m]
nhc = hc * 1e9  # [J*nm]
q = 1.60217657e-19  # elementary charge, [C] or [A*s]
nhcperq = nhc / q  # [nW/A]


#%% some analysis helper functions
# resample and interpolate so that given series agree
def make_same(dfs:list[pd.Series]) -> list[pd.Series]:
    if len(dfs) < 2:
        raise ValueError("Give at least two dataframes")
    uuindex = dfs[0].index  # unique union index
    for remainingdf in dfs[1:]:
        uuindex = uuindex.union(remainingdf.index).unique()
    dfs_rei = []
    for df in dfs:
        if not isinstance(df, pd.Series):
            raise ValueError(f"Expected Series, got {type(df)}")
        dfrei = df.reindex(index=uuindex)
        dfrei.interpolate(method='index', inplace=True, limit_direction='both')
        dfs_rei.append(dfrei)
        
    return dfs_rei

# divide one series by another even if they have different indicies
def different_divide(a:pd.Series, b:pd.Series, return_index:Literal["a","b"]="a", between=None) -> pd.Series:
    if return_index == "a":
        main_index = a.index
    elif return_index == "b":
        main_index = b.index
    else:
        raise ValueError("Unknown return index")
    samed = make_same([a, b])
    asa = samed[0]
    bsa = samed[1]
    rslt = asa / bsa
    reid = rslt.reindex(main_index)
    if between is not None:
        mask = main_index.to_series().between(between[0], between[1])
        reid = reid[mask]
    return reid

# multiply one series by another even if they have different indicies
def different_multiply(a:pd.Series, b:pd.Series, return_index:Literal["a","b"]="a", between=None) -> pd.Series:
    if return_index == "a":
        main_index = a.index
    elif return_index == "b":
        main_index = b.index
    else:
        raise ValueError("Unknown return index")
    main_index = a.index
    samed = make_same([a, b])
    asa = samed[0]
    bsa = samed[1]
    rslt = asa * bsa
    reid = rslt.reindex(main_index)
    if between is not None:
        mask = main_index.to_series().between(between[0], between[1])
        reid = reid[mask]
    return reid


#%% calibrate the shape returned by the spectrometer
shape_cal_factor = different_divide(lamp_shape[1], counts_shape[1], return_index="b")  # uW/counts / nm

# check shape cal
wl_shape_check = shape_cal_factor * counts_meas[1]
wl_shape_check_df = wl_shape_check.to_frame()
wl_shape_check_df.index.name = "Wavelength [nm]"
wl_shape_check_df["norm"] = wl_shape_check/wl_shape_check.max()

E_lamp = nhc / lamp_shape.index.to_numpy()  # [uJ]
lamp_shape["particles"] = lamp_shape[1]/E_lamp
shape_cal_factor_part = different_divide(lamp_shape["particles"], counts_shape[1], return_index="b")  # particles/counts / nm

some_cal_factors = shape_cal_factor.to_frame("power")
some_cal_factors["particles"] = shape_cal_factor_part
some_cal_factors.plot(secondary_y=["particles"], title="Shape Calibration Factor")  # with the current setup, this seems to show the shape cal factor exploding past 1000nm


wl_shape_check_part = shape_cal_factor_part * counts_meas[1]
wl_shape_check_df["particles_norm"] = wl_shape_check_part/wl_shape_check_part.max()
#wl_shape_check_df[["norm","particles_norm"]].plot(xlim=(350, 1075))
wl_shape_check_df[["norm","particles_norm"]].plot(title="Wavelabs with normalized shape cal measurement")

#this_shape_cal = shape_cal_factor_part  # looks bad (intensities from seabreeze indicate photons)
this_shape_cal = shape_cal_factor  # looks good (intensities from seabreeze indicate irradiance)


#%% calibrate irradiance
#irradiance_cal_range = (0, float("inf"))  # use all data in intensity calibration

# ensure eqe
if sensitivity_file_format == "Spectral Sensitivity":  # let's convert that to EQE
    cal_sens["EQE"] = nhcperq * cal_sens[sensitivity_file_format] / cal_sens.index  # unitless (it's a fraction)
elif self.sensitivity_file_format == "EQE":
    pass
else:
    raise ValueError("Unknown sensitivity file format.")
cal_sens.plot()  # EQE is unitless (it's a fraction) and Spectral Sensitivity is in A/W

# the power we'd get before applying the intensity scale
trapme = different_multiply(this_shape_cal*counts_one[1], cal_sens["EQE"], between=irradiance_cal_range)   # prep for the trapezoid
pre_correct_power = np.trapezoid(trapme, trapme.index)

# E_am15 = nhc / am15.index.to_numpy()  # [J]
# am15pcheck = np.trapezoid(am15, am15.index)  # W/m^2
# am15icheck = q*np.trapezoid(am15/E_am15, am15.index)  # A/m^2
# am15icheckmacm = am15icheck / sqcmpersqm * 1000  # mA/cm^2


# calicheck = q*np.trapezoid(different_multiply(am15/E_am15, cal_sens["EQE"]), am15.index)  # A/m^2
# calicheckmacm = calicheck / sqcmpersqm * 1000  # mA/cm^2
# calicheckma = calicheckmacm * 4  # mA / calibration device

# predict the power that would be absorbed by the calibration device under AM1.5G
trapme = different_multiply(am15, cal_sens["EQE"], between=irradiance_cal_range)  # prep for the trapezoid
P_am15_predict = np.trapezoid(trapme, trapme.index)  # W/m^2

# scale the predicted power by the device's intensity at measurement time
expected_power = P_am15_predict * i_meas/i_nom

# find the number to use to scale up the measurement 
intensity_scale_factor = expected_power/pre_correct_power

# apply all the calibrations to the measurement
calibtrated_measurement = this_shape_cal*intensity_scale_factor*counts_meas[1]

# plot a spectral irradiance comparison between the measured data and that of AM1.5G
sames = make_same([am15, calibtrated_measurement])
power_compare = sames[0].to_frame("AM1.5G")
power_compare["Snaith Wavelabs"] = sames[1]
power_compare.index.name = "Wavelength [nm]"
power_compare[power_compare.index.to_series().between(*am15_compare_plot_range)].plot(title="Spectral Irradiance Comparison", ylabel="Spectral Irradiance [W/m^2 per nm]", grid=True)

# save the comparison
power_compare.to_csv("spectral_irradiance_compare.tsv.txt", sep="\t")


E_compare = nhc / power_compare.index.to_series()  # [J]

# into [mA/cm^2 per nm]
current_compare = power_compare.divide(E_compare, axis=0) * q / 10
teh_plot = current_compare[current_compare.index.to_series().between(*am15_compare_plot_range)].plot(title="Current Density Comparison", ylabel="Spectral Current Density [mA/cm^2 per nm]", grid=True)

# %%
