"""
Channel Browser Sidebar

Collapsible sidebar for browsing and selecting channels to plot.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QCheckBox,
    QScrollArea,
    QFrame,
    QComboBox,
)
from PyQt6.QtCore import pyqtSignal


class ChannelItem(QWidget):
    """Single channel item with checkbox for selection."""

    def __init__(self, channel_id: str, parent=None):
        super().__init__(parent)
        self.channel_id = channel_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        self.checkbox = QCheckBox()
        self.checkbox.setToolTip("Select channel")

        # Parse channel_id for display
        if ":" in channel_id:
            group, name = channel_id.split(":", 1)
            display_text = name
            tooltip = f"{group}:{name}"
        else:
            display_text = channel_id
            tooltip = channel_id

        self.label = QLabel(display_text)
        self.label.setToolTip(tooltip)

        layout.addWidget(self.checkbox)
        layout.addWidget(self.label)
        layout.addStretch()

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool):
        self.checkbox.setChecked(checked)


class ChannelGroupWidget(QWidget):
    """Collapsible group of channels from one signal group (modality)."""

    def __init__(self, group_name: str, parent=None):
        super().__init__(parent)
        self.group_name = group_name
        self.channel_items: dict[str, ChannelItem] = {}
        self._collapsed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 2, 4, 2)

        self.btn_collapse = QPushButton("▼")
        self.btn_collapse.setFixedSize(20, 20)
        self.btn_collapse.clicked.connect(self._toggle_collapse)

        self.lbl_name = QLabel(group_name)

        header_layout.addWidget(self.btn_collapse)
        header_layout.addWidget(self.lbl_name)
        header_layout.addStretch()

        layout.addWidget(header)

        # Content area
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(16, 0, 0, 0)
        self.content_layout.setSpacing(0)

        layout.addWidget(self.content)

    def add_channel(self, channel_name: str):
        """Add a channel to this group."""
        channel_id = f"{self.group_name}:{channel_name}"
        if channel_id in self.channel_items:
            return

        item = ChannelItem(channel_id)
        self.channel_items[channel_id] = item
        self.content_layout.addWidget(item)

    def get_selected_channels(self) -> list[str]:
        """Return list of selected channel IDs."""
        return [cid for cid, item in self.channel_items.items() if item.is_checked()]

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self.content.setVisible(not self._collapsed)
        self.btn_collapse.setText("▶" if self._collapsed else "▼")


class ChannelBrowser(QWidget):
    """
    Sidebar for browsing and selecting channels to add to plots.

    Signals:
        add_to_row_requested(channel_ids, row_index): User wants to add selected channels
        new_row_requested(channel_ids): User wants to create a new row with selected channels
    """

    add_to_row_requested = pyqtSignal(list, int)  # [channel_ids], row_index
    new_row_requested = pyqtSignal(list)  # [channel_ids]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)

        self.groups: dict[str, ChannelGroupWidget] = {}
        self._row_names: list[str] = []  # For the dropdown

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)

        lbl_title = QLabel("Channels")

        self.btn_collapse = QPushButton("◀")
        self.btn_collapse.setFixedSize(20, 20)
        self.btn_collapse.setToolTip("Collapse sidebar")
        # Collapse is handled by parent

        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_collapse)

        layout.addWidget(header)

        # Scroll area for channel groups
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(0)
        self.scroll_layout.addStretch()

        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

        # Action bar
        action_bar = QFrame()
        action_layout = QVBoxLayout(action_bar)
        action_layout.setContentsMargins(4, 4, 4, 4)
        action_layout.setSpacing(4)

        # Row selector
        row_select_layout = QHBoxLayout()
        row_select_layout.addWidget(QLabel("Row:"))
        self.cmb_row = QComboBox()
        self.cmb_row.addItem("(New Row)")
        self.cmb_row.setMinimumWidth(100)
        row_select_layout.addWidget(self.cmb_row)
        action_layout.addLayout(row_select_layout)

        # Add button
        self.btn_add = QPushButton("Add to Plot")
        self.btn_add.clicked.connect(self._on_add_clicked)
        action_layout.addWidget(self.btn_add)

        layout.addWidget(action_bar)

    def load_from_run(self, run) -> None:
        """Populate channel browser from RunData."""
        # Clear existing
        for grp in self.groups.values():
            grp.deleteLater()
        self.groups.clear()

        # Build from run.signals
        for group_name, signal_group in sorted(run.signals.items()):
            group_widget = ChannelGroupWidget(group_name)

            for col in sorted(signal_group.data.columns):
                if col.lower() in ("utc", "time", "timestamp"):
                    continue
                group_widget.add_channel(col)

            self.groups[group_name] = group_widget
            self.scroll_layout.insertWidget(
                self.scroll_layout.count() - 1, group_widget
            )

    def update_row_list(self, row_names: list[str]) -> None:
        """Update the row selector dropdown."""
        self._row_names = row_names
        self.cmb_row.clear()
        self.cmb_row.addItem("(New Row)")
        for i, name in enumerate(row_names):
            self.cmb_row.addItem(f"Row {i + 1}: {name}")

    def get_selected_channels(self) -> list[str]:
        """Return all currently selected channel IDs."""
        selected = []
        for grp in self.groups.values():
            selected.extend(grp.get_selected_channels())
        return selected

    def _on_add_clicked(self):
        selected = self.get_selected_channels()
        if not selected:
            return

        idx = self.cmb_row.currentIndex()
        if idx == 0:  # "(New Row)"
            self.new_row_requested.emit(selected)
        else:
            self.add_to_row_requested.emit(selected, idx - 1)

        # Clear selection after adding
        for grp in self.groups.values():
            for item in grp.channel_items.values():
                item.set_checked(False)
