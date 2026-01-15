"""
Pipeline Step Dataclasses

Defines the configuration objects for each step in a pipeline.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PreprocessingStep:
    """
    Configuration for a preprocessing operation on a channel.

    Attributes:
        channel: Channel identifier in "group:channel" format
        operations: List of operation configs, each with 'op' key and parameters

    Example:
        PreprocessingStep(
            channel="tablet_motion:X",
            operations=[
                {"op": "butter", "cutoff": 10, "order": 4},
                {"op": "savgol", "window_length": 11, "polyorder": 3}
            ]
        )
    """

    channel: str
    operations: list[dict] = field(default_factory=list)


@dataclass
class AnnotatorStep:
    """
    Configuration for running an annotator plugin.

    Attributes:
        name: Class name of the annotator (must be registered)
        channel_bindings: Optional override for channel bindings
        save_to: Output path template (supports {run}, {subject}, etc.)
        enabled: Whether this step is enabled
    """

    name: str
    channel_bindings: dict[str, str] | None = None  # Override project defaults
    save_to: str = "derived/{run}_annotations.json"
    enabled: bool = True


@dataclass
class ComputeStep:
    """
    Configuration for running a compute (metrics) plugin.

    Attributes:
        name: Class name of the compute module (must be registered)
        depends_on: List of annotator names that must run first
        channel_bindings: Optional override for channel bindings
        event_bindings: Optional override for event bindings
        output: Output path template for results
        enabled: Whether this step is enabled
    """

    name: str
    depends_on: list[str] = field(default_factory=list)
    channel_bindings: dict[str, str] | None = None
    event_bindings: dict[str, str] | None = None
    output: str = "derived/{run}_metrics.csv"
    enabled: bool = True


@dataclass
class ExportConfig:
    """
    Configuration for exporting pipeline results.

    Attributes:
        aggregate: Path template for aggregated metrics CSV (None to skip)
        summary_stats: Whether to compute summary statistics
        per_run: Whether to save per-run results
        format: Export format ("csv", "parquet", "json")
    """

    aggregate: str | None = "exports/aggregate_metrics.csv"
    summary_stats: bool = True
    per_run: bool = True
    format: str = "csv"


@dataclass
class PipelineStepResult:
    """Result from running a single pipeline step."""

    step_name: str
    step_type: str  # "preprocessing", "annotator", "compute"
    success: bool
    message: str = ""
    output: object = None  # Events, DataFrame, etc.
    duration_seconds: float = 0.0


def step_from_dict(data: dict) -> PreprocessingStep | AnnotatorStep | ComputeStep:
    """
    Create a step dataclass from a dictionary (e.g., from YAML).

    The dict must have a 'type' key to identify step type.
    """
    step_type = data.get("type", "annotator")

    if step_type == "preprocessing":
        return PreprocessingStep(
            channel=data["channel"],
            operations=data.get("operations", []),
        )
    elif step_type == "annotator":
        return AnnotatorStep(
            name=data["name"],
            channel_bindings=data.get("channel_bindings"),
            save_to=data.get("save_to", "derived/{run}_annotations.json"),
            enabled=data.get("enabled", True),
        )
    elif step_type == "compute":
        return ComputeStep(
            name=data["name"],
            depends_on=data.get("depends_on", []),
            channel_bindings=data.get("channel_bindings"),
            event_bindings=data.get("event_bindings"),
            output=data.get("output", "derived/{run}_metrics.csv"),
            enabled=data.get("enabled", True),
        )
    else:
        raise ValueError(f"Unknown step type: {step_type}")
