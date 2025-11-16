"""
轻量 GUI 冒烟测试：
- 通过依赖注入使用 Dummy 通信控制器，无需真实网络
- 启动通信 -> 等待周期发送 -> 停止通信
- 统计事件总线的 waveform_send 次数，验证定时发送
- 验证停止后后台解析/格式化线程已退出
"""

import sys, os
# 确保项目根目录在路径中（便于直接导入 ACU_simulation）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from ACU_simulation import ACUSimulator
from controllers.parse_controller import ParseController
from controllers.frame_builder import FrameBuilder
from model.control_state import ControlState
from model.device import Device, DeviceConfig
from views.event_bus import ViewEventBus


class DummyComm:
    def __init__(self):
        self.on_receive = None
        self.on_error = None
        self.on_status = None
        self.started = False
        self.cfg = {}

    def update_config(self, **kwargs):
        self.cfg.update(kwargs)

    def setup(self):
        return True

    def start_receive_loop(self):
        self.started = True

    def send(self, data: bytes):
        # 不真正发送，仅验证调用链
        pass

    def stop(self):
        self.started = False


def main():
    app = QApplication.instance() or QApplication(sys.argv)

    comm = DummyComm()
    parse = ParseController()
    state = ControlState()
    device = Device(DeviceConfig(name="ACU", ip="127.0.0.1", send_port=40000, receive_port=40001, category="ACU"))
    frame = FrameBuilder(state, device)
    bus = ViewEventBus()

    win = ACUSimulator(comm=comm, parse_controller=parse, control_state=state,
                       acu_device=device, frame_builder=frame, view_bus=bus)

    # 统计周期发送次数
    counters = {"send": 0}
    def on_send(_buf, _ts):
        counters["send"] += 1
    bus.waveform_send.connect(on_send)

    # 设置较快的周期
    win.period_spin.setValue(100)

    def do_start():
        win.start_communication()

    def do_stop_and_check():
        win.stop_communication()
        # 检查发送次数与线程状态
        ok_send = counters["send"] >= 2
        parse_alive = getattr(win, 'parse_worker_thread', None)
        fmt_alive = getattr(win, 'format_worker_thread', None)
        parse_ok = (parse_alive is None) or (not parse_alive.is_alive())
        fmt_ok = (fmt_alive is None) or (not fmt_alive.is_alive())
        print(f"waveform_send_count>=2: {ok_send}, parse_stopped: {parse_ok}, format_stopped: {fmt_ok}")
        app.quit()

    # 调度：启动 -> 500ms 后停止并检查 -> 退出
    QTimer.singleShot(50, do_start)
    QTimer.singleShot(700, do_stop_and_check)

    app.exec()


if __name__ == "__main__":
    main()
