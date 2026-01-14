"""
Tracetool Channel Utilities

Central utilities for creating and managing derived channels.
All signal processing that affects annotation or compute must go through here.

GUIDING RULE: If a transformation affects annotation or compute,
it must produce a persistent derived channel.
"""

from tracetool.data.descriptors import (
    RunData,
    Channel,
    ChannelProvenance,
)
from tracetool.processing.registry import get_processor
from tracetool.utils.signal_processing import compute_derivative
from datetime import datetime
import pandas as pd
import numpy as np


# =============================================================================
# Naming Convention
# =============================================================================

# Format: {base}_{op1}_{op2}...
# | Operation         | Suffix       | Example            |
# |-------------------|--------------|-------------------|
# | Butterworth       | _bf{cutoff}  | X_bf10            |
# | Savitzky-Golay    | _sg          | X_sg              |
# | Rolling Mean      | _rm{window}  | X_rm5             |
# | Derivative        | _dN          | X_d1, X_d2        |
# | Detrend           | _dt          | X_dt              |
# | Resample          | _rs{hz}      | X_rs100           |


def get_derived_name(base_name: str, operation: str, params: dict) -> str:
    """
    Generate a derived channel name based on operation and parameters.

    Args:
        base_name: The source channel name (may already have suffixes)
        operation: The operation being applied
        params: Operation parameters

    Returns:
        New channel name with appropriate suffix
    """
    if operation == "butter":
        cutoff = int(params.get("cutoff", 10))
        return f"{base_name}_bf{cutoff}"
    elif operation == "savitzky_golay":
        return f"{base_name}_sg"
    elif operation == "rolling_mean":
        window = int(params.get("window_size", 5))
        return f"{base_name}_rm{window}"
    elif operation == "derivative":
        order = int(params.get("order", 1))
        return f"{base_name}_d{order}"
    elif operation == "detrend":
        return f"{base_name}_dt"
    elif operation == "resample":
        hz = int(params.get("target_hz", 100))
        return f"{base_name}_rs{hz}"
    else:
        # Generic suffix
        return f"{base_name}_{operation}"


# =============================================================================
# Derived Channel Creation
# =============================================================================


def create_derived_channel(
    run: RunData,
    group_name: str,
    source_channel: str,
    operation: str,
    params: dict,
    custom_suffix: str | None = None,
) -> Channel:
    """
    Create a derived channel and store it in the RunData.

    This is the central function for all signal processing that should
    persist and be available to annotators/compute.

    Args:
        run: The RunData to modify
        group_name: Name of the SignalGroup (modality)
        source_channel: Name of the source channel
        operation: Operation to apply ("butter", "derivative", etc.)
        params: Operation-specific parameters
        custom_suffix: Optional custom name instead of auto-generated

    Returns:
        Channel reference to the new derived channel

    Raises:
        KeyError: If group or source channel not found
        ValueError: If operation fails
    """
    if group_name not in run.signals:
        raise KeyError(f"SignalGroup '{group_name}' not found in run")

    signal_group = run.signals[group_name]

    if source_channel not in signal_group.data.columns:
        raise KeyError(f"Channel '{source_channel}' not found in group '{group_name}'")

    # Generate derived name
    if custom_suffix:
        derived_name = f"{source_channel}_{custom_suffix}"
    else:
        derived_name = get_derived_name(source_channel, operation, params)

    # Get source data
    source_data = signal_group.data[source_channel].to_numpy()

    # Handle missing values if requested
    if params.get("interpolate_missing", False):
        # Interpolate NaNs: linear for interior, bfill/ffill for edges
        interp_series = pd.Series(source_data).interpolate().bfill().ffill()
        source_data = interp_series.to_numpy()
        print(
            f"[create_derived_channel] Interpolated NaNs, remaining: {np.sum(np.isnan(source_data))}"
        )

    # Apply operation
    if operation == "derivative":
        time_raw = pd.to_datetime(signal_group.data["utc"], utc=True, format="mixed")
        t_sec = (time_raw - run.start_time).dt.total_seconds().to_numpy()
        order = params.get("order", 1)
        result = compute_derivative(t_sec, source_data, order=order)
    else:
        # Use processor registry for filters
        processor_cls = get_processor(operation)
        if processor_cls is None:
            raise ValueError(f"Unknown operation: {operation}")

        processor = processor_cls()
        fs = signal_group.sampling_rate or 100.0
        # Filter out non-processor params
        processor_params = {
            k: v for k, v in params.items() if k != "interpolate_missing"
        }
        result = processor.process(source_data, fs, **processor_params)

    # Store result in SignalGroup
    signal_group.data[derived_name] = result

    # Create Channel reference
    channel = Channel.from_parts(group_name, derived_name)

    # Register provenance
    parent_id = f"{group_name}:{source_channel}"
    run.channel_provenance[channel.id] = ChannelProvenance(
        parents=[parent_id],
        operation=operation,
        parameters=params,
        timestamp=datetime.now(),
    )

    return channel


def create_filter_channel(
    run: RunData,
    group_name: str,
    source_channel: str,
    filter_type: str,
    **filter_params,
) -> Channel:
    """
    Convenience function to create a filtered channel.

    Args:
        run: The RunData to modify
        group_name: Name of the SignalGroup
        source_channel: Name of the source channel
        filter_type: Filter type ("butter", "savitzky_golay", "rolling_mean")
        **filter_params: Filter-specific parameters

    Returns:
        Channel reference to the filtered channel
    """
    return create_derived_channel(
        run=run,
        group_name=group_name,
        source_channel=source_channel,
        operation=filter_type,
        params=filter_params,
    )


def create_averaged_channel(
    run: RunData,
    source_channels: list[tuple[str, str]],
    target_group: str,
    output_name: str,
    interpolate_missing: bool = True,
) -> Channel:
    """
    Create an averaged channel from multiple source channels.

    Args:
        run: The RunData to modify
        source_channels: List of (group_name, channel_name) tuples
        target_group: Group to store the result in
        output_name: Name for the new averaged channel
        interpolate_missing: Whether to interpolate NaNs before averaging

    Returns:
        Channel reference to the averaged channel

    Raises:
        KeyError: If any source channel is not found
        ValueError: If channels have different lengths
    """
    if len(source_channels) < 2:
        raise ValueError("Need at least 2 channels to average")

    # Collect data from all source channels
    data_arrays = []
    parent_ids = []

    for group_name, channel_name in source_channels:
        if group_name not in run.signals:
            raise KeyError(f"SignalGroup '{group_name}' not found")

        signal_group = run.signals[group_name]

        if channel_name not in signal_group.data.columns:
            raise KeyError(f"Channel '{channel_name}' not found in '{group_name}'")

        data = signal_group.data[channel_name].to_numpy().copy()

        if interpolate_missing:
            interp_series = pd.Series(data).interpolate().bfill().ffill()
            data = interp_series.to_numpy()

        data_arrays.append(data)
        parent_ids.append(f"{group_name}:{channel_name}")

    # Verify all arrays have same length
    lengths = [len(arr) for arr in data_arrays]
    if len(set(lengths)) > 1:
        raise ValueError(f"Channel lengths differ: {lengths}")

    # Compute average
    stacked = np.stack(data_arrays, axis=0)
    averaged = np.nanmean(stacked, axis=0)

    # Store in target group
    if target_group not in run.signals:
        raise KeyError(f"Target group '{target_group}' not found")

    run.signals[target_group].data[output_name] = averaged

    # Create Channel reference
    channel = Channel.from_parts(target_group, output_name)

    # Register provenance
    run.channel_provenance[channel.id] = ChannelProvenance(
        parents=parent_ids,
        operation="average",
        parameters={"interpolate_missing": interpolate_missing},
        timestamp=datetime.now(),
    )

    return channel


def create_derivative_channel(
    run: RunData,
    group_name: str,
    source_channel: str,
    order: int = 1,
) -> Channel:
    """
    Convenience function to create a derivative channel.

    Args:
        run: The RunData to modify
        group_name: Name of the SignalGroup
        source_channel: Name of the source channel
        order: Derivative order (1=velocity, 2=acceleration)

    Returns:
        Channel reference to the derivative channel
    """
    return create_derived_channel(
        run=run,
        group_name=group_name,
        source_channel=source_channel,
        operation="derivative",
        params={"order": order},
    )


# =============================================================================
# Batch Operations
# =============================================================================


def apply_processing_chain(
    run: RunData,
    group_name: str,
    source_channel: str,
    operations: list[tuple[str, dict]],
) -> Channel:
    """
    Apply a chain of operations to create a derived channel.

    Args:
        run: The RunData to modify
        group_name: Name of the SignalGroup
        source_channel: Starting channel name
        operations: List of (operation, params) tuples

    Returns:
        Channel reference to the final derived channel

    Example:
        # Filter then derivative
        channel = apply_processing_chain(
            run, "tablet_motion", "X",
            [("butter", {"cutoff": 10}), ("derivative", {"order": 1})]
        )
        # Creates: X → X_bf10 → X_bf10_d1
    """
    current_channel = source_channel

    for operation, params in operations:
        channel = create_derived_channel(
            run=run,
            group_name=group_name,
            source_channel=current_channel,
            operation=operation,
            params=params,
        )
        current_channel = channel.name

    return channel


def save_derived_channels(run: RunData, derived_dir) -> None:
    """
    Save all channel provenance for a run.

    Args:
        run: The RunData with provenance to save
        derived_dir: Path to the derived directory
    """
    from tracetool.data.loader import save_channel_provenance
    from pathlib import Path

    if not isinstance(derived_dir, Path):
        derived_dir = Path(derived_dir)

    # We need to reconstruct run_id from run
    run_id = (
        run.subject,
        run.session,
        run.metadata.get("task"),
        run.metadata.get("condition"),
        run.run,
    )

    save_channel_provenance(derived_dir, run_id, run.channel_provenance)
