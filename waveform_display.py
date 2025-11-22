# waveform_display.py
from typing import Dict, Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QComboBox,
    QLabel,
    QSplitter,
    QCheckBox,
    QMessageBox,
    QFileDialog,
)
from PySide6.QtCore import Qt
from waveform_controller import WaveformController
from signal_manager import SignalManager
from waveform_plot import WaveformPlotWidget
from infra.settings_store import (
    WaveformSettings,
    load_waveform_settings,
    save_waveform_settings,
)
import logging

# 创建日志记录器
logger = logging.getLogger("WaveformDisplay")


class WaveformDisplay(QWidget):
    """波形显示主界面"""

    def __init__(
        self,
        parent=None,
        event_bus=None,
        field_service=None,
        field_preferences=None,
    ):
        super().__init__(parent)
        self.signal_manager = SignalManager()
        self.controller = WaveformController(signal_manager=self.signal_manager)
        self.event_bus = None
        self._field_service = field_service
        self._field_preferences = field_preferences or {}
        self._populating_tree = False
        self._settings_dialog_cls = None
        self.init_ui()
        self.setup_connections()
        if field_service is not None:
            try:
                self.apply_field_preferences(field_service, self._field_preferences)
            except Exception:
                logger.exception("Failed to apply protocol field preferences")
        self.bind_event_bus(event_bus)
        # Load persisted UI/settings
        try:
            self.load_settings()
        except Exception:
            pass

    def init_ui(self):
        """Create and arrange widgets for the WaveformDisplay UI."""
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)

        # 分割区域
        self.splitter = QSplitter(Qt.Horizontal)

        # 左侧信号选择树
        self.signal_tree = self.create_signal_tree()
        self.splitter.addWidget(self.signal_tree)

        # 右侧波形显示区域
        self.waveform_widget = WaveformPlotWidget(self.controller)
        self.splitter.addWidget(self.waveform_widget)

        self.splitter.setSizes([350, 650])
        layout.addWidget(self.splitter)

        # interactive legend area below the plot for quick show/hide
        from PySide6.QtWidgets import QScrollArea, QWidget

        self.legend_area = QScrollArea()
        self.legend_area.setWidgetResizable(True)
        legend_container = QWidget()
        self._legend_layout = QVBoxLayout(legend_container)
        self._legend_layout.setContentsMargins(2, 2, 2, 2)
        self._legend_layout.setSpacing(4)
        self.legend_area.setWidget(legend_container)
        self.legend_area.setMaximumHeight(120)
        layout.addWidget(self.legend_area)

        # ensure the layout is applied
        self.setLayout(layout)

    def bind_event_bus(self, event_bus):
        """Bind or replace the ViewEventBus used to dispatch UI-level events.

        The ViewEventBus has signals: `waveform_send`, `waveform_receive`,
        and `recording_toggle`. When a new event_bus is provided we connect
        those signals to local handlers; if `None` is given we simply clear
        the reference.
        """
        # if unchanged, nothing to do
        if self.event_bus is event_bus:
            return

        # unbind previous (best-effort)
        try:
            if self.event_bus is not None:
                try:
                    self.event_bus.waveform_send.disconnect(self._on_bus_waveform_send)
                except Exception:
                    pass
                try:
                    self.event_bus.waveform_receive.disconnect(
                        self._on_bus_waveform_receive
                    )
                except Exception:
                    pass
                try:
                    self.event_bus.recording_toggle.disconnect(
                        self._on_bus_recording_toggle
                    )
                except Exception:
                    pass
        except Exception:
            pass

        self.event_bus = event_bus
        if self.event_bus is None:
            return

        try:
            self.event_bus.waveform_send.connect(self._on_bus_waveform_send)
        except Exception:
            pass
        try:
            self.event_bus.waveform_receive.connect(self._on_bus_waveform_receive)
        except Exception:
            pass
        try:
            self.event_bus.recording_toggle.connect(self._on_bus_recording_toggle)
        except Exception:
            pass

    def _on_bus_waveform_send(self, data_buffer, timestamp):
        self.controller.add_send_data(data_buffer, timestamp)

    def _on_bus_waveform_receive(self, parsed_data, device_type, timestamp):
        self.controller.add_receive_data(parsed_data, device_type, timestamp)

    def _on_bus_recording_toggle(self, should_record):
        block = self.record_btn.blockSignals(True)
        self.record_btn.setChecked(should_record)
        self.record_btn.blockSignals(block)
        if should_record:
            self.controller.start_recording()
            self.record_btn.setText("停止记录")
            self.pause_btn.setEnabled(True)
        else:
            self.controller.stop_recording()
            self.record_btn.setText("开始记录")
            self.pause_btn.setChecked(False)
            self.pause_btn.setEnabled(False)
        # legend area already managed in init_ui

    def create_toolbar(self):
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setSpacing(8)
        layout.setContentsMargins(5, 5, 5, 5)

        self.record_btn = QPushButton("开始记录")
        self.record_btn.setCheckable(True)
        self.record_btn.setMinimumHeight(30)
        self.record_btn.setToolTip("开始或停止数据记录")
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setCheckable(True)
        self.pause_btn.setMinimumHeight(30)
        self.pause_btn.setToolTip("暂停/继续记录，不会清空已记录数据")
        self.clear_btn = QPushButton("清空波形")
        self.clear_btn.setMinimumHeight(30)
        self.clear_btn.setToolTip("清除当前所有显示的波形和缓存")
        self.export_btn = QPushButton("导出数据")
        self.export_btn.setMinimumHeight(30)
        self.export_btn.setToolTip("导出当前选中信号的历史数据为 CSV 或 JSON")
        # accessibility: keyboard shortcut and accessible name for export
        try:
            self.export_btn.setShortcut("Ctrl+E")
            self.export_btn.setAccessibleName("export_data")
        except Exception:
            pass

        # thumbnail preview button + label
        self.thumb_btn = QPushButton("预览缩略图")
        self.thumb_btn.setMinimumHeight(30)
        self.thumb_btn.setToolTip("生成当前波形的缩略图并在工具栏显示")
        self.thumb_label = QLabel("")
        self.thumb_label.setFixedSize(160, 80)
        self.thumb_label.setVisible(False)
        try:
            self.thumb_label.setAccessibleName("thumbnail_preview")
        except Exception:
            pass

        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems(["1分钟", "5分钟", "10分钟", "30分钟", "1小时"])
        self.time_range_combo.setCurrentText("10分钟")
        self.time_range_combo.setMinimumHeight(30)

        self.auto_range_check = QCheckBox("自动范围")
        self.auto_range_check.setChecked(True)
        self.auto_range_check.setMinimumHeight(30)

        layout.addWidget(self.record_btn)
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.clear_btn)
        layout.addWidget(self.export_btn)
        layout.addWidget(self.thumb_btn)
        layout.addWidget(self.thumb_label)
        layout.addStretch()
        layout.addWidget(QLabel("时间范围:"))
        layout.addWidget(self.time_range_combo)
        layout.addWidget(self.auto_range_check)
        # theme and legend/grid controls
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setCurrentText("Light")
        self.theme_combo.setToolTip("切换绘图主题（明亮/暗色）")
        self.legend_check = QCheckBox("显示图例")
        self.legend_check.setChecked(True)
        self.legend_check.setToolTip("切换图例显示")
        try:
            # keyboard shortcut to toggle legend visibility
            self.legend_check.setShortcut("Ctrl+L")
            self.legend_check.setAccessibleName("toggle_legend")
        except Exception:
            pass
        self.grid_btn = QPushButton("切换网格")
        self.grid_btn.setToolTip("显示/隐藏网格")
        layout.addWidget(self.theme_combo)
        layout.addWidget(self.legend_check)
        layout.addWidget(self.grid_btn)

        # palette actions condensed into a combo box to save toolbar space
        self.palette_combo = QComboBox()
        self.palette_combo.setMinimumWidth(120)
        self.palette_combo.addItem("配色操作…", None)
        self.palette_combo.addItem("保存配色", "save")
        self.palette_combo.addItem("加载配色", "load")
        self.palette_combo.addItem("导出配色", "export")
        self.palette_combo.addItem("导入配色", "import")
        self.palette_combo.setToolTip("选择配色相关操作")
        layout.addWidget(self.palette_combo)

        return toolbar

    def create_signal_tree(self):
        tree = QTreeWidget()
        tree.setHeaderLabels(["信号选择", "状态", "数值"])
        tree.setColumnCount(3)
        tree.setColumnWidth(0, 220)
        tree.setColumnWidth(1, 60)
        tree.setColumnWidth(2, 70)
        tree.setMinimumHeight(600)  # 增加最小高度
        self._populate_signal_tree(tree)
        return tree

    def _populate_signal_tree(self, tree: Optional[QTreeWidget] = None) -> None:
        tree = tree or getattr(self, "signal_tree", None)
        if tree is None:
            return

        self._populating_tree = True
        try:
            try:
                tree.blockSignals(True)
            except Exception:
                pass

            tree.clear()

            available_ids = set(self.controller.signal_manager.signals.keys())
            for sid in list(self.controller.get_selected_signals()):
                if sid not in available_ids:
                    self.controller.deselect_signal(sid)

            selected = set(self.controller.get_selected_signals())
            categories = self.controller.signal_manager.get_signal_categories()
            for category in categories:
                category_item = QTreeWidgetItem(tree, [category, "", ""])
                category_item.setExpanded(True)
                signals = self.controller.signal_manager.get_signals_by_category(
                    category
                )
                for signal_id, signal_info in signals:
                    label = signal_info.get("name") or str(signal_id)
                    checked = Qt.Checked if signal_id in selected else Qt.Unchecked
                    status_text = "●" if checked == Qt.Checked else "○"
                    signal_item = QTreeWidgetItem(
                        category_item, [label, status_text, "--"]
                    )
                    signal_item.setData(0, Qt.UserRole, signal_id)
                    signal_item.setCheckState(0, checked)
                    try:
                        tip = (
                            f"{label} (id={signal_id}, type={signal_info.get('type')})"
                        )
                        signal_item.setToolTip(0, tip)
                    except Exception:
                        pass

            try:
                tree.expandToDepth(1)
            except Exception:
                pass
        finally:
            try:
                tree.blockSignals(False)
            except Exception:
                pass
            self._populating_tree = False

        try:
            self._rebuild_legend()
        except Exception:
            pass

    def apply_field_preferences(
        self, field_service, preferences: Optional[Dict[str, object]] = None
    ) -> None:
        """Update available waveform signals based on protocol field selections."""

        self._field_service = field_service
        self._field_preferences = preferences or {}

        retained = set(self.controller.get_selected_signals())

        try:
            self.signal_manager.load_from_protocol(
                field_service, self._field_preferences
            )
        except Exception:
            logger.exception("Failed to refresh signal definitions from protocol")
            self.signal_manager.load_signal_definitions()

        available_ids = set(self.signal_manager.signals.keys())

        # Remove plots and selections that are no longer available
        for sid in list(retained):
            if sid not in available_ids:
                self.controller.deselect_signal(sid)
                try:
                    self.waveform_widget.remove_signal_plot(sid)
                except Exception:
                    pass
                retained.discard(sid)

        self._populate_signal_tree()

        # Ensure existing selections have active plots after tree rebuild
        current_curves = getattr(self.waveform_widget, "curves", {})
        for sid in retained:
            info = self.signal_manager.get_signal_info(sid)
            if info is None:
                continue
            if sid not in current_curves:
                try:
                    self.waveform_widget.add_signal_plot(sid, info)
                except Exception:
                    pass

        try:
            self._rebuild_legend()
        except Exception:
            pass

    def setup_connections(self):
        """设置信号连接"""
        self.record_btn.toggled.connect(self.on_record_toggled)
        self.pause_btn.toggled.connect(self.on_pause_toggled)
        self.clear_btn.clicked.connect(self.on_clear_clicked)
        self.export_btn.clicked.connect(self.on_export_clicked)
        self.thumb_btn.clicked.connect(self._on_thumb_clicked)
        self.time_range_combo.currentTextChanged.connect(self.on_time_range_changed)
        self.auto_range_check.toggled.connect(self.on_auto_range_toggled)
        self.signal_tree.itemChanged.connect(self.on_signal_selection_changed)

        # 改为统一更新
        self.controller.data_updated.connect(self.on_data_updated)
        # additional UX handlers
        self.signal_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.signal_tree.customContextMenuRequested.connect(
            self._on_signal_context_menu
        )
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        self.legend_check.toggled.connect(self._on_legend_toggled)
        self.grid_btn.clicked.connect(self._on_grid_toggled)
        # palette handlers via combo box
        self.palette_combo.currentIndexChanged.connect(self._on_palette_combo_changed)

    def on_record_toggled(self, checked):
        """记录按钮切换"""
        if checked:
            self.controller.start_recording()
            self.record_btn.setText("停止记录")
            self.pause_btn.setEnabled(True)
        else:
            self.controller.stop_recording()
            self.record_btn.setText("开始记录")
            self.pause_btn.setChecked(False)
            self.pause_btn.setEnabled(False)

    def on_pause_toggled(self, checked):
        """暂停按钮切换"""
        if checked:
            self.controller.stop_recording()
            self.pause_btn.setText("继续")
        else:
            self.controller.start_recording()
            self.pause_btn.setText("暂停")

    def on_clear_clicked(self):
        """清空波形"""
        self.controller.clear_buffer()
        self.waveform_widget.clear_plots()

    def on_export_clicked(self):
        """导出数据为 CSV 或 JSON。导出当前选中信号的全部缓冲数据。"""
        try:
            selected = list(self.controller.get_selected_signals())
            if not selected:
                QMessageBox.information(self, "导出", "未选择任何信号，无法导出")
                return

            # 选择导出文件
            path, fmt = QFileDialog.getSaveFileName(
                self,
                "导出数据",
                "waveform_export.csv",
                "CSV 文件 (*.csv);;JSON 文件 (*.json)",
            )
            if not path:
                return

            # 规范格式
            fmt = (
                "csv"
                if path.lower().endswith(".csv") or "csv" in fmt.lower()
                else "json"
            )

            timestamps = self.controller.get_timestamps()

            # 组织数据为行格式（时间戳为第一列）
            # 使用信号显示名作为 CSV header，便于阅读
            display_names = []
            sig_to_name = {}
            for sig in selected:
                info = self.controller.signal_manager.get_signal_info(sig) or {}
                name = info.get("name") or str(sig)
                display_names.append(name)
                sig_to_name[sig] = name

            rows = []
            for i, ts in enumerate(timestamps):
                row = {"timestamp": ts}
                for sig in selected:
                    vals = self.controller.get_signal_data(sig)
                    row[sig_to_name[sig]] = vals[i] if i < len(vals) else None
                rows.append(row)

            if fmt == "csv":
                import csv

                fieldnames = ["timestamp"] + display_names

                # write without BOM so CSV headers are plain ASCII/UTF-8
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for r in rows:
                        writer.writerow(r)
            else:
                import json

                with open(path, "w", encoding="utf-8") as f:
                    json.dump(rows, f, ensure_ascii=False, indent=2)

            # remember last export path for convenience
            try:
                self._last_export_path = path
                self.save_settings()
            except Exception:
                pass

            QMessageBox.information(self, "导出", f"导出成功: {path}")
        except Exception as e:
            logger.exception(f"导出失败: {e}")
            QMessageBox.critical(self, "导出", f"导出失败: {e}")

    def on_time_range_changed(self, text):
        """时间范围改变"""
        time_ranges = {
            "1分钟": 60,
            "5分钟": 300,
            "10分钟": 600,
            "30分钟": 1800,
            "1小时": 3600,
        }
        seconds = time_ranges.get(text, 600)
        self.waveform_widget.set_time_range(seconds)

    def on_auto_range_toggled(self, checked):
        """自动范围切换"""
        self.waveform_widget.set_auto_y_enabled(bool(checked))
        if checked:
            self.waveform_widget.auto_range()

    def on_signal_selection_changed(self, item, column):
        """信号选择改变"""
        if column != 0 or self._populating_tree:
            return

        signal_id = item.data(0, Qt.UserRole)
        if not signal_id:
            return

        signal_info = self.controller.signal_manager.get_signal_info(signal_id)
        if not signal_info:
            return

        if item.checkState(0) == Qt.Checked:
            # 选中信号
            self.controller.select_signal(signal_id)
            self.waveform_widget.add_signal_plot(signal_id, signal_info)
            item.setText(1, "●")

            # 立即显示当前值
            latest_value = self.controller.data_buffer.get_latest_value(signal_id)
            if latest_value is not None:
                if signal_info["type"] == "bool":
                    value_str = "1" if latest_value else "0"
                else:
                    value_str = f"{latest_value:.2f}"
                item.setText(2, value_str)

            logger.info(f"选择信号: {signal_info['name']}, 类型: {signal_info['type']}")
            # update interactive legend
            try:
                self._rebuild_legend()
            except Exception:
                pass

        else:
            # 取消选中
            self.controller.deselect_signal(signal_id)
            self.waveform_widget.remove_signal_plot(signal_id)
            item.setText(1, "○")
            item.setText(2, "--")
            logger.info(f"取消选择信号: {signal_info['name']}")
            try:
                self._rebuild_legend()
            except Exception:
                pass

    def _on_signal_context_menu(self, pos):
        """Context menu for signal tree to allow color editing, etc."""
        try:
            item = self.signal_tree.itemAt(pos)
            if item is None:
                return
            sid = item.data(0, Qt.UserRole)
            if not sid:
                return
            from PySide6.QtWidgets import QMenu

            menu = QMenu(self)
            change_color = menu.addAction("更改颜色")
            action = menu.exec(self.signal_tree.viewport().mapToGlobal(pos))
            if action == change_color:
                self._change_signal_color(item)
        except Exception:
            pass

    def _change_signal_color(self, item):
        try:
            sid = item.data(0, Qt.UserRole)
            if not sid:
                return
            from PySide6.QtWidgets import QColorDialog

            color = QColorDialog.getColor()
            if not color.isValid():
                return
            hexc = color.name()
            # update waveform plot color
            try:
                self.waveform_widget.set_curve_color(sid, hexc)
                # update legend visuals
                try:
                    self._rebuild_legend()
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass

    def _on_theme_changed(self, text):
        try:
            theme = "dark" if text == "Dark" else "light"
            try:
                self.waveform_widget.set_theme(theme)
            except Exception:
                pass
        except Exception:
            pass

    def _on_legend_toggled(self, visible):
        try:
            self.waveform_widget.show_legend(visible)
        except Exception:
            pass

    def _rebuild_legend(self):
        """Rebuild the small interactive legend area below the plot.

        Each entry contains a visibility checkbox, a color swatch button and a label.
        """
        try:
            layout = getattr(self, "_legend_layout", None)
            if layout is None:
                legend_container = QWidget()
                layout = QVBoxLayout(legend_container)
                layout.setContentsMargins(2, 2, 2, 2)
                layout.setSpacing(4)
                self._legend_layout = layout
                try:
                    self.legend_area.setWidget(legend_container)
                except Exception:
                    pass

            # clear existing widgets
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w is not None:
                    try:
                        w.setParent(None)
                        w.deleteLater()
                    except Exception:
                        pass

            # build entries for currently selected signals
            selected = list(self.controller.get_selected_signals())
            for sid in selected:
                info = self.controller.signal_manager.get_signal_info(sid) or {}
                name = info.get("name") or str(sid)

                entry = QWidget()
                hl = QHBoxLayout(entry)
                hl.setContentsMargins(2, 2, 2, 2)
                hl.setSpacing(6)

                vis = QCheckBox(name)
                vis.setChecked(True)

                # toggle visibility
                def _make_toggle(s):
                    return lambda checked: self.waveform_widget.set_curve_visible(
                        s, checked
                    )

                vis.toggled.connect(_make_toggle(sid))

                color_btn = QPushButton()
                color_btn.setFixedSize(18, 14)
                # determine current color from waveform_widget if available
                cur_color = None
                try:
                    curves = getattr(self.waveform_widget, "curves", {})
                    if sid in curves:
                        cur_color = curves[sid].get("color")
                except Exception:
                    cur_color = None

                if cur_color:
                    color_btn.setStyleSheet(
                        f"background-color: {cur_color}; border: 1px solid #333;"
                    )
                else:
                    color_btn.setStyleSheet(
                        "background-color: #888; border: 1px solid #333;"
                    )

                def _make_color_click(s, btn):
                    return lambda: self._on_legend_color_clicked(s, btn)

                color_btn.clicked.connect(_make_color_click(sid, color_btn))

                try:
                    vis.setAccessibleName(f"legend_vis_{sid}")
                    color_btn.setAccessibleName(f"legend_color_{sid}")
                except Exception:
                    pass

                hl.addWidget(vis)
                hl.addWidget(color_btn)
                hl.addStretch()

                layout.addWidget(entry)

            layout.addStretch(1)

        except Exception:
            logger.exception("重建交互式图例失败")

    def _on_legend_color_clicked(self, sid, btn):
        try:
            from PySide6.QtWidgets import QColorDialog

            color = QColorDialog.getColor()
            if not color.isValid():
                return
            hexc = color.name()
            try:
                self.waveform_widget.set_curve_color(sid, hexc)
            except Exception:
                pass
            try:
                btn.setStyleSheet(f"background-color: {hexc}; border: 1px solid #333;")
            except Exception:
                pass
        except Exception:
            pass

    def _on_palette_combo_changed(self, index: int) -> None:
        if index <= 0:
            return

        action = self.palette_combo.itemData(index)
        handlers = {
            "save": self._on_save_palette,
            "load": self._on_load_palette,
            "export": self._on_export_palette,
            "import": self._on_import_palette,
        }

        try:
            handler = handlers.get(action)
            if handler:
                handler()
        finally:
            try:
                self.palette_combo.blockSignals(True)
                self.palette_combo.setCurrentIndex(0)
            finally:
                self.palette_combo.blockSignals(False)

    def _on_save_palette(self):
        """Save current signal color mapping to QSettings.

        Stored under the `WaveformDisplay/palette` key as JSON.
        """
        try:
            curves = getattr(self.waveform_widget, "curves", {})
            mapping = {
                str(sid): info.get("color") or "#000000" for sid, info in curves.items()
            }

            cls = self._get_settings_dialog_cls()
            if not cls:
                QMessageBox.information(self, "配色", "设置对话框不可用，无法保存配色")
                return
            ok = cls.save_palette_to_settings(mapping)
            if ok:
                QMessageBox.information(self, "配色", "配色已保存")
            else:
                QMessageBox.critical(self, "配色", "保存配色失败")
        except Exception:
            logger.exception("保存配色失败")
            QMessageBox.critical(self, "配色", "保存配色失败")

    def _on_load_palette(self):
        """Load palette mapping from QSettings and apply colors to existing curves."""
        try:
            if self._load_palette_from_settings(silent=True):
                QMessageBox.information(self, "配色", "配色已加载并应用")
            else:
                QMessageBox.information(self, "配色", "未找到已保存的配色")
        except Exception:
            logger.exception("加载配色失败")
            QMessageBox.critical(self, "配色", "加载配色失败")

    def _on_export_palette(self):
        """Export current palette mapping to a JSON file chosen by the user."""
        try:
            curves = getattr(self.waveform_widget, "curves", {})
            mapping = {
                str(sid): info.get("color") or "#000000" for sid, info in curves.items()
            }
            cls = self._get_settings_dialog_cls()
            if not cls:
                QMessageBox.information(self, "配色", "设置对话框不可用，无法导出配色")
                return
            ok = cls.export_palette_to_file(mapping, parent=self)
            if ok:
                QMessageBox.information(self, "配色", "配色已导出")
            else:
                QMessageBox.information(self, "配色", "导出已取消或失败")
        except Exception:
            logger.exception("导出配色失败")
            QMessageBox.critical(self, "配色", "导出配色失败")

    def _on_import_palette(self):
        """Import a palette JSON file and apply it to existing curves."""
        try:
            cls = self._get_settings_dialog_cls()
            if not cls:
                QMessageBox.information(self, "配色", "设置对话框不可用，无法导入配色")
                return
            mapping = cls.import_palette_from_file(parent=self)

            for k, v in (mapping or {}).items():
                try:
                    self.waveform_widget.set_curve_color(k, v)
                except Exception:
                    try:
                        self.waveform_widget.set_curve_color(int(k), v)
                    except Exception:
                        pass

            try:
                self._rebuild_legend()
            except Exception:
                pass

            QMessageBox.information(self, "配色", "配色已导入并应用")
        except Exception:
            logger.exception("导入配色失败")
            QMessageBox.critical(self, "配色", "导入配色失败")

    def _on_grid_toggled(self):
        try:
            # toggle grid visibility
            cur = getattr(self.waveform_widget, "main_plot", None)
            if cur is None:
                return
            # grid visibility can be inferred from showGrid
            # flip: if currently shown, hide by setting alpha to 0
            # we simply toggle by calling showGrid with inverse
            # here we check by trying to call showGrid and keeping state
            if getattr(self.waveform_widget, "_grid_on", True):
                self.waveform_widget.main_plot.showGrid(x=False, y=False)
                self.waveform_widget._grid_on = False
            else:
                self.waveform_widget.main_plot.showGrid(x=True, y=True, alpha=0.3)
                self.waveform_widget._grid_on = True
        except Exception:
            pass

    def on_data_updated(self):
        """统一数据更新"""
        logger.debug("波形显示数据更新触发")

        # 更新所有数值显示
        for i in range(self.signal_tree.topLevelItemCount()):
            category_item = self.signal_tree.topLevelItem(i)
            for j in range(category_item.childCount()):
                signal_item = category_item.child(j)
                signal_id = signal_item.data(0, Qt.UserRole)
                if signal_id and signal_id in self.controller.selected_signals:
                    latest_value = self.controller.data_buffer.get_latest_value(
                        signal_id
                    )
                    if latest_value is not None:
                        # 获取信号信息以确定类型
                        signal_info = self.controller.signal_manager.get_signal_info(
                            signal_id
                        )
                        if signal_info:
                            if signal_info["type"] == "bool":
                                value_str = "1" if latest_value else "0"
                            else:
                                # 模拟信号：根据值大小决定显示精度
                                if abs(latest_value) < 0.1:
                                    value_str = f"{latest_value:.4f}"
                                elif abs(latest_value) < 1:
                                    value_str = f"{latest_value:.3f}"
                                elif abs(latest_value) < 10:
                                    value_str = f"{latest_value:.2f}"
                                elif abs(latest_value) < 100:
                                    value_str = f"{latest_value:.1f}"
                                else:
                                    value_str = f"{int(latest_value)}"
                        else:
                            value_str = str(latest_value)

                        signal_item.setText(2, value_str)

        # 更新所有绘图
        self.waveform_widget.update_all_plots()
        if self.auto_range_check.isChecked():
            self.waveform_widget.auto_range()

    def add_send_data(self, data_buffer, timestamp=None):
        """添加发送数据（供外部调用）"""
        self.controller.add_send_data(data_buffer, timestamp)

    def add_receive_data(self, parsed_data, device_type, timestamp=None):
        """添加接收数据（供外部调用）"""
        self.controller.add_receive_data(parsed_data, device_type, timestamp)

    def shutdown(self) -> None:
        """Release resources ahead of application shutdown."""
        try:
            if getattr(self, "controller", None) is not None:
                self.controller.shutdown()
        except Exception:
            pass

    def save_settings(self):
        """Persist WaveformDisplay settings using the central store."""
        try:
            order: list[str] = []
            try:
                for i in range(self.signal_tree.topLevelItemCount()):
                    cat = self.signal_tree.topLevelItem(i)
                    for j in range(cat.childCount()):
                        item = cat.child(j)
                        if item.checkState(0) == Qt.Checked:
                            sid = item.data(0, Qt.UserRole)
                            if sid:
                                order.append(str(sid))
            except Exception:
                order = []

            palette: dict[str, str] = {}
            try:
                curves = getattr(self.waveform_widget, "curves", {})
                for sid, info in curves.items():
                    color = info.get("color")
                    if color:
                        palette[str(sid)] = color
            except Exception:
                palette = {}

            splitter_sizes = None
            try:
                if getattr(self, "splitter", None) is not None:
                    splitter_sizes = [int(x) for x in self.splitter.sizes()]
            except Exception:
                splitter_sizes = None

            state = WaveformSettings(
                selected_signals=list(self.controller.get_selected_signals()),
                time_range=self.time_range_combo.currentText(),
                auto_range=self.auto_range_check.isChecked(),
                last_export_path=getattr(self, "_last_export_path", ""),
                signal_order=order,
                splitter_sizes=splitter_sizes,
                palette=palette,
            )
            save_waveform_settings(state)
        except Exception:
            logger.exception("保存 WaveformDisplay 设置失败")

    def load_settings(self):
        """Load persisted WaveformDisplay settings and apply to UI."""
        try:
            stored = load_waveform_settings()
            sel = stored.selected_signals or []
            time_range = stored.time_range or self.time_range_combo.currentText()
            auto_range = stored.auto_range
            last_export = stored.last_export_path or ""
            signal_order = stored.signal_order or []
            splitter_sizes = stored.splitter_sizes

            # apply time range and auto range
            try:
                if time_range:
                    self.time_range_combo.setCurrentText(time_range)
            except Exception:
                pass
            try:
                if splitter_sizes and getattr(self, "splitter", None) is not None:
                    self.splitter.setSizes(splitter_sizes)
            except Exception:
                pass

            # apply auto-range and remember last export if present
            try:
                self.auto_range_check.setChecked(bool(auto_range))
            except Exception:
                pass
            try:
                if last_export:
                    self._last_export_path = last_export
            except Exception:
                pass

            # apply selected signals: find items in tree and check them
            if sel:
                # build a lookup of signal_id -> QTreeWidgetItem
                lookup = {}
                for i in range(self.signal_tree.topLevelItemCount()):
                    cat = self.signal_tree.topLevelItem(i)
                    for j in range(cat.childCount()):
                        item = cat.child(j)
                        sid = item.data(0, Qt.UserRole)
                        if sid:
                            lookup[str(sid)] = item

                # If saved order exists, apply it first so plots are added in
                # the saved order; otherwise, fall back to sel order.
                apply_order = signal_order if signal_order else sel

                # Block tree signals while restoring to avoid itemChanged handlers.
                try:
                    self.signal_tree.blockSignals(True)
                except Exception:
                    pass

                try:
                    for sid in apply_order:
                        item = lookup.get(str(sid))
                        if item is not None:
                            # set checked state; tree signals are blocked
                            item.setCheckState(0, Qt.Checked)
                            try:
                                info = self.controller.signal_manager.get_signal_info(
                                    sid
                                )
                                if info is None:
                                    continue
                                self.controller.select_signal(sid)
                                # add plot in the same order
                                self.waveform_widget.add_signal_plot(sid, info)
                            except Exception:
                                pass
                finally:
                    try:
                        self.signal_tree.blockSignals(False)
                    except Exception:
                        pass

            # try to restore saved palette/colors if any
            applied_palette = False
            try:
                if stored.palette:
                    applied_palette = self._apply_palette_mapping(stored.palette)
            except Exception:
                applied_palette = False

            if not applied_palette:
                try:
                    self._load_palette_from_settings(silent=True)
                except Exception:
                    pass

        except Exception:
            logger.exception("加载 WaveformDisplay 设置失败")

    # Helpers: resolve SettingsDialog class (palette I/O centralized in dialog)
    def _get_settings_dialog_cls(self):
        """Return the SettingsDialog class if available, trying import if needed."""
        if getattr(self, "_settings_dialog_cls", None):
            return self._settings_dialog_cls
        try:
            from gui.settings_dialog import SettingsDialog

            self._settings_dialog_cls = SettingsDialog
            return SettingsDialog
        except Exception:
            return None

    def _apply_palette_mapping(self, mapping: dict) -> bool:
        if not mapping:
            return False

        applied = False
        for key, color in (mapping or {}).items():
            try:
                self.waveform_widget.set_curve_color(key, color)
                applied = True
            except Exception:
                try:
                    self.waveform_widget.set_curve_color(int(key), color)
                    applied = True
                except Exception:
                    pass

        if applied:
            try:
                self._rebuild_legend()
            except Exception:
                pass
        return applied

    def _load_palette_from_settings(self, silent: bool = False) -> bool:
        cls = self._get_settings_dialog_cls()
        if not cls:
            if not silent:
                QMessageBox.information(self, "配色", "设置对话框不可用，无法加载配色")
            return False

        try:
            mapping = cls.load_palette_from_settings()
        except Exception:
            if not silent:
                QMessageBox.critical(self, "配色", "读取配色时发生错误")
            return False

        if not mapping:
            return False

        applied = self._apply_palette_mapping(mapping)
        if applied:
            try:
                state = load_waveform_settings()
                state.palette = {str(k): str(v) for k, v in mapping.items()}
                save_waveform_settings(state)
            except Exception:
                pass
        return applied

    def _on_thumb_clicked(self):
        """Generate a small thumbnail snapshot of the current plot."""
        try:
            if getattr(self, "graphics_view", None) is None:
                # fallback to waveform_widget's graphics if available
                gv = getattr(self.waveform_widget, "graphics_view", None)
            else:
                gv = self.graphics_view

            if gv is None:
                return

            # grab returns a QPixmap
            try:
                pix = gv.grab()
            except Exception:
                # some versions may require grabWidget
                try:
                    pix = gv.grabWidget()
                except Exception:
                    pix = None

            if pix is None:
                return

            # scale to thumbnail size while keeping aspect
            thumb = pix.scaled(self.thumb_label.size(), Qt.KeepAspectRatio)
            self.thumb_label.setPixmap(thumb)
            self.thumb_label.setVisible(True)
        except Exception:
            pass
