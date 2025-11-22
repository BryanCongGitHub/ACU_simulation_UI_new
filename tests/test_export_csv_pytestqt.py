import csv


def test_export_csv_basic(tmp_path):
    from waveform_display import WaveformDisplay
    from views.event_bus import ViewEventBus
    from PySide6.QtWidgets import QFileDialog

    bus = ViewEventBus()
    w = WaveformDisplay(event_bus=bus)

    # prepare data in controller buffer
    sig = "sig_test"
    w.controller.selected_signals.add(sig)
    # add some timestamps and values
    for i in range(5):
        w.controller.data_buffer.add_data_points({sig: i}, timestamp=1600000000 + i)

    out_path = tmp_path / "out.csv"
    # monkeypatch QFileDialog for save path
    QFileDialog.getSaveFileName = lambda *a, **k: (str(out_path), "CSV File (*.csv)")

    # trigger export
    w.on_export_clicked()

    # read file and assert header
    assert out_path.exists()
    with open(out_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert "timestamp" in header
        assert sig in header
