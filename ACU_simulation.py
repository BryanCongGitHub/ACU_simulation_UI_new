from __future__ import annotations

import sys
import os
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
from infra.logging_config import (
    configure_logging,
    initialize_app_environment as infra_initialize_app_environment,
)

from setup_qt_environment import setup_qt_environment  # noqa: E402

# Ensure Qt environment configured on import unless explicitly skipped
if os.environ.get("ACU_SKIP_QT_ENV_ON_IMPORT", "0") != "1":
    setup_qt_environment()

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

LOG_PATH = BASE_DIR / "acu_simulator.log"

# Module-level logger references; can be initialized at import based on env var
logger = logging.getLogger("ACUSim")
file_handler: RotatingFileHandler | None = None
if os.environ.get("ACU_INIT_LOGGING_ON_IMPORT", "1") == "1":
    logger, file_handler = configure_logging(LOG_PATH)


def initialize_app_environment() -> None:
    """Initialize environment and logging for application entry points.

    Safe to call multiple times (idempotent).
    """
    infra_initialize_app_environment(LOG_PATH)


# Keep this module as a thin entrypoint: import the real UI from gui.main_window
from gui.main_window import ACUSimulator  # noqa: E402


if __name__ == "__main__":
    initialize_app_environment()
    # Local run path: create QApplication and show the window
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("ACU Simulator")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("Railway System")

    window = ACUSimulator()
    window.show()

    sys.exit(app.exec())
