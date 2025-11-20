import pytest
from PySide6.QtCore import QSettings, Qt

from infra.settings_store import WaveformSettings, save_waveform_settings
from waveform_display import WaveformDisplay
from views.event_bus import ViewEventBus


@pytest.fixture
def isolated_settings(tmp_path):
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    QSettings.setPath(QSettings.IniFormat, QSettings.SystemScope, str(tmp_path))
    settings = QSettings()
    settings.clear()
    yield
    settings = QSettings()
    settings.clear()


def test_auto_range_toggle_persists(qtbot, isolated_settings):
    bus = ViewEventBus()
    widget = WaveformDisplay(event_bus=bus)
    qtbot.addWidget(widget)

    widget.auto_range_check.setChecked(False)
    widget.save_settings()

    widget2 = WaveformDisplay(event_bus=bus)
    qtbot.addWidget(widget2)

    widget2.load_settings()

    assert not widget2.auto_range_check.isChecked()


def test_palette_restored_from_settings(qtbot, isolated_settings, monkeypatch):
    target_signal = "send_bool_均衡充电模式"
    palette_color = "#123456"

    state = WaveformSettings(
        selected_signals=[target_signal],
        signal_order=[target_signal],
        palette={target_signal: palette_color},
    )
    save_waveform_settings(state)

    bus = ViewEventBus()
    widget = WaveformDisplay(event_bus=bus)
    qtbot.addWidget(widget)

    applied = {}
    monkeypatch.setattr(
        widget.waveform_widget,
        "set_curve_color",
        lambda sid, color: applied.setdefault(str(sid), color),
    )
    monkeypatch.setattr(
        widget.waveform_widget, "add_signal_plot", lambda sid, info: None
    )
    monkeypatch.setattr(
        widget.waveform_widget, "set_curve_visible", lambda sid, value: None
    )
    monkeypatch.setattr(widget.waveform_widget, "update_all_plots", lambda: None)
    monkeypatch.setattr(widget.waveform_widget, "auto_range", lambda: None)

    widget.load_settings()

    assert applied.get(target_signal) == palette_color


def test_time_range_saved_and_loaded(qtbot, isolated_settings):
    bus = ViewEventBus()
    widget = WaveformDisplay(event_bus=bus)
    qtbot.addWidget(widget)

    widget.time_range_combo.setCurrentText("30分钟")
    widget.save_settings()

    widget2 = WaveformDisplay(event_bus=bus)
    qtbot.addWidget(widget2)
    widget2.load_settings()

    assert widget2.time_range_combo.currentText() == "30分钟"
    assert widget2.auto_range_check.isChecked()


def test_signal_selection_triggers_controller(qtbot, isolated_settings, monkeypatch):
    bus = ViewEventBus()
    widget = WaveformDisplay(event_bus=bus)
    qtbot.addWidget(widget)

    target_item = None
    for i in range(widget.signal_tree.topLevelItemCount()):
        cat = widget.signal_tree.topLevelItem(i)
        if cat.childCount():
            target_item = cat.child(0)
            break
    assert target_item is not None

    signal_id = target_item.data(0, Qt.UserRole)
    assert signal_id

    select_calls = []
    original_select = widget.controller.select_signal

    def record_select(sid):
        select_calls.append(sid)
        original_select(sid)

    monkeypatch.setattr(widget.controller, "select_signal", record_select)

    deselect_calls = []
    original_deselect = widget.controller.deselect_signal

    def record_deselect(sid):
        deselect_calls.append(sid)
        original_deselect(sid)

    monkeypatch.setattr(widget.controller, "deselect_signal", record_deselect)

    added = []
    monkeypatch.setattr(
        widget.waveform_widget,
        "add_signal_plot",
        lambda sid, info: added.append((sid, info)),
    )

    removed = []
    monkeypatch.setattr(
        widget.waveform_widget, "remove_signal_plot", lambda sid: removed.append(sid)
    )

    target_item.setCheckState(0, Qt.Checked)

    assert signal_id in select_calls
    assert any(call[0] == signal_id for call in added)
    assert signal_id in widget.controller.get_selected_signals()

    target_item.setCheckState(0, Qt.Unchecked)

    assert signal_id in deselect_calls
    assert signal_id in removed
    assert signal_id not in widget.controller.get_selected_signals()


def test_selected_signals_restored_on_load(qtbot, isolated_settings, monkeypatch):
    bus = ViewEventBus()
    widget = WaveformDisplay(event_bus=bus)
    qtbot.addWidget(widget)

    chosen_items = []
    for i in range(widget.signal_tree.topLevelItemCount()):
        cat = widget.signal_tree.topLevelItem(i)
        for j in range(cat.childCount()):
            chosen_items.append(cat.child(j))
            if len(chosen_items) == 2:
                break
        if len(chosen_items) == 2:
            break

    assert len(chosen_items) == 2
    signal_ids = [item.data(0, Qt.UserRole) for item in chosen_items]
    for sid in signal_ids:
        assert sid

    for item in chosen_items:
        item.setCheckState(0, Qt.Checked)

    widget.save_settings()

    widget2 = WaveformDisplay(event_bus=bus)
    qtbot.addWidget(widget2)

    added = []
    monkeypatch.setattr(
        widget2.waveform_widget,
        "add_signal_plot",
        lambda sid, info: added.append((sid, info)),
    )
    monkeypatch.setattr(
        widget2.waveform_widget, "set_curve_visible", lambda sid, value: None
    )
    monkeypatch.setattr(widget2.waveform_widget, "update_all_plots", lambda: None)
    monkeypatch.setattr(widget2.waveform_widget, "auto_range", lambda: None)

    widget2.load_settings()

    restored = set(widget2.controller.get_selected_signals())
    for sid in signal_ids:
        assert sid in restored
        assert any(call[0] == sid for call in added)

    restored_items = []
    for i in range(widget2.signal_tree.topLevelItemCount()):
        cat = widget2.signal_tree.topLevelItem(i)
        for j in range(cat.childCount()):
            restored_items.append(cat.child(j))

    checked_ids = {
        item.data(0, Qt.UserRole)
        for item in restored_items
        if item.checkState(0) == Qt.Checked
    }

    for sid in signal_ids:
        assert sid in checked_ids
