from PySide6.QtGui import QPixmap, QColor

from waveform_display import WaveformDisplay


def test_thumbnail_generation_sets_label(qtbot, monkeypatch):
    wd = WaveformDisplay()
    qtbot.addWidget(wd)

    # ensure there is a graphics view to grab from
    gv = getattr(wd.waveform_widget, "graphics_view", None)
    assert gv is not None

    # create a dummy pixmap to be returned by grab
    dummy = QPixmap(320, 240)
    dummy.fill(QColor("#123456"))

    # monkeypatch grab method
    def fake_grab():
        return dummy

    monkeypatch.setattr(gv, "grab", fake_grab)

    # call thumbnail handler
    wd._on_thumb_clicked()

    # thumb_label should have a pixmap (visibility may be False in headless tests)
    pm = wd.thumb_label.pixmap()
    assert pm is not None
    # pixmap should be scaled to fit within the label size
    assert pm.width() <= wd.thumb_label.width()
    assert pm.height() <= wd.thumb_label.height()
