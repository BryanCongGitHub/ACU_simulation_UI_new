from __future__ import annotations

import copy
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from protocols.template_runtime.loader import ProtocolTemplateLoader
from protocols.template_runtime.schema import (
    FaultMapSpec,
    SendLayoutFieldSpec,
    SendLayoutReservedRangeSpec,
    SendLayoutWordFieldSpec,
    StatusFlagSpec,
    TemplateSpec,
    ValueFieldSpec,
)

from infra.app_paths import resource_path

PREF_VERSION = 1
PREF_STORAGE_KEY = "protocol_field_selection"
SEND_PREF_CATEGORY = "__send__"

DEFAULT_SEND_KEYS: List[str] = [
    "bool_commands:8:0",
    "bool_commands:8:1",
    "bool_commands:8:2",
    "bool_commands:8:6",
    "bool_commands:8:7",
    "bool_commands:9:0",
    "bool_commands:9:1",
    "bool_commands:9:2",
    "isolation_commands:64:0",
    "isolation_commands:64:1",
    "isolation_commands:64:2",
    "isolation_commands:64:3",
    "isolation_commands:64:4",
    "isolation_commands:64:5",
    "start_commands:65:0",
    "start_commands:65:1",
    "start_commands:65:2",
    "start_commands:65:3",
    "start_commands:65:4",
    "start_commands:65:5",
    "freq_controls:10",
    "freq_controls:12",
    "freq_controls:14",
    "freq_controls:16",
    "start_times:142",
    "branch_voltages:154",
    "branch_voltages:156",
    "battery_temp:158",
]


@dataclass(frozen=True)
class TemplateFieldMeta:
    label: str
    location: str
    source: Optional[str] = None
    detail: Optional[str] = None
    note: Optional[str] = None
    key: Optional[str] = None
    byte: Optional[int] = None
    bit: Optional[int] = None
    offset: Optional[int] = None
    size: Optional[int] = None


@dataclass(frozen=True)
class FieldSection:
    title: str
    items: List[TemplateFieldMeta]


@dataclass(frozen=True)
class ReceiveCategoryMeta:
    category: str
    display_name: str
    sections: List[FieldSection]


@dataclass(frozen=True)
class SendFieldInfo:
    key: str
    source: str
    group_title: str
    kind: str
    label: str
    location: str
    order: int
    byte: Optional[int] = None
    bit: Optional[int] = None
    offset: Optional[int] = None
    size: Optional[int] = None
    note: Optional[str] = None
    detail: Optional[str] = None
    scale: Optional[float] = None
    unit: Optional[str] = None


@dataclass(frozen=True)
class ReceiveFieldInfo:
    key: str
    category: str
    section: str
    source: str
    label: str
    location: str
    order: int
    byte: Optional[int] = None
    bit: Optional[int] = None
    offset: Optional[int] = None
    size: Optional[int] = None


class ProtocolFieldService:
    """Expose protocol template metadata and persisted user selections."""

    def __init__(
        self,
        loader: Optional[ProtocolTemplateLoader] = None,
        config_path: Optional[Path] = None,
    ) -> None:
        self._loader = loader or ProtocolTemplateLoader.default()
        default_config = resource_path("acu_config.json", prefer_write=True)
        if not default_config.exists():
            template_config = resource_path("acu_config.json", must_exist=True)
            if template_config.exists() and template_config != default_config:
                try:
                    default_config.parent.mkdir(parents=True, exist_ok=True)
                    default_config.write_text(
                        template_config.read_text(encoding="utf-8"), encoding="utf-8"
                    )
                except OSError:
                    pass
        self._config_path = Path(config_path) if config_path else default_config
        self._send_fields: Dict[str, SendFieldInfo] = {}
        self._receive_fields: Dict[str, ReceiveFieldInfo] = {}
        self._receive_lookup: Dict[Tuple[str, str, str], ReceiveFieldInfo] = {}
        self._default_preferences_cache: Optional[Dict[str, Any]] = None
        self._cached_preferences: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Metadata API
    # ------------------------------------------------------------------
    def get_send_sections(self) -> List[FieldSection]:
        spec = self._loader.spec()
        layout = spec.send_layout
        if layout is None:
            return []

        sections: List[FieldSection] = []

        if layout.life_signal is not None:
            sections.append(
                FieldSection(
                    title="生命信号",
                    items=[
                        self._field_meta_from_layout_field(
                            layout.life_signal, "life_signal"
                        )
                    ],
                )
            )

        if layout.timestamps:
            timestamp_items = [
                self._field_meta_from_layout_field(ts, "timestamps")
                for ts in layout.timestamps
            ]
            sections.append(FieldSection(title="时间戳", items=timestamp_items))

        for group in layout.bool_bitsets:
            section_title = f"布尔位 - {group.label}"
            group_items: List[TemplateFieldMeta] = []
            for bit in group.bits:
                key = self._make_send_key(group.source, byte=bit.byte, bit=bit.bit)
                meta = TemplateFieldMeta(
                    label=bit.label,
                    location=self._format_bit_location(bit.byte, bit.bit),
                    source=group.source,
                    detail="布尔位",
                    note=bit.note,
                    key=key,
                    byte=bit.byte,
                    bit=bit.bit,
                    size=1,
                )
                group_items.append(meta)
                self._register_send_field(
                    SendFieldInfo(
                        key=key,
                        source=group.source,
                        group_title=section_title,
                        kind="bool_bitset",
                        label=bit.label,
                        location=meta.location,
                        order=len(self._send_fields),
                        byte=bit.byte,
                        bit=bit.bit,
                        note=bit.note,
                        detail=meta.detail,
                        size=1,
                    )
                )
            sections.append(FieldSection(title=section_title, items=group_items))

        for packed in layout.packed_bytes:
            section_title = f"打包字节 - {packed.label}"
            packed_items: List[TemplateFieldMeta] = []
            for bit in packed.bits:
                key = self._make_send_key(
                    packed.source, offset=packed.offset, bit=bit.bit
                )
                meta = TemplateFieldMeta(
                    label=bit.label,
                    location=self._format_bit_location(packed.offset, bit.bit),
                    source=packed.source,
                    detail="打包字节",
                    note=bit.note,
                    key=key,
                    offset=packed.offset,
                    bit=bit.bit,
                    size=1,
                )
                packed_items.append(meta)
                self._register_send_field(
                    SendFieldInfo(
                        key=key,
                        source=packed.source,
                        group_title=section_title,
                        kind="packed_bit",
                        label=bit.label,
                        location=meta.location,
                        order=len(self._send_fields),
                        offset=packed.offset,
                        bit=bit.bit,
                        note=bit.note,
                        detail=meta.detail,
                        size=1,
                    )
                )
            sections.append(FieldSection(title=section_title, items=packed_items))

        if layout.word_fields:
            word_items: List[TemplateFieldMeta] = []
            for entry in layout.word_fields:
                key = self._make_send_key(entry.source, offset=entry.offset)
                size = self._word_field_size(entry)
                meta = TemplateFieldMeta(
                    label=entry.label,
                    location=self._format_byte_span(entry.offset, size),
                    source=entry.source,
                    detail=self._format_word_detail(entry),
                    note=entry.note,
                    key=key,
                    offset=entry.offset,
                    size=size,
                )
                word_items.append(meta)
                kind = "scalar_word" if entry.source == "battery_temp" else "word_field"
                self._register_send_field(
                    SendFieldInfo(
                        key=key,
                        source=entry.source,
                        group_title="字长字段",
                        kind=kind,
                        label=entry.label,
                        location=meta.location,
                        order=len(self._send_fields),
                        offset=entry.offset,
                        size=size,
                        note=entry.note,
                        detail=meta.detail,
                        scale=entry.scale,
                        unit=entry.unit,
                    )
                )
            sections.append(FieldSection(title="字长字段", items=word_items))

        if layout.reserved_ranges:
            reserved_items = [
                TemplateFieldMeta(
                    label=entry.label,
                    location=self._format_byte_span(
                        entry.start, entry.end - entry.start + 1
                    ),
                    source=None,
                    detail=self._format_reserved_detail(entry),
                    note=entry.note,
                )
                for entry in layout.reserved_ranges
            ]
            sections.append(FieldSection(title="预留区", items=reserved_items))

        return sections

    def get_receive_meta(self) -> Tuple[List[FieldSection], List[ReceiveCategoryMeta]]:
        spec = self._loader.spec()
        common_sections = self._build_common_sections(spec)
        category_sections = [
            self._build_category_sections(cat_spec)
            for cat_spec in spec.categories.values()
        ]
        return common_sections, category_sections

    def send_field_infos(self) -> Dict[str, SendFieldInfo]:
        self._ensure_indexes()
        return dict(self._send_fields)

    def receive_field_infos(self) -> Dict[str, ReceiveFieldInfo]:
        self._ensure_indexes()
        return dict(self._receive_fields)

    def find_receive_field(
        self, category: str, section: str, label: str
    ) -> Optional[ReceiveFieldInfo]:
        self._ensure_indexes()
        return self._receive_lookup.get((category, section, label))

    # ------------------------------------------------------------------
    # Preferences API
    # ------------------------------------------------------------------
    def default_preferences(self) -> Dict[str, Any]:
        if self._default_preferences_cache is not None:
            return copy.deepcopy(self._default_preferences_cache)
        self._ensure_indexes()
        send_defaults = [key for key in DEFAULT_SEND_KEYS if key in self._send_fields]
        receive_defaults: Dict[str, List[str]] = {}
        for info in sorted(self._receive_fields.values(), key=lambda item: item.order):
            receive_defaults.setdefault(info.category, []).append(info.key)
        defaults = {
            "version": PREF_VERSION,
            "send": send_defaults,
            "receive": receive_defaults,
        }
        self._default_preferences_cache = defaults
        return copy.deepcopy(defaults)

    def get_active_preferences(self) -> Dict[str, Any]:
        if self._cached_preferences is not None:
            return copy.deepcopy(self._cached_preferences)
        saved = self._load_preferences_from_disk()
        defaults = self.default_preferences()
        if not saved:
            self._cached_preferences = defaults
        else:
            self._cached_preferences = self._merge_preferences(saved, defaults)
        return copy.deepcopy(self._cached_preferences)

    def save_preferences(self, prefs: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_indexes()
        validated = self._validate_preferences_for_save(prefs)
        data = self._read_config_file()
        data[PREF_STORAGE_KEY] = validated
        self._write_config_file(data)
        defaults = self.default_preferences()
        self._cached_preferences = self._merge_preferences(validated, defaults)
        return copy.deepcopy(self._cached_preferences)

    def reset_preferences(self) -> Dict[str, Any]:
        defaults = self.default_preferences()
        self.save_preferences(defaults)
        return copy.deepcopy(defaults)

    # ------------------------------------------------------------------
    # Internal helpers - metadata
    # ------------------------------------------------------------------
    def _ensure_indexes(self) -> None:
        if not self._send_fields or not self._receive_fields:
            self.get_send_sections()
            self.get_receive_meta()

    def _field_meta_from_layout_field(
        self, field: SendLayoutFieldSpec, source: Optional[str]
    ) -> TemplateFieldMeta:
        size = self._calc_size(field.fmt)
        location = self._format_byte_span(field.offset, size)
        detail = self._format_field_detail(field)
        return TemplateFieldMeta(
            label=field.label,
            location=location,
            source=source,
            detail=detail,
            note=field.note,
            offset=field.offset,
            size=size,
        )

    def _format_field_detail(self, field: SendLayoutFieldSpec) -> str:
        parts = [f"fmt {field.fmt}"]
        if field.range_desc:
            parts.append(f"范围 {field.range_desc}")
        return "，".join(parts)

    def _format_word_detail(self, entry: SendLayoutWordFieldSpec) -> str:
        parts = [f"比例 {entry.scale}"]
        if entry.unit:
            parts.append(f"单位 {entry.unit}")
        return "，".join(parts)

    def _format_reserved_detail(self, entry: SendLayoutReservedRangeSpec) -> str:
        length = entry.end - entry.start + 1
        return f"长度 {length} 字节"

    def _build_common_sections(self, spec: TemplateSpec) -> List[FieldSection]:
        if not spec.device_info:
            return []
        items: List[TemplateFieldMeta] = []
        for field in spec.device_info:
            key = self._make_receive_key("common", "device_info", field.offset)
            meta = self._value_field_meta(field, source="device_info", key=key)
            items.append(meta)
            self._register_receive_field(
                ReceiveFieldInfo(
                    key=key,
                    category="common",
                    section="设备信息",
                    source="device_info",
                    label=field.label,
                    location=meta.location,
                    order=len(self._receive_fields),
                    offset=field.offset,
                    size=meta.size,
                )
            )
        return [FieldSection(title="设备信息", items=items)]

    def _build_category_sections(self, category_spec) -> ReceiveCategoryMeta:
        sections: List[FieldSection] = []

        if category_spec.run_parameters:
            run_items: List[TemplateFieldMeta] = []
            for field in category_spec.run_parameters:
                key = self._make_receive_key(
                    category_spec.category, "run_parameters", field.offset
                )
                meta = self._value_field_meta(field, source="run_parameters", key=key)
                run_items.append(meta)
                self._register_receive_field(
                    ReceiveFieldInfo(
                        key=key,
                        category=category_spec.category,
                        section="运行参数",
                        source="run_parameters",
                        label=field.label,
                        location=meta.location,
                        order=len(self._receive_fields),
                        offset=field.offset,
                        size=meta.size,
                    )
                )
            sections.append(FieldSection(title="运行参数", items=run_items))

        if category_spec.status_flags:
            status_items: List[TemplateFieldMeta] = []
            for flag in category_spec.status_flags:
                key = self._make_receive_key(
                    category_spec.category, "status_flags", flag.byte, bit=flag.bit
                )
                meta = self._status_flag_meta(flag, category_spec.category, key=key)
                status_items.append(meta)
                self._register_receive_field(
                    ReceiveFieldInfo(
                        key=key,
                        category=category_spec.category,
                        section="状态信息",
                        source="status_flags",
                        label=flag.label,
                        location=meta.location,
                        order=len(self._receive_fields),
                        byte=flag.byte,
                        bit=flag.bit,
                        size=1,
                    )
                )
            sections.append(FieldSection(title="状态信息", items=status_items))

        if category_spec.faults:
            fault_items: List[TemplateFieldMeta] = []
            for fault_spec in category_spec.faults:
                fault_items.extend(
                    self._fault_meta_entries(
                        fault_spec,
                        category_spec.category,
                        section_title="故障信息",
                    )
                )
            sections.append(FieldSection(title="故障信息", items=fault_items))

        return ReceiveCategoryMeta(
            category=category_spec.category,
            display_name=category_spec.display_name,
            sections=sections,
        )

    def _value_field_meta(
        self, field: ValueFieldSpec, source: Optional[str], *, key: Optional[str] = None
    ) -> TemplateFieldMeta:
        size = self._calc_size(field.fmt)
        location = self._format_byte_span(field.offset, size)
        parts = [f"fmt {field.fmt}"]
        if field.scale != 1.0:
            parts.append(f"scale {field.scale}")
        detail = "，".join(parts)
        return TemplateFieldMeta(
            label=field.label,
            location=location,
            source=source,
            detail=detail,
            key=key,
            offset=field.offset,
            size=size,
        )

    def _status_flag_meta(
        self,
        flag: StatusFlagSpec,
        source: Optional[str],
        *,
        key: Optional[str] = None,
    ) -> TemplateFieldMeta:
        return TemplateFieldMeta(
            label=flag.label,
            location=self._format_bit_location(flag.byte, flag.bit),
            source=source,
            detail="布尔位",
            key=key,
            byte=flag.byte,
            bit=flag.bit,
            size=1,
        )

    def _fault_meta_entries(
        self,
        fault_spec: FaultMapSpec,
        category: str,
        *,
        section_title: str,
    ) -> List[TemplateFieldMeta]:
        entries: List[TemplateFieldMeta] = []
        for bit, label in fault_spec.bit_labels.items():
            key = self._make_receive_key(category, "faults", fault_spec.byte, bit=bit)
            meta = TemplateFieldMeta(
                label=label,
                location=self._format_bit_location(fault_spec.byte, bit),
                source="faults",
                detail="故障位",
                key=key,
                byte=fault_spec.byte,
                bit=bit,
                size=1,
            )
            entries.append(meta)
            self._register_receive_field(
                ReceiveFieldInfo(
                    key=key,
                    category=category,
                    section=section_title,
                    source="faults",
                    label=label,
                    location=meta.location,
                    order=len(self._receive_fields),
                    byte=fault_spec.byte,
                    bit=bit,
                    size=1,
                )
            )
        return entries

    def _register_send_field(self, info: SendFieldInfo) -> None:
        if info.key not in self._send_fields:
            self._send_fields[info.key] = info

    def _register_receive_field(self, info: ReceiveFieldInfo) -> None:
        if info.key not in self._receive_fields:
            self._receive_fields[info.key] = info
        self._receive_lookup[(info.category, info.section, info.label)] = info

    @staticmethod
    def _calc_size(fmt: str) -> int:
        try:
            return struct.calcsize(fmt)
        except struct.error:
            return 1

    @staticmethod
    def _word_field_size(entry: SendLayoutWordFieldSpec) -> int:
        """Return the byte width for a word field entry.

        Current templates describe word fields backed by unsigned 16-bit values.
        Should templates introduce wider fields in the future, this helper can
        be extended to inspect additional metadata.
        """

        # Existing send operations (`dict_u16_scaled`, `scalar_u16_scaled`) map to
        # 16-bit payloads. Default to 2 bytes to match that contract.
        return 2

    @staticmethod
    def _format_byte_span(offset: int, size: int) -> str:
        if size <= 1:
            return f"字节{offset}"
        end = offset + size - 1
        return f"字节{offset}-{end}"

    @staticmethod
    def _format_bit_location(byte: int, bit: int) -> str:
        return f"字节{byte} 位{bit}"

    @staticmethod
    def _make_send_key(
        source: str,
        *,
        byte: Optional[int] = None,
        bit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> str:
        parts: List[str] = [source]
        if byte is not None:
            parts.append(str(byte))
        if offset is not None:
            parts.append(str(offset))
        if bit is not None:
            parts.append(str(bit))
        return ":".join(parts)

    @staticmethod
    def _make_receive_key(
        category: str,
        source: str,
        offset: int,
        *,
        bit: Optional[int] = None,
    ) -> str:
        parts = [category, source, str(offset)]
        if bit is not None:
            parts.append(str(bit))
        return ":".join(parts)

    # ------------------------------------------------------------------
    # Internal helpers - preferences
    # ------------------------------------------------------------------
    def _merge_preferences(
        self, candidate: Dict[str, Any], default: Dict[str, Any]
    ) -> Dict[str, Any]:
        if candidate.get("version") != PREF_VERSION:
            return copy.deepcopy(default)

        merged: Dict[str, Any] = {"version": PREF_VERSION, "send": [], "receive": {}}

        send_keys = candidate.get("send")
        if isinstance(send_keys, list):
            filtered = [key for key in send_keys if key in self._send_fields]
            merged["send"] = filtered
        else:
            merged["send"] = list(default.get("send", []))

        receive_candidate = candidate.get("receive", {})
        if not isinstance(receive_candidate, dict):
            receive_candidate = {}

        receive_defaults: Dict[str, List[str]] = default.get("receive", {})
        receive_merged: Dict[str, List[str]] = {}
        for category, default_keys in receive_defaults.items():
            raw_keys = receive_candidate.get(category)
            if isinstance(raw_keys, list):
                filtered = [
                    key
                    for key in raw_keys
                    if key in self._receive_fields
                    and self._receive_fields[key].category == category
                ]
                receive_merged[category] = filtered
            else:
                receive_merged[category] = list(default_keys)

        # include additional categories from candidate if known to the template
        for category, raw_keys in receive_candidate.items():
            if category in receive_merged:
                continue
            if not isinstance(raw_keys, list):
                continue
            filtered = [
                key
                for key in raw_keys
                if key in self._receive_fields
                and self._receive_fields[key].category == category
            ]
            receive_merged[category] = filtered

        merged["receive"] = receive_merged
        return merged

    def _validate_preferences_for_save(self, prefs: Dict[str, Any]) -> Dict[str, Any]:
        send: List[str] = []
        raw_send = prefs.get("send")
        if isinstance(raw_send, list):
            for key in raw_send:
                if key in self._send_fields and key not in send:
                    send.append(key)

        receive: Dict[str, List[str]] = {}
        raw_receive = prefs.get("receive")
        if isinstance(raw_receive, dict):
            for category in self._known_receive_categories():
                raw_keys = raw_receive.get(category)
                if not isinstance(raw_keys, list):
                    continue
                filtered: List[str] = []
                for key in raw_keys:
                    info = self._receive_fields.get(key)
                    if info and info.category == category and key not in filtered:
                        filtered.append(key)
                receive[category] = filtered

        return {"version": PREF_VERSION, "send": send, "receive": receive}

    def _known_receive_categories(self) -> Iterable[str]:
        self._ensure_indexes()
        categories = sorted(
            {info.category for info in self._receive_fields.values()} - {"common"}
        )
        return ["common", *categories]

    def _load_preferences_from_disk(self) -> Dict[str, Any]:
        data = self._read_config_file()
        pref = data.get(PREF_STORAGE_KEY)
        if isinstance(pref, dict):
            return pref
        return {}

    def _read_config_file(self) -> Dict[str, Any]:
        try:
            if not self._config_path.exists():
                return {}
            content = self._config_path.read_text(encoding="utf-8")
            return json.loads(content)
        except (OSError, ValueError):
            return {}

    def _write_config_file(self, data: Dict[str, Any]) -> None:
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        with self._config_path.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")


__all__ = [
    "ProtocolFieldService",
    "TemplateFieldMeta",
    "FieldSection",
    "ReceiveCategoryMeta",
    "SendFieldInfo",
    "ReceiveFieldInfo",
]
