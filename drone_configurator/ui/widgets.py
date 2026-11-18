"""Reusable custom widgets: cards, status pills, metric tiles, horizon, and joystick."""

from __future__ import annotations

import math
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.theme import PALETTE


class CardFrame(QFrame):
    """Styled card container with title and inner vertical layout."""

    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.body_layout = QVBoxLayout(self)
        self.body_layout.setContentsMargins(16, 14, 16, 14)
        self.body_layout.setSpacing(10)

        if title:
            title_lbl = QLabel(title)
            title_lbl.setObjectName("CardTitle")
            self.body_layout.addWidget(title_lbl)
        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setObjectName("MutedLabel")
            sub_lbl.setWordWrap(True)
            self.body_layout.addWidget(sub_lbl)


class StatusPill(QLabel):
    """Compact colored badge showing connection or subsystem state."""

    def __init__(self, text: str = "OFFLINE", tone: str = "muted", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state(text, tone)

    def set_state(self, text: str, tone: str = "muted") -> None:
        colors = {
            "success": ("#064E3B", "#10B981", "#A7F3D0"),
            "warning": ("#451A03", "#F59E0B", "#FDE68A"),
            "danger": ("#450A0A", "#EF4444", "#FECACA"),
            "accent": ("#0C4A6E", "#38BDF8", "#BAE6FD"),
            "muted": ("#1E293B", "#475569", "#94A3B8"),
        }
        bg, border, fg = colors.get(tone, colors["muted"])
        self.setText(f"  {text}  ")
        self.setStyleSheet(
            f"background-color: {bg}; border: 1px solid {border}; color: {fg}; "
            "border-radius: 11px; padding: 3px 10px; font-size: 11px; font-weight: 600;"
        )


class MetricTile(QFrame):
    """Numeric telemetry readout tile."""

    def __init__(self, label: str, unit: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._unit = unit
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        lbl = QLabel(label)
        lbl.setObjectName("MutedLabel")
        self.value_label = QLabel("--")
        self.value_label.setStyleSheet("font-size: 20px; font-weight: 700; color: #F8FAFC;")
        layout.addWidget(lbl)
        layout.addWidget(self.value_label)

    def set_value(self, value: str, color: str = "#F8FAFC") -> None:
        suffix = f" {self._unit}" if self._unit and value != "--" else ""
        self.value_label.setText(f"{value}{suffix}")
        self.value_label.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {color};")


class AttitudeHorizonWidget(QWidget):
    """Artificial horizon rendering live Roll and Pitch angles."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._roll = 0.0
        self._pitch = 0.0
        self.setMinimumSize(180, 180)

    def set_attitude(self, roll_deg: float, pitch_deg: float) -> None:
        self._roll = roll_deg
        self._pitch = pitch_deg
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        size = min(w, h) - 12
        cx, cy = w / 2.0, h / 2.0
        radius = size / 2.0

        # Clip to circular instrument face
        from PySide6.QtGui import QPainterPath
        clip = QPainterPath()
        clip.addEllipse(QPointF(cx, cy), radius, radius)
        painter.setClipPath(clip)

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self._roll)
        pitch_px = max(-radius, min(radius, self._pitch * 2.0))
        painter.translate(0, pitch_px)

        # Sky and ground
        painter.fillRect(QRectF(-size, -size, size * 2, size), QColor("#0E4A6F"))
        painter.fillRect(QRectF(-size, 0, size * 2, size), QColor("#4A3520"))

        # Horizon line
        painter.setPen(QPen(QColor("#F8FAFC"), 2))
        painter.drawLine(QPointF(-size, 0), QPointF(size, 0))

        # Pitch ladder
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        for deg in (-20, -10, 10, 20):
            y = -deg * 2.0
            painter.drawLine(QPointF(-22, y), QPointF(22, y))
        painter.restore()

        # Fixed aircraft reticle
        painter.setClipping(False)
        painter.setPen(QPen(QColor(PALETTE["warning"]), 2.5))
        painter.drawLine(QPointF(cx - 26, cy), QPointF(cx - 8, cy))
        painter.drawLine(QPointF(cx + 8, cy), QPointF(cx + 26, cy))
        painter.drawEllipse(QPointF(cx, cy), 3, 3)

        # Outer bezel
        painter.setPen(QPen(QColor(PALETTE["border"]), 2))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)


class JoystickVisualizerWidget(QWidget):
    """2D XY stick position visualizer for Radio Configuration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._x = 0.0
        self._y = 0.0
        self.setMinimumSize(180, 180)

    def set_position(self, x: float, y: float) -> None:
        self._x = max(-1.0, min(1.0, x))
        self._y = max(-1.0, min(1.0, y))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        side = min(w, h) - 16
        left = (w - side) / 2.0
        top = (h - side) / 2.0
        cx, cy = w / 2.0, h / 2.0

        painter.setPen(QPen(QColor(PALETTE["border"]), 1.5))
        painter.setBrush(QBrush(QColor(PALETTE["bg_input"])))
        painter.drawRoundedRect(QRectF(left, top, side, side), 8, 8)

        # Crosshair
        painter.setPen(QPen(QColor("#334155"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(cx, top), QPointF(cx, top + side))
        painter.drawLine(QPointF(left, cy), QPointF(left + side, cy))

        # Stick dot
        px = cx + self._x * (side / 2.0 - 10)
        py = cy - self._y * (side / 2.0 - 10)
        painter.setPen(QPen(QColor("#BAE6FD"), 2))
        painter.setBrush(QBrush(QColor(PALETTE["accent"])))
        painter.drawEllipse(QPointF(px, py), 8, 8)

