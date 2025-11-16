import os
import sys
import pytest

# 保证项目根在路径中（必须在其它本地导入之前）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

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


@pytest.mark.parametrize("period_ms", [80])
def test_periodic_send_emits_and_threads_stop(qtbot, period_ms):
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
    qtbot.addWidget(win)

    counters = {"send": 0}
    bus.waveform_send.connect(
        lambda *_: counters.__setitem__("send", counters["send"] + 1)
    )

    win.period_spin.setValue(period_ms)
    win.start_communication()
    # 直接调用发送方法避免依赖 QTimer 调度造成测试不稳定
    win.send_periodic_data()
    win.send_periodic_data()
    assert counters["send"] >= 2
    win.stop_communication()

    parse_thread = getattr(win, "parse_worker_thread", None)
    fmt_thread = getattr(win, "format_worker_thread", None)
    assert parse_thread is None or not parse_thread.is_alive()
    assert fmt_thread is None or not fmt_thread.is_alive()
