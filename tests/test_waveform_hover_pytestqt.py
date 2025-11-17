from PySide6.QtCore import QPointF

from waveform_controller import WaveformController
from waveform_plot import WaveformPlotWidget


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
