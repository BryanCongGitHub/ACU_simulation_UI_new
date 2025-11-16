import struct
from model.protocols.inv_protocol import InvLikeProtocol


def test_parse_inv_data_basic():
    # 构造 64 字节数据
    data = bytearray(64)
    # 生命信号 1
    data[0:2] = struct.pack('>H', 1)
    # 输出频率 50.0 Hz -> 原始值 500 (0.1Hz 单位)
    data[6:8] = struct.pack('>H', 500)

    proto = InvLikeProtocol('INV')
    parsed = proto.parse_receive_frame(bytes(data))
    assert "运行参数" in parsed
    assert parsed["运行参数"]["输出频率"] == 50.0
    assert parsed["设备信息"]["生命信号"] == 1


def test_parse_bcc_data_basic():
    data = bytearray(64)
    # 输出电压 raw=400 -> 400*0.25 = 100.0 V
    data[6:8] = struct.pack('>H', 400)

    proto = InvLikeProtocol('BCC')
    parsed = proto.parse_receive_frame(bytes(data))
    assert "运行参数" in parsed
    assert parsed["运行参数"]["输出电压"] == 400 * 0.25


def test_parse_data_length_short():
    data = bytearray(10)
    proto = InvLikeProtocol('INV')
    parsed = proto.parse_receive_frame(bytes(data))
    assert isinstance(parsed, dict)
    assert parsed.get("错误") == "数据长度不足"
