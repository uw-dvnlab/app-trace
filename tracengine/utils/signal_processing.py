import numpy as np

from tracengine.processing.registry import get_processor


def compute_derivative(time, values, order=1):
    """
    Compute determining derivative of signal using numpy gradient.

    Args:
        time: Time array.
        values: Signal array.
        order: Order of derivative (1=velocity, 2=acceleration).

    Returns:
        d_values: Derivative array.
    """
    d_values = values
    for _ in range(order):
        d_values = np.gradient(d_values, time)

    return d_values


def apply_filter(values, sampling_rate, filter_type="butter", **kwargs):
    """
    Apply a filter to the signal using the plugin system.

    Args:
        values: Signal array.
        sampling_rate: Sampling frequency in Hz.
        filter_type: Name of the processor (e.g., 'butter', 'savitzky_golay').
        **kwargs: Filter specific parameters.

    Returns:
        filtered_values: Filtered signal array.
    """
    processor_cls = get_processor(filter_type)
    if processor_cls:
        processor = processor_cls()
        return processor.process(values, sampling_rate, **kwargs)

    # Fallback to base or return values if not found
    return values
