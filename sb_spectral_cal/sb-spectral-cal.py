#!/usr/bin/env python3

# a live plotter for oceanoptics spectrometers
# needs https://github.com/ap--/python-seabreeze

# written by grey@christoforo.net

# usage:
# 1. run it with ./sb-spectral-cal.py
#    - cover the sensor and click the "Z" button to collect a zero baseline
#    - point the sensor at something with a known power emission shape and click the "S" button to collect the shape cal data file
#    - record the path of the "shape" calibration file and know the expected emission shape
# 3. run it with ./sb-spectral-cal.py
#    - cover the sensor and click the "Z" button to collect a zero baseline, record the path of the "zero" calibration file
#    - point the sensor at something with constant irradiance and click the "1" button to collect the intensity cal data file
#    - record the path of the resulting "one" calibration file
#    - replace the sensor with an calibrated intensity measuring device
#    - record the intensity value measured by the calibrated intensity measuring device, know the nominal 1 sun expected intensity value for the calibrated device and know its spectral sensitivity or EQE
# 4. now run it with ./sb-spectral-cal.py offset_cal.csv known_power_shape.csv measured_power_shape.csv measured_intensity.csv known_cal_sensitivity.csv 1_sun_intensity_value measured_intensity_value
# see runit.sh for examples


from seabreeze import spectrometers
import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import time
import sys
import itertools
from typing import Literal


class SBLivePlot(object):
    am15 = None
    correct_nonlinearity = True
    correct_dark_counts = True
    sensitivity_file_format:Literal["EQE", "Spectral Sensitivity"] = "Spectral Sensitivity"
    _integration_time_ms = 8
    count_clip_warning = None  # now we query the device for this
    count_clip_warning_buffer = 95  # warn at this percent of full scale
    min_plot_update_ms = 200
    am15_file = Path("ISO9845-1.csv")
    # curl https://www.nlr.gov/media/docs/libraries/grid/zip/astmg173.zip | bsdtar -xOf- ASTMG173.csv | sed '1s;^;#;' | sed '2s;^;#;' > ISO9845-1.csv
    navgs = 1
    cal_avgs = 500  # number of averages to do for calibration measurements (careful because calibraions done at longer integration times might take a very long time)
    plot_min_nm = float(0.0)
    plot_max_nm = float("inf")
    # better for Maya2000 pro
    #plot_min_nm = float(350)
    #plot_max_nm = float(1000)
    bars_begin = None
    bars_end = None
    P_solar_expect = 0  # expected solar power over bars range
    I_solar_expect = 0  # expected solar current over bars range
    spec = None
    wls = np.array([])
    nhc = None
    ax = None
    ax2 = None
    ani = None
    l = None  # line plot
    bars = None  # bar plot
    fig = None
    export_raw_data_to_disk = False
    nclip_start = 8  # ignore this many measurement values at the start of the spectrometer's measurement range
    nclip_end = 6  # ignore this many measurement values at the end of the spectrometer's measurement range
    shape_scale_factor = None
    zero_offset = None
    exclude = None   # true for wavelengths to not plot
    #bars_exclude = None
    intensity_scale_factor = None
    lasty = None
    fully_calibrated = False
    ylabel="Intensity [counts]"
    snapshot_pending = False
    enable_bars = True
    enable_am15 = True
    bar_lefts=[]
    zones=[]
    xlim=(300, 1200)  # draw the plots here
    #xlim=None
    plot_current = False


    def __init__(self, spec_num=0):
        h = 6.62607004081e-34  # [m^2*kg/s] planck constant
        c = 299792458  # [m/s] speed of light
        hc = h * c  # [J*m]
        self.nhc = hc * 1e9  # [J*nm]
        self.q = 1.60217657e-19  # elementary charge, [C] or [A*s]
        nhcperq = self.nhc /self.q  # [nW/A]
        self.zones = []
        self.zones.append(
            {
                "start": 300,
                "stop":  470,
                "p_nom": 16.61,
            }
        )
        self.zones.append(
            {
                "start": 470,
                "stop":  561,
                "p_nom": 16.74,
            }
        )
        self.zones.append(
            {
                "start": 561,
                "stop":  657,
                "p_nom": 16.67,
            }
        )
        self.zones.append(
            {
                "start": 657,
                "stop":  772,
                "p_nom": 16.63,
            }
        )
        self.zones.append(
            {
                "start": 772,
                "stop":  919,
                "p_nom": 16.66,
            }
        )
        self.zones.append(
            {
                "start": 919,
                #"stop":  1075,  # maya 2000pro isn't good enough to go all the way to 1200
                #"stop":  1100,  # QEPro isn't good enough to go all the way to 1200
                "stop":  1000,  # artifacts over 1000

                #"stop":  1200,  # maya 2000pro isn't good enough to go all the way to 1200
                "p_nom": 16.69,
            }
        )
        self.bar_lefts = [z["start"] for z in self.zones]
        #self.bar_lefts.append(self.zones[-1]["stop"])
        self.bar_widths = [z["stop"]-z["start"] for z in self.zones]
        devs = spectrometers.list_devices()
        self.bars_begin = self.bar_lefts[0]
        self.bars_end = self.bar_lefts[-1] + self.bar_widths[-1]

        if self.am15_file.is_file():
            self.am15 = pd.read_table(self.am15_file, sep=None, comment='#', engine='python', index_col=0, header=None)
            self.am15.index.name = "nm"
            self.am15.columns = ("am0", "am15g", "am15d")
            E_solar = self.nhc / self.am15.index
            self.am15["photon_density"] = self.am15["am15g"] / E_solar  # [photons/s/m^2/nm]
            self.am15["current_density"] = self.am15["photon_density"] * self.q  # [A/m^2/nm]
            self.am15["current_density_ma"] = self.am15["current_density"] / 10000 * 1000

        try:
            self.spec = spectrometers.Spectrometer(devs[spec_num])
        except Exception as e:
            raise ValueError(f"Initial spectrometer setup failed. Is the spectrometer connected and powered on? Error: {e}")
        self.count_clip_warning = self.spec.max_intensity * self.count_clip_warning_buffer/100
        self.integration_time_ms = self._integration_time_ms
        self.update_wls()
        try:
            zero_file = Path(sys.argv[1])  # measurement of the sensor when it's blocked/covered: (nm, counts)
            zero = pd.read_table(zero_file, sep=None, comment='#', engine='python', index_col=0, header=None)
            self.zero_offset = zero.to_numpy().flatten()
            print(f"Using zero offset")
        except Exception as e:
            print(f"No zero offset")

        try:
            shape_cal_reading_file = Path(sys.argv[2]) # measurement of the emitter with known spectral shape (nm, counts)
            shape_cal_truth_file = Path(sys.argv[3])  # should be given so that the first col is wavelengths in nm and the second column is power (maybe microwatts) per nm
            shape_cal_measure = pd.read_table(shape_cal_reading_file, sep=None, comment='#', engine='python', index_col=0, header=None)
            shape_cal_measure.columns = ("counts",)
            shape_cal_measure.index.name = 'nm'
            measure_idx = shape_cal_measure.index
            shape_cal_truth =   pd.read_table(shape_cal_truth_file, sep=None, comment='#', engine='python', index_col=0, header=None)
            shape_cal_truth.index.name = "nm"
            shape_cal_truth.columns = ('power',)
            #E = self.nhc / shape_cal_truth.index
            #shape_cal_truth["flux"] = shape_cal_truth["power"] / E
            uuindex = shape_cal_measure.index.union(shape_cal_truth.index).unique()
            shape_cal_measure = shape_cal_measure.reindex(index=uuindex)
            shape_cal_truth = shape_cal_truth.reindex(index=uuindex)
            shape_cal_truth.interpolate(method='index', inplace=True, limit_direction='both')
            shape_cal_measure.interpolate(method='index', inplace=True, limit_direction='both')
            shape_scale_factor = shape_cal_truth["power"]/shape_cal_measure["counts"]
            shape_scale_factor = shape_scale_factor.reindex(index=measure_idx)
            self.shape_scale_factor = shape_scale_factor.to_numpy().flatten()  # the particle shape factor, not power
            print(f"Using shape calibration")
            try:
                intensity_cal_reading_file = Path(sys.argv[4])  # what we measured
                intensity_cal_sensitivity_file = Path(sys.argv[5])  # in eqe or spectral sensitivity format (select the right one below)
                self.sensitivity_file_format = "Spectral Sensitivity"
                intensity_nominal = float(sys.argv[6])/1000  # nominal intensity value under 1000.0 W/m^2 am1.5 (mA maybe, units will cancel) for the calibration device. should include spectral mismatch correction
                intensity_measure = float(sys.argv[7])/1000  # intensity value seen by the calibration device (mA maybe, units will cancel)
                #cal_spectral_mismatch = float(sys.argv[8])  # spectral mismatch value (relative to AM1.5G) associated with the cal device, already taken into account in intensity_nominal

                intensity_cal_sensitivity = pd.read_table(intensity_cal_sensitivity_file, sep=None, comment='#', engine='python', index_col=0, header=None)
                intensity_cal_sensitivity.index.name = 'nm'
                intensity_cal_bounds = (337, 1000)  # eqe data starts at 337nm and the shape scale factor starts to explode past 1000nm


                if self.sensitivity_file_format == "Spectral Sensitivity":  # let's convert that to EQE
                    eqe = nhcperq * intensity_cal_sensitivity.to_numpy().flatten() / intensity_cal_sensitivity.index.to_numpy().flatten()
                elif self.sensitivity_file_format == "EQE":
                    eqe = intensity_cal_sensitivity.to_numpy().flatten()
                else:
                    raise ValueError("Unknown sensitivity file format.")
                intensity_cal_sensitivity.columns = (self.sensitivity_file_format,)
                intensity_cal_sensitivity["eqe"] = eqe
                #sensitivity_bounds = (intensity_cal_sensitivity.index.min(), intensity_cal_sensitivity.index.max())
                am15_mask = self.am15.index.to_series().between(intensity_cal_bounds[0], intensity_cal_bounds[1])
                #orig_am15_index = self.am15.index
                uuindex = self.am15.index.union(intensity_cal_sensitivity["eqe"].index).unique()
                am15 = self.am15.reindex(index=uuindex)
                reieqe = intensity_cal_sensitivity["eqe"].reindex(index=uuindex)
                am15.interpolate(method='index', inplace=True, limit_direction='both')
                reieqe.interpolate(method='index', inplace=True, limit_direction='both')

                # total optical power impinging on cal device during calibration that is responsible for its current generation
                P_am15_predict = np.trapezoid(am15["am15g"][am15_mask]*reieqe[am15_mask], am15.index[am15_mask])
                
                #intensity_cal_sensitivity["am15_current_density"] = np.interp(intensity_cal_sensitivity.index, self.am15.index, self.am15["am15g"], left=np.nan, right=np.nan)

                intensity_cal_measure = pd.read_table(intensity_cal_reading_file, sep=None, comment='#', engine='python', index_col=0, header=None)
                intensity_cal_measure.index.name = "nm"
                intensity_cal_measure.columns = ("counts",)
                intensity_cal_measure["shape_factor"] = self.shape_scale_factor
                uuindex = intensity_cal_measure.index.union(intensity_cal_sensitivity["eqe"].index).unique()
                #orig_measure_index = shape_cal_measure.index
                intensity_cal_measure = intensity_cal_measure.reindex(index=uuindex)
                reieqe = intensity_cal_sensitivity["eqe"].reindex(index=uuindex)
                intensity_cal_measure.interpolate(method='index', inplace=True, limit_direction='both')
                reieqe.interpolate(method='index', inplace=True, limit_direction='both')
                measure_mask = intensity_cal_measure.index.to_series().between(intensity_cal_bounds[0], intensity_cal_bounds[1])

                # measured power before intensity scale factor
                P_measure_prescale = np.trapezoid(intensity_cal_measure["counts"][measure_mask]*intensity_cal_measure["shape_factor"][measure_mask]*reieqe[measure_mask], intensity_cal_measure.index[measure_mask])
                


                #intensity_cal_measure = pd.read_table(intensity_cal_reading_file, sep=None, comment='#', engine='python', index_col=0, header=None)
                #intensity_cal_measure.index.name = "nm"
                #intensity_cal_measure.columns = ("counts",)
                #intensity_cal_measure["shape_factor"] = self.shape_scale_factor
                # spectrometer_index = intensity_cal_measure.index
                # uuindex = intensity_cal_measure.index.union(intensity_cal_sensitivity.index).unique()
                # intensity_cal_measure = intensity_cal_measure.reindex(index=uuindex)
                # intensity_cal_sensitivity = intensity_cal_sensitivity.reindex(index=uuindex)
                # intensity_cal_measure.interpolate(method='index', inplace=True, limit_direction='both')
                # intensity_cal_sensitivity.interpolate(method='index', inplace=True, limit_direction='both')

                # intensity_cal_measure["impinging_flux"] = intensity_cal_measure["counts"] * intensity_cal_measure["shape_factor"]/intensity_cal_sensitivity["eqe"]

                # intensity_cal_measure = intensity_cal_measure.reindex(index=spectrometer_index)

                # current_like = np.trapezoid(intensity_cal_measure["impinging_flux"].to_numpy().flatten(), intensity_cal_measure.index.to_numpy().flatten())

                # particle_scale_factor = intensity_measure / current_like

                
                # uuindex = intensity_cal_measure.index.union(sensitivity_bounds).unique()
                # intensity_cal_measure = intensity_cal_measure.reindex(index=uuindex)
                # intensity_cal_measure.interpolate(method='index', inplace=True, limit_direction="both")
                # intensity_measurement_mask = intensity_cal_measure.index.to_series().between(sensitivity_bounds[0], sensitivity_bounds[1])
                # intensity_cal_measure["E"] = self.nhc / intensity_cal_measure.index
                # intensity_cal_measure["power_like"] = intensity_cal_measure["shape_factor"] * intensity_cal_measure["counts"] * intensity_cal_measure["E"]
                # power_like_measured = np.trapezoid(intensity_cal_measure["power_like"][intensity_measurement_mask].to_numpy().flatten(), intensity_cal_measure.index[intensity_measurement_mask].to_numpy().flatten())

                #total_measured_spectral_flux_bounded = np.trapezoid(intensity_cal_measure["shape_factor"][intensity_measurement_mask].to_numpy().flatten()*intensity_cal_measure["counts"][intensity_measurement_mask].to_numpy().flatten(), intensity_cal_measure.index[intensity_measurement_mask].to_numpy().flatten())

                #cal_index = intensity_cal_measure.index


                # unscaled_power_spectrum = self.shape_scale_factor*intensity_cal_measure.to_numpy().flatten()
                # E_solar = nhc / intensity_cal_measure.index.to_numpy().flatten()  # [J]
                # unscaled_photon_density = unscaled_power_spectrum / E_solar  # [photons/s/m^2 per nm]
                # intensity_cal_measure["upd"] = unscaled_photon_density
                # uuindex  = intensity_cal_sensitivity.index.union(intensity_cal_measure.index).unique()
                # intensity_cal_sensitivity = intensity_cal_sensitivity.reindex(index=uuindex)
                # intensity_cal_measure = intensity_cal_measure.reindex(index=uuindex)
                # intensity_cal_sensitivity.interpolate(method='index', inplace=True, limit_direction='both')
                # intensity_cal_measure.interpolate(method='index', inplace=True, limit_direction='both')
                # intensity_cal_measure["unscaled_currents"] = intensity_cal_sensitivity["eqe"] * intensity_cal_measure["upd"] * q  # [A/m^2 per nm]
                # unscaled_currents = intensity_cal_measure.reindex(index=cal_index)["unscaled_currents"].to_numpy().flatten()
                
                # unscaled_current_measured = np.trapezoid(unscaled_currents, cal_index.to_numpy().flatten())  # [A/m^2]
                #scale_factor_to_actual = intensity_measure/unscaled_current_measured
                #self.intensity_scale_factor = intensity_measure/unscaled_current_measured*expected_irradiance  # multiply spectrometer readings by this to scale them to mW/cm^2
                
                cal_intensity = intensity_measure/intensity_nominal  # fractional intensity that the cal measurement was taken at 
                expected_power = P_am15_predict * cal_intensity   # in mW/cm^2
                intensity_scale_factor = expected_power/P_measure_prescale
                #measured_irradiance = np.trapezoid(self.shape_scale_factor*intensity_cal_measure[1].to_numpy().flatten(), cal_index.to_numpy().flatten())  # [A/m^2]
                #self.intensity_scale_factor = expected_irradiance/power_like_measured  # multiply spectrometer readings by this to scale them to mW/cm^2
                #self.intensity_scale_factor = particle_scale_factor
                self.intensity_scale_factor = intensity_scale_factor
                self.ylabel = "Spectral Irradiance [mW/cm^2 per nm]"
                if self.plot_current:
                    self.ylabel = "Spectral Current Density [mA/cm^2 per nm]"
                print(f"Using intensity calibration")
                self.fully_calibrated = True
            except Exception as e:
                print(f"No intensity calibration")
        except Exception as e:
            print(f"No shape calibration")
            print(f"No intensity calibration")
        
        if not self.fully_calibrated:
            self.enable_bars = False


    def update_wls(self):
        wls = self.spec.wavelengths()
        wls = wls[self.nclip_start::]
        if self.nclip_end > 0:
            wls = wls[:-self.nclip_end]
            
        self.wls = wls
        
        if self.export_raw_data_to_disk:
            np.savetxt(f"wls_{time.time()}.csv", self.wls, delimiter=",")
        
        self.E = self.nhc / wls

        print(self.exclude)
        clipped_min = self.wls < self.plot_min_nm
        self.exclude = clipped_min
        print(self.exclude)
        clipped_max = self.wls > self.plot_max_nm
        self.exclude |= clipped_max

        print(self.exclude)

        if self.am15 is not None:
            am15wls = self.am15.index.to_numpy().flatten()
            am15Es = self.nhc / am15wls
            am15g = self.am15["am15g"].to_numpy().flatten() / 10  # as mW/cm^2
            am15gi = am15g / am15Es * self.q
            mask = (am15wls >= self.bars_begin) & (am15wls < self.bars_end)
            nms = am15wls[mask]
            ps = am15g[mask]
            tehis = am15gi[mask]
            self.P_solar_expect = np.trapezoid(ps, nms)
            self.I_solar_expect = np.trapezoid(tehis, nms)


        # bars_clipped_min = self.wls < self.bars_begin
        # self.bars_exclude = bars_clipped_min

        # bars_clipped_max = self.wls > self.bars_end
        # self.bars_exclude |= bars_clipped_max

        return self.wls

    @property
    def integration_time_ms(self):
        return self._integration_time_ms

    @integration_time_ms.setter
    def integration_time_ms(self, value):
        old_time = self._integration_time_ms
        try:
            self.spec.integration_time_micros(value * 1000)
            # trash 2 measurements, one to flush the buffer, one to disard what's in process
            self.get_counts()
            self.get_counts()
            self._integration_time_ms = value
        except Exception as e:
            self.spec.integration_time_micros(old_time * 1000)
            self._integration_time_ms = old_time
            raise ValueError(f"Error setting integration time to {value}ms: {e}")

    def get_raw_counts(self, navgs=1):
        avgs = None
        for i in range(navgs):
            counts = self.spec.intensities(correct_dark_counts=self.correct_dark_counts, correct_nonlinearity=self.correct_nonlinearity)
            counts = counts[self.nclip_start::]
            if self.nclip_end > 0:
                counts = counts[:-self.nclip_end]
            counts_max = counts.max()
            if counts_max > self.count_clip_warning:
                print(f"Clip danger: {counts_max=}")
            avgs = np.vstack((avgs, counts)) if avgs is not None else counts
        
        if len(avgs.shape) == 2:
            retcounts = avgs.mean(axis=0)
        else:
            retcounts = avgs
        return retcounts


    def get_counts(self, navgs=1):
        ret = self.get_raw_counts(navgs)

        if self.zero_offset is not None:
            ret -= self.zero_offset

        if self.shape_scale_factor is not None:
            ret *= self.shape_scale_factor

        if self.intensity_scale_factor is not None:
            ret *= self.intensity_scale_factor

        return ret

    def prep_plot(self):
        (self.l,) = self.ax.plot(self.wls[~self.exclude], np.zeros(len(self.wls[~self.exclude])))
        if self.fully_calibrated:
            if self.am15 is not None:
                if self.enable_am15:
                    # plot in mW/cm^2
                    (self.am15line,) = self.ax.plot(self.am15.index.to_numpy().flatten(), self.am15["am15g"].to_numpy().flatten()/10)
            if self.enable_bars:
                #self.bars = self.ax2.stairs(np.zeros(len(self.bar_lefts)-1), self.bar_lefts, fill=True, color='yellow', edgecolor='black',linewidth=1)
                self.bars = self.ax2.bar(self.bar_lefts, np.zeros(len(self.bar_lefts)), align="edge", width=self.bar_widths, edgecolor="black", color="yellow")
                self.bar_labels = self.ax.bar_label(self.bars, label_type='center')
                self.ax2.set_xlim(self.xlim)
        self.ax.set_title("", y=1, pad=-14)
        self.ax.set_xlim(self.xlim)

        #print(f"a{len(self.ax.get_children())=}")

        to_return = [self.l, self.ax.title]
        if self.enable_bars:
            to_return.append(self.bars)
            to_return.append(self.bar_labels)

        return tuple(to_return)
    
    def do_zero(self, event=None):
        cal = self.cal_collect("zero")
        if cal is not None:
            self.zero_offset = cal
            #print(self.zero_offset)
            print(f"Zero offset updated")

    def do_shape(self, event=None):
        cal = self.cal_collect("shape")

    def do_one(self, event=None):
        cal = self.cal_collect("one")

    def cal_collect(self, atype=""):
        caldf = pd.DataFrame([])
        cal = None

        if self.zero_offset is None and atype != "zero":
            raise ValueError("Take a zero baseline before collecting calibration data.")
        else:
            cal = self.get_raw_counts(self.cal_avgs)

        if atype != "zero":
            cal -= self.zero_offset

        caldf = pd.DataFrame(cal)
        caldf.index = self.wls
        filename = Path(f"{atype}_spectrum_{self.integration_time_ms}ms_{time.time()}.csv")
        caldf.to_csv(path_or_buf=filename, header=[f"{atype}_counts_{self.cal_avgs}avgs_{self.integration_time_ms}ms",], index_label="# Wavelength [nm]")
        print(f"Saved file://{filename.absolute()}")
        return cal

    def update_data(self, frame, *fargs):
        #os.system('cls' if os.name == 'nt' else 'clear')
        # print(event)
        #print(frame)
        counts = self.get_counts(self.navgs)
        if self.fully_calibrated:
            y = counts / 10  # mW/cm^2 per nm
            if self.plot_current:
                y = y/self.E * self.q # mA/cm^2 per nm
        else:
            y = counts
        if self.export_raw_data_to_disk:
            np.savetxt(f"plot_data_{time.time()}.csv", y, delimiter=",")

        y_excluded = y[~self.exclude]
        i_ymax = np.argmax(y)
        ymax = y[i_ymax]
        self.l.set_ydata(y_excluded)
        if self.snapshot_pending: 
            self.ax.plot(self.wls[~self.exclude], y_excluded, color='tab:gray')
            self.snapshot_pending = False
        bar_heights = []
        if self.fully_calibrated:
            #total_irradiance = np.trapezoid(y, self.wls)
            mask = (self.wls >= self.bars_begin) & (self.wls < self.bars_end)
            nms = self.wls[mask]
            ps = y[mask]
            all_bar = np.trapezoid(ps, nms)
            #bars_irradiance = np.trapezoid(y[~self.bars_exclude], self.wls[~self.bars_exclude])
            #runsum = 0
            for zone in self.zones:
                mask = (self.wls >= zone["start"]) & (self.wls < zone["stop"])
                nms = self.wls[mask]
                ps = y[mask]
                this_bar = np.trapezoid(ps, nms)
                #print(f"{z_tot:0.3f}@{(zone["start"]+zone["stop"])/2}")
                z_percent = this_bar/all_bar * 100
                #runsum += z_percent
                bar_heights.append(z_percent)
                #bar_heights.append(5)
                percent_error = (z_percent - zone["p_nom"])/zone["p_nom"] * 100
                #print(f"{p_tot:0.1f}mW/cm^2 ({percent_error:0.1f}% error) on [{zone["start"]},{zone["stop"]})nm")
            #print(runsum)
            #self.ax.title.
            if self.plot_current:
                title_string = "Measured Current Density"
            else:
                title_string = "Measured Irradiance"
            title_string += f" on [{self.bars_begin},{self.bars_end}]nm = {all_bar:0.3f}"
            if self.plot_current:
                title_string += " mA/cm^2"
            else:
                title_string += " mW/cm^2"
            if self.P_solar_expect:
                if not self.plot_current:
                    title_string += f" (1Sun={self.P_solar_expect:0.1f})"
            if self.I_solar_expect:
                if self.plot_current:
                    title_string += f" (1Sun={self.I_solar_expect:0.1f})"
                
            self.ax.set_title(title_string, y=1, pad=-14)
            if self.enable_bars:
                #print(f"{self.bars.datavalues=}")
                #self.ax2.set_height(bar_heights)
                for abar,height,alabel in zip(self.bars, bar_heights, self.bar_labels):
                    abar.set_height(height)
                    alabel.set_text(f"{height:0.2f}%")
                #self.bar.datavalues = [float(h) for h in bar_heights]
                #self.bar.pchanged()
                
                #self.bar.set_data(bar_heights)
                self.ax2.relim()
                self.ax2.autoscale_view(True, False, True)
        else:
            #pass
            self.ax.set_title(f"Max = {ymax:0.3f} @ {self.wls[i_ymax]:0.1f} nm; {self.integration_time_ms:0.3f}ms exposure time", y=1, pad=-14)
        self.ax.relim()
        self.ax.autoscale_view(True, False, True)
        # print(f"{self.fig.get_children()=}")
        # for child in self.fig.get_children():
        #     print(f"{child=}")
        #     try:
        #         print(f"{child.get_bbox()=}")
        #     except:
        #         pass
        #     print(f"{child.get_children()=}")
        # print(f"{self.ax.get_children()=}")
        # for child in self.ax.get_children():
        #     print(f"{child=}")
        #     try:
        #         print(f"{child.get_bbox()=}")
        #     except:
        #         pass
        #     print(f"{child.get_children()=}")
        #print(f"b{len(self.ax.get_children())=}")

        to_return = [self.l, self.ax.title]

        if self.enable_bars:
            to_return.append(self.bars)
            to_return.append(self.bar_labels)

        return tuple(to_return)
        #plt.draw()
        # fig.savefig("spectrum.png")

    def run(self):
        self.fig, self.ax = plt.subplots()
        self.ax.autoscale(enable=True, axis="both", tight=True)
        plt.subplots_adjust(bottom=0.2, top=0.95)
        self.ax.set(xlabel="Wavelength [nm]", ylabel=self.ylabel)
        self.ax.grid()

        if self.fully_calibrated:
            if self.enable_bars:
                self.ax2 = self.ax.twinx()
                self.ax2.zorder = 0
                self.ax.set_zorder(self.ax2.get_zorder()+1)
                self.ax.patch.set_visible(False)
                self.ax2.autoscale(enable=True, axis="y", tight=True)

        self.type_radio = matplotlib.widgets.RadioButtons(plt.axes([0.01, 0.03, 0.05, 0.075]), ["p","i"])
        self.zero_btn = matplotlib.widgets.Button(        plt.axes([0.07, 0.03, 0.02, 0.075]), "0")
        self.once_btn = matplotlib.widgets.Button(        plt.axes([0.10, 0.03, 0.10, 0.075]), "Once")
        self.capture_btn = matplotlib.widgets.Button(     plt.axes([0.21, 0.03, 0.02, 0.075]), "C")
        self.export_btn = matplotlib.widgets.Button(      plt.axes([0.25, 0.03, 0.10, 0.075]), "Export")
        self.int_time_txt = matplotlib.widgets.TextBox(   plt.axes([0.50, 0.03, 0.10, 0.075]), "t_exp [ms]", str(self.integration_time_ms))
        self.pause_btn = matplotlib.widgets.Button(       plt.axes([0.65, 0.03, 0.10, 0.075]), "Pause")
        self.resume_btn = matplotlib.widgets.Button(      plt.axes([0.78, 0.03, 0.10, 0.075]), "Resume")
        self.shape_btn = matplotlib.widgets.Button(       plt.axes([0.91, 0.03, 0.02, 0.075]), "S")
        self.one_btn = matplotlib.widgets.Button(         plt.axes([0.95, 0.03, 0.02, 0.075]), "1")
        self.avgs_sldr = matplotlib.widgets.Slider(       plt.axes([0.90, 0.20, 0.10, 0.650]), "nAvg", 1, 50, valinit=1, valstep=1, orientation="vertical")

        self.type_radio.on_clicked(self.update_type)
        self.pause_btn.on_clicked(self.pause)
        self.resume_btn.on_clicked(self.resume)
        self.once_btn.on_clicked(self.update_data)
        self.export_btn.on_clicked(self.export)
        self.int_time_txt.on_submit(self.int_time_cb)
        self.zero_btn.on_clicked(self.do_zero)
        self.one_btn.on_clicked(self.do_one)
        self.shape_btn.on_clicked(self.do_shape)
        self.avgs_sldr.on_changed(self.update_avgs)
        self.capture_btn.on_clicked(self.snapshot)
        self.ani = animation.FuncAnimation(self.fig, func=self.update_data, frames=itertools.count, init_func=self.prep_plot, interval=self.min_plot_update_ms, save_count=10, blit=False)
        plt.show()
        print("Goodbye.")
    
    def snapshot(self, event=None):
        self.snapshot_pending = True

    def update_type(self, event=None):
        if self.type_radio.index_selected == 0:
            self.plot_current = False
            self.am15line.set_ydata(self.am15["am15g"])
            self.ylabel = "Spectral Irradiance [mW/cm^2 per nm]"
            self.ax.set(ylabel=self.ylabel)         
        elif self.type_radio.index_selected == 1:
            self.plot_current = True
            self.ylabel = "Spectral Current Density [mA/cm^2 per nm]"
            self.ax.set(ylabel=self.ylabel)
            self.am15line.set_ydata(self.am15["current_density_ma"])
        else:
            raise ValueError("Bad plot type.")

    def update_avgs(self, event=None):
        self.navgs = int(event)
        print(f"Now doing {self.navgs} averages.")

    def int_time_cb(self, event=None):
        try:
            self.integration_time_ms = float(event)
        except Exception as e:
            print(repr(e))
        self.int_time_txt.set_val(str(self.integration_time_ms))

    def export(self, event=None, prefix=""):
        x = self.l.get_xdata()
        y = self.l.get_ydata()
        xy = np.column_stack((x, y))
        filename = Path(f"{prefix}spectrum_{self.integration_time_ms}ms_{time.time()}.csv")
        np.savetxt(filename, xy, delimiter=",", header="Wavelength [nm], Counts", comments='# ')
        print(f"Saved file://{filename.absolute()}")

    def pause(self, event=None):
        self.ani.pause()

    def resume(self, event=None):
        self.ani.resume()


def main(plot_example=True):
    sblp = SBLivePlot()
    if plot_example == True:
        sblp.run()
        plt.show()
    else:  # non-plotting example
        wls = sblp.wls
        print(f"{wls=}")

        counts = sblp.get_counts()
        print(f"{counts=}")

        sblp.integration_time_ms = 300
        counts = sblp.get_counts()
        print(f"{counts=}")

        sblp.integration_time_ms = 50
        counts = sblp.get_counts()
        print(f"{counts=}")

        sblp.integration_time_ms = 5000
        counts = sblp.get_counts()
        print(f"{counts=}")

        sblp.integration_time_ms = 30
        counts = sblp.get_counts()
        print(f"{counts=}")

        print("Done!")


if __name__ == "__main__":
    main()
