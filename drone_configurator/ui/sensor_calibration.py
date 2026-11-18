"""Module C: MPU6050 Sensor Calibration interface."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from models.sensor_data import CalibrationProgress, IMUData
from services.calibration_service import CalibrationService
from ui.theme import PALETTE
from ui.widgets import CardFrame, MetricTile, StatusPill


class SensorCalibrationPage(QWidget):
    """MPU6050 detection, live readings, stationary verification, and calibration."""

    start_calibration_requested = Signal(str)  # "gyro" or "accel"

    def __init__(self, calibration_service: CalibrationService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cal_service = calibration_service
        self._connected = False
        self._cal_in_progress = False
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        title = QLabel("MPU6050 Sensor Calibration")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        # Detection & Calibration Status
        status_card = CardFrame("Sensor Health & Calibration State")
        pill_row = QHBoxLayout()
        pill_row.setSpacing(16)
        self.mpu_pill = StatusPill("MPU6050 NOT DETECTED", "muted")
        self.gcal_pill = StatusPill("GYRO UNCALIBRATED", "muted")
        self.acal_pill = StatusPill("ACCEL UNCALIBRATED", "muted")
        pill_row.addWidget(self.mpu_pill)
        pill_row.addWidget(self.gcal_pill)
        pill_row.addWidget(self.acal_pill)
        pill_row.addStretch()
        status_card.body_layout.addLayout(pill_row)

        self.stationary_label = QLabel("Connect to flight controller to monitor MPU6050 stability.")
        self.stationary_label.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-weight: 500;")
        status_card.body_layout.addWidget(self.stationary_label)
        root.addWidget(status_card)

        # Live Readings Grid
        readings_grid = QGridLayout()
        readings_grid.setSpacing(12)
        self.ax_tile = MetricTile("Accel X", "g")
        self.ay_tile = MetricTile("Accel Y", "g")
        self.az_tile = MetricTile("Accel Z", "g")
        self.gx_tile = MetricTile("Gyro X", "deg/s")
        self.gy_tile = MetricTile("Gyro Y", "deg/s")
        self.gz_tile = MetricTile("Gyro Z", "deg/s")
        self.roll_tile = MetricTile("Roll Est.", "deg")
        self.pitch_tile = MetricTile("Pitch Est.", "deg")
        self.temp_tile = MetricTile("IMU Temp", "C")

        for idx, tile in enumerate((
            self.ax_tile, self.ay_tile, self.az_tile,
            self.gx_tile, self.gy_tile, self.gz_tile,
            self.roll_tile, self.pitch_tile, self.temp_tile,
        )):
            readings_grid.addWidget(tile, idx // 3, idx % 3)

        readings_wrap = QWidget()
        readings_wrap.setLayout(readings_grid)
        root.addWidget(readings_wrap)

        # Calibration Controls
        cal_card = CardFrame(
            "Calibration Actions",
            "Place the quadcopter on a flat, level surface and keep it completely stationary before calibrating.",
        )
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.gyro_btn = QPushButton("Calibrate Gyroscope")
        self.gyro_btn.setObjectName("PrimaryButton")
        self.gyro_btn.setToolTip("Measures stationary gyro bias on X, Y, Z axes.")
        self.gyro_btn.clicked.connect(lambda: self.start_calibration_requested.emit("gyro"))

        self.accel_btn = QPushButton("Calibrate Accelerometer (Level)")
        self.accel_btn.setObjectName("PrimaryButton")
        self.accel_btn.setToolTip("Measures level surface accelerometer offsets (0, 0, +1g).")
        self.accel_btn.clicked.connect(lambda: self.start_calibration_requested.emit("accel"))

        btn_row.addWidget(self.gyro_btn)
        btn_row.addWidget(self.accel_btn)
        btn_row.addStretch()
        cal_card.body_layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_msg = QLabel("Idle.")
        self.progress_msg.setObjectName("MutedLabel")

        cal_card.body_layout.addWidget(self.progress_bar)
        cal_card.body_layout.addWidget(self.progress_msg)
        root.addWidget(cal_card)
        root.addStretch()

        self.set_connected_state(False)

    def set_connected_state(self, connected: bool) -> None:
        self._connected = connected
        if not connected:
            self._cal_in_progress = False
            self._cal_service.clear()
            self.mpu_pill.set_state("MPU6050 OFFLINE", "muted")
            self.gcal_pill.set_state("GYRO UNKNOWN", "muted")
            self.acal_pill.set_state("ACCEL UNKNOWN", "muted")
            self.stationary_label.setText("Connect to flight controller to monitor MPU6050 stability.")
            self.stationary_label.setStyleSheet(f"color: {PALETTE['text_secondary']};")
            self.gyro_btn.setEnabled(False)
            self.accel_btn.setEnabled(False)
            for tile in (
                self.ax_tile, self.ay_tile, self.az_tile,
                self.gx_tile, self.gy_tile, self.gz_tile,
                self.roll_tile, self.pitch_tile, self.temp_tile,
            ):
                tile.set_value("--")

    def update_imu(self, imu: IMUData) -> None:
        self._cal_service.push_sample(imu)

        if imu.mpu_connected:
            self.mpu_pill.set_state("MPU6050 DETECTED", "success")
        else:
            self.mpu_pill.set_state("MPU6050 COMM ERROR", "danger")

        self.gcal_pill.set_state("GYRO CALIBRATED" if imu.gyro_calibrated else "GYRO UNCALIBRATED",
                                 "success" if imu.gyro_calibrated else "warning")
        self.acal_pill.set_state("ACCEL CALIBRATED" if imu.accel_calibrated else "ACCEL UNCALIBRATED",
                                 "success" if imu.accel_calibrated else "warning")

        self.ax_tile.set_value(f"{imu.ax:+.3f}")
        self.ay_tile.set_value(f"{imu.ay:+.3f}")
        self.az_tile.set_value(f"{imu.az:+.3f}")
        self.gx_tile.set_value(f"{imu.gx:+.2f}")
        self.gy_tile.set_value(f"{imu.gy:+.2f}")
        self.gz_tile.set_value(f"{imu.gz:+.2f}")
        self.roll_tile.set_value(f"{imu.roll:+.1f}")
        self.pitch_tile.set_value(f"{imu.pitch:+.1f}")
        self.temp_tile.set_value(f"{imu.temperature_c:.1f}")

        stationary, msg = self._cal_service.is_stationary()
        if not imu.mpu_connected:
            self.stationary_label.setText("MPU6050 not responding on I2C (A4/A5). Check wiring.")
            self.stationary_label.setStyleSheet(f"color: {PALETTE['danger']}; font-weight: 600;")
        else:
            self.stationary_label.setText(msg)
            color = PALETTE["success"] if stationary else PALETTE["warning"]
            self.stationary_label.setStyleSheet(f"color: {color}; font-weight: 600;")

        can_cal = self._connected and imu.mpu_connected and stationary and not self._cal_in_progress
        self.gyro_btn.setEnabled(can_cal)
        self.accel_btn.setEnabled(can_cal)

    def update_progress(self, prog: CalibrationProgress) -> None:
        self.progress_bar.setValue(prog.percent)
        self.progress_msg.setText(f"[{prog.target.upper()}] {prog.message}")
        if prog.stage == "error":
            self._cal_in_progress = False
            self.progress_msg.setStyleSheet(f"color: {PALETTE['danger']}; font-weight: 600;")
        elif prog.stage == "done" or prog.percent >= 100:
            self._cal_in_progress = False
            self.progress_msg.setStyleSheet(f"color: {PALETTE['success']}; font-weight: 600;")
        else:
            self._cal_in_progress = True
            self.progress_msg.setStyleSheet(f"color: {PALETTE['accent']}; font-weight: 500;")

