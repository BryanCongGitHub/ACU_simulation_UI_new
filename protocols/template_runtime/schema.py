"""Data structures and validation helpers for protocol templates.

The schema intentionally stays lightweight so we can keep the runtime free of
extra dependencies.  The YAML specification is converted into strongly typed
dataclasses that drive the template-based protocol implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class TemplateConfigError(ValueError):
    """Raised when a template specification is malformed."""


@dataclass(frozen=True)
class SendOperationSpec:
    op: str
    source: Optional[str] = None
    offset: Optional[int] = None
    factor: float = 1.0


@dataclass(frozen=True)
class ValueFieldSpec:
    label: str
    offset: int
    fmt: str
    scale: float = 1.0


@dataclass(frozen=True)
class StatusFlagSpec:
    byte: int
    bit: int
    label: str


@dataclass(frozen=True)
class FaultMapSpec:
    byte: int
    bit_labels: Dict[int, str]


@dataclass(frozen=True)
class CategorySpec:
    category: str
    display_name: str
    run_parameters: List[ValueFieldSpec]
    status_flags: List[StatusFlagSpec]
    faults: List[FaultMapSpec]
    frame_length_receive: Optional[int] = None


@dataclass(frozen=True)
class TemplateSpec:
    name: str
    version: int
    frame_length_send: int
    frame_length_receive: int
    send_operations: List[SendOperationSpec]
    device_info: List[ValueFieldSpec]
    categories: Dict[str, CategorySpec]
    send_layout: Optional["SendLayoutSpec"] = None


@dataclass(frozen=True)
class SendLayoutFieldSpec:
    offset: int
    fmt: str
    label: str
    range_desc: Optional[str] = None
    note: Optional[str] = None


@dataclass(frozen=True)
class SendLayoutTimestampSpec(SendLayoutFieldSpec):
    pass


@dataclass(frozen=True)
class SendLayoutBitSpec:
    byte: int
    bit: int
    label: str
    note: Optional[str] = None


@dataclass(frozen=True)
class SendLayoutBitGroupSpec:
    source: str
    label: str
    bits: List[SendLayoutBitSpec]


@dataclass(frozen=True)
class SendLayoutPackedBitSpec:
    bit: int
    label: str
    note: Optional[str] = None


@dataclass(frozen=True)
class SendLayoutPackedByteSpec:
    source: str
    offset: int
    label: str
    bits: List[SendLayoutPackedBitSpec]


@dataclass(frozen=True)
class SendLayoutWordFieldSpec:
    source: str
    offset: int
    label: str
    scale: float
    unit: Optional[str] = None
    note: Optional[str] = None


@dataclass(frozen=True)
class SendLayoutReservedRangeSpec:
    start: int
    end: int
    label: str
    note: Optional[str] = None


@dataclass(frozen=True)
class SendLayoutSpec:
    life_signal: Optional[SendLayoutFieldSpec]
    timestamps: List[SendLayoutTimestampSpec]
    bool_bitsets: List[SendLayoutBitGroupSpec]
    packed_bytes: List[SendLayoutPackedByteSpec]
    word_fields: List[SendLayoutWordFieldSpec]
    reserved_ranges: List[SendLayoutReservedRangeSpec]


def _ensure_int(value: Any, *, context: str) -> int:
    if not isinstance(value, int):
        raise TemplateConfigError(f"{context} must be an integer")
    return value


def _ensure_float(value: Any, *, context: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raise TemplateConfigError(f"{context} must be a number")


def _ensure_str(value: Any, *, context: str) -> str:
    if not isinstance(value, str):
        raise TemplateConfigError(f"{context} must be a string")
    return value


def _ensure_optional_str(value: Any, *, context: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TemplateConfigError(f"{context} must be a string")
    return value


def _parse_send_operations(raw_ops: Any) -> List[SendOperationSpec]:
    if not isinstance(raw_ops, list):
        raise TemplateConfigError("send_operations must be a list")

    supported_ops = {
        "life_signal_u16",
        "dict_bitset",
        "dict_u16_scaled",
        "dict_packed_byte",
        "scalar_u16_scaled",
    }

    ops: List[SendOperationSpec] = []
    for idx, item in enumerate(raw_ops):
        if not isinstance(item, dict):
            raise TemplateConfigError(f"send_operations[{idx}] must be a mapping")
        op_name = _ensure_str(item.get("op"), context=f"send_operations[{idx}].op")
        if op_name not in supported_ops:
            raise TemplateConfigError(
                f"Unsupported send operation '{op_name}' in send_operations[{idx}]"
            )

        source: Optional[str] = None
        if "source" in item:
            source = _ensure_str(
                item["source"], context=f"send_operations[{idx}].source"
            )

        offset: Optional[int] = None
        if "offset" in item:
            offset = _ensure_int(
                item["offset"], context=f"send_operations[{idx}].offset"
            )

        factor = 1.0
        if "factor" in item:
            factor = _ensure_float(
                item["factor"], context=f"send_operations[{idx}].factor"
            )

        if op_name == "life_signal_u16" and offset is None:
            raise TemplateConfigError(
                f"send_operations[{idx}] life_signal_u16 requires 'offset'"
            )
        if op_name != "life_signal_u16" and source is None:
            raise TemplateConfigError(f"send_operations[{idx}] requires 'source'")
        if op_name in {"dict_packed_byte", "scalar_u16_scaled"} and offset is None:
            raise TemplateConfigError(f"send_operations[{idx}] requires 'offset'")
        if op_name in {"dict_u16_scaled", "scalar_u16_scaled"} and "factor" not in item:
            # factor is required for scaled operations so authors specify intent
            raise TemplateConfigError(f"send_operations[{idx}] requires 'factor'")

        ops.append(
            SendOperationSpec(
                op=op_name,
                source=source,
                offset=offset,
                factor=factor,
            )
        )

    return ops


def _parse_value_fields(raw_fields: Any, *, context: str) -> List[ValueFieldSpec]:
    if not isinstance(raw_fields, list):
        raise TemplateConfigError(f"{context} must be a list")

    fields: List[ValueFieldSpec] = []
    for idx, item in enumerate(raw_fields):
        if not isinstance(item, dict):
            raise TemplateConfigError(f"{context}[{idx}] must be a mapping")
        label = _ensure_str(item.get("label"), context=f"{context}[{idx}].label")
        offset = _ensure_int(item.get("offset"), context=f"{context}[{idx}].offset")
        fmt = _ensure_str(item.get("fmt"), context=f"{context}[{idx}].fmt")
        scale = 1.0
        if "scale" in item:
            scale = _ensure_float(item["scale"], context=f"{context}[{idx}].scale")
        fields.append(ValueFieldSpec(label=label, offset=offset, fmt=fmt, scale=scale))
    return fields


def _parse_status_flags(raw_flags: Any, *, context: str) -> List[StatusFlagSpec]:
    if not isinstance(raw_flags, list):
        raise TemplateConfigError(f"{context} must be a list")

    flags: List[StatusFlagSpec] = []
    for idx, item in enumerate(raw_flags):
        if not isinstance(item, dict):
            raise TemplateConfigError(f"{context}[{idx}] must be a mapping")
        byte = _ensure_int(item.get("byte"), context=f"{context}[{idx}].byte")
        bit = _ensure_int(item.get("bit"), context=f"{context}[{idx}].bit")
        label = _ensure_str(item.get("label"), context=f"{context}[{idx}].label")
        flags.append(StatusFlagSpec(byte=byte, bit=bit, label=label))
    return flags


def _parse_fault_maps(raw_faults: Any, *, context: str) -> List[FaultMapSpec]:
    if not isinstance(raw_faults, list):
        raise TemplateConfigError(f"{context} must be a list")

    fault_maps: List[FaultMapSpec] = []
    for idx, item in enumerate(raw_faults):
        if not isinstance(item, dict):
            raise TemplateConfigError(f"{context}[{idx}] must be a mapping")
        byte = _ensure_int(item.get("byte"), context=f"{context}[{idx}].byte")
        bits = item.get("bits")
        if not isinstance(bits, dict) or not bits:
            raise TemplateConfigError(
                f"{context}[{idx}].bits must be a non-empty mapping"
            )

        bit_labels: Dict[int, str] = {}
        for raw_bit, raw_label in bits.items():
            if isinstance(raw_bit, str) and raw_bit.isdigit():
                bit_index = int(raw_bit)
            elif isinstance(raw_bit, int):
                bit_index = raw_bit
            else:
                raise TemplateConfigError(f"{context}[{idx}] bit keys must be integers")
            bit_labels[bit_index] = _ensure_str(
                raw_label, context=f"{context}[{idx}].bits[{bit_index}]"
            )

        fault_maps.append(FaultMapSpec(byte=byte, bit_labels=bit_labels))

    return fault_maps


def parse_template_spec(raw: Dict[str, Any]) -> TemplateSpec:
    if not isinstance(raw, dict):
        raise TemplateConfigError("Template root must be a mapping")

    version = _ensure_int(raw.get("version", 1), context="version")
    metadata = raw.get("metadata", {})
    if not isinstance(metadata, dict):
        raise TemplateConfigError("metadata must be a mapping")

    name = _ensure_str(metadata.get("base_name"), context="metadata.base_name")
    frame_cfg = raw.get("frame_length", {})
    if not isinstance(frame_cfg, dict):
        raise TemplateConfigError("frame_length must be a mapping")
    length_send = _ensure_int(frame_cfg.get("send"), context="frame_length.send")
    length_recv = _ensure_int(frame_cfg.get("receive"), context="frame_length.receive")

    send_ops = _parse_send_operations(raw.get("send_operations", []))

    common = raw.get("receive_common", {})
    if not isinstance(common, dict):
        raise TemplateConfigError("receive_common must be a mapping")
    device_info = _parse_value_fields(
        common.get("device_info", []), context="receive_common.device_info"
    )

    categories_raw = raw.get("categories")
    if not isinstance(categories_raw, dict) or not categories_raw:
        raise TemplateConfigError("categories must be a non-empty mapping")

    categories: Dict[str, CategorySpec] = {}
    for cat_name, cat_raw in categories_raw.items():
        if not isinstance(cat_raw, dict):
            raise TemplateConfigError(f"categories[{cat_name}] must be a mapping")
        display_name = _ensure_str(
            cat_raw.get("display_name", str(cat_name)),
            context=f"categories[{cat_name}].display_name",
        )
        receive = cat_raw.get("receive", {})
        if not isinstance(receive, dict):
            raise TemplateConfigError(
                f"categories[{cat_name}].receive must be a mapping"
            )

        run_parameters = _parse_value_fields(
            receive.get("run_parameters", []),
            context=f"categories[{cat_name}].receive.run_parameters",
        )
        status_flags = _parse_status_flags(
            receive.get("status_flags", []),
            context=f"categories[{cat_name}].receive.status_flags",
        )
        faults = _parse_fault_maps(
            receive.get("faults", []),
            context=f"categories[{cat_name}].receive.faults",
        )

        frame_length_override = None
        if "frame_length_receive" in cat_raw:
            frame_length_override = _ensure_int(
                cat_raw["frame_length_receive"],
                context=f"categories[{cat_name}].frame_length_receive",
            )

        categories[cat_name] = CategorySpec(
            category=cat_name,
            display_name=display_name,
            run_parameters=run_parameters,
            status_flags=status_flags,
            faults=faults,
            frame_length_receive=frame_length_override,
        )

    send_layout = None
    if "send_layout" in raw:
        send_layout = _parse_send_layout(raw.get("send_layout"))

    return TemplateSpec(
        name=name,
        version=version,
        frame_length_send=length_send,
        frame_length_receive=length_recv,
        send_operations=send_ops,
        device_info=device_info,
        categories=categories,
        send_layout=send_layout,
    )


def _parse_send_layout(raw_layout: Any) -> SendLayoutSpec:
    if raw_layout is None:
        return SendLayoutSpec(
            life_signal=None,
            timestamps=[],
            bool_bitsets=[],
            packed_bytes=[],
            word_fields=[],
            reserved_ranges=[],
        )
    if not isinstance(raw_layout, dict):
        raise TemplateConfigError("send_layout must be a mapping")

    life_signal = None
    if "life_signal" in raw_layout:
        life_signal = _parse_layout_field(
            raw_layout.get("life_signal"), context="send_layout.life_signal"
        )

    timestamps = _parse_layout_field_list(
        raw_layout.get("timestamps", []),
        context="send_layout.timestamps",
        field_cls=SendLayoutTimestampSpec,
    )

    bool_bitsets = _parse_bit_group_list(
        raw_layout.get("bool_bitsets", []), context="send_layout.bool_bitsets"
    )

    packed_bytes = _parse_packed_byte_list(
        raw_layout.get("packed_bytes", []), context="send_layout.packed_bytes"
    )

    word_fields = _parse_word_field_list(
        raw_layout.get("word_fields", []), context="send_layout.word_fields"
    )

    reserved_ranges = _parse_reserved_range_list(
        raw_layout.get("reserved_ranges", []),
        context="send_layout.reserved_ranges",
    )

    return SendLayoutSpec(
        life_signal=life_signal,
        timestamps=timestamps,
        bool_bitsets=bool_bitsets,
        packed_bytes=packed_bytes,
        word_fields=word_fields,
        reserved_ranges=reserved_ranges,
    )


def _parse_layout_field(
    raw_field: Any, *, context: str, field_cls=SendLayoutFieldSpec
) -> SendLayoutFieldSpec:
    if not isinstance(raw_field, dict):
        raise TemplateConfigError(f"{context} must be a mapping")
    offset = _ensure_int(raw_field.get("offset"), context=f"{context}.offset")
    fmt = _ensure_str(raw_field.get("fmt"), context=f"{context}.fmt")
    label = _ensure_str(raw_field.get("label"), context=f"{context}.label")
    range_desc = _ensure_optional_str(
        raw_field.get("range"), context=f"{context}.range"
    )
    note = _ensure_optional_str(raw_field.get("note"), context=f"{context}.note")
    return field_cls(
        offset=offset, fmt=fmt, label=label, range_desc=range_desc, note=note
    )


def _parse_layout_field_list(
    raw_fields: Any,
    *,
    context: str,
    field_cls=SendLayoutFieldSpec,
) -> List[SendLayoutFieldSpec]:
    if not isinstance(raw_fields, list):
        raise TemplateConfigError(f"{context} must be a list")
    return [
        _parse_layout_field(item, context=f"{context}[{idx}]", field_cls=field_cls)
        for idx, item in enumerate(raw_fields)
    ]


def _parse_bit_group_list(
    raw_groups: Any, *, context: str
) -> List[SendLayoutBitGroupSpec]:
    if not isinstance(raw_groups, list):
        raise TemplateConfigError(f"{context} must be a list")
    groups: List[SendLayoutBitGroupSpec] = []
    for idx, item in enumerate(raw_groups):
        if not isinstance(item, dict):
            raise TemplateConfigError(f"{context}[{idx}] must be a mapping")
        source = _ensure_str(item.get("source"), context=f"{context}[{idx}].source")
        label = _ensure_str(item.get("label"), context=f"{context}[{idx}].label")
        bits_raw = item.get("bits")
        if not isinstance(bits_raw, list) or not bits_raw:
            raise TemplateConfigError(f"{context}[{idx}].bits must be a non-empty list")
        bits: List[SendLayoutBitSpec] = []
        for bit_idx, bit_item in enumerate(bits_raw):
            if not isinstance(bit_item, dict):
                raise TemplateConfigError(
                    f"{context}[{idx}].bits[{bit_idx}] must be a mapping"
                )
            byte = _ensure_int(
                bit_item.get("byte"), context=f"{context}[{idx}].bits[{bit_idx}].byte"
            )
            bit = _ensure_int(
                bit_item.get("bit"), context=f"{context}[{idx}].bits[{bit_idx}].bit"
            )
            label_bit = _ensure_str(
                bit_item.get("label"), context=f"{context}[{idx}].bits[{bit_idx}].label"
            )
            note = _ensure_optional_str(
                bit_item.get("note"), context=f"{context}[{idx}].bits[{bit_idx}].note"
            )
            bits.append(
                SendLayoutBitSpec(byte=byte, bit=bit, label=label_bit, note=note)
            )
        groups.append(SendLayoutBitGroupSpec(source=source, label=label, bits=bits))
    return groups


def _parse_packed_byte_list(
    raw_list: Any, *, context: str
) -> List[SendLayoutPackedByteSpec]:
    if not isinstance(raw_list, list):
        raise TemplateConfigError(f"{context} must be a list")
    packed_entries: List[SendLayoutPackedByteSpec] = []
    for idx, item in enumerate(raw_list):
        if not isinstance(item, dict):
            raise TemplateConfigError(f"{context}[{idx}] must be a mapping")
        source = _ensure_str(item.get("source"), context=f"{context}[{idx}].source")
        offset = _ensure_int(item.get("offset"), context=f"{context}[{idx}].offset")
        label = _ensure_str(item.get("label"), context=f"{context}[{idx}].label")
        bits_raw = item.get("bits")
        if not isinstance(bits_raw, list) or not bits_raw:
            raise TemplateConfigError(f"{context}[{idx}].bits must be a non-empty list")
        bits: List[SendLayoutPackedBitSpec] = []
        for bit_idx, bit_item in enumerate(bits_raw):
            if not isinstance(bit_item, dict):
                raise TemplateConfigError(
                    f"{context}[{idx}].bits[{bit_idx}] must be a mapping"
                )
            bit = _ensure_int(
                bit_item.get("bit"), context=f"{context}[{idx}].bits[{bit_idx}].bit"
            )
            bit_label = _ensure_str(
                bit_item.get("label"), context=f"{context}[{idx}].bits[{bit_idx}].label"
            )
            note = _ensure_optional_str(
                bit_item.get("note"), context=f"{context}[{idx}].bits[{bit_idx}].note"
            )
            bits.append(SendLayoutPackedBitSpec(bit=bit, label=bit_label, note=note))
        packed_entries.append(
            SendLayoutPackedByteSpec(
                source=source, offset=offset, label=label, bits=bits
            )
        )
    return packed_entries


def _parse_word_field_list(
    raw_list: Any, *, context: str
) -> List[SendLayoutWordFieldSpec]:
    if not isinstance(raw_list, list):
        raise TemplateConfigError(f"{context} must be a list")
    entries: List[SendLayoutWordFieldSpec] = []
    for idx, item in enumerate(raw_list):
        if not isinstance(item, dict):
            raise TemplateConfigError(f"{context}[{idx}] must be a mapping")
        source = _ensure_str(item.get("source"), context=f"{context}[{idx}].source")
        offset = _ensure_int(item.get("offset"), context=f"{context}[{idx}].offset")
        label = _ensure_str(item.get("label"), context=f"{context}[{idx}].label")
        scale = _ensure_float(item.get("scale", 1.0), context=f"{context}[{idx}].scale")
        unit = _ensure_optional_str(item.get("unit"), context=f"{context}[{idx}].unit")
        note = _ensure_optional_str(item.get("note"), context=f"{context}[{idx}].note")
        entries.append(
            SendLayoutWordFieldSpec(
                source=source,
                offset=offset,
                label=label,
                scale=scale,
                unit=unit,
                note=note,
            )
        )
    return entries


def _parse_reserved_range_list(
    raw_list: Any, *, context: str
) -> List[SendLayoutReservedRangeSpec]:
    if not isinstance(raw_list, list):
        raise TemplateConfigError(f"{context} must be a list")
    entries: List[SendLayoutReservedRangeSpec] = []
    for idx, item in enumerate(raw_list):
        if not isinstance(item, dict):
            raise TemplateConfigError(f"{context}[{idx}] must be a mapping")
        start = _ensure_int(item.get("start"), context=f"{context}[{idx}].start")
        end = _ensure_int(item.get("end"), context=f"{context}[{idx}].end")
        label = _ensure_str(item.get("label"), context=f"{context}[{idx}].label")
        note = _ensure_optional_str(item.get("note"), context=f"{context}[{idx}].note")
        entries.append(
            SendLayoutReservedRangeSpec(start=start, end=end, label=label, note=note)
        )
    return entries
