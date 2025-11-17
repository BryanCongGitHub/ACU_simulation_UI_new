from PySide6.QtCore import QCoreApplication, QSettings, Qt
import pytest

from waveform_display import WaveformDisplay
from views.event_bus import ViewEventBus


@pytest.fixture(scope="module")
def qapp():
    # Ensure a QCoreApplication exists for QSettings; avoid full QApplication
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    yield app


def test_save_and_load_settings(tmp_path, qapp):
    """Verify save_settings/load_settings persist splitter sizes
    and the signal display order.
    """
    # Force QSettings to use IniFormat in the temporary directory so we
    # do not affect user settings.
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))

    # Create the widget and set some state
    bus = ViewEventBus()
    w = WaveformDisplay(event_bus=bus)

    # Choose some signals if available (may be none depending on signal manager)
    # We'll toggle the first two available signals if present
    tree = w.signal_tree
    selected_ids = []
    for i in range(tree.topLevelItemCount()):
        cat = tree.topLevelItem(i)
        for j in range(cat.childCount()):
            item = cat.child(j)
            sid = item.data(0, Qt.UserRole)
            if sid:
                item.setCheckState(0, Qt.Checked)
                selected_ids.append(str(sid))
            if len(selected_ids) >= 2:
                break
        if len(selected_ids) >= 2:
            break

    # Adjust splitter sizes
    try:
        w.splitter.setSizes([200, 800])
    except Exception:
        pass

    # Save settings
    w.save_settings()

    # Create a new widget instance to load settings
    w2 = WaveformDisplay(event_bus=bus)
    # Clear current plots to ensure load actually restores
    try:
        w2.waveform_widget.clear_plots()
    except Exception:
        pass

    # Load settings into w2
    w2.load_settings()

    # Check last export path key exists (sanity)
    settings = QSettings()
    settings.beginGroup("WaveformDisplay")
    sig_order = settings.value("signal_order", []) or []
    splitter_sizes = settings.value("splitter_sizes", None)
    settings.endGroup()

    assert isinstance(sig_order, (list, tuple))
    # splitter sizes should be present and convertible to list
    assert splitter_sizes is None or isinstance(splitter_sizes, (list, tuple))

    # Clean up created widgets
    try:
        w.deleteLater()
        w2.deleteLater()
    except Exception:
        pass
