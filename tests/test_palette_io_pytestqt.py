from PySide6.QtCore import QSettings, Qt
import json

from waveform_display import WaveformDisplay
from views.event_bus import ViewEventBus


def test_save_and_export_import_palette(qtbot, tmp_path, monkeypatch):
    # Ensure QSettings uses tmp path
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))

    bus = ViewEventBus()
    w = WaveformDisplay(event_bus=bus)
    qtbot.addWidget(w)

    # select first available signal if any
    tree = w.signal_tree
    first_sid = None
    for i in range(tree.topLevelItemCount()):
        cat = tree.topLevelItem(i)
        for j in range(cat.childCount()):
            item = cat.child(j)
            sid = item.data(0, Qt.UserRole)
            if sid:
                item.setCheckState(0, Qt.Checked)
                first_sid = sid
                break
        if first_sid:
            break

    # Mock file dialogs: export to a temp file
    out_file = tmp_path / "palette_test.json"

    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(out_file), "JSON 文件 (*.json)"),
    )
    # call export
    w._on_export_palette()
    assert out_file.exists()

    # now clear QSettings and try import
    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # modify mapping and write a new file
    for k in list(data.keys()):
        data[k] = "#123456"

    in_file = tmp_path / "palette_in.json"
    with open(in_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        lambda *a, **k: (str(in_file), "JSON 文件 (*.json)"),
    )
    w._on_import_palette()

    # ensure that at least one curve color was set to new value if there was a signal
    if first_sid:
        curves = getattr(w.waveform_widget, "curves", {})
        c = curves.get(str(first_sid)) or curves.get(first_sid)
        assert c is not None
        assert c.get("color") == "#123456"

    w.deleteLater()
