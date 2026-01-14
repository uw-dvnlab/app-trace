"""
TraceTool Registry Module

Unified plugin registry and discovery system.
"""

from tracetool.registry.base import PluginRegistry
from tracetool.registry.discovery import discover_plugins

__all__ = [
    "PluginRegistry",
    "discover_plugins",
]
