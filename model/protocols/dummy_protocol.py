from .base import BaseProtocol
from typing import Dict, Any

class DummyProtocol(BaseProtocol):
    """示例协议：简单回显/固定解析，用于演示如何添加新协议。"""
    name = "DUMMY"
    frame_length_send = 32
    frame_length_receive = 16

    def category(self) -> str:
        return "DUMMY"

    def build_send_frame(self, control_snapshot: Dict[str, Any], life_signal: int) -> bytearray:
        buf = bytearray(self.frame_length_send)
        # 写入生命信号到字节0-1
        buf[0:2] = life_signal.to_bytes(2, 'big')
        # 将第2字节写为控制快照中的一个标记（若存在）
        marker = 0
        if 'marker' in control_snapshot:
            marker = int(control_snapshot.get('marker', 0)) & 0xFF
        buf[2] = marker
        return buf

    def parse_receive_frame(self, data: bytes) -> Dict[str, Any]:
        if len(data) < self.frame_length_receive:
            return {'错误': '数据长度不足'}
        life = int.from_bytes(data[0:2], 'big')
        code = data[2]
        return {'设备信息': {'生命信号': life, '示例码': code}, '备注': '这是一个示例协议解析结果'}
