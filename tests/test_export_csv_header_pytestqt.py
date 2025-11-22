import csv

from waveform_display import WaveformDisplay


def test_export_csv_header(qtbot, monkeypatch, tmp_path):
    # Create widget
    w = WaveformDisplay()
    qtbot.addWidget(w)

    # pick a known signal id from signal manager
    sig = None
    # prefer a recv analog signal that exists in definitions
    candidate = "recv_analog_输出频率"
    if candidate in w.controller.signal_manager.signals:
        sig = candidate
    else:
        # fallback to any available signal
        keys = list(w.controller.signal_manager.signals.keys())
        assert keys, "No signals found in SignalManager"
        sig = keys[0]

    info = w.controller.signal_manager.get_signal_info(sig)
    display_name = info.get("name") or str(sig)

    # select the signal and add some data
    w.controller.select_signal(sig)
    # add two data points
    w.controller.data_buffer.add_data_points({sig: 1}, timestamp=1)
    w.controller.data_buffer.add_data_points({sig: 2}, timestamp=2)

    # prepare temp csv path
    csv_file = tmp_path / "out.csv"

    # monkeypatch file dialog to return our path
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(csv_file), "CSV 文件 (*.csv)"),
    )

    # monkeypatch message boxes to avoid modal dialogs
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.information", lambda *a, **k: None
    )
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.critical", lambda *a, **k: None)

    # call export
    w.on_export_clicked()

    # assert file exists and header contains display name
    assert csv_file.exists(), "CSV file was not created"

    with open(csv_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)

    assert "timestamp" in header
    assert display_name in header

    w.deleteLater()
