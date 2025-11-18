# Changelog

## Unreleased

### Added
- Migrate waveform palette I/O to `SettingsDialog` and expose helpers:
  `save_palette_to_settings`, `load_palette_from_settings`, `export_palette_to_file`,
  `import_palette_from_file`.
- Add a throttled hover tooltip to waveform plots (`hover_label`) with
  a 150ms throttle and expose `self.last_hover` for headless tests.
- Add/adjust pytest-qt UI tests: hover, thumbnail, strict CSV header, and
  palette I/O tests to improve test coverage and CI stability.

### Changed
- Delegate palette save/load/export/import logic from `waveform_display.py`
  to `gui/settings_dialog.py`; remove redundant fallback implementations.
- Improve interactive legend UI and accessibility (accessible names and shortcuts).

### Fixed
- Stabilize test imports and headless behavior in `tests/conftest.py`.

---

_Generated during feature/gui-migration-waveform-settings work._
