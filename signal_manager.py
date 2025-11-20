# signal_manager.py
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

from PySide6.QtCore import QObject

if TYPE_CHECKING:
    from controllers.protocol_field_service import ProtocolFieldService


SignalInfo = Dict[str, object]


logger = logging.getLogger(__name__)
SIGNAL_DEFINITION_PATH = Path(__file__).with_name("signal_definitions.json")


class SignalManager(QObject):
    """管理所有可显示的信号定义"""

    def __init__(self):
        super().__init__()
        self.signals: Dict[str, SignalInfo] = {}
        self._category_order: List[str] = []
        self.load_signal_definitions()

    def load_signal_definitions(self):
        """加载信号定义"""
        payload = self._read_signal_payload(SIGNAL_DEFINITION_PATH)
        send_signals = self._validate_signal_group(payload.get("send"), "send")
        recv_signals = self._validate_signal_group(payload.get("receive"), "recv")

        self.signals.clear()
        self.signals.update(send_signals)
        self.signals.update(recv_signals)

        if not self.signals:
            logger.warning("未能加载任何信号定义，文件: %s", SIGNAL_DEFINITION_PATH)
            self._category_order = []
            return

        self._finalize_signals()

    def _read_signal_payload(self, path: Path) -> Dict[str, object]:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning("信号定义文件不存在: %s", path)
            return {"send": {}, "receive": {}}
        except Exception:
            logger.exception("读取信号定义文件失败: %s", path)
            return {"send": {}, "receive": {}}

        try:
            data = json.loads(text)
        except Exception:
            logger.exception("解析信号定义文件失败: %s", path)
            return {"send": {}, "receive": {}}

        if not isinstance(data, dict):
            logger.warning("信号定义文件格式无效，应为字典: %s", path)
            return {"send": {}, "receive": {}}
        return data

    def _validate_signal_group(
        self, group: Optional[Dict[str, object]], prefix: str
    ) -> Dict[str, SignalInfo]:
        result: Dict[str, SignalInfo] = {}
        if not isinstance(group, dict):
            return result

        for signal_id, raw in group.items():
            if not isinstance(signal_id, str):
                logger.warning("忽略非字符串的信号 ID: %r", signal_id)
                continue
            if prefix and not signal_id.startswith(f"{prefix}_"):
                logger.warning("信号 ID %s 不符合前缀 %s", signal_id, prefix)
            if not isinstance(raw, dict):
                logger.warning("信号 %s 定义格式无效: 需要字典", signal_id)
                continue

            try:
                byte_value = int(raw.get("byte"))
            except (TypeError, ValueError):
                logger.warning("信号 %s 缺少有效的 byte 字段", signal_id)
                continue

            name = str(raw.get("name", "")).strip() or signal_id
            category = str(raw.get("category", "")).strip() or "未分类"
            sig_type = str(raw.get("type", "")).strip() or "analog"

            entry: SignalInfo = {
                "name": name,
                "category": category,
                "type": sig_type,
                "byte": byte_value,
            }

            color = raw.get("color")
            if color:
                entry["color"] = str(color)

            for field in ("bit", "order"):
                value = raw.get(field)
                if value is not None:
                    try:
                        entry[field] = int(value)
                    except (TypeError, ValueError):
                        logger.warning("信号 %s 的 %s 字段无效", signal_id, field)

            offset_val = raw.get("offset")
            if offset_val is not None:
                try:
                    entry["offset"] = int(offset_val)
                except (TypeError, ValueError):
                    logger.warning("信号 %s 的 offset 字段无效", signal_id)

            scale_val = raw.get("scale")
            if scale_val is not None:
                try:
                    entry["scale"] = float(scale_val)
                except (TypeError, ValueError):
                    logger.warning("信号 %s 的 scale 字段无效", signal_id)

            for field in (
                "unit",
                "display_category",
                "source",
                "section",
                "category_key",
                "group_title",
                "kind",
            ):
                value = raw.get(field)
                if value:
                    entry[field] = str(value)

            result[signal_id] = entry

        return result

    def _finalize_signals(self) -> None:
        """Ensure display metadata and ordering are available for all signals."""

        self._category_order = []
        seen: set[str] = set()

        for signal_id in sorted(self.signals.keys()):
            info = self.signals[signal_id]
            display_category = info.get("display_category") or info.get("category")
            if not display_category:
                display_category = "未分类"
                info["display_category"] = display_category
            else:
                info.setdefault("display_category", display_category)

            if display_category not in seen:
                self._category_order.append(display_category)
                seen.add(display_category)

        per_category_counts: Dict[str, int] = {}
        for signal_id in sorted(self.signals.keys()):
            info = self.signals[signal_id]
            display_category = info.get("display_category") or "未分类"
            if not isinstance(info.get("order"), int):
                info["order"] = per_category_counts.get(display_category, 0)
            per_category_counts[display_category] = info["order"] + 1

    def load_from_protocol(
        self,
        field_service: Optional[ProtocolFieldService],
        preferences: Optional[Dict[str, object]],
    ) -> None:
        """Populate signal definitions from protocol metadata selections."""

        if field_service is None:
            self.load_signal_definitions()
            return

        try:
            send_infos = field_service.send_field_infos()
            receive_infos = field_service.receive_field_infos()
        except Exception:
            self.load_signal_definitions()
            return

        prefs = preferences or {}
        self.signals.clear()
        self._category_order = []

        def _make_signal_id(prefix: str, key: str) -> str:
            safe = (
                str(key)
                .replace("::", "_")
                .replace(":", "_")
                .replace("/", "_")
                .replace(" ", "_")
            )
            return f"{prefix}_{safe}"

        send_selected = prefs.get("send", []) or []
        for order, key in enumerate(send_selected):
            info = send_infos.get(key)
            if info is None:
                continue

            byte_pos = info.byte if info.byte is not None else info.offset
            if byte_pos is None and info.kind in {
                "bool_bitset",
                "packed_bit",
                "word_field",
                "scalar_word",
            }:
                # Without a byte or offset position we cannot sample data reliably.
                continue

            display_category = "发送帧"
            if info.group_title:
                display_category = f"发送帧 - {info.group_title}"

            entry: SignalInfo = {
                "name": info.label,
                "category": "发送帧",
                "display_category": display_category,
                "type": (
                    "bool" if info.kind in {"bool_bitset", "packed_bit"} else "analog"
                ),
                "byte": byte_pos,
                "bit": info.bit,
                "offset": info.offset,
                "source": info.source,
                "order": order,
                "key": info.key,
                "group_title": info.group_title,
                "scale": info.scale,
                "unit": info.unit,
                "kind": info.kind,
            }

            signal_id = _make_signal_id("send", info.key)
            self.signals[signal_id] = entry

        receive_selected: set[str] = set()
        receive_prefs = prefs.get("receive", {}) or {}
        for value in receive_prefs.values():
            if isinstance(value, (list, tuple, set)):
                receive_selected.update(str(k) for k in value)

        ordered_receive = sorted(
            (info for info in receive_infos.values() if info.key in receive_selected),
            key=lambda item: item.order,
        )

        for info in ordered_receive:
            byte_pos = info.byte if info.byte is not None else info.offset
            if byte_pos is None:
                continue

            section = info.section or info.category or "接收帧"
            display_category = f"接收帧 - {section}"
            entry = {
                "name": info.label,
                "category": section,
                "display_category": display_category,
                "type": "bool" if info.bit is not None else "analog",
                "byte": byte_pos,
                "bit": info.bit,
                "offset": info.offset,
                "source": info.source,
                "order": info.order,
                "key": info.key,
                "section": info.section,
                "category_key": info.category,
            }

            signal_id = _make_signal_id("recv", info.key)
            self.signals[signal_id] = entry

        if not self.signals:
            self.load_signal_definitions()
            return

        self._finalize_signals()

    def get_signal_categories(self):
        """获取所有信号分类"""
        if self._category_order:
            return list(self._category_order)

        categories = sorted(
            {
                info.get("display_category") or info.get("category") or "未分类"
                for info in self.signals.values()
            }
        )
        self._category_order = list(categories)
        return list(categories)

    def get_signals_by_category(self, category):
        """获取指定分类的信号"""
        results: List[tuple[str, SignalInfo]] = []
        for signal_id, signal_info in self.signals.items():
            display_category = (
                signal_info.get("display_category")
                or signal_info.get("category")
                or "未分类"
            )
            if display_category == category:
                results.append((signal_id, signal_info))
        results.sort(key=lambda item: item[1].get("order", 0))
        return results

    def get_signal_info(self, signal_id):
        """获取信号信息"""
        return self.signals.get(signal_id)

    def get_all_signals(self):
        """获取所有信号"""
        return self.signals.items()
