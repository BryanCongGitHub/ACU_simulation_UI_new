from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseProtocol(ABC):
    """设备协议基类：提供构建发送帧与解析接收帧的统一接口。"""

    name: str = "BASE"
    frame_length_send: int = 0
    frame_length_receive: int = 0

    @abstractmethod
    def build_send_frame(self, control_snapshot: Dict[str, Any], life_signal: int) -> bytearray:
        """构建发送帧。返回 bytearray。"""
        raise NotImplementedError

    @abstractmethod
    def parse_receive_frame(self, data: bytes) -> Dict[str, Any]:
        """解析接收帧，返回结构化 dict。"""
        raise NotImplementedError

    @abstractmethod
    def category(self) -> str:
        """返回协议所属设备类别，用于路由。"""
        raise NotImplementedError
