"""Module D: Real-time PyQtGraph sensor and attitude monitoring."""

from __future__ import annotations

from collections import deque

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from models.sensor_data import IMUData
from ui.theme import PALETTE


pg.setConfigOptions(antialias=False, background=PALETTE["bg_card"], foreground=PALETTE["text_primary"])


class LiveMonitorPage(QWidget):
    """Real-time PyQtGraph telemetry charts for Attitude, Gyroscope, and Accelerometer."""

    def __init__(self, max_points: int = 300, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._max_points = max_points
        self._paused = False
        self._dirty = False
        self._sample_idx = 0

        self._x_buf: deque[int] = deque(maxlen=max_points)
        self._roll: deque[float] = deque(maxlen=max_points)
        self._pitch: deque[float] = deque(maxlen=max_points)
        self._yaw_rate: deque[float] = deque(maxlen=max_points)

        self._gx: deque[float] = deque(maxlen=max_points)
        self._gy: deque[float] = deque(maxlen=max_points)
        self._gz: deque[float] = deque(maxlen=max_points)

        self._ax: deque[float] = deque(maxlen=max_points)
        self._ay: deque[float] = deque(maxlen=max_points)
        self._az: deque[float] = deque(maxlen=max_points)

        self._build_ui()

        # Throttle chart repaints to ~15 FPS and only when visible so Qt UI never freezes
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(66)
        self._render_timer.timeout.connect(self._flush_plots)
        self._render_timer.start()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Live Sensor Monitor")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch()

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self._pause)
        self.resume_btn = QPushButton("Resume")
        self.resume_btn.setObjectName("PrimaryButton")
        self.resume_btn.setEnabled(False)
        self.resume_btn.clicked.connect(self._resume)
        self.clear_btn = QPushButton("Clear Graphs")
        self.clear_btn.clicked.connect(self.clear_graphs)

        header.addWidget(self.pause_btn)
        header.addWidget(self.resume_btn)
        header.addWidget(self.clear_btn)
        root.addLayout(header)

        # 1. Attitude Plot
        self.att_plot = self._create_plot("Attitude (Roll / Pitch deg, Yaw Rate deg/s)")
        self.c_roll = self.att_plot.plot(pen=pg.mkPen("#38BDF8", width=2), name="Roll (deg)")
        self.c_pitch = self.att_plot.plot(pen=pg.mkPen("#10B981", width=2), name="Pitch (deg)")
        self.c_yaw = self.att_plot.plot(pen=pg.mkPen("#F59E0B", width=2), name="Yaw Rate (deg/s)")
        root.addWidget(self.att_plot, 1)

        # 2. Gyroscope Plot
        self.gyro_plot = self._create_plot("Gyroscope (deg/s)")
        self.c_gx = self.gyro_plot.plot(pen=pg.mkPen("#F43F5E", width=1.8), name="Gyro X")
        self.c_gy = self.gyro_plot.plot(pen=pg.mkPen("#A855F7", width=1.8), name="Gyro Y")
        self.c_gz = self.gyro_plot.plot(pen=pg.mkPen("#38BDF8", width=1.8), name="Gyro Z")
        root.addWidget(self.gyro_plot, 1)

        # 3. Accelerometer Plot
        self.accel_plot = self._create_plot("Accelerometer (g)")
        self.c_ax = self.accel_plot.plot(pen=pg.mkPen("#FB923C", width=1.8), name="Accel X")
        self.c_ay = self.accel_plot.plot(pen=pg.mkPen("#34D399", width=1.8), name="Accel Y")
        self.c_az = self.accel_plot.plot(pen=pg.mkPen("#60A5FA", width=1.8), name="Accel Z")
        root.addWidget(self.accel_plot, 1)

    @staticmethod
    def _create_plot(title: str) -> pg.PlotWidget:
        pw = pg.PlotWidget(title=title)
        pw.showGrid(x=True, y=True, alpha=0.22)
        pw.addLegend(offset=(10, 10))
        pw.setMouseEnabled(x=False, y=True)
        pw.setClipToView(True)
        return pw

    def _pause(self) -> None:
        self._paused = True
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(True)

    def _resume(self) -> None:
        self._paused = False
        self.pause_btn.setEnabled(True)
        self.resume_btn.setEnabled(False)
        self._dirty = True

    def clear_graphs(self) -> None:
        self._sample_idx = 0
        self._dirty = False
        for buf in (
            self._x_buf, self._roll, self._pitch, self._yaw_rate,
            self._gx, self._gy, self._gz, self._ax, self._ay, self._az,
        ):
            buf.clear()
        for curve in (
            self.c_roll, self.c_pitch, self.c_yaw,
            self.c_gx, self.c_gy, self.c_gz,
            self.c_ax, self.c_ay, self.c_az,
        ):
            curve.setData([], [])

    def update_imu(self, imu: IMUData) -> None:
        if self._paused:
            return
        self._sample_idx += 1
        self._x_buf.append(self._sample_idx)
        self._roll.append(imu.roll)
        self._pitch.append(imu.pitch)
        self._yaw_rate.append(imu.yaw_rate)
        self._gx.append(imu.gx)
        self._gy.append(imu.gy)
        self._gz.append(imu.gz)
        self._ax.append(imu.ax)
        self._ay.append(imu.ay)
        self._az.append(imu.az)
        self._dirty = True

    def _flush_plots(self) -> None:
        if not self._dirty or self._paused or not self.isVisible() or not self._x_buf:
            return
        self._dirty = False
        x = np.asarray(self._x_buf)
        self.c_roll.setData(x, np.asarray(self._roll), skipFiniteCheck=True)
        self.c_pitch.setData(x, np.asarray(self._pitch), skipFiniteCheck=True)
        self.c_yaw.setData(x, np.asarray(self._yaw_rate), skipFiniteCheck=True)
        self.c_gx.setData(x, np.asarray(self._gx), skipFiniteCheck=True)
        self.c_gy.setData(x, np.asarray(self._gy), skipFiniteCheck=True)
        self.c_gz.setData(x, np.asarray(self._gz), skipFiniteCheck=True)
        self.c_ax.setData(x, np.asarray(self._ax), skipFiniteCheck=True)
        self.c_ay.setData(x, np.asarray(self._ay), skipFiniteCheck=True)
        self.c_az.setData(x, np.asarray(self._az), skipFiniteCheck=True)
