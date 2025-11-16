import struct
import time
from model.control_state import ControlState
from model.device import Device, DeviceConfig
from controllers.frame_builder import FrameBuilder


def test_frame_builder_basic_fields():
    cs = ControlState()
    # set a boolean command at byte 8 bit 0
    cs.bool_commands[(8, 0)] = True
    # set frequency at byte 10 -> 50 Hz
    cs.freq_controls[10] = 50
    # set branch voltage at byte 154 -> 100 V
    cs.branch_voltages[154] = 100
    # battery temp
    cs.battery_temp = 30

    dev = Device(DeviceConfig(name='ACU', ip='127.0.0.1', send_port=40000, receive_port=40001, category='ACU'))
    fb = FrameBuilder(cs, dev)

    buf = fb.build()
    assert isinstance(buf, bytearray)
    assert len(buf) == 320

    # life signal was incremented from 0 to 1 by update_life
    life = dev.state.life_signal
    assert life >= 1
    assert int.from_bytes(buf[0:2], 'big') == life

    # boolean bit at byte 8 bit0 set
    assert (buf[8] & 0x01) == 0x01

    # frequency 50Hz -> raw 500 -> check bytes at 10:12
    assert buf[10:12] == struct.pack('>H', 500)

    # branch voltage conversion: stored as raw_v = int(v / 0.25)
    raw_v = int(100 / 0.25)
    assert buf[154:156] == struct.pack('>H', raw_v)

    # battery temp 30 C -> raw = int(30/0.1) = 300
    assert buf[158:160] == struct.pack('>H', 300)
