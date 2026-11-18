"""Modern aerospace Ground Control Station (GCS) dark theme, presets, and customizer."""

from PySide6.QtGui import QColor

PALETTE = {
    "bg_window": "#090D16",
    "bg_sidebar": "#0D1320",
    "bg_card": "#121A2A",
    "bg_elevated": "#182236",
    "bg_input": "#1A253A",
    "border": "#233148",
    "border_focus": "#38BDF8",
    "text_primary": "#F1F5F9",
    "text_secondary": "#94A3B8",
    "text_muted": "#64748B",
    "accent": "#38BDF8",
    "accent_hover": "#0EA5E9",
    "indigo": "#818CF8",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
}

THEME_PRESETS: dict[str, dict[str, str]] = {
    "Deep Aerospace":  {"bg": "#090D16", "accent": "#38BDF8"},
    "Midnight Navy":   {"bg": "#071124", "accent": "#60A5FA"},
    "Obsidian Carbon": {"bg": "#0B0B0E", "accent": "#38BDF8"},
    "Slate Steel":     {"bg": "#0F172A", "accent": "#38BDF8"},
    "Emerald Night":   {"bg": "#061512", "accent": "#10B981"},
    "Ocean Teal":      {"bg": "#06161E", "accent": "#2DD4BF"},
    "Royal Indigo":    {"bg": "#0D0B21", "accent": "#818CF8"},
    "Cyber Purple":    {"bg": "#14091F", "accent": "#C084FC"},
    "Crimson Cockpit": {"bg": "#18090D", "accent": "#F87171"},
    "Amber Dusk":      {"bg": "#171007", "accent": "#FBBF24"},
    "Forest Moss":     {"bg": "#0B160C", "accent": "#4ADE80"},
    "Graphite Warm":   {"bg": "#141210", "accent": "#FB923C"},
}


def _shift(hex_color: str, amount: int) -> str:
    """Lighten (positive) or darken (negative) a hex color while clamping."""
    c = QColor(hex_color)
    r = max(0, min(255, c.red() + amount))
    g = max(0, min(255, c.green() + amount))
    b = max(0, min(255, c.blue() + amount))
    return f"#{r:02X}{g:02X}{b:02X}"


def build_stylesheet(bg_hex: str = "#090D16", accent_hex: str = "#38BDF8") -> str:
    """Generate a cohesive QSS stylesheet from any background color and accent."""
    c = QColor(bg_hex)
    is_light = c.lightness() > 140
    step = -10 if is_light else 10

    bg_win = c.name().upper()
    bg_side = _shift(bg_win, step // 2)
    bg_card = _shift(bg_win, step)
    bg_metric = _shift(bg_win, int(step * 1.4))
    bg_input = _shift(bg_win, int(step * 1.6))
    border = _shift(bg_win, int(step * 2.6))
    text_pri = "#0F172A" if is_light else "#F1F5F9"
    text_sec = "#475569" if is_light else "#94A3B8"

    qss = DARK_STYLESHEET
    qss = qss.replace("#090D16", bg_win)
    qss = qss.replace("#0D1320", bg_side)
    qss = qss.replace("#121A2A", bg_card)
    qss = qss.replace("#151F32", bg_metric)
    qss = qss.replace("#1A253A", bg_input)
    qss = qss.replace("#1F2D42", border)
    qss = qss.replace("#233148", border)
    qss = qss.replace("#38BDF8", accent_hex)
    if is_light:
        qss = qss.replace("#F1F5F9", text_pri).replace("#F8FAFC", text_pri).replace("#94A3B8", text_sec)
    return qss

DARK_STYLESHEET = """
QMainWindow {
    background-color: #090D16;
    color: #F1F5F9;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}

QWidget {
    color: #F1F5F9;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}

QStackedWidget, QSplitter {
    background-color: #090D16;
}

QLabel, QCheckBox {
    background-color: transparent;
}

QFrame#Sidebar {
    background-color: #0D1320;
    border-right: 1px solid #1E293B;
}

QFrame#TopBar {
    background-color: #0D1320;
    border-bottom: 1px solid #1E293B;
}

QFrame#Card {
    background-color: #121A2A;
    border: 1px solid #1F2D42;
    border-radius: 10px;
}

QFrame#MetricCard {
    background-color: #151F32;
    border: 1px solid #22314A;
    border-radius: 10px;
}

QFrame#CardDivider {
    background-color: #1F2D42;
    max-height: 1px;
    min-height: 1px;
}

QFrame#WarningBanner {
    background-color: #2A1B0E;
    border: 1px solid #D97706;
    border-radius: 8px;
}

QFrame#DangerBanner {
    background-color: #2A1216;
    border: 1px solid #DC2626;
    border-radius: 8px;
}

QLabel#PageTitle {
    font-size: 22px;
    font-weight: 700;
    color: #F8FAFC;
    letter-spacing: 0.3px;
}

QLabel#PageSubtitle {
    font-size: 12px;
    color: #94A3B8;
}

QLabel#CardTitle {
    font-size: 14px;
    font-weight: 600;
    color: #F8FAFC;
}

QLabel#MutedLabel {
    color: #94A3B8;
    font-size: 12px;
}

QLabel#SectionLabel {
    color: #64748B;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
    padding: 8px 10px 2px 10px;
}

QPushButton#NavButton {
    text-align: left;
    padding: 10px 14px;
    border: 1px solid transparent;
    border-radius: 8px;
    color: #94A3B8;
    background-color: transparent;
    font-weight: 500;
    font-size: 13px;
}

QPushButton#NavButton:hover {
    background-color: #162033;
    color: #F1F5F9;
}

QPushButton#NavButton[active="true"] {
    background-color: #162840;
    color: #38BDF8;
    border: 1px solid #1E4268;
    font-weight: 600;
}

QPushButton {
    background-color: #1A253A;
    border: 1px solid #2D3E58;
    border-radius: 7px;
    padding: 7px 14px;
    color: #F1F5F9;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #23324D;
    border-color: #3E5578;
}

QPushButton:pressed {
    background-color: #151E30;
}

QPushButton:disabled {
    background-color: #101724;
    color: #475569;
    border-color: #1A2333;
}

QPushButton#PrimaryButton {
    background-color: #0284C7;
    border: 1px solid #38BDF8;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background-color: #0EA5E9;
}

QPushButton#PrimaryButton:disabled {
    background-color: #112A3E;
    border-color: #1B3B54;
    color: #526A80;
}

QPushButton#SuccessButton {
    background-color: #059669;
    border: 1px solid #10B981;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton#SuccessButton:hover {
    background-color: #10B981;
}

QPushButton#DangerButton {
    background-color: #B91C1C;
    border: 1px solid #EF4444;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton#DangerButton:hover {
    background-color: #DC2626;
}

QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QTextEdit, QListWidget {
    background-color: #151F32;
    border: 1px solid #2A3A54;
    border-radius: 6px;
    padding: 6px 9px;
    color: #F8FAFC;
    selection-background-color: #0284C7;
}

QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
    border-color: #38BDF8;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QProgressBar {
    background-color: #151F32;
    border: 1px solid #2A3A54;
    border-radius: 6px;
    text-align: center;
    color: #F8FAFC;
    font-weight: 600;
    height: 20px;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8);
    border-radius: 5px;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #1E293B;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #0EA5E9;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #38BDF8;
    border: 2px solid #F8FAFC;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 8px;
}

QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #3B4F6E;
    background-color: #151F32;
}

QCheckBox::indicator:checked {
    background-color: #0EA5E9;
    border-color: #38BDF8;
}

QScrollBar:vertical {
    background: #0D1320;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #283852;
    border-radius: 4px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #38BDF8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QStatusBar {
    background-color: #0D1320;
    border-top: 1px solid #1E293B;
    color: #94A3B8;
}

QToolTip {
    background-color: #182236;
    color: #F8FAFC;
    border: 1px solid #38BDF8;
    padding: 6px;
    border-radius: 5px;
}
"""
