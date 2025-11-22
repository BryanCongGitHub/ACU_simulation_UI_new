from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QCheckBox,
    QLabel,
    QMessageBox,
    QFileDialog,
)
from PySide6.QtCore import QSettings
import json
import logging

from infra.settings_store import (
    apply_default_device_config,
    apply_default_waveform_settings,
    clear_all_settings,
    export_to_ini,
    import_from_ini,
    reset_groups,
)

logger = logging.getLogger("SettingsDialog")


class SettingsDialog(QDialog):
    """A lightweight settings dialog to reset persisted UI and app settings.

    This dialog intentionally keeps behavior minimal: it performs group-level
    resets in `QSettings` and lets the caller decide how to reload UI state.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Reset stored settings (select groups to reset):"))

        self.reset_waveform = QCheckBox("Waveform display settings")
        self.reset_device = QCheckBox("Device configuration")
        self.reset_app = QCheckBox("Application settings (window geometry, etc.)")

        # default to unchecked
        self.reset_waveform.setChecked(False)
        self.reset_device.setChecked(False)
        self.reset_app.setChecked(False)

        layout.addWidget(self.reset_waveform)
        layout.addWidget(self.reset_device)
        layout.addWidget(self.reset_app)

        btn_area = QHBoxLayout()
        self.reset_btn = QPushButton("Reset Selected")
        self.close_btn = QPushButton("Close")
        btn_area.addWidget(self.reset_btn)
        btn_area.addWidget(self.close_btn)

        layout.addLayout(btn_area)

        # Export / Import / Defaults
        io_area = QHBoxLayout()
        self.export_btn = QPushButton("Export Selected")
        self.import_btn = QPushButton("Import From File")
        self.restore_defaults_btn = QPushButton("Restore Recommended Defaults")
        # palette IO buttons
        self.export_palette_btn = QPushButton("Export Palette")
        self.import_palette_btn = QPushButton("Import Palette")
        io_area.addWidget(self.export_btn)
        io_area.addWidget(self.import_btn)
        io_area.addWidget(self.restore_defaults_btn)
        io_area.addWidget(self.export_palette_btn)
        io_area.addWidget(self.import_palette_btn)
        layout.addLayout(io_area)

        self.reset_btn.clicked.connect(self._on_reset_clicked)
        self.close_btn.clicked.connect(self.accept)
        self.export_btn.clicked.connect(self._on_export_clicked)
        self.import_btn.clicked.connect(self._on_import_clicked)
        self.restore_defaults_btn.clicked.connect(self._on_restore_defaults_clicked)
        self.export_palette_btn.clicked.connect(self._on_export_palette_clicked)
        self.import_palette_btn.clicked.connect(self._on_import_palette_clicked)

    # Palette IO helpers exposed for programmatic access
    @staticmethod
    def save_palette_to_settings(mapping: dict):
        try:
            settings = QSettings()
            settings.beginGroup("WaveformDisplay")
            settings.setValue("palette", json.dumps(mapping, ensure_ascii=False))
            settings.endGroup()
            try:
                settings.sync()
            except Exception:
                pass
            return True
        except Exception:
            logger.exception("Failed to save palette to settings")
            return False

    @staticmethod
    def load_palette_from_settings() -> dict:
        try:
            settings = QSettings()
            settings.beginGroup("WaveformDisplay")
            raw = settings.value("palette", "") or ""
            settings.endGroup()
            if not raw:
                return {}
            try:
                mapping = json.loads(raw)
                return mapping or {}
            except Exception:
                return {}
        except Exception:
            logger.exception("Failed to load palette from settings")
            return {}

    @staticmethod
    def export_palette_to_file(mapping: dict = None, parent=None) -> bool:
        try:
            if mapping is None:
                mapping = SettingsDialog.load_palette_from_settings()
            path, _ = QFileDialog.getSaveFileName(
                parent, "Export palette", "palette.json", "JSON 文件 (*.json)"
            )
            if not path:
                return False
            with open(path, "w", encoding="utf-8") as f:
                json.dump(mapping or {}, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            logger.exception("Export palette failed")
            return False

    @staticmethod
    def import_palette_from_file(parent=None) -> dict:
        try:
            path, _ = QFileDialog.getOpenFileName(
                parent, "Import palette", "", "JSON 文件 (*.json)"
            )
            if not path:
                return {}
            with open(path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            # write into settings as well
            try:
                SettingsDialog.save_palette_to_settings(mapping)
            except Exception:
                pass
            return mapping or {}
        except Exception:
            logger.exception("Import palette failed")
            return {}

    def _on_reset_clicked(self):
        summary: list[str] = []
        try:
            groups: list[str] = []
            if self.reset_waveform.isChecked():
                groups.append("WaveformDisplay")
            if self.reset_device.isChecked():
                groups.append("ACUSimulator")

            if groups:
                reset_groups(groups)
                summary.extend(groups)

            if self.reset_app.isChecked():
                clear_all_settings()
                summary.append("All")
        except Exception as exc:
            logger.exception("Failed to reset settings: %s", exc)
            QMessageBox.critical(self, "Error", f"Reset failed: {exc}")
            return

        message = ", ".join(summary) if summary else "None"
        QMessageBox.information(self, "Reset", f"Reset: {message}")
        # close dialog after reset
        self.accept()

    def _on_export_clicked(self):
        """Export selected groups to an INI file chosen by the user."""
        try:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Export settings to INI",
                "settings_export.ini",
                "INI Files (*.ini);;All Files (*)",
            )
            if not path:
                return

            groups = []
            if self.reset_waveform.isChecked():
                groups.append("WaveformDisplay")
            if self.reset_device.isChecked():
                groups.append("ACUSimulator")

            if self.reset_app.isChecked():
                export_to_ini(path, None)
            else:
                export_to_ini(path, groups)

            QMessageBox.information(self, "Export", f"Settings exported to: {path}")
        except Exception as exc:
            logger.exception("Export failed: %s", exc)
            QMessageBox.critical(self, "Export failed", str(exc))

    def _on_import_clicked(self):
        """Import settings from an INI file, merging into current QSettings."""
        try:
            path, _ = QFileDialog.getOpenFileName(
                self, "Import settings from INI", "", "INI Files (*.ini);;All Files (*)"
            )
            if not path:
                return

            groups = []
            if self.reset_waveform.isChecked():
                groups.append("WaveformDisplay")
            if self.reset_device.isChecked():
                groups.append("ACUSimulator")

            if self.reset_app.isChecked():
                import_from_ini(path, None)
            else:
                import_from_ini(path, groups)

            QMessageBox.information(self, "Import", f"Settings imported from: {path}")
        except Exception as exc:
            logger.exception("Import failed: %s", exc)
            QMessageBox.critical(self, "Import failed", str(exc))

    def _on_restore_defaults_clicked(self):
        """Write a set of recommended defaults into QSettings for common groups."""
        try:
            apply_default_waveform_settings()
            apply_default_device_config()

            QMessageBox.information(
                self, "Defaults", "Recommended defaults restored to settings."
            )
            self.accept()
        except Exception as exc:
            logger.exception("Restore defaults failed: %s", exc)
            QMessageBox.critical(self, "Restore failed", str(exc))

    def _on_export_palette_clicked(self):
        """Handler for the Export Palette button in the dialog UI."""
        try:
            ok = self.export_palette_to_file(parent=self)
            if ok:
                QMessageBox.information(self, "Export Palette", "配色已导出")
            else:
                QMessageBox.information(self, "Export Palette", "导出已取消或失败")
        except Exception:
            logger.exception("Export palette button handler failed")
            QMessageBox.critical(self, "Export Palette", "导出失败")

    def _on_import_palette_clicked(self):
        """Handler for the Import Palette button in the dialog UI."""
        try:
            mapping = self.import_palette_from_file(parent=self)
            if mapping:
                QMessageBox.information(
                    self, "Import Palette", "配色已导入并保存到设置"
                )
            else:
                QMessageBox.information(self, "Import Palette", "导入已取消或失败")
        except Exception:
            logger.exception("Import palette button handler failed")
            QMessageBox.critical(self, "Import Palette", "导入失败")

    @staticmethod
    def reset_all_settings():
        """Convenience to clear all QSettings groups."""
        try:
            clear_all_settings()
            return True
        except Exception:
            return False
