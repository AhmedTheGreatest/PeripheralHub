"""Desktop Notification Service for PeripheralHub.

Handles battery warning notifications via notify-send with deduplication
to prevent repeated notifications for the same battery event.
"""

from __future__ import annotations
import subprocess
import shutil
import logging
from typing import Dict, Optional
from .battery import DeviceState, ChargingStatus

logger = logging.getLogger("peripheralhub")


class NotificationManager:
    """Manages desktop notifications for battery thresholds with deduplication."""

    def __init__(self):
        self._notify_send_bin: Optional[str] = shutil.which("notify-send")
        # Stores last notified threshold per device: None, "low" (20%), "critical" (10%), "full" (100%)
        self._last_alert_state: Dict[str, Optional[str]] = {}

    def send_notification(self, title: str, message: str, urgency: str = "normal", icon: str = "battery"):
        """Dispatch desktop notification via notify-send."""
        if not self._notify_send_bin:
            logger.debug(f"notify-send not found on system: {title} - {message}")
            return

        cmd = [
            self._notify_send_bin,
            "-a", "PeripheralHub",
            "-u", urgency,
            "-i", icon,
            title,
            message,
        ]
        try:
            subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.debug(f"Error executing notify-send: {e}")

    def check_and_notify(self, state: DeviceState):
        """Evaluate device state and trigger notification if threshold crossed."""
        if not state.device_connected or state.battery_percentage is None:
            # If device disconnected or unknown, reset notification state
            if not state.device_connected:
                self._last_alert_state[state.device_id] = None
            return

        bat = state.battery_percentage
        last_state = self._last_alert_state.get(state.device_id)

        # Critical battery (<= 10%)
        if bat <= 10:
            if last_state != "critical":
                self.send_notification(
                    title=f"Critical Battery: {state.name}",
                    message=f"Battery is at {bat}%! Please connect the charger immediately.",
                    urgency="critical",
                    icon="battery-caution",
                )
                self._last_alert_state[state.device_id] = "critical"
            return

        # Low battery (<= 20%)
        if bat <= 20:
            if last_state not in ("low", "critical"):
                self.send_notification(
                    title=f"Low Battery: {state.name}",
                    message=f"Battery is at {bat}%. Consider charging soon.",
                    urgency="normal",
                    icon="battery-low",
                )
                self._last_alert_state[state.device_id] = "low"
            return

        # Fully charged (100% or ChargingStatus.FULL)
        if (bat == 100 or state.charging_status == ChargingStatus.FULL) and state.charging_status in (ChargingStatus.CHARGING, ChargingStatus.FULL):
            if last_state != "full":
                self.send_notification(
                    title=f"Fully Charged: {state.name}",
                    message=f"{state.name} is fully charged (100%).",
                    urgency="normal",
                    icon="battery-full-charging",
                )
                self._last_alert_state[state.device_id] = "full"
            return

        # Normal battery (> 20%) - reset alert state so subsequent low transitions trigger again
        if bat > 25:
            self._last_alert_state[state.device_id] = None
