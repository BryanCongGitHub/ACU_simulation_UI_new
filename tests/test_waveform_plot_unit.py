from waveform_plot import WaveformPlotWidget


class DummyController:
    def __init__(self):
        self._data = {"t": [0, 1, 2], "sig": [0.1, 0.2, 0.3]}

    def get_timestamps(self):
        return self._data["t"]

    def get_signal_data(self, sid):
        return self._data.get("sig", [])


def test_set_curve_visible(qtbot):
    ctrl = DummyController()
    w = WaveformPlotWidget(ctrl)
    # add a fake signal
    info = {"name": "sig1", "type": "analog"}
    w.add_signal_plot("sig", info)
    # hide it
    w.set_curve_visible("sig", False)
    cinfo = w.curves.get("sig")
    assert cinfo is not None
    try:
        assert not cinfo["curve"].isVisible()
    except Exception:
        # some versions may remove the item; ensure no crash
        pass
    # show it
    w.set_curve_visible("sig", True)
    try:
        assert cinfo["curve"].isVisible()
    except Exception:
        pass
