"""
TRACE Annotator Base

Base class for all annotation plugins.
Annotators detect events in signal data.
"""

from tracengine.data.descriptors import Event, ChannelSpec, RunData
from tracengine.data.resolve import resolve_all
from abc import ABC, abstractmethod
from typing import Literal, List, Dict, Any


class AnnotatorBase(ABC):
    """
    Base class for all annotators.

    Subclasses must define:
        - name: str
        - version: str (e.g., "1.0.0")
        - produces: "timepoint" or "interval"
        - required_channels: dict[str, ChannelSpec]

    Optionally override:
        - get_parameters() -> list of parameter definitions

    And implement:
        - annotate(run, **resolved_channels) -> list[Event]
    """

    name: str = "UnnamedAnnotator"
    version: str = "1.0.0"
    produces: Literal["timepoint", "interval"] = "timepoint"
    required_channels: dict[str, ChannelSpec] = {}

    @classmethod
    def get_parameters(cls) -> List[Dict[str, Any]]:
        """
        Return a list of configurable parameters for this annotator.

        Each parameter is a dict with:
        - name: internal name (passed to annotate())
        - label: display name for UI
        - type: 'int', 'float', 'bool', 'enum'
        - default: default value
        - min/max: bounds (for numbers)
        - step: increment (for numbers)
        - options: list of choices (for enum)
        - suffix: unit label (optional)
        """
        return []

    def run(
        self, run: RunData, instance_name: str | None = None, **params
    ) -> list[Event]:
        """
        Public API: resolve channels and call annotate.

        Args:
            run: The RunData to annotate
            instance_name: Instance name for looking up channel bindings
            **params: Runtime parameter values (from get_parameters)

        Returns:
            List of detected Event objects
        """
        if self.required_channels:
            resolved = resolve_all(
                run, self.required_channels, run.run_config, instance_name
            )
            channel_data = {}
            for role, channel in resolved.items():
                t, y = run.get_channel_data(channel)
                channel_data[role] = (t, y)
            return self.annotate(run, **channel_data, **params)
        else:
            # Fallback: pass signals dict for simple annotators
            return self.annotate(run, signals=run.signals, **params)

    @abstractmethod
    def annotate(self, run: RunData, **inputs) -> list[Event]:
        """
        Detect events in the data.

        Args:
            run: The RunData being annotated
            **inputs: Resolved channel data as (time, values) tuples,
                      plus runtime parameters

        Returns:
            List of Event objects
        """
        ...
