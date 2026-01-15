import numpy as np
from scipy import signal as sp_signal
from .base import SignalProcessor
from .registry import register_processor


@register_processor
class ButterworthProcessor(SignalProcessor):
    name = "butter"
    description = "Butterworth Low-pass Filter"

    @classmethod
    def get_parameters(cls):
        return [
            {
                "name": "order",
                "label": "Order",
                "type": "int",
                "default": 4,
                "min": 1,
                "max": 10,
            },
            {
                "name": "cutoff",
                "label": "Cutoff Freq",
                "type": "float",
                "default": 10.0,
                "min": 0.1,
                "max": 1000.0,
                "suffix": " Hz",
            },
        ]

    def process(self, data, sampling_rate, **kwargs):
        order = kwargs.get("order", 4)
        cutoff = kwargs.get("cutoff", 10.0)

        # Normalize cutoff frequency
        nyq = 0.5 * sampling_rate
        if nyq <= 0:
            return data

        normal_cutoff = cutoff / nyq

        # Ensure cutoff is within valid range
        if normal_cutoff >= 1.0:
            normal_cutoff = 0.99
        if normal_cutoff <= 0.0:
            normal_cutoff = 0.01

        # Design filter
        b, a = sp_signal.butter(order, normal_cutoff, btype="low", analog=False)
        return sp_signal.filtfilt(b, a, data)


@register_processor
class SavitzkyGolayProcessor(SignalProcessor):
    name = "savitzky_golay"
    description = "Savitzky-Golay Filter"

    @classmethod
    def get_parameters(cls):
        return [
            {
                "name": "window_length",
                "label": "Window Length (odd)",
                "type": "int",
                "default": 11,
                "min": 3,
                "max": 999,
                "step": 2,
            },
            {
                "name": "polyorder",
                "label": "Poly Order",
                "type": "int",
                "default": 3,
                "min": 1,
                "max": 10,
            },
        ]

    def process(self, data, sampling_rate, **kwargs):
        window_length = kwargs.get("window_length", 11)
        polyorder = kwargs.get("polyorder", 3)

        # Ensure window_length is odd
        if window_length % 2 == 0:
            window_length += 1

        # Ensure polyorder is less than window_length
        if polyorder >= window_length:
            polyorder = window_length - 1

        return sp_signal.savgol_filter(data, window_length, polyorder)


@register_processor
class RollingMeanProcessor(SignalProcessor):
    name = "rolling_mean"
    description = "Rolling Mean / Moving Average"

    @classmethod
    def get_parameters(cls):
        return [
            {
                "name": "window_size",
                "label": "Window Size",
                "type": "int",
                "default": 5,
                "min": 2,
                "max": 1000,
            }
        ]

    def process(self, data, sampling_rate, **kwargs):
        window_size = kwargs.get("window_size", 5)
        # Simple convolution for moving average
        kernel = np.ones(window_size) / window_size
        # Use mode='same' to keep size
        return np.convolve(data, kernel, mode="same")
