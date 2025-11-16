from types import SimpleNamespace

from model.control_state import ControlState
from model.device import Device
from model.device import DeviceConfig
from controllers.frame_builder import FrameBuilder


def fake_localtime():
    # return an object with tm_year, tm_mon, tm_mday, tm_hour, tm_min, tm_sec
    return SimpleNamespace(
        tm_year=2025, tm_mon=11, tm_mday=15, tm_hour=12, tm_min=34, tm_sec=56
    )


def test_build_writes_timestamp_and_increments_life(monkeypatch):
    cs = ControlState()
    cfg = DeviceConfig(name="TST", ip="127.0.0.1", send_port=50000)
    dev = Device(cfg)
    fb = FrameBuilder(cs, dev)

    # freeze localtime
    monkeypatch.setattr(
        "controllers.frame_builder.time.localtime", lambda: fake_localtime()
    )

    buf1 = fb.build()
    # life first increment -> 1
    assert buf1[0] == 0 and buf1[1] == 1
    # timestamp bytes 2-7
    assert buf1[2] == 2025 % 100
    assert buf1[3] == 11
    assert buf1[4] == 15
    assert buf1[5] == 12
    assert buf1[6] == 34
    assert buf1[7] == 56

    buf2 = fb.build()
    # life increments again -> 2
    assert buf2[0] == 0 and buf2[1] == 2


def test_build_applies_bool_commands():
    cs = ControlState()
    # set a boolean command at byte 10 bit 3
    cs.bool_commands[(10, 3)] = True
    cfg = DeviceConfig(name="TST", ip="127.0.0.1", send_port=50000)
    dev = Device(cfg)
    fb = FrameBuilder(cs, dev)
    buf = fb.build()
    assert (buf[10] & (1 << 3)) != 0


def test_build_encodes_frequency_control():
    cs = ControlState()
    cs.freq_controls[20] = 55.5  # Hz
    cfg = DeviceConfig(name="TST", ip="127.0.0.1", send_port=50000)
    dev = Device(cfg)
    fb = FrameBuilder(cs, dev)
    buf = fb.build()
    raw = (buf[20] << 8) | buf[21]
    assert raw == int(55.5 * 10)


def test_build_encodes_voltage_and_temperature():
    cs = ControlState()
    cs.branch_voltages[100] = 125.0  # volts
    cs.battery_temp = 37  # degC
    cfg = DeviceConfig(name="TST", ip="127.0.0.1", send_port=50000)
    dev = Device(cfg)
    fb = FrameBuilder(cs, dev)
    buf = fb.build()
    voltage_raw = (buf[100] << 8) | buf[101]
    assert voltage_raw == int(125.0 / 0.25)
    temp_raw = (buf[158] << 8) | buf[159]
    assert temp_raw == int(37 / 0.1)
