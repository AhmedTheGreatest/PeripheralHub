"""Unit tests for notification deduplication logic."""

from unittest.mock import MagicMock
from src.battery import DeviceState, DeviceType, ChargingStatus
from src.notifications import NotificationManager


def test_notification_deduplication():
    manager = NotificationManager()
    manager.send_notification = MagicMock()

    mouse = DeviceState(
        device_id="mouse",
        name="Mouse",
        model="M",
        device_type=DeviceType.MOUSE,
        receiver_connected=True,
        device_connected=True,
        battery_percentage=19,
    )

    # 1. First trigger at 19% (Low)
    manager.check_and_notify(mouse)
    assert manager.send_notification.call_count == 1
    kwargs = manager.send_notification.call_args.kwargs
    assert kwargs["urgency"] == "normal"
    assert "Low Battery" in kwargs["title"]

    # 2. Subsequent check at 18% should NOT trigger again
    mouse.battery_percentage = 18
    manager.check_and_notify(mouse)
    assert manager.send_notification.call_count == 1

    # 3. Transition into Critical (<= 10%) should trigger
    mouse.battery_percentage = 9
    manager.check_and_notify(mouse)
    assert manager.send_notification.call_count == 2
    kwargs_crit = manager.send_notification.call_args.kwargs
    assert kwargs_crit["urgency"] == "critical"
    assert "Critical Battery" in kwargs_crit["title"]

    # 4. Another poll at 8% should NOT repeat critical
    mouse.battery_percentage = 8
    manager.check_and_notify(mouse)
    assert manager.send_notification.call_count == 2

    # 5. Charged back up to 50% resets state
    mouse.battery_percentage = 50
    manager.check_and_notify(mouse)
    assert manager.send_notification.call_count == 2

    # 6. Dropping back to 19% triggers low alert again
    mouse.battery_percentage = 19
    manager.check_and_notify(mouse)
    assert manager.send_notification.call_count == 3
