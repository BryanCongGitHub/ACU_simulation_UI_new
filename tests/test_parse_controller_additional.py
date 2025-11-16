import struct
from controllers.parse_controller import ParseController


def make_inv_receive_frame(life=42, sw_code=1, sw_ver=2, freq_raw=500):
    data = bytearray(64)
    data[0:2] = struct.pack(">H", life)
    data[2:4] = struct.pack(">H", sw_code)
    data[4:6] = struct.pack(">H", sw_ver)
    data[6:8] = struct.pack(">H", freq_raw)
    # status byte at 48 -> set bit0 and bit1
    data[48] = 0x03
    return bytes(data)


def test_parse_accepts_bytearray_input():
    pc = ParseController()
    port = 49153  # maps to INV1
    data = make_inv_receive_frame()
    # pass a bytearray instead of bytes
    res = pc.parse(bytearray(data), port)
    assert isinstance(res, dict)
    assert "设备信息" in res
    assert res["设备信息"]["生命信号"] == 42
    # frequency should be parsed and present in 运行参数
    assert "运行参数" in res
