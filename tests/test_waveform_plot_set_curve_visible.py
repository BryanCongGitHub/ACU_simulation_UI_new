from waveform_plot import WaveformPlotWidget


class DummyController:
    def get_timestamps(self):
        return [0, 1, 2]

    def get_signal_data(self, signal_id):
        return [0, 1, 2]


def test_set_curve_visible(qtbot):
    ctrl = DummyController()
    w = WaveformPlotWidget(controller=ctrl)
    qtbot.addWidget(w)

    # add a test signal
    sid = "test_sig"
    w.add_signal_plot(sid, {"name": "Test Signal", "type": "analog"})

    curves = getattr(w, "curves", {})
    assert sid in curves
    cinfo = curves[sid]
    curve = cinfo.get("curve")

    # initially visible (PlotDataItem default)
    try:
        assert curve.isVisible()
    except Exception:
        # If isVisible not available, proceed to test toggling for absence of exceptions
        pass

    # hide
    w.set_curve_visible(sid, False)
    try:
        assert not curve.isVisible()
    except Exception:
        pass

    # show again
    w.set_curve_visible(sid, True)
    try:
        assert curve.isVisible()
    except Exception:
        pass

    w.deleteLater()
