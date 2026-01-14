"""
TraceTool Command Line Interface

Click-based CLI for project management, GUI launch, and headless pipeline execution.
"""

import click
from pathlib import Path
import sys


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version="1.0.0", prog_name="TraceTool")
def cli(ctx):
    """
    TraceTool: Time-series representation, annotation, and computation engine.

    Use 'trace gui' to launch the interactive GUI, or 'trace pipeline' for
    headless batch processing.
    """
    # If no command provided, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.argument("session_path", type=click.Path(exists=True), required=False)
def gui(session_path):
    """
    Launch the TraceTool GUI.

    Optionally provide a SESSION_PATH to auto-load on startup.

    Examples:

        trace gui

        trace gui ./test-data/ses-01
    """
    from tracetool.gui.main_window import run_trace_tool

    if session_path:
        click.echo(f"Launching GUI with session: {session_path}")
    else:
        click.echo("Launching GUI...")

    run_trace_tool(session_path=session_path)


@cli.command()
@click.argument("pipeline_path", type=click.Path(exists=True))
@click.argument("session_path", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Show what would run without executing")
@click.option(
    "--run-filter", "-f", default="*", help="Glob pattern to filter runs (default: *)"
)
@click.option(
    "--output", "-o", type=click.Path(), help="Output directory (default: derived/)"
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def pipeline(pipeline_path, session_path, dry_run, run_filter, output, verbose):
    """
    Run a pipeline headlessly on a session.

    PIPELINE_PATH: Path to pipeline YAML configuration file

    SESSION_PATH: Path to session directory containing data

    Examples:

        trace pipeline ./pipelines/default.yaml ./data/ses-01

        trace pipeline ./pipelines/default.yaml ./data/ses-01 --dry-run

        trace pipeline ./pipelines/default.yaml ./data/ses-01 -f "run-00*"
    """
    from tracetool.project.structure import load_pipeline
    from tracetool.data.loader import load_session
    from tracetool.engine.runner import PipelineRunner
    from tracetool.engine.export import export_results
    from tracetool.project.config import ProjectConfig, ProjectPaths

    pipeline_path = Path(pipeline_path)
    session_path = Path(session_path)
    output_dir = Path(output) if output else session_path / "derived"

    click.echo(f"Loading pipeline: {pipeline_path}")
    pipeline_config = load_pipeline(pipeline_path)

    click.echo(f"Loading session: {session_path}")
    runs = load_session(session_path)
    click.echo(f"Found {len(runs)} runs")

    # Create minimal project config
    paths = ProjectPaths.from_root(session_path)
    project = ProjectConfig(
        name=session_path.name,
        root=session_path,
        paths=paths,
        default_channel_bindings={},
        default_pipeline=pipeline_path.name,
    )

    def progress_callback(message, current, total):
        if verbose:
            click.echo(f"  [{current}/{total}] {message}")

    runner = PipelineRunner(
        project, pipeline_config, progress_callback=progress_callback
    )

    click.echo()
    if dry_run:
        click.echo("=== DRY RUN MODE ===")
        result = runner.run(runs, run_filter=run_filter, dry_run=True)
    else:
        click.echo(f"Running pipeline '{pipeline_config.name}'...")
        result = runner.run(runs, run_filter=run_filter)

        # Export results
        click.echo()
        click.echo("Exporting results...")
        exported = export_results(result, output_dir, pipeline_config.export)
        for name, path in exported.items():
            click.echo(f"  {name}: {path}")

    click.echo()
    click.echo(result.summary_str())

    if result.failed_runs > 0:
        click.echo()
        click.echo("Failed runs:")
        for run_result in result.run_results:
            if not run_result.success:
                click.echo(f"  {run_result.run_id}: {run_result.error}")
        sys.exit(1)


@cli.command()
@click.argument("project_path", type=click.Path())
@click.option("--name", "-n", prompt="Project name", help="Name of the project")
def init(project_path, name):
    """
    Initialize a new TraceTool project structure.

    Creates the standard directory layout and configuration files.

    Example:

        trace init ./my-project --name "My Research Project"
    """
    from tracetool.project.structure import init_project

    project_path = Path(project_path)

    if project_path.exists() and any(project_path.iterdir()):
        if not click.confirm(
            f"Directory '{project_path}' is not empty. Continue anyway?"
        ):
            click.echo("Aborted.")
            return

    click.echo(f"Initializing project '{name}' at {project_path}")
    config = init_project(project_path, name)

    click.echo()
    click.echo("Created project structure:")
    click.echo(f"  {project_path}/")
    click.echo("    ├── data/           # Session data (or set data_source in config)")
    click.echo("    ├── derived/        # Annotations, metrics")
    click.echo("    ├── plugins/        # Custom plugins")
    click.echo("    │   ├── annotators/")
    click.echo("    │   └── compute/")
    click.echo("    ├── pipelines/      # Pipeline configs")
    click.echo("    ├── exports/        # Aggregated results")
    click.echo("    ├── notebooks/      # Development templates")
    click.echo("    └── tracetool.yaml  # Project manifest")
    click.echo()
    click.echo("Project initialized successfully!")


@cli.command()
@click.argument("project_path", type=click.Path(exists=True))
@click.option("--fix", is_flag=True, help="Attempt to fix minor issues")
def validate(project_path, fix):
    """
    Validate a TraceTool project structure.

    Checks for required directories, config files, and data integrity.

    Example:

        trace validate ./my-project
    """
    from tracetool.project.structure import validate_project, load_project
    from tracetool.data.loader import load_session

    project_path = Path(project_path)
    errors = []
    warnings = []

    click.echo(f"Validating project: {project_path}")
    click.echo()

    # Check project structure
    click.echo("Checking project structure...")
    try:
        result = validate_project(project_path)
        if not result:
            click.echo("  ✓ Project structure is valid")
        else:
            for error in result.get("errors", []):
                errors.append(f"Structure: {error}")
                click.echo(f"  X {error}")
    except Exception as e:
        errors.append(f"Validation error: {e}")
        click.echo(f"  X Error: {e}")

    # Check tracetool.yaml
    click.echo("Checking project configuration...")
    manifest_path = project_path / "tracetool.yaml"
    if manifest_path.exists():
        try:
            config = load_project(project_path)
            click.echo(f"  ✓ Loaded project: {config.name}")
        except Exception as e:
            errors.append(f"Config error: {e}")
            click.echo(f"  X Failed to load config: {e}")
    else:
        warnings.append("No tracetool.yaml found")
        click.echo("  ⚠ No tracetool.yaml found (optional)")

    # Check for data files
    click.echo("Checking data files...")
    processed_dir = project_path / "processed"
    if processed_dir.exists():
        try:
            runs = load_session(processed_dir)
            click.echo(f"  ✓ Found {len(runs)} runs in processed/")
        except Exception as e:
            warnings.append(f"Could not load data: {e}")
            click.echo(f"  ⚠ Could not load data: {e}")
    else:
        # Try loading from project root as session
        try:
            runs = load_session(project_path)
            if runs:
                click.echo(f"  ✓ Found {len(runs)} runs in project root")
        except Exception:
            warnings.append("No data files found")
            click.echo("  ⚠ No data files found")

    # Summary
    click.echo()
    if errors:
        click.echo(f"Validation failed with {len(errors)} error(s).")
        sys.exit(1)
    elif warnings:
        click.echo(f"Validation passed with {len(warnings)} warning(s).")
    else:
        click.echo("Validation passed! ✓")


@cli.command("list-plugins")
def list_plugins():
    """
    List all registered plugins (annotators and compute modules).
    """
    from tracetool.annotate import list_annotators
    from tracetool.compute import list_compute

    click.echo("=== Annotators ===")
    annotators = list_annotators()
    if annotators:
        for name, cls in sorted(annotators.items()):
            display = getattr(cls, "name", name)
            version = getattr(cls, "version", "")
            click.echo(
                f"  {name}: {display} (v{version})"
                if version
                else f"  {name}: {display}"
            )
    else:
        click.echo("  (none)")

    click.echo()
    click.echo("=== Compute Modules ===")
    computes = list_compute()
    if computes:
        for name, cls in sorted(computes.items()):
            display = getattr(cls, "name", name)
            version = getattr(cls, "version", "")
            click.echo(
                f"  {name}: {display} (v{version})"
                if version
                else f"  {name}: {display}"
            )
    else:
        click.echo("  (none)")


@cli.command("link-data")
@click.argument("project_path", type=click.Path())
@click.argument("data_path", type=click.Path())
def link_data(project_path, data_path):
    """
    Link data files to the project.

    Example:

        trace link-data ./my-project ./data
    """
    from tracetool.project.structure import (
        load_project,
        set_config_data_source,
        save_project,
    )

    click.echo("Linking data files...")
    project_path = Path(project_path)
    data_path = Path(data_path)
    try:
        config = load_project(project_path)
        config = set_config_data_source(config, data_path)
        save_project(project_path, config)
        click.echo("Data linked successfully!")
    except Exception as e:
        click.echo(f"Failed to link data: {e}")
        sys.exit(1)


@cli.command("provenance")
@click.argument("provenance_path", type=click.Path(exists=True))
def provenance(provenance_path):
    """
    Visualize data provenance graph.

    PROVENANCE_PATH: Path to a provenance JSON file.
    """
    from tracetool.engine.provenance import show_provenance_graph

    path = Path(provenance_path)
    click.echo(f"Visualizing provenance from: {path}")
    show_provenance_graph(path)


@cli.command("reset-notebooks")
@click.argument("project_path", type=click.Path(exists=True))
@click.option(
    "--force", is_flag=True, help="Overwrite existing notebooks without prompting"
)
def reset_notebooks(project_path, force):
    """
    Restore template notebooks to a project.

    Copies fresh development notebooks to the project's notebooks/ folder.
    Use this if you've accidentally modified the originals and want to start fresh.

    Example:

        trace reset-notebooks ./my-project

        trace reset-notebooks ./my-project --force
    """
    import shutil

    project_path = Path(project_path)
    notebooks_dir = project_path / "notebooks"
    notebooks_dir.mkdir(exist_ok=True)

    # Locate bundled templates
    templates_dir = Path(__file__).parent / "templates"
    if not templates_dir.exists():
        click.echo("Error: Template notebooks not found in installation.")
        sys.exit(1)

    templates = list(templates_dir.glob("*.ipynb")) + list(
        templates_dir.glob("develop_*.py")
    )
    if not templates:
        click.echo("Error: No template notebooks found.")
        sys.exit(1)

    click.echo(f"Restoring {len(templates)} template notebook(s) to {notebooks_dir}/")

    for template in templates:
        dest = notebooks_dir / template.name
        if dest.exists() and not force:
            if not click.confirm(f"  '{template.name}' exists. Overwrite?"):
                click.echo(f"  Skipped: {template.name}")
                continue
        shutil.copy(template, dest)
        click.echo(f"  ✓ {template.name}")

    click.echo()
    click.echo("Done! Template notebooks restored.")


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
