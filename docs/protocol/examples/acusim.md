# ACUSim Protocol Example

The `acusim.yaml` template reproduces the legacy `InvLikeProtocol` behaviour
for three device categories (INV, CHU, BCC).  This guide highlights the pieces
of the template file and how they map onto concrete behaviour.

## Metadata

```yaml
version: 1
metadata:
    base_name: INV_LIKE
frame_length:
    send: 320
    receive: 64
```

The base name becomes the protocol name surfaced through `BaseProtocol.name`.
All categories use the same frame lengths, but a category may override
`frame_length_receive` if required.

## Send Operations

```yaml
send_operations:
    - op: life_signal_u16
        offset: 0
    - op: dict_bitset
        source: bool_commands
    - op: dict_u16_scaled
        source: freq_controls
        factor: 10
    ...
```

Each operation references keys from the control snapshot returned by
`ControlState.snapshot()`.  For instance, `dict_bitset` iterates over the
`bool_commands` mapping `(byte, bit) -> bool` and sets bits accordingly.  The
`scalar_u16_scaled` operation at the end writes the battery temperature to bytes
158-159 using the same scaling as the legacy implementation.

## Send Layout Metadata

`send_layout` mirrors the authoritative send-frame specification so the template
captures every byte, bit, and scaling factor:

```yaml
send_layout:
    life_signal:
        offset: 0
        fmt: ">H"
        label: CCU生命信号
    timestamps:
        - offset: 2
            label: 年
            fmt: B
        - offset: 3
            label: 月
            fmt: B
    bool_bitsets:
        - source: bool_commands
            label: 基本控制命令
            bits:
                - byte: 8
                    bit: 0
                    label: 均衡充电模式
                - byte: 9
                    bit: 0
                    label: 故障复位命令
    word_fields:
        - source: freq_controls
            offset: 10
            label: CCU给定INV2频率
            scale: 0.1
```

The runtime ignores this metadata today, but it provides an authoritative
reference for UI configuration and future automation.

## Receive Layout

Common fields (生命信号、软件编码、软件版本) live under `receive_common` and are
shared by every category.  Category blocks augment this with run parameters,
status bits, and fault tables:

```yaml
categories:
    INV:
        receive:
            run_parameters:
                - label: 输出频率
                    offset: 6
                    fmt: ">H"
                    scale: 0.1
            status_flags:
                - byte: 48
                    bit: 0
                    label: 工作允许反馈
            faults:
                - byte: 52
                    bits:
                        0: 模块A相管保护
                        ...
```

INV and CHU share the same parameter list and fault map.  CHU adds the
`斩波器准备完成` status bit, while BCC replaces the parameter group and fault
descriptions with its charger-specific mappings.

## Testing

`tests/template_protocol/test_template_protocol.py` compares the template-driven
implementation against the legacy `InvLikeProtocol` for both frame generation
and parsing.  When editing the template, extending these parity tests helps
guarantee backwards compatibility.
