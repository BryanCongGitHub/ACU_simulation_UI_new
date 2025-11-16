"""Minimal CI runner for smoke tests without pytest plugins.
Runs send and receive smoke logic deterministically and exits with non-zero
if any expectation fails. Use when pytest plugin autoload causes permission issues.
"""

import os
import sys

# Ensure project root is on sys.path before importing local modules
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication  # noqa: E402

try:
    from ACU_simulation import ACUSimulator  # noqa: E402
    from controllers.parse_controller import ParseController  # noqa: E402
    from controllers.frame_builder import FrameBuilder  # noqa: E402
    from model.control_state import ControlState  # noqa: E402
    from model.device import Device  # noqa: E402
    from model.device import DeviceConfig  # noqa: E402
    from views.event_bus import ViewEventBus  # noqa: E402
except Exception:
    # If imports fail (e.g., running from tests where project root isn't on sys.path),
    # add project root to sys.path and retry.
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

    def update_config(self, **cfg):
        pass

    def setup(self):
        return True

    def start_receive_loop(self):
        self.started = True

    def send(self, data: bytes):
        pass

    def stop(self):
        self.started = False


def run_send_smoke(app):
    print("SMOKE: run_send_smoke - start")
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
    print("SMOKE: ACUSimulator created")
    send_count = {"n": 0}
    bus.waveform_send.connect(
        lambda *_: send_count.__setitem__("n", send_count["n"] + 1)
    )
    print("SMOKE: starting communication")
    win.start_communication()
    print("SMOKE: started; calling send_periodic_data twice")
    win.send_periodic_data()
    win.send_periodic_data()
    print("SMOKE: calling stop_communication")
    win.stop_communication()
    parse_thr = getattr(win, "parse_worker_thread", None)
    fmt_thr = getattr(win, "format_worker_thread", None)
    ok = (
        send_count["n"] >= 2
        and (parse_thr is None or not parse_thr.is_alive())
        and (fmt_thr is None or not fmt_thr.is_alive())
    )
    print(f"SMOKE: run_send_smoke - result send_count={send_count['n']} ok={ok}")
    win.close()
    return ok


def run_recv_smoke(app):
    print("SMOKE: run_recv_smoke - start")
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
    print("SMOKE: ACUSimulator created for recv")
    recv_count = {"n": 0}
    bus.waveform_receive.connect(
        lambda *_: recv_count.__setitem__("n", recv_count["n"] + 1)
    )
    print("SMOKE: starting communication (recv)")
    win.start_communication()
    fake = bytearray(16)
    fake[0:2] = (0x55AA).to_bytes(2, "big")
    fake[2] = 0x42
    print("SMOKE: injecting fake data")
    win.on_data_received_comm(bytes(fake), ("127.0.0.1", 49999))
    win.stop_communication()
    parse_thr = getattr(win, "parse_worker_thread", None)
    fmt_thr = getattr(win, "format_worker_thread", None)
    ok = (
        recv_count["n"] >= 1
        and (parse_thr is None or not parse_thr.is_alive())
        and (fmt_thr is None or not fmt_thr.is_alive())
    )
    print(f"SMOKE: run_recv_smoke - result recv_count={recv_count['n']} ok={ok}")
    win.close()
    return ok


def main():
    print("SMOKE: creating QApplication")
    app = QApplication.instance() or QApplication(sys.argv)
    print("SMOKE: QApplication created")
    ok_send = run_send_smoke(app)
    ok_recv = run_recv_smoke(app)
    if ok_send and ok_recv:
        print("SMOKE CI: OK send & receive")
        sys.exit(0)
    else:
        print(f"SMOKE CI: FAILED send={ok_send} receive={ok_recv}")
        sys.exit(1)


if __name__ == "__main__":
    main()
