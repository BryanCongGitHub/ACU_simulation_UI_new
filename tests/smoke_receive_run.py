"""
接收路径冒烟测试：
- 使用 Dummy 通信控制器 + 事件总线计数
- 启动通信 -> 触发一次伪造接收帧（DUMMY 协议，端口 49999）
- 验证 bus.waveform_receive 被触发，并检查线程在停止后退出
"""

import os
import sys

# 确保项目根目录在路径中（必须在其它本地导入之前）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402

from ACU_simulation import ACUSimulator  # noqa: E402
from controllers.parse_controller import ParseController  # noqa: E402
from controllers.frame_builder import FrameBuilder  # noqa: E402
from model.control_state import ControlState  # noqa: E402
from model.device import Device  # noqa: E402
from model.device import DeviceConfig  # noqa: E402
from views.event_bus import ViewEventBus  # noqa: E402


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
        pass

    def stop(self):
        self.started = False


def main():
    app = QApplication.instance() or QApplication(sys.argv)

    comm = DummyComm()
    parse = ParseController()
    state = ControlState()
    device = Device(
        DeviceConfig(
            name="ACU",
            ip="127.0.0.1",
            send_port=40000,
            receive_port=40001,
            category="ACU",
        )
    )
    frame = FrameBuilder(state, device)
    bus = ViewEventBus()

    win = ACUSimulator(
        comm=comm,
        parse_controller=parse,
        control_state=state,
        acu_device=device,
        frame_builder=frame,
        view_bus=bus,
    )

    counters = {"recv": 0}

    def on_recv(parsed_data, device_type, ts):
        counters["recv"] += 1
        # 打印一条解析结果摘要
        print(f"recv device={device_type}, fields={list(parsed_data.keys())[:2]}")

    bus.waveform_receive.connect(on_recv)

    def do_start_and_inject():
        win.start_communication()
        # 伪造一帧 DUMMY 协议数据（长度>=16，前2字节生命信号=0x1234，第3字节示例码=0x56）
        fake = bytearray(16)
        fake[0:2] = (0x1234).to_bytes(2, "big")
        fake[2] = 0x56
        # 49999 -> DUMMY1
        if callable(getattr(win.comm, "on_receive", None)):
            win.comm.on_receive(bytes(fake), ("127.0.0.1", 49999))

    def do_stop_and_check():
        win.stop_communication()
        ok_recv = counters["recv"] >= 1
        parse_alive = getattr(win, "parse_worker_thread", None)
        fmt_alive = getattr(win, "format_worker_thread", None)
        parse_ok = (parse_alive is None) or (not parse_alive.is_alive())
        fmt_ok = (fmt_alive is None) or (not fmt_alive.is_alive())
        summary = (
            f"waveform_receive_count>=1: {ok_recv}, "
            f"parse_stopped: {parse_ok}, format_stopped: {fmt_ok}"
        )
        print(summary)
        app.quit()

    QTimer.singleShot(50, do_start_and_inject)
    QTimer.singleShot(500, do_stop_and_check)

    app.exec()


if __name__ == "__main__":
    main()
