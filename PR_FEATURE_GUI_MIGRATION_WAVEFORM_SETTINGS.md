# PR: refactor(gui): migrate ACUSimulator to `gui.main_window` and add waveform settings persistence

## Summary

This PR moves the UI/worker logic out of the top-level `ACU_simulation.py` into a dedicated module `gui/main_window.py`, centralizes environment/logging initialization, and adds persistence for the waveform display settings.

Branch: `feature/gui-migration-waveform-settings`

Remote branch URL (create PR in browser):
https://github.com/BryanCongGitHub/ACU_simulation_UI_new/pull/new/feature/gui-migration-waveform-settings

---

## What changed

- Move `ACUSimulator` implementation from `ACU_simulation.py` to `gui/main_window.py`.
  - `gui/main_window.py` contains `ACUSimulator`, lightweight `ParseWorker` and `FormatWorker`, worker lifecycle management (start/stop in `QThread`), and a minimal UI required by tests.
- Keep `ACU_simulation.py` as a thin launcher entrypoint importing `ACUSimulator` from `gui.main_window`.
- Add `app/bootstrap.py` with `create_application()` and `run()` helper functions that lazily import Qt and initialize the environment.
- Add `infra/logging_config.py` to centralize logging configuration and idempotent initialization.
- Update `setup_qt_environment.py`:
  - Replace deprecated `QLibraryInfo.location()` with `QLibraryInfo.path()`.
  - Improve robustness when running in packaged (`_MEIPASS`) and dev environments.
- Add `WaveformDisplay` persistence (via `QSettings`) and remember last export path.
- Add `ACUSimulator.closeEvent()` to save waveforms and main-window geometry on exit.
- Add a minimal menu (File→Exit, Help→About) to the main window.
- Testing and linting fixes (black/flake8) and minor refactors to satisfy CI.

---

## Files of interest (high-level)

- `gui/main_window.py` — new main UI module with `ACUSimulator`, workers, and lifecycle.
- `ACU_simulation.py` — thin launcher (imports `ACUSimulator` lazily).
- `app/bootstrap.py` — application factory: `create_application()` and `run()`.
- `infra/logging_config.py` — centralized logging and environment initializer.
- `setup_qt_environment.py` — Qt plugin/qml path setup (deprecation fix).
- `waveform_display.py` — add `QSettings`-based `save_settings()`/`load_settings()` and remember last export path.

---

## Tests

All tests run locally with the repository on `PYTHONPATH` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`:

```
$ env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. pytest -q
34 passed
```

Targeted smoke tests (receive/send) were run individually and passed.

---

## How to review

- Review the high-level refactor in `gui/main_window.py`. The file contains a minimal, test-safe UI and implements the worker lifecycle. Many original UI niceties were intentionally left out to keep the migration incremental and testable.
- Confirm logging and Qt environment setup are correctly centralized in `infra/logging_config.py` and `setup_qt_environment.py`.
- Run the smoke tests locally to validate communication/start/stop flows.

Suggested review steps:
1. Checkout the branch locally:
   ```bash
   git fetch origin feature/gui-migration-waveform-settings
   git checkout feature/gui-migration-waveform-settings
   ```
2. Run tests:
   ```bash
   $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; $env:PYTHONPATH='E:\Codes\py\py_vscode\ACU_simulation_UI'; pytest -q
   ```
3. Manually run the UI (optional, requires PySide6):
   ```bash
   python -m ACU_simulation
   ```

---

## Migration plan / next steps (suggested)

- [ ] Add unit tests for `WaveformDisplay.save_settings` and `load_settings` using a temporary `QSettings` path.
- [ ] Incrementally port additional UI features from the original `ACU_simulation.py` (menus, dialogs, waveform layout persistence, full control widgets).
- [ ] Improve error handling and logging around worker thread shutdown.
- [ ] Prepare changelog entry and update README with new run instructions (`app.bootstrap.run()` or `python -m ACU_simulation`).

---

## Risks & notes

- The `ACUSimulator` in `gui/main_window.py` is intentionally minimal to keep tests passing during migration. Some UI elements from the original monolith are not yet migrated — they will be ported in follow-up PRs.
- `gh` CLI is not available in the environment used to push this branch; open the link above to create the PR in the browser.

---

If you'd like, I can also prepare a short review checklist, add unit tests for the new settings behavior, or create a draft PR description updated with any changes you want before opening the PR.
