#!/usr/bin/env python3

# a live plotter for oceanoptics spectrometers
# needs https://github.com/ap--/python-seabreeze

# written by grey@christoforo.net

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


# usage:
# 1. run it with ./sb-spectral-cal.py
#    - cover the sensor and click the "Z" button to collect a zero baseline
#    - point the sensor at something with a known power emission shape and click the "S" button to collect the shape cal data file
#    - record the path of the "shape" calibration file and know the expected emission shape
# 3. run it with ./sb-spectral-cal.py
#    - cover the sensor and click the "Z" button to collect a zero baseline, record the path of the "zero" calibration file
#    - point the sensor at something with constant irradiance and click the "1" button to collect the intensity cal data file
#    - record the path of the "one" calibration file
#    - replace the sensor with an calibrated intensity measuring device
#    - record the intensity value measured by the calibrated intensity measuring device, know the nominal 1 sun expected intensity value for the calibrated device and know its spectral sensitivity or EQE
# 4. now run it with ./sb-spectral-cal.py offset_cal.csv known_power_shape.csv measured_power_shape.csv measured_intensity.csv known_cal_sensitivity.csv 1_sun_intensity_value measured_intensity_value

# def power_to_photonflux(power:pd.DataFrame, esolar):
#     flux_frame = power.copy()
#     flux_frame[1] = flux_frame[1] / esolar
#     flux_frame["scaler"] = E_solar
#     return flux_frame


class SBLivePlot(object):
    am15 = None
    correct_nonlinearity = True
    correct_dark_counts = True
    sensitivity_file_format:Literal["EQE","Spectral Sensitivity"] = "Spectral Sensitivity"
    _integration_time_ms = 10
    count_clip_warning = 60000
    min_plot_update_ms = 200
    am15_file = Path("ISO9845-1.csv")  # curl https://www.nlr.gov/media/docs/libraries/grid/zip/astmg173.zip | bsdtar -xOf- ASTMG173.csv | tail -n +2 | sed '1s|.*|nm,am0,am15g,am15d[W*m-2*nm-1]|' > ISO9845-1.csv
    navgs = 1
    cal_avgs = 50  # number of averages to do for calibration measurements
    plot_min_nm = float(0.0)
    plot_max_nm = float("inf")
    #plot_min_nm = float(350)
    plot_max_nm = float(1080)
    #power_calc_min = plot_min_nm
    #power_calc_max = plot_max_nm
    spec = None
    wls = np.array([])
    E_solar = np.array([])
    ax = None
    ani = None
    l = None
    fig = None
    export_raw_data_to_disk = False
    clip_first = True  # ignore the first spectral point
    shape_scale_factor = None
    zero_offset = None
    exclude = None   # true for wavelengths to not plot
    intensity_scale_factor = None
    lasty = None
    ylabel="Intensity [arbitrary units]"
    zones=[]


    def __init__(self, spec_num=0):
        if self.am15_file.is_file():
            self.am15 = pd.read_table(self.am15_file, sep=None, comment='#', engine='python', index_col=0, header="infer")
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
                "stop":  1200,
                "p_nom": 16.69,
            }
        )
        devs = spectrometers.list_devices()

        try:
            self.spec = spectrometers.Spectrometer(devs[spec_num])
        except Exception as e:
            raise ValueError(f"Initial spectrometer setup failed. Is the spectrometer connected and powered on? Error: {e}")
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
            measure_idx = shape_cal_measure.index
            shape_cal_truth =   pd.read_table(shape_cal_truth_file, sep=None, comment='#', engine='python', index_col=0, header=None)
            index = shape_cal_measure.index.union(shape_cal_truth.index).unique()
            shape_cal_measure = shape_cal_measure.reindex(index=index)
            shape_cal_truth = shape_cal_truth.reindex(index=index)
            shape_cal_truth.interpolate(method='index', inplace=True, limit_direction='both')
            shape_cal_measure.interpolate(method='index', inplace=True, limit_direction='both')
            shape_scale_factor = shape_cal_truth/shape_cal_measure
            self.shape_scale_factor = shape_scale_factor.reindex(index=measure_idx).to_numpy().flatten()
            print(f"Using shape calibration")
            try:
                h = 6.62607004081e-34  # [m^2*kg/s] planck constant
                c = 299792458  # [m/s] speed of light
                hc = h * c  # [J*m]
                nhc = hc * 1e9  # [J*nm]
                q = 1.60217657e-19  # elementary charge, [C] or [A*s]
                nhcperq = hc/q * 1e9  # [nW/A]
                intensity_cal_reading_file = Path(sys.argv[4])  # what we measured
                intensity_cal_sensitivity_file = Path(sys.argv[5])  # in eqe or spectral sensitivity format (select the right one below)
                self.sensitivity_file_format = "Spectral Sensitivity"
                intensity_nominal = float(sys.argv[6])  # nominal intensity value under 1000.0 W/m^2 (mA maybe, units will cancel) for the calibration device
                intensity_measure = float(sys.argv[7])  # value that corresponds to the intensity_cal_reading_file (mA maybe, units will cancel)
                intensity_cal_measure = pd.read_table(intensity_cal_reading_file, sep=None, comment='#', engine='python', index_col=0, header=None)
                measured_irradiance = np.trapezoid(self.shape_scale_factor*intensity_cal_measure.to_numpy().flatten(), intensity_cal_measure.to_numpy().flatten()) 
                cal_index = intensity_cal_measure.index
                intensity_cal_sensitivity = pd.read_table(intensity_cal_sensitivity_file, sep=None, comment='#', engine='python', index_col=0, header=None)
                if self.sensitivity_file_format == "Spectral Sensitivity":  # let's convert that to EQE
                    eqe = nhcperq * intensity_cal_sensitivity.to_numpy().flatten() / intensity_cal_sensitivity.index.to_numpy().flatten()
                elif self.sensitivity_file_format == "EQE":
                    eqe = intensity_cal_sensitivity.to_numpy().flatten()
                else:
                    raise ValueError("Uknown sensitivity file format.")
                intensity_cal_sensitivity["eqe"] = eqe

                unscaled_power_spectrum = self.shape_scale_factor*intensity_cal_measure.to_numpy().flatten()
                E_solar = nhc / intensity_cal_measure.index.to_numpy().flatten()  # [J]
                unscaled_photon_density = unscaled_power_spectrum / E_solar  # [photons/s/m^2 per nm]
                intensity_cal_measure["upd"] = unscaled_photon_density
                uuindex  = intensity_cal_sensitivity.index.union(intensity_cal_measure.index).unique()
                intensity_cal_sensitivity = intensity_cal_sensitivity.reindex(index=uuindex)
                intensity_cal_measure = intensity_cal_measure.reindex(index=uuindex)
                intensity_cal_sensitivity.interpolate(method='index', inplace=True, limit_direction='both')
                intensity_cal_measure.interpolate(method='index', inplace=True, limit_direction='both')
                intensity_cal_measure["unscaled_currents"] = intensity_cal_sensitivity["eqe"] * intensity_cal_measure["upd"] * q  # [A/m^2 per nm]
                unscaled_currents = intensity_cal_measure.reindex(index=cal_index)["unscaled_currents"].to_numpy().flatten()
                
                unscaled_current_measured = np.trapezoid(unscaled_currents, cal_index.to_numpy().flatten())  # [A/m^2]
                #scale_factor_to_actual = intensity_measure/unscaled_current_measured
                #self.intensity_scale_factor = intensity_measure/unscaled_current_measured*expected_irradiance  # multiply spectrometer readings by this to scale them to mW/cm^2
                
                cal_intensity = intensity_measure/intensity_nominal  # fractional intensity that the calibration was done at
                expected_irradiance = 100 * cal_intensity   # in mW/cm^2
                #measured_irradiance = np.trapezoid(self.shape_scale_factor*intensity_cal_measure[1].to_numpy().flatten(), cal_index.to_numpy().flatten())  # [A/m^2]
                self.intensity_scale_factor = expected_irradiance/measured_irradiance  # multiply spectrometer readings by this to scale them to mW/cm^2

                self.ylabel = "Spectral irradiance [mW/cm^2 per nm]"
                print(f"Using intensity calibration")
            except Exception as e:
                print(f"No intensity calibration")
        except Exception as e:
            print(f"No shape calibration: {e}")
            print(f"No intensity calibration")


    def update_wls(self):
        if self.clip_first:
            self.wls = self.spec.wavelengths()[1::]
        else:
            self.wls = self.spec.wavelengths()
        if self.export_raw_data_to_disk:
            np.savetxt(f"wls_{time.time()}.csv", self.wls, delimiter=",")
        
        # h = 6.62607004081e-34  # [m^2*kg/s] planck constant
        # c = 299792458  # [m/s] speed of light
        # hc = h * c  # [J*m]
        # self.E_solar = hc / (self.wls * 1e-9)


        clipped_min = self.wls < self.plot_min_nm
        self.exclude = clipped_min

        clipped_max = self.wls > self.plot_max_nm
        self.exclude |= clipped_max

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
            counts_max = counts.max()
            if counts_max > self.count_clip_warning:
                print(f"Clip danger: {counts_max=}")
            if self.clip_first:
                counts = counts[1::]
            avgs = np.vstack((avgs, counts)) if avgs is not None else counts
        
        if len(avgs.shape) == 2:
            retcounts = avgs.mean(axis=0)
        else:
            retcounts = avgs
        return retcounts


    def get_counts(self, navgs=1):
        retcounts = self.get_raw_counts(navgs)

        if self.zero_offset is not None:
            retcounts -= self.zero_offset
        if self.shape_scale_factor is not None:
            ret = retcounts*self.shape_scale_factor
        else:
            ret = retcounts
        if self.intensity_scale_factor is not None:
            ret *= self.intensity_scale_factor
        return ret

    def prep_plot(self):
        (self.l,) = self.ax.plot(self.wls[~self.exclude], np.zeros(len(self.wls[~self.exclude])))
        if self.am15 is not None:
            (self.am15line,) = self.ax.plot(self.am15.index.to_numpy().flatten(), self.am15["am15g"].to_numpy().flatten()/10)
        self.ax.set_title("", y=1, pad=-14)
        #print(f"a{len(self.ax.get_children())=}")

        return self.l, self.ax.title
    
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
        y = self.get_counts(self.navgs)
        if self.export_raw_data_to_disk:
            np.savetxt(f"counts_{time.time()}.csv", y, delimiter=",")

        i_ymax = np.argmax(y)
        ymax = y[i_ymax]
        self.l.set_ydata(y[~self.exclude])
        if "rradiance" in self.ylabel:
            irradiance = np.trapezoid(y, self.wls)
            for zone in self.zones:
                mask = (self.wls >= zone["start"]) & (self.wls < zone["stop"])
                nms = self.wls[mask]
                ps = y[mask]
                p_tot = np.trapezoid(ps, nms)
                percent_error = (p_tot - zone["p_nom"])/zone["p_nom"] * 100
                #print(f"{p_tot:0.1f}mW/cm^2 ({percent_error:0.1f}% error) on [{zone["start"]},{zone["stop"]})nm")
            #self.ax.title.
            self.ax.set_title(f"Irradiance = {irradiance:0.3f} mW/cm^2; {self.integration_time_ms:0.3f}ms exposure time", y=1, pad=-14)
        else:
            #pass
            self.ax.set_title(f"Max = {ymax:0.3f} @ {self.wls[i_ymax]:0.1f} nm; {self.integration_time_ms:0.3f}ms exposure time", y=1, pad=-14)
        self.ax.relim()
        self.ax.autoscale_view(True, True, True)
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
        return self.l, self.ax.title

        #plt.draw()
        # fig.savefig("spectrum.png")

    def run(self):
        self.fig, self.ax = plt.subplots()
        self.ax.autoscale(enable=True, axis="both", tight=True)
        plt.subplots_adjust(bottom=0.2, top=0.95)
        self.ax.set(xlabel="Wavelength [nm]", ylabel=self.ylabel)
        self.ax.grid()

        self.zero_btn = matplotlib.widgets.Button(     plt.axes([0.05, 0.03, 0.02, 0.075]), "0")
        self.once_btn = matplotlib.widgets.Button(     plt.axes([0.10, 0.03, 0.10, 0.075]), "Once")
        self.export_btn = matplotlib.widgets.Button(   plt.axes([0.25, 0.03, 0.10, 0.075]), "Export")
        self.int_time_txt = matplotlib.widgets.TextBox(plt.axes([0.50, 0.03, 0.10, 0.075]), "t_exp [ms]", str(self.integration_time_ms))
        self.pause_btn = matplotlib.widgets.Button(    plt.axes([0.65, 0.03, 0.10, 0.075]), "Pause")
        self.resume_btn = matplotlib.widgets.Button(   plt.axes([0.78, 0.03, 0.10, 0.075]), "Resume")
        self.shape_btn = matplotlib.widgets.Button(    plt.axes([0.91, 0.03, 0.02, 0.075]), "S")
        self.one_btn = matplotlib.widgets.Button(      plt.axes([0.95, 0.03, 0.02, 0.075]), "1")
        self.avgs_sldr = matplotlib.widgets.Slider(    plt.axes([0.90, 0.20, 0.10, 0.650]), "nAvg", 1, 50, valinit=1, valstep=1, orientation="vertical")

        self.pause_btn.on_clicked(self.pause)
        self.resume_btn.on_clicked(self.resume)
        self.once_btn.on_clicked(self.update_data)
        self.export_btn.on_clicked(self.export)
        self.int_time_txt.on_submit(self.int_time_cb)
        self.zero_btn.on_clicked(self.do_zero)
        self.one_btn.on_clicked(self.do_one)
        self.shape_btn.on_clicked(self.do_shape)
        self.avgs_sldr.on_changed(self.update_avgs)
        self.ani = animation.FuncAnimation(self.fig, func=self.update_data, frames=itertools.count, init_func=self.prep_plot, interval=self.min_plot_update_ms, save_count=10, blit=False)
        plt.show()
        print("Goodbye.")

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
        x = self.wls
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
