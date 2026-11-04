"""Unit tests for PeripheralHub data models."""

import pytest
from src.battery import DeviceState, DeviceType, ChargingStatus


def test_device_state_serialization():
    state = DeviceState(
        device_id="test_mouse",
        name="Test Mouse",
        model="Model X",
        device_type=DeviceType.MOUSE,
        receiver_connected=True,
        device_connected=True,
        battery_percentage=85,
        charging_status=ChargingStatus.DISCHARGING,
        last_reading_time=1700000000.0,
    )

    d = state.to_dict()
    assert d["device_id"] == "test_mouse"
    assert d["battery_percentage"] == 85
    assert d["device_type"] == "mouse"
    assert d["charging_status"] == "discharging"

    restored = DeviceState.from_dict(d)
    assert restored.device_id == state.device_id
    assert restored.battery_percentage == 85
    assert restored.device_type == DeviceType.MOUSE
    assert restored.charging_status == ChargingStatus.DISCHARGING


def test_formatted_battery():
    # No dongle
    s1 = DeviceState("d1", "N1", "M1", DeviceType.MOUSE, receiver_connected=False)
    assert s1.formatted_battery == "No Dongle"

    # Disconnected device
    s2 = DeviceState("d2", "N2", "M2", DeviceType.MOUSE, receiver_connected=True, device_connected=False)
    assert s2.formatted_battery == "Off / Disconnected"

    # Connected with battery
    s3 = DeviceState("d3", "N3", "M3", DeviceType.MOUSE, receiver_connected=True, device_connected=True, battery_percentage=90)
    assert s3.formatted_battery == "90%"

    # Low battery thresholds
    assert not s3.is_low_battery
    assert not s3.is_critical_battery

    s4 = DeviceState("d4", "N4", "M4", DeviceType.MOUSE, receiver_connected=True, device_connected=True, battery_percentage=15)
    assert s4.is_low_battery
    assert not s4.is_critical_battery

    s5 = DeviceState("d5", "N5", "M5", DeviceType.MOUSE, receiver_connected=True, device_connected=True, battery_percentage=8)
    assert s5.is_low_battery
    assert s5.is_critical_battery
