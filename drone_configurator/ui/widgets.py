"""Reusable custom widgets: cards, status pills, metric tiles, horizon, Quad-X diagram, and joystick."""

from __future__ import annotations

import math
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.theme import PALETTE


class CardFrame(QFrame):
    """Styled card container with header, subtle divider, and inner vertical layout."""

    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.body_layout = QVBoxLayout(self)
        self.body_layout.setContentsMargins(18, 14, 18, 16)
        self.body_layout.setSpacing(10)

        if title or subtitle:
            hdr_box = QVBoxLayout()
            hdr_box.setSpacing(2)
            if title:
                title_lbl = QLabel(title)
                title_lbl.setObjectName("CardTitle")
                title_lbl.setStyleSheet("background: transparent;")
                hdr_box.addWidget(title_lbl)
            if subtitle:
                sub_lbl = QLabel(subtitle)
                sub_lbl.setObjectName("MutedLabel")
                sub_lbl.setStyleSheet("background: transparent;")
                sub_lbl.setWordWrap(True)
                hdr_box.addWidget(sub_lbl)
            self.body_layout.addLayout(hdr_box)

            divider = QFrame()
            divider.setObjectName("CardDivider")
            self.body_layout.addWidget(divider)


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
            "muted": ("#151F32", "#334155", "#94A3B8"),
        }
        bg, border, fg = colors.get(tone, colors["muted"])
        self.setText(f"● {text}")
        self.setStyleSheet(
            f"background-color: {bg}; border: 1px solid {border}; color: {fg}; "
            "border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 700;"
        )


class MetricTile(QFrame):
    """Clean KPI telemetry readout tile with accent bar."""

    def __init__(self, label: str, unit: str = "", accent: str = "#38BDF8", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setMinimumHeight(74)
        self._unit = unit
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        dot = QLabel("▪")
        dot.setStyleSheet(f"color: {accent}; background: transparent; font-size: 12px;")
        lbl = QLabel(label.upper())
        lbl.setStyleSheet("color: #94A3B8; background: transparent; font-size: 11px; font-weight: 600; letter-spacing: 0.6px;")
        top_row.addWidget(dot)
        top_row.addWidget(lbl)
        top_row.addStretch()

        self.value_label = QLabel("--")
        self.value_label.setStyleSheet("font-size: 19px; font-weight: 700; color: #F8FAFC; background: transparent;")
        layout.addLayout(top_row)
        layout.addWidget(self.value_label)

    def set_value(self, value: str, color: str = "#F8FAFC") -> None:
        suffix = f" {self._unit}" if self._unit and value != "--" else ""
        self.value_label.setText(f"{value}{suffix}")
        self.value_label.setStyleSheet(f"font-size: 19px; font-weight: 700; color: {color}; background: transparent;")


class AttitudeHorizonWidget(QWidget):
    """Artificial horizon rendering live Roll and Pitch angles with bank scale."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._roll = 0.0
        self._pitch = 0.0
        self.setMinimumSize(175, 175)

    def set_attitude(self, roll_deg: float, pitch_deg: float) -> None:
        self._roll = roll_deg
        self._pitch = pitch_deg
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        size = min(w, h) - 16
        cx, cy = w / 2.0, h / 2.0
        radius = size / 2.0

        clip = QPainterPath()
        clip.addEllipse(QPointF(cx, cy), radius, radius)
        painter.setClipPath(clip)

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self._roll)
        pitch_px = max(-radius, min(radius, self._pitch * 2.2))
        painter.translate(0, pitch_px)

        # Sky gradient
        sky_grad = QLinearGradient(0, -size, 0, 0)
        sky_grad.setColorAt(0.0, QColor("#082F49"))
        sky_grad.setColorAt(1.0, QColor("#0284C7"))
        painter.fillRect(QRectF(-size, -size, size * 2, size), sky_grad)

        # Ground gradient
        gnd_grad = QLinearGradient(0, 0, 0, size)
        gnd_grad.setColorAt(0.0, QColor("#78350F"))
        gnd_grad.setColorAt(1.0, QColor("#291508"))
        painter.fillRect(QRectF(-size, 0, size * 2, size), gnd_grad)

        # Horizon line
        painter.setPen(QPen(QColor("#F8FAFC"), 2.2))
        painter.drawLine(QPointF(-size, 0), QPointF(size, 0))

        # Pitch ladder
        painter.setPen(QPen(QColor("#E2E8F0"), 1.2))
        for deg in (-20, -10, 10, 20):
            y = -deg * 2.2
            half_w = 24 if abs(deg) == 20 else 14
            painter.drawLine(QPointF(-half_w, y), QPointF(half_w, y))
        painter.restore()

        # Bank angle ticks around top bezel
        painter.save()
        painter.translate(cx, cy)
        painter.setPen(QPen(QColor("#94A3B8"), 1.4))
        for ang in (-45, -30, -15, 0, 15, 30, 45):
            rad = math.radians(ang - 90)
            r_in = radius - (9 if ang % 30 == 0 else 5)
            painter.drawLine(
                QPointF(math.cos(rad) * r_in, math.sin(rad) * r_in),
                QPointF(math.cos(rad) * (radius - 1), math.sin(rad) * (radius - 1)),
            )
        painter.restore()

        # Fixed aircraft reticle
        painter.setClipping(False)
        painter.setPen(QPen(QColor(PALETTE["warning"]), 2.6))
        painter.drawLine(QPointF(cx - 30, cy), QPointF(cx - 9, cy))
        painter.drawLine(QPointF(cx + 9, cy), QPointF(cx + 30, cy))
        painter.drawEllipse(QPointF(cx, cy), 3.5, 3.5)

        # Numeric overlay
        painter.setPen(QColor("#E2E8F0"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(cx - 50, cy + radius - 26, 100, 18), Qt.AlignmentFlag.AlignCenter,
                         f"R {self._roll:+.1f}°  P {self._pitch:+.1f}°")

        # Outer bezel
        painter.setPen(QPen(QColor("#334155"), 2.5))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)


class QuadXDiagramWidget(QWidget):
    """Top-down Quad-X frame diagram showing M1-M4 positions and live PWM throttle rings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._motors = [1000, 1000, 1000, 1000]
        self.setMinimumSize(220, 220)

    def set_outputs(self, m1: int, m2: int, m3: int, m4: int) -> None:
        self._motors = [m1, m2, m3, m4]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        arm = min(w, h) * 0.31

        # Motor coordinates: M1=FL, M2=FR, M3=RR, M4=RL
        pts = [
            (cx - arm, cy - arm, "M1", "CW", self._motors[0]),
            (cx + arm, cy - arm, "M2", "CCW", self._motors[1]),
            (cx + arm, cy + arm, "M3", "CW", self._motors[2]),
            (cx - arm, cy + arm, "M4", "CCW", self._motors[3]),
        ]

        # Arms
        painter.setPen(QPen(QColor("#334155"), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for mx, my, *_ in pts:
            painter.drawLine(QPointF(cx, cy), QPointF(mx, my))

        # Center hub + Front arrow
        painter.setPen(QPen(QColor("#38BDF8"), 2))
        painter.setBrush(QBrush(QColor("#151F32")))
        painter.drawRoundedRect(QRectF(cx - 18, cy - 22, 36, 44), 6, 6)
        painter.setPen(QColor("#38BDF8"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(cx - 18, cy - 20, 36, 16), Qt.AlignmentFlag.AlignCenter, "▲")
        painter.setPen(QColor("#94A3B8"))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(QRectF(cx - 18, cy - 4, 36, 20), Qt.AlignmentFlag.AlignCenter, "FRONT")

        # Motor rings
        r = 24
        for mx, my, name, spin, pwm in pts:
            frac = max(0.0, min(1.0, (pwm - 1000) / 1000.0))
            painter.setPen(QPen(QColor("#1E293B"), 4))
            painter.setBrush(QBrush(QColor("#0F172A")))
            painter.drawEllipse(QPointF(mx, my), r, r)

            if frac > 0.01:
                color = QColor("#10B981") if frac < 0.4 else (QColor("#F59E0B") if frac < 0.75 else QColor("#EF4444"))
                painter.setPen(QPen(color, 4))
                painter.drawArc(QRectF(mx - r, my - r, r * 2, r * 2), 90 * 16, int(-frac * 360 * 16))

            painter.setPen(QColor("#F8FAFC"))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(mx - r, my - 12, r * 2, 14), Qt.AlignmentFlag.AlignCenter, name)
            painter.setPen(QColor("#94A3B8"))
            painter.setFont(QFont("Segoe UI", 7))
            painter.drawText(QRectF(mx - r, my + 1, r * 2, 14), Qt.AlignmentFlag.AlignCenter, spin)


class JoystickVisualizerWidget(QWidget):
    """2D XY stick position visualizer for Radio Configuration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._x = 0.0
        self._y = 0.0
        self.setMinimumSize(190, 190)

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
        painter.drawRoundedRect(QRectF(left, top, side, side), 10, 10)

        painter.setPen(QPen(QColor("#334155"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(cx, top), QPointF(cx, top + side))
        painter.drawLine(QPointF(left, cy), QPointF(left + side, cy))

        px = cx + self._x * (side / 2.0 - 12)
        py = cy - self._y * (side / 2.0 - 12)
        painter.setPen(QPen(QColor("#BAE6FD"), 2))
        painter.setBrush(QBrush(QColor(PALETTE["accent"])))
        painter.drawEllipse(QPointF(px, py), 9, 9)
