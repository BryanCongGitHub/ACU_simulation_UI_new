from __future__ import annotations

import copy
import queue
import time
from datetime import datetime
from collections import OrderedDict, defaultdict, deque
from typing import Any, Deque, Dict, List, Optional, Tuple
import logging

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QGridLayout,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QScrollArea,
    QMessageBox,
    QDockWidget,
    QPlainTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QListWidget,
    QStackedWidget,
    QCheckBox,
)
from PySide6.QtCore import (
    Slot,
    QObject,
    QThread,
    QTimer,
    QMetaObject,
    Signal,
    QSettings,
    QEvent,
    Qt,
)
from shiboken6 import isValid

# no GUI font customization required in this migration patch

from waveform_display import WaveformDisplay
from views.event_bus import ViewEventBus
from gui.settings_dialog import SettingsDialog
from gui.protocol_field_browser import ProtocolFieldBrowser

from infra.app_paths import get_app_base_dir, resource_path
from infra.settings_store import (
    DeviceConfigSettings,
    load_device_config,
    save_device_config,
)

from controllers.communication_controller import CommunicationController
from controllers.parse_controller import ParseController
from controllers.frame_builder import FrameBuilder
from controllers.protocol_field_service import (
    ProtocolFieldService,
    SendFieldInfo,
)
from model.control_state import ControlState
from model.device import Device, DeviceConfig

BASE_DIR = get_app_base_dir()
CONFIG_PATH = resource_path("acu_config.json", prefer_write=True)
logger = logging.getLogger("ACUSim")

ParseTask = Tuple[bytes, str, int, str]
RecordDict = Dict[str, Any]


class ParseWorker(QObject):
    parse_result = Signal(dict)

    def __init__(self, parse_controller, parse_queue, parent=None):
        super().__init__(parent)
        self.parse_controller = parse_controller
        self.parse_queue = parse_queue
        self._running = False
        self._timer = QTimer(self)
        self._timer.setInterval(50)

        # Wire up device config buttons
        try:
            if getattr(self, "device_apply_btn", None) is not None:
                self.device_apply_btn.clicked.connect(self._on_device_apply)
            if getattr(self, "device_save_btn", None) is not None:
                self.device_save_btn.clicked.connect(self.save_device_settings)
        except Exception:
            pass
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
        import queue as _queue

        loops = 0
        while self._running and loops < 64:
            try:
                item = self.parse_queue.get_nowait()
            except _queue.Empty:
                break

            timestamp = ""
            address = ""
            data = b""
            port = 0
            try:
                data, address, port, timestamp = item
                device_type = self.parse_controller.device_type_from_port(port)
                parsed = self.parse_controller.parse(data, port)
                parsed_record = {
                    "timestamp": timestamp,
                    "address": address,
                    "device_type": device_type,
                    "data_length": len(data),
                    "parsed_data": parsed,
                }
                self.parse_result.emit(parsed_record)
            except Exception as exc:
                error_record = {
                    "timestamp": timestamp,
                    "address": address,
                    "device_type": "ERROR",
                    "data_length": len(data),
                    "parsed_data": {"错误": str(exc)},
                }
                self.parse_result.emit(error_record)
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
        import queue as _queue

        loops = 0
        while self._running and loops < 128:
            try:
                item = self.format_queue.get_nowait()
            except _queue.Empty:
                break
            try:
                record = item
                data = record.get("data", b"") or b""
                try:
                    hex_str = " ".join(f"{byte:02X}" for byte in data)
                except Exception:
                    hex_str = ""
                record["hex"] = hex_str
                try:
                    self.formatted_queue.put(record)
                except Exception:
                    pass
            except Exception:
                continue
            loops += 1


class ACUSimulator(QMainWindow):
    def __init__(
        self,
        *,
        comm=None,
        parse_controller=None,
        control_state=None,
        acu_device=None,
        frame_builder=None,
        view_bus=None,
        enable_dialogs: bool = True,
    ):
        super().__init__()
        self._cleanup_done = False
        self._cleanup_in_progress = False
        self._log_handler = None
        try:
            self.destroyed.connect(self._on_destroyed)
        except Exception:
            pass
        self.comm = comm or CommunicationController()
        self._enable_dialogs = enable_dialogs
        self.worker_thread = None
        self.send_timer = QTimer()
        self.send_data_buffer = bytearray(320)

        self.parse_queue: queue.Queue[ParseTask] = queue.Queue()
        self.parse_controller = parse_controller or ParseController()
        self.parse_worker = None
        self.parse_worker_thread = None

        self.format_queue: queue.Queue[RecordDict] = queue.Queue()
        self.formatted_queue: queue.Queue[RecordDict] = queue.Queue()
        self.format_worker = None
        self.format_worker_thread = None

        self.max_parse_records = 5000
        self.parsed_data_history: Deque[RecordDict] = deque(
            maxlen=self.max_parse_records
        )

        self.parse_table_buffer: Deque[RecordDict] = deque()
        self.ui_update_timer = QTimer()
        self.ui_update_interval = 200
        self.ui_update_timer.setInterval(self.ui_update_interval)
        self.ui_update_timer.timeout.connect(self._drain_parse_table)

        # Receive tree incremental update
        self.recv_tree_buffer: Deque[RecordDict] = deque()
        self.recv_tree_timer = QTimer()
        self.recv_tree_timer.setInterval(120)
        self.recv_tree_timer.timeout.connect(self._drain_recv_tree)
        self._recv_tree_categories: Dict[str, Any] = {}
        self._recv_tree_keys: Dict[str, Dict[str, Any]] = {}

        self._rebuild_timer = QTimer()
        self._rebuild_timer.setInterval(20)
        self._rebuild_timer.timeout.connect(self._rebuild_tick)
        self._rebuild_in_progress = False
        self._rebuild_entries: List[RecordDict] = []
        self._rebuild_index = 0
        self._rebuild_chunk_size = 50

        self.ccu_life_signal = 0
        self.is_sending = False

        self.control_values = {
            "bool_commands": {},
            "freq_controls": {},
            "isolation_commands": {},
            "start_commands": {},
            "chu_controls": {},
            "redundant_commands": {},
            "start_times": {},
            "branch_voltages": {},
            "battery_temp": 25,
        }

        cs = control_state or ControlState()
        dev = acu_device or Device(
            DeviceConfig(
                name="ACU",
                ip="10.2.0.1",
                send_port=49152,
                receive_port=49156,
                category="ACU",
            )
        )
        self._frame_builder = frame_builder or FrameBuilder(cs, dev)
        self._control_state_model = getattr(self._frame_builder, "control_state", cs)
        self._acu_device = getattr(self._frame_builder, "acu_device", dev)

        # Protocol field metadata & preferences
        self._protocol_field_service = ProtocolFieldService()
        self._protocol_field_prefs = (
            self._protocol_field_service.get_active_preferences()
        )
        self._send_field_infos = self._protocol_field_service.send_field_infos()
        self._receive_field_infos = self._protocol_field_service.receive_field_infos()
        self._send_field_widgets: Dict[str, QWidget] = {}
        self._receive_selection_cache: Dict[str, set[str]] = {}
        self._common_receive_selection: set[str] = set()
        self._update_receive_selection_cache()

        self.memory_check_timer = QTimer()
        self.memory_check_interval = 10000
        self.last_memory_check = time.time()

        self.view_bus = view_bus or ViewEventBus()
        self.waveform_display = WaveformDisplay(
            event_bus=self.view_bus,
            field_service=self._protocol_field_service,
            field_preferences=self._protocol_field_prefs,
        )

        self.init_ui()
        self.init_data()
        self.setup_connections()
        self.setup_memory_management()
        self._setup_workers()

    def _rebuild_tick(self):
        """分块填充表格的定时器回调

        在 UI 线程中分块将大量解析记录加入到 `parse_table_buffer`，以
        避免一次性填充阻塞 UI。保持实现轻量以满足测试依赖。
        """
        if not getattr(self, "_rebuild_in_progress", False):
            return

        try:
            processed = 0
            total = len(self._rebuild_entries)
            while self._rebuild_index < total and processed < self._rebuild_chunk_size:
                entry = self._rebuild_entries[self._rebuild_index]
                try:
                    self.parse_table_buffer.append(entry)
                except Exception:
                    pass
                self._rebuild_index += 1
                processed += 1

            if self._rebuild_index >= total:
                self._rebuild_in_progress = False
                self._rebuild_entries = []
                self._rebuild_index = 0
                try:
                    self._rebuild_timer.stop()
                except Exception:
                    pass

        except Exception:
            self._rebuild_in_progress = False
            self._rebuild_entries = []
            self._rebuild_index = 0
            try:
                self._rebuild_timer.stop()
            except Exception:
                pass

    def init_ui(self):
        """Initialize a minimal UI required by tests.

        This creates a small set of widgets referenced by the logic (spinbox,
        control buttons and a status label). The full visual layout is not
        necessary for tests — only the attributes and basic signal wiring.
        """
        central = QWidget(self)
        layout = QVBoxLayout(central)

        # Central area: waveform on the right side of a splitter
        splitter = QSplitter(Qt.Horizontal)

        # Device configuration (left panel top)
        device_group = QGroupBox("Device Config")
        device_group.setObjectName("device_group")
        self.device_group = device_group
        device_form = QFormLayout(device_group)

        self.acu_ip_edit = QLineEdit("10.2.0.1")
        self.acu_send_port_edit = QLineEdit("49152")
        self.acu_receive_port_edit = QLineEdit("49156")
        self.target_ip_edit = QLineEdit("10.2.0.5")
        self.target_receive_port_edit = QLineEdit("49152")

        # Device preset/type selector (自动填充 IP/端口)
        try:
            self.device_type_combo = QComboBox()
            self.device_type_combo.setObjectName("device_type_combo")
        except Exception:
            self.device_type_combo = None

        # Insert device type combo above the other fields if available
        try:
            if getattr(self, "device_type_combo", None) is not None:
                device_form.addRow(QLabel("设备类型"), self.device_type_combo)
        except Exception:
            pass

        device_form.addRow(QLabel("ACU IP"), self.acu_ip_edit)
        device_form.addRow(QLabel("ACU Send Port"), self.acu_send_port_edit)
        device_form.addRow(QLabel("ACU Receive Port"), self.acu_receive_port_edit)
        device_form.addRow(QLabel("Target IP"), self.target_ip_edit)
        device_form.addRow(QLabel("Target Receive Port"), self.target_receive_port_edit)

        # Apply / Save buttons for device config
        btns = QWidget()
        btns_layout = QHBoxLayout(btns)
        btns_layout.setContentsMargins(0, 0, 0, 0)
        self.device_apply_btn = QPushButton("Apply")
        self.device_save_btn = QPushButton("Save")
        self.device_restore_btn = QPushButton("Restore Defaults")
        btns_layout.addWidget(self.device_apply_btn)
        btns_layout.addWidget(self.device_save_btn)
        btns_layout.addWidget(self.device_restore_btn)
        device_form.addRow(btns)

        # Wire up device preset combo and manual edits
        try:
            if getattr(self, "device_type_combo", None) is not None:
                presets = self._load_device_presets()
                # keep an ordered list: presets keys then 自定义
                names = list(presets.keys())
                names.append("自定义")
                self.device_type_combo.addItems(names)
                self.device_type_combo.currentTextChanged.connect(
                    lambda txt: self._on_device_preset_changed(txt, presets)
                )
                # when user edits IP/port manually, switch to 自定义
                try:
                    self.acu_ip_edit.textChanged.connect(
                        self._on_manual_device_field_changed
                    )
                    self.acu_send_port_edit.textChanged.connect(
                        self._on_manual_device_field_changed
                    )
                    self.acu_receive_port_edit.textChanged.connect(
                        self._on_manual_device_field_changed
                    )
                    self.target_ip_edit.textChanged.connect(
                        self._on_manual_device_field_changed
                    )
                    self.target_receive_port_edit.textChanged.connect(
                        self._on_manual_device_field_changed
                    )
                except Exception:
                    pass
        except Exception:
            pass

        # Controls (left panel actions)
        controls = QWidget()
        c_layout = QHBoxLayout(controls)
        self.period_spin = QSpinBox()
        self.period_spin.setRange(1, 10000)
        self.period_spin.setValue(100)

        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.test_btn = QPushButton("Test")
        self.preview_btn = QPushButton("Preview")

        c_layout.addWidget(self.period_spin)
        c_layout.addWidget(self.start_btn)
        c_layout.addWidget(self.stop_btn)
        c_layout.addWidget(self.test_btn)
        c_layout.addWidget(self.preview_btn)

        # Left panel: device config + controls + status label stacked vertically
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        # Device config sits above the action controls
        try:
            left_layout.addWidget(device_group)
        except Exception:
            # Some test environments may not render group boxes; fall back
            left_layout.addWidget(controls)
        left_layout.addWidget(controls)

        # Status (still part of left panel)
        self.status_label = QLabel("Ready")
        left_layout.addWidget(self.status_label)

        # Do not add the legacy left_panel to the central splitter; its
        # content moves into the sidebar dock pages.

        # Central waveform only; left panel will be moved into sidebar dock
        if getattr(self, "waveform_display", None) is not None:
            splitter.addWidget(self.waveform_display)
            try:
                self.waveform_display.setMinimumWidth(220)
            except Exception:
                pass

        # Wire up control buttons to actions
        try:
            self.start_btn.clicked.connect(self.start_communication)
            self.stop_btn.clicked.connect(self.stop_communication)
            self.test_btn.clicked.connect(self.run_test_once)
            self.preview_btn.clicked.connect(self.preview_once)
            # device config buttons
            try:
                self.device_apply_btn.clicked.connect(self._on_device_apply)
                self.device_save_btn.clicked.connect(self.save_device_settings)
                self.device_restore_btn.clicked.connect(self.restore_device_defaults)
            except Exception:
                pass
        except Exception:
            pass

        splitter.setSizes([350, 650])
        layout.addWidget(splitter)

        # Menu bar (basic File/Help) - part of migration from original UI
        try:
            menubar = self.menuBar()
            file_menu = menubar.addMenu("&File")
            exit_action = file_menu.addAction("E&xit")
            exit_action.triggered.connect(self.close)

            settings_menu = menubar.addMenu("&Settings")
            reset_action = settings_menu.addAction("Settings...")
            reset_action.triggered.connect(self._open_settings_dialog)

            # Palette import/export (also expose under Settings menu)
            try:
                import_palette_action = settings_menu.addAction("Import Palette...")
                import_palette_action.triggered.connect(
                    lambda: self.waveform_display._on_import_palette()
                )
                export_palette_action = settings_menu.addAction("Export Palette...")
                export_palette_action.triggered.connect(
                    lambda: self.waveform_display._on_export_palette()
                )
            except Exception:
                pass

            help_menu = menubar.addMenu("&Help")
            about_action = help_menu.addAction("&About")
            about_action.triggered.connect(
                lambda: QMessageBox.information(self, "About", "ACU Simulator")
            )
        except Exception:
            # Some test environments may not have a full QApplication; ignore
            pass

        self.setCentralWidget(central)

        # Initialize sidebar dock (left) and other docks (parse table)
        try:
            self._init_sidebar_dock(left_panel)
            self._init_docks()
        except Exception:
            pass
        # Load any saved device settings (non-blocking, safe for tests)
        try:
            self.load_device_settings()
        except Exception:
            pass

        # Restore dock/geometry state
        try:
            self._restore_mainwindow_state()
        except Exception:
            pass
        # Apply header visibility settings once parse_table exists
        try:
            self._load_header_visibility_settings()
            self._apply_header_visibility_settings_to_table()
        except Exception:
            pass

    def _open_settings_dialog(self):
        try:
            dlg = SettingsDialog(self)
            res = dlg.exec()
            # after dialog closes, reload settings so UI reflects cleared state
            try:
                self.waveform_display.load_settings()
            except Exception:
                pass
            try:
                self.load_device_settings()
            except Exception:
                pass
            return res
        except Exception:
            return None

    def init_data(self):
        """Initialize lightweight data structures used by the UI logic."""
        # Ensure send buffer exists
        if not hasattr(self, "send_data_buffer"):
            self.send_data_buffer = bytearray(320)

    def _show_error(self, message: str, title: str = "错误"):
        """Show an error message to the user if dialogs are enabled.

        This is guarded by `self._enable_dialogs` so tests/CI can run
        without blocking on modal dialogs.
        """
        try:
            logger.error(message)
            if getattr(self, "_enable_dialogs", True):
                try:
                    QMessageBox.critical(self, title, message)
                except Exception:
                    # In some headless/test environments QMessageBox may fail;
                    # swallow and rely on logging.
                    pass
        except Exception:
            pass

    def setup_connections(self):
        """Wire up internal signals and communication callbacks."""
        # Timer for periodic send
        try:
            self.send_timer.timeout.connect(self.send_periodic_data)
        except Exception:
            pass

        # Communication controller callbacks
        try:
            self.comm.on_receive = lambda data, addr: self.on_data_received_comm(
                data, addr
            )
            self.comm.on_error = lambda msg: self.on_status_updated(str(msg))
            self.comm.on_status = lambda msg: self.on_status_updated(str(msg))
        except Exception:
            pass

    def load_device_settings(self):
        """Load persisted device configuration into the sidebar fields."""
        try:
            defaults = DeviceConfigSettings(
                acu_ip=str(self.acu_ip_edit.text()),
                acu_send_port=str(self.acu_send_port_edit.text()),
                acu_receive_port=str(self.acu_receive_port_edit.text()),
                target_ip=str(self.target_ip_edit.text()),
                target_receive_port=str(self.target_receive_port_edit.text()),
            )
            config = load_device_config(defaults)

            try:
                self.acu_ip_edit.setText(str(config.acu_ip))
            except Exception:
                pass
            try:
                self.acu_send_port_edit.setText(str(config.acu_send_port))
            except Exception:
                pass
            try:
                self.acu_receive_port_edit.setText(str(config.acu_receive_port))
            except Exception:
                pass
            try:
                self.target_ip_edit.setText(str(config.target_ip))
            except Exception:
                pass
            try:
                self.target_receive_port_edit.setText(str(config.target_receive_port))
            except Exception:
                pass
            # apply device preset selection if available
            try:
                if getattr(self, "device_type_combo", None) is not None:
                    preset_name = getattr(config, "device_preset", "") or ""
                    if preset_name and preset_name in [
                        self.device_type_combo.itemText(i)
                        for i in range(self.device_type_combo.count())
                    ]:
                        self.device_type_combo.setCurrentText(preset_name)
                    else:
                        # default to 自定义
                        try:
                            self.device_type_combo.setCurrentText("自定义")
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception:
            pass

    def save_device_settings(self):
        """Persist current device sidebar fields via the centralized store."""
        try:
            # determine selected preset name if any
            preset = ""
            try:
                if getattr(self, "device_type_combo", None) is not None:
                    cur = str(self.device_type_combo.currentText() or "")
                    if cur and cur != "自定义":
                        preset = cur
            except Exception:
                preset = ""

            data = DeviceConfigSettings(
                acu_ip=str(self.acu_ip_edit.text()),
                acu_send_port=str(self.acu_send_port_edit.text()),
                acu_receive_port=str(self.acu_receive_port_edit.text()),
                target_ip=str(self.target_ip_edit.text()),
                target_receive_port=str(self.target_receive_port_edit.text()),
                device_preset=preset,
            )
            save_device_config(data)
            try:
                self._show_info("设备配置已保存。", "信息")
            except Exception:
                pass
        except Exception:
            pass

    def _on_device_apply(self):
        """Apply device config values to the communication controller."""
        try:
            acu_ip = self.acu_ip_edit.text()
            target_ip = self.target_ip_edit.text()

            # validate ports
            def _parse_port(text):
                try:
                    v = int(text)
                except Exception:
                    return None
                if 1 <= v <= 65535:
                    return v
                return None

            acu_send_port = _parse_port(self.acu_send_port_edit.text())
            acu_receive_port = _parse_port(self.acu_receive_port_edit.text())
            target_receive_port = _parse_port(self.target_receive_port_edit.text())

            invalid = []
            if acu_send_port is None:
                invalid.append("ACU Send Port")
            if acu_receive_port is None:
                invalid.append("ACU Receive Port")
            if target_receive_port is None:
                invalid.append("Target Receive Port")

            if invalid:
                # Inform user about invalid fields and abort apply
                self._show_error(
                    f"端口无效或超出范围: {', '.join(invalid)} (应为 1-65535)",
                    title="配置错误",
                )
                return False

            # Update comm config (validated)
            try:
                self.comm.update_config(
                    acu_ip=acu_ip,
                    acu_send_port=acu_send_port,
                    acu_receive_port=acu_receive_port,
                    target_ip=target_ip,
                    target_receive_port=target_receive_port,
                )
                self._show_info("设备配置已应用。", "信息")
                return True
            except Exception as exc:
                logger.exception("Applying device config failed")
                self._show_error(f"应用设备配置失败: {exc}")
                return False
        except Exception as exc:
            logger.exception("_on_device_apply unexpected error")
            self._show_error(f"应用失败: {exc}")
            return False

    # ---- Device preset helpers ----
    def _load_device_presets(self) -> dict:
        """Load presets from `infra/device_presets.json` next to the codebase.

        Returns a mapping name->config dict. Best-effort; on error returns {}.
        """
        try:
            import json

            path = resource_path("infra", "device_presets.json", must_exist=True)
            if not path.exists():
                return {}
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except Exception:
            logger.exception("加载 device_presets.json 失败")
        return {}

    def _on_device_preset_changed(self, text: str, presets: dict) -> None:
        """Apply preset values into the device fields when a preset is selected.

        Selecting "自定义" leaves fields as-is.
        """
        try:
            if not text or text == "自定义":
                return
            preset = presets.get(text)
            if not isinstance(preset, dict):
                return
            # apply values if present; set a short-lived flag so the
            # manual-edit handler does not interpret these programmatic
            # updates as user edits (which would switch the combo to 自定义).
            try:
                self._applying_preset = True
                if "acu_ip" in preset:
                    self.acu_ip_edit.setText(str(preset.get("acu_ip", "")))
                if "acu_send_port" in preset:
                    self.acu_send_port_edit.setText(
                        str(preset.get("acu_send_port", ""))
                    )
                if "acu_receive_port" in preset:
                    self.acu_receive_port_edit.setText(
                        str(preset.get("acu_receive_port", ""))
                    )
                if "target_ip" in preset:
                    self.target_ip_edit.setText(str(preset.get("target_ip", "")))
                if "target_receive_port" in preset:
                    self.target_receive_port_edit.setText(
                        str(preset.get("target_receive_port", ""))
                    )
            finally:
                try:
                    # small defensive cleanup
                    self._applying_preset = False
                except Exception:
                    pass
        except Exception:
            pass

    def _on_manual_device_field_changed(self, *args, **kwargs):
        """Switch device_type combo to '自定义' when user edits fields manually."""
        try:
            # if we are programmatically applying a preset, ignore these
            if getattr(self, "_applying_preset", False):
                return
            if getattr(self, "device_type_combo", None) is None:
                return
            cur = str(self.device_type_combo.currentText() or "")
            if cur != "自定义":
                # set current to 自定义 without emitting change handling
                try:
                    self.device_type_combo.blockSignals(True)
                    self.device_type_combo.setCurrentText("自定义")
                finally:
                    self.device_type_combo.blockSignals(False)
        except Exception:
            pass

    def restore_device_defaults(self):
        """Restore device UI fields to defaults from device model and comm config."""
        try:
            # Use device config for ACU-specific defaults
            try:
                dev = getattr(self, "_acu_device", None)
                if dev and getattr(dev, "config", None):
                    cfg = dev.config
                    try:
                        self.acu_ip_edit.setText(str(cfg.ip))
                    except Exception:
                        pass
                    try:
                        self.acu_send_port_edit.setText(str(cfg.send_port))
                    except Exception:
                        pass
                    try:
                        if cfg.receive_port is not None:
                            self.acu_receive_port_edit.setText(str(cfg.receive_port))
                    except Exception:
                        pass
            except Exception:
                pass

            # Use comm defaults for target
            try:
                comm_cfg = getattr(self, "comm", None).config
                try:
                    self.target_ip_edit.setText(str(comm_cfg.get("target_ip", "")))
                except Exception:
                    pass
                try:
                    self.target_receive_port_edit.setText(
                        str(comm_cfg.get("target_receive_port", ""))
                    )
                except Exception:
                    pass
            except Exception:
                pass

            try:
                self._show_info("已恢复设备配置到默认值。", "信息")
            except Exception:
                pass
        except Exception:
            pass

    def setup_memory_management(self):
        """Start any lightweight timers for memory checks (no-op if not needed)."""
        try:
            self.memory_check_timer.timeout.connect(self.check_memory_usage)
        except Exception:
            pass

    # ---- Sidebar dock ----
    def _init_sidebar_dock(self, legacy_left_panel: QWidget):
        """Create left sidebar dock with navigation + stacked pages.

        Pages: 设备设置 / 发送配置 / 接收数据 / 解析表头 / 日志
        """
        sidebar_container = QWidget()
        container_layout = QHBoxLayout(sidebar_container)
        container_layout.setContentsMargins(4, 4, 4, 4)
        container_layout.setSpacing(6)

        if legacy_left_panel is not None:
            legacy_left_panel.setParent(None)
            device_page = QWidget()
            device_layout = QVBoxLayout(device_page)
            device_layout.setContentsMargins(0, 0, 0, 0)
            device_layout.addWidget(legacy_left_panel)
        else:
            device_page = QWidget()

        self.sidebar_nav = QListWidget()
        self.sidebar_nav.addItems(
            ["设备设置", "发送配置", "协议字段", "接收数据", "解析表头", "日志"]
        )
        self.sidebar_nav.setMinimumWidth(70)
        self.sidebar_nav.setMaximumWidth(140)
        container_layout.addWidget(self.sidebar_nav)

        self.sidebar_pages = QStackedWidget()
        container_layout.addWidget(self.sidebar_pages, 1)
        # Page 2: 发送配置（配置发送数据内容）
        sendcfg_page = QWidget()
        sendcfg_layout = QVBoxLayout(sendcfg_page)
        sendcfg_layout.setSpacing(8)

        self._sendcfg_dynamic_container = QWidget()
        dynamic_layout = QVBoxLayout(self._sendcfg_dynamic_container)
        dynamic_layout.setContentsMargins(0, 0, 0, 0)
        dynamic_layout.setSpacing(8)
        sendcfg_layout.addWidget(self._sendcfg_dynamic_container)
        self._build_send_config_groups()
        # 操作区
        sc_actions = QWidget()
        sc_actions.setLayout(QHBoxLayout())
        self.sc_apply_btn = QPushButton("应用到发送状态")
        self.sc_preview_btn = QPushButton("生成预览")
        sc_actions.layout().addWidget(self.sc_apply_btn)
        sc_actions.layout().addWidget(self.sc_preview_btn)
        sendcfg_layout.addWidget(sc_actions)
        # 预览区域
        self.sc_preview_edit = QPlainTextEdit()
        self.sc_preview_edit.setReadOnly(True)
        self.sc_preview_edit.setPlaceholderText("发送帧HEX预览")
        sendcfg_layout.addWidget(self.sc_preview_edit)
        # 连接
        self.sc_apply_btn.clicked.connect(self._apply_send_config)
        self.sc_preview_btn.clicked.connect(self._preview_send_frame)

        # Page 3: 接收数据（树）
        recv_page = QWidget()
        recv_layout = QVBoxLayout(recv_page)
        self.recv_tree = QTreeWidget()
        self.recv_tree.setHeaderLabels(["类别/键", "值"])
        self.recv_tree.setColumnCount(2)
        recv_layout.addWidget(self.recv_tree)

        # Page 4: 解析表头
        header_page = QWidget()
        header_layout = QVBoxLayout(header_page)
        header_hint = QLabel(
            '解析表位于窗口下方的 "解析表" Dock，若未显示，可在菜单中启用。'
        )
        header_hint.setWordWrap(True)
        header_layout.addWidget(header_hint)
        self.chk_col_timestamp = QCheckBox("显示 timestamp")
        self.chk_col_address = QCheckBox("显示 address")
        self.chk_col_device = QCheckBox("显示 device_type")
        self.chk_col_length = QCheckBox("显示 data_length")
        self.chk_col_parsed = QCheckBox("显示 parsed_data")
        for chk in [
            self.chk_col_timestamp,
            self.chk_col_address,
            self.chk_col_device,
            self.chk_col_length,
            self.chk_col_parsed,
        ]:
            chk.setChecked(True)
            header_layout.addWidget(chk)

        def _apply_header_visibility():
            self._save_header_visibility_settings()
            self._apply_header_visibility_settings_to_table()

        for chk in [
            self.chk_col_timestamp,
            self.chk_col_address,
            self.chk_col_device,
            self.chk_col_length,
            self.chk_col_parsed,
        ]:
            chk.toggled.connect(_apply_header_visibility)

        self.parse_table_group = QGroupBox("解析记录")
        self.parse_table_group_layout = QVBoxLayout(self.parse_table_group)
        self.parse_table_group_layout.setContentsMargins(0, 8, 0, 0)
        self.parse_table_group_placeholder = QLabel(
            "解析结果将在此显示。启动通信后可查看最新数据。"
        )
        self.parse_table_group_placeholder.setWordWrap(True)
        self.parse_table_group_layout.addWidget(self.parse_table_group_placeholder)
        header_layout.addWidget(self.parse_table_group)
        header_layout.addStretch(1)

        # Page 5: 日志
        log_page = QWidget()
        log_layout = QVBoxLayout(log_page)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        log_layout.addWidget(self.log_view)
        try:
            self._attach_log_handler()
        except Exception:
            pass

        # Assemble pages
        self.sidebar_pages.addWidget(self._wrap_sidebar_page(device_page))
        self.sidebar_pages.addWidget(self._wrap_sidebar_page(sendcfg_page))
        self.protocol_field_browser = ProtocolFieldBrowser(
            self, field_service=self._protocol_field_service
        )
        try:
            self.protocol_field_browser.preferences_changed.connect(
                self._on_protocol_field_preferences_changed
            )
        except Exception:
            pass
        self.sidebar_pages.addWidget(
            self._wrap_sidebar_page(self.protocol_field_browser)
        )
        self.sidebar_pages.addWidget(self._wrap_sidebar_page(recv_page))
        self.sidebar_pages.addWidget(self._wrap_sidebar_page(header_page))
        self.sidebar_pages.addWidget(self._wrap_sidebar_page(log_page))
        self.sidebar_nav.currentRowChanged.connect(self.sidebar_pages.setCurrentIndex)
        self.sidebar_nav.setCurrentRow(0)

        # Create dock and install container
        sidebar_dock = QDockWidget("侧边栏", self)
        sidebar_dock.setObjectName("dock_sidebar")
        sidebar_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        sidebar_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetVerticalTitleBar
        )
        sidebar_dock.setWidget(sidebar_container)
        self.addDockWidget(Qt.LeftDockWidgetArea, sidebar_dock)
        # 分配停靠区域优先级，让侧边栏占据左侧并保留调整手柄
        try:
            self.setDockNestingEnabled(True)
            self.resizeDocks([sidebar_dock], [280], Qt.Horizontal)
            self.setCorner(Qt.TopLeftCorner, Qt.LeftDockWidgetArea)
            self.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        except Exception:
            pass

        # default indicator state (ensure consistent color)
        self._set_comm_status_indicator("#999", "通信未启动")

    def _wrap_sidebar_page(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(widget)
        return scroll

    # ---- Protocol field helpers ----
    def _build_send_config_groups(self) -> None:
        container_layout = self._sendcfg_dynamic_container.layout()
        if container_layout is None:
            return

        self._clear_layout(container_layout)
        self._send_field_widgets.clear()

        grouped = self._group_selected_send_fields()
        if not grouped:
            placeholder = QLabel("未选择发送字段，请在‘协议字段’页中勾选并保存。")
            placeholder.setWordWrap(True)
            container_layout.addWidget(placeholder)
            return

        for group_title, infos in grouped.items():
            widget: Optional[QWidget] = None
            if infos and all(
                info.kind in {"bool_bitset", "packed_bit"} for info in infos
            ):
                widget = self._create_bool_group(group_title, infos)
            else:
                widget = self._create_word_group(group_title, infos)
            if widget is not None:
                container_layout.addWidget(widget)

    def _group_selected_send_fields(self) -> "OrderedDict[str, List[SendFieldInfo]]":
        selected = self._protocol_field_prefs.get("send", []) or []
        grouped: "OrderedDict[str, List[SendFieldInfo]]" = OrderedDict()
        for key in selected:
            info = self._send_field_infos.get(key)
            if info is None:
                continue
            grouped.setdefault(info.group_title, []).append(info)
        for infos in grouped.values():
            infos.sort(key=lambda item: item.order)
        return grouped

    def _create_bool_group(
        self, title: str, infos: List[SendFieldInfo]
    ) -> Optional[QGroupBox]:
        if not infos:
            return None
        group = QGroupBox(title)
        layout = QGridLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(6)
        columns = 3
        for idx, info in enumerate(infos):
            chk = QCheckBox(info.label or info.key)
            chk.setChecked(self._is_send_field_checked(info))
            layout.addWidget(chk, idx // columns, idx % columns)
            self._send_field_widgets[info.key] = chk
        group.setLayout(layout)
        return group

    def _create_word_group(
        self, title: str, infos: List[SendFieldInfo]
    ) -> Optional[QGroupBox]:
        if not infos:
            return None
        group = QGroupBox(title)
        form = QFormLayout()
        form.setContentsMargins(8, 8, 8, 8)
        for info in infos:
            widget = self._create_word_widget(info)
            label = info.label or info.key
            form.addRow(label, widget)
            self._send_field_widgets[info.key] = widget
        group.setLayout(form)
        return group

    def _create_word_widget(self, info: SendFieldInfo) -> QWidget:
        value = self._get_send_field_value(info)
        source = info.source

        if source == "battery_temp":
            spin = QSpinBox()
            spin.setRange(-40, 125)
            spin.setSingleStep(1)
            spin.setValue(int(value))
            return spin

        if source == "start_times":
            spin = QSpinBox()
            spin.setRange(0, 600)
            spin.setSingleStep(1)
            spin.setValue(int(value))
            return spin

        decimals = 1 if abs(info.scale or 0.0) < 1 else 0
        spin = QDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setSingleStep(info.scale or 0.5)
        if source == "freq_controls":
            spin.setRange(0.0, 4000.0)
            spin.setSingleStep(0.1)
        elif source == "branch_voltages":
            spin.setRange(0.0, 800.0)
            spin.setSingleStep(0.5)
        else:
            spin.setRange(0.0, 10000.0)
        spin.setValue(float(value))
        if info.unit:
            spin.setSuffix(f" {info.unit}")
        return spin

    def _clear_layout(self, layout) -> None:
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)

    def _is_send_field_checked(self, info: SendFieldInfo) -> bool:
        cs = getattr(self, "_control_state_model", None)
        if cs is None:
            return False
        target = getattr(cs, info.source, None)
        if info.kind == "bool_bitset" and isinstance(target, dict):
            if info.byte is None or info.bit is None:
                return False
            return bool(target.get((info.byte, info.bit)))
        if info.kind == "packed_bit" and isinstance(target, dict):
            if info.bit is None:
                return False
            return bool(target.get(info.bit))
        return False

    def _get_send_field_value(self, info: SendFieldInfo) -> float:
        cs = getattr(self, "_control_state_model", None)
        if cs is None:
            return 0.0
        if info.kind == "scalar_word":
            return float(getattr(cs, info.source, 0))
        target = getattr(cs, info.source, None)
        if isinstance(target, dict) and info.offset is not None:
            return float(target.get(info.offset, 0))
        return 0.0

    def _update_receive_selection_cache(self) -> None:
        receive = self._protocol_field_prefs.get("receive", {}) or {}
        self._common_receive_selection = set(receive.get("common", []))
        self._receive_selection_cache = {
            category: set(keys)
            for category, keys in receive.items()
            if category != "common"
        }

    def _on_protocol_field_preferences_changed(self, prefs: Dict[str, object]) -> None:
        try:
            self._protocol_field_prefs = copy.deepcopy(prefs)
        except Exception:
            self._protocol_field_prefs = prefs or {}
        # refresh caches to reflect template or selection changes
        self._send_field_infos = self._protocol_field_service.send_field_infos()
        self._receive_field_infos = self._protocol_field_service.receive_field_infos()
        self._update_receive_selection_cache()
        self._build_send_config_groups()
        self._reset_recv_tree_view()
        try:
            self.waveform_display.apply_field_preferences(
                self._protocol_field_service, self._protocol_field_prefs
            )
        except Exception:
            logger.exception("Failed to refresh waveform signal preferences")

    def _reset_recv_tree_view(self) -> None:
        tree = getattr(self, "recv_tree", None)
        if tree is not None:
            try:
                tree.clear()
            except Exception:
                pass
        self._recv_tree_categories = {}
        self._recv_tree_keys = {}

    def _filter_parsed_record(self, record: RecordDict) -> Dict[str, Any]:
        parsed = record.get("parsed_data", {}) or {}
        device_type = str(record.get("device_type", ""))
        try:
            category = self.parse_controller.category_from_device(device_type)
        except Exception:
            category = ""
        if not category:
            category = "generic"
        return self._filter_parsed_data(parsed, category)

    def _filter_parsed_data(
        self, parsed: Dict[str, Any], category: str
    ) -> Dict[str, Any]:
        filtered: Dict[str, Any] = {}
        category_selected = self._receive_selection_cache.get(category)
        common_selected = self._common_receive_selection

        for section_name, value in parsed.items():
            if isinstance(value, dict):
                selection_category = (
                    "common" if section_name == "设备信息" else category
                )
                selected_keys = (
                    common_selected
                    if selection_category == "common"
                    else category_selected
                )
                section_result: Dict[str, Any] = {}
                for label, field_value in value.items():
                    info = self._protocol_field_service.find_receive_field(
                        selection_category, section_name, label
                    )
                    if info is None:
                        section_result[label] = field_value
                        continue
                    if selected_keys is None or info.key in selected_keys:
                        section_result[label] = field_value
                if section_result:
                    filtered[section_name] = section_result
            else:
                filtered[section_name] = value

        return filtered

    def _setup_workers(self):
        """Create worker placeholders used by start/stop logic.

        We intentionally keep these as light placeholders. Tests expect
        attributes `parse_worker_thread` and `format_worker_thread` to exist
        (and to be None or not alive after stopping).
        """
        self.parse_worker = None
        self.parse_worker_thread = None
        self.format_worker = None
        self.format_worker_thread = None

    def start_communication(self):
        """Start communication: configure comm, start receive loop and timers."""
        try:
            acu_ip = self.acu_ip_edit.text()
            acu_send_port = int(self.acu_send_port_edit.text())
            acu_receive_port = int(self.acu_receive_port_edit.text())
            target_ip = self.target_ip_edit.text()
            target_receive_port = int(self.target_receive_port_edit.text())

            self.comm.update_config(
                acu_ip=acu_ip,
                acu_send_port=acu_send_port,
                acu_receive_port=acu_receive_port,
                target_ip=target_ip,
                target_receive_port=target_receive_port,
            )

            try:
                setup_ok = self.comm.setup()
            except Exception as exc:
                logger.exception("Communication setup raised an exception")
                self._show_error(f"Socket 初始化异常: {exc}")
                return False

            if setup_ok:
                try:
                    self.comm.start_receive_loop()
                except Exception:
                    logger.exception("start_receive_loop failed")
                    self._show_error("启动接收循环失败，请检查网络配置或权限。")
                    self._set_comm_status_indicator("#e74c3c", "启动接收失败")
                    return False

                # start parse/format workers
                try:
                    self._start_workers()
                except Exception as exc:
                    logger.exception("启动后台 worker 失败")
                    self._show_error(f"启动后台处理失败: {exc}")
                    # attempt best-effort stop
                    try:
                        self.stop_communication()
                    except Exception:
                        pass
                    self._set_comm_status_indicator("#e74c3c", "后台处理启动失败")
                    return False

                period = int(self.period_spin.value())
                self.send_timer.start(period)
                self.is_sending = True

                self.start_btn.setEnabled(False)
                self.stop_btn.setEnabled(True)

                try:
                    self.view_bus.recording_toggle.emit(True)
                except Exception:
                    logger.exception("Emitting recording_toggle failed")

                self._set_comm_status_indicator("#2ecc71", "通信已启动")
                self.on_status_updated("Communication started")
                self._show_info("通信已启动")
                return True
            else:
                logger.warning("Communication.setup() returned False")
                self._show_error("Socket 初始化失败，请检查端口或权限")
                self.on_status_updated("Socket init failed")
                self._set_comm_status_indicator("#e74c3c", "Socket 初始化失败")
                return False

        except Exception as e:
            logger.exception("Unexpected error starting communication")
            self._show_error(f"启动通信失败: {e}")
            self.on_status_updated(f"Start failed: {e}")
            self._set_comm_status_indicator("#e74c3c", "通信启动失败")
            return False

    def run_test_once(self):
        """Send a single test waveform event (non-blocking)."""
        try:
            # Prepare a frame (best-effort) and emit via view bus so UI receives it
            self.prepare_send_data()
            sent_via_comm = False
            try:
                if getattr(self.comm, "send", None) is not None:
                    self.comm.send(bytes(self.send_data_buffer))
                    sent_via_comm = True
            except Exception as exc:
                logger.exception("Test UDP send failed")
                try:
                    self.on_status_updated(f"UDP发送失败: {exc}")
                except Exception:
                    pass
            try:
                self.view_bus.waveform_send.emit(
                    bytearray(self.send_data_buffer), time.time()
                )
                self.on_status_updated("Test frame sent")
            except Exception:
                if not sent_via_comm:
                    try:
                        if getattr(self.comm, "send", None) is not None:
                            self.comm.send(bytes(self.send_data_buffer))
                            sent_via_comm = True
                    except Exception as exc:
                        self.on_status_updated(f"Test send failed: {exc}")
                        return
                if sent_via_comm:
                    self.on_status_updated("Test frame sent via comm")
        except Exception as exc:
            self.on_status_updated(f"Test preparation failed: {exc}")

    def preview_once(self):
        """Quick preview action: trigger a single waveform emit and
        auto-range refresh.
        """
        try:
            # trigger a test send so waveform_display receives something
            self.run_test_once()
            try:
                if getattr(self, "waveform_display", None) is not None:
                    self.waveform_display.waveform_widget.auto_range()
            except Exception:
                pass
        except Exception:
            pass

    def stop_communication(self):
        """Stop communication and background workers."""
        try:
            self.send_timer.stop()
        except Exception:
            pass

        try:
            self.comm.stop()
        except Exception:
            logger.exception("comm.stop() failed")
            self._show_error("停止通信时发生错误，请查看日志。")

        self.is_sending = False
        if not getattr(self, "_cleanup_in_progress", False):
            self._set_comm_status_indicator("#999", "通信已停止")

        # Stop and clean up workers
        try:
            self._stop_workers()
        except Exception:
            # best-effort cleanup
            pass

        # Clear thread placeholders to satisfy tests expecting .is_alive()
        self.parse_worker_thread = None
        self.format_worker_thread = None

        try:
            self.view_bus.recording_toggle.emit(False)
        except Exception:
            logger.exception("Emitting recording_toggle(False) failed")

        if not getattr(self, "_cleanup_in_progress", False):
            try:
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
            except Exception:
                pass
            try:
                self.on_status_updated("Communication stopped")
            except Exception:
                pass

    def send_periodic_data(self):
        """Called periodically to emit send waveform events."""
        if not getattr(self, "is_sending", False):
            return
        try:
            self.prepare_send_data()
            if getattr(self.comm, "send", None) is not None:
                self.comm.send(bytes(self.send_data_buffer))
            self.view_bus.waveform_send.emit(
                bytearray(self.send_data_buffer), time.time()
            )
        except Exception:
            pass

    def on_data_received_comm(self, data: bytes, addr: tuple):
        """Callback adapter for CommunicationController receive events."""
        try:
            ip, port = addr[0], addr[1]
        except Exception:
            ip = str(addr)
            port = 0
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # Enqueue for parsing
        try:
            self.parse_queue.put((data, f"{ip}:{port}", port, timestamp))
        except Exception:
            pass

        # Quick waveform emit if parse controller can handle it
        try:
            device_type = self.parse_controller.device_type_from_port(port)
            device_category = self.parse_controller.category_from_device(device_type)
            if device_category in ["INV", "CHU", "BCC", "DUMMY"]:
                parsed_data = self.parse_controller.parse(data, port)
                self.view_bus.waveform_receive.emit(
                    parsed_data, device_type, time.time()
                )
        except Exception:
            pass

    def prepare_send_data(self):
        """Prepare the send buffer using frame_builder if available."""
        try:
            try:
                self._update_control_state_from_ui()
            except Exception:
                pass
            if getattr(self, "_frame_builder", None) is not None:
                frame = self._frame_builder.build()
                self.send_data_buffer = frame
        except Exception:
            # keep existing buffer on failure
            pass

    def on_status_updated(self, status_msg):
        """Update status label and optionally log the status."""
        try:
            self.status_label.setText(status_msg)
            logger.info(status_msg)
        except Exception:
            pass

    def _show_info(self, message: str, title: str = "信息"):
        """Show an informational message if dialogs are enabled; also log."""
        try:
            logger.info(message)
            if getattr(self, "_enable_dialogs", True):
                try:
                    QMessageBox.information(self, title, message)
                except Exception:
                    pass
        except Exception:
            pass

    # Note: The full set of methods for ACUSimulator (UI setup, handlers,
    # worker management, save/load, etc.) are intentionally omitted here for
    # brevity in the patch preview. The implementation in this file mirrors
    # the original logic from the repository's `ACU_simulation.py`.

    def _on_parse_result(self, record: RecordDict):
        """Handle parse worker results: record into history and forward to formatter."""
        try:
            self.parsed_data_history.append(record)
        except Exception:
            pass
        try:
            # forward to format queue for formatting
            self.format_queue.put(record)
        except Exception:
            pass
        # Buffer parse records for UI-friendly incremental insertion
        try:
            if getattr(self, "parse_table", None) is not None:
                try:
                    self.parse_table_buffer.append(record)
                    # ensure the UI timer is running to drain the buffer
                    if not self.ui_update_timer.isActive():
                        self.ui_update_timer.start()
                except Exception:
                    # fallback to direct insertion on failure
                    try:
                        self._add_parse_record_to_table(record)
                    except Exception:
                        pass
        except Exception:
            pass

        # Buffer for receive tree updates
        try:
            if getattr(self, "recv_tree", None) is not None:
                self.recv_tree_buffer.append(record)
                if not self.recv_tree_timer.isActive():
                    self.recv_tree_timer.start()
        except Exception:
            pass

    def _drain_parse_table(self):
        """Drain a limited number of buffered parse records into the table.

        This keeps UI updates incremental and prevents long blocking operations
        when a large number of parse records arrive in a short time.
        """
        try:
            if not getattr(self, "parse_table", None):
                try:
                    self.ui_update_timer.stop()
                except Exception:
                    pass
                return

            processed = 0
            max_per_tick = 50
            while self.parse_table_buffer and processed < max_per_tick:
                try:
                    record = self.parse_table_buffer.popleft()
                except Exception:
                    break
                try:
                    self._add_parse_record_to_table(record)
                except Exception:
                    pass
                processed += 1

            # stop timer if buffer drained
            if not self.parse_table_buffer:
                try:
                    self.ui_update_timer.stop()
                except Exception:
                    pass
        except Exception:
            try:
                self.ui_update_timer.stop()
            except Exception:
                pass

    def _add_parse_record_to_table(self, record: RecordDict):
        try:
            # keep a bounded table size by removing oldest rows if necessary
            max_rows = max(1000, getattr(self, "max_parse_records", 5000))
            table = self.parse_table
            # append at end
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(record.get("timestamp", ""))))
            table.setItem(row, 1, QTableWidgetItem(str(record.get("address", ""))))
            table.setItem(row, 2, QTableWidgetItem(str(record.get("device_type", ""))))
            table.setItem(row, 3, QTableWidgetItem(str(record.get("data_length", ""))))
            # parsed_data may be complex; store as string
            parsed = record.get("parsed_data", "")
            try:
                parsed_str = str(parsed)
            except Exception:
                parsed_str = "<unserializable>"
            table.setItem(row, 4, QTableWidgetItem(parsed_str))

            # prune
            if table.rowCount() > max_rows:
                # remove top rows
                remove_count = table.rowCount() - max_rows
                for _ in range(remove_count):
                    table.removeRow(0)
        except Exception:
            pass

    def _drain_recv_tree(self):
        """Incrementally update the receive tree with parsed records."""
        try:
            if not getattr(self, "recv_tree", None):
                self.recv_tree_timer.stop()
                return
            processed = 0
            max_per_tick = 50
            while self.recv_tree_buffer and processed < max_per_tick:
                try:
                    record = self.recv_tree_buffer.popleft()
                except Exception:
                    break
                try:
                    filtered = self._filter_parsed_record(record)
                except Exception:
                    filtered = record.get("parsed_data", {}) or {}
                try:
                    self._update_recv_tree(filtered)
                except Exception:
                    pass
                processed += 1
            if not self.recv_tree_buffer:
                self.recv_tree_timer.stop()
        except Exception:
            try:
                self.recv_tree_timer.stop()
            except Exception:
                pass

    def _get_or_create_category_item(self, category: str):
        tree = self.recv_tree
        cat = self._recv_tree_categories.get(category)
        if cat is None:
            cat = QTreeWidgetItem(tree, [category, ""])
            cat.setExpanded(True)
            self._recv_tree_categories[category] = cat
            self._recv_tree_keys[category] = {}
        return cat

    def _get_or_create_key_item(self, category: str, key: str):
        parent = self._get_or_create_category_item(category)
        d = self._recv_tree_keys.get(category) or {}
        item = d.get(key)
        if item is None:
            item = QTreeWidgetItem(parent, [key, "--"])
            d[key] = item
            self._recv_tree_keys[category] = d
        return item

    def _update_recv_tree(self, parsed: Dict[str, Any]):
        """Merge a parsed_data dict into the recv_tree items.

        Supports top-level categories mapping to dicts of key->value. For deeper
        nesting, value is stringified.
        """
        for category, value in parsed.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    item = self._get_or_create_key_item(category, str(k))
                    try:
                        item.setText(1, str(v))
                    except Exception:
                        pass
            else:
                # Put non-dict values under a special category
                item = self._get_or_create_key_item(str(category), "值")
                try:
                    item.setText(1, str(value))
                except Exception:
                    pass

    def _start_workers(self):
        """Create and start parse/format workers in separate QThreads."""
        # Parse worker
        if getattr(self, "parse_worker", None) is None:
            self.parse_worker = ParseWorker(self.parse_controller, self.parse_queue)
            self.parse_worker_thread = QThread()
            self.parse_worker.moveToThread(self.parse_worker_thread)
            # connect signals
            self.parse_worker.parse_result.connect(self._on_parse_result)
            self.parse_worker_thread.started.connect(self.parse_worker.start)
            self.parse_worker_thread.start()

        # Format worker
        if getattr(self, "format_worker", None) is None:
            self.format_worker = FormatWorker(self.format_queue, self.formatted_queue)
            self.format_worker_thread = QThread()
            self.format_worker.moveToThread(self.format_worker_thread)
            self.format_worker_thread.started.connect(self.format_worker.start)
            self.format_worker_thread.start()

    def _stop_workers(self):
        """Stop and clean up parse/format worker threads."""
        # Stop parse worker
        if getattr(self, "parse_worker", None) is not None:
            try:
                QMetaObject.invokeMethod(self.parse_worker, "stop")
            except Exception:
                try:
                    self.parse_worker.stop()
                except Exception:
                    pass
        if getattr(self, "parse_worker_thread", None) is not None:
            try:
                self.parse_worker_thread.quit()
                self.parse_worker_thread.wait(500)
            except Exception:
                pass
        if getattr(self, "parse_worker", None) is not None:
            try:
                self.parse_worker.deleteLater()
            except Exception:
                pass

        # Stop format worker
        if getattr(self, "format_worker", None) is not None:
            try:
                QMetaObject.invokeMethod(self.format_worker, "stop")
            except Exception:
                try:
                    self.format_worker.stop()
                except Exception:
                    pass
        if getattr(self, "format_worker_thread", None) is not None:
            try:
                self.format_worker_thread.quit()
                self.format_worker_thread.wait(500)
            except Exception:
                pass
        if getattr(self, "format_worker", None) is not None:
            try:
                self.format_worker.deleteLater()
            except Exception:
                pass

        # Clear instances
        self.parse_worker = None
        self.parse_worker_thread = None
        self.format_worker = None
        self.format_worker_thread = None

    def _stop_timers(self):
        """Stop recurring QTimers owned by the main window."""
        timer_attrs = [
            "send_timer",
            "ui_update_timer",
            "recv_tree_timer",
            "_rebuild_timer",
            "memory_check_timer",
        ]
        for attr in timer_attrs:
            timer = getattr(self, attr, None)
            if isinstance(timer, QTimer):
                try:
                    timer.stop()
                except Exception:
                    pass
                try:
                    timer.deleteLater()
                except Exception:
                    pass

    def _cleanup_resources(self):
        if getattr(self, "_cleanup_done", False):
            return
        self._cleanup_done = True
        self._cleanup_in_progress = True

        try:
            self.stop_communication()
        except Exception:
            pass

        try:
            self._stop_timers()
        except Exception:
            pass

        for thread_attr in ("parse_worker_thread", "format_worker_thread"):
            thread = getattr(self, thread_attr, None)
            if isinstance(thread, QThread):
                try:
                    thread.quit()
                    thread.wait(1000)
                except Exception:
                    pass

        display = getattr(self, "waveform_display", None)
        if display is not None:
            try:
                display.shutdown()
            except Exception:
                pass
            try:
                display.save_settings()
            except Exception:
                pass

        self._persist_window_settings()

        try:
            handler = getattr(self, "_log_handler", None)
            if handler is not None:
                root_logger = logging.getLogger("ACUSim")
                try:
                    root_logger.removeHandler(handler)
                except Exception:
                    pass
                for name in ["WaveformController", "WaveformPlot", "WaveformDisplay"]:
                    try:
                        logging.getLogger(name).removeHandler(handler)
                    except Exception:
                        pass
        except Exception:
            pass
        self._log_handler = None

    def _persist_window_settings(self):
        try:
            settings = QSettings()
            settings.beginGroup("ACUSimulator")
            try:
                settings.setValue("geometry", self.saveGeometry())
                try:
                    settings.setValue("main_state", self.saveState())
                except Exception:
                    pass
                try:
                    sidebar = getattr(self, "sidebar_nav", None)
                    if sidebar is not None:
                        settings.setValue("sidebar_index", sidebar.currentRow())
                except Exception:
                    pass
            except Exception:
                pass
            settings.endGroup()
            settings.sync()
        except Exception:
            pass

    def _on_destroyed(self, _obj=None):
        try:
            self._cleanup_resources()
        except Exception:
            pass

    def event(self, event):
        try:
            if event.type() == QEvent.DeferredDelete:
                self._cleanup_resources()
        except Exception:
            pass
        return super().event(event)

    def closeEvent(self, event):
        """Ensure resources are released when the window closes."""
        try:
            self._cleanup_resources()
        except Exception:
            pass

        try:
            super().closeEvent(event)
        except Exception:
            event.accept()

    # ---- Dock helpers ----
    def _init_docks(self):
        """Create additional dock widgets (currently: parse table).

        Keeps attribute names (`parse_table`) for test compatibility.
        """
        try:
            self.parse_table = QTableWidget()
            self.parse_table.setObjectName("parse_table_widget")
            self.parse_table.setColumnCount(5)
            self.parse_table.setHorizontalHeaderLabels(
                [
                    "timestamp",
                    "address",
                    "device_type",
                    "data_length",
                    "parsed_data",
                ]
            )
            self.parse_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.Stretch
            )
            self._embed_parse_table_into_header()

            # legacy dock shim: keep a dock entry so旧布局仍可恢复，但引导至侧边栏
            try:
                parse_dock = QDockWidget("解析表", self)
                parse_dock.setObjectName("dock_parse_table")
                notice = QWidget()
                notice_layout = QVBoxLayout(notice)
                notice_layout.setContentsMargins(8, 8, 8, 8)
                label = QLabel("解析表已移动至侧边栏 -> 解析表头 页面。")
                label.setWordWrap(True)
                btn = QPushButton("跳转到解析表页面")
                btn.clicked.connect(lambda: self.sidebar_nav.setCurrentRow(3))
                notice_layout.addWidget(label)
                notice_layout.addWidget(btn)
                notice_layout.addStretch(1)
                parse_dock.setWidget(notice)
                self.addDockWidget(Qt.BottomDockWidgetArea, parse_dock)
            except Exception:
                pass
        except Exception:
            self.parse_table = None

    def _embed_parse_table_into_header(self):
        layout = getattr(self, "parse_table_group_layout", None)
        table = getattr(self, "parse_table", None)
        if not layout or table is None:
            return
        try:
            placeholder = getattr(self, "parse_table_group_placeholder", None)
            if placeholder is not None:
                layout.removeWidget(placeholder)
                placeholder.deleteLater()
                self.parse_table_group_placeholder = None
        except Exception:
            pass
        try:
            if (
                table.parent() is not None
                and table.parent() is not self.parse_table_group
            ):
                table.setParent(None)
        except Exception:
            pass
        try:
            layout.addWidget(table)
        except Exception:
            pass

    def _restore_mainwindow_state(self):
        """Restore QMainWindow geometry and dock state from QSettings."""
        settings = QSettings()
        settings.beginGroup("ACUSimulator")
        try:
            geom = settings.value("geometry")
            if geom is not None:
                try:
                    self.restoreGeometry(geom)
                except Exception:
                    pass
            state = settings.value("main_state")
            if state is not None:
                try:
                    self.restoreState(state)
                except Exception:
                    pass
            # Restore sidebar selected page
            try:
                idx = int(settings.value("sidebar_index", 1))
                if getattr(self, "sidebar_nav", None) is not None:
                    self.sidebar_nav.setCurrentRow(
                        max(0, min(idx, self.sidebar_pages.count() - 1))
                    )
            except Exception:
                pass
        finally:
            settings.endGroup()

    # ---- Logging handler ----
    def _attach_log_handler(self):
        """Attach a logging.Handler that writes to the log dock widget."""
        if not getattr(self, "log_view", None):
            return
        import logging

        class _DockLogHandler(logging.Handler):
            def __init__(self, widget):
                super().__init__()
                self.widget = widget

            def emit(self, record):
                try:
                    msg = self.format(record)
                    from PySide6.QtCore import QTimer

                    target = self.widget

                    def _append_safe(widget=target, text=msg):
                        try:
                            if widget is None or not isValid(widget):
                                return
                            widget.appendPlainText(text)
                        except Exception:
                            pass

                    QTimer.singleShot(0, _append_safe)
                except Exception:
                    pass

        handler = _DockLogHandler(self.log_view)
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        handler.setLevel(logging.INFO)
        root_logger = logging.getLogger("ACUSim")
        # Avoid duplicate handlers stacking
        for h in list(root_logger.handlers):
            if isinstance(h, _DockLogHandler):
                root_logger.removeHandler(h)
        root_logger.addHandler(handler)
        self._log_handler = handler
        # Optionally attach to waveform/log related loggers
        for name in ["WaveformController", "WaveformPlot", "WaveformDisplay"]:
            try:
                lg = logging.getLogger(name)
                lg.addHandler(handler)
            except Exception:
                pass

    # ---- Parse table header persistence ----
    def _save_header_visibility_settings(self):
        try:
            settings = QSettings()
            settings.beginGroup("ACUSimulator")
            try:
                data = {
                    "timestamp": bool(self.chk_col_timestamp.isChecked()),
                    "address": bool(self.chk_col_address.isChecked()),
                    "device_type": bool(self.chk_col_device.isChecked()),
                    "data_length": bool(self.chk_col_length.isChecked()),
                    "parsed_data": bool(self.chk_col_parsed.isChecked()),
                }
                settings.setValue("parse_header_visibility", data)
            finally:
                settings.endGroup()
        except Exception:
            pass

    def _load_header_visibility_settings(self):
        try:
            settings = QSettings()
            settings.beginGroup("ACUSimulator")
            try:
                hv = settings.value("parse_header_visibility")
                if isinstance(hv, dict):
                    self.chk_col_timestamp.setChecked(bool(hv.get("timestamp", True)))
                    self.chk_col_address.setChecked(bool(hv.get("address", True)))
                    self.chk_col_device.setChecked(bool(hv.get("device_type", True)))
                    self.chk_col_length.setChecked(bool(hv.get("data_length", True)))
                    self.chk_col_parsed.setChecked(bool(hv.get("parsed_data", True)))
            finally:
                settings.endGroup()
        except Exception:
            pass

    def _apply_header_visibility_settings_to_table(self):
        table = getattr(self, "parse_table", None)
        if not table:
            return
        try:
            table.setColumnHidden(0, not self.chk_col_timestamp.isChecked())
            table.setColumnHidden(1, not self.chk_col_address.isChecked())
            table.setColumnHidden(2, not self.chk_col_device.isChecked())
            table.setColumnHidden(3, not self.chk_col_length.isChecked())
            table.setColumnHidden(4, not self.chk_col_parsed.isChecked())
        except Exception:
            pass

    def _set_comm_status_indicator(self, color: str, tooltip: str = ""):
        """Update the status indicator dot color and tooltip."""
        indicator = getattr(self, "comm_status_indicator", None)
        if not indicator:
            return
        try:
            indicator.setStyleSheet(
                f"border-radius:7px; border:1px solid #555; background-color:{color};"
            )
            if tooltip:
                indicator.setToolTip(tooltip)
        except Exception:
            pass

    def _update_control_state_from_ui(self) -> bool:
        """Sync widgets on the 发送配置 page back into the control state model."""
        cs = getattr(self, "_control_state_model", None)
        if not cs:
            return False

        bool_maps: Dict[str, Dict[Tuple[int, int], bool]] = defaultdict(dict)
        packed_maps: Dict[str, Dict[int, bool]] = defaultdict(dict)
        numeric_maps: Dict[str, Dict[int, float]] = defaultdict(dict)
        scalar_values: Dict[str, float] = {}

        for key, widget in self._send_field_widgets.items():
            info = self._send_field_infos.get(key)
            if info is None:
                continue

            if isinstance(widget, QCheckBox):
                checked = widget.isChecked()
                if (
                    info.kind == "bool_bitset"
                    and info.byte is not None
                    and info.bit is not None
                ):
                    if checked:
                        bool_maps[info.source][(info.byte, info.bit)] = True
                elif info.kind == "packed_bit" and info.bit is not None:
                    if checked:
                        packed_maps[info.source][info.bit] = True
            elif hasattr(widget, "value"):
                try:
                    value = widget.value()
                except Exception:
                    continue
                if info.kind == "scalar_word" and info.source == "battery_temp":
                    scalar_values[info.source] = int(value)
                elif info.offset is not None:
                    if info.source == "start_times":
                        val = int(value)
                    else:
                        val = float(value)
                    if val > 0:
                        numeric_maps[info.source][info.offset] = val

        cs.bool_commands = dict(bool_maps.get("bool_commands", {}))
        cs.chu_controls = dict(bool_maps.get("chu_controls", {}))
        cs.redundant_commands = dict(bool_maps.get("redundant_commands", {}))
        cs.isolation_commands = dict(packed_maps.get("isolation_commands", {}))
        cs.start_commands = dict(packed_maps.get("start_commands", {}))
        cs.freq_controls = {
            offset: float(val)
            for offset, val in numeric_maps.get("freq_controls", {}).items()
        }
        cs.start_times = {
            offset: int(val)
            for offset, val in numeric_maps.get("start_times", {}).items()
        }
        cs.branch_voltages = {
            offset: float(val)
            for offset, val in numeric_maps.get("branch_voltages", {}).items()
        }
        if "battery_temp" in scalar_values:
            cs.battery_temp = int(scalar_values["battery_temp"])

        try:
            self.control_values["bool_commands"] = dict(cs.bool_commands)
            self.control_values["chu_controls"] = dict(cs.chu_controls)
            self.control_values["redundant_commands"] = dict(cs.redundant_commands)
            self.control_values["isolation_commands"] = dict(cs.isolation_commands)
            self.control_values["start_commands"] = dict(cs.start_commands)
            self.control_values["freq_controls"] = dict(cs.freq_controls)
            self.control_values["start_times"] = dict(cs.start_times)
            self.control_values["branch_voltages"] = dict(cs.branch_voltages)
            self.control_values["battery_temp"] = getattr(cs, "battery_temp", 25)
        except Exception:
            pass

        return True

    # ---- Send config actions ----
    def _apply_send_config(self, *args, show_message: bool = True):
        """Apply values from '发送配置' page to ControlState."""
        try:
            updated = self._update_control_state_from_ui()
            if updated and show_message:
                self._show_info("发送配置已应用到内部状态。")
        except Exception:
            self._show_error("应用发送配置失败。")

    def _preview_send_frame(self):
        try:
            self._update_control_state_from_ui()
            self.prepare_send_data()
            data = bytes(self.send_data_buffer)
            if not data:
                self.sc_preview_edit.setPlainText("No data to preview")
                return
            hex_str = " ".join(f"{b:02X}" for b in data[:256])
            suffix = " ..." if len(data) > 256 else ""
            self.sc_preview_edit.setPlainText(hex_str + suffix)
        except Exception:
            self.sc_preview_edit.setPlainText("<预览失败>")
