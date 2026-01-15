"""
TRACE Compute Registry

Registry for compute/metric plugins.
"""

from tracengine.registry.base import PluginRegistry
from tracengine.compute.base import ComputeBase


# Global compute registry instance
_compute_registry = PluginRegistry(base_class=ComputeBase)


def register_compute(cls):
    """
    Decorator to register a compute plugin.

    Usage:
        @register_compute
        class MyCompute(ComputeBase):
            ...
    """
    return _compute_registry.register(cls)


def get_compute(name: str):
    """Get a compute class by name."""
    return _compute_registry.get(name)


def list_compute():
    """Return all registered compute plugins."""
    return _compute_registry.list_all()


def list_compute_names():
    """Return names of all registered compute plugins."""
    return _compute_registry.list_names()


# Expose registry for direct access
compute_registry = _compute_registry


def get_registry():
    """Get the global compute registry instance."""
    return _compute_registry
