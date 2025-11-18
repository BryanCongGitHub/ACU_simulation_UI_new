from PySide6.QtCore import QPointF

from waveform_controller import WaveformController
from waveform_plot import WaveformPlotWidget


class DummyController:
    def __init__(self, timestamps, data_map):
        self._timestamps = timestamps
        self._data_map = data_map

    def get_timestamps(self):
        return self._timestamps

    def get_signal_data(self, signal_id):
        return self._data_map.get(signal_id, [])


def test_hover_updates_last_hover(qtbot):
    # prepare timestamps and single signal
    timestamps = [0, 1, 2]
    sig_id = 42
    data_map = {sig_id: [10, 20, 30]}

    controller = DummyController(timestamps, data_map)

    widget = WaveformPlotWidget(controller)
    qtbot.addWidget(widget)

    # add signal metadata expected by add_signal_plot
    widget.add_signal_plot(sig_id, {"name": "S1", "type": "analog"})

    # Monkeypatch mapSceneToView to force x near first timestamp (0)
    widget.main_plot.vb.mapSceneToView = lambda pos: QPointF(0.01, 0)

    # call hover handler with arbitrary scene pos
    widget._on_scene_mouse_moved(QPointF(0, 0))

    # last_hover should contain the signal id as a string key
    assert str(sig_id) in widget.last_hover
    entry = widget.last_hover[str(sig_id)]
    assert entry["time"] == timestamps[0]
    assert entry["value"] == 10


def test_hover_populates_last_hover(qtbot):
    ctrl = WaveformController()

    # create a few timestamps with values
    t0 = 1000.0
    ctrl.data_buffer.add_data_points({"sig1": 1.0}, timestamp=t0)
    ctrl.data_buffer.add_data_points({"sig1": 2.0}, timestamp=t0 + 1)
    ctrl.data_buffer.add_data_points({"sig1": 3.0}, timestamp=t0 + 2)

    widget = WaveformPlotWidget(ctrl)
    qtbot.addWidget(widget)

    # add a curve for the signal
    widget.add_signal_plot("sig1", {"name": "Sig1", "type": "analog"})

    # call the hover handler with a dummy QPointF. Mapping may produce x=0
    # which should pick the first sample (t0)
    widget._on_scene_mouse_moved(QPointF(0, 0))

    assert isinstance(widget.last_hover, dict)
    assert "sig1" in widget.last_hover
    assert widget.last_hover["sig1"]["value"] == 1.0
