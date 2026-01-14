"""
ThresholdAnnotator - Detect signal threshold crossings.
"""

import numpy as np
from tracetool.annotate.base import AnnotatorBase
from tracetool.data.descriptors import Event, ChannelSpec, RunData
from typing import List, Dict, Any


class ThresholdAnnotator(AnnotatorBase):
    """
    Detect timepoints where a signal crosses a threshold.

    Produces timepoint events at each crossing.
    """

    name = "ThresholdAnnotator"
    version = "1.0.0"
    produces = "timepoint"

    required_channels = {
        "signal": ChannelSpec(semantic_role="signal")  # Must be bound at runtime
    }

    @classmethod
    def get_parameters(cls) -> List[Dict[str, Any]]:
        return [
            {
                "name": "threshold",
                "label": "Threshold",
                "type": "float",
                "default": 0.0,
                "step": 0.1,
            },
            {
                "name": "direction",
                "label": "Direction",
                "type": "enum",
                "options": ["rising", "falling", "both"],
                "default": "rising",
            },
        ]

    def annotate(self, run: RunData, **inputs) -> list[Event]:
        t, y = inputs["signal"]
        threshold = inputs.get("threshold", 0.0)
        direction = inputs.get("direction", "rising")

        events = []

        # Find crossings
        above = y > threshold

        if direction in ("rising", "both"):
            # Rising: was below, now above
            rising_crossings = np.where(~above[:-1] & above[1:])[0] + 1
            for idx in rising_crossings:
                events.append(
                    Event(
                        annotator=self.name,
                        name="threshold_rising",
                        event_type="timepoint",
                        onset=t[idx],
                        offset=None,
                        confidence=1.0,
                        metadata={"threshold": threshold, "direction": "rising"},
                    )
                )

        if direction in ("falling", "both"):
            # Falling: was above, now below
            falling_crossings = np.where(above[:-1] & ~above[1:])[0] + 1
            for idx in falling_crossings:
                events.append(
                    Event(
                        annotator=self.name,
                        name="threshold_falling",
                        event_type="timepoint",
                        onset=t[idx],
                        offset=None,
                        confidence=1.0,
                        metadata={"threshold": threshold, "direction": "falling"},
                    )
                )

        # Sort by time
        events.sort(key=lambda e: e.onset)
        return events
