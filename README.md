# ACU Simulation UI 重构说明

![CI](https://github.com/BryanCongGitHub/ACU_simulation_UI_new/actions/workflows/ci.yml/badge.svg)

文档索引：请参阅仓库根的 `DOCS_INDEX.md`（包含 `BUILD.md`、`TESTS.md` 等文档的快速入口与说明）。

开发者文档：请参阅 `README_DEV.md` 获取开发者运行/测试指引与脚本说明。

本项目已开始从单文件/紧耦合结构重构为 MVC + 可插拔协议 架构，目标：

- 易维护：清晰的 Model / Controller / View 分层，逻辑职责单一。
- 易扩展：新增设备或协议时，仅新增协议类与设备配置，不修改核心窗口。
- 易阅读：发送帧构建、解析、通信、UI 分离。
- 功能不减：保留原全部功能，并逐步迁移；允许并行使用旧界面与新控制层。

## 分层概览

- model/
  - device.py : `Device` / `DeviceConfig` / `DeviceState`
  - control_state.py : 发送控制状态集中管理
  - protocols/ : 协议定义 (`BaseProtocol`, `InvLikeProtocol`)
- controllers/
  - communication_controller.py : UDP收发与状态回调
  - frame_builder.py : 基于控制状态构建发送帧
  - parse_controller.py : 统一解析入口，可注册新协议
- views/
  - 现有 Qt 页面（后续将拆分更细）
  - `waveform_display.py` 等保留作为 View

## 扩展协议示例
新增协议步骤：
1. 在 `model/protocols/` 新建文件，继承 `BaseProtocol` 实现 `build_send_frame` / `parse_receive_frame` / `category`。
2. 在 `parse_controller.py` 注册协议实例。
3. 若需特殊发送构建，在 `frame_builder.py` 中根据设备类别选择不同协议。

示例：已内置 `DummyProtocol`（端口 `49999` → 设备 `DUMMY1` → 类别 `DUMMY`）。收到该端口的16字节数据将按示例解析显示。

## 新增设备示例
1. 在设备注册（待建立集中 registry）中添加 `DeviceConfig`：名称/IP/端口/类别。
2. 控制层即可自动路由解析。发送端（ACU）构建帧不需修改。

## 兼容性
直接运行：

```powershell
python main.py
```

或在代码中自定义依赖（依赖注入）进行启动：

```python
from ACU_simulation import ACUSimulator
from controllers.communication_controller import CommunicationController
from controllers.parse_controller import ParseController
from controllers.frame_builder import FrameBuilder
from model.control_state import ControlState
from model.device import Device, DeviceConfig
from views.event_bus import ViewEventBus

comm = CommunicationController()
parse = ParseController()
state = ControlState()
device = Device(DeviceConfig(name="ACU", ip="10.2.0.1", send_port=49152, receive_port=49156, category="ACU"))
frame = FrameBuilder(state, device)
bus = ViewEventBus()

win = ACUSimulator(comm=comm, parse_controller=parse, control_state=state,
                   acu_device=device, frame_builder=frame, view_bus=bus)
win.show()
```
- 将 `ACUSimulator` 中的发送帧准备逻辑迁移到 `FrameBuilder`。

## 如何继续
如需添加新协议或设备，请在 issue 中说明字段与长度要求；按照上述步骤添加后即可被解析与绘制。欢迎继续优化。

## 测试 & CI

- 本地运行 pytest（需 dev 依赖）：

```powershell
pip install -r requirements-dev.txt
set QT_QPA_PLATFORM=offscreen
pytest -q
```

- 为了避免在系统安装目录无法写入 `.pyc` 导致的权限错误，仓库添加了两个便捷脚本用于在本地/CI 环境中禁用写入字节码：

  - PowerShell 脚本：`tools/run_pytest_no_pyc.ps1`
  - Windows 批处理：`run_pytest_no_pyc.bat`

  用法示例（PowerShell）：

  ```powershell
  cd "E:\Codes\py\py_vscode\ACU_simulation_UI"
  .\tools\run_pytest_no_pyc.ps1  # 默认运行 tests/test_protocol_parser.py
  .\tools\run_pytest_no_pyc.ps1 tests  # 传入路径运行所有测试
  ```

  用法示例（CMD / 双击）：

  ```cmd
  run_pytest_no_pyc.bat
  run_pytest_no_pyc.bat tests
  ```

  说明：这些脚本会临时设置环境变量 `PYTHONDONTWRITEBYTECODE=1` 来防止 pytest 及其插件在系统 site-packages 下写入缓存文件，从而避免权限问题。更稳妥的长期方案仍是在 virtualenv/conda 环境中运行测试。

- 重要用例：
  - `tests/test_smoke_send_pytest.py`：验证启动/停止与周期发送事件。
  - `tests/test_smoke_receive_pytest.py`：验证接收路径解析并分发事件。

- GitHub Actions：`.github/workflows/python-tests.yml` 在 Windows 上使用 PySide6 + pytest-qt 离屏运行。
- Quick / Full 工作流：
  - `quick-tests.yml`（push/PR）：安装 dev 依赖 → `mypy --config-file mypy.ini controllers model tests` → 运行核心单元/集成测试（协议解析、通信控制器、帧构建、UI 集成）。
  - `full-tests.yml`（Nightly + 手动触发）：同样运行 mypy，然后执行 `tools/run_pytest_no_pyc.ps1 tests`，覆盖全部 pytest 用例（包含 smoke pytest 用例与 extra 测试）。

### 清理构建/缓存产物

仓库提供 `tools/clean_artifacts.py` 用于删除打包/缓存目录：

```powershell
cd "E:\Codes\py\py_vscode\ACU_simulation_UI"
python tools/clean_artifacts.py          # 直接清理 build/ dist/ 缓存
python tools/clean_artifacts.py --dry-run # 查看将被清理的路径
```

脚本默认移除：`build/`、`dist/`、`.mypy_cache/`、`.pytest_cache/`、所有 `__pycache__/` 与 `.pyc` 文件，以及 `acu_simulator.log`。如需扩展可在脚本顶部修改列表。

## 项目文件架构（当前工作副本）

## Developer Notes (开发者说明)

下面是开发者在本地运行、调试和在 CI 上稳定执行测试时常用的说明：

PYTEST_DISABLE_PLUGIN_AUTOLOAD
-----------------------------
在某些环境（尤其是 CI 中或 Windows 的系统安装目录）上，pytest 插件会尝试在 site-packages 下写入插件缓存，这可能因没有写权限而导致挂起或失败。为避免这种间歇性问题，推荐在运行测试时禁用插件自动加载：

- PowerShell:

  ```powershell
  $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
  ```

- Bash:

  ```bash
  export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
  ```

仓库已提供便捷脚本（会自动设置上面的环境变量）：

- `tools/run_pytest_no_pyc.ps1` — PowerShell 运行器（已设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 与 `PYTHONDONTWRITEBYTECODE=1`）。
- `run_pytest_no_pyc.bat` — Windows 批处理运行器（已设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 与 `PYTHONDONTWRITEBYTECODE=1`）。

示例（PowerShell）：

```powershell
cd "E:\Codes\py\py_vscode\ACU_simulation_UI"
.\tools\run_pytest_no_pyc.ps1            # 默认运行少量关键测试
.\tools\run_pytest_no_pyc.ps1 tests     # 传入参数运行所有 tests
```

Logging (日志)
---------------
为便于在 CI 或本地控制输出，库中原有的顶层 `print()` 调试信息已替换为 `logging` 调用。日志由 `ACUSim` 根 logger 管理，并在应用入口通过 `configure_logging()` 初始化。测试或特殊场景下可以通过环境变量控制是否在导入时自动初始化日志（详见代码注释）：

- 跳过导入时的 Qt 环境设置：`ACU_SKIP_QT_ENV_ON_IMPORT=1`
- 跳过导入时的日志初始化：`ACU_INIT_LOGGING_ON_IMPORT=0`

如果希望在非主入口脚本中显式初始化环境与日志，可调用：

```python
from ACU_simulation import initialize_app_environment
initialize_app_environment()
```

以上设置与脚本已在 `requirements-dev.txt` 中列出必要的开发依赖（如 `pytest`, `pytest-qt`, `PySide6` 等），用于本地测试与 CI 验证。


项目根目录概览：

- `ACU_simulation.py` : 主窗口，实现了 UI 与控制层的组装（现支持依赖注入）。
- `main.py` : 启动脚本（设置环境后创建 `ACUSimulator`）。
- `README.md` : 本文件。
- `requirements-dev.txt` : 开发/测试依赖（`pytest`, `pytest-qt`, `PySide6` 等）。
- `acu_config.json` : 默认网络/周期配置（可修改）。
- `package.bat` / `build/` / `dist/` : 打包相关产物（`dist/` 中包含打包器产物，可忽略或清理）。

- `controllers/` : 控制器层
  - `communication_controller.py` : UDP 收发管理与回调
  - `parse_controller.py` : 协议注册与统一解析入口
  - `frame_builder.py` : 将 `ControlState` -> 发送帧

- `model/` : 模型层
  - `control_state.py` : 控制状态模型
  - `device.py` : `Device` / `DeviceConfig`
  - `protocols/` : 协议实现（`base.py`, `inv_protocol.py`, `dummy_protocol.py` 等）

- `views/` : 视图相关（小型组件与事件总线）
  - `event_bus.py` : `ViewEventBus`（UI 事件总线）

- 其它 top-level 模块
  - `waveform_display.py`, `waveform_controller.py`, `waveform_plot.py` : 波形显示与绘图逻辑
  - `protocol_parser.py` : 兼容层（保留旧接口以兼容历史测试）
  - `tests/` : 测试用例（包含 smoke 测试与 pytest 用例）

## 重构/优化状态总结

已完成（主要工作项）：

- 将通信管理抽离到 `controllers/communication_controller.py`，并改为可注入的 `ACUSimulator(comm=...)`。
- 提取帧构建逻辑到 `controllers/frame_builder.py`（使用 `ControlState` 与 `Device`）。
- 统一解析入口 `controllers/parse_controller.py`，并注册示例 `DummyProtocol`。
- 引入 `views/event_bus.py` 事件总线，解耦 `waveform_display` 与控制层（发送/接收/记录信号通过总线分发）。
- 添加后台解析/格式化线程的启动/停止管理，确保 `start_communication`/`stop_communication` 幂等且清理队列、线程。
- 支持依赖注入以便测试（已为自动化冒烟测试添加 `tests/smoke_*` 与 `tests/smoke_ci_runner.py`）。

遗留 / 建议优化项（后续可跟进）：

1. `waveform_display` 的“导出数据”功能仍标记为“待实现”。
2. `dist/` 目录中包含的大量 PySide6 打包内置脚本中的 TODO（属于第三方或打包产物），无需修改但可清理打包产物以减小仓库体积。
3. 将 smoke runner 正式纳入 CI：当前添加了 `tests/smoke_ci_runner.py` 用于绕过某些环境下 pytest 插件/断言重写引发的权限问题；建议在 CI 上使用一个用户可写的虚拟环境，或设置环境变量 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 与 `PYTHONDONTWRITEBYTECODE=1` 后再执行 `pytest`。
4. 增强 `CommunicationController.setup()` 的幂等性以便热重载配置时更稳妥：可以在 `setup()` 内部先执行 `stop()` 清理旧 socket，然后重建。
5. 增加更全面的单元测试覆盖（协议解析边界条件、异常路径、UI 交互细节）。

如需我把上述第 1、3、4 项逐一实现（例如补全导出功能、添加 `pytest.ini`、或让 `setup()` 自动做 stop/cleanup），请告知优先级，我会按清单逐项完成并提交对应补丁。