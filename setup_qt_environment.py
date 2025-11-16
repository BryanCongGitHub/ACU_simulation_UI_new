import sys
import os
from pathlib import Path


def setup_qt_environment():
    """Configure Qt environment paths for packaged and development runs."""

    # Disable the internal qt.conf so we can override paths
    os.environ["PYSIDE_DISABLE_INTERNAL_QT_CONF"] = "1"

    if hasattr(sys, "_MEIPASS"):
        # Running inside a packaged executable (PyInstaller)
        base_path = sys._MEIPASS
        print(f"Packaged env - MEIPASS: {base_path}")

        # Configure plugin paths for the packaged layout
        plugin_path = os.path.join(base_path, "PySide6", "plugins")
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path

        # Configure additional Qt paths
        os.environ["QT_PLUGIN_PATH"] = plugin_path
        os.environ["QML2_IMPORT_PATH"] = os.path.join(base_path, "PySide6", "qml")

        print(f"Configured plugin path: {plugin_path}")

        # Check whether the platform plugins exist
        platforms_path = os.path.join(plugin_path, "platforms")
        if os.path.exists(platforms_path):
            print(f"Found platform plugin dir: {platforms_path}")
            plugins = os.listdir(platforms_path)
            print(f"Platform plugins: {plugins}")
        else:
            print(f"Warning: platform plugin dir missing: {platforms_path}")

    else:
        # Running in a development environment
        try:
            import PySide6

            pyside6_dir = Path(PySide6.__file__).parent
            plugin_path = pyside6_dir / "plugins"

            if plugin_path.exists():
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugin_path)
                os.environ["QT_PLUGIN_PATH"] = str(plugin_path)
                print(f"Dev env - Qt plugin path: {plugin_path}")
            else:
                print("Warning: Qt plugin path not found")

        except ImportError as e:
            print(f"Unable to import PySide6: {e}")
            sys.exit(1)


# Call before importing any PySide6 modules
setup_qt_environment()

# Debug info
print("=== Qt environment configured ===")
qt_platform_path = os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH", "unset")
print(f"QT_QPA_PLATFORM_PLUGIN_PATH: {qt_platform_path}")
qt_plugin_path = os.environ.get("QT_PLUGIN_PATH", "unset")
print(f"QT_PLUGIN_PATH: {qt_plugin_path}")
