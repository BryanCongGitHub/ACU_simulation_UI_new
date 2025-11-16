import time
from model.control_state import ControlState
from model.device import Device
from model.protocols.inv_protocol import InvLikeProtocol


class FrameBuilder:
    """根据控制状态与协议构建发送帧，解耦 ACUSimulator 的逻辑。"""

    def __init__(self, control_state: ControlState, acu_device: Device):
        self.control_state = control_state
        self.acu_device = acu_device
        # 当前实现中仅一个协议类型（INV_LIKE），可未来扩展
        self.protocol = InvLikeProtocol("INV")

    def build(self) -> bytearray:
        snapshot = self.control_state.snapshot()
        life = self.acu_device.update_life()
        buf = self.protocol.build_send_frame(snapshot, life)
        # 时间戳补充（兼容旧结构）字节2-7 年月日时分秒
        now = time.localtime()
        buf[2] = now.tm_year % 100
        buf[3] = now.tm_mon
        buf[4] = now.tm_mday
        buf[5] = now.tm_hour
        buf[6] = now.tm_min
        buf[7] = now.tm_sec
        return buf
