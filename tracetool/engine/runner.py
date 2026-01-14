"""
Pipeline Runner

Core execution engine for running pipelines on multiple runs.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
import time
import fnmatch

from tracetool.data.descriptors import RunData, RunConfig
from tracetool.project.config import ProjectConfig, PipelineConfig
from tracetool.engine.steps import (
    PreprocessingStep,
    AnnotatorStep,
    ComputeStep,
    PipelineStepResult,
)


@dataclass
class RunResult:
    """Result from running a pipeline on a single run."""

    run_id: str
    subject: str
    session: str
    run: str
    success: bool
    step_results: list[PipelineStepResult] = field(default_factory=list)
    error: str | None = None
    duration_seconds: float = 0.0

    @property
    def failed_steps(self) -> list[PipelineStepResult]:
        return [s for s in self.step_results if not s.success]


@dataclass
class PipelineResult:
    """Aggregated result from running a pipeline on all runs."""

    pipeline_name: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    run_results: list[RunResult] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.successful_runs / self.total_runs

    def summary_str(self) -> str:
        return (
            f"Pipeline '{self.pipeline_name}': "
            f"{self.successful_runs}/{self.total_runs} runs succeeded "
            f"({self.success_rate:.1%}) in {self.duration_seconds:.1f}s"
        )


class PipelineRunner:
    """
    Core pipeline execution engine.

    Executes preprocessing, annotators, and compute modules on a batch of runs.

    Example:
        project = load_project(Path("./myproject"))
        pipeline = load_pipeline(Path("./myproject/pipelines/default.yaml"))

        runner = PipelineRunner(project, pipeline)
        result = runner.run(run_filter="run-00*")

        print(result.summary_str())
    """

    def __init__(
        self,
        project: ProjectConfig,
        pipeline: PipelineConfig,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ):
        """
        Initialize the pipeline runner.

        Args:
            project: Project configuration
            pipeline: Pipeline configuration
            progress_callback: Optional callback(message, current, total) for progress
        """
        self.project = project
        self.pipeline = pipeline
        self.progress_callback = progress_callback

        # Load registries
        from tracetool.annotate import list_annotators, get_annotator
        from tracetool.compute import list_compute, get_compute

        self._annotators = list_annotators()
        self._computes = list_compute()
        self._get_annotator = get_annotator
        self._get_compute = get_compute

    def run(
        self,
        runs: list[RunData],
        run_filter: str = "*",
        dry_run: bool = False,
        stop_on_error: bool = False,
    ) -> PipelineResult:
        """
        Execute pipeline on a batch of runs.

        Args:
            runs: List of RunData objects to process
            run_filter: Glob pattern to filter runs by run ID
            dry_run: If True, print what would run without executing
            stop_on_error: If True, stop pipeline on first error

        Returns:
            PipelineResult with aggregated results
        """
        start_time = time.time()

        # Filter runs
        filtered_runs = [r for r in runs if fnmatch.fnmatch(r.run, run_filter)]

        if dry_run:
            return self._dry_run(filtered_runs)

        results = []
        for i, run in enumerate(filtered_runs):
            if self.progress_callback:
                self.progress_callback(
                    f"Processing run {run.run}...",
                    i + 1,
                    len(filtered_runs),
                )

            run_result = self.run_single(run)
            results.append(run_result)

            if stop_on_error and not run_result.success:
                break

        successful = sum(1 for r in results if r.success)

        return PipelineResult(
            pipeline_name=self.pipeline.name,
            total_runs=len(filtered_runs),
            successful_runs=successful,
            failed_runs=len(results) - successful,
            run_results=results,
            duration_seconds=time.time() - start_time,
        )

    def run_single(self, run: RunData) -> RunResult:
        """
        Execute pipeline on a single run.

        Args:
            run: RunData object to process

        Returns:
            RunResult with step-by-step results
        """
        start_time = time.time()
        step_results = []
        run_id = f"{run.subject}_{run.session}_{run.run}"

        try:
            # 1. Apply preprocessing
            for step in self.pipeline.preprocessing:
                result = self._run_preprocessing(run, step)
                step_results.append(result)
                if not result.success:
                    raise RuntimeError(f"Preprocessing failed: {result.message}")

            # 2. Run annotators
            for step in self.pipeline.annotators:
                if not step.enabled:
                    continue
                result = self._run_annotator(run, step)
                step_results.append(result)
                if not result.success:
                    raise RuntimeError(f"Annotator failed: {result.message}")

            # 3. Run compute modules
            for step in self.pipeline.compute:
                if not step.enabled:
                    continue
                # Check dependencies
                deps_met = all(
                    any(r.step_name == dep and r.success for r in step_results)
                    for dep in step.depends_on
                )
                if not deps_met:
                    step_results.append(
                        PipelineStepResult(
                            step_name=step.name,
                            step_type="compute",
                            success=False,
                            message="Dependencies not met",
                        )
                    )
                    continue

                result = self._run_compute(run, step)
                step_results.append(result)
                if not result.success:
                    raise RuntimeError(f"Compute failed: {result.message}")

            return RunResult(
                run_id=run_id,
                subject=run.subject,
                session=run.session,
                run=run.run,
                success=True,
                step_results=step_results,
                duration_seconds=time.time() - start_time,
            )

        except Exception as e:
            return RunResult(
                run_id=run_id,
                subject=run.subject,
                session=run.session,
                run=run.run,
                success=False,
                step_results=step_results,
                error=str(e),
                duration_seconds=time.time() - start_time,
            )

    def _run_preprocessing(
        self, run: RunData, step: PreprocessingStep
    ) -> PipelineStepResult:
        """Apply preprocessing operations to a channel."""
        start_time = time.time()

        try:
            from tracetool.processing.channel_utils import create_derived_channel

            # Parse channel spec
            parts = step.channel.split(":")
            if len(parts) != 2:
                raise ValueError(f"Invalid channel format: {step.channel}")
            group_name, channel_name = parts

            # Apply operations in sequence
            current_channel = channel_name
            for op_config in step.operations:
                op_name = op_config.get("op", "unknown")
                params = {k: v for k, v in op_config.items() if k != "op"}

                result = create_derived_channel(
                    run=run,
                    group_name=group_name,
                    source_channel=current_channel,
                    operation=op_name,
                    params=params,
                )

                if result:
                    current_channel = result.name

            return PipelineStepResult(
                step_name=f"preprocess:{step.channel}",
                step_type="preprocessing",
                success=True,
                message=f"Applied {len(step.operations)} operations",
                duration_seconds=time.time() - start_time,
            )

        except Exception as e:
            return PipelineStepResult(
                step_name=f"preprocess:{step.channel}",
                step_type="preprocessing",
                success=False,
                message=str(e),
                duration_seconds=time.time() - start_time,
            )

    def _run_annotator(self, run: RunData, step: AnnotatorStep) -> PipelineStepResult:
        """Run an annotator on the run."""
        start_time = time.time()

        try:
            annotator_cls = self._get_annotator(step.name)
            if not annotator_cls:
                raise ValueError(f"Annotator not found: {step.name}")

            # Apply step-specific bindings if provided
            if step.channel_bindings:
                if run.run_config is None:
                    run.run_config = RunConfig()
                run.run_config.channel_bindings.update(step.channel_bindings)

            # Create and run annotator
            annotator = annotator_cls()
            events = annotator.run(run)

            # Store events
            run.annotations[step.name] = events

            return PipelineStepResult(
                step_name=step.name,
                step_type="annotator",
                success=True,
                message=f"Detected {len(events)} events",
                output=events,
                duration_seconds=time.time() - start_time,
            )

        except Exception as e:
            return PipelineStepResult(
                step_name=step.name,
                step_type="annotator",
                success=False,
                message=str(e),
                duration_seconds=time.time() - start_time,
            )

    def _run_compute(self, run: RunData, step: ComputeStep) -> PipelineStepResult:
        """Run a compute module on the run."""
        start_time = time.time()

        try:
            compute_cls = self._get_compute(step.name)
            if not compute_cls:
                raise ValueError(f"Compute module not found: {step.name}")

            # Apply step-specific bindings if provided
            if step.channel_bindings:
                if run.run_config is None:
                    run.run_config = RunConfig()
                run.run_config.channel_bindings.update(step.channel_bindings)

            # Create and run compute
            compute = compute_cls()
            result_df = compute.run(run)

            return PipelineStepResult(
                step_name=step.name,
                step_type="compute",
                success=True,
                message=f"Computed {len(result_df)} rows"
                if result_df is not None
                else "No output",
                output=result_df,
                duration_seconds=time.time() - start_time,
            )

        except Exception as e:
            return PipelineStepResult(
                step_name=step.name,
                step_type="compute",
                success=False,
                message=str(e),
                duration_seconds=time.time() - start_time,
            )

    def _dry_run(self, runs: list[RunData]) -> PipelineResult:
        """Print what would run without executing."""
        print(f"\n=== DRY RUN: Pipeline '{self.pipeline.name}' ===")
        print(f"Runs to process: {len(runs)}")
        print()

        print("Steps:")
        step_num = 1

        for step in self.pipeline.preprocessing:
            print(f"  {step_num}. [PREPROCESSING] {step.channel}")
            for op in step.operations:
                print(f"       - {op.get('op', '?')}: {op}")
            step_num += 1

        for step in self.pipeline.annotators:
            status = "" if step.enabled else " (DISABLED)"
            print(f"  {step_num}. [ANNOTATOR] {step.name}{status}")
            if step.channel_bindings:
                print(f"       bindings: {step.channel_bindings}")
            step_num += 1

        for step in self.pipeline.compute:
            status = "" if step.enabled else " (DISABLED)"
            deps = f" (depends: {step.depends_on})" if step.depends_on else ""
            print(f"  {step_num}. [COMPUTE] {step.name}{status}{deps}")
            step_num += 1

        print()
        print("Export config:")
        if self.pipeline.export:
            if self.pipeline.export.aggregate:
                print(f"  Aggregate: {self.pipeline.export.aggregate}")
            print(f"  Format: {self.pipeline.export.format}")
            print(f"  Per-run: {self.pipeline.export.per_run}")

        return PipelineResult(
            pipeline_name=self.pipeline.name,
            total_runs=len(runs),
            successful_runs=len(runs),  # Assume success for dry run
            failed_runs=0,
            run_results=[],
            duration_seconds=0,
        )
