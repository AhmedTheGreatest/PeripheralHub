"""AULA F75 Wireless Keyboard Adapter.

Communicates with the AULA F75 2.4 GHz wireless receiver (3554:fa09)
over the secondary HID composite interface (input1 / hidraw) using Report ID 0x13.
"""

from __future__ import annotations
import os
import select
import time
import logging
from typing import Optional, Tuple
from pathlib import Path

from .base import BasePeripheralAdapter
from ..battery import DeviceState, DeviceType, ChargingStatus

logger = logging.getLogger("peripheralhub")

VID_WIRELESS = "3554"
PID_WIRELESS = "FA09"
VID_WIRED = "258A"
PID_WIRED = "010C"
CMD_GET_PSD = 0x05
REPORT_ID = 0x13
PACKET_SIZE = 20


class AulaF75Adapter(BasePeripheralAdapter):
    """Adapter for AULA F75 wireless mechanical keyboard."""

    def __init__(self):
        super().__init__(
            device_id="aula_f75",
            name="AULA F75",
            model="F75 Mechanical Keyboard",
            device_type=DeviceType.KEYBOARD,
        )
        self._cached_battery: Optional[int] = None
        self._last_reading: Optional[float] = None

    def _find_hidraw_path(self) -> Tuple[Optional[str], bool]:
        """Find the hidraw device path for the AULA keyboard.

        Returns (path, is_wireless).
        """
        sysfs_hidraw = Path("/sys/class/hidraw")
        if not sysfs_hidraw.exists():
            return None, False

        for node in sorted(sysfs_hidraw.glob("hidraw*")):
            uevent_path = node / "device" / "uevent"
            if not uevent_path.exists():
                continue
            try:
                uevent = uevent_path.read_text().upper()
                if VID_WIRELESS in uevent and PID_WIRELESS in uevent and "INPUT1" in uevent:
                    dev_path = f"/dev/{node.name}"
                    if os.path.exists(dev_path):
                        return dev_path, True
                elif VID_WIRED in uevent and PID_WIRED in uevent and "INPUT1" in uevent:
                    dev_path = f"/dev/{node.name}"
                    if os.path.exists(dev_path):
                        return dev_path, False
            except Exception as e:
                logger.debug(f"Error checking sysfs node {node}: {e}")
                continue

        return None, False

    def is_receiver_present(self) -> bool:
        """Check if AULA USB receiver or wired keyboard is connected."""
        path, _ = self._find_hidraw_path()
        return path is not None

    def poll(self) -> DeviceState:
        """Query battery percentage from the AULA F75."""
        path, is_wireless = self._find_hidraw_path()
        if not path:
            return self.get_fallback_state(receiver_present=False)

        if not is_wireless:
            # Connected via wired cable
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
                error_message="Connected via USB cable (wired)",
            )

        fd = None
        try:
            fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)

            # Drain any buffered packets
            while True:
                r, _, _ = select.select([fd], [], [], 0.02)
                if r:
                    try:
                        os.read(fd, 64)
                    except OSError:
                        break
                else:
                    break

            # Send CMD_GET_PSD (0x05) on Report ID 0x13
            req = bytearray(PACKET_SIZE)
            req[0] = REPORT_ID
            req[1] = CMD_GET_PSD
            os.write(fd, bytes(req))

            battery = None
            device_connected = False
            start = time.time()

            # Read response frames within 1.0 second
            while time.time() - start < 1.0:
                r, _, _ = select.select([fd], [], [], 0.05)
                if r:
                    try:
                        resp = os.read(fd, 64)
                        # Packet CMD 0x0A or 0x0B contains FW and battery
                        if len(resp) >= 8 and resp[0] == REPORT_ID and (resp[1] == 0x0A or resp[1] == 0x0B):
                            val = resp[6]
                            extra = resp[7]
                            # extra byte == 0x01 indicates wireless active
                            if 0 <= val <= 100:
                                battery = val
                                device_connected = (extra == 0x01) or (val > 0)
                                self._cached_battery = battery
                                self._last_reading = time.time()
                                break
                    except OSError as e:
                        logger.debug(f"AULA read error: {e}")
                        break

            if battery is not None and device_connected:
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
                now = time.time()
                # Keep cached battery if fresh within 5 minutes
                if self._cached_battery is not None and self._last_reading is not None and (now - self._last_reading) < 300:
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
                    error_message="Keyboard is sleeping or turned off",
                )

        except Exception as e:
            logger.warning(f"Error communicating with AULA F75 on {path}: {e}")
            return self.get_fallback_state(receiver_present=True, error=str(e))
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except Exception:
                    pass
