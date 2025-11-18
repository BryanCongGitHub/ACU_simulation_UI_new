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