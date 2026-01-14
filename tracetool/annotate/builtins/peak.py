"""
PeakAnnotator - Detect local maxima using scipy.signal.find_peaks.
"""

from scipy.signal import find_peaks
from tracetool.annotate.base import AnnotatorBase
from tracetool.data.descriptors import Event, ChannelSpec, RunData
from typing import List, Dict, Any


class PeakAnnotator(AnnotatorBase):
    """
    Detect local maxima (peaks) in a signal.

    Uses scipy.signal.find_peaks with configurable parameters.
    Produces timepoint events at each detected peak.
    """

    name = "PeakAnnotator"
    version = "1.0.0"
    produces = "timepoint"

    required_channels = {
        "signal": ChannelSpec(semantic_role="signal")  # Must be bound at runtime
    }

    @classmethod
    def get_parameters(cls) -> List[Dict[str, Any]]:
        return [
            {
                "name": "height",
                "label": "Minimum Height",
                "type": "float",
                "default": 0.0,
                "step": 0.1,
                "suffix": "",
            },
            {
                "name": "distance",
                "label": "Minimum Distance",
                "type": "int",
                "default": 1,
                "min": 1,
                "max": 1000,
                "suffix": "samples",
            },
            {
                "name": "prominence",
                "label": "Prominence",
                "type": "float",
                "default": 0.0,
                "min": 0.0,
                "step": 0.1,
            },
            {
                "name": "detect_valleys",
                "label": "Detect Valleys (Minima)",
                "type": "bool",
                "default": False,
            },
        ]

    def annotate(self, run: RunData, **inputs) -> list[Event]:
        t, y = inputs["signal"]
        height = inputs.get("height", None)
        distance = inputs.get("distance", 1)
        prominence = inputs.get("prominence", None)
        detect_valleys = inputs.get("detect_valleys", False)

        # Prepare find_peaks kwargs
        kwargs = {"distance": distance}
        if height and height > 0:
            kwargs["height"] = height
        if prominence and prominence > 0:
            kwargs["prominence"] = prominence

        events = []

        # Detect peaks (maxima)
        if not detect_valleys:
            peak_indices, properties = find_peaks(y, **kwargs)
            event_name = "peak"
        else:
            # For valleys, invert the signal
            peak_indices, properties = find_peaks(-y, **kwargs)
            event_name = "valley"

        for idx in peak_indices:
            events.append(
                Event(
                    annotator=self.name,
                    name=event_name,
                    event_type="timepoint",
                    onset=t[idx],
                    offset=None,
                    confidence=1.0,
                    metadata={
                        "value": float(y[idx]),
                        "index": int(idx),
                    },
                )
            )

        return events
