"""
TraceTool GUI Dialogs Module

Advanced dialogs for plugin configuration and execution.
"""

from tracetool.gui.dialogs.channel_binding import ChannelBindingDialog
from tracetool.gui.dialogs.plugin_runner import PluginRunnerDialog
from tracetool.gui.dialogs.processing import (
    DerivativeDialog,
    FilterDialog,
    AverageChannelsDialog,
)

__all__ = [
    "ChannelBindingDialog",
    "PluginRunnerDialog",
    "DerivativeDialog",
    "FilterDialog",
    "AverageChannelsDialog",
]
