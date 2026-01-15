"""
Pipeline Export Module

Handles exporting and aggregating pipeline results.
"""

from pathlib import Path
import pandas as pd
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tracengine.engine.runner import PipelineResult
    from tracengine.engine.steps import ExportConfig


def export_results(
    result: "PipelineResult",
    output_dir: Path,
    config: "ExportConfig | None" = None,
) -> dict[str, Path]:
    """
    Export pipeline results to files.

    Args:
        result: PipelineResult from pipeline run
        output_dir: Base directory for output files
        config: Export configuration (uses defaults if None)

    Returns:
        Dict of exported file paths by type
    """
    from tracengine.engine.steps import ExportConfig

    if config is None:
        config = ExportConfig()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    exported = {}

    # Collect compute results for aggregation
    all_metrics = []

    for run_result in result.run_results:
        if not run_result.success:
            continue

        run_metrics = []
        for step_result in run_result.step_results:
            if step_result.step_type == "compute" and step_result.output is not None:
                df = step_result.output
                if isinstance(df, pd.DataFrame) and not df.empty:
                    # Add run metadata
                    df = df.copy()
                    df["__run__"] = run_result.run
                    df["__subject__"] = run_result.subject
                    df["__session__"] = run_result.session
                    df["__step__"] = step_result.step_name
                    run_metrics.append(df)

        # Save per-run if configured
        if config.per_run and run_metrics:
            run_df = pd.concat(run_metrics, ignore_index=True)
            run_path = output_dir / f"{run_result.run_id}_metrics.{config.format}"
            _save_dataframe(run_df, run_path, config.format)
            exported[f"run_{run_result.run_id}"] = run_path

        all_metrics.extend(run_metrics)

    # Aggregate if configured
    if config.aggregate and all_metrics:
        aggregate_df = pd.concat(all_metrics, ignore_index=True)

        # Compute summary stats if configured
        if config.summary_stats:
            summary = _compute_summary_stats(aggregate_df)
            summary_path = output_dir / f"summary_stats.{config.format}"
            _save_dataframe(summary, summary_path, config.format)
            exported["summary"] = summary_path

        # Save aggregate
        aggregate_path = output_dir / Path(config.aggregate).name
        _save_dataframe(aggregate_df, aggregate_path, config.format)
        exported["aggregate"] = aggregate_path

    # Save pipeline report
    report_path = output_dir / "pipeline_report.json"
    _save_report(result, report_path)
    exported["report"] = report_path

    return exported


def _save_dataframe(df: pd.DataFrame, path: Path, format: str) -> None:
    """Save a DataFrame to the specified format."""
    if format == "csv":
        df.to_csv(path, index=False)
    elif format == "parquet":
        df.to_parquet(path, index=False)
    elif format == "json":
        df.to_json(path, orient="records", indent=2)
    else:
        raise ValueError(f"Unknown format: {format}")


def _compute_summary_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute summary statistics for numeric columns."""
    # Get numeric columns (excluding metadata)
    numeric_cols = [
        c for c in df.select_dtypes(include="number").columns if not c.startswith("__")
    ]

    if not numeric_cols:
        return pd.DataFrame()

    stats = []
    for col in numeric_cols:
        stats.append(
            {
                "column": col,
                "mean": df[col].mean(),
                "std": df[col].std(),
                "min": df[col].min(),
                "max": df[col].max(),
                "median": df[col].median(),
                "count": df[col].count(),
            }
        )

    return pd.DataFrame(stats)


def _save_report(result: "PipelineResult", path: Path) -> None:
    """Save pipeline execution report as JSON."""
    import json

    report = {
        "pipeline_name": result.pipeline_name,
        "total_runs": result.total_runs,
        "successful_runs": result.successful_runs,
        "failed_runs": result.failed_runs,
        "success_rate": result.success_rate,
        "duration_seconds": result.duration_seconds,
        "runs": [],
    }

    for run_result in result.run_results:
        run_data = {
            "run_id": run_result.run_id,
            "subject": run_result.subject,
            "session": run_result.session,
            "run": run_result.run,
            "success": run_result.success,
            "error": run_result.error,
            "duration_seconds": run_result.duration_seconds,
            "steps": [],
        }

        for step in run_result.step_results:
            step_data = {
                "name": step.step_name,
                "type": step.step_type,
                "success": step.success,
                "message": step.message,
                "duration_seconds": step.duration_seconds,
            }
            run_data["steps"].append(step_data)

        report["runs"].append(run_data)

    with open(path, "w") as f:
        json.dump(report, f, indent=2)


def merge_exports(
    export_paths: list[Path],
    output_path: Path,
    format: str = "csv",
) -> Path:
    """
    Merge multiple export files into a single aggregate file.

    Useful for combining exports from multiple pipeline runs.
    """
    all_dfs = []

    for path in export_paths:
        if path.suffix == ".csv":
            df = pd.read_csv(path)
        elif path.suffix == ".parquet":
            df = pd.read_parquet(path)
        elif path.suffix == ".json":
            df = pd.read_json(path)
        else:
            continue
        all_dfs.append(df)

    if not all_dfs:
        return output_path

    merged = pd.concat(all_dfs, ignore_index=True)
    _save_dataframe(merged, output_path, format)

    return output_path
