import queue
import sys
import struct
import threading
import time
from datetime import datetime
from collections import deque
from typing import Any, Deque, Dict, List, Tuple
import psutil
import gc
import logging
from logging.handlers import RotatingFileHandler
import json
from pathlib import Path

from setup_qt_environment import setup_qt_environment
setup_qt_environment()

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QGroupBox, QLabel, QLineEdit, 
                               QPushButton, QTextEdit, QTableWidget, 
                               QTableWidgetItem, QSpinBox, QComboBox, 
                               QTabWidget, QCheckBox, QHeaderView, QMessageBox,
                               QScrollArea, QTreeWidget, QTreeWidgetItem,
                               QSplitter, QStyle)
from PySide6.QtCore import QTimer, Qt, Signal, QObject, QThread, Slot, QMetaObject
from PySide6.QtGui import QFont, QColor, QIcon
from PySide6.QtCore import QAbstractTableModel, QModelIndex

# 导入波形显示模块
from waveform_display import WaveformDisplay
from views.event_bus import ViewEventBus

# 日志与配置路径
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

LOG_PATH = BASE_DIR / "acu_simulator.log"
CONFIG_PATH = BASE_DIR / "acu_config.json"

# 如果配置不存在，创建一个带合理默认值的配置文件（首次运行时生成）
try:
    if not CONFIG_PATH.exists():
        default_cfg = {
            'acu_ip': '10.2.0.1',
            'acu_send_port': 49152,
            'acu_receive_port': 49156,
            'target_ip': '10.2.0.5',
            'target_receive_port': 49152,
            'period_ms': 100
        }
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(default_cfg, f, indent=2, ensure_ascii=False)
except Exception:
    pass

# 配置日志（滚动日志）
logger = logging.getLogger("ACUSim")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(str(LOG_PATH), maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(fmt)
    logger.addHandler(console)

# 配置DataBuffer日志
data_buffer_logger = logging.getLogger("DataBuffer")
data_buffer_logger.setLevel(logging.INFO)
data_buffer_logger.addHandler(handler)

# 配置WaveformController日志
waveform_logger = logging.getLogger("WaveformController")
waveform_logger.setLevel(logging.INFO)
waveform_logger.addHandler(handler)

ParseTask = Tuple[bytes, str, int, str]
RecordDict = Dict[str, Any]

from controllers.communication_controller import CommunicationController
from controllers.parse_controller import ParseController
from model.control_state import ControlState
from model.device import Device, DeviceConfig
from controllers.frame_builder import FrameBuilder

# 使用新的 CommunicationController 管理底层 socket 与线程

class ParseWorker(QObject):
    parse_result = Signal(dict)

    def __init__(self, parse_controller, parse_queue, parent=None):
        super().__init__(parent)
        self.parse_controller = parse_controller
        self.parse_queue = parse_queue
        self._running = False
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._drain)

    @Slot()
    def start(self):
        if self._running:
            return
        self._running = True
        self._timer.start()

    @Slot()
    def stop(self):
        if not self._running:
            return
        self._running = False
        self._timer.stop()

    def _drain(self):
        if not self._running:
            return
        import queue as _q
        loops = 0
        while self._running and loops < 64:
            try:
                item = self.parse_queue.get_nowait()
            except _q.Empty:
                break
            try:
                data, address, port, timestamp = item
                device_type = self.parse_controller.device_type_from_port(port)
                parsed = self.parse_controller.parse(data, port)
                parsed_record = {
                    'timestamp': timestamp,
                    'address': address,
                    'device_type': device_type,
                    'data_length': len(data),
                    'parsed_data': parsed
                }
                self.parse_result.emit(parsed_record)
            except Exception as e:
                self.parse_result.emit({
                    'timestamp': timestamp if 'timestamp' in locals() else '',
                    'address': address if 'address' in locals() else '',
                    'device_type': 'ERROR',
                    'data_length': len(data) if 'data' in locals() else 0,
                    'parsed_data': {"错误": str(e)}
                })
            loops += 1


class FormatWorker(QObject):
    def __init__(self, format_queue, formatted_queue, parent=None):
        super().__init__(parent)
        self.format_queue = format_queue
        self.formatted_queue = formatted_queue
        self._running = False
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._drain)

    @Slot()
    def start(self):
        if self._running:
            return
        self._running = True
        self._timer.start()

    @Slot()
    def stop(self):
        if not self._running:
            return
        self._running = False
        self._timer.stop()

    def _drain(self):
        if not self._running:
            return
        import queue as _q
        loops = 0
        while self._running and loops < 128:
            try:
                item = self.format_queue.get_nowait()
            except _q.Empty:
                break
            try:
                rec = item
                data = rec.get('data', b'') or b''
                try:
                    hex_str = ' '.join(f"{b:02X}" for b in data)
                except Exception:
                    hex_str = ''
                rec['hex'] = hex_str
                try:
                    self.formatted_queue.put(rec)
                except Exception:
                    pass
            except Exception:
                continue
            loops += 1


class ACUSimulator(QMainWindow):
    def __init__(self, *, comm=None, parse_controller=None, control_state=None,
                 acu_device=None, frame_builder=None, view_bus=None,
                 enable_dialogs: bool = True):
        super().__init__()
        # 使用新的通信控制器替代旧的 EthernetWorker
        self.comm = comm or CommunicationController()
        self._enable_dialogs = enable_dialogs
        self.worker_thread = None
        self.send_timer = QTimer()
        self.send_data_buffer = bytearray(320)
        
        # 解析线程相关（使用统一的 ParseController）
        self.parse_queue: queue.Queue[ParseTask] = queue.Queue()
        self.parse_controller = parse_controller or ParseController()
        self.parse_worker = None
        self.parse_worker_thread = None
        
        # 格式化线程
        self.format_queue: queue.Queue[RecordDict] = queue.Queue()
        self.formatted_queue: queue.Queue[RecordDict] = queue.Queue()
        self.format_worker = None
        self.format_worker_thread = None
        
        # 内存管理配置
        self.max_parse_records = 5000
        self.parsed_data_history: Deque[RecordDict] = deque(maxlen=self.max_parse_records)

        # 用于批量更新 UI 的缓冲
        self.parse_table_buffer: Deque[RecordDict] = deque()
        self.ui_update_timer = QTimer()
        self.ui_update_interval = 200  # ms
        
        # 非阻塞重建表格的定时器
        self._rebuild_timer = QTimer()
        self._rebuild_timer.setInterval(20)
        self._rebuild_timer.timeout.connect(self._rebuild_tick)
        self._rebuild_in_progress = False
        self._rebuild_entries: List[RecordDict] = []
        self._rebuild_index = 0
        self._rebuild_chunk_size = 50
        
        self.ccu_life_signal = 0
        self.is_sending = False
        
        # 扩展控制值字典（保持原结构供 UI 使用）
        self.control_values = {
            'bool_commands': {},
            'freq_controls': {},
            'isolation_commands': {},
            'start_commands': {},
            'chu_controls': {},
            'redundant_commands': {},
            'start_times': {},
            'branch_voltages': {},
            'battery_temp': 25
        }
        # 新的模型层对象（ACU 设备 + 控制状态 + 帧构建器）支持依赖注入
        cs = control_state or ControlState()
        dev = acu_device or Device(DeviceConfig(name="ACU", ip="10.2.0.1", send_port=49152, receive_port=49156, category="ACU"))
        self._frame_builder = frame_builder or FrameBuilder(cs, dev)
        # 确保本地引用与 FrameBuilder 内一致
        self._control_state_model = getattr(self._frame_builder, 'control_state', cs)
        self._acu_device = getattr(self._frame_builder, 'acu_device', dev)
        
        # 内存管理
        self.memory_check_timer = QTimer()
        self.memory_check_interval = 10000
        self.last_memory_check = time.time()
        
        # 事件总线 + 波形显示（实现视图解耦）
        self.view_bus = view_bus or ViewEventBus()
        self.waveform_display = WaveformDisplay(event_bus=self.view_bus)
        
        self.init_ui()
        self.init_data()
        self.setup_connections()
        self.setup_memory_management()
        self._setup_workers()

    def _setup_workers(self):
        """创建解析/格式化工作线程与定时器，并启动 UI 刷新。"""
        self._create_parse_worker()
        self._create_format_worker()

        # 兼容旧测试字段（不再使用 Python threading）
        self.parse_worker_thread = None
        self.format_worker_thread = None

        self.ui_update_timer.timeout.connect(self.flush_ui_buffers)
        self.ui_update_timer.start(self.ui_update_interval)

        self.prepare_send_data()
        self.update_data_preview()

    def _create_parse_worker(self):
        self.parse_worker = ParseWorker(self.parse_controller, self.parse_queue)
        self.parse_thread = QThread(self)
        self.parse_worker.moveToThread(self.parse_thread)
        self.parse_worker.parse_result.connect(self.on_parse_result)
        self.parse_thread.started.connect(self.parse_worker.start)
        self.parse_thread.start()

    def _create_format_worker(self):
        self.format_worker = FormatWorker(self.format_queue, self.formatted_queue)
        self.format_thread = QThread(self)
        self.format_worker.moveToThread(self.format_thread)
        self.format_thread.started.connect(self.format_worker.start)
        self.format_thread.start()

    def _start_background_workers_if_needed(self):
        """确保 QThread 工作者在线；如已停止则重建并启动。"""
        if not getattr(self, 'parse_thread', None) or not self.parse_thread.isRunning():
            self._cleanup_parse_worker()
            self._create_parse_worker()
        if not getattr(self, 'format_thread', None) or not self.format_thread.isRunning():
            self._cleanup_format_worker()
            self._create_format_worker()

    def _stop_background_workers(self):
        """停止解析/格式化 QThread 工作者并清空相关队列。"""
        self._cleanup_parse_worker()
        self._cleanup_format_worker()
        # 清空解析队列
        try:
            while True:
                self.parse_queue.get_nowait()
        except Exception:
            pass
        # 清空格式化队列
        try:
            while True:
                self.format_queue.get_nowait()
        except Exception:
            pass

    def _cleanup_parse_worker(self):
        try:
            if getattr(self, 'parse_worker', None):
                QMetaObject.invokeMethod(self.parse_worker, "stop", Qt.BlockingQueuedConnection)
            if getattr(self, 'parse_thread', None):
                self.parse_thread.quit(); self.parse_thread.wait(1000)
        except Exception:
            pass
        finally:
            self.parse_worker = None
            self.parse_thread = None
            self.parse_worker_thread = None

    def _cleanup_format_worker(self):
        try:
            if getattr(self, 'format_worker', None):
                QMetaObject.invokeMethod(self.format_worker, "stop", Qt.BlockingQueuedConnection)
            if getattr(self, 'format_thread', None):
                self.format_thread.quit(); self.format_thread.wait(1000)
        except Exception:
            pass
        finally:
            self.format_worker = None
            self.format_thread = None
            self.format_worker_thread = None
    
    def init_ui(self):
        self.setWindowTitle("ACU Simulator - 辅助变流系统通信模拟器 (完整版)")
        self.setGeometry(50, 50, 1600, 1000)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)

        self.setup_config_tab()
        self.setup_send_tab()
        self.setup_waveform_tab()  # 替换原来的接收数据页面
        self.setup_parse_tab()
        self.setup_preview_tab()

        layout.addWidget(self.tab_widget)
    
    def setup_config_tab(self):
        """设置配置页面"""
        config_tab = QWidget()
        self.config_tab = config_tab
        config_layout = QVBoxLayout(config_tab)
        config_layout.setSpacing(10)
        
        splitter = QSplitter(Qt.Vertical)

        # ACU配置 (compact)
        acu_config_group = QGroupBox("ACU配置 (协议标准)")
        acu_config_layout = QHBoxLayout(acu_config_group)
        acu_config_layout.setSpacing(12)

        acu_ip_layout = QVBoxLayout()
        acu_ip_layout.addWidget(QLabel("ACU IP地址:"))
        self.acu_ip_edit = QLineEdit("10.2.0.1")
        self.acu_ip_edit.setMaximumWidth(150)
        acu_ip_layout.addWidget(self.acu_ip_edit)
        acu_config_layout.addLayout(acu_ip_layout)

        acu_send_layout = QVBoxLayout()
        acu_send_layout.addWidget(QLabel("ACU发送端口:"))
        self.acu_send_port_edit = QLineEdit("49152")
        self.acu_send_port_edit.setMaximumWidth(100)
        acu_send_layout.addWidget(self.acu_send_port_edit)
        acu_config_layout.addLayout(acu_send_layout)

        acu_receive_layout = QVBoxLayout()
        acu_receive_layout.addWidget(QLabel("ACU接收端口:"))
        self.acu_receive_port_edit = QLineEdit("49156")
        self.acu_receive_port_edit.setMaximumWidth(100)
        acu_receive_layout.addWidget(self.acu_receive_port_edit)
        acu_config_layout.addLayout(acu_receive_layout)

        acu_config_layout.addStretch()

        # 目标设备配置（紧凑水平布局）
        target_config_group = QGroupBox("目标设备配置")
        target_config_layout = QHBoxLayout(target_config_group)
        target_config_layout.setSpacing(12)

        target_ip_layout = QVBoxLayout()
        target_ip_layout.addWidget(QLabel("目标设备IP:"))
        self.target_ip_edit = QLineEdit("10.2.0.5")
        self.target_ip_edit.setMaximumWidth(150)
        target_ip_layout.addWidget(self.target_ip_edit)
        target_config_layout.addLayout(target_ip_layout)

        target_receive_layout = QVBoxLayout()
        target_receive_layout.addWidget(QLabel("目标接收端口:"))
        self.target_receive_port_edit = QLineEdit("49152")
        self.target_receive_port_edit.setMaximumWidth(100)
        target_receive_layout.addWidget(self.target_receive_port_edit)
        target_config_layout.addLayout(target_receive_layout)

        send_config_layout = QVBoxLayout()
        send_config_layout.addWidget(QLabel("发送周期(ms):"))
        self.period_spin = QSpinBox()
        self.period_spin.setRange(10, 1000)
        self.period_spin.setValue(100)
        self.period_spin.setMaximumWidth(100)
        send_config_layout.addWidget(self.period_spin)
        target_config_layout.addLayout(send_config_layout)

        target_config_layout.addStretch()

        # 顶部快速状态面板（连接状态、最近接收、接收计数、当前周期、预设）
        status_panel = QWidget()
        status_panel_layout = QHBoxLayout(status_panel)
        status_panel_layout.setContentsMargins(0, 0, 0, 0)
        status_panel_layout.setSpacing(12)

        # 连接状态指示（圆点 + 文字）
        self.conn_dot = QLabel()
        self.conn_dot.setFixedSize(14, 14)
        self.conn_dot.setStyleSheet("background-color:#d9534f; border-radius:7px;")
        self.conn_status_label = QLabel(" 未连接")
        conn_box = QWidget()
        conn_layout = QHBoxLayout(conn_box)
        conn_layout.setContentsMargins(0, 0, 0, 0)
        conn_layout.addWidget(self.conn_dot)
        conn_layout.addWidget(self.conn_status_label)
        status_panel_layout.addWidget(conn_box)

        # 最近接收
        self.top_last_recv = QLabel("最近接收: -")
        status_panel_layout.addWidget(self.top_last_recv)

        # 顶部显示的接收计数（与下方标签独立，避免布局重叠）
        self.top_receive_count = QLabel("接收: 0")
        status_panel_layout.addWidget(self.top_receive_count)

        # 当前发送周期显示（同步 period_spin）
        self.top_period_label = QLabel(f"周期: {self.period_spin.value()} ms")
        status_panel_layout.addWidget(self.top_period_label)

        # 预设下拉（占位）
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("默认")
        self.preset_combo.setMaximumWidth(160)
        status_panel_layout.addStretch()
        status_panel_layout.addWidget(self.preset_combo)

        config_layout.addWidget(status_panel)

        # 控制按钮 及 状态（右侧队列）
        control_group = QGroupBox("通信控制")
        control_layout = QHBoxLayout(control_group)

        self.start_btn = QPushButton("开始通信")
        self.stop_btn = QPushButton("停止通信")
        self.stop_btn.setEnabled(False)
        self.test_btn = QPushButton("单次发送测试")
        self.preview_btn = QPushButton("更新预览")
        self.save_config_btn = QPushButton("保存配置")
        self.load_config_btn = QPushButton("加载配置")

        # 使用标准样式图标增强视觉
        _style = QApplication.style()
        try:
            self.start_btn.setIcon(_style.standardIcon(QStyle.SP_MediaPlay))
            self.stop_btn.setIcon(_style.standardIcon(QStyle.SP_MediaStop))
            self.test_btn.setIcon(_style.standardIcon(QStyle.SP_MediaSeekForward))
            self.preview_btn.setIcon(_style.standardIcon(QStyle.SP_FileDialogContentsView))
            self.save_config_btn.setIcon(_style.standardIcon(QStyle.SP_DialogSaveButton))
            self.load_config_btn.setIcon(_style.standardIcon(QStyle.SP_DialogOpenButton))
        except Exception:
            pass

        for btn in [self.start_btn, self.stop_btn, self.test_btn, self.preview_btn]:
            btn.setFixedHeight(34)
            btn.setMinimumWidth(110)
        for btn in [self.save_config_btn, self.load_config_btn]:
            btn.setFixedHeight(28)
            btn.setMinimumWidth(90)

        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.test_btn)
        control_layout.addWidget(self.preview_btn)
        control_layout.addWidget(self.save_config_btn)
        control_layout.addWidget(self.load_config_btn)
        control_layout.addStretch()

        status_group = QGroupBox("通信状态")
        status_layout = QVBoxLayout(status_group)

        status_info_layout = QHBoxLayout()
        self.status_label = QLabel("就绪 - 按照协议标准配置")
        self.status_label.setStyleSheet("QLabel { background-color: #f8f8f8; padding: 8px; border: 1px solid #ddd; font-size: 10pt; }")
        self.status_label.setMinimumHeight(40)
        status_info_layout.addWidget(self.status_label)

        status_indicators_layout = QHBoxLayout()
        self.life_signal_label = QLabel("生命信号: 0")
        self.life_signal_label.setStyleSheet("QLabel { background-color: #e8f4ff; padding: 5px; border: 1px solid #cce6ff; font-size: 9pt; }")
        self.life_signal_label.setMinimumHeight(30)
        self.life_signal_label.setMinimumWidth(120)

        self.receive_count_label = QLabel("接收数据包: 0")
        self.receive_count_label.setStyleSheet("QLabel { background-color: #f7ffe8; padding: 5px; border: 1px solid #e6f6cc; font-size: 9pt; }")
        self.receive_count_label.setMinimumHeight(30)
        self.receive_count_label.setMinimumWidth(120)

        self.memory_status_label = QLabel("内存: 计算中...")
        self.memory_status_label.setStyleSheet("QLabel { background-color: #fff7e8; padding: 5px; border: 1px solid #f3e6cc; font-size: 9pt; }")
        self.memory_status_label.setMinimumHeight(30)
        self.memory_status_label.setMinimumWidth(180)

        status_indicators_layout.addWidget(self.life_signal_label)
        status_indicators_layout.addWidget(self.receive_count_label)
        status_indicators_layout.addWidget(self.memory_status_label)
        status_indicators_layout.addStretch()

        status_layout.addLayout(status_info_layout)
        status_layout.addLayout(status_indicators_layout)

        # 左右组合布局
        left_col = QVBoxLayout()
        left_col.addWidget(acu_config_group)
        left_col.addWidget(target_config_group)
        left_col.addStretch()

        right_col = QVBoxLayout()
        right_col.addWidget(control_group)
        right_col.addWidget(status_group)
        right_col.addStretch()

        main_h = QHBoxLayout()
        left_widget = QWidget()
        left_widget.setLayout(left_col)
        right_widget = QWidget()
        right_widget.setLayout(right_col)

        main_h.addWidget(left_widget, 2)
        main_h.addWidget(right_widget, 1)

        config_layout.addLayout(main_h)
        
        # 在通信配置页中加入协议信息，避免单独页面过于稀疏
        protocol_group = QGroupBox("通信协议信息")
        protocol_inner_layout = QVBoxLayout(protocol_group)
        protocol_info = """
通信协议标准 (IEC61375-2-3)

ACU设备配置:
• IP地址: 10.2.0.1
• 发送端口: 49152 (固定)
• 接收端口范围: 49153-49162

INV设备端口分配:
• INV1 (10.2.0.2): 发送端口49153
• INV2 (10.2.0.3): 发送端口49154  
• INV3 (10.2.0.4): 发送端口49155
• INV4 (10.2.0.5): 发送端口49156
• INV5 (10.2.0.6): 发送端口49157
• INV6 (10.2.0.7): 发送端口49158
• CHU3 (10.2.0.8): 发送端口49159
• CHU4 (10.2.0.9): 发送端口49160
• BCC1 (10.2.0.10): 发送端口49161
• BCC2 (10.2.0.11): 发送端口49162

通信参数:
• 传输方式: UDP
• ACU发送周期: 20ms
• 设备响应周期: 100ms
• 数据大小端: 大端(Big Endian)
• ACU发送数据长度: 320字节
• 设备响应数据长度: 64字节
        """
        protocol_text = QTextEdit()
        protocol_text.setPlainText(protocol_info)
        protocol_text.setReadOnly(True)
        protocol_text.setFont(QFont("Microsoft YaHei", 10))
        protocol_inner_layout.addWidget(protocol_text)
        config_layout.addWidget(protocol_group)

        self.tab_widget.addTab(config_tab, "通信配置")
    
    def setup_send_tab(self):
        """设置发送配置页面"""
        send_tab = QWidget()
        send_tab.setObjectName("send_tab")
        send_layout = QVBoxLayout(send_tab)
        send_layout.setSpacing(8)

        # 卡片样式，用于将多个控制组统一为卡片视觉（方法内局部定义）
        card_style = (
            "QGroupBox { background-color: #ffffff; border: 1px solid #e6e6e6; "
            "border-radius: 8px; margin-top: 6px; padding: 8px; }"
        )
        # 设置 send_tab 背景
        send_tab.setStyleSheet("QWidget#send_tab { background-color: #f6f7f8; }")

        send_scroll = QScrollArea()
        send_scroll.setWidgetResizable(True)
        send_scroll_content = QWidget()
        send_scroll_layout = QVBoxLayout(send_scroll_content)
        send_scroll_layout.setSpacing(8)

        # --- 基本控制命令 ---
        basic_control_group = QGroupBox("基本控制命令")
        basic_control_group.setStyleSheet(card_style)
        basic_layout = QVBoxLayout(basic_control_group)

        bool_grid_layout = QHBoxLayout()
        bool_left_layout = QVBoxLayout()
        bool_right_layout = QVBoxLayout()

        bool_commands = [
            ("均衡充电模式", 8, 0),
            ("停止工作", 8, 1),
            ("预发车测试", 8, 2),
            ("DCDC3隔离", 8, 6),
            ("DCDC4隔离", 8, 7),
            ("故障复位", 9, 0),
            ("空压机1启动", 9, 1),
            ("空压机2启动", 9, 2),
            ("除尘风机KM61", 9, 3),
            ("热保障KM62", 9, 4),
            ("热保障KM63", 9, 5),
            ("电池水泵KM65", 9, 6),
            ("柴油机起动", 9, 7)
        ]

        mid_point = (len(bool_commands) + 1) // 2
        for i, (name, byte_pos, bit_pos) in enumerate(bool_commands):
            checkbox = QCheckBox(name)
            checkbox.setToolTip(f"字节{byte_pos} bit{bit_pos}")
            # 初始化控制值（若已存在，保留原值）
            if (byte_pos, bit_pos) not in self.control_values['bool_commands']:
                self.control_values['bool_commands'][(byte_pos, bit_pos)] = False
            checkbox.setChecked(self.control_values['bool_commands'].get((byte_pos, bit_pos), False))
            checkbox.stateChanged.connect(
                lambda state, bp=byte_pos, bit=bit_pos: 
                self.on_bool_command_changed(bp, bit, state)
            )
            checkbox.clicked.connect(self.on_control_changed)

            if i < mid_point:
                bool_left_layout.addWidget(checkbox)
            else:
                bool_right_layout.addWidget(checkbox)

        bool_grid_layout.addLayout(bool_left_layout)
        bool_grid_layout.addLayout(bool_right_layout)
        basic_layout.addLayout(bool_grid_layout)

        # --- 频率控制 ---
        freq_group = QGroupBox("频率控制 (Hz)")
        freq_group.setStyleSheet(card_style)
        freq_layout = QHBoxLayout(freq_group)
        freq_layout.setSpacing(15)

        freq_commands = [
            ("INV2频率", 10),
            ("INV3频率", 12),
            ("INV4频率", 14),
            ("INV5频率", 16)
        ]

        for name, byte_pos in freq_commands:
            freq_item_layout = QVBoxLayout()
            freq_item_layout.addWidget(QLabel(name))
            spinbox = QSpinBox()
            spinbox.setRange(0, 500)
            spinbox.setValue(self.control_values['freq_controls'].get(byte_pos, 50))
            spinbox.setMaximumWidth(80)
            self.control_values['freq_controls'][byte_pos] = spinbox.value()
            spinbox.valueChanged.connect(
                lambda value, bp=byte_pos: 
                self.on_freq_control_changed(bp, value)
            )
            spinbox.valueChanged.connect(self.on_control_changed)
            freq_item_layout.addWidget(spinbox)
            freq_layout.addLayout(freq_item_layout)

        freq_layout.addStretch()

        send_scroll_layout.addWidget(basic_control_group)
        send_scroll_layout.addWidget(freq_group)

        # --- 设备控制命令 ---
        device_control_group = QGroupBox("设备控制命令")
        device_control_group.setStyleSheet(card_style)
        device_layout = QVBoxLayout(device_control_group)

        # 隔离指令
        isolation_group = QGroupBox("隔离指令")
        isolation_group.setStyleSheet(card_style)
        isolation_layout = QVBoxLayout(isolation_group)
        isolation_grid = QHBoxLayout()
        isolation_left = QVBoxLayout()
        isolation_right = QVBoxLayout()

        devices = ["INV1", "INV2", "INV3", "INV4", "INV5", "INV6", "BCC1", "BCC2"]

        for i, device in enumerate(devices):
            checkbox = QCheckBox(device)
            if i not in self.control_values['isolation_commands']:
                self.control_values['isolation_commands'][i] = False
            checkbox.setChecked(self.control_values['isolation_commands'].get(i, False))
            checkbox.stateChanged.connect(
                lambda state, idx=i: 
                self.on_isolation_command_changed(idx, state)
            )
            checkbox.clicked.connect(self.on_control_changed)

            if i < 4:
                isolation_left.addWidget(checkbox)
            else:
                isolation_right.addWidget(checkbox)

        isolation_grid.addLayout(isolation_left)
        isolation_grid.addLayout(isolation_right)
        isolation_layout.addLayout(isolation_grid)
        device_layout.addWidget(isolation_group)

        # 启动指令
        start_group = QGroupBox("启动指令")
        start_group.setStyleSheet(card_style)
        start_layout = QVBoxLayout(start_group)
        start_grid = QHBoxLayout()
        start_left = QVBoxLayout()
        start_right = QVBoxLayout()

        for i, device in enumerate(devices):
            checkbox = QCheckBox(device)
            if i not in self.control_values['start_commands']:
                self.control_values['start_commands'][i] = False
            checkbox.setChecked(self.control_values['start_commands'].get(i, False))
            checkbox.stateChanged.connect(
                lambda state, idx=i: 
                self.on_start_command_changed(idx, state)
            )
            checkbox.clicked.connect(self.on_control_changed)

            if i < 4:
                start_left.addWidget(checkbox)
            else:
                start_right.addWidget(checkbox)

        start_grid.addLayout(start_left)
        start_grid.addLayout(start_right)
        start_layout.addLayout(start_grid)
        device_layout.addWidget(start_group)

        # CHU控制
        chu_group = QGroupBox("CHU控制")
        chu_group.setStyleSheet(card_style)
        chu_layout = QHBoxLayout(chu_group)

        chu_commands = [
            ("CHU3启动", 66, 0),
            ("CHU4启动", 66, 1),
            ("CHU3隔离", 66, 2),
            ("CHU4隔离", 66, 3)
        ]

        for name, byte_pos, bit_pos in chu_commands:
            checkbox = QCheckBox(name)
            if (byte_pos, bit_pos) not in self.control_values['chu_controls']:
                self.control_values['chu_controls'][(byte_pos, bit_pos)] = False
            checkbox.setChecked(self.control_values['chu_controls'].get((byte_pos, bit_pos), False))
            checkbox.stateChanged.connect(
                lambda state, bp=byte_pos, bit=bit_pos: 
                self.on_chu_control_changed(bp, bit, state)
            )
            checkbox.clicked.connect(self.on_control_changed)
            chu_layout.addWidget(checkbox)

        chu_layout.addStretch()
        device_layout.addWidget(chu_group)

        # 冗余启动控制
        redundant_group = QGroupBox("冗余启动控制")
        redundant_group.setStyleSheet(card_style)
        redundant_layout = QHBoxLayout(redundant_group)

        redundant_commands = [
            ("INV1冗余启动", 67, 0),
            ("INV4冗余启动", 67, 1)
        ]

        for name, byte_pos, bit_pos in redundant_commands:
            checkbox = QCheckBox(name)
            if (byte_pos, bit_pos) not in self.control_values['redundant_commands']:
                self.control_values['redundant_commands'][(byte_pos, bit_pos)] = False
            checkbox.setChecked(self.control_values['redundant_commands'].get((byte_pos, bit_pos), False))
            checkbox.stateChanged.connect(
                lambda state, bp=byte_pos, bit=bit_pos: 
                self.on_redundant_command_changed(bp, bit, state)
            )
            checkbox.clicked.connect(self.on_control_changed)
            redundant_layout.addWidget(checkbox)

        redundant_layout.addStretch()
        device_layout.addWidget(redundant_group)

        send_scroll_layout.addWidget(device_control_group)

        # 启动时间配置
        start_time_group = QGroupBox("启动时间配置 (单位: 秒)")
        start_time_group.setStyleSheet(card_style)
        start_time_layout = QHBoxLayout(start_time_group)

        inv_devices = ["INV1", "INV2", "INV3", "INV4", "INV5", "INV6"]
        start_time_positions = [142, 144, 146, 148, 150, 152]

        for i, device in enumerate(inv_devices):
            time_layout = QVBoxLayout()
            time_layout.addWidget(QLabel(device))
            spinbox = QSpinBox()
            spinbox.setRange(0, 65535)
            spinbox.setValue(self.control_values['start_times'].get(start_time_positions[i], 0))
            spinbox.setMaximumWidth(80)
            self.control_values['start_times'][start_time_positions[i]] = spinbox.value()
            spinbox.valueChanged.connect(
                lambda value, pos=start_time_positions[i]: 
                self.on_start_time_changed(pos, value)
            )
            spinbox.valueChanged.connect(self.on_control_changed)
            time_layout.addWidget(spinbox)
            start_time_layout.addLayout(time_layout)

        start_time_layout.addStretch()
        send_scroll_layout.addWidget(start_time_group)

        # 电压和温度配置
        voltage_temp_group = QGroupBox("电压和温度配置")
        voltage_temp_group.setStyleSheet(card_style)
        voltage_temp_layout = QHBoxLayout(voltage_temp_group)

        # 支路电压
        branch_voltage_layout = QVBoxLayout()
        branch_voltage_layout.addWidget(QLabel("3支路电压 (V):"))
        self.branch3_voltage_spin = QSpinBox()
        self.branch3_voltage_spin.setRange(0, 1000)
        self.branch3_voltage_spin.setValue(self.control_values['branch_voltages'].get(154, 0))
        self.branch3_voltage_spin.setMaximumWidth(80)
        self.control_values['branch_voltages'][154] = self.branch3_voltage_spin.value()
        self.branch3_voltage_spin.valueChanged.connect(
            lambda value: self.on_branch_voltage_changed(154, value)
        )
        self.branch3_voltage_spin.valueChanged.connect(self.on_control_changed)
        branch_voltage_layout.addWidget(self.branch3_voltage_spin)

        branch_voltage_layout.addWidget(QLabel("4支路电压 (V):"))
        self.branch4_voltage_spin = QSpinBox()
        self.branch4_voltage_spin.setRange(0, 1000)
        self.branch4_voltage_spin.setValue(self.control_values['branch_voltages'].get(156, 0))
        self.branch4_voltage_spin.setMaximumWidth(80)
        self.control_values['branch_voltages'][156] = self.branch4_voltage_spin.value()
        self.branch4_voltage_spin.valueChanged.connect(
            lambda value: self.on_branch_voltage_changed(156, value)
        )
        self.branch4_voltage_spin.valueChanged.connect(self.on_control_changed)
        branch_voltage_layout.addWidget(self.branch4_voltage_spin)

        # 蓄电池温度
        battery_temp_layout = QVBoxLayout()
        battery_temp_layout.addWidget(QLabel("蓄电池温度 (°C):"))
        self.battery_temp_spin = QSpinBox()
        self.battery_temp_spin.setRange(-50, 150)
        self.battery_temp_spin.setValue(self.control_values.get('battery_temp', 25))
        self.battery_temp_spin.setMaximumWidth(80)
        self.control_values['battery_temp'] = self.battery_temp_spin.value()
        self.battery_temp_spin.valueChanged.connect(
            lambda value: self.on_battery_temp_changed(value)
        )
        self.battery_temp_spin.valueChanged.connect(self.on_control_changed)
        battery_temp_layout.addWidget(self.battery_temp_spin)

        voltage_temp_layout.addLayout(branch_voltage_layout)
        voltage_temp_layout.addLayout(battery_temp_layout)
        voltage_temp_layout.addStretch()

        send_scroll_layout.addWidget(voltage_temp_group)

        # 原始数据编辑
        raw_data_group = QGroupBox("原始数据编辑 (十六进制)")
        raw_data_group.setStyleSheet(card_style)
        raw_layout = QVBoxLayout(raw_data_group)
        self.raw_data_edit = QTextEdit()
        self.raw_data_edit.setMaximumHeight(120)
        self.raw_data_edit.setPlaceholderText("可在此输入十六进制数据覆盖自动生成的数据")
        raw_layout.addWidget(self.raw_data_edit)

        send_scroll_layout.addWidget(raw_data_group)
        send_scroll_layout.addStretch()

        send_scroll.setWidget(send_scroll_content)
        send_layout.addWidget(send_scroll)

        self.tab_widget.addTab(send_tab, "发送配置")
    
    def setup_waveform_tab(self):
        """设置波形显示页面（替换原来的接收数据页面）"""
        self.tab_widget.addTab(self.waveform_display, "波形显示")
    
    def setup_parse_tab(self):
        """设置协议解析页面"""
        parse_tab = QWidget()
        parse_layout = QVBoxLayout(parse_tab)
        parse_layout.setSpacing(8)
        
        splitter = QSplitter(Qt.Vertical)
        
        # 解析结果显示区域
        parse_display_group = QGroupBox("协议解析结果")
        parse_display_layout = QVBoxLayout(parse_display_group)
        
        self.parse_tree = QTreeWidget()
        self.parse_tree.setHeaderLabels(["参数", "值", "单位"])
        self.parse_tree.setColumnCount(3)
        self.parse_tree.setColumnWidth(0, 300)
        self.parse_tree.setColumnWidth(1, 200)
        self.parse_tree.setColumnWidth(2, 100)
        parse_display_layout.addWidget(self.parse_tree)
        
        # 解析历史记录
        parse_history_group = QGroupBox("解析历史记录")
        parse_history_layout = QVBoxLayout(parse_history_group)
        
        self.parse_history_table = QTableWidget()
        self.parse_history_table.setColumnCount(5)
        self.parse_history_table.setHorizontalHeaderLabels(["时间", "来源", "设备类型", "数据长度", "解析状态"])
        self.parse_history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.parse_history_table.doubleClicked.connect(self.on_parse_history_double_clicked)
        
        header = self.parse_history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        
        parse_history_layout.addWidget(self.parse_history_table)
        
        parse_control_layout = QHBoxLayout()
        clear_parse_btn = QPushButton("清空解析记录")
        clear_parse_btn.clicked.connect(self.clear_parse_history)
        clear_parse_btn.setFixedHeight(35)
        parse_control_layout.addWidget(clear_parse_btn)
        parse_control_layout.addStretch()
        
        parse_history_layout.addLayout(parse_control_layout)
        
        splitter.addWidget(parse_display_group)
        splitter.addWidget(parse_history_group)
        splitter.setSizes([400, 300])
        
        parse_layout.addWidget(splitter)
        
        self.tab_widget.addTab(parse_tab, "协议解析")
    
    def setup_preview_tab(self):
        """设置数据预览页面"""
        preview_tab = QWidget()
        preview_layout = QVBoxLayout(preview_tab)
        preview_layout.setSpacing(8)
        
        preview_group = QGroupBox("当前发送数据预览")
        preview_layout.addWidget(preview_group)
        
        preview_inner_layout = QVBoxLayout(preview_group)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        font = QFont("Consolas", 10)
        self.preview_text.setFont(font)
        preview_inner_layout.addWidget(self.preview_text)
        
        self.tab_widget.addTab(preview_tab, "数据预览")
    
    def setup_connections(self):
        """设置信号连接"""
        self.start_btn.clicked.connect(self.start_communication)
        self.stop_btn.clicked.connect(self.stop_communication)
        self.test_btn.clicked.connect(self.send_test_data)
        self.preview_btn.clicked.connect(self.update_data_preview)
        self.save_config_btn.clicked.connect(self.save_config)
        self.load_config_btn.clicked.connect(self.load_config)
        self.send_timer.timeout.connect(self.send_periodic_data)
        # 将 CommunicationController 的回调适配为 UI 方法
        self.comm.on_receive = lambda data, addr: self.on_data_received_comm(data, addr)
        self.comm.on_error = lambda msg: self.on_error_occurred(msg)
        self.comm.on_status = lambda msg: self.on_status_updated(msg)
        
        # 确保所有控件变化都能触发预览更新
        self.period_spin.valueChanged.connect(self.on_control_changed)
        self.raw_data_edit.textChanged.connect(self.on_control_changed)
        
        # 连接所有配置变化的信号
        self.acu_ip_edit.textChanged.connect(self.on_control_changed)
        self.acu_send_port_edit.textChanged.connect(self.on_control_changed)
        self.acu_receive_port_edit.textChanged.connect(self.on_control_changed)
        self.target_ip_edit.textChanged.connect(self.on_control_changed)
        self.target_receive_port_edit.textChanged.connect(self.on_control_changed)

    def on_data_received_comm(self, data: bytes, addr: tuple):
        """CommunicationController 接收回调适配器（addr=(ip,port)）"""
        try:
            ip, port = addr[0], addr[1]
        except Exception:
            ip = str(addr)
            port = 0
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # 入队解析
        self.parse_queue.put((data, f"{ip}:{port}", port, timestamp))

        # 为波形显示做快速解析（非阻塞）
        try:
            device_type = self.parse_controller.device_type_from_port(port)
            device_category = self.parse_controller.category_from_device(device_type)
            if device_category in ["INV", "CHU", "BCC", "DUMMY"]:
                parsed_data = self.parse_controller.parse(data, port)
                self.view_bus.waveform_receive.emit(parsed_data, device_type, time.time())
        except Exception as e:
            logger.exception(f"波形快速解析错误: {e}")
    
    def setup_memory_management(self):
        """设置内存管理"""
        self.memory_check_timer.timeout.connect(self.check_memory_usage)
        self.memory_check_timer.start(self.memory_check_interval)

        # 加载配置（如果存在）
        try:
            self.load_config()
        except Exception as e:
            logger.warning(f"加载配置失败: {e}")
    
    def init_data(self):
        """初始化数据"""
        # 初始化频率控制值
        self.control_values['freq_controls'][10] = 50  # INV2频率
        self.control_values['freq_controls'][12] = 50  # INV3频率
        self.control_values['freq_controls'][14] = 50  # INV4频率
        self.control_values['freq_controls'][16] = 50  # INV5频率

        self.prepare_send_data()
        self.update_data_preview()
    
    def on_control_changed(self):
        """当任何控件发生变化时调用"""
        self.prepare_send_data()
        self.update_data_preview()
    
    def on_bool_command_changed(self, byte_pos, bit_pos, state):
        """布尔命令变化"""
        self.control_values['bool_commands'][(byte_pos, bit_pos)] = bool(state)
        self.prepare_send_data()
        self.update_data_preview()
    
    def on_freq_control_changed(self, byte_pos, value):
        """频率控制变化"""
        self.control_values['freq_controls'][byte_pos] = value
        self.prepare_send_data()
        self.update_data_preview()
    
    def on_isolation_command_changed(self, index, state):
        """隔离指令变化"""
        self.control_values['isolation_commands'][index] = bool(state)
        self.prepare_send_data()
        self.update_data_preview()
    
    def on_start_command_changed(self, index, state):
        """启动指令变化"""
        self.control_values['start_commands'][index] = bool(state)
        self.prepare_send_data()
        self.update_data_preview()
    
    def on_chu_control_changed(self, byte_pos, bit_pos, state):
        """CHU控制变化"""
        self.control_values['chu_controls'][(byte_pos, bit_pos)] = bool(state)
        self.prepare_send_data()
        self.update_data_preview()
    
    def on_redundant_command_changed(self, byte_pos, bit_pos, state):
        """冗余启动控制变化"""
        self.control_values['redundant_commands'][(byte_pos, bit_pos)] = bool(state)
        self.prepare_send_data()
        self.update_data_preview()
    
    def on_start_time_changed(self, byte_pos, value):
        """启动时间变化"""
        self.control_values['start_times'][byte_pos] = value
        self.prepare_send_data()
        self.update_data_preview()
    
    def on_branch_voltage_changed(self, byte_pos, value):
        """支路电压变化"""
        self.control_values['branch_voltages'][byte_pos] = value
        self.prepare_send_data()
        self.update_data_preview()
    
    def on_battery_temp_changed(self, value):
        """蓄电池温度变化"""
        self.control_values['battery_temp'] = value
        self.prepare_send_data()
        self.update_data_preview()
    
    def prepare_send_data(self):
        """准备发送数据 - 使用新的 FrameBuilder 实现以支持可扩展协议"""
        # 将 self.control_values 同步到模型层 ControlState
        cs = self._control_state_model
        cs.bool_commands = dict(self.control_values['bool_commands'])
        cs.freq_controls = dict(self.control_values['freq_controls'])
        cs.isolation_commands = dict(self.control_values['isolation_commands'])
        cs.start_commands = dict(self.control_values['start_commands'])
        cs.chu_controls = dict(self.control_values['chu_controls'])
        cs.redundant_commands = dict(self.control_values['redundant_commands'])
        cs.start_times = dict(self.control_values['start_times'])
        cs.branch_voltages = dict(self.control_values['branch_voltages'])
        cs.battery_temp = self.control_values['battery_temp']

        # 使用 FrameBuilder 构建基础帧
        frame = self._frame_builder.build()
        self.send_data_buffer = frame
        # 同步生命信号供旧 UI 使用
        self.ccu_life_signal = self._acu_device.state.life_signal

        # 原始数据编辑覆盖（仍保留旧功能）
        raw_text = self.raw_data_edit.toPlainText().strip()
        if raw_text:
            try:
                hex_data = bytes.fromhex(raw_text.replace(" ", ""))
                for i, byte in enumerate(hex_data):
                    if i < len(self.send_data_buffer):
                        self.send_data_buffer[i] = byte
            except ValueError:
                pass
    
    def update_data_preview(self):
        """更新数据预览 - 显示详细信息"""
        try:
            # 显示基本信息
            preview_text = f"""=== ACU发送数据预览 (完整协议) ===
数据长度: {len(self.send_data_buffer)} 字节
生命信号: {self.ccu_life_signal}
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

=== 控制状态解析 ===
基本控制 (字节8):
• 均衡充电模式(bit0): {'开启' if self.control_values['bool_commands'].get((8, 0), False) else '关闭'}
• 停止工作(bit1):     {'开启' if self.control_values['bool_commands'].get((8, 1), False) else '关闭'}
• 预发车测试(bit2):   {'开启' if self.control_values['bool_commands'].get((8, 2), False) else '关闭'}
• DCDC3隔离(bit6):   {'开启' if self.control_values['bool_commands'].get((8, 6), False) else '关闭'}
• DCDC4隔离(bit7):   {'开启' if self.control_values['bool_commands'].get((8, 7), False) else '关闭'}

设备控制 (字节9):
• 故障复位(bit0):    {'开启' if self.control_values['bool_commands'].get((9, 0), False) else '关闭'}
• 空压机1启动(bit1): {'开启' if self.control_values['bool_commands'].get((9, 1), False) else '关闭'}
• 空压机2启动(bit2): {'开启' if self.control_values['bool_commands'].get((9, 2), False) else '关闭'}
• 除尘风机KM61(bit3): {'开启' if self.control_values['bool_commands'].get((9, 3), False) else '关闭'}
• 热保障KM62(bit4):  {'开启' if self.control_values['bool_commands'].get((9, 4), False) else '关闭'}
• 热保障KM63(bit5):  {'开启' if self.control_values['bool_commands'].get((9, 5), False) else '关闭'}
• 电池水泵KM65(bit6): {'开启' if self.control_values['bool_commands'].get((9, 6), False) else '关闭'}
• 柴油机起动(bit7):  {'开启' if self.control_values['bool_commands'].get((9, 7), False) else '关闭'}

频率控制:
• INV2频率: {self.control_values['freq_controls'].get(10, 0)} Hz
• INV3频率: {self.control_values['freq_controls'].get(12, 0)} Hz
• INV4频率: {self.control_values['freq_controls'].get(14, 0)} Hz
• INV5频率: {self.control_values['freq_controls'].get(16, 0)} Hz

隔离指令 (字节64):
"""
            
            devices = ["INV1", "INV2", "INV3", "INV4", "INV5", "INV6", "BCC1", "BCC2"]
            for i, device in enumerate(devices):
                preview_text += f"• {device}: {'隔离' if self.control_values['isolation_commands'].get(i, False) else '正常'}\n"
            
            preview_text += "\n启动指令 (字节65):\n"
            for i, device in enumerate(devices):
                preview_text += f"• {device}: {'启动' if self.control_values['start_commands'].get(i, False) else '停止'}\n"
            
            preview_text += f"""

CHU控制 (字节66):
• CHU3启动: {'开启' if self.control_values['chu_controls'].get((66, 0), False) else '关闭'}
• CHU4启动: {'开启' if self.control_values['chu_controls'].get((66, 1), False) else '关闭'}
• CHU3隔离: {'开启' if self.control_values['chu_controls'].get((66, 2), False) else '关闭'}
• CHU4隔离: {'开启' if self.control_values['chu_controls'].get((66, 3), False) else '关闭'}

冗余启动 (字节67):
• INV1冗余启动: {'开启' if self.control_values['redundant_commands'].get((67, 0), False) else '关闭'}
• INV4冗余启动: {'开启' if self.control_values['redundant_commands'].get((67, 1), False) else '关闭'}

启动时间配置:
"""
            
            inv_devices = ["INV1", "INV2", "INV3", "INV4", "INV5", "INV6"]
            start_time_positions = [142, 144, 146, 148, 150, 152]
            for i, device in enumerate(inv_devices):
                preview_text += f"• {device}: {self.control_values['start_times'].get(start_time_positions[i], 0)} 秒\n"
            
            preview_text += f"""
电压和温度配置:
• 3支路电压: {self.control_values['branch_voltages'].get(154, 0)} V
• 4支路电压: {self.control_values['branch_voltages'].get(156, 0)} V
• 蓄电池温度: {self.control_values['battery_temp']} °C

=== 关键字节状态 ===
字节8 (基本控制):  {self.send_data_buffer[8]:08b} = {self.send_data_buffer[8]:02X}h
字节9 (设备控制):  {self.send_data_buffer[9]:08b} = {self.send_data_buffer[9]:02X}h  
字节64(隔离指令): {self.send_data_buffer[64]:08b} = {self.send_data_buffer[64]:02X}h
字节65(启动指令): {self.send_data_buffer[65]:08b} = {self.send_data_buffer[65]:02X}h
字节66(CHU控制):  {self.send_data_buffer[66]:08b} = {self.send_data_buffer[66]:02X}h
字节67(冗余启动): {self.send_data_buffer[67]:08b} = {self.send_data_buffer[67]:02X}h

=== 十六进制数据 (前100字节) ===
"""
            
            # 显示前100字节的十六进制数据
            display_length = min(100, len(self.send_data_buffer))
            hex_data = ''.join(f'{b:02X}' for b in self.send_data_buffer[:display_length])
            formatted_hex = ' '.join(hex_data[i:i+2] for i in range(0, len(hex_data), 2))
            
            # 分多行显示，每行16字节
            hex_lines = []
            for i in range(0, display_length, 16):
                line_hex = ' '.join(f'{self.send_data_buffer[j]:02X}' for j in range(i, min(i+16, display_length)))
                hex_lines.append(f"{i:04X}: {line_hex}")
            
            preview_text += '\n'.join(hex_lines)
            
            if len(self.send_data_buffer) > display_length:
                preview_text += f"\n... (剩余 {len(self.send_data_buffer) - display_length} 字节)"
            
            self.preview_text.setText(preview_text)
            
        except Exception as e:
            self.preview_text.setText(f"预览生成错误: {str(e)}")
    
    def start_communication(self):
        """开始通信"""
        try:
            # 确保后台解析/格式化线程处于运行状态（若曾停止）
            self._start_background_workers_if_needed()
            acu_ip = self.acu_ip_edit.text()
            acu_send_port = int(self.acu_send_port_edit.text())
            acu_receive_port = int(self.acu_receive_port_edit.text())
            target_ip = self.target_ip_edit.text()
            target_receive_port = int(self.target_receive_port_edit.text())
            # 更新配置并使用 CommunicationController 启动
            self.comm.update_config(acu_ip=acu_ip, acu_send_port=acu_send_port,
                                     acu_receive_port=acu_receive_port,
                                     target_ip=target_ip, target_receive_port=target_receive_port)

            if self.comm.setup():
                self.comm.start_receive_loop()

                period = self.period_spin.value()
                self.send_timer.start(period)
                self.is_sending = True

                self.start_btn.setEnabled(False)
                self.stop_btn.setEnabled(True)
                self.test_btn.setEnabled(False)
                self.preview_btn.setEnabled(True)

                # 通知视图开始记录
                self.view_bus.recording_toggle.emit(True)

                self.on_status_updated("通信已启动 - 数据收发中...")
                logger.info("通信启动成功")
            else:
                self._show_dialog('critical', "错误", "Socket初始化失败")
                logger.error("Socket初始化失败")
                
        except Exception as e:
            self._show_dialog('critical', "错误", f"启动通信失败: {str(e)}")
            logger.exception("启动通信失败")
    
    def stop_communication(self):
        """停止通信"""
        self.send_timer.stop()
        try:
            self.comm.stop()
        except Exception:
            pass
        self.is_sending = False

        # 停止后台解析/格式化线程，避免资源泄漏
        self._stop_background_workers()
        
        # 通知视图停止记录
        self.view_bus.recording_toggle.emit(False)
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.test_btn.setEnabled(True)
        self.preview_btn.setEnabled(True)
        
        self.on_status_updated("通信已停止")
        logger.info("通信已停止")
    
    def send_test_data(self):
        """发送测试数据"""
        self.prepare_send_data()
        data_to_send = bytes(self.send_data_buffer)
        try:
            self.comm.send(data_to_send)
            self.on_status_updated(f"测试数据发送成功，长度: {len(data_to_send)} 字节")
            logger.info(f"测试数据发送成功，长度: {len(data_to_send)} 字节")
            self.update_data_preview()
        except Exception:
            self.on_status_updated("测试数据发送失败")
            logger.warning("测试数据发送失败")
    
    def send_periodic_data(self):
        """周期性发送数据"""
        if self.is_sending:
            self.prepare_send_data()
            data_to_send = bytes(self.send_data_buffer)
            try:
                self.comm.send(data_to_send)
            except Exception:
                logger.warning("周期发送失败")
            
            # 添加时间戳用于调试
            current_time = time.time()
            logger.debug(f"[发送周期] 时间戳: {current_time:.3f}, 生命信号: {self.ccu_life_signal}")
            
            # 传递副本避免数据竞争，并确保是bytearray类型
            self.view_bus.waveform_send.emit(bytearray(self.send_data_buffer), current_time)
            
            # 更新生命信号显示
            self.life_signal_label.setText(f"生命信号: {self.ccu_life_signal}")
    
    def on_parse_result(self, parsed_record):
        """解析线程回传结果"""
        try:
            self.parsed_data_history.append(parsed_record)
            self.parse_table_buffer.append(parsed_record)
            device_type = parsed_record.get('device_type', 'UNKNOWN')
            parsed_data = parsed_record.get('parsed_data', {})
            self.last_parsed_for_display = (parsed_data, device_type)
        except Exception as e:
            logger.exception(f"on_parse_result 异常: {e}")
    
    def display_parsed_data(self, parsed_data, device_type):
        """显示解析数据"""
        self.parse_tree.clear()
        
        root_item = QTreeWidgetItem(self.parse_tree, [f"设备类型: {device_type}", "", ""])
        
        for category, items in parsed_data.items():
            category_item = QTreeWidgetItem(root_item, [category, "", ""])
            
            if isinstance(items, dict):
                for key, value in items.items():
                    if isinstance(value, list):
                        list_item = QTreeWidgetItem(category_item, [key, "", ""])
                        for item in value:
                            QTreeWidgetItem(list_item, [item, "", ""])
                    else:
                        unit = ""
                        if "频率" in key or "转速" in key:
                            unit = "Hz"
                        elif "电流" in key:
                            unit = "A"
                        elif "电压" in key:
                            unit = "V"
                        elif "温度" in key:
                            unit = "°C"
                        
                        value_str = str(value)
                        if isinstance(value, float):
                            value_str = f"{value:.2f}"
                        
                        QTreeWidgetItem(category_item, [key, value_str, unit])
            else:
                QTreeWidgetItem(category_item, [str(items), "", ""])
        
        self.parse_tree.expandAll()

    def flush_ui_buffers(self):
        """批量将解析缓冲刷新到 UI 表格"""
        try:
            # 刷新解析历史表格
            if self.parse_table_buffer:
                start_t = time.time()
                count = len(self.parse_table_buffer)
                MAX_PARSE_PER_FLUSH = 100
                self.parse_history_table.setUpdatesEnabled(False)
                processed_parse = 0
                while self.parse_table_buffer and processed_parse < MAX_PARSE_PER_FLUSH:
                    rec = self.parse_table_buffer.popleft()
                    if self.parse_history_table.rowCount() >= self.max_parse_records:
                        self.parse_history_table.removeRow(0)
                    row = self.parse_history_table.rowCount()
                    self.parse_history_table.insertRow(row)
                    self.parse_history_table.setItem(row, 0, QTableWidgetItem(rec.get('timestamp', '')))
                    self.parse_history_table.setItem(row, 1, QTableWidgetItem(rec.get('address', '')))
                    self.parse_history_table.setItem(row, 2, QTableWidgetItem(rec.get('device_type', '')))
                    self.parse_history_table.setItem(row, 3, QTableWidgetItem(str(rec.get('data_length', 0))))
                    self.parse_history_table.setItem(row, 4, QTableWidgetItem("解析成功"))
                    processed_parse += 1

                self.parse_history_table.scrollToBottom()
                self.parse_history_table.setUpdatesEnabled(True)
                elapsed = (time.time() - start_t) * 1000.0
                logger.debug(f"[perf] parse_table_buffer flushed: requested={count}, processed={processed_parse}, elapsed_ms={elapsed:.1f}")

            # 如果有最近解析结果需要显示，显示并清理
            if hasattr(self, 'last_parsed_for_display') and self.last_parsed_for_display:
                parsed_data, device_type = self.last_parsed_for_display
                self.display_parsed_data(parsed_data, device_type)
                self.last_parsed_for_display = None

        except Exception as e:
            self.on_status_updated(f"UI刷新错误: {e}")
    
    def _rebuild_tick(self):
        """分块填充表格的定时器回调"""
        pass  # 保留方法，但不再需要实现
    
    def on_parse_history_double_clicked(self, index):
        """解析历史表格双击事件"""
        row = index.row()
        if row < len(self.parsed_data_history):
            parse_info = self.parsed_data_history[row]
            self.display_parsed_data(parse_info['parsed_data'], parse_info['device_type'])
    
    def clear_parse_history(self):
        """清空解析历史"""
        self.parsed_data_history.clear()
        self.parse_history_table.setRowCount(0)
        self.parse_tree.clear()

    def save_config(self, *, show_message: bool = True):
        """保存当前网络/周期配置到 JSON 文件"""
        try:
            cfg = {
                'acu_ip': self.acu_ip_edit.text(),
                'acu_send_port': int(self.acu_send_port_edit.text()),
                'acu_receive_port': int(self.acu_receive_port_edit.text()),
                'target_ip': self.target_ip_edit.text(),
                'target_receive_port': int(self.target_receive_port_edit.text()),
                'period_ms': int(self.period_spin.value())
            }
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            logger.info(f"配置已保存到 {CONFIG_PATH}")
            if show_message:
                QMessageBox.information(self, "保存配置", "配置已保存")
        except Exception as e:
            logger.exception("保存配置失败")
            if show_message:
                QMessageBox.warning(self, "保存失败", f"保存配置时发生错误: {e}")

    def load_config(self):
        """从 JSON 加载配置并应用到 UI"""
        if not CONFIG_PATH.exists():
            logger.info("配置文件不存在，跳过加载")
            return
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)

            # 应用到 UI
            self.acu_ip_edit.setText(cfg.get('acu_ip', self.acu_ip_edit.text()))
            self.acu_send_port_edit.setText(str(cfg.get('acu_send_port', self.acu_send_port_edit.text())))
            self.acu_receive_port_edit.setText(str(cfg.get('acu_receive_port', self.acu_receive_port_edit.text())))
            self.target_ip_edit.setText(cfg.get('target_ip', self.target_ip_edit.text()))
            self.target_receive_port_edit.setText(str(cfg.get('target_receive_port', self.target_receive_port_edit.text())))
            self.period_spin.setValue(int(cfg.get('period_ms', self.period_spin.value())))

            # 更新 worker 配置
            try:
                # 更新新的通信控制器配置
                self.comm.update_config(acu_ip=self.acu_ip_edit.text(),
                                        acu_send_port=int(self.acu_send_port_edit.text()),
                                        acu_receive_port=int(self.acu_receive_port_edit.text()),
                                        target_ip=self.target_ip_edit.text(),
                                        target_receive_port=int(self.target_receive_port_edit.text()))
            except Exception:
                logger.warning("应用配置到 worker 时部分字段无效")

            self.on_status_updated("配置已加载")
            logger.info(f"从 {CONFIG_PATH} 加载配置成功")
        except Exception as e:
            logger.exception("加载配置失败")
            QMessageBox.warning(self, "加载失败", f"加载配置时发生错误: {e}")
    
    def on_error_occurred(self, error_msg):
        """处理错误"""
        self.status_label.setText(f"错误: {error_msg}")
        self.status_label.setStyleSheet("QLabel { background-color: #ffe0e0; padding: 8px; border: 1px solid #ff0000; }")
        logger.error(error_msg)
    
    def on_status_updated(self, status_msg):
        """更新状态"""
        self.status_label.setText(status_msg)
        logger.info(status_msg)
        if "错误" in status_msg:
            self.status_label.setStyleSheet("QLabel { background-color: #ffe0e0; padding: 8px; border: 1px solid #ff0000; }")
        elif "启动" in status_msg:
            self.status_label.setStyleSheet("QLabel { background-color: #e0f0ff; padding: 8px; border: 1px solid #0080ff; }")
        elif "停止" in status_msg:
            self.status_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 8px; border: 1px solid #cccccc; }")
        else:
            self.status_label.setStyleSheet("QLabel { background-color: #e0ffe0; padding: 8px; border: 1px solid #00cc00; }")
    
    def _show_dialog(self, level: str, title: str, text: str):
        """统一处理弹窗，便于在 headless 测试中禁用对话框。"""
        if not self._enable_dialogs:
            log_map = {
                'information': logger.info,
                'warning': logger.warning,
                'critical': logger.error,
            }
            log_func = log_map.get(level, logger.info)
            log_func(f"{title}: {text}")
            return
        func_map = {
            'information': QMessageBox.information,
            'warning': QMessageBox.warning,
            'critical': QMessageBox.critical,
        }
        func = func_map.get(level, QMessageBox.information)
        func(self, title, text)

    def check_memory_usage(self):
        """检查内存使用情况"""
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        
        current_time = time.time()
        if current_time - self.last_memory_check > 30:
            gc.collect()
            self.last_memory_check = current_time
        
        self.memory_status_label.setText(f"内存使用: {memory_mb:.1f} MB")
        
        if memory_mb > 500:
            self.memory_status_label.setStyleSheet("QLabel { background-color: #ffcccc; padding: 5px; border: 1px solid #ff0000; }")
        elif memory_mb > 300:
            self.memory_status_label.setStyleSheet("QLabel { background-color: #fff0cc; padding: 5px; border: 1px solid #ff9900; }")
        else:
            self.memory_status_label.setStyleSheet("QLabel { background-color: #f0ffe0; padding: 5px; border: 1px solid #00cc00; }")
    
    def closeEvent(self, event):
        """关闭事件：确保 stop() 总是执行并让 QMainWindow 完成默认收尾。"""
        try:
            self.save_config(show_message=False)
        except Exception:
            logger.warning("退出时保存配置失败")

        try:
            self.stop_communication()
        except Exception:
            logger.exception("关闭窗口时 stop_communication 失败")

        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
        logger.info("程序退出")
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用程序属性
    app.setApplicationName("ACU Simulator")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("Railway System")
    
    window = ACUSimulator()
    window.show()
    
    sys.exit(app.exec())