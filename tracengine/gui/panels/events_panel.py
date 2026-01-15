from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QMessageBox,
    QMenu,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QAction
from tracengine.data.descriptors import RunData, Event


class EventsPanel(QWidget):
    annotations_run = pyqtSignal(str, object)  # annotator_name, results(list[Event])
    event_visibility_toggled = pyqtSignal(
        str, object, bool
    )  # group_name, events, visible
    annotations_changed = pyqtSignal(object)  # RunData
    event_selected = pyqtSignal(object)  # event object
    group_deleted = pyqtSignal(str)  # group_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.run_data: RunData = None

        layout = QVBoxLayout(self)

        # --- Annotator Section ---
        # (Removed in favor of Analysis menu)

        # --- Splitter for Groups vs Events ---
        splitter = QSplitter(Qt.Orientation.Vertical)

        # --- Groups Section ---
        groups_widget = QWidget()
        groups_layout = QVBoxLayout(groups_widget)
        groups_layout.setContentsMargins(0, 0, 0, 0)
        groups_layout.addWidget(QLabel("<b>Annotation Groups</b>"))

        self.list_groups = QListWidget()
        self.list_groups.itemClicked.connect(self.on_group_selected)
        # We need a custom widget for the list item to include a checkbox
        # Actually easier to use itemChanged if we set check state
        self.list_groups.itemChanged.connect(self.on_group_visibility_changed)

        # Enable context menu
        self.list_groups.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_groups.customContextMenuRequested.connect(
            self._show_group_context_menu
        )

        groups_layout.addWidget(self.list_groups)
        splitter.addWidget(groups_widget)

        # --- Events Table Section ---
        events_widget = QWidget()
        events_layout = QVBoxLayout(events_widget)
        events_layout.setContentsMargins(0, 0, 0, 0)
        events_layout.addWidget(QLabel("<b>Events</b>"))

        self.table_events = QTableWidget()
        self.table_events.setColumnCount(4)
        self.table_events.setHorizontalHeaderLabels(["ID", "Start", "End", "Conf"])
        self.table_events.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table_events.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table_events.itemClicked.connect(self.on_event_row_clicked)
        # Using itemChanged for confidence editing if we make it editable

        events_layout.addWidget(self.table_events)
        splitter.addWidget(events_widget)

        layout.addWidget(splitter)

        # State
        self.current_events: list[Event] = []

    def refresh_annotators(self):
        # Deprecated
        pass

    def run_annotator(self):
        # Deprecated; use Analysis menu
        pass

    def finalize_manual_annotation(self, annotator_name, events):
        if not self.run_data:
            return

        group_name = f"{annotator_name}"
        if group_name in self.run_data.annotations:
            self.run_data.annotations[group_name].extend(events)
        else:
            self.run_data.annotations[group_name] = events

        self.refresh_groups()

        # Auto-select
        items = self.list_groups.findItems(group_name, Qt.MatchFlag.MatchExactly)
        if items:
            items[0].setCheckState(Qt.CheckState.Checked)
            self.list_groups.setCurrentItem(items[0])
            self.on_group_selected(items[0])

        QMessageBox.information(self, "Success", f"Added {len(events)} manual events.")

        self.annotations_changed.emit(self.run_data)

    def set_run(self, run: RunData):
        self.run_data = run
        self.refresh_groups()
        self.table_events.setRowCount(0)

    def refresh_groups(self):
        self.list_groups.clear()
        if not self.run_data:
            return

        for name in self.run_data.annotations.keys():
            # Recreate item
            from PyQt6.QtWidgets import QListWidgetItem

            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list_groups.addItem(item)

    def _show_group_context_menu(self, pos):
        """Show context menu for annotation groups."""
        item = self.list_groups.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        delete_action = QAction("Delete Group", self)
        delete_action.triggered.connect(lambda: self.delete_group(item.text()))
        menu.addAction(delete_action)

        menu.exec(self.list_groups.mapToGlobal(pos))

    def delete_group(self, group_name: str):
        """Delete an annotation group."""
        if not self.run_data:
            return

        if group_name not in self.run_data.annotations:
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Annotation Group",
            f"Are you sure you want to delete '{group_name}' and all its events?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Remove from run data
        del self.run_data.annotations[group_name]

        # Hide events on plot
        self.event_visibility_toggled.emit(group_name, [], False)

        # Refresh UI
        self.refresh_groups()
        self.table_events.setRowCount(0)

        # Emit signals
        self.group_deleted.emit(group_name)
        self.annotations_changed.emit(self.run_data)

    def remove_event(self, event):
        if not self.run_data:
            return

        # Search in all groups
        found = False
        for group_name, events in self.run_data.annotations.items():
            if event in events:
                events.remove(event)
                found = True
                # If this group is currently showing, refresh table
                current_item = self.list_groups.currentItem()
                if current_item and current_item.text() == group_name:
                    self.populate_event_table(events)
                self.annotations_changed.emit(self.run_data)

                # Auto-delete empty groups
                if len(events) == 0:
                    self._prompt_delete_empty_group(group_name)

                break  # Event should only be in one group

        if not found:
            print(f"Warning: Event {event} not found in run data")

    def _prompt_delete_empty_group(self, group_name: str):
        """Prompt to delete an empty annotation group."""
        reply = QMessageBox.question(
            self,
            "Empty Annotation Group",
            f"'{group_name}' has no more events. Delete the group?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,  # Default to Yes for empty groups
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Remove without re-prompting
            del self.run_data.annotations[group_name]
            self.event_visibility_toggled.emit(group_name, [], False)
            self.refresh_groups()
            self.table_events.setRowCount(0)
            self.group_deleted.emit(group_name)
            self.annotations_changed.emit(self.run_data)

    def on_group_visibility_changed(self, item):
        group_name = item.text()
        visible = item.checkState() == Qt.CheckState.Checked
        events = self.run_data.annotations.get(group_name, [])
        self.event_visibility_toggled.emit(group_name, events, visible)

    def on_group_selected(self, item):
        group_name = item.text()
        if not self.run_data or group_name not in self.run_data.annotations:
            return

        self.current_events = self.run_data.annotations[group_name]
        self.populate_event_table(self.current_events)

    def populate_event_table(self, events: list[Event]):
        self.table_events.setRowCount(len(events))
        # Block signals to prevent itemChanged checks while populating
        self.table_events.blockSignals(True)

        for i, ev in enumerate(events):
            # ID
            self.table_events.setItem(i, 0, QTableWidgetItem(str(i)))

            start_val = ev.onset
            end_val = ev.offset

            t_start = (
                f"{start_val:.3f}"
                if isinstance(start_val, (float, int))
                else str(start_val)
            )
            t_end = (
                f"{end_val:.3f}" if isinstance(end_val, (float, int)) else str(end_val)
            )

            self.table_events.setItem(i, 1, QTableWidgetItem(t_start))
            self.table_events.setItem(i, 2, QTableWidgetItem(t_end))

            # Confidence (editable?)
            conf_item = QTableWidgetItem(str(ev.confidence))
            # Make it editable effectively by allowing check? Or just text edit.
            # User asked to toggle confidence 0/1.
            # Let's make it checkable? Or just editable text 1.0/0.0
            conf_item.setFlags(conf_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table_events.setItem(i, 3, conf_item)

            # Store event object on the first item
            self.table_events.item(i, 0).setData(Qt.ItemDataRole.UserRole, ev)

        self.table_events.blockSignals(False)

    def on_event_row_clicked(self, item):
        row = item.row()
        # Retrieve event
        # Assuming we stored it in column 0
        event = self.table_events.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if event:
            self.event_selected.emit(event)

    def select_event(self, event):
        # Find row with this event
        for row in range(self.table_events.rowCount()):
            item_event = self.table_events.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if item_event == event:
                self.table_events.selectRow(row)
                # self.table_events.scrollToItem(self.table_events.item(row, 0)) # optional
                break

    def update_event_display(self, event):
        # Find row and update confidence
        for row in range(self.table_events.rowCount()):
            item_event = self.table_events.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if item_event == event:
                self.table_events.item(row, 3).setText(str(event.confidence))
                self.annotations_changed.emit(self.run_data)
                break
