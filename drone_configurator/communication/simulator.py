"""Virtual Arduino Nano (ATmega328P) Flight Controller simulator for offline testing."""

from __future__ import annotations

import json
import math
import time
from typing import Any

from models.motor_config import MotorConfig
from models.pid_config import PIDConfig
from models.radio_data import RadioConfig


class VirtualFlightController:
    """In-memory flight controller responding to the exact JSON serial protocol."""

    def __init__(self) -> None:
        self._start_time = time.monotonic()
        self._stream_enabled = True
        self._stream_rate_hz = 20
        self._last_telemetry = 0.0
        self._pid = PIDConfig.defaults()
        self._radio_cfg = RadioConfig()
        self._motor_cfg = MotorConfig()
        self._armed = False
        self._test_motor: int | None = None
        self._test_pwm: int = 1000
        self._test_expires_at: float = 0.0
        self._cal_target: str | None = None
        self._cal_start_time: float = 0.0
        self._cal_last_pct: int = -1
        self._gyro_cal = True
        self._accel_cal = True

    def handle_command(self, raw_bytes: bytes) -> list[str]:
        """Process an incoming JSON command frame and return response JSON lines."""
        text = raw_bytes.decode("ascii", errors="replace").strip()
        if not text:
            return []
        try:
            req = json.loads(text)
        except json.JSONDecodeError:
            return [json.dumps({"type": "err", "id": None, "code": "BAD_JSON", "msg": "Invalid JSON"})]

        req_id = req.get("id")
        cmd = req.get("cmd", "")
        data: dict[str, Any] = req.get("data") or {}

        if cmd == "hello":
            return [self._ack(req_id, cmd, {
                "device": "NanoFC-QuadX (Simulated)",
                "mcu": "ATmega328P",
                "fw_version": "1.0.0-sim",
                "protocol_version": "1.0",
                "layout": "Quad-X",
            })]

        if cmd == "get_config":
            return [self._ack(req_id, cmd, {
                "pid": self._pid.to_dict(),
                "radio": self._radio_cfg.to_dict(),
                "motor": self._motor_cfg.to_dict(),
            })]

        if cmd == "set_pid":
            candidate = PIDConfig.from_dict(data)
            errors = candidate.validate()
            if errors:
                return [self._err(req_id, cmd, "INVALID_PID", errors[0])]
            self._pid = candidate
            return [self._ack(req_id, cmd, {"pid": self._pid.to_dict()})]

        if cmd == "reset_pid":
            self._pid = PIDConfig.defaults()
            return [self._ack(req_id, cmd, {"pid": self._pid.to_dict()})]

        if cmd == "save_eeprom":
            return [self._ack(req_id, cmd, {"saved": True})]

        if cmd == "set_radio_cfg":
            candidate = RadioConfig.from_dict(data)
            errors = candidate.validate()
            if errors:
                return [self._err(req_id, cmd, "INVALID_RADIO", errors[0])]
            self._radio_cfg = candidate
            return [self._ack(req_id, cmd, {"radio": self._radio_cfg.to_dict()})]

        if cmd == "set_motor_cfg":
            candidate = MotorConfig.from_dict(data)
            errors = candidate.validate()
            if errors:
                return [self._err(req_id, cmd, "INVALID_MOTOR", errors[0])]
            self._motor_cfg = candidate
            return [self._ack(req_id, cmd, {"motor": self._motor_cfg.to_dict()})]

        if cmd == "cal_start":
            target = data.get("target", "gyro")
            if target not in ("gyro", "accel"):
                return [self._err(req_id, cmd, "BAD_TARGET", "Calibration target must be gyro or accel")]
            if self._armed:
                return [self._err(req_id, cmd, "ARMED", "Disarm before calibrating")]
            self._cal_target = target
            self._cal_start_time = time.monotonic()
            self._cal_last_pct = -1
            return [self._ack(req_id, cmd, {"target": target, "started": True})]

        if cmd == "motor_test":
            if self._armed:
                return [self._err(req_id, cmd, "ARMED", "Cannot test motors while armed")]
            if not data.get("confirm", False):
                return [self._err(req_id, cmd, "NO_CONFIRM", "Explicit confirmation required")]
            motor = int(data.get("motor", 0))
            pwm = int(data.get("pwm", 1000))
            if motor not in (1, 2, 3, 4):
                return [self._err(req_id, cmd, "BAD_MOTOR", "Motor must be 1..4")]
            if pwm < self._motor_cfg.min_us or pwm > self._motor_cfg.test_max_us:
                return [self._err(req_id, cmd, "PWM_LIMIT", f"PWM capped at {self._motor_cfg.test_max_us} us")]
            self._test_motor = motor
            self._test_pwm = pwm
            self._test_expires_at = time.monotonic() + 2.5
            return [self._ack(req_id, cmd, {"motor": motor, "pwm": pwm})]

        if cmd == "motor_stop":
            self._test_motor = None
            self._test_pwm = self._motor_cfg.min_us
            return [self._ack(req_id, cmd, {"stopped": True})]

        if cmd == "set_stream":
            self._stream_enabled = bool(data.get("enabled", True))
            rate = int(data.get("rate_hz", 20))
            self._stream_rate_hz = max(5, min(50, rate))
            return [self._ack(req_id, cmd, {"enabled": self._stream_enabled, "rate_hz": self._stream_rate_hz})]

        return [self._err(req_id, cmd, "UNKNOWN_CMD", f"Unknown command: {cmd}")]

    def poll_periodic(self) -> list[str]:
        """Generate periodic telemetry and calibration progress messages."""
        now = time.monotonic()
        lines: list[str] = []

        if self._test_motor is not None and now > self._test_expires_at:
            self._test_motor = None
            self._test_pwm = self._motor_cfg.min_us

        if self._cal_target is not None:
            elapsed = now - self._cal_start_time
            pct = min(100, int((elapsed / 1.8) * 100))
            if pct >= self._cal_last_pct + 20 or pct == 100:
                self._cal_last_pct = pct
                stage = "done" if pct == 100 else ("checking_stationary" if pct < 20 else "sampling")
                msg = (
                    f"{self._cal_target.capitalize()} calibration complete"
                    if pct == 100
                    else f"Sampling {self._cal_target} offsets ({pct}%)"
                )
                lines.append(json.dumps({
                    "type": "cal_progress",
                    "target": self._cal_target,
                    "pct": pct,
                    "stage": stage,
                    "msg": msg,
                }))
                if pct == 100:
                    if self._cal_target == "gyro":
                        self._gyro_cal = True
                    else:
                        self._accel_cal = True
                    self._cal_target = None

        if self._stream_enabled and (now - self._last_telemetry) >= (1.0 / self._stream_rate_hz):
            self._last_telemetry = now
            t = now - self._start_time
            roll = 2.2 * math.sin(t * 1.1)
            pitch = 1.6 * math.cos(t * 0.8)
            gx = 2.5 * math.cos(t * 1.1)
            gy = -1.8 * math.sin(t * 0.8)
            gz = 0.6 * math.sin(t * 0.4)
            ax = math.sin(math.radians(roll)) * 0.98
            ay = math.sin(math.radians(pitch)) * 0.98
            az = math.sqrt(max(0.0, 1.0 - ax * ax - ay * ay))

            motors = [self._motor_cfg.min_us] * 4
            if self._test_motor is not None:
                motors[self._test_motor - 1] = self._test_pwm

            roll_us = int(1500 + 80 * math.sin(t * 0.6))
            pitch_us = int(1500 + 60 * math.cos(t * 0.5))

            lines.append(json.dumps({
                "type": "telemetry",
                "status": {
                    "armed": self._armed,
                    "mode": "STABILIZE" if self._pid.angle_loop_enabled else "ACRO",
                    "rx": True,
                    "mpu": True,
                    "bat_v": round(11.4 + 0.05 * math.sin(t * 0.2), 2),
                    "hz": 250,
                    "ram": 642,
                    "warn": [],
                },
                "imu": {
                    "ax": round(ax, 3),
                    "ay": round(ay, 3),
                    "az": round(az, 3),
                    "gx": round(gx, 2),
                    "gy": round(gy, 2),
                    "gz": round(gz, 2),
                    "roll": round(roll, 2),
                    "pitch": round(pitch, 2),
                    "yaw_rate": round(gz, 2),
                    "temp": 29.4,
                    "mpu": True,
                    "gcal": self._gyro_cal,
                    "acal": self._accel_cal,
                    "ts": int(t * 1000),
                },
                "rx": {
                    "roll": roll_us,
                    "pitch": pitch_us,
                    "thr": 1000,
                    "yaw": 1500,
                    "rx": True,
                    "age_ms": 12,
                    "loss": 0.0,
                },
                "motors": {
                    "m": motors,
                    "test": self._test_motor is not None,
                    "test_m": self._test_motor,
                },
            }))
        return lines

    @staticmethod
    def _ack(req_id: int | None, cmd: str, data: dict[str, Any]) -> str:
        return json.dumps({"type": "ack", "id": req_id, "cmd": cmd, "ok": True, "data": data})

    @staticmethod
    def _err(req_id: int | None, cmd: str, code: str, msg: str) -> str:
        return json.dumps({"type": "err", "id": req_id, "cmd": cmd, "ok": False, "code": code, "msg": msg})

