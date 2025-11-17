from waveform_display import WaveformDisplay


def test_palette_save_and_load(qtbot):
    wd = WaveformDisplay()
    qtbot.addWidget(wd)

    # add a signal and assign a custom color
    sid = "sigA"
    wd.controller.select_signal(sid)
    wd.waveform_widget.add_signal_plot(sid, {"name": "Sig A", "type": "analog"})

    # set a distinct color
    wd.waveform_widget.set_curve_color(sid, "#112233")
    assert wd.waveform_widget.curves[str(sid)]["color"] == "#112233"

    # save palette to QSettings via the handler
    wd._on_save_palette()

    # change color to something else
    wd.waveform_widget.set_curve_color(sid, "#445566")
    assert wd.waveform_widget.curves[str(sid)]["color"] == "#445566"

    # load palette from QSettings (should restore #112233)
    wd._on_load_palette()

    # after load, color should be restored
    restored = wd.waveform_widget.curves.get(str(sid))
    assert restored is not None
    assert restored.get("color") == "#112233"
