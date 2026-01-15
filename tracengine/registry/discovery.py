"""
TRACE Plugin Discovery

Automatic plugin discovery from project folders.
"""

import importlib.util
import logging
from pathlib import Path
from typing import Type

from tracengine.registry.base import PluginRegistry

logger = logging.getLogger(__name__)


def discover_plugins(
    plugins_path: Path,
    base_class: Type,
    registry: PluginRegistry | None = None,
) -> dict[str, Type]:
    """
    Discover and load plugins from a directory.

    Scans Python files in the directory, imports them, and finds
    all classes that inherit from the specified base class.
    Also scans subdirectories that are Python packages.

    Args:
        plugins_path: Path to plugins directory
        base_class: Base class that plugins must inherit from
        registry: Optional registry to add discovered plugins to

    Returns:
        Dict of plugin_name -> plugin_class
    """
    discovered = {}

    if not plugins_path.exists():
        logger.debug(f"Plugins path does not exist: {plugins_path}")
        return discovered

    if not plugins_path.is_dir():
        logger.warning(f"Plugins path is not a directory: {plugins_path}")
        return discovered

    # Scan top-level .py files
    for py_file in plugins_path.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        try:
            plugins = _load_plugins_from_file(py_file, base_class)
            for name, cls in plugins.items():
                discovered[name] = cls
                if registry is not None:
                    registry.register(cls)
                logger.info(f"Discovered plugin: {name} from {py_file.name}")
        except Exception as e:
            logger.error(f"Error loading plugins from {py_file}: {e}")

    # Scan subdirectories (recursively scan all .py files)
    for subdir in plugins_path.iterdir():
        if not subdir.is_dir():
            continue
        if subdir.name.startswith("_"):
            continue

        try:
            plugins = _load_plugins_from_package(subdir, base_class)
            for name, cls in plugins.items():
                discovered[name] = cls
                if registry is not None:
                    registry.register(cls)
                logger.info(f"Discovered plugin: {name} from {subdir.name}/")
        except Exception as e:
            logger.error(f"Error loading plugins from {subdir}: {e}")

    return discovered


def _load_plugins_from_file(file_path: Path, base_class: Type) -> dict[str, Type]:
    """
    Load all plugin classes from a Python file.

    Args:
        file_path: Path to the Python file
        base_class: Base class that plugins must inherit from

    Returns:
        Dict of class_name -> class for all matching classes
    """
    plugins = {}

    # Create module spec and load
    spec = importlib.util.spec_from_file_location(
        file_path.stem,
        file_path,
    )
    if spec is None or spec.loader is None:
        return plugins

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        logger.error(f"Failed to execute module {file_path}: {e}")
        return plugins

    # Find all classes that inherit from base_class
    for name in dir(module):
        if name.startswith("_"):
            continue

        obj = getattr(module, name)

        # Check if it's a class and inherits from base_class
        if (
            isinstance(obj, type)
            and issubclass(obj, base_class)
            and obj is not base_class
        ):
            plugins[name] = obj

    return plugins


def _load_plugins_from_package(package_path: Path, base_class: Type) -> dict[str, Type]:
    """
    Load all plugin classes from a Python package (directory with __init__.py).

    Recursively scans the package for all .py files and loads plugin classes.

    Args:
        package_path: Path to the package directory
        base_class: Base class that plugins must inherit from

    Returns:
        Dict of class_name -> class for all matching classes
    """
    plugins = {}

    # Scan all .py files in the package recursively
    for py_file in package_path.rglob("*.py"):
        if py_file.name.startswith("_"):
            continue

        try:
            file_plugins = _load_plugins_from_file(py_file, base_class)
            plugins.update(file_plugins)
        except Exception as e:
            logger.error(f"Error loading from {py_file}: {e}")

    return plugins


def discover_annotators(project_plugins_path: Path) -> dict[str, Type]:
    """
    Discover annotator plugins from a project's plugins/annotators directory.

    Args:
        project_plugins_path: Path to project's plugins directory

    Returns:
        Dict of annotator_name -> annotator_class
    """
    from tracengine.annotate.base import AnnotatorBase

    annotators_path = project_plugins_path / "annotators"
    return discover_plugins(annotators_path, AnnotatorBase)


def discover_compute(project_plugins_path: Path) -> dict[str, Type]:
    """
    Discover compute plugins from a project's plugins/compute directory.

    Args:
        project_plugins_path: Path to project's plugins directory

    Returns:
        Dict of compute_name -> compute_class
    """
    from tracengine.compute.base import ComputeBase

    compute_path = project_plugins_path / "compute"
    return discover_plugins(compute_path, ComputeBase)
