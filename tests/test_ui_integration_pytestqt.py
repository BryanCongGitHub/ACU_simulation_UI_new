import pytest
from PySide6.QtCore import QSettings, Qt

from gui.main_window import ACUSimulator


@pytest.fixture(autouse=True)
def qsettings_tmpdir(tmp_path, monkeypatch):
    # Force QSettings to INI and put files under tmp_path
    # to avoid touching user settings
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    yield


def test_main_window_start_stop(qtbot, monkeypatch):
    """Basic UI integration test using pytest-qt's qtbot.

    - Launches `ACUSimulator` window
    - Toggles a couple of signals in WaveformDisplay (if present)
    - Saves and reloads waveform settings
    - Mocks CommunicationController.setup/start_receive_loop to avoid network operations
    - Clicks Start and Stop buttons and asserts state changes
    """
    # Ensure headless platform used (CI will set QT_QPA_PLATFORM)
    # Create window
    win = ACUSimulator(enable_dialogs=False)
    qtbot.addWidget(win)

    # mock comm.setup and start_receive_loop to be no-op
    class DummyComm:
        def __init__(self, real):
            # keep config dict shape
            self.config = real.config
            self.on_receive = None
            self.on_error = None
            self.on_status = None

        def update_config(self, **cfg):
            self.config.update(cfg)

        def setup(self):
            return True

        def start_receive_loop(self):
            return None

        def stop(self):
            return None

        def send(self, data):
            return None

    monkeypatch.setattr(win, "comm", DummyComm(win.comm))

    # show the window (offscreen)
    win.show()

    # Interact: click Start
    qtbot.mouseClick(win.start_btn, Qt.LeftButton)

    # After start, start_btn disabled, stop_btn enabled
    qtbot.wait(100)
    assert not win.start_btn.isEnabled()
    assert win.stop_btn.isEnabled()

    # click Stop
    qtbot.mouseClick(win.stop_btn, Qt.LeftButton)
    qtbot.wait(100)
    assert win.start_btn.isEnabled()
    assert not win.stop_btn.isEnabled()

    # Try save/load waveform settings via display
    try:
        w = win.waveform_display
        # toggle first available signal if exists
        tree = getattr(w, "signal_tree", None)
        if tree and tree.topLevelItemCount() > 0:
            top = tree.topLevelItem(0)
            if top.childCount() > 0:
                item = top.child(0)
                # simulate checking
                item.setCheckState(0, 2)  # Qt.Checked
        w.save_settings()
        # create another display instance and load
        w2 = type(w)(event_bus=win.view_bus)
        w2.load_settings()
        w2.deleteLater()
    except Exception:
        pass

    win.close()
