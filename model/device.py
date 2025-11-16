from dataclasses import dataclass, field
from typing import Optional, Dict

@dataclass
class DeviceConfig:
    name: str
    ip: str
    send_port: int
    receive_port: Optional[int] = None
    category: str = "UNKNOWN"  # INV / CHU / BCC / ACU

@dataclass
class DeviceState:
    life_signal: int = 0
    last_seen_timestamp: Optional[float] = None
    parsed_cache: Dict[str, Dict] = field(default_factory=dict)

@dataclass
class Device:
    config: DeviceConfig
    state: DeviceState = field(default_factory=DeviceState)

    def update_life(self):
        self.state.life_signal = (self.state.life_signal + 1) % 65536
        return self.state.life_signal
