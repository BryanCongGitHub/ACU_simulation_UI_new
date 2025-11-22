````markdown
**项目测试说明（中文）**

概述
- 本仓库使用 `pytest` 作为测试运行框架，包含单元测试、控制器/解析器相关的集成测试和若干 GUI 交互相关的测试（基于 `pytest-qt` 或 pytest 的 GUI 插件）。
- 在我的开发环境（conda 环境 `acu_sim_311` / Python 3.11）中执行全部测试结果为：`72 passed`。

测试结构
- 测试文件位于仓库根的 `tests/` 目录，文件命名通常以 `test_*.py` 或 `*_test.py` 形式出现。
- 常见测试类型：
  - 单元测试：针对单一函数/类的逻辑断言。
  - 集成测试：组件之间交互（例如协议解析、帧构建器）。
  - GUI/交互测试：使用 pytest-qt 或 PySide6 在桌面环境下运行的 UI 测试。

先决条件（Windows）
- 有两种常见方式准备测试环境：使用 Conda 环境或 Python venv。

Conda（推荐，项目开发环境）
```powershell
conda activate acu_sim_311
pip install -r requirements-dev.txt
```

虚拟环境（venv）
```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements-dev.txt
```

快速检查：确认 Python 版本和路径
```powershell
python -V
where python
```

运行全部测试
```powershell
# 使用当前 python 解释器运行 pytest（推荐）
python -m pytest -q
# 或者（如果已在 PATH 中）：
pytest -q
```

运行带输出详情的测试
```powershell
pytest -v
# 或者限制失败次数并生成 junit xml（CI 常用）：
pytest --maxfail=1 --disable-warnings -q --junitxml=report.xml
```

运行单个测试文件或测试用例
```powershell
# 单个文件
pytest tests/test_parse_controller.py -q
# 文件中的单个测试函数
pytest tests/test_parse_controller.py::test_some_behavior -q
# 通过关键字过滤
pytest -k "parse and success" -q
```

生成覆盖率报告
```powershell
pip install coverage
coverage run -m pytest
coverage report -m
coverage html    # 在 htmlcov/ 中查看
```

GUI 测试注意点
- GUI 测试依赖 PySide6（或其他 Qt 绑定）以及桌面环境。Windows 上通常可直接运行；在 CI（Linux）上需要 XVFB 或相应虚拟显示环境。
- 如果 GUI 测试失败，先确认本地能正常启动主程序（`python main.py` 或 `python -m app.bootstrap`）。

没有发现测试时的排查步骤
- 确保 `tests/` 目录存在且测试文件命名符合 `pytest` 发现规则。
- 使用 `python -m pytest -q -vv` 查看更详细的收集/发现信息。
- 确保使用的是你安装了测试依赖的 Python 解释器（见“先决条件”）。

CI 与调试辅助命令
- 推荐的 CI 命令示例（Windows 或 Linux）：
```powershell
# 安装依赖
pip install -r requirements-dev.txt
# 运行测试并输出 junit xml
pytest --maxfail=1 --disable-warnings -q --junitxml=report.xml
```

记录测试输出到文件
```powershell
python -m pytest -q | Tee-Object test-output.txt
```

常见问题与建议
- 如果遇到 Qt 相关的 DLL/符号错误（例如 PySide6 / Qt6Core 载入失败），请确认：
  - 你正在使用与开发环境一致的 Python 版本（本项目推荐 `acu_sim_311`）。
  - 已安装匹配版本的 `PySide6`。
- 如果在 CI 上运行 GUI 测试失败，考虑将 GUI 测试标记为慢用例（`@pytest.mark.slow`）并在 CI 中跳过，或在专用的 GUI runner 环境中运行。

我已在本地运行并验证：
- 命令 `python -m pytest -q` 在当前仓库运行结果为 `72 passed`（耗时约 4.4s）。

如果需要，我可以：
- 把测试输出保存到仓库（例如 `test-results.txt`）并提交；
- 帮你在 CI（GitHub Actions）上写一份测试工作流模板；
- 将 GUI 测试拆分或标记以便在无图形环境下跳过。

---
文件：`TESTS.md`（位于仓库根）

````
