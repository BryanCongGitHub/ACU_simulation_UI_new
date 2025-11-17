from __future__ import annotations

import sys
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    # Static-only imports to satisfy type checkers and linters
    from PySide6.QtWidgets import QApplication
    from ACU_simulation import ACUSimulator


def create_application(
    argv: Optional[list[str]] = None,
) -> Tuple["QApplication", "ACUSimulator"]:
    """Create and configure a `QApplication` and the main `ACUSimulator` window.

    This function avoids side-effects at import-time; it performs environment
    initialization and imports PySide6 inside the function so it can be used
    safely by tests that only import the module.
    """
    # Lazy imports to avoid importing Qt at module import time
    from PySide6.QtWidgets import QApplication

    # Initialize environment (logging, Qt plugin paths) before creating QApplication
    try:
        from infra.logging_config import initialize_app_environment

        initialize_app_environment()
    except Exception:
        # Fail-safe: do not raise during environment setup; tests may run without Qt
        pass

    # Create QApplication
    _argv = argv if argv is not None else sys.argv
    app = QApplication(_argv)
    app.setApplicationName("ACU Simulator")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("Railway System")

    # Import the window class lazily so tests can mock or inject dependencies
    from ACU_simulation import ACUSimulator

    window = ACUSimulator()
    return app, window


def run(argv: Optional[list[str]] = None) -> int:
    """Run the full application. Returns the QApplication exit code."""
    app, window = create_application(argv)
    window.show()
    return app.exec()
