"""
TRACE Plugin Registry Base

Generic plugin registry with type-safe registration and lookup.
"""

from typing import TypeVar, Generic, Type
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PluginRegistry(Generic[T]):
    """
    Generic plugin registry for type-safe plugin management.

    Usage:
        class MyPluginRegistry(PluginRegistry[MyPluginBase]):
            pass

        registry = MyPluginRegistry()
        registry.register(MyPlugin)
        plugin_cls = registry.get("MyPlugin")
    """

    def __init__(self, base_class: Type[T] | None = None):
        """
        Initialize the registry.

        Args:
            base_class: Optional base class for type validation
        """
        self._plugins: dict[str, Type[T]] = {}
        self._base_class = base_class

    def register(self, plugin_cls: Type[T]) -> Type[T]:
        """
        Register a plugin class.

        Can be used as a decorator:
            @registry.register
            class MyPlugin(PluginBase):
                ...

        Args:
            plugin_cls: The plugin class to register

        Returns:
            The plugin class (for decorator support)

        Raises:
            ValueError: If plugin doesn't inherit from base class
        """
        if self._base_class and not issubclass(plugin_cls, self._base_class):
            raise ValueError(
                f"{plugin_cls.__name__} must inherit from {self._base_class.__name__}"
            )

        # Use class name as key
        key = plugin_cls.__name__
        self._plugins[key] = plugin_cls
        logger.debug(f"Registered plugin: {key}")

        return plugin_cls

    def get(self, name: str) -> Type[T] | None:
        """
        Get a plugin class by name.

        Args:
            name: The plugin class name

        Returns:
            The plugin class, or None if not found
        """
        return self._plugins.get(name)

    def list_all(self) -> dict[str, Type[T]]:
        """Return all registered plugins."""
        return self._plugins.copy()

    def list_names(self) -> list[str]:
        """Return names of all registered plugins."""
        return list(self._plugins.keys())

    def __contains__(self, name: str) -> bool:
        """Check if a plugin is registered."""
        return name in self._plugins

    def __len__(self) -> int:
        """Return number of registered plugins."""
        return len(self._plugins)

    def clear(self) -> None:
        """Clear all registered plugins."""
        self._plugins.clear()
