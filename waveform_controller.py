# waveform_controller.py
import time
import logging
from PySide6.QtCore import QObject, QTimer, Signal
from data_buffer import DataBuffer
from signal_manager import SignalManager

# 创建日志记录器
logger = logging.getLogger("WaveformController")
logger.setLevel(logging.INFO)

class WaveformController(QObject):
    """改进的波形控制器"""
    
    data_updated = Signal()
    
    def __init__(self):
        super().__init__()
        self.signal_manager = SignalManager()
        self.data_buffer = DataBuffer(max_points=5000)
        self.selected_signals = set()
        self.is_recording = False
        self.start_time = time.time()
        
        # 使用单个定时器统一更新
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._on_update_timer)
        self.update_timer.start(200)  # 5Hz更新
        
        logger.info("WaveformController 初始化完成")
    
    def _on_update_timer(self):
        """定时器回调 - 统一通知更新"""
        if self.is_recording and self.selected_signals:
            logger.debug(f"定时器触发更新，选中信号: {len(self.selected_signals)} 个")
            self.data_updated.emit()
    
    def start_recording(self):
        """开始记录"""
        self.is_recording = True
        self.start_time = time.time()
        logger.info("波形记录已开始")
    
    def stop_recording(self):
        """停止记录"""
        self.is_recording = False
        logger.info("波形记录已停止")
    
    def add_send_data(self, data_buffer, timestamp=None):
        """添加发送数据"""
        if not self.is_recording:
            logger.debug("未在记录状态，忽略数据")
            return
            
        if timestamp is None:
            timestamp = time.time()
        
        # 收集所有信号值
        signal_values = {}
        inv2_debug_info = None
        
        for signal_id in self.selected_signals:
            if signal_id.startswith('send_'):
                signal_info = self.signal_manager.get_signal_info(signal_id)
                if signal_info:
                    value = self._extract_signal_value(data_buffer, signal_info)
                    if value is not None:
                        signal_values[signal_id] = value
                        
                        # 捕获INV2频率调试信息
                        if signal_info['name'] == 'INV2频率':
                            inv2_debug_info = {
                                'byte': signal_info.get('byte'),
                                'value': value,
                                'raw_bytes': f"{data_buffer[10]:02X}{data_buffer[11]:02X}"
                            }
        
        # 一次性添加所有数据
        if signal_values:
            logger.debug(f"准备批量添加信号值: {[(k, v) for k, v in list(signal_values.items())[:3]]}...")
            self.data_buffer.add_data_points(signal_values, timestamp)
        else:
            logger.debug("无有效信号值可添加")

    def add_receive_data(self, parsed_data, device_type, timestamp=None):
        """添加接收数据"""
        if not self.is_recording:
            return
            
        if timestamp is None:
            timestamp = time.time()
        
        # 收集所有信号值
        signal_values = {}
        for signal_id in self.selected_signals:
            if signal_id.startswith('recv_'):
                signal_info = self.signal_manager.get_signal_info(signal_id)
                if signal_info:
                    value = self._extract_receive_signal_value(parsed_data, signal_info, device_type)
                    if value is not None:
                        signal_values[signal_id] = value
        
        # 一次性添加所有数据
        if signal_values:
            self.data_buffer.add_data_points(signal_values, timestamp)
    
    def _extract_signal_value(self, data_buffer, signal_info):
        """从发送数据缓冲区提取信号值 - 修复版本"""
        try:
            byte_pos = signal_info.get('byte')
            if byte_pos is None:
                logger.warning(f"信号 {signal_info.get('name')} 无字节位置")
                return None
                
            if signal_info['type'] == 'bool':
                bit_pos = signal_info.get('bit')
                if bit_pos is not None and byte_pos < len(data_buffer):
                    value = 1 if (data_buffer[byte_pos] & (1 << bit_pos)) else 0
                    logger.debug(f"提取布尔信号: {signal_info['name']} 字节{byte_pos}位{bit_pos} = {value}")
                    return value
                else:
                    logger.warning(f"布尔信号 {signal_info['name']} 位位置无效")
                    return 0
                    
            elif signal_info['type'] == 'analog':
                if byte_pos + 1 < len(data_buffer):
                    raw_value = (data_buffer[byte_pos] << 8) | data_buffer[byte_pos + 1]
                    
                    # 根据信号类型进行转换
                    if '频率' in signal_info['name']:
                        value = raw_value * 0.1
                        logger.debug(f"提取频率信号: {signal_info['name']} 原始值={raw_value} 转换后={value} Hz")
                        return value
                    elif '电压' in signal_info['name']:
                        value = raw_value * 0.25
                        logger.debug(f"提取电压信号: {signal_info['name']} 原始值={raw_value} 转换后={value} V")
                        return value
                    elif '温度' in signal_info['name']:
                        value = raw_value * 0.1
                        logger.debug(f"提取温度信号: {signal_info['name']} 原始值={raw_value} 转换后={value} °C")
                        return value
                    elif '生命信号' in signal_info['name'] or '软件编码' in signal_info['name'] or '软件版本' in signal_info['name']:
                        # 设备信息类信号（生命信号、软件编码、软件版本等）直接使用原始值
                        logger.debug(f"提取设备信息信号: {signal_info['name']} = {raw_value}")
                        return raw_value
                    else:
                        logger.debug(f"提取模拟信号: {signal_info['name']} = {raw_value}")
                        return raw_value
                else:
                    logger.warning(f"模拟信号 {signal_info['name']} 字节位置超出范围")
                    return 0
                    
        except Exception as e:
            logger.error(f"提取信号值错误 {signal_info.get('name')}: {e}")
            return 0  # 返回默认值而不是None
    
    def _extract_receive_signal_value(self, parsed_data, signal_info, device_type):
        """从解析数据中提取接收信号值"""
        try:
            signal_name = signal_info['name']
            
            # 在解析数据中查找对应的值
            for category, items in parsed_data.items():
                if isinstance(items, dict):
                    for key, value in items.items():
                        if signal_name == key:  # 精确匹配信号名称
                            # 布尔信号返回 0 或 1
                            if signal_info['type'] == 'bool':
                                return 1 if value else 0
                            else:
                                return float(value) if isinstance(value, (int, float)) else value
            
            # 对于设备信息类模拟信号（APU生命信号、软件编码、软件版本等），从设备信息中提取
            if signal_info['type'] == 'analog' and signal_info['category'] == '设备信息':
                device_info = parsed_data.get("设备信息", {})
                # 去掉信号名称中的"APU"前缀来匹配解析数据中的键名
                clean_signal_name = signal_name.replace("APU", "").strip()
                if clean_signal_name in device_info:
                    value = device_info[clean_signal_name]
                    logger.debug(f"提取设备信息信号: {signal_name} = {value}")
                    return float(value) if isinstance(value, (int, float)) else value
            
            # 对于故障类布尔信号，需要特殊处理
            if signal_info['type'] == 'bool' and signal_info['category'] == '故障信息':
                # 检查是否在故障列表中
                fault_list = parsed_data.get("故障信息", {}).get("故障列表", [])
                if signal_name in fault_list or \
                   signal_name.replace('BCC', '') in fault_list or \
                   signal_name.replace('模块', '') in fault_list:
                    return 1
                else:
                    return 0
                    
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"提取接收信号错误: {e}")
            pass
            
        return None
    
    def select_signal(self, signal_id):
        """选择要显示的信号"""
        self.selected_signals.add(signal_id)
        logger.info(f"选择信号: {signal_id}")
    
    def deselect_signal(self, signal_id):
        """取消选择信号"""
        self.selected_signals.discard(signal_id)
        logger.info(f"取消选择信号: {signal_id}")
    
    def get_selected_signals(self):
        """获取选中的信号"""
        return list(self.selected_signals)
    
    def clear_buffer(self):
        """清空数据缓冲区"""
        self.data_buffer.clear()
    
    def get_signal_data(self, signal_id):
        """获取信号数据"""
        return self.data_buffer.get_data(signal_id)
    
    def get_timestamps(self):
        """获取时间戳数据"""
        return self.data_buffer.get_timestamps()
    
    def get_latest_value(self, signal_id):
        """获取最新值"""
        return self.data_buffer.get_latest_value(signal_id)
    
    def get_current_time_range(self, time_range_seconds=300):
        """获取当前时间范围的数据"""
        current_time = time.time()
        start_time = current_time - time_range_seconds
        
        result = {}
        for signal_id in self.selected_signals:
            times, values = self.data_buffer.get_time_range_data(
                signal_id, start_time, current_time)
            result[signal_id] = {'times': times, 'values': values}
            
        return result