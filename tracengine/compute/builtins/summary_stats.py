"""
SummaryStats - Calculate summary statistics for signal channels.
"""

import numpy as np
import pandas as pd
from tracengine.compute.base import ComputeBase
from tracengine.data.descriptors import ChannelSpec, RunData
from tracengine.utils.signal_processing import compute_derivative
from typing import List, Dict, Any


class SummaryStats(ComputeBase):
    """
    Compute summary statistics for signal channels.

    Calculates mean, std, min, max, median, and optionally
    percentiles and derivative statistics.
    """

    name = "SummaryStats"
    version = "1.0.0"

    required_channels = {
        "signal": ChannelSpec(semantic_role="signal")  # Must be bound at runtime
    }
    required_events = {}  # No events required

    @classmethod
    def get_parameters(cls) -> List[Dict[str, Any]]:
        return [
            {
                "name": "percentiles",
                "label": "Percentiles (comma-separated)",
                "type": "str",
                "default": "25,75",
            },
            {
                "name": "include_derivatives",
                "label": "Include Derivative Stats",
                "type": "bool",
                "default": False,
            },
            {
                "name": "include_range",
                "label": "Include Range (max-min)",
                "type": "bool",
                "default": True,
            },
            {
                "name": "include_iqr",
                "label": "Include IQR",
                "type": "bool",
                "default": True,
            },
            {
                "name": "include_skew_kurtosis",
                "label": "Include Skewness/Kurtosis",
                "type": "bool",
                "default": False,
            },
        ]

    def compute(self, run: RunData, **inputs) -> pd.DataFrame:
        t, y = inputs["signal"]

        # Parse parameters
        percentiles_str = inputs.get("percentiles", "25,75")
        include_derivatives = inputs.get("include_derivatives", False)
        include_range = inputs.get("include_range", True)
        include_iqr = inputs.get("include_iqr", True)
        include_skew_kurtosis = inputs.get("include_skew_kurtosis", False)

        # Parse percentiles
        try:
            percentiles = [
                float(p.strip()) for p in percentiles_str.split(",") if p.strip()
            ]
        except ValueError:
            percentiles = [25, 75]

        # Basic statistics
        stats = {
            "mean": np.nanmean(y),
            "std": np.nanstd(y),
            "min": np.nanmin(y),
            "max": np.nanmax(y),
            "median": np.nanmedian(y),
            "count": len(y),
            "valid_count": np.sum(~np.isnan(y)),
        }

        # Percentiles
        for pct in percentiles:
            stats[f"p{int(pct)}"] = np.nanpercentile(y, pct)

        # Range
        if include_range:
            stats["range"] = stats["max"] - stats["min"]

        # IQR
        if include_iqr:
            q1 = np.nanpercentile(y, 25)
            q3 = np.nanpercentile(y, 75)
            stats["iqr"] = q3 - q1

        # Skewness and Kurtosis
        if include_skew_kurtosis:
            from scipy.stats import skew, kurtosis

            stats["skewness"] = skew(y[~np.isnan(y)])
            stats["kurtosis"] = kurtosis(y[~np.isnan(y)])

        # Derivative statistics
        if include_derivatives:
            try:
                dy = compute_derivative(t, y, order=1)
                stats["derivative_mean"] = np.nanmean(dy)
                stats["derivative_std"] = np.nanstd(dy)
                stats["derivative_max"] = np.nanmax(np.abs(dy))
            except Exception:
                pass

        return pd.DataFrame([stats])
