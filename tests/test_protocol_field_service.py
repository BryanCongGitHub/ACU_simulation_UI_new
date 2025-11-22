from __future__ import annotations

from controllers.protocol_field_service import ProtocolFieldService


def test_send_sections_include_life_signal() -> None:
    service = ProtocolFieldService()
    sections = service.get_send_sections()
    titles = [section.title for section in sections]
    assert "生命信号" in titles

    life_section = next(section for section in sections if section.title == "生命信号")
    assert life_section.items
    assert life_section.items[0].label == "CCU生命信号"


def test_receive_meta_contains_inv_run_parameters() -> None:
    service = ProtocolFieldService()
    common_sections, categories = service.get_receive_meta()

    assert common_sections
    assert common_sections[0].title == "设备信息"

    inv_meta = next(category for category in categories if category.category == "INV")
    run_section = next(
        section for section in inv_meta.sections if section.title == "运行参数"
    )
    labels = [item.label for item in run_section.items]
    assert "输出频率" in labels
