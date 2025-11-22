````markdown
Developer notes
================

This file documents local developer conventions and test runner tips.

Waveform display quick start
----------------------------
这段指南用于帮助测试或演示新的波形视图配置能力。

1. **信号筛选**：
	- 左侧树按类别列出所有可用信号；勾选后即刻通过 `WaveformController` 拉取数据并在图例区生成条目。
	- 取消勾选会同时从控制器 deselect，并移除对应曲线。

2. **配色管理**：
	- 工具栏的“配色操作…”下拉包含保存、加载、导入、导出四个动作。
	- 保存/加载操作使用集中化设置模块，JSON 被存放在 `WaveformDisplay/palette` 键中；导入/导出针对独立 JSON 文件，字段为 `signal_id -> hex`。
	- 图例中的色块按钮也可快速更改单条曲线颜色。

3. **自动/手动范围**：
	- “自动范围”复选框切换 Y 轴自动缩放；关闭后可通过鼠标缩放、平移调整手动范围。
	- 所有范围设置（自动状态、时间轴下拉值、手动 splitter 配置）都会在关闭时写入 `infra/settings_store`，新实例启动后读取。

4. **即时反馈**：
	- `预览缩略图` 按钮可截取当前绘图快照，便于在 PR 或文档中展示效果。
	- 波形数据导出支持 CSV/JSON，导出路径也会通过集中设置持久化。

若遇到颜色或范围未恢复的情况，可检查 `settings_store.py` 对应的 `WaveformSettings` dataclass；测试文件 `tests/test_waveform_display_regressions.py` 提供回归样例。

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

Final changes in `feature/gui-migration-waveform-settings`
-------------------------------------------------------

The branch consolidates UI migration work for the ACUSimulator waveform view and
adds several UX improvements and test fixes. Summary of the important changes:

- **Compact, interactive legend**: the waveform view now shows a compact legend
	below the plot with a small visibility checkbox, a color swatch button and a
	short label for each selected signal. Clicking the checkbox toggles curve
	visibility; clicking the swatch opens a color picker to change the curve
	color.
- **Palette save / load**: users can save the current signal color mapping into
	`QSettings` (stored as JSON under `WaveformDisplay/palette`) and reload it later
	to restore custom palettes.
- **Programmatic visibility control**: `waveform_plot.py` exposes
	`set_curve_visible(signal_id, visible)` used by the interactive legend.
- **CSV export & UX polish**: improved CSV export headers (use display names),
	thumbnail preview button, theme/legend/grid toggles and signal tree tooltips.
- **Tests & pytest config fixes**: restored a local `qapp` fixture in one test
	and removed a forced `-p pytestqt.plugin` addopt from `pyproject.toml` to avoid
	duplicate pytest-qt plugin registration issues. The full test-suite was run
	locally in the `acu_sim_311` environment and reports `43 passed`.

Developer notes / how this was tested
------------------------------------

- Tests were run locally with `PySide6 6.10.0` and `pytest-qt` available.
- If you prefer to disable plugin auto-discovery (some CI setups), set
	`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and ensure the `pytest-qt` plugin is
	explicitly loaded (or use the provided `run_pytest_no_pyc.bat` / PowerShell
	wrapper). The branch chooses to let pytest auto-discover plugins by default
	to remain compatible with typical developer environments.

If you'd like, I can also add a short QA checklist for the PR (manual steps to
verify color save/load, legend visibility toggles, and CSV export) and a small
UI test that exercises the color-change flow.
 
Palette JSON format example
---------------------------

The palette JSON is a simple mapping of signal id -> hex color string. Example:

```json
{
	"1": "#FF0000",
	"2": "#00FF00",
	"temperature": "#3366FF"
}
```

PR QA checklist
----------------

- Open the waveform view. Select a few signals from the tree.
- Verify the compact legend shows one line per selected signal with a checkbox and color swatch.
- Click a swatch, pick a new color, and confirm the curve color updates immediately.
- Toggle the checkbox to hide/show the curve.
- Click `保存配色`, then `导出配色` and confirm a JSON file is written.
- Click `导入配色` with the exported file and confirm colors are applied.
- Export CSV for selected signals and confirm header uses signal display names.
- Click `预览缩略图` and confirm a thumbnail appears in the toolbar.
CI UI Test Results (artifact)
-----------------------------
CI runs targeted UI tests (palette save/load and legend interaction) and uploads
the captured pytest output as an artifact named `ui-tests-output`. Reviewers can
download this artifact from the Actions run for quick validation without the CI
modifying repository files. Example usage:

1. Open the GitHub Actions run for the workflow.
2. Download the `ui-tests-output` artifact from the run's Artifacts section.
3. Inspect `ui_tests_output.txt` for pytest output and timestamps.

If you prefer the CI to append results into `README_DEV.md` instead, tell me and
I will switch back to the commit-and-push behavior (note: that requires write
permissions for the Actions runner and may be blocked by branch protections).

PR 测试输出摘要（已保存）
---------------------------------
下面是可粘贴到 PR 描述的测试输出摘要，我已将其保存到此处以便留存。包含变更要点、运行命令、示例 pytest 输出块，以及 CI artifact 的说明。

变更摘要
- 将波形视图的配色保存/加载、交互图例等功能补充进 UI，并新增相应测试。
- CI 已配置运行针对性的 UI 测试并把输出以 artifact (`ui-tests-output`) 上传，便于 Reviewers 下载查看。

包含的测试
- `tests/test_palette_save_load_pytestqt.py` — 验证 palette 保存到 `QSettings` 并能成功恢复到曲线颜色。
- `tests/test_legend_interaction_pytestqt.py` — 验证交互式图例的颜色编辑与可见性切换（用 `QColorDialog` 的模拟返回）。

如何在本地复现（PowerShell）
```powershell
$env:PYTHONPATH = "E:\Codes\py\py_vscode\ACU_simulation_UI"
$env:QT_QPA_PLATFORM = "offscreen"
pytest -q tests/test_palette_save_load_pytestqt.py tests/test_legend_interaction_pytestqt.py
```

示例 pytest 输出（示意）
```
tests/test_palette_save_load_pytestqt.py . 
tests/test_legend_interaction_pytestqt.py . 

2 passed in 0.8s
```

CI 行为 / Artifact
- CI workflow 会运行上述两个测试并把完整输出写入 `ui_tests_output.txt`，然后上传为 Actions artifact 名为 `ui-tests-output`。Reviewers 可在对应 Actions 运行页面的 Artifacts 区下载该文件查看完整日志与时间戳。

注意（CI 状态）
- 我注意到最近一次 CI 运行显示未通过（见 Actions 列表）。请在 GitHub Actions 的该 workflow 运行页面检查：
	1. 下载 `ui-tests-output` artifact（如果存在）并查看 pytest 日志；
	2. 查看 Actions 日志中具体失败步骤和 traceback；
	3. 若需要，我可以帮你解析失败日志并提出修复建议。

如果你希望我把 pytest 输出也写回 PR 描述（供审核时直接可见），我可以从 artifact 中提取并生成一个 ready-to-paste 的文本块。

Add these steps to the PR description so reviewers can quickly validate the UX.

````
