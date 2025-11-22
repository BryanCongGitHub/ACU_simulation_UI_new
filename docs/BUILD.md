````markdown
# 构建说明 — ACU_simulation_UI

本文档说明如何在 Windows 下使用 PyInstaller 构建独立可执行文件（EXE），并推荐使用开发环境 `acu_sim_311` 进行打包，以避免与 Qt / 本地 DLL 的 ABI 不匹配问题。

先决条件
- Windows 10/11 的开发机
- 已创建并安装好 `acu_sim_311`（Python 3.11）的 conda 环境，且该环境中已安装与开发时相同版本的 PySide6
- PyInstaller 6.16.0（或兼容版本）

构建步骤（PowerShell）

1. 激活构建环境：

```powershell
conda activate acu_sim_311
```

2. 安装/确认构建依赖：

```powershell
python -m pip install -U pip setuptools
python -m pip install pyinstaller pyqtgraph pyside6
```

3. 在项目根目录执行 PyInstaller（使用项目内的 spec 文件）：

```powershell
& 'D:\ProgramData\Anaconda3\envs\acu_sim_311\python.exe' -m PyInstaller build\acu_simulation.spec --noconfirm
```

注意事项与说明
- 请务必使用与开发时相同的 Python/Qt 环境（即 `acu_sim_311`），这样 PyInstaller 打包的本地 Qt 与 ICU DLL 才能与 PySide6 wheel 匹配。不同 Python 版本或不同环境可能导致符号/ABI 不匹配（例如丢失 DLL 的入口点），从而在运行时出现 ImportError 或 DLL 加载失败。
- `build/acu_simulation.spec` 已包含 `protocols/templates` 等资源的打包配置；若添加新的资源文件，请相应更新 spec 中的 `datas`。
- 调试已冻结（frozen）可执行文件时，最好在 PowerShell 控制台中运行 EXE 并观察 stdout/stderr，以便获取完整 trace 信息；双击弹窗通常不包含可复制的完整 traceback。

常见故障与排查建议
- 如果出现缺少 MSVC 运行时的错误，请在目标机上安装最新版 Microsoft Visual C++ Redistributable。
- 如果 Qt 插件加载失败，请确认 `dist\ACU_simulation_UI\_internal\PySide6\plugins\platforms` 等插件目录已经被打包，并且 spec 中包含了运行时 hook（`build/pyside6_rth_path.py`），以正确设置 `QT_PLUGIN_PATH`。

进一步帮助
- 若构建仍然失败，请提供以下内容：PyInstaller 的完整构建日志（`build\acu_simulation\*`），以及在 PowerShell 中运行 EXE 时的完整控制台 traceback。我可以基于这些日志继续定位问题。

### 关键代码位置（与打包/运行相关）

下面列出了与构建与运行时行为直接相关的代码文件与说明，方便你在修改代码后更新文档或调整 spec：

- `main.py`：应用入口，包含 `_configure_qt_runtime()`（在 frozen 模式下设置 PATH、调用 `os.add_dll_directory()`、并设置 `QT_PLUGIN_PATH` 等）。如果你更改 Qt 相关启动逻辑，请同时更新 `docs/BUILD.md` 中的“注意事项”并在 PR 描述中记录验证步骤。
- `build/pyside6_rth_path.py`：PyInstaller 运行时 hook，负责将 PySide6 的 DLL 路径注册到 Windows 的 DLL 搜索路径（使用 `AddDllDirectory` / `os.add_dll_directory`）。在修改 PySide6 版本或 plugin 布局时需同步更新该 hook。
- `build/acu_simulation.spec`：PyInstaller spec 文件，`datas` 字段用于把 `protocols/templates`、图标、resources 等一起打包。新增资源后请在此添加对应条目并在本地重建进行验证。
- `protocols/templates/`：模版与配置（例如 `acusim.yaml`），运行时需存在于程序可读路径下；若出现 FileNotFoundError，请把文件加入 spec 的 `datas` 并重建。
- `tools/`：包含若干辅助脚本（如 `run_pytest_no_pyc.ps1`、`clean_artifacts.py`），在 CI 或本地调试时非常有用。

### 常见代码改动与对策

- 修改 Qt 启动/搜索路径（`main.py`）后：先在未打包的解释器下确认 `import PySide6` 无误，再运行 PyInstaller 打包并在控制台运行 EXE 获取错误输出。
- 增加第三方依赖（如新 pip 包）：在构建环境中 `pip install <pkg>` 后再打包，或把该依赖列入 `requirements-dev.txt` 以便 CI 安装。
- 更改打包资源后：修改 `build/acu_simulation.spec` 中 `datas`，并执行 `python -m PyInstaller --clean build\acu_simulation.spec` 以清理旧缓存后重建。

### 在代码中记录变更

当你修改与运行/打包直接相关的代码（如 `main.py`、spec、runtime hook、模板路径解析），建议：

1. 在 `docs/BUILD.md` 或 `docs/README_DEV.md` 中记录变更的要点与所需的额外打包步骤。
2. 在 PR 描述中列出与构建相关的验证步骤（例如：`python -m PyInstaller build\acu_simulation.spec --noconfirm`，运行 EXE 并观察控制台）。

````
