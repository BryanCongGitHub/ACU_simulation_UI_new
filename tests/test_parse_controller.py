from controllers.parse_controller import ParseController


def test_device_type_and_category():
    pc = ParseController()
    assert pc.device_type_from_port(49153) == "INV1"
    assert pc.category_from_device("INV1") == "INV"
    assert pc.category_from_device("CHU3") == "CHU"
    assert pc.category_from_device("BCC1") == "BCC"
    assert pc.category_from_device("DUMMY1") == "DUMMY"
    assert pc.device_type_from_port(40000) == "UNKNOWN"


def test_parse_dummy_protocol():
    pc = ParseController()
    # Port 49999 maps to DUMMY1 -> DUMMY category
    port = 49999
    # Build a 16-byte payload for DummyProtocol
    data = bytearray(16)
    data[0:2] = (123).to_bytes(2, "big")
    data[2] = 0x7F
    parsed = pc.parse(bytes(data), port)
    assert isinstance(parsed, dict)
    assert "设备信息" in parsed
    assert parsed["设备信息"]["生命信号"] == 123
    assert parsed["设备信息"]["示例码"] == 0x7F


def test_parse_unknown_device_returns_error():
    pc = ParseController()
    parsed = pc.parse(b"\x00" * 16, 40000)
    assert isinstance(parsed, dict)
    assert "错误" in parsed or parsed.get("错误") is not None
