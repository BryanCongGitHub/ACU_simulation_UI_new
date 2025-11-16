from dataclasses import dataclass, field
from typing import Dict, Tuple

@dataclass
class ControlState:
    bool_commands: Dict[Tuple[int,int], bool] = field(default_factory=dict)
    freq_controls: Dict[int, int] = field(default_factory=dict)  # Hz integer
    isolation_commands: Dict[int, bool] = field(default_factory=dict)
    start_commands: Dict[int, bool] = field(default_factory=dict)
    chu_controls: Dict[Tuple[int,int], bool] = field(default_factory=dict)
    redundant_commands: Dict[Tuple[int,int], bool] = field(default_factory=dict)
    start_times: Dict[int, int] = field(default_factory=dict)  # seconds
    branch_voltages: Dict[int, int] = field(default_factory=dict)  # volts
    battery_temp: int = 25

    def snapshot(self):
        """返回不可变快照用于构建帧，避免并发写入导致的状态不一致"""
        return {
            'bool_commands': dict(self.bool_commands),
            'freq_controls': dict(self.freq_controls),
            'isolation_commands': dict(self.isolation_commands),
            'start_commands': dict(self.start_commands),
            'chu_controls': dict(self.chu_controls),
            'redundant_commands': dict(self.redundant_commands),
            'start_times': dict(self.start_times),
            'branch_voltages': dict(self.branch_voltages),
            'battery_temp': self.battery_temp
        }
