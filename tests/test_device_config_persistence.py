from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
import pytest

from gui.main_window import ACUSimulator


@pytest.fixture(scope="module")
def qapp():
    # Ensure a QApplication exists for QWidget creation and QSettings
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_device_config_save_load(tmp_path, qapp):
    """Verify that device configuration is persisted via QSettings.

    This test forces `QSettings` to use an INI file under a temporary
    directory so it doesn't touch user settings.
    """
    # Use INI backend in tmp_path to avoid touching real user settings
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))

    # Create the main window (no dialogs during tests)
    win = ACUSimulator(enable_dialogs=False)

    # Set some device values
    win.acu_ip_edit.setText("192.0.2.10")
    win.acu_send_port_edit.setText("40000")
    win.acu_receive_port_edit.setText("40001")
    win.target_ip_edit.setText("192.0.2.20")
    win.target_receive_port_edit.setText("40002")

    # Save into settings
    win.save_device_settings()

    # verify settings file was written (QSettings read used later by load)

    # Create a fresh instance to load values
    win2 = ACUSimulator(enable_dialogs=False)

    # Overwrite fields to ensure load actually changes them
    win2.acu_ip_edit.setText("0.0.0.0")
    win2.acu_send_port_edit.setText("0")
    win2.acu_receive_port_edit.setText("0")
    win2.target_ip_edit.setText("0.0.0.0")
    win2.target_receive_port_edit.setText("0")

    # Load saved settings
    win2.load_device_settings()

    # Assert values restored
    assert win2.acu_ip_edit.text() == "192.0.2.10"
    assert win2.acu_send_port_edit.text() == "40000"
    assert win2.acu_receive_port_edit.text() == "40001"
    assert win2.target_ip_edit.text() == "192.0.2.20"
    assert win2.target_receive_port_edit.text() == "40002"

    # Clean up
    try:
        win.deleteLater()
        win2.deleteLater()
    except Exception:
        pass
