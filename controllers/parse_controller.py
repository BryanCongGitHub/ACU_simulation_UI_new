from typing import Dict, Any
from model.protocols.inv_protocol import InvLikeProtocol
from model.protocols.dummy_protocol import DummyProtocol

class ParseController:
    """解析控制器：集中管理协议实例与解析。后续可注册多协议。"""
    def __init__(self):
        self._protocols = {
            'INV': InvLikeProtocol('INV'),
            'CHU': InvLikeProtocol('CHU'),
            'BCC': InvLikeProtocol('BCC')
        }
        # 示例协议注册
        self._protocols['DUMMY'] = DummyProtocol()
        # 端口映射（与旧实现保持一致）
        self._port_map = {
            49153: 'INV1', 49154: 'INV2', 49155: 'INV3', 49156: 'INV4',
            49157: 'INV5', 49158: 'INV6', 49159: 'CHU3', 49160: 'CHU4',
            49161: 'BCC1', 49162: 'BCC2',
            # 示例设备端口 -> DUMMY
            49999: 'DUMMY1'
        }

    def device_type_from_port(self, port: int) -> str:
        return self._port_map.get(port, 'UNKNOWN')

    def category_from_device(self, device_type: str) -> str:
        if device_type.startswith('INV'): return 'INV'
        if device_type.startswith('CHU'): return 'CHU'
        if device_type.startswith('BCC'): return 'BCC'
        if device_type.startswith('DUMMY'): return 'DUMMY'
        return 'UNKNOWN'

    def parse(self, data: bytes, port: int) -> Dict[str, Any]:
        dev_type = self.device_type_from_port(port)
        cat = self.category_from_device(dev_type)
        proto = self._protocols.get(cat)
        if not proto:
            return {'错误': f'未知设备类型: {dev_type}'}
        return proto.parse_receive_frame(data)
