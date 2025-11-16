# waveform_display.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                               QTreeWidgetItem, QPushButton, QComboBox, QLabel, 
                               QSplitter, QCheckBox, QMessageBox, QFileDialog)
from PySide6.QtCore import Qt
from waveform_controller import WaveformController
from waveform_plot import WaveformPlotWidget
import logging

# 创建日志记录器
logger = logging.getLogger("WaveformDisplay")

class WaveformDisplay(QWidget):
    """波形显示主界面"""
    
    def __init__(self, parent=None, event_bus=None):
        super().__init__(parent)
        self.controller = WaveformController()
        self.event_bus = None
        self.init_ui()
        self.setup_connections()
        self.bind_event_bus(event_bus)

    def bind_event_bus(self, event_bus):
        """绑定或更换事件总线，确保视图层与控制层解耦"""
        if self.event_bus is event_bus:
            return
        # 解除旧连接
        if self.event_bus:
            try:
                self.event_bus.waveform_send.disconnect(self._on_bus_waveform_send)
                self.event_bus.waveform_receive.disconnect(self._on_bus_waveform_receive)
                self.event_bus.recording_toggle.disconnect(self._on_bus_recording_toggle)
            except Exception:
                pass
        self.event_bus = event_bus
        if event_bus:
            event_bus.waveform_send.connect(self._on_bus_waveform_send)
            event_bus.waveform_receive.connect(self._on_bus_waveform_receive)
            event_bus.recording_toggle.connect(self._on_bus_recording_toggle)

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
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # 工具栏
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)
        
        # 分割区域
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧信号选择树
        self.signal_tree = self.create_signal_tree()
        splitter.addWidget(self.signal_tree)
        
        # 右侧波形显示区域
        self.waveform_widget = WaveformPlotWidget(self.controller)
        splitter.addWidget(self.waveform_widget)
        
        splitter.setSizes([350, 650])
        layout.addWidget(splitter)
        
    def create_toolbar(self):
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setSpacing(8)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.record_btn = QPushButton("开始记录")
        self.record_btn.setCheckable(True)
        self.record_btn.setMinimumHeight(30)
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setCheckable(True)
        self.pause_btn.setMinimumHeight(30)
        self.clear_btn = QPushButton("清空波形")
        self.clear_btn.setMinimumHeight(30)
        self.export_btn = QPushButton("导出数据")
        self.export_btn.setMinimumHeight(30)
        
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
        layout.addStretch()
        layout.addWidget(QLabel("时间范围:"))
        layout.addWidget(self.time_range_combo)
        layout.addWidget(self.auto_range_check)
        
        return toolbar
        
    def create_signal_tree(self):
        tree = QTreeWidget()
        tree.setHeaderLabels(["信号选择", "状态", "数值"])
        tree.setColumnCount(3)
        tree.setColumnWidth(0, 220)
        tree.setColumnWidth(1, 60)
        tree.setColumnWidth(2, 70)
        tree.setMinimumHeight(600)  # 增加最小高度
        
        categories = self.controller.signal_manager.get_signal_categories()
        for category in categories:
            category_item = QTreeWidgetItem(tree, [category, "", ""])
            category_item.setExpanded(True)
            signals = self.controller.signal_manager.get_signals_by_category(category)
            
            for signal_id, signal_info in signals:
                signal_item = QTreeWidgetItem(category_item, 
                                            [signal_info['name'], '○', '--'])
                signal_item.setData(0, Qt.UserRole, signal_id)
                signal_item.setCheckState(0, Qt.Unchecked)
                
        return tree
    
    def setup_connections(self):
        """设置信号连接"""
        self.record_btn.toggled.connect(self.on_record_toggled)
        self.pause_btn.toggled.connect(self.on_pause_toggled)
        self.clear_btn.clicked.connect(self.on_clear_clicked)
        self.export_btn.clicked.connect(self.on_export_clicked)
        self.time_range_combo.currentTextChanged.connect(self.on_time_range_changed)
        self.auto_range_check.toggled.connect(self.on_auto_range_toggled)
        self.signal_tree.itemChanged.connect(self.on_signal_selection_changed)
        
        # 改为统一更新
        self.controller.data_updated.connect(self.on_data_updated)
    
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
            path, fmt = QFileDialog.getSaveFileName(self, "导出数据", "waveform_export.csv", "CSV 文件 (*.csv);;JSON 文件 (*.json)")
            if not path:
                return

            # 规范格式
            fmt = 'csv' if path.lower().endswith('.csv') or 'csv' in fmt.lower() else 'json'

            timestamps = self.controller.get_timestamps()

            # 组织数据为行格式（时间戳为第一列）
            rows = []
            for i, ts in enumerate(timestamps):
                row = {'timestamp': ts}
                for sig in selected:
                    vals = self.controller.get_signal_data(sig)
                    row[sig] = vals[i] if i < len(vals) else None
                rows.append(row)

            if fmt == 'csv':
                import csv
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['timestamp'] + selected)
                    writer.writeheader()
                    for r in rows:
                        writer.writerow(r)
            else:
                import json
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(rows, f, ensure_ascii=False, indent=2)

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
            "1小时": 3600
        }
        seconds = time_ranges.get(text, 600)
        self.waveform_widget.set_time_range(seconds)
    
    def on_auto_range_toggled(self, checked):
        """自动范围切换"""
        if checked:
            self.waveform_widget.auto_range()
    
    def on_signal_selection_changed(self, item, column):
        """信号选择改变"""
        if column != 0:
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
            item.setText(1, '●')
            
            # 立即显示当前值
            latest_value = self.controller.data_buffer.get_latest_value(signal_id)
            if latest_value is not None:
                if signal_info['type'] == 'bool':
                    value_str = "1" if latest_value else "0"
                else:
                    value_str = f"{latest_value:.2f}"
                item.setText(2, value_str)
                
            logger.info(f"选择信号: {signal_info['name']}, 类型: {signal_info['type']}")
            
        else:
            # 取消选中
            self.controller.deselect_signal(signal_id)
            self.waveform_widget.remove_signal_plot(signal_id)
            item.setText(1, '○')
            item.setText(2, '--')
            logger.info(f"取消选择信号: {signal_info['name']}")
    
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
                    latest_value = self.controller.data_buffer.get_latest_value(signal_id)
                    if latest_value is not None:
                        # 获取信号信息以确定类型
                        signal_info = self.controller.signal_manager.get_signal_info(signal_id)
                        if signal_info:
                            if signal_info['type'] == 'bool':
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

    def add_send_data(self, data_buffer, timestamp=None):
        """添加发送数据（供外部调用）"""
        self.controller.add_send_data(data_buffer, timestamp)
    
    def add_receive_data(self, parsed_data, device_type, timestamp=None):
        """添加接收数据（供外部调用）"""
        self.controller.add_receive_data(parsed_data, device_type, timestamp)