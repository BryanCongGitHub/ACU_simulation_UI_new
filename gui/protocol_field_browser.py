from __future__ import annotations

import copy
from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from controllers.protocol_field_service import (
    FieldSection,
    ProtocolFieldService,
    TemplateFieldMeta,
)

SEND_CATEGORY = "__send__"


class ProtocolFieldBrowser(QWidget):
    """Interactive protocol field configuration view."""

    preferences_changed = Signal(dict)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        field_service: Optional[ProtocolFieldService] = None,
    ):
        super().__init__(parent)
        self._service = field_service or ProtocolFieldService()
        self._tree = QTreeWidget(self)
        self._header = QLabel(
            "选择需要在发送配置和接收视图中展示的字段，保存后即时生效。",
            self,
        )
        self._save_btn = QPushButton("保存", self)
        self._reset_btn = QPushButton("恢复默认", self)
        self._prefs: Dict[str, object] = {}
        self._send_selected: set[str] = set()
        self._receive_selected: Dict[str, set[str]] = {}
        self._updating_tree = False
        self._dirty = False
        self._send_info_cache = self._service.send_field_infos()
        self._receive_info_cache = self._service.receive_field_infos()
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._header.setWordWrap(True)
        layout.addWidget(self._header)

        self._tree.setHeaderLabels(["字段", "位置", "来源", "说明", "备注"])
        self._tree.setColumnCount(5)
        self._tree.setUniformRowHeights(True)
        self._tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._tree, 1)

        button_bar = QHBoxLayout()
        button_bar.addWidget(self._save_btn)
        button_bar.addWidget(self._reset_btn)
        button_bar.addStretch(1)
        layout.addLayout(button_bar)

        self._save_btn.clicked.connect(self._save_preferences)
        self._reset_btn.clicked.connect(self._restore_defaults)
        self._update_button_state()

    # ------------------------------------------------------------------
    # Data population
    # ------------------------------------------------------------------
    def refresh(self, *, preferences: Optional[Dict[str, object]] = None) -> None:
        if preferences is None:
            prefs = self._service.get_active_preferences()
        else:
            prefs = copy.deepcopy(preferences)

        self._prefs = prefs
        self._send_selected = set(self._prefs.get("send", []))
        receive_map = self._prefs.get("receive", {})
        self._receive_selected = {
            category: set(keys) for category, keys in receive_map.items()
        }

        self._updating_tree = True
        self._tree.clear()
        send_sections = self._service.get_send_sections()
        common_sections, category_sections = self._service.get_receive_meta()

        send_root = QTreeWidgetItem(["发送帧", "", "", "", ""])
        self._tree.addTopLevelItem(send_root)
        self._populate_section_group(send_root, send_sections, SEND_CATEGORY)

        receive_root = QTreeWidgetItem(["接收帧", "", "", "", ""])
        self._tree.addTopLevelItem(receive_root)
        if common_sections:
            common_item = QTreeWidgetItem(["公共字段", "", "", "", ""])
            receive_root.addChild(common_item)
            self._populate_sections(common_item, common_sections, "common")
            common_item.setExpanded(True)

        for category_meta in category_sections:
            display = f"{category_meta.category} ({category_meta.display_name})"
            category_item = QTreeWidgetItem([display, "", "", "", ""])
            receive_root.addChild(category_item)
            self._populate_sections(
                category_item, category_meta.sections, category_meta.category
            )
            category_item.setExpanded(True)

        send_root.setExpanded(True)
        receive_root.setExpanded(True)
        self._tree.expandToDepth(2)
        self._updating_tree = False
        self._update_button_state()

    def _populate_section_group(
        self,
        parent_item: QTreeWidgetItem,
        sections: list[FieldSection],
        category: str,
    ) -> None:
        for section in sections:
            section_item = QTreeWidgetItem([section.title, "", "", "", ""])
            parent_item.addChild(section_item)
            self._populate_items(section_item, section.items, category, section.title)
            section_item.setExpanded(True)

    def _populate_sections(
        self,
        parent_item: QTreeWidgetItem,
        sections: list[FieldSection],
        category: str,
    ) -> None:
        for section in sections:
            section_item = QTreeWidgetItem([section.title, "", "", "", ""])
            parent_item.addChild(section_item)
            self._populate_items(section_item, section.items, category, section.title)
            section_item.setExpanded(True)

    def _populate_items(
        self,
        parent_item: QTreeWidgetItem,
        items: list[TemplateFieldMeta],
        category: str,
        section_title: str,
    ) -> None:
        for meta in items:
            row = QTreeWidgetItem(
                [
                    meta.label or "",
                    meta.location or "",
                    meta.source or "",
                    meta.detail or "",
                    meta.note or "",
                ]
            )
            parent_item.addChild(row)
            if meta.key:
                row.setFlags(row.flags() | Qt.ItemIsUserCheckable)
                row.setData(0, Qt.UserRole, meta.key)
                row.setData(0, Qt.UserRole + 1, category)
                row.setData(0, Qt.UserRole + 2, section_title)
                checked = (
                    Qt.Checked
                    if self._is_key_selected(meta.key, category)
                    else Qt.Unchecked
                )
                row.setCheckState(0, checked)
            else:
                row.setFlags(row.flags() & ~Qt.ItemIsUserCheckable)

    # ------------------------------------------------------------------
    # Selection management
    # ------------------------------------------------------------------
    def _is_key_selected(self, key: str, category: str) -> bool:
        if not key:
            return False
        if category == SEND_CATEGORY:
            return key in self._send_selected
        selected = self._receive_selected.get(category)
        if selected is None:
            return False
        return key in selected

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._updating_tree or column != 0:
            return
        key = item.data(0, Qt.UserRole)
        if not key:
            return
        category = item.data(0, Qt.UserRole + 1) or SEND_CATEGORY
        state = item.checkState(0)
        if category == SEND_CATEGORY:
            self._update_send_selection(key, state)
        else:
            self._update_receive_selection(category, key, state)
        self._update_button_state()

    def _update_send_selection(self, key: str, state: Qt.CheckState) -> None:
        selected_list = self._prefs.setdefault("send", [])
        if state == Qt.Checked:
            if key not in selected_list:
                selected_list.append(key)
                self._send_selected.add(key)
                self._sort_keys_in_place(selected_list, self._send_info_cache)
        else:
            if key in selected_list:
                selected_list.remove(key)
            self._send_selected.discard(key)
        self._dirty = True

    def _update_receive_selection(
        self, category: str, key: str, state: Qt.CheckState
    ) -> None:
        receive = self._prefs.setdefault("receive", {})
        selected_list = receive.setdefault(category, [])
        selected_set = self._receive_selected.setdefault(category, set())
        if state == Qt.Checked:
            if key not in selected_list:
                selected_list.append(key)
                selected_set.add(key)
                self._sort_keys_in_place(selected_list, self._receive_info_cache)
        else:
            if key in selected_list:
                selected_list.remove(key)
            selected_set.discard(key)
        self._dirty = True

    @staticmethod
    def _sort_keys_in_place(keys: list[str], info_map: Dict[str, object]) -> None:
        try:
            keys.sort(key=lambda item: getattr(info_map.get(item), "order", 0))
        except Exception:
            pass

    def _save_preferences(self) -> None:
        baseline = self._service.default_preferences()
        payload = {
            "version": baseline.get("version"),
            "send": list(self._prefs.get("send", [])),
            "receive": {
                category: list(keys)
                for category, keys in self._prefs.get("receive", {}).items()
            },
        }
        active = self._service.save_preferences(payload)
        self._dirty = False
        self.refresh(preferences=active)
        self.preferences_changed.emit(active)

    def _restore_defaults(self) -> None:
        defaults = self._service.default_preferences()
        self.refresh(preferences=defaults)
        self._dirty = True
        self._update_button_state()

    def _update_button_state(self) -> None:
        self._save_btn.setEnabled(self._dirty)


__all__ = ["ProtocolFieldBrowser"]
