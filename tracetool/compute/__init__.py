"""
TraceTool Compute Module

Metric extraction and computation plugins.
"""

from tracetool.compute.base import ComputeBase
from tracetool.compute.registry import (
    register_compute,
    get_compute,
    list_compute,
    compute_registry,
    get_registry,
)

# Built-in compute modules
from tracetool.compute.builtins.summary_stats import SummaryStats

# Auto-register built-in compute modules
register_compute(SummaryStats)

__all__ = [
    "ComputeBase",
    "register_compute",
    "get_compute",
    "list_compute",
    "compute_registry",
    "get_registry",
    "SummaryStats",
]
