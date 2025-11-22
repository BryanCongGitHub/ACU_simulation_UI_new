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
