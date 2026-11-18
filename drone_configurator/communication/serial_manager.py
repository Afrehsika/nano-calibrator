"""Background serial communication manager with handshake, timeouts, and disconnect detection."""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass
from typing import Any

import serial
import serial.tools.list_ports
from PySide6.QtCore import QObject, QThread, Signal

from communication.protocol import (
    CommandType,
    MessageType,
    ProtocolError,
    ProtocolMessage,
    build_command,
    parse_line,
)
from communication.simulator import VirtualFlightController
from models.motor_config import MotorOutputs
from models.radio_data import RadioData
from models.sensor_data import CalibrationProgress, IMUData, SystemStatus


SIMULATOR_PORT = "SIMULATOR (Virtual Nano FC)"


@dataclass
class _PendingRequest:
    req_id: int
    cmd: str
    sent_at: float
    timeout_s: float


def list_available_ports() -> list[tuple[str, str]]:
    """Return list of (port_device, human_label) including the virtual simulator."""
    ports: list[tuple[str, str]] = []
    for p in serial.tools.list_ports.comports():
        desc = p.description or "USB Serial Device"
        ports.append((p.device, f"{p.device} - {desc}"))
    ports.append((SIMULATOR_PORT, SIMULATOR_PORT))
    return ports


class _SerialWorker(QThread):
    """Dedicated I/O thread so serial reads/writes never block the Qt UI."""

    connected_signal = Signal(dict)
    disconnected_signal = Signal()
    connection_lost_signal = Signal(str)
    command_ack_signal = Signal(str, dict)
    command_err_signal = Signal(str, str)
    telemetry_signal = Signal(object, object, object, object)
    cal_progress_signal = Signal(object)
    log_signal = Signal(str, str)

    def __init__(self, port: str, baudrate: int, cmd_timeout_s: float = 2.5) -> None:
        super().__init__()
        self._port = port
        self._baudrate = baudrate
        self._cmd_timeout_s = cmd_timeout_s
        self._running = False
        self._tx_queue: queue.Queue[tuple[int, str, dict[str, Any] | None, float]] = queue.Queue()
        self._pending: dict[int, _PendingRequest] = {}
        self._serial: serial.Serial | None = None
        self._sim: VirtualFlightController | None = None
        self._handshake_done = False

    def enqueue_command(self, req_id: int, cmd: str, payload: dict[str, Any] | None, timeout_s: float) -> None:
        self._tx_queue.put((req_id, cmd, payload, timeout_s))

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        self._running = True
        use_sim = self._port == SIMULATOR_PORT

        try:
            if use_sim:
                self._sim = VirtualFlightController()
                self.log_signal.emit("INFO", "Connected to Virtual Nano FC simulator.")
            else:
                self._serial = serial.Serial(
                    port=self._port,
                    baudrate=self._baudrate,
                    timeout=0.05,
                    write_timeout=1.0,
                )
                # Classic Arduino Nano (ATmega328P) resets on DTR open; wait for bootloader.
                self.log_signal.emit("INFO", f"Opened {self._port} @ {self._baudrate} baud. Waiting for Nano boot...")
                time.sleep(2.2)
                self._serial.reset_input_buffer()

            if not self._perform_handshake():
                self.connection_lost_signal.emit(
                    f"Handshake timed out on {self._port} @ {self._baudrate} baud: "
                    "device did not respond to 'hello'.\n\n"
                    "Check:\n"
                    "1. Flash firmware/nano_fc_receiver/nano_fc_receiver.ino to the Nano.\n"
                    "2. Match baud rate (115200) and close Arduino Serial Monitor.\n"
                    "3. Check Dashboard Event Log for any raw serial output."
                )
                return

            rx_buffer = bytearray()
            while self._running:
                self._drain_tx_queue()
                self._check_timeouts()

                if self._sim is not None:
                    for line in self._sim.poll_periodic():
                        self._handle_line(line)
                    time.sleep(0.02)
                elif self._serial is not None:
                    try:
                        waiting = self._serial.in_waiting
                        chunk = self._serial.read(max(1, waiting))
                    except (serial.SerialException, OSError) as exc:
                        self.connection_lost_signal.emit(f"Serial read error: {exc}")
                        break

                    if chunk:
                        rx_buffer.extend(chunk)
                        while b"\n" in rx_buffer:
                            idx = rx_buffer.index(b"\n")
                            raw_line = bytes(rx_buffer[:idx]).decode("utf-8", errors="replace")
                            del rx_buffer[: idx + 1]
                            if raw_line.strip():
                                self._handle_line(raw_line)
        except (serial.SerialException, OSError) as exc:
            self.connection_lost_signal.emit(f"Failed to open {self._port}: {exc}")
        finally:
            if self._serial is not None and self._serial.is_open:
                try:
                    # Safety: ensure motor test stops if user disconnects unexpectedly
                    self._serial.write(build_command(CommandType.MOTOR_STOP, 9999))
                    self._serial.close()
                except Exception:
                    pass
            self._serial = None
            self._sim = None
            self.disconnected_signal.emit()

    def _perform_handshake(self) -> bool:
        """Send 'hello' and wait up to 3 seconds (with 2 attempts) for valid ACK."""
        for attempt in range(2):
            if not self._running:
                return False
            req_id = 100 + attempt
            frame = build_command(CommandType.HELLO, req_id)
            self._write_bytes(b"\n" + frame if self._serial is not None else frame)
            deadline = time.monotonic() + 1.5
            rx_buf = bytearray()
            while time.monotonic() < deadline and self._running:
                if self._sim is not None:
                    for line in self._sim.handle_command(frame):
                        msg = self._safe_parse(line)
                        if msg and msg.msg_type == MessageType.ACK and msg.req_id == req_id:
                            self._handshake_done = True
                            self.connected_signal.emit(msg.data)
                            return True
                elif self._serial is not None:
                    chunk = self._serial.read(max(1, self._serial.in_waiting))
                    if chunk:
                        rx_buf.extend(chunk)
                        while b"\n" in rx_buf:
                            idx = rx_buf.index(b"\n")
                            line = bytes(rx_buf[:idx]).decode("utf-8", errors="replace")
                            del rx_buf[: idx + 1]
                            msg = self._safe_parse(line)
                            if msg and msg.msg_type == MessageType.ACK and msg.req_id == req_id:
                                self._handshake_done = True
                                self.connected_signal.emit(msg.data)
                                return True
            if rx_buf:
                self.log_signal.emit("WARN", f"Unparsed handshake bytes: {rx_buf.decode('utf-8', errors='replace')[:120]}")
        return False

    def _drain_tx_queue(self) -> None:
        while not self._tx_queue.empty():
            req_id, cmd, payload, timeout_s = self._tx_queue.get_nowait()
            frame = build_command(cmd, req_id, payload)
            self._pending[req_id] = _PendingRequest(req_id, cmd, time.monotonic(), timeout_s)
            if self._sim is not None:
                for line in self._sim.handle_command(frame):
                    self._handle_line(line)
            else:
                self._write_bytes(frame)

    def _write_bytes(self, frame: bytes) -> None:
        if self._serial is not None and self._serial.is_open:
            # Chunk writes in 32-byte slices so ATmega328P's 64-byte UART RX buffer never overflows
            chunk_size = 32
            for i in range(0, len(frame), chunk_size):
                self._serial.write(frame[i : i + chunk_size])
                if i + chunk_size < len(frame):
                    time.sleep(0.005)

    def _check_timeouts(self) -> None:
        now = time.monotonic()
        expired = [
            req for req in self._pending.values()
            if (now - req.sent_at) > req.timeout_s
        ]
        for req in expired:
            self._pending.pop(req.req_id, None)
            self.command_err_signal.emit(req.cmd, f"Command '{req.cmd}' timed out after {req.timeout_s:.1f}s")

    def _safe_parse(self, line: str) -> ProtocolMessage | None:
        try:
            return parse_line(line)
        except ProtocolError as exc:
            self.log_signal.emit("WARN", f"Ignored invalid frame: {exc}")
            return None

    def _handle_line(self, line: str) -> None:
        msg = self._safe_parse(line)
        if msg is None:
            return

        if msg.msg_type == MessageType.ACK:
            if msg.req_id is not None:
                self._pending.pop(msg.req_id, None)
            self.command_ack_signal.emit(msg.cmd or "", msg.data)
            return

        if msg.msg_type == MessageType.ERR:
            if msg.req_id is not None:
                self._pending.pop(msg.req_id, None)
            self.command_err_signal.emit(msg.cmd or "", f"[{msg.error_code}] {msg.error_msg}")
            return

        if msg.msg_type == MessageType.CAL_PROGRESS:
            raw = msg.data
            progress = CalibrationProgress(
                target=str(raw.get("target", "gyro")),
                percent=int(raw.get("pct", 0)),
                stage=str(raw.get("stage", "sampling")),
                message=str(raw.get("msg", "")),
                offsets=raw.get("offsets", {}),
            )
            self.cal_progress_signal.emit(progress)
            return

        if msg.msg_type == MessageType.TELEMETRY:
            raw = msg.data
            status = SystemStatus.from_dict(raw.get("status", {}))
            imu = IMUData.from_dict(raw.get("imu", {}))
            radio = RadioData.from_dict(raw.get("rx", {}))
            motors = MotorOutputs.from_dict(raw.get("motors", {}))
            self.telemetry_signal.emit(status, imu, radio, motors)


class SerialManager(QObject):
    """High-level Qt facade managing the background serial worker and request IDs."""

    connected = Signal(dict)
    disconnected = Signal()
    connection_lost = Signal(str)
    command_succeeded = Signal(str, dict)
    command_failed = Signal(str, str)
    telemetry_received = Signal(object, object, object, object)
    calibration_progress = Signal(object)
    log_message = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker: _SerialWorker | None = None
        self._is_connected = False
        self._next_req_id = 1000
        self._default_timeout_s = 2.5

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def set_command_timeout(self, timeout_s: float) -> None:
        self._default_timeout_s = max(0.5, min(10.0, float(timeout_s)))

    def connect_port(self, port: str, baudrate: int = 115200) -> None:
        if self._worker is not None:
            self.disconnect_port()
        self._worker = _SerialWorker(port, baudrate, self._default_timeout_s)
        self._worker.connected_signal.connect(self._on_connected)
        self._worker.disconnected_signal.connect(self._on_disconnected)
        self._worker.connection_lost_signal.connect(self._on_connection_lost)
        self._worker.command_ack_signal.connect(self._on_command_ack_internal)
        self._worker.command_ack_signal.connect(self.command_succeeded)
        self._worker.command_err_signal.connect(self.command_failed)
        self._worker.telemetry_signal.connect(self.telemetry_received)
        self._worker.cal_progress_signal.connect(self.calibration_progress)
        self._worker.log_signal.connect(self.log_message)
        self._worker.start()

    def disconnect_port(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(2500)
            self._worker.deleteLater()
            self._worker = None
        self._is_connected = False

    def send_command(
        self,
        cmd: CommandType | str,
        payload: dict[str, Any] | None = None,
        timeout_s: float | None = None,
    ) -> bool:
        if not self._is_connected or self._worker is None:
            self.command_failed.emit(
                cmd.value if isinstance(cmd, CommandType) else str(cmd),
                "Not connected to flight controller.",
            )
            return False
        self._next_req_id += 1
        cmd_str = cmd.value if isinstance(cmd, CommandType) else str(cmd)
        self._worker.enqueue_command(
            self._next_req_id,
            cmd_str,
            payload,
            timeout_s if timeout_s is not None else self._default_timeout_s,
        )
        return True

    def _on_connected(self, info: dict[str, Any]) -> None:
        self._is_connected = True
        self.connected.emit(info)
        # Fetch current FC configuration first; enable telemetry stream once get_config ACKs
        self.send_command(CommandType.GET_CONFIG)

    def _on_command_ack_internal(self, cmd: str, _data: dict[str, Any]) -> None:
        if cmd == CommandType.GET_CONFIG.value and self._is_connected:
            self.send_command(CommandType.SET_STREAM, {"enabled": True, "rate_hz": 20})

    def _on_disconnected(self) -> None:
        self._is_connected = False
        self.disconnected.emit()

    def _on_connection_lost(self, reason: str) -> None:
        self._is_connected = False
        self.connection_lost.emit(reason)

