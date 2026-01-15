"""
TRACE Annotator Registry

Registry for annotator plugins.
"""

from tracengine.registry.base import PluginRegistry
from tracengine.annotate.base import AnnotatorBase


# Global annotator registry instance
_annotator_registry = PluginRegistry(base_class=AnnotatorBase)


def register_annotator(cls):
    """
    Decorator to register an annotator plugin.

    Usage:
        @register_annotator
        class MyAnnotator(AnnotatorBase):
            ...
    """
    return _annotator_registry.register(cls)


def get_annotator(name: str):
    """Get an annotator class by name."""
    return _annotator_registry.get(name)


def list_annotators():
    """Return all registered annotator plugins."""
    return _annotator_registry.list_all()


def list_annotator_names():
    """Return names of all registered annotator plugins."""
    return _annotator_registry.list_names()


# Expose registry for direct access
annotator_registry = _annotator_registry


def get_registry():
    """Get the global annotator registry instance."""
    return _annotator_registry
