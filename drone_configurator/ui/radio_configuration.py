"""Module F: nRF24L01 Radio Receiver monitoring and endpoint configuration."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from models.radio_data import ChannelConfig, RadioConfig, RadioData
from ui.widgets import CardFrame, JoystickVisualizerWidget, StatusPill


class RadioConfigurationPage(QWidget):
    """Radio link status, live joystick/channel bars, and endpoint calibration."""

    send_radio_config_requested = Signal(object)  # RadioConfig

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ch_widgets: dict[str, dict[str, QSpinBox | QCheckBox]] = {}
        self._build_ui()
        self.set_radio_config(RadioConfig())

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel("Radio Configuration (nRF24L01)")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        # Top row: Link Status + Live Channels + Joystick Visualizer
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        live_card = CardFrame("Live Receiver Channels")
        status_row = QHBoxLayout()
        self.rx_pill = StatusPill("RX OFFLINE", "muted")
        self.age_label = QLabel("Packet Age: -- ms | Loss: -- %")
        self.age_label.setObjectName("MutedLabel")
        status_row.addWidget(self.rx_pill)
        status_row.addWidget(self.age_label)
        status_row.addStretch()
        live_card.body_layout.addLayout(status_row)

        self.ch_bars: dict[str, QProgressBar] = {}
        for ch_key, ch_label in [("roll", "Roll (Joy X)"), ("pitch", "Pitch (Joy Y)"), ("throttle", "Throttle"), ("yaw", "Yaw")]:
            row = QHBoxLayout()
            lbl = QLabel(ch_label)
            lbl.setMinimumWidth(100)
            bar = QProgressBar()
            bar.setRange(900, 2100)
            bar.setValue(1500 if ch_key != "throttle" else 1000)
            bar.setFormat("%v us")
            row.addWidget(lbl)
            row.addWidget(bar, 1)
            live_card.body_layout.addLayout(row)
            self.ch_bars[ch_key] = bar

        top_row.addWidget(live_card, 2)

        sticks_card = CardFrame("Dual Joystick Monitor")
        sticks_row = QHBoxLayout()
        sticks_row.setSpacing(12)

        left_box = QVBoxLayout()
        left_lbl = QLabel("Left Stick (Yaw / Throttle)")
        left_lbl.setObjectName("MutedLabel")
        self.left_joystick = JoystickVisualizerWidget()
        left_box.addWidget(left_lbl)
        left_box.addWidget(self.left_joystick)

        right_box = QVBoxLayout()
        right_lbl = QLabel("Right Stick (Roll / Pitch)")
        right_lbl.setObjectName("MutedLabel")
        self.joystick = JoystickVisualizerWidget()
        right_box.addWidget(right_lbl)
        right_box.addWidget(self.joystick)

        sticks_row.addLayout(left_box)
        sticks_row.addLayout(right_box)
        sticks_card.body_layout.addLayout(sticks_row)
        top_row.addWidget(sticks_card, 2)

        root.addLayout(top_row)

        # Endpoint Configuration Card
        ep_card = CardFrame("Channel Endpoints & Failsafe Timeout")
        grid = QGridLayout()
        grid.setSpacing(8)
        for col, hdr in enumerate(["Channel", "Min (us)", "Center (us)", "Max (us)", "Deadband (us)", "Reverse"]):
            lbl = QLabel(hdr)
            lbl.setObjectName("MutedLabel")
            grid.addWidget(lbl, 0, col)

        for row_idx, ch_key in enumerate(("roll", "pitch", "throttle", "yaw"), start=1):
            grid.addWidget(QLabel(ch_key.capitalize()), row_idx, 0)
            min_s = self._make_spin(800, 1400, 1000)
            ctr_s = self._make_spin(900, 1800, 1500)
            max_s = self._make_spin(1600, 2200, 2000)
            db_s = self._make_spin(0, 100, 10)
            rev_cb = QCheckBox()

            grid.addWidget(min_s, row_idx, 1)
            grid.addWidget(ctr_s, row_idx, 2)
            grid.addWidget(max_s, row_idx, 3)
            grid.addWidget(db_s, row_idx, 4)
            grid.addWidget(rev_cb, row_idx, 5)
            self._ch_widgets[ch_key] = {
                "min": min_s,
                "center": ctr_s,
                "max": max_s,
                "deadband": db_s,
                "rev": rev_cb,
            }

        ep_card.body_layout.addLayout(grid)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(QLabel("Signal Loss Timeout (ms):"))
        self.timeout_spin = self._make_spin(100, 5000, 500)
        self.timeout_spin.setToolTip("Time without nRF24L01 packets before triggering failsafe.")
        bottom_row.addWidget(self.timeout_spin)
        bottom_row.addStretch()

        self.send_btn = QPushButton("Send Radio Config to FC")
        self.send_btn.setObjectName("PrimaryButton")
        self.send_btn.clicked.connect(lambda: self.send_radio_config_requested.emit(self.get_radio_config()))
        bottom_row.addWidget(self.send_btn)

        ep_card.body_layout.addLayout(bottom_row)
        root.addWidget(ep_card)
        root.addStretch()

        self.set_connected_state(False)

    @staticmethod
    def _make_spin(low: int, high: int, val: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(low, high)
        s.setValue(val)
        return s

    def set_radio_config(self, cfg: RadioConfig) -> None:
        for key in ("roll", "pitch", "throttle", "yaw"):
            ch: ChannelConfig = getattr(cfg, key)
            w = self._ch_widgets[key]
            w["min"].setValue(ch.min_us)  # type: ignore[union-attr]
            w["center"].setValue(ch.center_us)  # type: ignore[union-attr]
            w["max"].setValue(ch.max_us)  # type: ignore[union-attr]
            w["deadband"].setValue(ch.deadband_us)  # type: ignore[union-attr]
            w["rev"].setChecked(ch.reversed)  # type: ignore[union-attr]
        self.timeout_spin.setValue(cfg.timeout_ms)

    def get_radio_config(self) -> RadioConfig:
        def _build(key: str) -> ChannelConfig:
            w = self._ch_widgets[key]
            return ChannelConfig(
                name=key.capitalize(),
                min_us=w["min"].value(),  # type: ignore[union-attr]
                center_us=w["center"].value(),  # type: ignore[union-attr]
                max_us=w["max"].value(),  # type: ignore[union-attr]
                deadband_us=w["deadband"].value(),  # type: ignore[union-attr]
                reversed=w["rev"].isChecked(),  # type: ignore[union-attr]
            )

        return RadioConfig(
            roll=_build("roll"),
            pitch=_build("pitch"),
            throttle=_build("throttle"),
            yaw=_build("yaw"),
            timeout_ms=self.timeout_spin.value(),
        )

    def set_connected_state(self, connected: bool) -> None:
        self.send_btn.setEnabled(connected)
        if not connected:
            self.rx_pill.set_state("RX OFFLINE", "muted")
            self.age_label.setText("Packet Age: -- ms | Loss: -- %")

    def update_radio(self, rx: RadioData) -> None:
        self.rx_pill.set_state("RX LINK ACTIVE" if rx.rx_connected else "RX TIMEOUT",
                               "success" if rx.rx_connected else "danger")
        self.age_label.setText(f"Packet Age: {rx.last_packet_age_ms} ms | Loss: {rx.packet_loss_pct:.1f}%")
        self.ch_bars["roll"].setValue(rx.roll_us)
        self.ch_bars["pitch"].setValue(rx.pitch_us)
        self.ch_bars["throttle"].setValue(rx.throttle_us)
        self.ch_bars["yaw"].setValue(rx.yaw_us)
        self.joystick.set_position(rx.joystick_x, rx.joystick_y)
        yaw_norm = max(-1.0, min(1.0, (rx.yaw_us - 1500) / 500.0))
        thr_norm = max(-1.0, min(1.0, (rx.throttle_us - 1500) / 500.0))
        self.left_joystick.set_position(yaw_norm, thr_norm)

