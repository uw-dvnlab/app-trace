"""
Plugin Runner Dialog

Unified dialog for selecting, configuring, and running annotator/compute plugins.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QGroupBox,
    QProgressBar,
    QTextEdit,
    QCheckBox,
    QLineEdit,
    QMessageBox,
    QFrame,
    QSpinBox,
    QDoubleSpinBox,
)
from pathlib import Path
from PyQt6.QtCore import pyqtSignal, Qt, QThread, QObject
import traceback

from tracengine.data.descriptors import RunData
from tracengine.gui.dialogs.channel_binding import ChannelBindingDialog


class PluginWorker(QObject):
    """Worker thread for running plugins without blocking UI."""

    finished = pyqtSignal(object)  # Result or None
    error = pyqtSignal(str)  # Error message
    progress = pyqtSignal(str)  # Status message

    def __init__(self, plugin_instance, run: RunData):
        super().__init__()
        self.plugin = plugin_instance
        self.run = run

    def run_plugin(self):
        """Execute the plugin."""
        try:
            self.progress.emit(f"Running {self.plugin.name}...")
            result = self.plugin.run(self.run)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")


class PluginRunnerDialog(QDialog):
    """
    Unified dialog for running annotator or compute plugins.

    Features:
    - Select plugin from registry dropdown
    - Configure bindings via ChannelBindingDialog
    - Run on current run
    - Show progress and results
    - Apply bindings to ALL runs in session for persistence
    """

    plugin_completed = pyqtSignal(object, object)  # (plugin_name, result)
    bindings_changed = pyqtSignal()  # Emitted when bindings are saved for all runs

    def __init__(
        self,
        run: RunData,
        plugin_type: str = "annotator",  # "annotator" or "compute"
        all_runs: list[RunData]
        | None = None,  # All runs in session for binding propagation
        project_dir: Path | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.run = run
        self.all_runs = all_runs or [run]  # Default to just current run
        self.plugin_type = plugin_type
        self.project_dir = project_dir
        self.plugin_type = plugin_type
        self.selected_plugin_cls = None
        self._worker = None
        self._thread = None
        self._param_widgets = {}  # name -> widget

        title = "Run Annotator" if plugin_type == "annotator" else "Run Compute"
        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._setup_ui()
        self._populate_plugins()

    def _setup_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout(self)

        # Plugin selection
        select_group = QGroupBox("Select Plugin")
        select_layout = QFormLayout()

        self.combo_plugin = QComboBox()
        self.combo_plugin.currentIndexChanged.connect(self._on_plugin_selected)
        select_layout.addRow("Plugin:", self.combo_plugin)

        # Instance Name
        self.txt_instance_name = QLineEdit()
        self.txt_instance_name.setPlaceholderText(
            "Instance Name (default: Plugin Name)"
        )
        self.txt_instance_name.textChanged.connect(self._on_instance_name_changed)
        select_layout.addRow("Instance Name:", self.txt_instance_name)

        # Plugin info
        self.lbl_version = QLabel("")
        self.lbl_version.setStyleSheet("color: gray;")
        select_layout.addRow("Version:", self.lbl_version)

        self.lbl_requirements = QLabel("")
        self.lbl_requirements.setWordWrap(True)
        select_layout.addRow("Requirements:", self.lbl_requirements)

        select_group.setLayout(select_layout)
        layout.addWidget(select_group)

        # Parameters Group
        self.param_group = QGroupBox("Parameters")
        self.param_layout = QFormLayout()
        self.param_group.setLayout(self.param_layout)
        self.param_group.hide()  # Hidden by default
        layout.addWidget(self.param_group)

        # Configure button
        btn_layout = QHBoxLayout()

        self.btn_configure = QPushButton("Configure Bindings...")
        self.btn_configure.clicked.connect(self._on_configure)
        self.btn_configure.setEnabled(False)
        btn_layout.addWidget(self.btn_configure)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: green;")
        btn_layout.addWidget(self.lbl_status)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        # Export option (for compute)
        if self.plugin_type == "compute":
            self.chk_export = QCheckBox("Export Results (CSV + Provenance)")
            self.chk_export.setChecked(True)
            self.chk_export.setToolTip("Save outputs to project/exports folder")
            layout.addWidget(self.chk_export)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Output area
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.hide()
        output_layout.addWidget(self.progress_bar)

        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setMaximumHeight(150)
        output_layout.addWidget(self.txt_output)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        btn_cancel = QPushButton("Close")
        btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(btn_cancel)

        self.btn_run = QPushButton("Run Plugin")
        self.btn_run.clicked.connect(self._on_run)
        self.btn_run.setEnabled(False)
        self.btn_run.setDefault(True)
        bottom_layout.addWidget(self.btn_run)

        layout.addLayout(bottom_layout)

    def _populate_plugins(self):
        """Populate plugin dropdown from registry."""
        self.combo_plugin.addItem("-- Select Plugin --", None)

        if self.plugin_type == "annotator":
            from tracengine.annotate import list_annotators

            plugins = list_annotators()
        else:
            from tracengine.compute import list_compute

            plugins = list_compute()

        for name, cls in sorted(plugins.items()):
            display_name = getattr(cls, "name", name)
            self.combo_plugin.addItem(f"{display_name} ({name})", cls)

    def _on_instance_name_changed(self, text):
        """Re-validate when instance name changes."""
        required_channels = getattr(self.selected_plugin_cls, "required_channels", {})
        required_events = getattr(self.selected_plugin_cls, "required_events", {})
        has_requirements = bool(required_channels or required_events)

        if self._check_configured():
            self.lbl_status.setText("✓ Configured")
            self.btn_run.setEnabled(True)
        else:
            self.lbl_status.setText(
                "⚠ Configure bindings first" if has_requirements else ""
            )
            self.btn_run.setEnabled(not has_requirements)

    def _on_plugin_selected(self, index):
        """Handle plugin selection."""
        cls = self.combo_plugin.currentData()
        self.selected_plugin_cls = cls

        if cls is None:
            self.lbl_version.setText("")
            self.lbl_requirements.setText("")
            self.btn_configure.setEnabled(False)
            self.btn_run.setEnabled(False)
            self.lbl_status.setText("")
            return

        # Update default instance name
        if cls:
            current_name = self.txt_instance_name.text()

            # Check for existing config for this plugin
            existing_name = None
            if self.run.run_config:
                # Check channel bindings
                full_bindings = self.run.run_config.channel_bindings
                for name in full_bindings:
                    if name == cls.name or name.startswith(f"{cls.name}_"):
                        existing_name = name
                        break

                # Check event bindings if not found
                if not existing_name and self.run.run_config.event_bindings:
                    for name in self.run.run_config.event_bindings:
                        if name == cls.name or name.startswith(f"{cls.name}_"):
                            existing_name = name
                            break

            if existing_name:
                self.txt_instance_name.setText(existing_name)
            elif not current_name or current_name == cls.name:
                self.txt_instance_name.setText(cls.name)

        # Show plugin info
        version = getattr(cls, "version", "unknown")
        self.lbl_version.setText(version)

        # Build requirements summary
        reqs = []
        required_channels = getattr(cls, "required_channels", {})
        required_events = getattr(cls, "required_events", {})

        if required_channels:
            reqs.append(f"{len(required_channels)} channel(s)")
        if required_events:
            reqs.append(f"{len(required_events)} event group(s)")

        self.lbl_requirements.setText(", ".join(reqs) if reqs else "None")

        # Enable configure if there are requirements
        has_requirements = bool(required_channels or required_events)
        self.btn_configure.setEnabled(has_requirements)

        # Check if already configured
        self._on_instance_name_changed(self.txt_instance_name.text())

        # Build parameter form
        self._build_parameter_form(cls)

    def _build_parameter_form(self, cls):
        """Build parameter UI based on plugin definition."""
        # Clear existing
        while self.param_layout.rowCount() > 0:
            self.param_layout.removeRow(0)
        self._param_widgets.clear()
        self.param_group.hide()

        if not cls:
            return

        # Get parameters
        params = getattr(cls, "get_parameters", lambda: [])()
        if not params:
            return

        self.param_group.show()

        for p in params:
            name = p["name"]
            label = p.get("label", name)
            ptype = p.get("type", "str")
            default = p.get("default")

            widget = None

            if ptype == "int":
                widget = QSpinBox()
                widget.setRange(p.get("min", -999999), p.get("max", 999999))
                widget.setSingleStep(p.get("step", 1))
                if default is not None:
                    widget.setValue(int(default))
                if "suffix" in p:
                    widget.setSuffix(f" {p['suffix']}")

            elif ptype == "float":
                widget = QDoubleSpinBox()
                widget.setRange(p.get("min", -999999.0), p.get("max", 999999.0))
                widget.setSingleStep(p.get("step", 0.1))
                if default is not None:
                    widget.setValue(float(default))
                if "suffix" in p:
                    widget.setSuffix(f" {p['suffix']}")

            elif ptype == "bool":
                widget = QCheckBox()
                if default is not None:
                    widget.setChecked(bool(default))

            elif ptype == "enum":
                widget = QComboBox()
                options = p.get("options", [])
                for opt in options:
                    widget.addItem(str(opt))
                if default is not None:
                    widget.setCurrentText(str(default))

            else:
                # Default to string
                widget = QLineEdit()
                if default is not None:
                    widget.setText(str(default))

            if widget:
                # Add tooltip if description exists
                if "description" in p:
                    widget.setToolTip(p["description"])
                self.param_layout.addRow(f"{label}:", widget)
                self._param_widgets[name] = widget

    def _get_param_values(self) -> dict:
        """Collect values from parameter widgets."""
        values = {}
        for name, widget in self._param_widgets.items():
            if isinstance(widget, QSpinBox):
                values[name] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                values[name] = widget.value()
            elif isinstance(widget, QCheckBox):
                values[name] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                # Try to infer type from current text, fallback to string
                text = widget.currentText()
                # If we knew the original type we could cast, but for now str is safe for enums
                values[name] = text
            elif isinstance(widget, QLineEdit):
                values[name] = widget.text()
        return values

    def _check_configured(self) -> bool:
        """Check if all required bindings are configured for current instance."""
        if not self.selected_plugin_cls:
            return False

        required_channels = getattr(self.selected_plugin_cls, "required_channels", {})
        if not required_channels:
            return True

        if not self.run.run_config:
            return False

        # Get instance name
        instance_name = self.txt_instance_name.text()
        if not instance_name:
            instance_name = self.selected_plugin_cls.name

        if instance_name:
            # Check channels
            if required_channels:
                if instance_name not in self.run.run_config.channel_bindings:
                    return False
                instance_bindings = self.run.run_config.channel_bindings[instance_name]
                for role, spec in required_channels.items():
                    if spec.semantic_role not in instance_bindings:
                        return False

            # Check events
            required_events = getattr(self.selected_plugin_cls, "required_events", {})
            if required_events:
                if instance_name not in self.run.run_config.event_bindings:
                    return False
                instance_event_bindings = self.run.run_config.event_bindings[
                    instance_name
                ]
                for role, spec in required_events.items():
                    if role not in instance_event_bindings:
                        return False

        return True

    def _on_configure(self):
        """Open channel binding dialog."""
        if not self.selected_plugin_cls:
            return

        dialog = ChannelBindingDialog(
            run=self.run,
            required_channels=getattr(
                self.selected_plugin_cls, "required_channels", {}
            ),
            required_events=getattr(self.selected_plugin_cls, "required_events", {}),
            plugin_name=getattr(self.selected_plugin_cls, "name", "Plugin"),
            parent=self,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get the bindings that were saved to current run
            bindings = dialog.get_bindings()
            channel_bindings = bindings.get("channels", {})

            # Generate instance name first (needed for nested storage)
            instance_name = self.txt_instance_name.text()
            if not instance_name and self.selected_plugin_cls:
                instance_name = self.selected_plugin_cls.name

            # Suggest better instance name based on bindings
            if self.selected_plugin_cls and channel_bindings:
                base_name = self.selected_plugin_cls.name
                first_binding = list(channel_bindings.values())[0]
                safe_suffix = first_binding.replace(":", "_").replace(" ", "_")
                instance_name = f"{base_name}_{safe_suffix}"
                self.txt_instance_name.setText(instance_name)

            # Apply to current run only
            if channel_bindings or bindings.get("events"):
                from tracengine.data.descriptors import RunConfig

                if self.run.run_config is None:
                    self.run.run_config = RunConfig()

                # Store channel bindings
                if channel_bindings:
                    self.run.run_config.channel_bindings[instance_name] = (
                        channel_bindings
                    )

                # Store event bindings
                if bindings.get("events"):
                    self.run.run_config.event_bindings[instance_name] = bindings[
                        "events"
                    ]

            self.lbl_status.setText("✓ Configured")
            self.btn_run.setEnabled(True)
            self.bindings_changed.emit()

    def _on_run(self):
        """Execute the selected plugin."""
        if not self.selected_plugin_cls:
            return

        self.txt_output.clear()
        self.txt_output.append(f"Initializing {self.selected_plugin_cls.name}...")
        self.progress_bar.show()
        self.btn_run.setEnabled(False)

        try:
            # Create plugin instance
            plugin = self.selected_plugin_cls()

            # Run synchronously for now (can make async later)
            # Run synchronously for now (can make async later)
            self.txt_output.append("Running...")
            instance_name = self.txt_instance_name.text() or plugin.name

            # Get parameters
            params = self._get_param_values()
            if params:
                self.txt_output.append(f"Parameters: {params}")

            # Add export args if compute
            kwargs = {}
            if self.plugin_type == "compute":
                export = self.chk_export.isChecked()
                kwargs["export"] = export
                kwargs["project_dir"] = self.project_dir

                if export and not self.project_dir:
                    self.txt_output.append(
                        "Warning: Cannot export - project directory not known."
                    )

            result = plugin.run(
                self.run, instance_name=instance_name, **params, **kwargs
            )

            self.progress_bar.hide()
            self._handle_result(plugin, result)

        except Exception as e:
            self.progress_bar.hide()
            self.btn_run.setEnabled(True)
            self.txt_output.append(f"\n❌ Error: {e}")
            self.txt_output.append(traceback.format_exc())

    def _handle_result(self, plugin, result):
        """Handle plugin execution result."""
        self.btn_run.setEnabled(True)

        instance_name = self.txt_instance_name.text() or plugin.name
        params = self._get_param_values()

        # Save parameters to RunConfig for reproducibility
        if params:
            from tracengine.data.descriptors import RunConfig

            if self.run.run_config is None:
                self.run.run_config = RunConfig()
            self.run.run_config.parameters[instance_name] = params

            self.bindings_changed.emit()  # Trigger config save

        if self.plugin_type == "annotator":
            # Result is list of Event objects
            count = len(result) if result else 0
            self.txt_output.append(f"\n✓ Detected {count} events")

            if result:
                # Add to run annotations
                self.run.annotations[instance_name] = result
                self.txt_output.append(f"Added to annotations under '{instance_name}'")

        else:
            # Result is DataFrame
            if result is not None and not result.empty:
                self.txt_output.append(f"\n✓ Computed {len(result)} rows")
                self.txt_output.append(f"Columns: {', '.join(result.columns[:5])}...")
            else:
                self.txt_output.append("\n✓ Computation complete (no rows)")

        self.plugin_completed.emit(plugin.name, result)
