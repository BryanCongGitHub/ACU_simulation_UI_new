from PySide6.QtCore import QObject
from PySide6.QtCore import Signal

from waveform_controller import WaveformController
from waveform_display import WaveformDisplay


class StubBus(QObject):
    waveform_send = Signal(object, float)
    waveform_receive = Signal(object, str, float)
    recording_toggle = Signal(bool)


def test_waveform_controller_timer_emits(qtbot):
    wc = WaveformController()
    # ensure timer conditions are met
    wc.selected_signals.add("send_test")
    wc.start_recording()

    # wait for a single data_updated emission (timer runs at 200ms)
    with qtbot.waitSignal(wc.data_updated, timeout=2000):
        pass

    wc.stop_recording()


def test_waveform_display_record_toggle_via_event_bus(qtbot):
    bus = StubBus()
    wd = WaveformDisplay(None, event_bus=bus)
    qtbot.addWidget(wd)

    # initially not recording
    assert not wd.controller.is_recording

    # toggle on
    bus.recording_toggle.emit(True)
    qtbot.waitUntil(lambda: wd.controller.is_recording is True, timeout=2000)
    assert wd.record_btn.isChecked() is True
    assert wd.record_btn.text() == "停止记录"

    # toggle off
    bus.recording_toggle.emit(False)
    qtbot.waitUntil(lambda: wd.controller.is_recording is False, timeout=2000)
    assert wd.record_btn.isChecked() is False
    assert wd.record_btn.text() == "开始记录"
