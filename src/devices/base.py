"""Base Peripheral Adapter for PeripheralHub."""

from abc import ABC, abstractmethod
from typing import Optional
import logging
from ..battery import DeviceState, DeviceType, ChargingStatus

logger = logging.getLogger("peripheralhub")


class BasePeripheralAdapter(ABC):
    """Abstract base class for all wireless peripheral hardware adapters."""

    def __init__(self, device_id: str, name: str, model: str, device_type: DeviceType):
        self.device_id = device_id
        self.name = name
        self.model = model
        self.device_type = device_type
        self.last_state: Optional[DeviceState] = None

    @abstractmethod
    def is_receiver_present(self) -> bool:
        """Check if the 2.4 GHz USB receiver is currently plugged into the system."""
        pass

    @abstractmethod
    def poll(self) -> DeviceState:
        """Poll the device for battery percentage and connection status.

        Must return a valid DeviceState object without raising uncaught hardware exceptions.
        """
        pass

    def get_fallback_state(self, receiver_present: bool = False, error: Optional[str] = None) -> DeviceState:
        """Return a safe fallback state when communication fails or device is absent."""
        return DeviceState(
            device_id=self.device_id,
            name=self.name,
            model=self.model,
            device_type=self.device_type,
            receiver_connected=receiver_present,
            device_connected=False,
            battery_percentage=None,
            charging_status=ChargingStatus.UNKNOWN,
            error_message=error,
        )
