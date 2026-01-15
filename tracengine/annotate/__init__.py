"""
TRACE Annotate Module

Event detection and annotation plugins.
"""

from tracengine.annotate.base import AnnotatorBase
from tracengine.annotate.registry import (
    register_annotator,
    get_annotator,
    list_annotators,
    annotator_registry,
    get_registry,
)

# Built-in annotators
from tracengine.annotate.builtins.threshold import ThresholdAnnotator
from tracengine.annotate.builtins.peak import PeakAnnotator
from tracengine.annotate.builtins.interval import IntervalAnnotator
from tracengine.annotate.manual.interval import ManualIntervalAnnotator
from tracengine.annotate.manual.timepoint import ManualTimepointAnnotator

# Auto-register built-in annotators
register_annotator(ThresholdAnnotator)
register_annotator(PeakAnnotator)
register_annotator(IntervalAnnotator)
register_annotator(ManualIntervalAnnotator)
register_annotator(ManualTimepointAnnotator)

__all__ = [
    "AnnotatorBase",
    "register_annotator",
    "get_annotator",
    "list_annotators",
    "annotator_registry",
    "get_registry",
    "ThresholdAnnotator",
    "PeakAnnotator",
    "IntervalAnnotator",
    "ManualIntervalAnnotator",
    "ManualTimepointAnnotator",
]
