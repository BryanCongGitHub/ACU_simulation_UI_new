import csv
import json

from waveform_display import WaveformDisplay


def _prepare_two_signals_with_data(wd):
    # choose two distinct signals from signal manager
    keys = list(wd.controller.signal_manager.signals.keys())
    assert len(keys) >= 2, "Need at least two signals for this test"
    s1, s2 = keys[0], keys[1]

    # select them at controller level
    wd.controller.select_signal(s1)
    wd.controller.select_signal(s2)

    # create timestamps and add paired data points
    timestamps = [1, 2, 3]
    for i, ts in enumerate(timestamps):
        wd.controller.data_buffer.add_data_points(
            {s1: i + 10, s2: i + 100}, timestamp=ts
        )

    return s1, s2, timestamps


def test_export_csv_and_json_headers_and_rows(qtbot, monkeypatch, tmp_path):
    wd = WaveformDisplay()
    qtbot.addWidget(wd)

    s1, s2, timestamps = _prepare_two_signals_with_data(wd)

    # determine expected header order from controller.get_selected_signals()
    selected = list(wd.controller.get_selected_signals())
    assert len(selected) >= 2
    # map to display names in the selected order
    display_names = []
    for sid in selected:
        info = wd.controller.signal_manager.get_signal_info(sid) or {}
        display_names.append(info.get("name") or str(sid))

    # CSV export
    csv_file = tmp_path / "out.csv"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(csv_file), "CSV 文件 (*.csv)"),
    )

    wd.on_export_clicked()

    assert csv_file.exists(), "CSV file not created"
    with open(csv_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == ["timestamp"] + display_names

        rows = list(reader)
        # rows should match timestamps order
        assert len(rows) == len(timestamps)
        for i, row in enumerate(rows):
            assert row[0] == str(timestamps[i])
            # values follow the same selected order
            assert row[1] == str(i + 10) or row[1] == str(i + 100)
            assert row[2] == str(i + 10) or row[2] == str(i + 100)

    # settings should have recorded last_export_path
    from PySide6.QtCore import QSettings

    settings = QSettings()
    last = settings.value("WaveformDisplay/last_export_path", "") or ""
    assert str(csv_file) == last

    # JSON export
    json_file = tmp_path / "out.json"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(json_file), "JSON 文件 (*.json)"),
    )

    wd.on_export_clicked()
    assert json_file.exists()
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == len(timestamps)
        # each element should be a dict with timestamp and display names
        for i, item in enumerate(data):
            assert item.get("timestamp") == timestamps[i]
            # JSON uses display names as keys; check both appear
            for dn in display_names:
                assert dn in item
