"""Adapter that turns a template specification into a protocol instance."""

from __future__ import annotations

import struct
from typing import Any, Dict

from model.protocols.base import BaseProtocol

from ..schema import (
    CategorySpec,
    FaultMapSpec,
    SendOperationSpec,
    TemplateSpec,
    ValueFieldSpec,
)


class TemplateProtocol(BaseProtocol):
    """Protocol implementation driven entirely by a template specification."""

    def __init__(self, spec: TemplateSpec, category_spec: CategorySpec):
        self._spec = spec
        self._category_spec = category_spec
        self.name = spec.name
        self.frame_length_send = spec.frame_length_send
        self.frame_length_receive = (
            category_spec.frame_length_receive or spec.frame_length_receive
        )

    # ------------------------------------------------------------------
    # BaseProtocol API
    # ------------------------------------------------------------------
    def category(self) -> str:  # pragma: no cover - trivial getter
        return self._category_spec.category

    def build_send_frame(
        self, control_snapshot: Dict[str, Any], life_signal: int
    ) -> bytearray:
        buf = bytearray(self.frame_length_send)

        for op in self._spec.send_operations:
            if op.op == "life_signal_u16":
                self._apply_life_signal(buf, op, life_signal)
            elif op.op == "dict_bitset":
                self._apply_dict_bitset(buf, op, control_snapshot)
            elif op.op == "dict_u16_scaled":
                self._apply_dict_u16_scaled(buf, op, control_snapshot)
            elif op.op == "dict_packed_byte":
                self._apply_dict_packed_byte(buf, op, control_snapshot)
            elif op.op == "scalar_u16_scaled":
                self._apply_scalar_u16_scaled(buf, op, control_snapshot)
            else:  # pragma: no cover - guarded by schema validation
                raise RuntimeError(f"Unsupported operation: {op.op}")

        return buf

    def parse_receive_frame(self, data: bytes) -> Dict[str, Any]:
        if len(data) < self.frame_length_receive:
            return {"错误": "数据长度不足"}

        result: Dict[str, Any] = {
            "设备信息": {},
            "运行参数": {},
            "状态信息": {},
            "故障信息": {},
        }

        self._extract_fields(data, self._spec.device_info, result["设备信息"])
        self._extract_fields(
            data, self._category_spec.run_parameters, result["运行参数"]
        )
        self._extract_status_flags(data, result["状态信息"])
        faults = self._extract_faults(data)
        if faults:
            result["故障信息"]["故障列表"] = faults
            result["故障信息"]["故障数量"] = len(faults)
        else:
            result["故障信息"]["故障列表"] = ["正常"]
            result["故障信息"]["故障数量"] = 0

        return result

    # ------------------------------------------------------------------
    # Send-frame helpers
    # ------------------------------------------------------------------
    def _apply_life_signal(
        self, buf: bytearray, op: SendOperationSpec, life_signal: int
    ) -> None:
        if op.offset is None:
            return
        raw = int(max(0, min(0xFFFF, life_signal)))
        buf[op.offset : op.offset + 2] = raw.to_bytes(2, "big")

    def _apply_dict_bitset(
        self,
        buf: bytearray,
        op: SendOperationSpec,
        control_snapshot: Dict[str, Any],
    ) -> None:
        source = op.source or ""
        entries = control_snapshot.get(source, {})
        if not isinstance(entries, dict):
            return
        for key, enabled in entries.items():
            if not enabled:
                continue
            if not isinstance(key, (tuple, list)) or len(key) != 2:
                continue
            byte_idx, bit_idx = key
            if not isinstance(byte_idx, int) or not isinstance(bit_idx, int):
                continue
            if 0 <= byte_idx < len(buf) and 0 <= bit_idx < 8:
                buf[byte_idx] |= 1 << bit_idx

    def _apply_dict_u16_scaled(
        self,
        buf: bytearray,
        op: SendOperationSpec,
        control_snapshot: Dict[str, Any],
    ) -> None:
        source = op.source or ""
        entries = control_snapshot.get(source, {})
        if not isinstance(entries, dict):
            return
        for byte_idx, value in entries.items():
            if not isinstance(byte_idx, int):
                continue
            raw_value = int(float(value) * op.factor)
            raw_value = max(0, min(0xFFFF, raw_value))
            if 0 <= byte_idx < len(buf) - 1:
                buf[byte_idx : byte_idx + 2] = raw_value.to_bytes(2, "big")

    def _apply_dict_packed_byte(
        self,
        buf: bytearray,
        op: SendOperationSpec,
        control_snapshot: Dict[str, Any],
    ) -> None:
        if op.offset is None:
            return
        source = op.source or ""
        entries = control_snapshot.get(source, {})
        if not isinstance(entries, dict):
            return
        packed = 0
        for bit_idx, enabled in entries.items():
            if bool(enabled) and isinstance(bit_idx, int) and 0 <= bit_idx < 8:
                packed |= 1 << bit_idx
        if 0 <= op.offset < len(buf):
            buf[op.offset] = packed

    def _apply_scalar_u16_scaled(
        self,
        buf: bytearray,
        op: SendOperationSpec,
        control_snapshot: Dict[str, Any],
    ) -> None:
        if op.offset is None or op.source is None:
            return
        value = control_snapshot.get(op.source, 0)
        raw_value = int(float(value) * op.factor)
        raw_value = max(0, min(0xFFFF, raw_value))
        if 0 <= op.offset < len(buf) - 1:
            buf[op.offset : op.offset + 2] = raw_value.to_bytes(2, "big")

    # ------------------------------------------------------------------
    # Receive-frame helpers
    # ------------------------------------------------------------------
    def _extract_fields(
        self, data: bytes, fields: list[ValueFieldSpec], out: Dict[str, Any]
    ) -> None:
        for field in fields:
            start = field.offset
            end = start + struct.calcsize(field.fmt)
            if end > len(data):
                continue
            raw = struct.unpack(field.fmt, data[start:end])[0]
            value = raw * field.scale
            out[field.label] = value

    def _extract_status_flags(self, data: bytes, out: Dict[str, Any]) -> None:
        for flag in self._category_spec.status_flags:
            if flag.byte >= len(data):
                continue
            byte_val = data[flag.byte]
            out[flag.label] = bool(byte_val & (1 << flag.bit))

    def _extract_faults(self, data: bytes) -> list[str]:
        faults: list[str] = []
        for entry in self._category_spec.faults:
            self._extract_fault_map(data, entry, faults)
        return faults

    def _extract_fault_map(
        self, data: bytes, spec: FaultMapSpec, faults: list[str]
    ) -> None:
        if spec.byte >= len(data):
            return
        value = data[spec.byte]
        if value == 0:
            return
        for bit, label in spec.bit_labels.items():
            if value & (1 << bit):
                faults.append(label)
