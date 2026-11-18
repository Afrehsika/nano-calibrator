"""Module E: Motor Configuration, Output Monitoring, and Safe Motor Testing."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from models.motor_config import MotorConfig, MotorOutputs
from models.sensor_data import SystemStatus
from ui.theme import PALETTE
from ui.widgets import CardFrame, QuadXDiagramWidget, StatusPill


class _MotorCard(CardFrame):
    """Single motor card showing identification, live output, and safe test slider."""

    test_requested = Signal(int, int)  # motor_idx (1..4), pwm_us

    def __init__(self, motor_num: int, position: str, direction: str, pin: str, parent: QWidget | None = None) -> None:
        super().__init__(f"Motor {motor_num} ({position})", f"Direction: {direction} | Pin: {pin}", parent)
        self.motor_num = motor_num

        self.pwm_label = QLabel("1000 us")
        self.pwm_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #38BDF8;")
        self.bar = QProgressBar()
        self.bar.setRange(1000, 2000)
        self.bar.setValue(1000)
        self.bar.setFormat("%v us")

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1000, 1250)
        self.slider.setValue(1000)
        self.slider.valueChanged.connect(self._on_slider_changed)

        row = QHBoxLayout()
        self.test_val_lbl = QLabel("Test: 1000 us")
        self.test_btn = QPushButton(f"Spin M{motor_num}")
        self.test_btn.setObjectName("PrimaryButton")
        self.test_btn.clicked.connect(lambda: self.test_requested.emit(self.motor_num, self.slider.value()))
        row.addWidget(self.test_val_lbl)
        row.addStretch()
        row.addWidget(self.test_btn)

        self.body_layout.addWidget(self.pwm_label)
        self.body_layout.addWidget(self.bar)
        self.body_layout.addWidget(self.slider)
        self.body_layout.addLayout(row)

    def _on_slider_changed(self, val: int) -> None:
        self.test_val_lbl.setText(f"Test: {val} us")

    def set_test_cap(self, min_us: int, test_max_us: int) -> None:
        self.slider.setRange(min_us, test_max_us)

    def set_test_enabled(self, enabled: bool) -> None:
        self.slider.setEnabled(enabled)
        self.test_btn.setEnabled(enabled)
        if not enabled:
            self.slider.setValue(self.slider.minimum())

    def update_output(self, pwm_us: int) -> None:
        self.pwm_label.setText(f"{pwm_us} us")
        self.bar.setValue(max(self.bar.minimum(), min(self.bar.maximum(), pwm_us)))


class MotorConfigurationPage(QWidget):
    """Quad-X motor configuration and safety-interlocked motor testing."""

    motor_test_requested = Signal(int, int)  # motor 1..4, pwm_us
    motor_stop_requested = Signal()
    send_motor_config_requested = Signal(object)  # MotorConfig

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._connected = False
        self._armed = False
        self._session_confirmed = False
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel("Motor Configuration & Testing (Quad-X)")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        # Prominent Safety Banner
        banner = QFrame()
        banner.setObjectName("DangerBanner")
        b_layout = QVBoxLayout(banner)
        b_layout.setContentsMargins(14, 10, 14, 10)
        warn_lbl = QLabel(
            "SAFETY WARNING: Remove ALL propellers before testing motors. "
            "Motor testing is only permitted while DISARMED and is capped in firmware."
        )
        warn_lbl.setStyleSheet("color: #FECACA; font-weight: 700;")
        warn_lbl.setWordWrap(True)
        b_layout.addWidget(warn_lbl)

        safety_row = QHBoxLayout()
        self.prop_confirm_cb = QCheckBox("I confirm all propellers are removed and the frame is secured.")
        self.prop_confirm_cb.toggled.connect(self._update_test_interlock)

        self.stop_all_btn = QPushButton("STOP ALL MOTORS")
        self.stop_all_btn.setObjectName("DangerButton")
        self.stop_all_btn.clicked.connect(self._on_stop_all)

        safety_row.addWidget(self.prop_confirm_cb, 1)
        safety_row.addWidget(self.stop_all_btn)
        b_layout.addLayout(safety_row)
        root.addWidget(banner)

        # 4 Individual Motor Cards + Live Quad-X Frame Diagram
        center_row = QHBoxLayout()
        center_row.setSpacing(14)

        grid = QGridLayout()
        grid.setSpacing(12)
        specs = [
            (1, "Front-Left", "CW", "D3"),
            (2, "Front-Right", "CCW", "D5"),
            (3, "Rear-Right", "CW", "D6"),
            (4, "Rear-Left", "CCW", "D9"),
        ]
        self.motor_cards: list[_MotorCard] = []
        positions = [(0, 0), (0, 1), (1, 1), (1, 0)]
        for (m_num, pos, spin, pin), (r, c) in zip(specs, positions):
            card = _MotorCard(m_num, pos, spin, pin)
            card.test_requested.connect(self._on_motor_test_clicked)
            self.motor_cards.append(card)
            grid.addWidget(card, r, c)

        grid_wrap = QWidget()
        grid_wrap.setLayout(grid)
        center_row.addWidget(grid_wrap, 2)

        diagram_card = CardFrame("Quad-X Frame Layout", "Live ESC output rings (green/amber/red)")
        self.quad_diagram = QuadXDiagramWidget()
        diagram_card.body_layout.addWidget(self.quad_diagram, 1)
        center_row.addWidget(diagram_card, 1)

        root.addLayout(center_row)

        # Output Range & ESC Calibration Status
        cfg_card = CardFrame("ESC & Output Range Configuration")
        cfg_row = QHBoxLayout()
        cfg_row.setSpacing(12)

        self.esc_cal_pill = StatusPill("ESC STATUS UNKNOWN", "muted")
        self.min_spin = self._make_pwm_spin(900, 1200, 1000)
        self.idle_spin = self._make_pwm_spin(1000, 1300, 1080)
        self.max_spin = self._make_pwm_spin(1700, 2100, 2000)
        self.test_max_spin = self._make_pwm_spin(1050, 1400, 1250)

        for lbl_text, widget in [
            ("Min PWM:", self.min_spin),
            ("Idle PWM:", self.idle_spin),
            ("Max PWM:", self.max_spin),
            ("Test Cap:", self.test_max_spin),
        ]:
            cfg_row.addWidget(QLabel(lbl_text))
            cfg_row.addWidget(widget)

        cfg_row.addWidget(self.esc_cal_pill)
        self.apply_cfg_btn = QPushButton("Send Motor Config")
        self.apply_cfg_btn.setObjectName("PrimaryButton")
        self.apply_cfg_btn.clicked.connect(self._on_apply_config)
        cfg_row.addWidget(self.apply_cfg_btn)

        cfg_card.body_layout.addLayout(cfg_row)
        root.addWidget(cfg_card)

        self.set_connected_state(False)

    @staticmethod
    def _make_pwm_spin(low: int, high: int, val: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(val)
        spin.setSuffix(" us")
        return spin

    def _update_test_interlock(self) -> None:
        allow = self._connected and (not self._armed) and self.prop_confirm_cb.isChecked()
        for card in self.motor_cards:
            card.set_test_enabled(allow)
        if not allow:
            self._session_confirmed = False

    def _on_motor_test_clicked(self, motor_num: int, pwm_us: int) -> None:
        if not self._session_confirmed:
            reply = QMessageBox.warning(
                self,
                "Confirm Motor Spin Test",
                f"You are about to spin Motor {motor_num} at {pwm_us} us.\n\n"
                "Confirm all propellers are removed and hands are clear.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._session_confirmed = True
        self.motor_test_requested.emit(motor_num, pwm_us)

    def _on_stop_all(self) -> None:
        for card in self.motor_cards:
            card.slider.setValue(card.slider.minimum())
        self.motor_stop_requested.emit()

    def _on_apply_config(self) -> None:
        cfg = self.get_motor_config()
        self.send_motor_config_requested.emit(cfg)

    def set_motor_config(self, cfg: MotorConfig) -> None:
        self.min_spin.setValue(cfg.min_us)
        self.idle_spin.setValue(cfg.idle_us)
        self.max_spin.setValue(cfg.max_us)
        self.test_max_spin.setValue(cfg.test_max_us)
        self.esc_cal_pill.set_state(
            "ESC CALIBRATED" if cfg.esc_calibrated else "ESC UNCALIBRATED",
            "success" if cfg.esc_calibrated else "warning",
        )
        for card in self.motor_cards:
            card.set_test_cap(cfg.min_us, cfg.test_max_us)

    def get_motor_config(self) -> MotorConfig:
        return MotorConfig(
            min_us=self.min_spin.value(),
            idle_us=self.idle_spin.value(),
            max_us=self.max_spin.value(),
            test_max_us=self.test_max_spin.value(),
            esc_calibrated=False,
        )

    def set_connected_state(self, connected: bool) -> None:
        self._connected = connected
        self.apply_cfg_btn.setEnabled(connected)
        self.stop_all_btn.setEnabled(connected)
        if not connected:
            self.prop_confirm_cb.setChecked(False)
            self.esc_cal_pill.set_state("ESC STATUS UNKNOWN", "muted")
        self._update_test_interlock()

    def update_telemetry(self, status: SystemStatus, motors: MotorOutputs) -> None:
        if status.armed != self._armed:
            self._armed = status.armed
            self._update_test_interlock()
        self.quad_diagram.set_outputs(motors.m1_us, motors.m2_us, motors.m3_us, motors.m4_us)
        for card, pwm in zip(self.motor_cards, (motors.m1_us, motors.m2_us, motors.m3_us, motors.m4_us)):
            card.update_output(pwm)

