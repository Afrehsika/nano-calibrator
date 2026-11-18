"""Sensor, attitude, calibration, and system status data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IMUData:
    """Live MPU6050 sensor readings and complementary/Kalman attitude estimates."""

    ax: float = 0.0
    ay: float = 0.0
    az: float = 1.0
    gx: float = 0.0
    gy: float = 0.0
    gz: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw_rate: float = 0.0
    temperature_c: float = 0.0
    mpu_connected: bool = False
    gyro_calibrated: bool = False
    accel_calibrated: bool = False
    timestamp_ms: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IMUData":
        return cls(
            ax=float(data.get("ax", 0.0)),
            ay=float(data.get("ay", 0.0)),
            az=float(data.get("az", 1.0)),
            gx=float(data.get("gx", 0.0)),
            gy=float(data.get("gy", 0.0)),
            gz=float(data.get("gz", 0.0)),
            roll=float(data.get("roll", 0.0)),
            pitch=float(data.get("pitch", 0.0)),
            yaw_rate=float(data.get("yaw_rate", data.get("gz", 0.0))),
            temperature_c=float(data.get("temp", 0.0)),
            mpu_connected=bool(data.get("mpu", False)),
            gyro_calibrated=bool(data.get("gcal", False)),
            accel_calibrated=bool(data.get("acal", False)),
            timestamp_ms=int(data.get("ts", 0)),
        )


@dataclass
class SystemStatus:
    """High-level flight controller health and mode state."""

    armed: bool = False
    flight_mode: str = "DISARMED"
    rx_connected: bool = False
    mpu_connected: bool = False
    battery_v: float | None = None
    loop_hz: int = 0
    free_ram_bytes: int = 0
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SystemStatus":
        bat = data.get("bat_v")
        return cls(
            armed=bool(data.get("armed", False)),
            flight_mode=str(data.get("mode", "DISARMED")),
            rx_connected=bool(data.get("rx", False)),
            mpu_connected=bool(data.get("mpu", False)),
            battery_v=float(bat) if bat is not None else None,
            loop_hz=int(data.get("hz", 0)),
            free_ram_bytes=int(data.get("ram", 0)),
            warnings=list(data.get("warn", [])),
        )


@dataclass
class CalibrationProgress:
    """Progress update during gyro or accelerometer calibration."""

    target: str  # "gyro" or "accel"
    percent: int = 0
    stage: str = "idle"  # "idle", "checking_stationary", "sampling", "done", "error"
    message: str = ""
    offsets: dict[str, float] = field(default_factory=dict)

