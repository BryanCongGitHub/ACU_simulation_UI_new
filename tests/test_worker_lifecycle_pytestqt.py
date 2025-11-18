from gui.main_window import ACUSimulator


class DummyComm:
    def __init__(self, real):
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


def test_worker_start_stop(monkeypatch):
    win = ACUSimulator(enable_dialogs=False)
    # replace comm with dummy
    monkeypatch.setattr(win, "comm", DummyComm(win.comm))

    ok = win.start_communication()
    assert ok is True
    # workers should be created
    assert getattr(win, "parse_worker", None) is not None
    assert getattr(win, "format_worker", None) is not None

    # stop
    win.stop_communication()

    # threads placeholders cleared
    assert win.parse_worker_thread is None
    assert win.format_worker_thread is None
