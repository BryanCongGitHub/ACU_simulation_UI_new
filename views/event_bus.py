from PySide6.QtCore import QObject, Signal

class ViewEventBus(QObject):
    """UI 层事件总线：打通控制器与各个视图组件。"""

    waveform_send = Signal(object, float)          # data_buffer, timestamp
    waveform_receive = Signal(object, str, float)  # parsed_data, device_type, timestamp
    recording_toggle = Signal(bool)                # True=开始，False=停止

    def __init__(self):
        super().__init__()
