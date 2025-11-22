from __future__ import annotations

import pytest

from model.control_state import ControlState
from model.protocols.inv_protocol import InvLikeProtocol
from protocols.template_runtime.loader import load_template_protocol


def _build_control_snapshot() -> dict:
    state = ControlState()
    state.bool_commands[(10, 3)] = True
    state.bool_commands[(15, 7)] = True
    state.freq_controls[32] = 50.5  # -> 505 raw
    state.isolation_commands[0] = True
    state.isolation_commands[4] = True
    state.start_commands[1] = True
    state.chu_controls[(70, 2)] = True
    state.redundant_commands[(75, 5)] = True
    state.start_times[180] = 12
    state.branch_voltages[200] = 25.0  # -> 100 raw
    state.battery_temp = 42.0  # -> 420 raw
    return state.snapshot()


def _build_receive_frame(category: str) -> bytes:
    buf = bytearray(64)
    buf[0:2] = (1234).to_bytes(2, "big")
    buf[2:4] = (4321).to_bytes(2, "big")
    buf[4:6] = (7).to_bytes(2, "big")

    if category in {"INV", "CHU"}:
        buf[6:8] = (305).to_bytes(2, "big")  # 30.5 Hz
        buf[8:10] = (200).to_bytes(2, "big")  # 50.0 A
        buf[10:12] = (120).to_bytes(2, "big")
        buf[12:14] = (80).to_bytes(2, "big")
        buf[14:16] = (400).to_bytes(2, "big")
        buf[24:26] = (350).to_bytes(2, "big")
        status_bits = 0x0B  # bits 0,1,3 true
        if category == "CHU":
            status_bits |= 0x10
        buf[48] = status_bits
        buf[52] = 0b00110011
        buf[53] = 0b10000101
    elif category == "BCC":
        buf[6:8] = (220).to_bytes(2, "big")
        buf[8:10] = (180).to_bytes(2, "big")
        buf[10:12] = (160).to_bytes(2, "big")
        buf[12:14] = (250).to_bytes(2, "big")
        buf[14:16] = (480).to_bytes(2, "big")
        buf[48] = 0x1B  # bits 0,1,3,4 true
        buf[52] = 0b11110000
        buf[53] = 0b00000111
    else:
        raise ValueError(f"Unsupported category: {category}")

    return bytes(buf)


@pytest.mark.parametrize("category", ["INV", "CHU", "BCC"])
def test_build_send_frame_matches_legacy(category: str) -> None:
    template_proto = load_template_protocol(category)
    legacy_proto = InvLikeProtocol(category)
    snapshot = _build_control_snapshot()
    frame_template = template_proto.build_send_frame(snapshot, life_signal=2468)
    frame_legacy = legacy_proto.build_send_frame(snapshot, life_signal=2468)
    assert frame_template == frame_legacy


@pytest.mark.parametrize("category", ["INV", "CHU", "BCC"])
def test_parse_receive_frame_matches_legacy(category: str) -> None:
    template_proto = load_template_protocol(category)
    legacy_proto = InvLikeProtocol(category)
    payload = _build_receive_frame(category)
    parsed_template = template_proto.parse_receive_frame(payload)
    parsed_legacy = legacy_proto.parse_receive_frame(payload)
    assert parsed_template == parsed_legacy


def test_parse_length_guard() -> None:
    proto = load_template_protocol("INV")
    result = proto.parse_receive_frame(b"short")
    assert result == {"错误": "数据长度不足"}
