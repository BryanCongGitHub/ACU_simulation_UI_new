# 文档索引（中文）

目的
- 本文件为仓库中文档的总览/索引，帮助开发者和发布者快速找到需要的说明文档与维护入口。

主要文档清单
- `README.md`：项目总体说明与快速使用指南（主入口）。
- `README_DEV.md`：开发者指南（开发环境、调试与运行说明）。
- `BUILD.md`：打包/发布相关步骤与注意事项（构建 PyInstaller、制作安装程序等）。
- `TESTS.md`：测试说明与如何运行测试（已在仓库根）。
- `CHANGELOG.md`：变更记录（发布历史/重要改动）。
- `PR_DESCRIPTION.md` / `PR_FEATURE_GUI_MIGRATION_WAVEFORM_SETTINGS.md`：Pull Request 模板与大型变更说明。

其他有用文档与脚本
- `tools/`：包含若干辅助脚本（运行/清理/测试包装器），例如：
  - `tools/run_pytest_no_pyc.ps1`：防止在受限目录写入 `.pyc` 时运行 pytest 的包装脚本。
  - `tools/clean_artifacts.py`：清理 `build/`、`dist/`、`.pytest_cache/` 等。
- `build/acu_simulation.spec`：PyInstaller 打包规范，修改资源须更新该文件。

文档状态与推荐入口
- 推荐阅读顺序（新进开发者）：
  1. `README.md`（快速了解项目）
  2. `README_DEV.md`（搭建开发环境）
  3. `TESTS.md`（测试运行）和 `BUILD.md`（打包发布）
- 若你要进行打包或发布，请优先参考 `BUILD.md` 并在修改 `build/acu_simulation.spec` 后在本地重新构建确认。

如何更新文档（约定）
- 变更影响用户/发布流程时：更新 `CHANGELOG.md` 并在 PR 描述中引用对应条目。
- 开发者/测试相关的变更：更新 `README_DEV.md` 或 `TESTS.md`（视影响范围）。
- 打包或资源变更：同时更新 `BUILD.md` 与 `build/acu_simulation.spec`。

建议的下一步（可选）
- 将关键文档移动到 `docs/` 目录以便通过静态站点（如 GitHub Pages）发布；或在仓库根保留简短索引并把详细文档放到 `docs/`。
- 为 `BUILD.md`、`TESTS.md` 添加元数据头（版本/最后更新者/最后更新时间）。

本索引由开发者自动生成并已提交到 `test` 分支；如需进一步分类（按观众：使用者/开发者/发布者）我可以继续拆分并调整 README 中的链接。
