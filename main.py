import sys
import os


def _configure_qt_runtime() -> None:
    if not getattr(sys, "frozen", False):
        os.environ.setdefault("QT_API", "PySide6")
        os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")
        return

    os.environ.setdefault("QT_API", "PySide6")
    os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    qt_dir = os.path.join(base_dir, "PySide6")
    candidates = [
        qt_dir,
        os.path.join(qt_dir, "Qt", "bin"),
        os.path.join(base_dir, "shiboken6"),
        base_dir,
    ]

    if qt_dir not in sys.path:
        sys.path.insert(0, qt_dir)

    for path in candidates:
        if not os.path.isdir(path):
            continue
        os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
        try:
            os.add_dll_directory(path)
        except Exception:
            pass

    plugins_dir = os.path.join(qt_dir, "plugins")
    if os.path.isdir(plugins_dir):
        os.environ.setdefault("QT_PLUGIN_PATH", plugins_dir)
        platform_dir = os.path.join(plugins_dir, "platforms")
        if os.path.isdir(platform_dir):
            os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", platform_dir)

    # Note: we intentionally avoid importing PySide6 until after runtime
    # paths are configured above. Do not pre-load Qt DLLs here.


_configure_qt_runtime()

from PySide6 import QtCore  # noqa: F401,E402

import pyqtgraph as pg  # noqa: E402

pg.setConfigOptions(useOpenGL=False)


# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from app.bootstrap import run  # noqa: E402

if __name__ == "__main__":
    try:
        exit_code = run(sys.argv)
        sys.exit(exit_code)
    except Exception:
        # Print traceback to stderr so it is captured when running from a
        # console (preferred for debugging frozen executables).
        import traceback

        traceback.print_exc()
        sys.exit(1)
