"""Razer Barracuda X (2022) Wireless Headset Adapter.

Communicates with the Razer Barracuda X 2.4 GHz USB dongle (1532:0552)
over HID report 1 on the dongle's hidraw interface.
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

VID = "1532"
PID = "0552"
REPORT_SIZE = 64
CLASS_LINK = 0x0E
CLASS_CUSTOMER = 0x08
CMD_GET_LINK = 0xE3
CMD_SET_ROUTE = 0xE1
PARAM_BATTERY = 0x21
PARAM_CABLE = 0x2A


class RazerBarracudaAdapter(BasePeripheralAdapter):
    """Adapter for Razer Barracuda X (2022) 2.4 GHz wireless headset."""

    def __init__(self):
        super().__init__(
            device_id="razer_barracuda_x",
            name="Razer Barracuda X",
            model="Barracuda X (2022)",
            device_type=DeviceType.HEADSET,
        )
        self._cached_battery: Optional[int] = None
        self._cached_charging: ChargingStatus = ChargingStatus.UNKNOWN
        self._last_reading: Optional[float] = None
        self._seq: int = 0x20

    def _next_seq(self) -> int:
        self._seq = (self._seq % 0x7E) + 1
        return self._seq

    def _find_hidraw_path(self) -> Optional[str]:
        """Find the hidraw device path for the Barracuda X dongle."""
        sysfs_hidraw = Path("/sys/class/hidraw")
        if not sysfs_hidraw.exists():
            return None

        for node in sorted(sysfs_hidraw.glob("hidraw*")):
            uevent_path = node / "device" / "uevent"
            if not uevent_path.exists():
                continue
            try:
                uevent = uevent_path.read_text().upper()
                if VID in uevent and PID in uevent:
                    dev_path = f"/dev/{node.name}"
                    if os.path.exists(dev_path):
                        return dev_path
            except Exception as e:
                logger.debug(f"Error checking sysfs node {node}: {e}")
                continue

        return None

    def is_receiver_present(self) -> bool:
        """Check if Razer Barracuda X 2.4 GHz dongle is plugged in."""
        return self._find_hidraw_path() is not None

    def _build_report(self, klass: int, seq: int, command: int, *args: int) -> bytes:
        """Build standard 64-byte framed report for the Barracuda dongle."""
        frame = b"PA" + bytes([klass, seq, len(args) + 1, command, *args])
        if len(frame) > REPORT_SIZE - 3:
            raise ValueError("Frame too long")
        return bytes([0x01, 0x80, len(frame)]) + frame.ljust(REPORT_SIZE - 3, b"\x00")

    def poll(self) -> DeviceState:
        """Poll the Barracuda X dongle for link status, battery, and charging cable."""
        path = self._find_hidraw_path()
        if not path:
            return self.get_fallback_state(receiver_present=False)

        fd = None
        try:
            fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)

            # Drain old reports
            while True:
                r, _, _ = select.select([fd], [], [], 0.02)
                if r:
                    try:
                        os.read(fd, REPORT_SIZE)
                    except OSError:
                        break
                else:
                    break

            # 1. Query Link Status (CMD 0xE3)
            seq = self._next_seq()
            req = self._build_report(CLASS_LINK, seq, CMD_GET_LINK)
            os.write(fd, req)

            link_status: Optional[bool] = None
            start = time.time()

            while time.time() - start < 1.0:
                r, _, _ = select.select([fd], [], [], 0.05)
                if r:
                    try:
                        resp = os.read(fd, REPORT_SIZE)
                        # Check for E3 reply
                        if len(resp) >= 15 and resp[3:5] == b"PI" and resp[5] == CLASS_LINK:
                            for i in range(len(resp) - 3):
                                if resp[i:i + 3] == bytes([0x02, 0x00, CMD_GET_LINK]):
                                    link_status = bool(resp[i + 3])
                                    break
                        # Also check unsolicited transition report
                        if len(resp) >= 17 and resp[3:5] == b"PI" and resp[11:16] == bytes([0x04, 0x00, 0x20, 0x02, 0x01]):
                            link_status = bool(resp[16])
                            break
                    except OSError:
                        break
                if link_status is not None:
                    break

            if link_status is not True:
                # Disconnected or link status unconfirmed
                now = time.time()
                # Retain cached battery if read recently, but mark device disconnected
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
                    error_message="Headset is disconnected or powered off",
                )

            # 2. Link is active! Query battery and charging cable
            battery = self._cached_battery
            charging = self._cached_charging
            route_selected = False

            try:
                # Set route to remote headset (0x01)
                seq = self._next_seq()
                route_req = self._build_report(CLASS_LINK, seq, CMD_SET_ROUTE, 0x01)
                os.write(fd, route_req)
                route_selected = True

                # Small delay for route setup
                time.sleep(0.05)

                # Query battery: Customer family 0x08, param 0x21
                seq = self._next_seq()
                bat_req = self._build_report(CLASS_CUSTOMER, seq, PARAM_BATTERY, 0x00, 0x00)
                os.write(fd, bat_req)

                bat_deadline = time.time() + 1.0
                while time.time() < bat_deadline:
                    r, _, _ = select.select([fd], [], [], 0.05)
                    if r:
                        try:
                            resp = os.read(fd, REPORT_SIZE)
                            # Parse customer reply: [21 01 01 VV] or report [21 02 01 VV]
                            for i in range(len(resp) - 3):
                                if resp[i] == PARAM_BATTERY and (resp[i + 1] in (0x01, 0x02)) and resp[i + 2] == 0x01:
                                    val = resp[i + 3]
                                    if 0 <= val <= 100:
                                        battery = val
                                        self._cached_battery = val
                                        self._last_reading = time.time()
                                        break
                        except OSError:
                            break
                    if battery is not None:
                        break

                # Query cable: Customer family 0x08, param 0x2A
                seq = self._next_seq()
                cable_req = self._build_report(CLASS_CUSTOMER, seq, PARAM_CABLE, 0x00, 0x00)
                os.write(fd, cable_req)

                cable_deadline = time.time() + 0.8
                while time.time() < cable_deadline:
                    r, _, _ = select.select([fd], [], [], 0.05)
                    if r:
                        try:
                            resp = os.read(fd, REPORT_SIZE)
                            for i in range(len(resp) - 3):
                                if resp[i] == PARAM_CABLE and (resp[i + 1] in (0x01, 0x02)) and resp[i + 2] == 0x01:
                                    cable_val = resp[i + 3]
                                    if cable_val == 0x01:
                                        charging = ChargingStatus.CHARGING
                                    elif cable_val == 0x00:
                                        charging = ChargingStatus.DISCHARGING
                                    self._cached_charging = charging
                                    break
                        except OSError:
                            break
                    if charging != ChargingStatus.UNKNOWN:
                        break

            finally:
                # 3. Always restore local diagnostic route (0x00)
                if route_selected:
                    try:
                        seq = self._next_seq()
                        restore_req = self._build_report(CLASS_LINK, seq, CMD_SET_ROUTE, 0x00)
                        os.write(fd, restore_req)
                        time.sleep(0.02)
                    except Exception as e:
                        logger.warning(f"Failed to restore local route on Barracuda: {e}")

            return DeviceState(
                device_id=self.device_id,
                name=self.name,
                model=self.model,
                device_type=self.device_type,
                receiver_connected=True,
                device_connected=True,
                battery_percentage=battery,
                charging_status=charging,
                last_reading_time=self._last_reading or time.time(),
            )

        except Exception as e:
            logger.warning(f"Error communicating with Razer Barracuda X on {path}: {e}")
            return self.get_fallback_state(receiver_present=True, error=str(e))
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except Exception:
                    pass
