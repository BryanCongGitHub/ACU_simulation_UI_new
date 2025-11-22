from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
import pytest

from gui.main_window import ACUSimulator


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_preset_selection_and_persistence(tmp_path, qapp):
    # Use INI backend in tmp_path to avoid touching real user settings
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))

    # Create main window and ensure presets loaded
    win = ACUSimulator(enable_dialogs=False)

    # combo should exist
    assert hasattr(win, "device_type_combo") and win.device_type_combo is not None

    # Choose a preset known to exist in infra/device_presets.json
    preset_name = "INV3"
    # Ensure preset is in combo items
    items = [
        win.device_type_combo.itemText(i) for i in range(win.device_type_combo.count())
    ]
    assert preset_name in items

    # Select the preset
    win.device_type_combo.setCurrentText(preset_name)

    # After selection, fields should be populated according to presets
    # INV3 target_ip per presets should be 10.2.0.4
    assert win.target_ip_edit.text() == "10.2.0.4"

    # Save settings (should persist device_preset and fields to QSettings)
    win.save_device_settings()

    # Create a fresh instance to load values
    win2 = ACUSimulator(enable_dialogs=False)

    # Overwrite fields to ensure load actually changes them
    win2.target_ip_edit.setText("0.0.0.0")

    # Load saved settings
    win2.load_device_settings()

    # Assert the combo restored to the preset
    assert getattr(win2, "device_type_combo", None) is not None
    assert win2.device_type_combo.currentText() == preset_name

    # And the target IP restored
    assert win2.target_ip_edit.text() == "10.2.0.4"

    # Clean up
    try:
        win.deleteLater()
        win2.deleteLater()
    except Exception:
        pass
