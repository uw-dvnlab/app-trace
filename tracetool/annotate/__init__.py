"""
TraceTool Annotate Module

Event detection and annotation plugins.
"""

from tracetool.annotate.base import AnnotatorBase
from tracetool.annotate.registry import (
    register_annotator,
    get_annotator,
    list_annotators,
    annotator_registry,
    get_registry,
)

# Built-in annotators
from tracetool.annotate.builtins.threshold import ThresholdAnnotator
from tracetool.annotate.builtins.peak import PeakAnnotator
from tracetool.annotate.builtins.interval import IntervalAnnotator
from tracetool.annotate.manual.interval import ManualIntervalAnnotator
from tracetool.annotate.manual.timepoint import ManualTimepointAnnotator

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
