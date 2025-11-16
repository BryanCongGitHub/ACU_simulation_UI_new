import pytest

from controllers.parse_controller import ParseController


def test_unknown_port_returns_error():
    pc = ParseController()
    data = b"\x00" * 16
    res = pc.parse(data, 40000)
    assert isinstance(res, dict)
    assert '错误' in res


def test_dummy_protocol_parsing_success():
    pc = ParseController()
    # port 49999 maps to DUMMY1 per ParseController
    life = (5).to_bytes(2, 'big')
    code = bytes([7])
    payload = life + code + b"\x00" * (16 - 3)
    res = pc.parse(payload, 49999)
    assert isinstance(res, dict)
    assert '设备信息' in res
    assert res['设备信息']['生命信号'] == 5
    assert res['设备信息']['示例码'] == 7


def test_dummy_protocol_short_data_returns_error():
    pc = ParseController()
    short = b"\x00" * 4
    res = pc.parse(short, 49999)
    assert isinstance(res, dict)
    assert res.get('错误') == '数据长度不足'


def test_parse_propagates_exception_when_protocol_raises():
    pc = ParseController()

    class BadProto:
        def parse_receive_frame(self, data):
            raise RuntimeError("boom")

    # swap in bad protocol for DUMMY category
    pc._protocols['DUMMY'] = BadProto()
    with pytest.raises(RuntimeError):
        pc.parse(b"\x00" * 16, 49999)


def test_category_mapping_for_known_devices():
    pc = ParseController()
    assert pc.category_from_device('INV5') == 'INV'
    assert pc.category_from_device('CHU3') == 'CHU'
    assert pc.category_from_device('BCC2') == 'BCC'
    assert pc.category_from_device('DUMMY1') == 'DUMMY'
    assert pc.category_from_device('??') == 'UNKNOWN'


def test_parse_returns_error_when_protocol_missing():
    pc = ParseController()
    # remove INV handler to simulate unregistered protocol
    pc._protocols.pop('INV', None)
    res = pc.parse(b"\x00" * 20, 49153)
    assert res == {'错误': '未知设备类型: INV1'}
