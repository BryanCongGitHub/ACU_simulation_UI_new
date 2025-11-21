# 优化计划清单

以下任务用于指导接下来对 ACU 仿真器的重构与优化工作，按优先级大致排序：

1. [x] **统一配置持久化入口**
   - 已创建 `infra/settings_store.py`，并将 `WaveformDisplay`、`SettingsDialog`、`ACUSimulator` 主窗口的设备配置加载/保存逻辑迁移到该模块。
   - 当前集中化 helper 支持默认值合并、分组导入导出与统一 flush，后续需要时可继续扩展更多偏好项。

2. [x] **信号管理解耦**
   - `signal_manager.py` 现从 `signal_definitions.json` 加载默认信号，并在导入阶段校验必需字段与数值类型，缺失或异常都会写入日志。
   - 后续若需要，可在外部工具中复用该 JSON，也可继续扩展校验策略（目前覆盖 byte/bit/scale 等关键字段）。

3. [x] **波形 UI 回归测试**
   - 新增 `tests/test_waveform_display_regressions.py`，覆盖自动范围持久化、时间范围恢复、配色映射以及信号树勾选同步等核心交互。
   - 后续如需扩展到更多 UI 细节（例如缩放操作），可在此文件继续追加场景。

4. [x] **线程与定时器退出流程**
   - `ACUSimulator` 新增 `_stop_timers()`，在 `closeEvent` 中与 worker 停止一起执行，同时调用 `WaveformDisplay.shutdown()` 关闭内部控制器定时器。
   - `WaveformController`/`WaveformDisplay` 提供显式 `shutdown()`，确保退出时不再残留活跃定时器。

5. [x] **文档与指南更新**
   - `README_DEV.md` 新增 “Waveform display quick start” 小节，覆盖信号筛选、配色管理、范围切换与缩略图导出等操作步骤。
   - 后续若需要对终端使用者补充 FAQ，可在该章节下继续扩展。

> 完成以上项目时，请记得同步更新该清单，勾选已完成的条目或补充新的优化想法。

6. [ ] **绘图时间窗口下采样（已实现草案）**
    - 目标：保持 `WaveformPlot.max_display_points`（默认 1000）以保证渲染稳定性，
       同时让 X 轴覆盖用户选择的时间窗口（例如 60s、300s、600s）。
    - 实现：在绘图阶段按时间窗口筛选要显示的时间索引；如果窗口内点数超过 `max_display_points`，
       按块下采样（每块选择最后或代表值）以控制绘图点数。这样能在不增加绘制负担的前提下，
       保证显示跨度与所选时间窗口一致。
    - 状态：已在 `waveform_plot.py` 中实现基于时间窗口的索引选择与按块下采样逻辑（需在长期运行下验证性能）。
    - 后续：添加回归测试，监控长时间运行内存/CPU，必要时改为更复杂的聚合策略（如每块取平均或最大值）。
   - 回归测试已添加：`tests/test_waveform_downsampling.py` 覆盖多种采样间隔与时间窗口组合，确保 `DataBuffer.get_window_indices` 与绘图下采样逻辑在高/中/低采样率下按预期工作。
   - CI：已在 `.github/workflows/ci.yml` 中新增 `waveform-regression` job（矩阵覆盖 sample-intervals），用于在 CI 中并行验证下采样回归。该 job 使用 `xvfb` 在无头环境运行特定回归测试，以避免在 PR 主 CI 中阻塞所有测试（可按需改为 nightly）。
   - 状态：回归测试与 CI job 已添加并在本地通过；建议在合并到主分支后观察 CI 运行成本并决定是否将该 job 调整为 nightly 触发。
