import struct
import pytest
from model.control_state import ControlState
from model.device import Device
from model.device import DeviceConfig
from controllers.frame_builder import FrameBuilder


def test_life_wraps_at_65536():
    cs = ControlState()
    cfg = DeviceConfig(name="WRAP", ip="127.0.0.1", send_port=50000)
    dev = Device(cfg)
    # set life to max
    dev.state.life_signal = 65535
    fb = FrameBuilder(cs, dev)
    buf = fb.build()
    # after increment it should wrap to 0
    assert int.from_bytes(buf[0:2], "big") == 0


def test_build_raises_on_frequency_overflow():
    cs = ControlState()
    # set a huge freq that will overflow 16-bit when multiplied by 10
    cs.freq_controls[10] = 7000.0  # raw = 70000
    cfg = DeviceConfig(name="OF", ip="127.0.0.1", send_port=50000)
    dev = Device(cfg)
    fb = FrameBuilder(cs, dev)
    with pytest.raises(struct.error):
        fb.build()


def test_build_raises_on_negative_frequency():
    cs = ControlState()
    cs.freq_controls[10] = -5.0
    cfg = DeviceConfig(name="NEG", ip="127.0.0.1", send_port=50000)
    dev = Device(cfg)
    fb = FrameBuilder(cs, dev)
    with pytest.raises(struct.error):
        fb.build()
