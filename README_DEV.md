Developer notes
================

This file documents local developer conventions and test runner tips.

PYTEST_DISABLE_PLUGIN_AUTOLOAD
-----------------------------
Some environments (notably certain CI and Windows setups) can fail when pytest plugins attempt to write their plugin cache into site-packages directories that are not writable. To avoid intermittent hangs or errors, set:

- In PowerShell:

  ```powershell
  $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
  ```

- In Bash:

  ```bash
  export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
  ```

This repository includes convenience scripts:

- `run_pytest_no_pyc.bat` - Windows batch runner (already sets the env var)
- `tools/run_pytest_no_pyc.ps1` - PowerShell runner (already sets the env var)

Logging
-------
Modules that produced verbose console output during CI debugging now use the `logging` module so their verbosity can be controlled by the application or test harness.

If you need anything added here, open a PR to update these developer notes.

Running tests locally (headless Qt)
----------------------------------

We run UI tests in a headless Qt mode for CI and local development. Use the following
commands in PowerShell to run the full test-suite in a reproducible environment:

```powershell
$env:PYTHONPATH = "E:\Codes\py\py_vscode\ACU_simulation_UI"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
$env:QT_QPA_PLATFORM = "offscreen"
pytest -q -vv
```

Notes:
- `QT_QPA_PLATFORM=offscreen` disables native windowing so tests that create widgets can run
  on CI runners without a display server.
- We provide `tests/conftest.py` which creates a `QApplication` and patches modal dialogs
  (`QMessageBox`, `QFileDialog`) during tests to avoid blocking interactive prompts.
- If you see warnings about missing fonts from Qt, they are usually harmless in CI; consider
  installing `libfontconfig1` / fonts on the runner if necessary.

CI (GitHub Actions)
--------------------

This repo includes a CI workflow at `.github/workflows/ci.yml` which:
- Installs system libraries required for Qt (xvfb, libfontconfig, libegl, etc.)
- Installs Python dependencies from `requirements-dev.txt` and `pytest-qt`, `PySide6`
- Runs `black --check .` and `flake8 .` to enforce formatting and lint rules
- Runs `pre-commit run --all-files` and then executes the test-suite with `pytest`.

If CI fails on linting steps, run `pre-commit run --all-files` locally and fix or auto-format
with `black .` before pushing.
