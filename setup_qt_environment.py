import sys
import os
import logging
from pathlib import Path


def setup_qt_environment():
    """Configure Qt environment paths for packaged and development runs."""

    # Disable the internal qt.conf so we can override paths
    os.environ["PYSIDE_DISABLE_INTERNAL_QT_CONF"] = "1"

    if hasattr(sys, "_MEIPASS"):
        # Running inside a packaged executable (PyInstaller)
        base_path = sys._MEIPASS
        logging.getLogger(__name__).info("Packaged env - MEIPASS: %s", base_path)

        # Configure plugin paths for the packaged layout
        plugin_path = os.path.join(base_path, "PySide6", "plugins")
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path

        # Configure additional Qt paths
        os.environ["QT_PLUGIN_PATH"] = plugin_path
        os.environ["QML2_IMPORT_PATH"] = os.path.join(base_path, "PySide6", "qml")

        logging.getLogger(__name__).info("Configured plugin path: %s", plugin_path)

        # Check whether the platform plugins exist
        platforms_path = os.path.join(plugin_path, "platforms")
        if os.path.exists(platforms_path):
            logging.getLogger(__name__).info(
                "Found platform plugin dir: %s", platforms_path
            )
            plugins = os.listdir(platforms_path)
            logging.getLogger(__name__).debug("Platform plugins: %s", plugins)
        else:
            logging.getLogger(__name__).warning(
                "Platform plugin dir missing: %s", platforms_path
            )

    else:
        # Running in a development environment
        try:
            import PySide6

            pyside6_dir = Path(PySide6.__file__).parent
            plugin_path = pyside6_dir / "plugins"

            if plugin_path.exists():
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugin_path)
                os.environ["QT_PLUGIN_PATH"] = str(plugin_path)
                logging.getLogger(__name__).info(
                    "Dev env - Qt plugin path: %s", plugin_path
                )
            else:
                logging.getLogger(__name__).warning("Qt plugin path not found")

        except ImportError as e:
            logging.getLogger(__name__).error("Unable to import PySide6: %s", e)
            sys.exit(1)


# Call before importing any PySide6 modules
setup_qt_environment()

logger = logging.getLogger(__name__)
logger.debug("=== Qt environment configured ===")
qt_platform_path = os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH", "unset")
logger.debug("QT_QPA_PLATFORM_PLUGIN_PATH: %s", qt_platform_path)
qt_plugin_path = os.environ.get("QT_PLUGIN_PATH", "unset")
logger.debug("QT_PLUGIN_PATH: %s", qt_plugin_path)
