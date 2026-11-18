"""MPU6050 stationary detection and calibration state helper."""

from __future__ import annotations

from collections import deque

import numpy as np

from models.sensor_data import IMUData


class CalibrationService:
    """Monitors live IMU samples to verify the quadcopter is stationary before calibration."""

    def __init__(self, window_size: int = 15) -> None:
        self._samples: deque[IMUData] = deque(maxlen=window_size)

    def push_sample(self, imu: IMUData) -> None:
        if imu.mpu_connected:
            self._samples.append(imu)

    def clear(self) -> None:
        self._samples.clear()

    def is_stationary(self) -> tuple[bool, str]:
        """Return (is_stationary, human_status_message)."""
        if len(self._samples) < 8:
            return False, "Collecting IMU samples to verify stability..."

        gyro_mag = np.array(
            [np.sqrt(s.gx**2 + s.gy**2 + s.gz**2) for s in self._samples],
            dtype=float,
        )
        accel_mag = np.array(
            [np.sqrt(s.ax**2 + s.ay**2 + s.az**2) for s in self._samples],
            dtype=float,
        )

        max_gyro = float(np.max(gyro_mag))
        accel_std = float(np.std(accel_mag))

        if max_gyro > 3.0:
            return False, f"Motion detected (gyro {max_gyro:.1f} deg/s > 3.0 deg/s). Keep drone still."
        if accel_std > 0.04:
            return False, f"Vibration detected (accel std {accel_std:.3f} g). Place on flat surface."

        return True, f"Stationary (gyro {max_gyro:.2f} deg/s, accel std {accel_std:.3f} g). Ready."

