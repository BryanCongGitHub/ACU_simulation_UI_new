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

````
