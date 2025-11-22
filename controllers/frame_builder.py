import time
from model.control_state import ControlState
from model.device import Device
from model.protocols.inv_protocol import InvLikeProtocol
from protocols.template_runtime.loader import load_template_protocol
from protocols.template_runtime.schema import TemplateConfigError


class FrameBuilder:
    """根据控制状态与协议构建发送帧，解耦 ACUSimulator 的逻辑。"""

    def __init__(self, control_state: ControlState, acu_device: Device):
        self.control_state = control_state
        self.acu_device = acu_device
        # 当前实现中默认走模板协议，若模板不可用则回退到旧实现
        try:
            self.protocol = load_template_protocol("INV")
        except (FileNotFoundError, TemplateConfigError):
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
