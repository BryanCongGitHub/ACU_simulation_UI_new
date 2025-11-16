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
