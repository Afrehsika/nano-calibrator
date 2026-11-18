"""Settings page for serial protocol, background theme colors, and hardware reference."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.theme import THEME_PRESETS
from ui.widgets import CardFrame


class SettingsPage(QWidget):
    """Application settings, background theme picker, and Arduino Nano hardware reference."""

    timeout_changed = Signal(float)
    stream_rate_changed = Signal(int)
    theme_changed = Signal(str, str)  # bg_hex, accent_hex

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_bg = "#090D16"
        self._current_accent = "#38BDF8"
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        title = QLabel("Settings & Appearance")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        # Appearance & Background Color Picker
        theme_card = CardFrame(
            "Background & Theme Colors",
            "Choose a preset cockpit theme or pick any custom background color.",
        )
        grid = QGridLayout()
        grid.setSpacing(8)
        for idx, (name, colors) in enumerate(THEME_PRESETS.items()):
            btn = QPushButton(f"  {name}")
            btn.setStyleSheet(
                f"background-color: {colors['bg']}; color: #F1F5F9; "
                f"border: 2px solid {colors['accent']}; border-radius: 7px; "
                "padding: 8px 10px; font-weight: 600; text-align: left;"
            )
            btn.clicked.connect(
                lambda _c=False, bg=colors["bg"], acc=colors["accent"]: self._apply_theme(bg, acc)
            )
            grid.addWidget(btn, idx // 4, idx % 4)
        theme_card.body_layout.addLayout(grid)

        custom_row = QHBoxLayout()
        self.custom_bg_btn = QPushButton("Custom Background Color...")
        self.custom_bg_btn.setObjectName("PrimaryButton")
        self.custom_bg_btn.clicked.connect(self._pick_custom_bg)

        self.custom_accent_btn = QPushButton("Custom Accent Color...")
        self.custom_accent_btn.clicked.connect(self._pick_custom_accent)

        self.reset_theme_btn = QPushButton("Reset Default")
        self.reset_theme_btn.clicked.connect(lambda: self._apply_theme("#090D16", "#38BDF8"))

        self.active_color_lbl = QLabel("Active: #090D16")
        self.active_color_lbl.setObjectName("MutedLabel")

        custom_row.addWidget(self.custom_bg_btn)
        custom_row.addWidget(self.custom_accent_btn)
        custom_row.addWidget(self.reset_theme_btn)
        custom_row.addStretch()
        custom_row.addWidget(self.active_color_lbl)
        theme_card.body_layout.addLayout(custom_row)
        root.addWidget(theme_card)

        # Serial Communication Settings
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

    def _apply_theme(self, bg_hex: str, accent_hex: str) -> None:
        self._current_bg = bg_hex
        self._current_accent = accent_hex
        self.active_color_lbl.setText(f"Active: {bg_hex} (Accent {accent_hex})")
        self.theme_changed.emit(bg_hex, accent_hex)

    def _pick_custom_bg(self) -> None:
        color = QColorDialog.getColor(QColor(self._current_bg), self, "Select Background Color")
        if color.isValid():
            self._apply_theme(color.name().upper(), self._current_accent)

    def _pick_custom_accent(self) -> None:
        color = QColorDialog.getColor(QColor(self._current_accent), self, "Select Accent Color")
        if color.isValid():
            self._apply_theme(self._current_bg, color.name().upper())

    def set_theme_display(self, bg_hex: str, accent_hex: str) -> None:
        self._current_bg = bg_hex
        self._current_accent = accent_hex
        self.active_color_lbl.setText(f"Active: {bg_hex} (Accent {accent_hex})")

    def set_connected_state(self, connected: bool) -> None:
        self.apply_rate_btn.setEnabled(connected)
