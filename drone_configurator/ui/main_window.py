"""Main application window with sidebar navigation and subsystem coordination."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from communication.protocol import CommandType
from communication.serial_manager import SerialManager
from models.motor_config import MotorConfig, MotorOutputs
from models.pid_config import PIDConfig
from models.radio_data import RadioConfig, RadioData
from models.sensor_data import CalibrationProgress, IMUData, SystemStatus
from services.calibration_service import CalibrationService
from services.configuration_service import ConfigurationService, ProfileData
from ui.dashboard import DashboardPage
from ui.live_monitor import LiveMonitorPage
from ui.motor_configuration import MotorConfigurationPage
from ui.pid_tuning import PIDTuningPage
from ui.profiles import ProfilesPage
from ui.radio_configuration import RadioConfigurationPage
from ui.sensor_calibration import SensorCalibrationPage
from ui.settings import SettingsPage
from ui.theme import build_stylesheet
from ui.widgets import StatusPill


class MainWindow(QMainWindow):
    """Top-level PySide6 window hosting sidebar navigation and all 8 modules."""

    def __init__(self, profiles_dir: Path) -> None:
        super().__init__()
        self.setWindowTitle("NanoFC Quad-X Flight Controller Configurator")
        self.resize(1280, 820)
        self.setMinimumSize(1024, 680)

        self.serial_mgr = SerialManager(self)
        self.config_service = ConfigurationService(profiles_dir)
        self.calibration_service = CalibrationService()
        self._settings_path = profiles_dir.parent / "ui_settings.json"

        self._nav_buttons: list[QPushButton] = []
        self._build_ui()
        self._connect_signals()
        self._load_saved_theme()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Left Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(235)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(14, 18, 14, 16)
        sb_layout.setSpacing(4)

        brand_title = QLabel("NANO FC")
        brand_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #38BDF8; letter-spacing: 1px; padding: 0 8px;")
        brand_sub = QLabel("GROUND CONTROL v1.0")
        brand_sub.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748B; letter-spacing: 1.4px; padding: 0 8px 14px 8px;")
        sb_layout.addWidget(brand_title)
        sb_layout.addWidget(brand_sub)

        self.stack = QStackedWidget()
        self.dashboard_page = DashboardPage()
        self.pid_page = PIDTuningPage()
        self.sensors_page = SensorCalibrationPage(self.calibration_service)
        self.motors_page = MotorConfigurationPage()
        self.radio_page = RadioConfigurationPage()
        self.monitor_page = LiveMonitorPage()
        self.profiles_page = ProfilesPage(self.config_service)
        self.settings_page = SettingsPage()

        nav_groups = [
            ("FLIGHT DECK", [
                ("◈  Dashboard", self.dashboard_page),
                ("∿  Live Monitor", self.monitor_page),
            ]),
            ("TUNING & HARDWARE", [
                ("⊞  PID Tuning", self.pid_page),
                ("◎  Sensors & Cal", self.sensors_page),
                ("✦  Motor Config", self.motors_page),
                ("▤  Radio Config", self.radio_page),
            ]),
            ("SYSTEM", [
                ("◫  Profiles", self.profiles_page),
                ("⚙  Settings", self.settings_page),
            ]),
        ]

        page_idx = 0
        for section, items in nav_groups:
            sec_lbl = QLabel(section)
            sec_lbl.setObjectName("SectionLabel")
            sb_layout.addWidget(sec_lbl)
            for label, widget in items:
                self.stack.addWidget(widget)
                btn = QPushButton(label)
                btn.setObjectName("NavButton")
                btn.setProperty("active", page_idx == 0)
                idx_copy = page_idx
                btn.clicked.connect(lambda _checked=False, i=idx_copy: self._switch_page(i))
                sb_layout.addWidget(btn)
                self._nav_buttons.append(btn)
                page_idx += 1

        sb_layout.addStretch()
        ver_lbl = QLabel("ATmega328P  |  Quad-X\nJSON Protocol v1.0")
        ver_lbl.setObjectName("MutedLabel")
        ver_lbl.setStyleSheet("padding: 8px; color: #64748B; font-size: 11px;")
        sb_layout.addWidget(ver_lbl)
        outer.addWidget(sidebar)

        # Right Main Column (TopBar + Stacked Pages)
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(54)
        tb_layout = QHBoxLayout(topbar)
        tb_layout.setContentsMargins(20, 8, 20, 8)
        tb_layout.setSpacing(10)

        self.top_conn_pill = StatusPill("DISCONNECTED", "muted")
        self.top_mode_pill = StatusPill("DISARMED", "muted")
        self.top_bat_pill = StatusPill("BAT: N/A", "muted")
        self.top_status_lbl = QLabel("Ready. Select a serial port on Dashboard to connect.")
        self.top_status_lbl.setObjectName("MutedLabel")

        self.top_stop_btn = QPushButton("STOP MOTORS")
        self.top_stop_btn.setObjectName("DangerButton")
        self.top_stop_btn.setEnabled(False)
        self.top_stop_btn.setToolTip("Immediately set all 4 ESC outputs to minimum PWM")
        self.top_stop_btn.clicked.connect(lambda: self.serial_mgr.send_command(CommandType.MOTOR_STOP))

        tb_layout.addWidget(self.top_conn_pill)
        tb_layout.addWidget(self.top_mode_pill)
        tb_layout.addWidget(self.top_bat_pill)
        tb_layout.addWidget(self.top_status_lbl, 1)
        tb_layout.addWidget(self.top_stop_btn)

        right_col.addWidget(topbar)
        right_col.addWidget(self.stack, 1)
        outer.addLayout(right_col, 1)

        self.statusBar().showMessage("Disconnected")

    def _switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for idx, btn in enumerate(self._nav_buttons):
            btn.setProperty("active", idx == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _connect_signals(self) -> None:
        # Dashboard -> SerialManager
        self.dashboard_page.connect_requested.connect(self.serial_mgr.connect_port)
        self.dashboard_page.disconnect_requested.connect(self.serial_mgr.disconnect_port)

        # SerialManager -> MainWindow
        self.serial_mgr.connected.connect(self._on_fc_connected)
        self.serial_mgr.disconnected.connect(self._on_fc_disconnected)
        self.serial_mgr.connection_lost.connect(self._on_fc_connection_lost)
        self.serial_mgr.command_succeeded.connect(self._on_command_succeeded)
        self.serial_mgr.command_failed.connect(self._on_command_failed)
        self.serial_mgr.telemetry_received.connect(self._on_telemetry)
        self.serial_mgr.calibration_progress.connect(self.sensors_page.update_progress)
        self.serial_mgr.log_message.connect(self.dashboard_page.append_log)

        # PID Tuning (Profiles is at index 6)
        self.pid_page.read_requested.connect(lambda: self.serial_mgr.send_command(CommandType.GET_CONFIG))
        self.pid_page.send_requested.connect(self._on_send_pid)
        self.pid_page.save_eeprom_requested.connect(lambda: self.serial_mgr.send_command(CommandType.SAVE_EEPROM))
        self.pid_page.reset_requested.connect(self._on_reset_pid)
        self.pid_page.open_profiles_requested.connect(lambda: self._switch_page(6))

        # Sensor Calibration
        self.sensors_page.start_calibration_requested.connect(self._on_start_calibration)

        # Motor Configuration
        self.motors_page.motor_test_requested.connect(self._on_motor_test)
        self.motors_page.motor_stop_requested.connect(
            lambda: self.serial_mgr.send_command(CommandType.MOTOR_STOP)
        )
        self.motors_page.send_motor_config_requested.connect(self._on_send_motor_config)

        # Radio Configuration
        self.radio_page.send_radio_config_requested.connect(self._on_send_radio_config)

        # Profiles
        self.profiles_page.request_current_profile.connect(self._on_save_current_profile)
        self.profiles_page.profile_loaded.connect(self._on_profile_loaded)

        # Settings
        self.settings_page.timeout_changed.connect(self.serial_mgr.set_command_timeout)
        self.settings_page.stream_rate_changed.connect(
            lambda rate: self.serial_mgr.send_command(CommandType.SET_STREAM, {"enabled": True, "rate_hz": rate})
        )
        self.settings_page.theme_changed.connect(self._apply_and_save_theme)

    def _apply_and_save_theme(self, bg_hex: str, accent_hex: str) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(bg_hex, accent_hex))
        self.settings_page.set_theme_display(bg_hex, accent_hex)
        try:
            self._settings_path.write_text(
                json.dumps({"bg": bg_hex, "accent": accent_hex}, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _load_saved_theme(self) -> None:
        if self._settings_path.exists():
            try:
                data = json.loads(self._settings_path.read_text(encoding="utf-8"))
                self._apply_and_save_theme(data.get("bg", "#090D16"), data.get("accent", "#38BDF8"))
            except Exception:
                pass

    def _set_all_connected(self, connected: bool, info: dict[str, Any] | None = None) -> None:
        self.top_stop_btn.setEnabled(connected)
        self.dashboard_page.set_connected_state(connected, info)
        self.pid_page.set_connected_state(connected)
        self.sensors_page.set_connected_state(connected)
        self.motors_page.set_connected_state(connected)
        self.radio_page.set_connected_state(connected)
        self.settings_page.set_connected_state(connected)

    def _on_fc_connected(self, info: dict[str, Any]) -> None:
        self._set_all_connected(True, info)
        self.top_conn_pill.set_state("CONNECTED", "success")
        dev = info.get("device", "NanoFC")
        self.top_status_lbl.setText(f"Connected to {dev} (Protocol {info.get('protocol_version', '1.0')})")
        self.statusBar().showMessage(f"Connected: {dev}", 4000)
        self.dashboard_page.append_log("INFO", f"Handshake OK: {info}")

    def _on_fc_disconnected(self) -> None:
        self._set_all_connected(False)
        self.top_conn_pill.set_state("DISCONNECTED", "muted")
        self.top_mode_pill.set_state("OFFLINE", "muted")
        self.top_bat_pill.set_state("BAT: N/A", "muted")
        self.top_status_lbl.setText("Disconnected from flight controller.")
        self.statusBar().showMessage("Disconnected", 3000)

    def _on_fc_connection_lost(self, reason: str) -> None:
        self._on_fc_disconnected()
        self.dashboard_page.append_log("ERROR", f"Connection lost: {reason}")
        QMessageBox.warning(self, "Serial Connection Lost", f"Communication with the flight controller was lost:\n\n{reason}")

    def _on_command_succeeded(self, cmd: str, data: dict[str, Any]) -> None:
        self.statusBar().showMessage(f"ACK: {cmd}", 3000)
        self.dashboard_page.append_log("ACK", f"{cmd} succeeded")
        if cmd == CommandType.GET_CONFIG.value:
            if "pid" in data:
                self.pid_page.set_pid_config(PIDConfig.from_dict(data["pid"]))
            if "radio" in data:
                self.radio_page.set_radio_config(RadioConfig.from_dict(data["radio"]))
            if "motor" in data:
                self.motors_page.set_motor_config(MotorConfig.from_dict(data["motor"]))
        elif cmd in (CommandType.SET_PID.value, CommandType.RESET_PID.value) and "pid" in data:
            self.pid_page.set_pid_config(PIDConfig.from_dict(data["pid"]))
        elif cmd == CommandType.SET_RADIO_CFG.value and "radio" in data:
            self.radio_page.set_radio_config(RadioConfig.from_dict(data["radio"]))
        elif cmd == CommandType.SET_MOTOR_CFG.value and "motor" in data:
            self.motors_page.set_motor_config(MotorConfig.from_dict(data["motor"]))

    def _on_command_failed(self, cmd: str, msg: str) -> None:
        self.statusBar().showMessage(f"ERR ({cmd}): {msg}", 5000)
        self.dashboard_page.append_log("ERROR", f"{cmd}: {msg}")
        QMessageBox.warning(self, "Command Error", f"Command '{cmd}' failed:\n\n{msg}")

    def _on_telemetry(
        self,
        status: SystemStatus,
        imu: IMUData,
        radio: RadioData,
        motors: MotorOutputs,
    ) -> None:
        self.top_mode_pill.set_state(
            f"{status.flight_mode} ({'ARMED' if status.armed else 'DISARMED'})",
            "danger" if status.armed else "accent",
        )
        if status.battery_v is not None:
            pct, _ = self.dashboard_page._estimate_lipo_pct(status.battery_v)
            tone = "success" if pct > 30 else ("warning" if pct > 15 else "danger")
            self.top_bat_pill.set_state(f"BAT: {status.battery_v:.2f}V ({pct}%)", tone)
        else:
            self.top_bat_pill.set_state("BAT: N/A", "muted")
        self.dashboard_page.update_telemetry(status, imu)
        self.sensors_page.update_imu(imu)
        self.monitor_page.update_imu(imu)
        self.motors_page.update_telemetry(status, motors)
        self.radio_page.update_radio(radio)

    def _on_send_pid(self, cfg: PIDConfig) -> None:
        errors = cfg.validate()
        if errors:
            QMessageBox.warning(self, "Invalid PID Values", "\n".join(errors))
            return
        self.serial_mgr.send_command(CommandType.SET_PID, cfg.to_dict())

    def _on_reset_pid(self) -> None:
        reply = QMessageBox.question(self, "Reset PID", "Reset flight controller PID gains to firmware defaults?")
        if reply == QMessageBox.StandardButton.Yes:
            self.serial_mgr.send_command(CommandType.RESET_PID)

    def _on_start_calibration(self, target: str) -> None:
        stationary, msg = self.calibration_service.is_stationary()
        if not stationary:
            QMessageBox.warning(self, "Drone Not Stationary", msg)
            return
        self.serial_mgr.send_command(CommandType.CAL_START, {"target": target}, timeout_s=5.0)

    def _on_motor_test(self, motor_num: int, pwm_us: int) -> None:
        self.serial_mgr.send_command(
            CommandType.MOTOR_TEST,
            {"motor": motor_num, "pwm": pwm_us, "confirm": True},
        )

    def _on_send_motor_config(self, cfg: MotorConfig) -> None:
        errors = cfg.validate()
        if errors:
            QMessageBox.warning(self, "Invalid Motor Config", "\n".join(errors))
            return
        self.serial_mgr.send_command(CommandType.SET_MOTOR_CFG, cfg.to_dict())

    def _on_send_radio_config(self, cfg: RadioConfig) -> None:
        errors = cfg.validate()
        if errors:
            QMessageBox.warning(self, "Invalid Radio Config", "\n".join(errors))
            return
        self.serial_mgr.send_command(CommandType.SET_RADIO_CFG, cfg.to_dict())

    def _on_save_current_profile(self, name: str, notes: str) -> None:
        profile = ProfileData(
            name=name,
            notes=notes,
            pid=self.pid_page.get_pid_config(),
            radio=self.radio_page.get_radio_config(),
            motor=self.motors_page.get_motor_config(),
        )
        self.profiles_page.save_profile_data(profile)

    def _on_profile_loaded(self, profile: ProfileData) -> None:
        self.pid_page.set_pid_config(profile.pid)
        self.radio_page.set_radio_config(profile.radio)
        self.motors_page.set_motor_config(profile.motor)
        if self.serial_mgr.is_connected:
            reply = QMessageBox.question(
                self,
                "Apply Profile to FC?",
                f"Profile '{profile.name}' loaded into editor.\n\nSend PID, Radio, and Motor settings to the connected flight controller now?",
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.serial_mgr.send_command(CommandType.SET_PID, profile.pid.to_dict())
                self.serial_mgr.send_command(CommandType.SET_RADIO_CFG, profile.radio.to_dict())
                self.serial_mgr.send_command(CommandType.SET_MOTOR_CFG, profile.motor.to_dict())
        else:
            QMessageBox.information(self, "Profile Loaded", f"Loaded '{profile.name}' into the configurator editor.")

    def closeEvent(self, event) -> None:  # noqa: N802
        self.serial_mgr.disconnect_port()
        super().closeEvent(event)

