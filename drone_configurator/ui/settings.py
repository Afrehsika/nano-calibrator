"""Settings page for serial protocol options and hardware pinout reference."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.widgets import CardFrame


class SettingsPage(QWidget):
    """Application settings and Arduino Nano ATmega328P hardware reference."""

    timeout_changed = Signal(float)
    stream_rate_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        title = QLabel("Settings & Hardware Reference")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        comm_card = CardFrame("Serial Communication Settings")
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Command ACK Timeout (s):"))
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(0.5, 10.0)
        self.timeout_spin.setSingleStep(0.5)
        self.timeout_spin.setValue(2.5)
        self.timeout_spin.valueChanged.connect(self.timeout_changed.emit)
        row1.addWidget(self.timeout_spin)
        row1.addStretch()
        comm_card.body_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Telemetry Stream Rate (Hz):"))
        self.rate_spin = QSpinBox()
        self.rate_spin.setRange(5, 50)
        self.rate_spin.setValue(20)
        self.apply_rate_btn = QPushButton("Apply Stream Rate")
        self.apply_rate_btn.setObjectName("PrimaryButton")
        self.apply_rate_btn.clicked.connect(lambda: self.stream_rate_changed.emit(self.rate_spin.value()))
        row2.addWidget(self.rate_spin)
        row2.addWidget(self.apply_rate_btn)
        row2.addStretch()
        comm_card.body_layout.addLayout(row2)
        root.addWidget(comm_card)

        hw_card = CardFrame(
            "Confirmed Hardware Architecture (Classic Arduino Nano ATmega328P)",
            "Reference pinout defined in firmware/nano_fc_receiver/config.h",
        )
        ref = QLabel(
            "• MCU: Classic Arduino Nano (ATmega328P, 5V, 16 MHz, 2 KB SRAM)\n"
            "• Frame Layout: Quad-X | ESC Protocol: Standard PWM (1000-2000 us)\n"
            "• Motors: M1 Front-Left (CW) -> D3 | M2 Front-Right (CCW) -> D5 | "
            "M3 Rear-Right (CW) -> D6 | M4 Rear-Left (CCW) -> D9\n"
            "• MPU6050 IMU (I2C): SDA -> A4 | SCL -> A5\n"
            "• nRF24L01 Radio (SPI): MOSI -> D11 | MISO -> D12 | SCK -> D13 | CE -> D7 | CSN -> D8\n"
            "• Optional Battery Voltage Divider: A0 | Status LED: D4"
        )
        ref.setWordWrap(True)
        hw_card.body_layout.addWidget(ref)
        root.addWidget(hw_card)
        root.addStretch()

    def set_connected_state(self, connected: bool) -> None:
        self.apply_rate_btn.setEnabled(connected)

