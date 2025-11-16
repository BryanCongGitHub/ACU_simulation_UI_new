import struct

from controllers.parse_controller import ParseController
from controllers.frame_builder import FrameBuilder
from model.control_state import ControlState
from model.device import Device
from model.device import DeviceConfig


def test_parse_controller_inv_frequency_parsing():
    controller = ParseController()
    data = bytearray(64)
    data[0:2] = (0x1234).to_bytes(2, "big")
    data[6:8] = (500).to_bytes(2, "big")  # 50.0 Hz

    result = controller.parse(bytes(data), 49153)

    assert result["设备信息"]["生命信号"] == 0x1234
    assert result["运行参数"]["输出频率"] == 50.0


def test_parse_controller_unknown_device_returns_error():
    controller = ParseController()
    result = controller.parse(b"\x00" * 64, 12345)
    assert result.get("错误") == "未知设备类型: UNKNOWN"


def test_frame_builder_populates_key_fields():
    state = ControlState()
    state.bool_commands[(8, 0)] = True
    state.freq_controls[10] = 50  # Hz
    state.isolation_commands[0] = True
    state.start_commands[1] = True
    state.chu_controls[(66, 3)] = True
    state.redundant_commands[(67, 0)] = True
    state.start_times[142] = 3
    state.branch_voltages[154] = 100
    state.battery_temp = 30

    device = Device(
        DeviceConfig(
            name="ACU",
            ip="10.0.0.1",
            send_port=40000,
            receive_port=40001,
            category="ACU",
        )
    )
    builder = FrameBuilder(state, device)

    frame = builder.build()
    assert frame[0:2] == struct.pack(">H", 1)
    assert frame[8] & 0x01
    assert frame[10:12] == struct.pack(">H", 500)
    assert frame[64] & 0x01
    assert frame[65] & 0x02
    assert frame[66] & (1 << 3)
    assert frame[67] & 0x01
    assert frame[142:144] == struct.pack(">H", 3)
    assert frame[154:156] == struct.pack(">H", 400)
    assert frame[158:160] == struct.pack(">H", 300)

    frame_second = builder.build()
    assert frame_second[0:2] == struct.pack(">H", 2)
