from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog
from gui.settings_dialog import SettingsDialog


def test_export_import_settings(tmp_path, monkeypatch, qapp):
    # Prepare some settings to export
    settings = QSettings()
    settings.beginGroup("WaveformDisplay")
    settings.setValue("time_range", "5分钟")
    settings.setValue("auto_range", False)
    settings.endGroup()

    settings.beginGroup("ACUSimulator")
    settings.beginGroup("DeviceConfig")
    settings.setValue("acu_ip", "192.0.2.50")
    settings.setValue("acu_send_port", 45000)
    settings.endGroup()
    settings.endGroup()

    # create dialog and select groups to export
    dlg = SettingsDialog()
    dlg.reset_waveform.setChecked(True)
    dlg.reset_device.setChecked(True)

    out_path = tmp_path / "exported.ini"
    # monkeypatch QFileDialog to return our path
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *a, **k: (str(out_path), "INI Files (*.ini)"),
    )

    # call export
    dlg._on_export_clicked()

    # verify exported file contains keys
    src = QSettings(str(out_path), QSettings.IniFormat)
    keys = src.allKeys()
    assert any(
        "WaveformDisplay/time_range" in k or "WaveformDisplay/auto_range" in k
        for k in keys
    )
    assert any("ACUSimulator/DeviceConfig/acu_ip" in k for k in keys)

    # Now modify current settings to different values
    settings.beginGroup("WaveformDisplay")
    settings.setValue("time_range", "1小时")
    settings.endGroup()

    # Prepare import: select both groups
    dlg2 = SettingsDialog()
    dlg2.reset_waveform.setChecked(True)
    dlg2.reset_device.setChecked(True)

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *a, **k: (str(out_path), "INI Files (*.ini)"),
    )

    # import
    dlg2._on_import_clicked()

    # verify settings restored from file
    settings_after = QSettings()
    assert settings_after.value("WaveformDisplay/time_range") == "5分钟"
    assert settings_after.value("ACUSimulator/DeviceConfig/acu_ip") == "192.0.2.50"


def test_restore_recommended_defaults(tmp_path, qapp):
    # clear settings then call restore defaults
    settings = QSettings()
    settings.clear()

    dlg = SettingsDialog()
    dlg._on_restore_defaults_clicked()

    s = QSettings()
    # Check some recommended defaults exist
    assert s.value("WaveformDisplay/time_range") == "10分钟"
    assert s.value("ACUSimulator/DeviceConfig/acu_ip") == "10.2.0.1"
    assert int(s.value("ACUSimulator/DeviceConfig/acu_send_port")) == 49152
