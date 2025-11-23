import os
import sys


def _add_dll_directory(path):
    if not path:
        return
    try:
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(path)
    except Exception:
        # Best-effort; on older platforms or restricted env this may fail.
        pass


def _add_path_to_env(path):
    if not path or not os.path.isdir(path):
        return
    os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
    _add_dll_directory(path)


def _set_qt_plugin_path(path):
    if not path or not os.path.isdir(path):
        return
    existing = os.environ.get("QT_PLUGIN_PATH", "")
    if existing:
        os.environ["QT_PLUGIN_PATH"] = path + os.pathsep + existing
    else:
        os.environ["QT_PLUGIN_PATH"] = path


try:
    if getattr(sys, "frozen", False):
        _meipass = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        base = _meipass
        pyside_dir = os.path.join(base, "PySide6")
    else:
        from PySide6 import QtCore  # type: ignore

        pyside_dir = os.path.dirname(QtCore.__file__)

    plugins_dir = os.path.join(pyside_dir, "plugins")
    qt_bin_dir = os.path.join(pyside_dir, "Qt", "bin")
    shiboken_dir = os.path.join(os.path.dirname(pyside_dir), "shiboken6")

    _add_path_to_env(pyside_dir)
    _add_path_to_env(qt_bin_dir)
    _add_path_to_env(shiboken_dir)

    _set_qt_plugin_path(plugins_dir)

    # Also set platform plugin path for Qt if available
    platform_dir = os.path.join(plugins_dir, "platforms")
    if os.path.isdir(platform_dir):
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", platform_dir)

except Exception:
    # Best-effort runtime hook; do not fail the application
    # if something goes wrong here.
    pass
