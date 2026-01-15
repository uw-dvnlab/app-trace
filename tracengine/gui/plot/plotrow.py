from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QCheckBox,
)
from PyQt6.QtCore import pyqtSignal, Qt
import pyqtgraph as pg
import numpy as np
from tracengine.utils.signal_processing import apply_filter
import pandas as pd


class PlotControlPanel(QWidget):
    moved_up = pyqtSignal()
    moved_down = pyqtSignal()
    selection_toggled = pyqtSignal(bool)
    processing_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(60)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        # Selection
        self.chk_select = QCheckBox()
        self.chk_select.setToolTip("Select for processing")
        self.chk_select.toggled.connect(self.selection_toggled.emit)

        # Move Buttons
        self.btn_up = QPushButton("▲")
        self.btn_up.setFixedWidth(40)
        self.btn_up.clicked.connect(self.moved_up.emit)

        self.btn_down = QPushButton("▼")
        self.btn_down.setFixedWidth(40)
        self.btn_down.clicked.connect(self.moved_down.emit)

        # Processing Toggle
        self.btn_proc = QPushButton("Raw")
        self.btn_proc.setCheckable(True)
        self.btn_proc.setFixedWidth(50)
        self.btn_proc.setToolTip("Toggle between Raw and Processed Data")
        self.btn_proc.setEnabled(False)
        self.btn_proc.toggled.connect(self._on_proc_toggled)

        layout.addWidget(self.chk_select, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.btn_up, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.btn_down, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        layout.addWidget(self.btn_proc, alignment=Qt.AlignmentFlag.AlignCenter)

    def _on_proc_toggled(self, checked):
        text = "Proc" if checked else "Raw"
        self.btn_proc.setText(text)
        self.processing_toggled.emit(checked)

    def enable_processing_toggle(self, enabled):
        self.btn_proc.setEnabled(enabled)
        if not enabled:
            self.btn_proc.setChecked(False)


class PlotRow(QWidget):
    moved_up = pyqtSignal(object)
    moved_down = pyqtSignal(object)

    def __init__(self, signal_name, modality, channel):
        super().__init__()
        self.signal_name = signal_name
        self.modality = modality
        self.channel = channel

        # Data storage
        self.raw_t = None
        self.raw_y = None
        self.proc_t = None
        self.proc_y = None

        # Persistent settings
        self.filter_params = None

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setMinimumHeight(200)

        # Title Label
        self.lbl_title = QLabel(signal_name)
        self.lbl_title.setStyleSheet(
            "font-weight: bold; background-color: #333; color: #EEE; padding: 2px;"
        )
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.lbl_title)

        # Content Layout
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Control Panel
        self.controls = PlotControlPanel()
        self.controls.moved_up.connect(lambda: self.moved_up.emit(self))
        self.controls.moved_down.connect(lambda: self.moved_down.emit(self))
        self.controls.processing_toggled.connect(self.update_plot)
        self.chk_select = self.controls.chk_select

        # Plot Widget
        self.plot_widget = pg.PlotWidget()
        self.plot_item = self.plot_widget.plot([], [], pen="g")
        self.plot_widget.setLabel("left", channel)

        # Style
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        content_layout.addWidget(self.controls)
        content_layout.addWidget(self.plot_widget)

        main_layout.addWidget(content_widget)

    def update_from_run(self, run):
        t, y = run.get_signal(self.modality, self.channel)
        self.raw_t = t
        self.raw_y = y
        self.proc_t = None
        self.proc_y = None

        # Re-apply processing if exists
        self._reapply_processing()

        self.update_plot()

    def interpolate_missing(self):
        if self.raw_y is not None:
            # interpolate() fills interior gaps (linear)
            # bfill() handles leading NaNs, ffill() handles trailing NaNs
            interp_y = pd.Series(self.raw_y).interpolate().bfill().ffill().values
            remaining_nans = np.sum(np.isnan(interp_y))
            if remaining_nans > 0:
                print(f"Warning: {remaining_nans} NaNs remain after interpolation")
            return interp_y
        return self.raw_y

    def set_filter(self, params):
        self.filter_params = params
        self._reapply_processing()
        # Auto-enable processed view if filtering is active
        if self.proc_y is not None:
            self.controls.enable_processing_toggle(True)
            self.controls.btn_proc.setChecked(True)
        self.update_plot()

    def _reapply_processing(self):
        if self.raw_y is not None and self.filter_params:
            # Check if interpolation is requested
            do_interp = self.filter_params.get("interpolate_missing", False)
            print(f"[DEBUG] filter_params keys: {self.filter_params.keys()}")
            print(f"[DEBUG] interpolate_missing={do_interp}")
            print(f"[DEBUG] NaNs in raw_y: {np.sum(np.isnan(self.raw_y))}")

            if do_interp:
                raw_y = self.interpolate_missing()
                print(f"[DEBUG] NaNs after interpolation: {np.sum(np.isnan(raw_y))}")
            else:
                raw_y = self.raw_y

            dt = np.mean(np.diff(self.raw_t))
            if dt > 0:
                fs = 1.0 / dt
                self.proc_y = apply_filter(raw_y, fs, **self.filter_params)
                print(f"[DEBUG] NaNs in proc_y: {np.sum(np.isnan(self.proc_y))}")
                self.proc_t = self.raw_t
                self.controls.enable_processing_toggle(True)
        else:
            self.controls.enable_processing_toggle(False)

    def update_plot(self, show_processed=None):
        if show_processed is None:
            show_processed = self.controls.btn_proc.isChecked()

        # Update Title
        base_title = self.signal_name
        mods = []
        if self.filter_params:
            mods.append(f"Filter: {self.filter_params.get('filter_type')}")

        if show_processed and self.proc_y is not None:
            self.plot_item.setData(self.proc_t, self.proc_y)
            self.plot_item.setPen("c")
            full_title = f"{base_title} [{' | '.join(mods)}]" if mods else base_title
        else:
            if self.raw_y is not None:
                self.plot_item.setData(self.raw_t, self.raw_y)
                self.plot_item.setPen("g")
            full_title = base_title

        self.lbl_title.setText(full_title)

    def get_active_signal(self):
        """Returns tuple (t, y) of currently visible signal"""
        if self.controls.btn_proc.isChecked() and self.proc_y is not None:
            return self.proc_t, self.proc_y
        return self.raw_t, self.raw_y


class DerivedPlotRow(PlotRow):
    """
    Operates on a derivative of a source signal.
    """

    def __init__(self, target_modality, source_channel, order):
        suffix = "Velocity" if order == 1 else "Acceleration"
        name = f"{source_channel} [{suffix}]"
        # We pass target_modality (e.g. optotrak_deriv1) to super
        # So super will fetch from that modality.
        super().__init__(name, target_modality, source_channel)
        self.order = order
        self.lbl_title.setStyleSheet(
            "font-weight: bold; background-color: #522; color: #EEE; padding: 2px;"
        )

    # We remove update_from_run override because standard logic works now!
    # The signal is in RunData.
