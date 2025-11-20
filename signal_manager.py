# signal_manager.py
from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

from PySide6.QtCore import QObject

if TYPE_CHECKING:
    from controllers.protocol_field_service import ProtocolFieldService


SignalInfo = Dict[str, object]


class SignalManager(QObject):
    """管理所有可显示的信号定义"""

    def __init__(self):
        super().__init__()
        self.signals: Dict[str, SignalInfo] = {}
        self._category_order: List[str] = []
        self.load_signal_definitions()

    def load_signal_definitions(self):
        """加载信号定义"""
        # 发送信号定义
        send_signals: Dict[str, SignalInfo] = {
            # 基本控制命令
            "send_bool_均衡充电模式": {
                "name": "均衡充电模式",
                "category": "发送指令",
                "type": "bool",
                "color": "#FF6B6B",
                "byte": 8,
                "bit": 0,
            },
            "send_bool_停止工作": {
                "name": "停止工作",
                "category": "发送指令",
                "type": "bool",
                "color": "#4ECDC4",
                "byte": 8,
                "bit": 1,
            },
            "send_bool_预发车测试": {
                "name": "预发车测试",
                "category": "发送指令",
                "type": "bool",
                "color": "#45B7D1",
                "byte": 8,
                "bit": 2,
            },
            "send_bool_DCDC3隔离": {
                "name": "DCDC3隔离",
                "category": "发送指令",
                "type": "bool",
                "color": "#96CEB4",
                "byte": 8,
                "bit": 6,
            },
            "send_bool_DCDC4隔离": {
                "name": "DCDC4隔离",
                "category": "发送指令",
                "type": "bool",
                "color": "#FFEAA7",
                "byte": 8,
                "bit": 7,
            },
            "send_bool_故障复位": {
                "name": "故障复位",
                "category": "发送指令",
                "type": "bool",
                "color": "#DDA0DD",
                "byte": 9,
                "bit": 0,
            },
            # 设备控制
            "send_bool_空压机1启动": {
                "name": "空压机1启动",
                "category": "发送指令",
                "type": "bool",
                "color": "#98D8C8",
                "byte": 9,
                "bit": 1,
            },
            "send_bool_空压机2启动": {
                "name": "空压机2启动",
                "category": "发送指令",
                "type": "bool",
                "color": "#F7DC6F",
                "byte": 9,
                "bit": 2,
            },
            # 隔离指令
            "send_bool_INV1隔离": {
                "name": "INV1隔离",
                "category": "隔离指令",
                "type": "bool",
                "color": "#BB8FCE",
                "byte": 64,
                "bit": 0,
            },
            "send_bool_INV2隔离": {
                "name": "INV2隔离",
                "category": "隔离指令",
                "type": "bool",
                "color": "#85C1E9",
                "byte": 64,
                "bit": 1,
            },
            "send_bool_INV3隔离": {
                "name": "INV3隔离",
                "category": "隔离指令",
                "type": "bool",
                "color": "#F8C471",
                "byte": 64,
                "bit": 2,
            },
            "send_bool_INV4隔离": {
                "name": "INV4隔离",
                "category": "隔离指令",
                "type": "bool",
                "color": "#82E0AA",
                "byte": 64,
                "bit": 3,
            },
            "send_bool_INV5隔离": {
                "name": "INV5隔离",
                "category": "隔离指令",
                "type": "bool",
                "color": "#F1948A",
                "byte": 64,
                "bit": 4,
            },
            "send_bool_INV6隔离": {
                "name": "INV6隔离",
                "category": "隔离指令",
                "type": "bool",
                "color": "#AED6F1",
                "byte": 64,
                "bit": 5,
            },
            # 启动指令
            "send_bool_INV1启动": {
                "name": "INV1启动",
                "category": "启动指令",
                "type": "bool",
                "color": "#ABEBC6",
                "byte": 65,
                "bit": 0,
            },
            "send_bool_INV2启动": {
                "name": "INV2启动",
                "category": "启动指令",
                "type": "bool",
                "color": "#F9E79F",
                "byte": 65,
                "bit": 1,
            },
            "send_bool_INV3启动": {
                "name": "INV3启动",
                "category": "启动指令",
                "type": "bool",
                "color": "#D7BDE2",
                "byte": 65,
                "bit": 2,
            },
            "send_bool_INV4启动": {
                "name": "INV4启动",
                "category": "启动指令",
                "type": "bool",
                "color": "#A9CCE3",
                "byte": 65,
                "bit": 3,
            },
            "send_bool_INV5启动": {
                "name": "INV5启动",
                "category": "启动指令",
                "type": "bool",
                "color": "#FAD7A0",
                "byte": 65,
                "bit": 4,
            },
            "send_bool_INV6启动": {
                "name": "INV6启动",
                "category": "启动指令",
                "type": "bool",
                "color": "#A2D9CE",
                "byte": 65,
                "bit": 5,
            },
            # 频率控制
            "send_analog_INV2频率": {
                "name": "INV2频率",
                "category": "模拟量控制",
                "type": "analog",
                "color": "#FF6B6B",
                "byte": 10,
                "unit": "Hz",
            },
            "send_analog_INV3频率": {
                "name": "INV3频率",
                "category": "模拟量控制",
                "type": "analog",
                "color": "#4ECDC4",
                "byte": 12,
                "unit": "Hz",
            },
            "send_analog_INV4频率": {
                "name": "INV4频率",
                "category": "模拟量控制",
                "type": "analog",
                "color": "#45B7D1",
                "byte": 14,
                "unit": "Hz",
            },
            "send_analog_INV5频率": {
                "name": "INV5频率",
                "category": "模拟量控制",
                "type": "analog",
                "color": "#96CEB4",
                "byte": 16,
                "unit": "Hz",
            },
            # 新增发送信号 - 软件版本和生命信号等
            "send_analog_生命信号": {
                "name": "ACU生命信号",
                "category": "设备信息",
                "type": "analog",
                "color": "#FF7F50",
                "byte": 0,
                "unit": "",
            },
            "send_analog_软件编码": {
                "name": "ACU软件编码",
                "category": "设备信息",
                "type": "analog",
                "color": "#9ACD32",
                "byte": 2,
                "unit": "",
            },
            "send_analog_软件版本": {
                "name": "ACU软件版本",
                "category": "设备信息",
                "type": "analog",
                "color": "#1E90FF",
                "byte": 4,
                "unit": "",
            },
        }

        # 接收信号定义
        recv_signals: Dict[str, SignalInfo] = {
            # 状态反馈
            "recv_bool_工作允许反馈": {
                "name": "工作允许反馈",
                "category": "状态反馈",
                "type": "bool",
                "color": "#FF6B6B",
                "byte": 48,
                "bit": 0,
            },
            "recv_bool_工作中状态反馈": {
                "name": "工作中状态反馈",
                "category": "状态反馈",
                "type": "bool",
                "color": "#4ECDC4",
                "byte": 48,
                "bit": 1,
            },
            "recv_bool_隔离及锁定反馈": {
                "name": "隔离及锁定反馈",
                "category": "状态反馈",
                "type": "bool",
                "color": "#45B7D1",
                "byte": 48,
                "bit": 2,
            },
            "recv_bool_总故障反馈": {
                "name": "总故障反馈",
                "category": "状态反馈",
                "type": "bool",
                "color": "#96CEB4",
                "byte": 48,
                "bit": 3,
            },
            "recv_bool_斩波器准备完成": {
                "name": "斩波器准备完成",
                "category": "状态反馈",
                "type": "bool",
                "color": "#FFEAA7",
                "byte": 48,
                "bit": 4,
            },
            "recv_bool_均衡充电模式状态": {
                "name": "均衡充电模式状态",
                "category": "状态反馈",
                "type": "bool",
                "color": "#DDA0DD",
                "byte": 48,
                "bit": 4,
            },
            # 运行参数
            "recv_analog_输出频率": {
                "name": "输出频率",
                "category": "运行参数",
                "type": "analog",
                "color": "#98D8C8",
                "byte": 6,
                "unit": "Hz",
                "scale": 0.1,
            },
            "recv_analog_U相电流": {
                "name": "U相电流",
                "category": "运行参数",
                "type": "analog",
                "color": "#F7DC6F",
                "byte": 8,
                "unit": "A",
                "scale": 0.25,
            },
            "recv_analog_V相电流": {
                "name": "V相电流",
                "category": "运行参数",
                "type": "analog",
                "color": "#BB8FCE",
                "byte": 10,
                "unit": "A",
                "scale": 0.25,
            },
            "recv_analog_W相电流": {
                "name": "W相电流",
                "category": "运行参数",
                "type": "analog",
                "color": "#85C1E9",
                "byte": 12,
                "unit": "A",
                "scale": 0.25,
            },
            "recv_analog_输入电压": {
                "name": "输入电压",
                "category": "运行参数",
                "type": "analog",
                "color": "#F8C471",
                "byte": 14,
                "unit": "V",
                "scale": 0.25,
            },
            "recv_analog_IPM温度": {
                "name": "IPM温度",
                "category": "运行参数",
                "type": "analog",
                "color": "#82E0AA",
                "byte": 24,
                "unit": "°C",
                "scale": 0.1,
            },
            # 新增接收信号 - 设备信息
            "recv_analog_生命信号": {
                "name": "APU生命信号",
                "category": "设备信息",
                "type": "analog",
                "color": "#FF7F50",
                "byte": 0,
                "unit": "",
            },
            "recv_analog_软件编码": {
                "name": "APU软件编码",
                "category": "设备信息",
                "type": "analog",
                "color": "#9ACD32",
                "byte": 2,
                "unit": "",
            },
            "recv_analog_软件版本": {
                "name": "APU软件版本",
                "category": "设备信息",
                "type": "analog",
                "color": "#1E90FF",
                "byte": 4,
                "unit": "",
            },
            # 新增接收信号 - 故障信息相关
            "recv_bool_模块A相管保护": {
                "name": "模块A相管保护",
                "category": "故障信息",
                "type": "bool",
                "color": "#8B0000",
                "byte": 52,
                "bit": 0,
            },
            "recv_bool_模块B相管保护": {
                "name": "模块B相管保护",
                "category": "故障信息",
                "type": "bool",
                "color": "#8B0000",
                "byte": 52,
                "bit": 1,
            },
            "recv_bool_模块C相管保护": {
                "name": "模块C相管保护",
                "category": "故障信息",
                "type": "bool",
                "color": "#8B0000",
                "byte": 52,
                "bit": 2,
            },
            "recv_bool_模块过热": {
                "name": "模块过热",
                "category": "故障信息",
                "type": "bool",
                "color": "#8B0000",
                "byte": 52,
                "bit": 3,
            },
            "recv_bool_模块输出短路过流": {
                "name": "模块输出短路过流",
                "category": "故障信息",
                "type": "bool",
                "color": "#8B0000",
                "byte": 52,
                "bit": 4,
            },
            "recv_bool_模块输出三相不平衡": {
                "name": "模块输出三相不平衡",
                "category": "故障信息",
                "type": "bool",
                "color": "#8B0000",
                "byte": 52,
                "bit": 5,
            },
            "recv_bool_输出过流": {
                "name": "输出过流",
                "category": "故障信息",
                "type": "bool",
                "color": "#8B0000",
                "byte": 52,
                "bit": 6,
            },
            "recv_bool_IPM电流异常": {
                "name": "IPM电流异常",
                "category": "故障信息",
                "type": "bool",
                "color": "#8B0000",
                "byte": 52,
                "bit": 7,
            },
            "recv_bool_模块输出1.5倍过载": {
                "name": "模块输出1.5倍过载",
                "category": "故障信息",
                "type": "bool",
                "color": "#8B0000",
                "byte": 53,
                "bit": 0,
            },
            "recv_bool_模块输出1.2倍过载": {
                "name": "模块输出1.2倍过载",
                "category": "故障信息",
                "type": "bool",
                "color": "#8B0000",
                "byte": 53,
                "bit": 1,
            },
            "recv_bool_Fuse熔断": {
                "name": "Fuse熔断",
                "category": "故障信息",
                "type": "bool",
                "color": "#8B0000",
                "byte": 53,
                "bit": 2,
            },
            "recv_bool_生命信号故障": {
                "name": "生命信号故障",
                "category": "故障信息",
                "type": "bool",
                "color": "#8B0000",
                "byte": 53,
                "bit": 7,
            },
        }

        self.signals.clear()
        self.signals.update(send_signals)
        self.signals.update(recv_signals)
        self._finalize_signals()

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
