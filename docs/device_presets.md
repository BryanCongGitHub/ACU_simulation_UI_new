# 设备预置（device_presets.json）

本文件说明如何使用和修改仓库中的 `infra/device_presets.json`，用于主窗口设备设置中的“设备类型/预置”下拉列表。

- 文件位置: `infra/device_presets.json`
- 格式: JSON 对象，键为预置名称（例如 `INV1`），值为包含以下字段的对象：
  - `acu_ip`：ACU 的 IP（通常为 `10.2.0.1`）
  - `acu_send_port`：ACU 用于发送的本地端口（字符串或数字）
  - `acu_receive_port`：设备（INV/CHU 等）发送到 ACU 的端口（字符串或数字）
  - `target_ip`：该设备的 IP（例如 `10.2.0.2`）
  - `target_receive_port`：设备用于接收目标数据的端口（通常为 `49152`）

示例条目:

```
"INV1": {
  "acu_ip": "10.2.0.1",
  "acu_send_port": "49152",
  "acu_receive_port": "49153",
  "target_ip": "10.2.0.2",
  "target_receive_port": "49152"
}
```

行为说明:

- 程序会在 `gui/main_window.py` 中加载此 JSON 文件并把键作为下拉项显示在“设备类型”选择框中。
- 选择预置时会自动将相应的 `acu_ip`/端口和 `target_ip`/端口填入设备设置面板。
- 如果用户手动编辑任意 IP/端口字段，下拉会自动切换为 “自定义”，保存时不会写入预置名称（除非用户再次选择一个预置）。

编辑建议:

- 编辑前请先备份 `infra/device_presets.json`。
- 请确保 JSON 格式有效（例如使用 `json.tool` 或在线校验器）。
- 字段可使用字符串或数字；QSettings 存储时会以字符串形式保存。

如果需要，我可以：

- 将新的预置添加到 UI 的下拉项排序（比如将“自定义”放到顶部），
- 或者把预置维护迁移到 `infra/device_presets.yaml` 以支持注释和更易维护的格式（需更新加载逻辑）。

**与 `acu_config.json` 的关系与使用优先级**

下面说明 `infra/device_presets.json`、`acu_config.json`（仓库级默认）和 UI/用户保存（`QSettings`）三者在运行时的作用与优先级：

- 启动加载：程序启动时会读取 `acu_config.json`（项目根）作为全局默认配置，用于填充初始的 ACU/目标 IP 与端口以及 `protocol_field_selection` 等协议偏好。这个文件通常由项目维护者或发行包提供。
- 预置选择（`device_presets.json`）：用户在 UI 的“设备类型/预置”下拉中选择某一项时，程序会立刻用对应预置值更新设备设置面板（IP/端口等），但默认并 **不** 修改 `acu_config.json`。预置用于快速切换设备网络参数和测试场景。
- 手动编辑与“自定义”：当用户在 UI 中手动修改任何 IP/端口字段，下拉会自动切换为“自定义”。此时 UI 显示的值以用户输入为准。
- 应用/保存：用户点击“应用/连接”会把 UI 中当前值应用到运行时（通信控制器），立即生效；若用户随后点击“保存”或程序在退出时保存设置，则这些值会写入 `QSettings`（通过 `infra/settings_store.py`），而不是直接覆盖仓库根下的 `acu_config.json`，除非你显式实现将设置写回该文件。

优先级（从高到低，运行时使用）：

1. 用户手动输入（当前 UI 值）
2. 选中的 `device_presets.json` 中的预置值（当用户选择了预置且未手动覆盖）
3. `QSettings` 中上次保存的值（当有保存且未被手动覆盖时用于初始化 UI）
4. `acu_config.json` 中的仓库默认值（首次启动或无其他保存值时使用）

持久化位置建议：

- 使用 `QSettings`（由 `infra/settings_store.py` 管理）保存用户的最后选择与自定义值（例如 `device_preset` 字段、手动输入的 IP/端口）。这样不同用户或不同机器的运行不会相互影响。`QSettings` 在开发/测试时可配置为写入临时 INI，便于测试。
- 保持 `acu_config.json` 作为发行/版本控制下的默认配置。如果你希望在运行时也能编辑并将更改写回该 JSON 文件，请明确在代码中实现写回逻辑（这通常需要处理权限与分发策略）。

关于是否需要修改 `acu_config.json` 示例：

- 当前仓库中的 `acu_config.json`（示例）包含 `acu_ip`, `acu_send_port`, `acu_receive_port`, `target_ip`, `target_receive_port` 和 `protocol_field_selection`。这个文件可继续作为全局默认，不必须和 `device_presets.json` 的每一条一一对应。
- 如果你希望仓库默认尽可能与常用预置一致，可以手动把 `acu_config.json` 的 `target_ip` 和端口与常用预置（比如 `INV5`）对齐；否则保持现状也没有问题，因为选中预置会覆盖 UI 显示并在应用时生效。

示例（推荐做法）：

- 把 `acu_config.json` 用作“发行默认”；把 `device_presets.json` 用作快速选择列表；把用户经常使用的配置通过 UI 保存到 `QSettings`（这由 `save_device_config` 实现）。

如果你同意，我可以：

- 将 `docs/index.md` 中加入一条链接到本页（我可以自动完成）；
- 或者把 `acu_config.json` 的示例值更新为你希望的默认 preset（我可以替你修改并提交）。
