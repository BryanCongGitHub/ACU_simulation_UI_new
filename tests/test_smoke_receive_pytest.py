import sys, os

# 保证项目根在路径中
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

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
        pass

    def stop(self):
        self.started = False


def test_receive_path_emits_and_threads_stop(qtbot):
    comm = DummyComm()
    parse = ParseController()
    state = ControlState()
    device = Device(DeviceConfig(name="ACU", ip="127.0.0.1", send_port=40000, receive_port=40001, category="ACU"))
    frame = FrameBuilder(state, device)
    bus = ViewEventBus()

    win = ACUSimulator(comm=comm, parse_controller=parse, control_state=state,
                       acu_device=device, frame_builder=frame, view_bus=bus)
    qtbot.addWidget(win)

    counters = {"recv": 0}
    def on_recv(*_):
        counters["recv"] += 1
    bus.waveform_receive.connect(on_recv)

    win.start_communication()
    # 注入一帧 DUMMY 数据（端口49999）并同步验证事件总线触发
    fake = bytearray(16)
    fake[0:2] = (0x1234).to_bytes(2, 'big')
    fake[2] = 0x56
    win.on_data_received_comm(bytes(fake), ("127.0.0.1", 49999))
    assert counters["recv"] >= 1
    win.stop_communication()

    parse_thread = getattr(win, 'parse_worker_thread', None)
    fmt_thread = getattr(win, 'format_worker_thread', None)
    assert parse_thread is None or not parse_thread.is_alive()
    assert fmt_thread is None or not fmt_thread.is_alive()
