"""Module G: Configuration Profiles management (CRUD, JSON import/export)."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from services.configuration_service import ConfigurationService, ProfileData
from ui.widgets import CardFrame


class ProfilesPage(QWidget):
    """Manage saved JSON configuration profiles and apply them to the configurator."""

    profile_loaded = Signal(object)  # ProfileData
    request_current_profile = Signal(str, str)  # name, notes

    def __init__(self, config_service: ConfigurationService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = config_service
        self._build_ui()
        self.refresh_list()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel("Configuration Profiles")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        split = QHBoxLayout()
        split.setSpacing(16)

        # Left: Profile List & Actions
        list_card = CardFrame("Saved Profiles")
        self.profile_list = QListWidget()
        self.profile_list.currentTextChanged.connect(self._on_selection_changed)
        list_card.body_layout.addWidget(self.profile_list, 1)

        btn_row1 = QHBoxLayout()
        self.create_btn = QPushButton("Create / Save Current")
        self.create_btn.setObjectName("PrimaryButton")
        self.create_btn.clicked.connect(self._on_create)

        self.load_btn = QPushButton("Load into Editor")
        self.load_btn.setObjectName("SuccessButton")
        self.load_btn.clicked.connect(self._on_load)

        self.rename_btn = QPushButton("Rename")
        self.rename_btn.clicked.connect(self._on_rename)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("DangerButton")
        self.delete_btn.clicked.connect(self._on_delete)

        for btn in (self.create_btn, self.load_btn, self.rename_btn, self.delete_btn):
            btn_row1.addWidget(btn)
        list_card.body_layout.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        self.import_btn = QPushButton("Import JSON...")
        self.import_btn.clicked.connect(self._on_import)
        self.export_btn = QPushButton("Export JSON...")
        self.export_btn.clicked.connect(self._on_export)
        btn_row2.addWidget(self.import_btn)
        btn_row2.addWidget(self.export_btn)
        btn_row2.addStretch()
        list_card.body_layout.addLayout(btn_row2)

        split.addWidget(list_card, 1)

        # Right: JSON Preview
        preview_card = CardFrame("Profile Preview (Validated JSON)")
        self.preview_box = QTextEdit()
        self.preview_box.setReadOnly(True)
        preview_card.body_layout.addWidget(self.preview_box, 1)
        split.addWidget(preview_card, 1)

        root.addLayout(split, 1)

    def refresh_list(self, select_name: str | None = None) -> None:
        self.profile_list.clear()
        names = self._service.list_profiles()
        self.profile_list.addItems(names)
        if select_name and select_name in names:
            self.profile_list.setCurrentRow(names.index(select_name))
        elif names:
            self.profile_list.setCurrentRow(0)

    def _selected_name(self) -> str | None:
        item = self.profile_list.currentItem()
        return item.text() if item else None

    def _on_selection_changed(self, name: str) -> None:
        if not name:
            self.preview_box.clear()
            return
        try:
            prof = self._service.load_profile(name)
            self.preview_box.setPlainText(json.dumps(prof.to_dict(), indent=2))
        except Exception as exc:
            self.preview_box.setPlainText(f"Error reading profile: {exc}")

    def _on_create(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Profile", "Profile name:")
        if not ok or not name.strip():
            return
        notes, _ = QInputDialog.getText(self, "Profile Notes", "Optional description:")
        self.request_current_profile.emit(name.strip(), notes.strip())

    def save_profile_data(self, profile: ProfileData) -> None:
        try:
            self._service.save_profile(profile)
            self.refresh_list(profile.name)
            QMessageBox.information(self, "Saved", f"Profile '{profile.name}' validated and saved.")
        except ValueError as exc:
            QMessageBox.warning(self, "Validation Error", str(exc))

    def _on_load(self) -> None:
        name = self._selected_name()
        if not name:
            return
        try:
            prof = self._service.load_profile(name)
            self.profile_loaded.emit(prof)
        except Exception as exc:
            QMessageBox.warning(self, "Load Failed", str(exc))

    def _on_rename(self) -> None:
        old_name = self._selected_name()
        if not old_name:
            return
        new_name, ok = QInputDialog.getText(self, "Rename Profile", "New profile name:", text=old_name)
        if not ok or not new_name.strip():
            return
        try:
            self._service.rename_profile(old_name, new_name.strip())
            self.refresh_list(new_name.strip())
        except Exception as exc:
            QMessageBox.warning(self, "Rename Failed", str(exc))

    def _on_delete(self) -> None:
        name = self._selected_name()
        if not name:
            return
        reply = QMessageBox.question(self, "Delete Profile", f"Delete profile '{name}'?")
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_profile(name)
            self.refresh_list()
        except Exception as exc:
            QMessageBox.warning(self, "Delete Failed", str(exc))

    def _on_import(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Import JSON Profile", "", "JSON Files (*.json)")
        if not file_path:
            return
        try:
            prof = self._service.import_profile(Path(file_path))
            self.refresh_list(prof.name)
            QMessageBox.information(self, "Imported", f"Imported and validated '{prof.name}'.")
        except Exception as exc:
            QMessageBox.warning(self, "Import Failed", str(exc))

    def _on_export(self) -> None:
        name = self._selected_name()
        if not name:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Export JSON Profile", f"{name}.json", "JSON Files (*.json)")
        if not file_path:
            return
        try:
            self._service.export_profile(name, Path(file_path))
            QMessageBox.information(self, "Exported", f"Exported '{name}' to {file_path}.")
        except Exception as exc:
            QMessageBox.warning(self, "Export Failed", str(exc))

