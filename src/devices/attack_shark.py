"""Attack Shark X11 Wireless Mouse Adapter.

Communicates with the Attack Shark X11 2.4 GHz wireless receiver (1d57:fa60)
over USB Interface 2 (vendor configuration endpoint 0x83).
"""

from __future__ import annotations
import time
import logging
from typing import Optional
import usb.core
import usb.util

from .base import BasePeripheralAdapter
from ..battery import DeviceState, DeviceType, ChargingStatus

logger = logging.getLogger("peripheralhub")

VID = 0x1D57
PID_WIRELESS = 0xFA60
PID_WIRED = 0xFA55
INTERFACE_NUM = 2
ENDPOINT_IN = 0x83


class AttackSharkAdapter(BasePeripheralAdapter):
    """Adapter for Attack Shark X11 wireless mouse."""

    def __init__(self):
        super().__init__(
            device_id="attack_shark_x11",
            name="Attack Shark X11",
            model="X11 Wireless Gaming Mouse",
            device_type=DeviceType.MOUSE,
        )
        self._cached_battery: Optional[int] = None
        self._last_reading: Optional[float] = None

    def is_receiver_present(self) -> bool:
        """Check if Attack Shark wireless receiver or wired mouse is plugged in."""
        try:
            dev = usb.core.find(idVendor=VID, idProduct=PID_WIRELESS)
            if dev is not None:
                return True
            wired = usb.core.find(idVendor=VID, idProduct=PID_WIRED)
            return wired is not None
        except Exception as e:
            logger.debug(f"Attack Shark presence check error: {e}")
            return False

    def poll(self) -> DeviceState:
        """Query battery percentage from the 2.4 GHz receiver."""
        try:
            dev = usb.core.find(idVendor=VID, idProduct=PID_WIRELESS)
            if dev is None:
                # Check if connected via wired mode
                wired = usb.core.find(idVendor=VID, idProduct=PID_WIRED)
                if wired is not None:
                    return DeviceState(
                        device_id=self.device_id,
                        name=self.name,
                        model=self.model,
                        device_type=self.device_type,
                        receiver_connected=True,
                        device_connected=True,
                        battery_percentage=None,
                        charging_status=ChargingStatus.CHARGING,
                        last_reading_time=time.time(),
                        error_message="Connected via USB cable (charging/wired)",
                    )
                return self.get_fallback_state(receiver_present=False)

            # Wireless receiver is present
            detached = False
            try:
                if dev.is_kernel_driver_active(INTERFACE_NUM):
                    dev.detach_kernel_driver(INTERFACE_NUM)
                    detached = True
            except usb.core.USBError as e:
                logger.debug(f"Kernel driver detach note on intf {INTERFACE_NUM}: {e}")

            battery = None
            device_connected = False

            try:
                usb.util.claim_interface(dev, INTERFACE_NUM)
                start = time.time()
                while time.time() - start < 1.8:
                    try:
                        data = dev.read(ENDPOINT_IN, 64, timeout=300)
                        if len(data) >= 5 and data[0] == 0x03 and data[1] == 0x55 and data[2] == 0x40 and data[3] == 0x01:
                            val = data[4]
                            if 0 <= val <= 100:
                                battery = val
                                device_connected = True
                                self._cached_battery = battery
                                self._last_reading = time.time()
                                break
                    except usb.core.USBTimeoutError:
                        continue
                    except usb.core.USBError as e:
                        logger.debug(f"USB read error on endpoint {hex(ENDPOINT_IN)}: {e}")
                        break
            finally:
                try:
                    usb.util.release_interface(dev, INTERFACE_NUM)
                except Exception:
                    pass
                if detached:
                    try:
                        dev.attach_kernel_driver(INTERFACE_NUM)
                    except Exception:
                        pass

            if battery is not None:
                return DeviceState(
                    device_id=self.device_id,
                    name=self.name,
                    model=self.model,
                    device_type=self.device_type,
                    receiver_connected=True,
                    device_connected=True,
                    battery_percentage=battery,
                    charging_status=ChargingStatus.DISCHARGING,
                    last_reading_time=self._last_reading,
                )
            else:
                # If cached reading is fresh (within 3 minutes), keep it with device_connected=True
                # because the mouse only sends battery reports when awake/moving.
                now = time.time()
                if self._cached_battery is not None and self._last_reading is not None and (now - self._last_reading) < 180:
                    return DeviceState(
                        device_id=self.device_id,
                        name=self.name,
                        model=self.model,
                        device_type=self.device_type,
                        receiver_connected=True,
                        device_connected=True,
                        battery_percentage=self._cached_battery,
                        charging_status=ChargingStatus.DISCHARGING,
                        last_reading_time=self._last_reading,
                    )

                return DeviceState(
                    device_id=self.device_id,
                    name=self.name,
                    model=self.model,
                    device_type=self.device_type,
                    receiver_connected=True,
                    device_connected=False,
                    battery_percentage=self._cached_battery,
                    charging_status=ChargingStatus.UNKNOWN,
                    last_reading_time=self._last_reading,
                    error_message="Mouse is sleeping or turned off",
                )

        except Exception as e:
            logger.warning(f"Error polling Attack Shark X11: {e}")
            return self.get_fallback_state(receiver_present=True, error=str(e))
