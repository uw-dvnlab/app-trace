"""
Unified Plot Row Widget

Single widget for displaying one or more channels overlaid.
Replaces PlotRow, DerivedPlotRow, and CombinedPlotRow.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QCheckBox,
    QFrame,
)
from PyQt6.QtCore import pyqtSignal, Qt
import pyqtgraph as pg
import numpy as np


# Default color palette for multi-channel plots
DEFAULT_COLORS = [
    "#2ecc71",  # green
    "#3498db",  # blue
    "#e74c3c",  # red
    "#f39c12",  # orange
    "#9b59b6",  # purple
    "#1abc9c",  # teal
    "#e91e63",  # pink
    "#00bcd4",  # cyan
]


class ChannelLegendItem(QWidget):
    """Individual channel item in the legend with visibility toggle and remove button."""

    visibility_toggled = pyqtSignal(str, bool)  # channel_id, is_visible
    remove_requested = pyqtSignal(str)  # channel_id

    def __init__(self, channel_id: str, color: str, parent=None):
        super().__init__(parent)
        self.channel_id = channel_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(4)

        # Visibility toggle (eye icon)
        self.btn_visible = QPushButton("👁")
        self.btn_visible.setCheckable(True)
        self.btn_visible.setChecked(True)
        self.btn_visible.setFixedSize(20, 20)
        self.btn_visible.setToolTip("Toggle visibility")
        self.btn_visible.toggled.connect(self._on_visibility_toggled)

        # Color swatch
        self.color_swatch = QLabel()
        self.color_swatch.setFixedSize(12, 12)
        self.set_color(color)

        # Channel name (short form)
        short_name = channel_id.split(":")[-1] if ":" in channel_id else channel_id
        self.lbl_name = QLabel(short_name)
        self.lbl_name.setToolTip(channel_id)
        self.lbl_name.setStyleSheet("color: #EEE; font-size: 11px;")

        # Remove button
        self.btn_remove = QPushButton("✕")
        self.btn_remove.setFixedSize(16, 16)
        self.btn_remove.setToolTip("Remove from plot")
        self.btn_remove.clicked.connect(
            lambda: self.remove_requested.emit(self.channel_id)
        )

        layout.addWidget(self.btn_visible)
        layout.addWidget(self.color_swatch)
        layout.addWidget(self.lbl_name)
        layout.addWidget(self.btn_remove)
        layout.addStretch()

    def set_color(self, color: str):
        self.color_swatch.setStyleSheet(
            f"background-color: {color}; border: 1px solid #555; border-radius: 2px;"
        )

    def _on_visibility_toggled(self, checked: bool):
        self.btn_visible.setText("👁" if checked else "🚫")
        self.visibility_toggled.emit(self.channel_id, checked)


class PlotRowControlPanel(QWidget):
    """Control panel for a plot row."""

    moved_up = pyqtSignal()
    moved_down = pyqtSignal()
    selection_toggled = pyqtSignal(bool)
    close_requested = pyqtSignal()
    split_requested = pyqtSignal()
    normalize_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(50)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        # Selection checkbox (for combining rows)
        self.chk_select = QCheckBox()
        self.chk_select.setToolTip("Select for combining")
        self.chk_select.toggled.connect(self.selection_toggled.emit)

        # Move buttons
        self.btn_up = QPushButton("▲")
        self.btn_up.setFixedWidth(40)
        self.btn_up.clicked.connect(self.moved_up.emit)

        self.btn_down = QPushButton("▼")
        self.btn_down.setFixedWidth(40)
        self.btn_down.clicked.connect(self.moved_down.emit)

        # Normalize toggle
        self.btn_normalize = QPushButton("N")
        self.btn_normalize.setCheckable(True)
        self.btn_normalize.setFixedWidth(30)
        self.btn_normalize.setToolTip("Toggle normalization (shared Y vs 0-1)")
        self.btn_normalize.toggled.connect(self.normalize_toggled.emit)
        self.btn_normalize.setVisible(False)  # Only show for multi-channel

        # Split button (for multi-channel rows)
        self.btn_split = QPushButton("⇆")
        self.btn_split.setFixedWidth(30)
        self.btn_split.setToolTip("Split into individual rows")
        self.btn_split.clicked.connect(self.split_requested.emit)
        self.btn_split.setVisible(False)  # Only show for multi-channel

        layout.addWidget(self.chk_select, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.btn_up, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.btn_down, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        layout.addWidget(self.btn_normalize, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.btn_split, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_multichannel_mode(self, enabled: bool):
        """Show/hide multi-channel specific controls."""
        self.btn_normalize.setVisible(enabled)
        self.btn_split.setVisible(enabled)


class PlotRowWidget(QWidget):
    """
    Unified plot row that can display one or more channels overlaid.

    Replaces PlotRow, DerivedPlotRow, and CombinedPlotRow.
    """

    moved_up = pyqtSignal(object)
    moved_down = pyqtSignal(object)
    close_requested = pyqtSignal(object)
    split_requested = pyqtSignal(object)  # Emits self, parent handles split

    def __init__(self, channel_ids: list[str] = None, parent=None):
        super().__init__(parent)

        self.channel_ids: list[str] = channel_ids or []
        self.visible: dict[str, bool] = {ch: True for ch in self.channel_ids}
        self.colors: dict[str, str] = {}
        self.plot_items: dict[str, pg.PlotDataItem] = {}
        self.legend_items: dict[str, ChannelLegendItem] = {}
        self._normalize = False

        # Cached data: channel_id -> (t, y)
        self._data_cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}

        self._init_ui()
        self._assign_colors()
        self._rebuild_legend()  # Build legend on init for multi-channel rows

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setMinimumHeight(200)

        # Header with title and close button
        header = QFrame()
        header.setStyleSheet("background-color: #333;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 2, 4, 2)

        self.lbl_title = QLabel(self._build_title())
        self.lbl_title.setStyleSheet("font-weight: bold; color: #EEE;")

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setToolTip("Close this plot row")
        self.btn_close.clicked.connect(lambda: self.close_requested.emit(self))

        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_close)

        main_layout.addWidget(header)

        # Content area
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Control panel
        self.controls = PlotRowControlPanel()
        self.controls.moved_up.connect(lambda: self.moved_up.emit(self))
        self.controls.moved_down.connect(lambda: self.moved_down.emit(self))
        self.controls.split_requested.connect(lambda: self.split_requested.emit(self))
        self.controls.normalize_toggled.connect(self._on_normalize_toggled)
        self.chk_select = self.controls.chk_select

        # Plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        content_layout.addWidget(self.controls)
        content_layout.addWidget(self.plot_widget)

        main_layout.addWidget(content_widget)

        # Legend area (for multi-channel)
        self.legend_widget = QWidget()
        self.legend_widget.setStyleSheet("background-color: #2a2a2a;")
        self.legend_layout = QHBoxLayout(self.legend_widget)
        self.legend_layout.setContentsMargins(60, 2, 4, 2)  # Offset for control panel
        self.legend_layout.addStretch()
        self.legend_widget.setVisible(False)

        main_layout.addWidget(self.legend_widget)

        self._update_multichannel_mode()

    def _build_title(self) -> str:
        if not self.channel_ids:
            return "(empty)"
        if len(self.channel_ids) == 1:
            return self.channel_ids[0]
        return f"{len(self.channel_ids)} channels"

    def _assign_colors(self):
        """Assign colors from palette to channels."""
        for i, ch in enumerate(self.channel_ids):
            if ch not in self.colors:
                self.colors[ch] = DEFAULT_COLORS[i % len(DEFAULT_COLORS)]

    def _update_multichannel_mode(self):
        """Update UI based on single vs multi-channel state."""
        is_multi = len(self.channel_ids) > 1
        self.controls.set_multichannel_mode(is_multi)
        self.legend_widget.setVisible(is_multi)
        self.lbl_title.setText(self._build_title())

    def _rebuild_legend(self):
        """Rebuild the legend items."""
        # Clear existing
        for item in self.legend_items.values():
            item.deleteLater()
        self.legend_items.clear()

        # Rebuild
        for ch in self.channel_ids:
            item = ChannelLegendItem(ch, self.colors.get(ch, "#fff"))
            item.visibility_toggled.connect(self._on_channel_visibility_toggled)
            item.remove_requested.connect(self.remove_channel)
            self.legend_layout.insertWidget(self.legend_layout.count() - 1, item)
            self.legend_items[ch] = item

    def add_channel(self, channel_id: str) -> None:
        """Add a channel to this plot row."""
        if channel_id in self.channel_ids:
            return

        self.channel_ids.append(channel_id)
        self.visible[channel_id] = True
        self._assign_colors()
        self._update_multichannel_mode()
        self._rebuild_legend()
        self.refresh_plot()

    def remove_channel(self, channel_id: str) -> None:
        """Remove a channel from this plot row."""
        if channel_id not in self.channel_ids:
            return

        self.channel_ids.remove(channel_id)
        self.visible.pop(channel_id, None)
        self.colors.pop(channel_id, None)
        self._data_cache.pop(channel_id, None)

        # Remove plot item
        if channel_id in self.plot_items:
            self.plot_widget.removeItem(self.plot_items.pop(channel_id))

        self._update_multichannel_mode()
        self._rebuild_legend()

        if not self.channel_ids:
            self.close_requested.emit(self)
        else:
            self.refresh_plot()

    def update_from_run(self, run) -> None:
        """Load data from RunData for all channels."""
        self._data_cache.clear()

        for channel_id in self.channel_ids:
            # Parse channel_id: "group:channel_name"
            if ":" in channel_id:
                group, name = channel_id.split(":", 1)
            else:
                # Legacy fallback
                group, name = channel_id, channel_id

            t, y = run.get_signal(group, name)
            if t is not None and len(t) > 0:
                self._data_cache[channel_id] = (t, y)

        self.refresh_plot()

    def refresh_plot(self) -> None:
        """Refresh the plot with current data and visibility settings."""
        # Ensure plot items exist for each channel
        for ch in self.channel_ids:
            if ch not in self.plot_items:
                color = self.colors.get(ch, "#fff")
                item = self.plot_widget.plot([], [], pen=pg.mkPen(color, width=1.5))
                self.plot_items[ch] = item

        # Update data
        for ch in self.channel_ids:
            item = self.plot_items.get(ch)
            if not item:
                continue

            if not self.visible.get(ch, True):
                item.setData([], [])
                continue

            data = self._data_cache.get(ch)
            if data is None:
                item.setData([], [])
                continue

            t, y = data

            if self._normalize and len(self.channel_ids) > 1:
                # # Normalize to [0, 1]
                # y_min, y_max = np.nanmin(y), np.nanmax(y)
                # if y_max - y_min > 0:
                #     y = (y - y_min) / (y_max - y_min)

                # Standardize to zero-mean unit-variance
                if np.nanstd(y) > 0:
                    y = (y - np.nanmean(y)) / np.nanstd(y)

            item.setData(t, y)

    def _on_channel_visibility_toggled(self, channel_id: str, is_visible: bool):
        self.visible[channel_id] = is_visible
        self.refresh_plot()

    def _on_normalize_toggled(self, checked: bool):
        self._normalize = checked
        self.refresh_plot()

    def get_channel_ids(self) -> list[str]:
        """Return list of channel IDs in this row."""
        return list(self.channel_ids)

    def is_selected(self) -> bool:
        """Return whether this row is selected."""
        return self.chk_select.isChecked()

    def split_to_rows(self) -> list["PlotRowWidget"]:
        """Create individual PlotRowWidgets for each channel."""
        rows = []
        for ch in self.channel_ids:
            row = PlotRowWidget([ch])
            row.colors[ch] = self.colors.get(ch, DEFAULT_COLORS[0])
            if ch in self._data_cache:
                row._data_cache[ch] = self._data_cache[ch]
            rows.append(row)
        return rows


# Legacy aliases for backward compatibility during migration
PlotRow = PlotRowWidget
