"""Modern dark-themed stylesheet and color palette for the configurator."""

PALETTE = {
    "bg_window": "#0D1117",
    "bg_sidebar": "#111722",
    "bg_card": "#161E2B",
    "bg_input": "#1E293B",
    "border": "#283548",
    "text_primary": "#E2E8F0",
    "text_secondary": "#94A3B8",
    "text_muted": "#64748B",
    "accent": "#38BDF8",
    "accent_hover": "#0EA5E9",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
}

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0D1117;
    color: #E2E8F0;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}

QFrame#Sidebar {
    background-color: #111722;
    border-right: 1px solid #283548;
}

QFrame#TopBar {
    background-color: #111722;
    border-bottom: 1px solid #283548;
}

QFrame#Card {
    background-color: #161E2B;
    border: 1px solid #283548;
    border-radius: 8px;
}

QFrame#WarningBanner {
    background-color: #2B1D12;
    border: 1px solid #F59E0B;
    border-radius: 6px;
}

QFrame#DangerBanner {
    background-color: #2D1519;
    border: 1px solid #EF4444;
    border-radius: 6px;
}

QLabel#PageTitle {
    font-size: 20px;
    font-weight: 600;
    color: #F8FAFC;
}

QLabel#CardTitle {
    font-size: 14px;
    font-weight: 600;
    color: #F1F5F9;
}

QLabel#MutedLabel {
    color: #94A3B8;
    font-size: 12px;
}

QPushButton#NavButton {
    text-align: left;
    padding: 10px 14px;
    border: none;
    border-radius: 6px;
    color: #94A3B8;
    background-color: transparent;
    font-weight: 500;
}

QPushButton#NavButton:hover {
    background-color: #1B2536;
    color: #E2E8F0;
}

QPushButton#NavButton[active="true"] {
    background-color: #1E2D42;
    color: #38BDF8;
    border-left: 3px solid #38BDF8;
    font-weight: 600;
}

QPushButton {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 7px 14px;
    color: #E2E8F0;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #273549;
    border-color: #475569;
}

QPushButton:disabled {
    background-color: #131A24;
    color: #475569;
    border-color: #1E293B;
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
    background-color: #163245;
    border-color: #1E3A52;
    color: #64748B;
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
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 5px 8px;
    color: #F1F5F9;
    selection-background-color: #0284C7;
}

QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
    border-color: #38BDF8;
}

QProgressBar {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 5px;
    text-align: center;
    color: #F8FAFC;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #0EA5E9;
    border-radius: 4px;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #1E293B;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #38BDF8;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QToolTip {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #38BDF8;
    padding: 5px;
    border-radius: 4px;
}
"""

