````markdown
Review checklist for `feature/gui-migration-waveform-settings`

- Summary:
  - Migrate palette IO into `SettingsDialog` (helpers + UI buttons).
  - Toolbar palette buttons now open `SettingsDialog`; programmatic access still available.
  - Add throttled hover tooltip (`hover_label`) and expose `self.last_hover` for headless tests.
  - Add/adjust pytest-qt tests (hover, thumbnail, CSV header strict checks).
  - Accessibility improvements: keyboard shortcuts and accessible names for key toolbar controls and legend entries.

- Local verification commands

```powershell
# activate environment (example)
conda activate acu_sim_311

# run full test suite
pytest -q

# run subset quickly
pytest -q tests/test_waveform_hover_pytestqt.py
pytest -q tests/test_waveform_thumb_pytestqt.py
pytest -q tests/test_export_csv_strict_pytestqt.py
```

- Files to review
  - `gui/settings_dialog.py` — palette IO helpers and dialog callbacks
  - `waveform_display.py` — toolbar wiring, shortcuts, accessible names, legend rebuild
  - `waveform_plot.py` — hover tooltip logic and `last_hover` exposure
  - `tests/conftest.py` and new/updated tests in `tests/`

- QA notes
  - Tests use monkeypatch to stub `QMessageBox`/`QFileDialog` to avoid blocking UI in headless CI.
  - On Windows/CI, ensure `pyqtgraph` and `numpy` are installed in the test environment.
  - If you want a single-squash commit for this feature branch, consider rebasing locally and force-pushing; coordinate with reviewers to avoid mid-review history rewrites.

- Suggested reviewers
  - @team-gui (UI/UX)
  - @team-testing (pytest-qt / CI)
  - @team-backend (persistence/QSettings)

- Recent changes in this branch (important for reviewers):
  - **Device presets**: Added `infra/device_presets.json` including INV1..INV6 (network parameters and ports).
  - **UI integration**: `gui/main_window.py` now exposes a device preset dropdown, applies preset values to device fields, and marks manual edits as “自定义”.
  - **Persistence**: `infra/settings_store.py` extended to persist the selected `device_preset` using QSettings.
  - **Tests & docs**: Added `tests/test_device_presets_ui.py` (pytest-qt) and `docs/device_presets.md` documenting format and priority vs `acu_config.json`.
  - **Fixes**: Guarded programmatic UI updates with `_applying_preset` to avoid treating preset application as manual edits; resolved pre-commit formatting changes.
  - **Dev/CI**: Added a GitHub Actions workflow to produce a PyInstaller build and upload `dist/` as an artifact for review/QA (see `.github/workflows/pyinstaller_build.yml`).

````