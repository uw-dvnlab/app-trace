"""
IntervalAnnotator - Mark regions based on threshold conditions.
"""

import numpy as np
from tracengine.annotate.base import AnnotatorBase
from tracengine.data.descriptors import Event, ChannelSpec, RunData
from typing import List, Dict, Any


class IntervalAnnotator(AnnotatorBase):
    """
    Mark intervals where a signal meets a threshold condition.

    Supports multiple modes:
    - above: value > threshold
    - below: value < threshold
    - between: lower < value < upper
    - outside: value < lower OR value > upper
    - abs_below: |value| < threshold

    Produces interval events with onset and offset times.
    """

    name = "IntervalAnnotator"
    version = "1.0.0"
    produces = "interval"

    required_channels = {"signal": ChannelSpec(semantic_role="signal")}

    @classmethod
    def get_parameters(cls) -> List[Dict[str, Any]]:
        return [
            {
                "name": "mode",
                "label": "Condition Mode",
                "type": "enum",
                "options": ["above", "below", "between", "outside", "abs_below"],
                "default": "above",
            },
            {
                "name": "threshold",
                "label": "Threshold",
                "type": "float",
                "default": 0.0,
                "step": 0.1,
            },
            {
                "name": "lower_threshold",
                "label": "Lower Threshold (for between/outside)",
                "type": "float",
                "default": -1.0,
                "step": 0.1,
            },
            {
                "name": "upper_threshold",
                "label": "Upper Threshold (for between/outside)",
                "type": "float",
                "default": 1.0,
                "step": 0.1,
            },
            {
                "name": "min_duration",
                "label": "Minimum Duration",
                "type": "float",
                "default": 0.0,
                "min": 0.0,
                "step": 0.01,
                "suffix": "s",
            },
        ]

    def annotate(self, run: RunData, **inputs) -> list[Event]:
        t, y = inputs["signal"]
        mode = inputs.get("mode", "above")
        threshold = inputs.get("threshold", 0.0)
        lower = inputs.get("lower_threshold", -1.0)
        upper = inputs.get("upper_threshold", 1.0)
        min_duration = inputs.get("min_duration", 0.0)

        # Determine condition mask based on mode
        if mode == "above":
            mask = y > threshold
            event_name = f"above_{threshold}"
        elif mode == "below":
            mask = y < threshold
            event_name = f"below_{threshold}"
        elif mode == "between":
            mask = (y > lower) & (y < upper)
            event_name = f"between_{lower}_{upper}"
        elif mode == "outside":
            mask = (y < lower) | (y > upper)
            event_name = f"outside_{lower}_{upper}"
        elif mode == "abs_below":
            mask = np.abs(y) < threshold
            event_name = f"abs_below_{threshold}"
        else:
            mask = y > threshold
            event_name = "interval"

        # Find contiguous regions
        events = []
        in_region = False
        start_idx = 0

        for i, is_active in enumerate(mask):
            if is_active and not in_region:
                # Start of region
                in_region = True
                start_idx = i
            elif not is_active and in_region:
                # End of region
                in_region = False
                onset = t[start_idx]
                offset = t[i - 1]
                duration = offset - onset

                if duration >= min_duration:
                    events.append(
                        Event(
                            annotator=self.name,
                            name=event_name,
                            event_type="interval",
                            onset=onset,
                            offset=offset,
                            confidence=1.0,
                            metadata={
                                "mode": mode,
                                "duration": float(duration),
                            },
                        )
                    )

        # Handle case where region extends to end
        if in_region:
            onset = t[start_idx]
            offset = t[-1]
            duration = offset - onset

            if duration >= min_duration:
                events.append(
                    Event(
                        annotator=self.name,
                        name=event_name,
                        event_type="interval",
                        onset=onset,
                        offset=offset,
                        confidence=1.0,
                        metadata={
                            "mode": mode,
                            "duration": float(duration),
                        },
                    )
                )

        return events
