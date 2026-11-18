"""Module B: Dual-loop PID Configuration (Inner Rate Loop & Outer Angle Loop)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from models.pid_config import AnglePID, AxisPID, PIDConfig, PID_MAX_GAIN, PID_MIN_GAIN, RatePID
from ui.widgets import CardFrame


class _LoopPIDGroup(CardFrame):
    """Reusable 3-axis (Roll, Pitch, Yaw) P/I/D editor card."""

    def __init__(self, title: str, subtitle: str, parent: QWidget | None = None) -> None:
        super().__init__(title, subtitle, parent)
        self.spins: dict[tuple[str, str], QDoubleSpinBox] = {}

        grid = QGridLayout()
        grid.setSpacing(10)

        headers = ["Axis", "P (Proportional)", "I (Integral)", "D (Derivative)"]
        tooltips = {
            "p": "Proportional gain: immediate corrective response to error.",
            "i": "Integral gain: eliminates steady-state drift over time.",
            "d": "Derivative gain: damps overshoot and rapid oscillations.",
        }
        for col, text in enumerate(headers):
            lbl = QLabel(text)
            lbl.setObjectName("MutedLabel")
            grid.addWidget(lbl, 0, col)

        for row, axis in enumerate(("roll", "pitch", "yaw"), start=1):
            axis_lbl = QLabel(axis.capitalize())
            axis_lbl.setStyleSheet("font-weight: 600;")
            grid.addWidget(axis_lbl, row, 0)

            for col, term in enumerate(("p", "i", "d"), start=1):
                spin = QDoubleSpinBox()
                spin.setRange(PID_MIN_GAIN, PID_MAX_GAIN)
                spin.setDecimals(3)
                spin.setSingleStep(0.05 if term != "d" else 0.5)
                spin.setToolTip(tooltips[term])
                grid.addWidget(spin, row, col)
                self.spins[(axis, term)] = spin

        self.body_layout.addLayout(grid)

    def set_values(self, loop_obj: RatePID | AnglePID) -> None:
        for axis in ("roll", "pitch", "yaw"):
            ax: AxisPID = getattr(loop_obj, axis)
            self.spins[(axis, "p")].setValue(ax.p)
            self.spins[(axis, "i")].setValue(ax.i)
            self.spins[(axis, "d")].setValue(ax.d)

    def get_axis(self, axis: str) -> AxisPID:
        return AxisPID(
            p=self.spins[(axis, "p")].value(),
            i=self.spins[(axis, "i")].value(),
            d=self.spins[(axis, "d")].value(),
        )


class PIDTuningPage(QWidget):
    """PID tuning page separating inner rate-control and outer angle-control loops."""

    read_requested = Signal()
    send_requested = Signal(object)  # PIDConfig
    save_eeprom_requested = Signal()
    reset_requested = Signal()
    open_profiles_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.set_pid_config(PIDConfig.defaults())

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        title = QLabel("PID Configuration")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        desc = QLabel(
            "Configure the cascaded flight controller loops. The Inner Rate Loop stabilizes angular "
            "velocity (deg/s) using the MPU6050 gyro; the Outer Angle Loop converts stick tilt angles "
            "(deg) into target rates for Stabilize mode."
        )
        desc.setObjectName("MutedLabel")
        desc.setWordWrap(True)
        root.addWidget(desc)

        self.angle_enable_cb = QCheckBox("Enable Outer Angle-Control Loop (Stabilize Mode)")
        self.angle_enable_cb.setChecked(True)
        self.angle_enable_cb.setToolTip("When unchecked, the flight controller runs pure Acro/Rate mode.")
        self.angle_enable_cb.toggled.connect(self._on_angle_toggled)
        root.addWidget(self.angle_enable_cb)

        loops_row = QHBoxLayout()
        loops_row.setSpacing(16)

        self.rate_group = _LoopPIDGroup(
            "Inner Rate-Control Loop (deg/s)",
            "Fast 250 Hz gyro feedback loop driving the Quad-X motor mixer.",
        )
        self.angle_group = _LoopPIDGroup(
            "Outer Angle-Control Loop (deg)",
            "Attitude hold loop outputting target angular rates to the inner loop.",
        )
        loops_row.addWidget(self.rate_group, 1)
        loops_row.addWidget(self.angle_group, 1)
        root.addLayout(loops_row)

        # Action Bar
        actions_card = CardFrame("Flight Controller Actions")
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.read_btn = QPushButton("Read from FC")
        self.read_btn.clicked.connect(self.read_requested.emit)

        self.send_btn = QPushButton("Send PID to FC")
        self.send_btn.setObjectName("PrimaryButton")
        self.send_btn.clicked.connect(self._on_send_clicked)

        self.eeprom_btn = QPushButton("Save to EEPROM")
        self.eeprom_btn.setObjectName("SuccessButton")
        self.eeprom_btn.setToolTip("Persist active PID gains to ATmega328P non-volatile EEPROM.")
        self.eeprom_btn.clicked.connect(self.save_eeprom_requested.emit)

        self.reset_btn = QPushButton("Reset Defaults")
        self.reset_btn.clicked.connect(self.reset_requested.emit)

        self.profiles_btn = QPushButton("Manage Profiles...")
        self.profiles_btn.clicked.connect(self.open_profiles_requested.emit)

        for btn in (self.read_btn, self.send_btn, self.eeprom_btn, self.reset_btn, self.profiles_btn):
            btn_row.addWidget(btn)
        btn_row.addStretch()

        actions_card.body_layout.addLayout(btn_row)
        root.addWidget(actions_card)
        root.addStretch()

        self.set_connected_state(False)

    def _on_angle_toggled(self, enabled: bool) -> None:
        self.angle_group.setEnabled(enabled)

    def _on_send_clicked(self) -> None:
        self.send_requested.emit(self.get_pid_config())

    def set_pid_config(self, cfg: PIDConfig) -> None:
        self.angle_enable_cb.setChecked(cfg.angle_loop_enabled)
        self.rate_group.set_values(cfg.rate)
        self.angle_group.set_values(cfg.angle)
        self.angle_group.setEnabled(cfg.angle_loop_enabled)

    def get_pid_config(self) -> PIDConfig:
        return PIDConfig(
            angle_loop_enabled=self.angle_enable_cb.isChecked(),
            rate=RatePID(
                roll=self.rate_group.get_axis("roll"),
                pitch=self.rate_group.get_axis("pitch"),
                yaw=self.rate_group.get_axis("yaw"),
            ),
            angle=AnglePID(
                roll=self.angle_group.get_axis("roll"),
                pitch=self.angle_group.get_axis("pitch"),
                yaw=self.angle_group.get_axis("yaw"),
            ),
        )

    def set_connected_state(self, connected: bool) -> None:
        self.read_btn.setEnabled(connected)
        self.send_btn.setEnabled(connected)
        self.eeprom_btn.setEnabled(connected)
        self.reset_btn.setEnabled(connected)

