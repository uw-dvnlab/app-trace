"""
TRACE Registry Module

Unified plugin registry and discovery system.
"""

from tracengine.registry.base import PluginRegistry
from tracengine.registry.discovery import discover_plugins

__all__ = [
    "PluginRegistry",
    "discover_plugins",
]
