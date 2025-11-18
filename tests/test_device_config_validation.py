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


def test_restore_defaults_and_validation(tmp_path, qapp):
    # Use INI backend in tmp_path
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))

    win = ACUSimulator(enable_dialogs=False)

    # mutate fields
    win.acu_ip_edit.setText("1.2.3.4")
    win.acu_send_port_edit.setText("40010")
    win.acu_receive_port_edit.setText("40011")
    win.target_ip_edit.setText("1.2.3.5")
    win.target_receive_port_edit.setText("40012")

    # restore defaults
    win.restore_device_defaults()

    # defaults should match device config and comm config
    dev_cfg = win._acu_device.config
    assert win.acu_ip_edit.text() == str(dev_cfg.ip)
    assert win.acu_send_port_edit.text() == str(dev_cfg.send_port)
    if dev_cfg.receive_port is not None:
        assert win.acu_receive_port_edit.text() == str(dev_cfg.receive_port)

    comm_cfg = win.comm.config
    assert win.target_ip_edit.text() == str(comm_cfg.get("target_ip", ""))
    assert win.target_receive_port_edit.text() == str(
        comm_cfg.get("target_receive_port", "")
    )

    # validation: entering invalid port should prevent applying
    prev_send = win.comm.config.get("acu_send_port")
    win.acu_send_port_edit.setText("not-a-port")
    applied = win._on_device_apply()
    assert applied is False
    # config should be unchanged
    assert win.comm.config.get("acu_send_port") == prev_send

    # valid port should apply
    win.acu_send_port_edit.setText("50000")
    applied = win._on_device_apply()
    assert applied is True
    assert win.comm.config.get("acu_send_port") == 50000

    try:
        win.deleteLater()
    except Exception:
        pass
