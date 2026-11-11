"""AULA F75 Wireless Keyboard Adapter.

Communicates with the AULA F75 2.4 GHz wireless receiver (3554:fa09)
over the secondary HID composite interface (input1 / hidraw) using Report ID 0x13.
Monitors keystroke activity on the primary interface (input0 / hidraw)
to guard keyboard sleep and avoid waking the device with unnecessary RF traffic.
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
    """Adapter for AULA F75 wireless mechanical keyboard with sleep-guarding."""

    def __init__(self, query_interval: int = 600, idle_threshold: int = 45, sleep_threshold: int = 90):
        super().__init__(
            device_id="aula_f75",
            name="AULA F75",
            model="F75 Mechanical Keyboard",
            device_type=DeviceType.KEYBOARD,
        )
        self.query_interval = query_interval
        self.idle_threshold = idle_threshold
        self.sleep_threshold = sleep_threshold
        self._cached_battery: Optional[int] = None
        self._last_reading: Optional[float] = None
        self._last_activity_time: Optional[float] = None
        self._kbd_fd: Optional[int] = None
        self._kbd_path: Optional[str] = None

    def _find_hidraw_path(self, interface: str = "INPUT1") -> Tuple[Optional[str], bool]:
        """Find the hidraw device path for the AULA keyboard.

        interface: 'INPUT0' for keyboard reports, 'INPUT1' for vendor composite.
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
                if VID_WIRELESS in uevent and PID_WIRELESS in uevent and interface in uevent:
                    dev_path = f"/dev/{node.name}"
                    if os.path.exists(dev_path):
                        return dev_path, True
                elif VID_WIRED in uevent and PID_WIRED in uevent and interface in uevent:
                    dev_path = f"/dev/{node.name}"
                    if os.path.exists(dev_path):
                        return dev_path, False
            except Exception as e:
                logger.debug(f"Error checking sysfs node {node}: {e}")
                continue

        return None, False

    def is_receiver_present(self) -> bool:
        """Check if AULA USB receiver or wired keyboard is connected."""
        path, _ = self._find_hidraw_path("INPUT1")
        return path is not None

    def _close_kbd_listener(self):
        """Close open file descriptor for keyboard event listener."""
        if self._kbd_fd is not None:
            try:
                os.close(self._kbd_fd)
            except Exception as e:
                logger.debug(f"Error closing kbd listener fd {self._kbd_fd}: {e}")
            self._kbd_fd = None
            self._kbd_path = None

    def __del__(self):
        self._close_kbd_listener()

    def _ensure_kbd_listener(self) -> Optional[int]:
        """Ensure input0 hidraw is open for non-blocking keystroke listening."""
        path, is_wireless = self._find_hidraw_path(interface="INPUT0")
        if not path or not is_wireless:
            self._close_kbd_listener()
            return None

        if self._kbd_fd is not None and self._kbd_path == path:
            return self._kbd_fd

        self._close_kbd_listener()
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            self._kbd_fd = fd
            self._kbd_path = path
            return fd
        except Exception as e:
            logger.debug(f"Could not open kbd listener on {path}: {e}")
            self._kbd_fd = None
            self._kbd_path = None
            return None

    def _check_activity(self) -> Tuple[bool, bool]:
        """Check if keystrokes were typed recently.

        Returns (is_active, is_asleep).
        is_active: True if typed within idle_threshold (default 45s).
        is_asleep: True if no keystrokes for sleep_threshold (default 90s).
        """
        fd = self._ensure_kbd_listener()
        now = time.time()
        typed_now = False

        if fd is not None:
            # Drain any buffered keystrokes from hidraw ring buffer
            while True:
                try:
                    r, _, _ = select.select([fd], [], [], 0)
                    if r:
                        os.read(fd, 64)
                        typed_now = True
                    else:
                        break
                except OSError:
                    self._close_kbd_listener()
                    break

        if typed_now:
            self._last_activity_time = now

        if self._last_activity_time is None:
            return False, False

        idle_time = now - self._last_activity_time
        is_active = idle_time < self.idle_threshold
        is_asleep = idle_time >= self.sleep_threshold

        return is_active, is_asleep

    def _send_query(self, path: str) -> Tuple[Optional[int], bool]:
        """Send CMD_GET_PSD over RF and wait for response.

        Returns (battery_percentage, device_connected).
        """
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
                                self._last_activity_time = time.time()
                                break
                    except OSError as e:
                        logger.debug(f"AULA read error: {e}")
                        break

            return battery, device_connected
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except Exception:
                    pass

    def poll(self, force: bool = False) -> DeviceState:
        """Query battery percentage from the AULA F75 with activity-aware idle guard."""
        path, is_wireless = self._find_hidraw_path("INPUT1")
        if not path:
            self._close_kbd_listener()
            return self.get_fallback_state(receiver_present=False)

        if not is_wireless:
            # Connected via wired cable
            self._close_kbd_listener()
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

        now = time.time()
        is_active, is_asleep = self._check_activity()

        # Decide whether an active over-the-air RF query is needed
        should_query = False
        if force:
            should_query = True
        elif self._cached_battery is None:
            # Initial poll on daemon/system startup
            should_query = True
        elif is_active:
            # Query only if the throttled query interval has passed
            if self._last_reading is None or (now - self._last_reading) >= self.query_interval:
                should_query = True

        if should_query:
            try:
                battery, connected = self._send_query(path)
                if battery is not None and connected:
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
                    # Query timed out (turned off, out of range, or unreachably asleep)
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

        # We are skipping the RF query to let the keyboard sleep or preserve its timer
        if is_asleep:
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
                error_message="Keyboard is sleeping or idle",
            )

        # Active or transitioning to sleep: return cached state with device_connected=True
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
