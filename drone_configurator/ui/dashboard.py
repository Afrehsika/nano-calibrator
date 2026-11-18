"""Module A: Dashboard view for connection, live attitude, and system health."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from communication.serial_manager import list_available_ports
from models.sensor_data import IMUData, SystemStatus
from ui.theme import PALETTE
from ui.widgets import AttitudeHorizonWidget, CardFrame, MetricTile, StatusPill


class DashboardPage(QWidget):
    """Main overview dashboard for serial connection and flight controller health."""

    connect_requested = Signal(str, int)
    disconnect_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.refresh_ports()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        # Connection Bar Card
        conn_card = CardFrame("Flight Controller Connection", "Connect via USB serial to the receiver Arduino Nano (ATmega328P).")
        conn_row = QHBoxLayout()
        conn_row.setSpacing(10)

        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(260)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_ports)

        self.baud_combo = QComboBox()
        for baud in (115200, 57600, 250000, 38400):
            self.baud_combo.addItem(f"{baud} baud", baud)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("PrimaryButton")
        self.connect_btn.clicked.connect(self._on_connect_clicked)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.clicked.connect(self.disconnect_requested.emit)

        conn_row.addWidget(QLabel("Port:"))
        conn_row.addWidget(self.port_combo, 1)
        conn_row.addWidget(self.refresh_btn)
        conn_row.addWidget(QLabel("Baud:"))
        conn_row.addWidget(self.baud_combo)
        conn_row.addWidget(self.connect_btn)
        conn_row.addWidget(self.disconnect_btn)
        conn_card.body_layout.addLayout(conn_row)
        root.addWidget(conn_card)

        # Subsystem Status Pills
        status_card = CardFrame("Subsystem Status")
        pill_grid = QGridLayout()
        pill_grid.setSpacing(12)

        self.fc_pill = StatusPill("DISCONNECTED", "muted")
        self.rx_pill = StatusPill("RX OFFLINE", "muted")
        self.mpu_pill = StatusPill("MPU6050 OFFLINE", "muted")
        self.mode_pill = StatusPill("UNKNOWN", "muted")

        for col, (lbl_text, pill) in enumerate([
            ("Flight Controller", self.fc_pill),
            ("nRF24L01 Receiver", self.rx_pill),
            ("MPU6050 IMU", self.mpu_pill),
            ("Flight Mode", self.mode_pill),
        ]):
            box = QVBoxLayout()
            lbl = QLabel(lbl_text)
            lbl.setObjectName("MutedLabel")
            box.addWidget(lbl)
            box.addWidget(pill)
            pill_grid.addLayout(box, 0, col)

        status_card.body_layout.addLayout(pill_grid)
        root.addWidget(status_card)

        # Middle row: Telemetry Metrics + Artificial Horizon
        mid_row = QHBoxLayout()
        mid_row.setSpacing(16)

        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(12)
        self.roll_tile = MetricTile("Roll", "deg")
        self.pitch_tile = MetricTile("Pitch", "deg")
        self.yaw_tile = MetricTile("Yaw Rate", "deg/s")
        self.bat_tile = MetricTile("Battery", "V")
        self.hz_tile = MetricTile("Loop Rate", "Hz")
        self.ram_tile = MetricTile("Free SRAM", "B")

        metrics_grid.addWidget(self.roll_tile, 0, 0)
        metrics_grid.addWidget(self.pitch_tile, 0, 1)
        metrics_grid.addWidget(self.yaw_tile, 0, 2)
        metrics_grid.addWidget(self.bat_tile, 1, 0)
        metrics_grid.addWidget(self.hz_tile, 1, 1)
        metrics_grid.addWidget(self.ram_tile, 1, 2)

        metrics_wrap = QWidget()
        metrics_wrap.setLayout(metrics_grid)
        mid_row.addWidget(metrics_wrap, 2)

        horizon_card = CardFrame("Live Attitude")
        self.horizon = AttitudeHorizonWidget()
        horizon_card.body_layout.addWidget(self.horizon)
        self.device_label = QLabel("Device: Not connected")
        self.device_label.setObjectName("MutedLabel")
        self.device_label.setWordWrap(True)
        horizon_card.body_layout.addWidget(self.device_label)
        mid_row.addWidget(horizon_card, 1)

        root.addLayout(mid_row)

        # Warnings & Event Log
        log_card = CardFrame("System Warnings & Event Log")
        self.warnings_label = QLabel("No active warnings.")
        self.warnings_label.setStyleSheet(f"color: {PALETTE['success']}; font-weight: 500;")
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(140)
        log_card.body_layout.addWidget(self.warnings_label)
        log_card.body_layout.addWidget(self.log_box)
        root.addWidget(log_card)

    def refresh_ports(self) -> None:
        current = self.port_combo.currentData()
        self.port_combo.clear()
        for dev, label in list_available_ports():
            self.port_combo.addItem(label, dev)
        if current:
            idx = self.port_combo.findData(current)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)

    def _on_connect_clicked(self) -> None:
        port = self.port_combo.currentData()
        baud = int(self.baud_combo.currentData())
        if port:
            self.connect_btn.setEnabled(False)
            self.fc_pill.set_state("CONNECTING...", "accent")
            self.connect_requested.emit(port, baud)

    def set_connected_state(self, connected: bool, info: dict | None = None) -> None:
        self.connect_btn.setEnabled(not connected)
        self.disconnect_btn.setEnabled(connected)
        self.port_combo.setEnabled(not connected)
        self.baud_combo.setEnabled(not connected)
        if connected:
            self.fc_pill.set_state("CONNECTED", "success")
            if info:
                self.device_label.setText(
                    f"Device: {info.get('device', 'NanoFC')} | "
                    f"MCU: {info.get('mcu', 'ATmega328P')} | "
                    f"FW: {info.get('fw_version', '?')} ({info.get('layout', 'Quad-X')})"
                )
        else:
            self.fc_pill.set_state("DISCONNECTED", "muted")
            self.rx_pill.set_state("RX OFFLINE", "muted")
            self.mpu_pill.set_state("MPU6050 OFFLINE", "muted")
            self.mode_pill.set_state("UNKNOWN", "muted")
            self.device_label.setText("Device: Not connected")
            for tile in (self.roll_tile, self.pitch_tile, self.yaw_tile, self.bat_tile, self.hz_tile, self.ram_tile):
                tile.set_value("--")
            self.horizon.set_attitude(0.0, 0.0)

    def update_telemetry(self, status: SystemStatus, imu: IMUData) -> None:
        self.rx_pill.set_state("RX OK" if status.rx_connected else "RX TIMEOUT", "success" if status.rx_connected else "warning")
        self.mpu_pill.set_state("MPU6050 OK" if status.mpu_connected else "MPU6050 ERROR", "success" if status.mpu_connected else "danger")

        mode_tone = "danger" if status.armed else ("accent" if status.flight_mode in ("STABILIZE", "ACRO") else "muted")
        mode_text = f"{status.flight_mode} ({'ARMED' if status.armed else 'DISARMED'})"
        self.mode_pill.set_state(mode_text, mode_tone)

        self.roll_tile.set_value(f"{imu.roll:+.1f}")
        self.pitch_tile.set_value(f"{imu.pitch:+.1f}")
        self.yaw_tile.set_value(f"{imu.yaw_rate:+.1f}")
        self.bat_tile.set_value(f"{status.battery_v:.2f}" if status.battery_v is not None else "N/A")
        self.hz_tile.set_value(str(status.loop_hz) if status.loop_hz else "--")
        self.ram_tile.set_value(str(status.free_ram_bytes) if status.free_ram_bytes else "--")
        self.horizon.set_attitude(imu.roll, imu.pitch)

        if status.warnings:
            self.warnings_label.setText("Warnings: " + " | ".join(status.warnings))
            self.warnings_label.setStyleSheet(f"color: {PALETTE['warning']}; font-weight: 600;")
        else:
            self.warnings_label.setText("All monitored subsystems nominal.")
            self.warnings_label.setStyleSheet(f"color: {PALETTE['success']}; font-weight: 500;")

    def append_log(self, level: str, message: str) -> None:
        self.log_box.append(f"[{level}] {message}")

