"""PeripheralHub Battery & Device Data Models.

Defines the core data structures for device state, charging status,
and serialization helpers.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
import time
from typing import Optional, Dict, Any


class ChargingStatus(str, Enum):
    CHARGING = "charging"
    DISCHARGING = "discharging"
    FULL = "full"
    NOT_CHARGING = "not_charging"
    UNKNOWN = "unknown"
    NOT_SUPPORTED = "unsupported"


class DeviceType(str, Enum):
    MOUSE = "mouse"
    KEYBOARD = "keyboard"
    HEADSET = "headset"


@dataclass
class DeviceState:
    device_id: str
    name: str
    model: str
    device_type: DeviceType
    receiver_connected: bool = False
    device_connected: bool = False
    battery_percentage: Optional[int] = None
    charging_status: ChargingStatus = ChargingStatus.UNKNOWN
    last_reading_time: Optional[float] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["device_type"] = self.device_type.value
        d["charging_status"] = self.charging_status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DeviceState:
        return cls(
            device_id=data["device_id"],
            name=data["name"],
            model=data["model"],
            device_type=DeviceType(data["device_type"]),
            receiver_connected=data.get("receiver_connected", False),
            device_connected=data.get("device_connected", False),
            battery_percentage=data.get("battery_percentage"),
            charging_status=ChargingStatus(data.get("charging_status", ChargingStatus.UNKNOWN.value)),
            last_reading_time=data.get("last_reading_time"),
            error_message=data.get("error_message"),
        )

    @property
    def formatted_battery(self) -> str:
        if not self.receiver_connected:
            return "No Dongle"
        if not self.device_connected:
            return "Off / Disconnected"
        if self.battery_percentage is not None:
            return f"{self.battery_percentage}%"
        return "Unknown"

    @property
    def is_low_battery(self) -> bool:
        return self.device_connected and self.battery_percentage is not None and self.battery_percentage <= 20

    @property
    def is_critical_battery(self) -> bool:
        return self.device_connected and self.battery_percentage is not None and self.battery_percentage <= 10
