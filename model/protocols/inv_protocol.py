import struct
from typing import Dict, Any
from .base import BaseProtocol


class InvLikeProtocol(BaseProtocol):
    """INV / CHU / BCC 统一协议（接收解析相似，仅差别字段）"""

    name = "INV_LIKE"
    frame_length_send = 320
    frame_length_receive = 64

    def __init__(self, device_category: str):
        self._cat = device_category  # INV / CHU / BCC

    def category(self) -> str:
        return self._cat

    def build_send_frame(
        self, control_snapshot: Dict[str, Any], life_signal: int
    ) -> bytearray:
        buf = bytearray(self.frame_length_send)
        # 生命信号
        life_bytes = bytearray(struct.pack(">H", life_signal))
        buf[0:2] = life_bytes  # type: ignore
        # 时间戳字段由外部补（保持兼容旧逻辑），这里不处理时间 -> 由控制层填充
        # 基本控制命令
        for (byte_pos, bit_pos), value in control_snapshot["bool_commands"].items():
            if value and 0 <= byte_pos < len(buf):
                buf[byte_pos] |= 1 << bit_pos
        # 频率控制
        for byte_pos, hz in control_snapshot["freq_controls"].items():
            raw = int(hz * 10)
            freq_bytes = bytearray(struct.pack(">H", raw))
            if byte_pos + 1 < len(buf):
                buf[byte_pos] = freq_bytes[0]  # type: ignore
                buf[byte_pos + 1] = freq_bytes[1]  # type: ignore
        # 隔离指令 64
        iso_byte = 0
        for i, v in control_snapshot["isolation_commands"].items():
            if v:
                iso_byte |= 1 << i
        if 64 < len(buf):
            buf[64] = iso_byte
        # 启动指令 65
        start_byte = 0
        for i, v in control_snapshot["start_commands"].items():
            if v:
                start_byte |= 1 << i
        if 65 < len(buf):
            buf[65] = start_byte
        # CHU 控制 66
        for (byte_pos, bit_pos), v in control_snapshot["chu_controls"].items():
            if v and byte_pos < len(buf):
                buf[byte_pos] |= 1 << bit_pos
        # 冗余启动 67
        for (byte_pos, bit_pos), v in control_snapshot["redundant_commands"].items():
            if v and byte_pos < len(buf):
                buf[byte_pos] |= 1 << bit_pos
        # 启动时间
        for byte_pos, secs in control_snapshot["start_times"].items():
            raw = bytearray(struct.pack(">H", int(secs)))
            if byte_pos + 1 < len(buf):
                buf[byte_pos] = raw[0]  # type: ignore
                buf[byte_pos + 1] = raw[1]  # type: ignore
        # 支路电压
        for byte_pos, v in control_snapshot["branch_voltages"].items():
            raw_v = int(v / 0.25)
            raw = bytearray(struct.pack(">H", raw_v))
            if byte_pos + 1 < len(buf):
                buf[byte_pos] = raw[0]  # type: ignore
                buf[byte_pos + 1] = raw[1]  # type: ignore
        # 电池温度 158-159
        temp_raw = int(control_snapshot["battery_temp"] / 0.1)
        temp_bytes = bytearray(struct.pack(">H", temp_raw))
        if 158 + 1 < len(buf):
            buf[158] = temp_bytes[0]  # type: ignore
            buf[159] = temp_bytes[1]  # type: ignore
        return buf

    def parse_receive_frame(self, data: bytes) -> Dict[str, Any]:
        if len(data) < self.frame_length_receive:
            return {"错误": "数据长度不足"}
        # 公共结构
        result: Dict[str, Any] = {
            "设备信息": {},
            "运行参数": {},
            "状态信息": {},
            "故障信息": {},
        }
        result["设备信息"]["生命信号"] = struct.unpack(">H", data[0:2])[0]
        result["设备信息"]["软件编码"] = struct.unpack(">H", data[2:4])[0]
        result["设备信息"]["软件版本"] = struct.unpack(">H", data[4:6])[0]

        if self._cat in ["INV", "CHU"]:
            result["运行参数"]["输出频率"] = struct.unpack(">H", data[6:8])[0] * 0.1
            result["运行参数"]["U相电流"] = struct.unpack(">H", data[8:10])[0] * 0.25
            result["运行参数"]["V相电流"] = struct.unpack(">H", data[10:12])[0] * 0.25
            result["运行参数"]["W相电流"] = struct.unpack(">H", data[12:14])[0] * 0.25
            result["运行参数"]["输入电压"] = struct.unpack(">H", data[14:16])[0] * 0.25
            result["运行参数"]["IPM温度"] = struct.unpack(">H", data[24:26])[0] * 0.1
        elif self._cat == "BCC":
            result["运行参数"]["输出电压"] = struct.unpack(">H", data[6:8])[0] * 0.25
            result["运行参数"]["输出电流"] = struct.unpack(">H", data[8:10])[0] * 0.25
            result["运行参数"]["充电电流"] = struct.unpack(">H", data[10:12])[0] * 0.25
            result["运行参数"]["电池温度"] = struct.unpack(">H", data[12:14])[0] * 0.1
            result["运行参数"]["模块温度"] = struct.unpack(">H", data[14:16])[0] * 0.1

        status_byte = data[48]
        result["状态信息"]["工作允许反馈"] = bool(status_byte & 0x01)
        result["状态信息"]["工作中状态反馈"] = bool(status_byte & 0x02)
        result["状态信息"]["隔离及锁定反馈"] = bool(status_byte & 0x04)
        result["状态信息"]["总故障反馈"] = bool(status_byte & 0x08)
        if self._cat == "CHU":
            result["状态信息"]["斩波器准备完成"] = bool(status_byte & 0x10)
        elif self._cat == "BCC":
            result["状态信息"]["均衡充电模式状态"] = bool(status_byte & 0x10)

        fault_byte1 = data[52]
        fault_byte2 = data[53]
        fault_info = []
        if self._cat != "BCC":
            if fault_byte1 & 0x01:
                fault_info.append("模块A相管保护")
            if fault_byte1 & 0x02:
                fault_info.append("模块B相管保护")
            if fault_byte1 & 0x04:
                fault_info.append("模块C相管保护")
            if fault_byte1 & 0x08:
                fault_info.append("模块过热")
            if fault_byte1 & 0x10:
                fault_info.append("模块输出短路过流")
            if fault_byte1 & 0x20:
                fault_info.append("模块输出三相不平衡")
            if fault_byte1 & 0x40:
                fault_info.append("输出过流")
            if fault_byte1 & 0x80:
                fault_info.append("IPM电流异常")
            if fault_byte2 & 0x01:
                fault_info.append("模块输出1.5倍过载")
            if fault_byte2 & 0x02:
                fault_info.append("模块输出1.2倍过载")
            if fault_byte2 & 0x04:
                fault_info.append("Fuse熔断")
            if fault_byte2 & 0x80:
                fault_info.append("生命信号故障")
        else:  # BCC 特殊
            if fault_byte1 & 0x01:
                fault_info.append("原边过流")
            if fault_byte1 & 0x02:
                fault_info.append("输出过压")
            if fault_byte1 & 0x04:
                fault_info.append("输出欠压")
            if fault_byte1 & 0x08:
                fault_info.append("输出过流")
            if fault_byte1 & 0x10:
                fault_info.append("蓄电池充电过流")
            if fault_byte1 & 0x20:
                fault_info.append("模块管保护")
            if fault_byte1 & 0x40:
                fault_info.append("输入熔断器故障")
            if fault_byte1 & 0x80:
                fault_info.append("蓄电池温度过高")
            if fault_byte2 & 0x01:
                fault_info.append("蓄电池温度传感器故障")
            if fault_byte2 & 0x02:
                fault_info.append("模块温度传感器故障")
            if fault_byte2 & 0x04:
                fault_info.append("模块过温")
        result["故障信息"]["故障列表"] = fault_info if fault_info else ["正常"]
        result["故障信息"]["故障数量"] = len(fault_info)
        return result
