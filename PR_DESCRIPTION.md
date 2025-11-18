# PR: UI: add throttled hover tooltip, hover tests, and robust test imports

## 概要

- 在波形绘图组件中新增一个轻量的悬停提示（`QLabel`），用于以节流（150ms）频率显示附近若干信号的时间/值摘要；同时确保 `self.last_hover` 始终更新以便 headless 测试或外部逻辑使用。
- 新增 pytest-qt 覆盖：`tests/test_waveform_hover_pytestqt.py`，验证 `_on_scene_mouse_moved` 能正确填充 `last_hover`。
- 为提高测试在不同环境（Windows / CI / headless）下的稳定性，在 `tests/conftest.py` 中保证将项目根目录加入 `sys.path`（修复此前出现的 ModuleNotFoundError）。
- 修复了少量格式化与 lint 问题（black / flake8），并确保本地测试通过。

## 变更清单（高层）

- 修改：`waveform_plot.py`
  - 新增 `hover_label: QLabel`，添加 150ms UI 节流更新逻辑；
  - 在 `_on_scene_mouse_moved` 中构建简短文本并尝试将 `hover_label` 定位到光标附近；
  - 对 headless / 旧 Qt 环境增加安全回退逻辑（避免抛出）。
- 新增：`tests/test_waveform_hover_pytestqt.py`
  - 通过模拟/替换 `mapSceneToView` 或使用 `WaveformController` 驱动，断言 `last_hover` 包含正确的时间/值。
- 修改：`tests/conftest.py`
  - 在测试会话初始化阶段把项目根插入 `sys.path`，保证顶级包（`controllers`、`gui` 等）按预期被导入。
- 其它：若干文件格式化（black）与 lint 修复（flake8）。

## 动机 / 为什么要做

- UX：快速的悬停摘要帮助用户在查看波形时快速定位并读出附近样本值，无需打开额外面板。
- 性能：通过 150ms 节流，避免高频鼠标移动时频繁重绘导致的性能问题。
- 稳定性：CI 与 Windows 环境在不同 Pytest 导入路径下曾出现 ModuleNotFoundError，`conftest.py` 的修改能显著提高跨环境测试稳定性，减少不必要的 CI 报错噪声。

## 测试

- 本地验证（在 `acu_sim_311` 环境）：
  - 全量测试：`pytest -vv --durations=25` → 全部通过（示例：51 passed）。
  - 单测示例：`pytest -q tests/test_waveform_hover_pytestqt.py` → 新增测试通过。
- 建议 reviewer 在本地或 CI 上运行以下命令复现验证：

```powershell
# 在项目根（已激活 acu_sim_311）运行全部测试
pytest -vv --durations=25

# 或仅运行悬停测试
pytest -q tests/test_waveform_hover_pytestqt.py -q
```

## 审查要点

- 请重点审查 `waveform_plot.py` 中：
  - `hover_label` 的创建与样式（是否满足产品/视觉要求）；
  - 节流阈值（150ms）是否合适，是否需要可配置化；
  - headless/异常回退路径是否充分（不能在无显示环境抛出）。
- `tests/conftest.py`：确认将项目根插入 `sys.path` 的做法是否符合项目约定（该改动用于提高 CI/Windows 的稳定性；如需更严格的包导入策略，可讨论替代方案）。
- 测试：确认新增的 `tests/test_waveform_hover_pytestqt.py` 覆盖了预期场景；如需，也可以补充针对 `hover_label` 可见性/文本的 UI 测试（仅在有显示环境或在能模拟 `views()` 的前提下可靠）。

## 回滚

- 如果需要回退：
  - 回滚 `waveform_plot.py` 的 hover 相关改动；
  - 删除 `tests/test_waveform_hover_pytestqt.py`；
  - 恢复 `tests/conftest.py` 原样（撤销 sys.path 注入）。
- 回滚命令示例（从 PR 分支）：

```bash
git checkout main
git revert <commit-hash>   # 或重置分支/恢复到特定提交，视团队流程而定
```

## QA 建议步骤（手动验证）

1. 启动应用或在 dev 环境打开 `WaveformDisplay` 页面；
2. 将鼠标移动到波形区域，观察是否在光标附近显示小悬停框（或至少 `last_hover` 被填充）；
3. 快速移动鼠标验证没有明显卡顿，且悬停信息跟随更新（节流后约 150ms 更新频率）；
4. 在 headless 环境（CI）确认不会因 UI 操作导致测试失败。

---

> 本文件由自动化助手生成，可按需修改。若需我将该内容直接在 GitHub PR 页面填入并打开 PR（需要授权或你复制粘贴），我也可以协助。