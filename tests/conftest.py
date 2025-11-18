import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PySide6.QtCore import QSettings
import pytest

# Ensure repository root is on sys.path so tests can import top-level packages
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Ensure a QApplication exists for all tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def disable_dialogs(monkeypatch):
    """Prevent modal dialogs from blocking tests by
    monkeypatching QMessageBox and QFileDialog.
    """
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    yield


@pytest.fixture(autouse=True)
def qsettings_tmpdir(tmp_path, monkeypatch):
    """Force QSettings to use an INI file in a temporary directory for isolation."""
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    yield
