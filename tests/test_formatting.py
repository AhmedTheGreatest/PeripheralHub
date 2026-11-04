"""Unit tests for Polybar output formatting."""

import pytest
from src.battery import DeviceState, DeviceType, ChargingStatus
from src.cli import format_device_polybar, DEFAULT_CONFIG


def test_format_polybar_connected_normal():
    state = DeviceState(
        device_id="mouse",
        name="Mouse",
        model="M",
        device_type=DeviceType.MOUSE,
        receiver_connected=True,
        device_connected=True,
        battery_percentage=85,
        charging_status=ChargingStatus.DISCHARGING,
    )

    out = format_device_polybar(state, DEFAULT_CONFIG, plain=False)
    assert "%{F#a6e3a1}󰍽 85%%{F-}" in out

    plain_out = format_device_polybar(state, DEFAULT_CONFIG, plain=True)
    assert plain_out == "󰍽 85%"


def test_format_polybar_low_and_critical():
    low_state = DeviceState(
        device_id="kb",
        name="Keyboard",
        model="K",
        device_type=DeviceType.KEYBOARD,
        receiver_connected=True,
        device_connected=True,
        battery_percentage=15,
        charging_status=ChargingStatus.DISCHARGING,
    )
    out_low = format_device_polybar(low_state, DEFAULT_CONFIG, plain=False)
    assert "%{F#fab387}󰌌 15%%{F-}" in out_low

    crit_state = DeviceState(
        device_id="headset",
        name="Headset",
        model="H",
        device_type=DeviceType.HEADSET,
        receiver_connected=True,
        device_connected=True,
        battery_percentage=8,
        charging_status=ChargingStatus.DISCHARGING,
    )
    out_crit = format_device_polybar(crit_state, DEFAULT_CONFIG, plain=False)
    assert "%{F#f38ba8}󰋋 8%%{F-}" in out_crit


def test_format_polybar_charging():
    charge_state = DeviceState(
        device_id="mouse",
        name="Mouse",
        model="M",
        device_type=DeviceType.MOUSE,
        receiver_connected=True,
        device_connected=True,
        battery_percentage=50,
        charging_status=ChargingStatus.CHARGING,
    )
    out_charge = format_device_polybar(charge_state, DEFAULT_CONFIG, plain=False)
    assert "%{F#89b4fa}󰍽 50%󱐋%{F-}" in out_charge


def test_format_polybar_disconnected():
    disc_state = DeviceState(
        device_id="headset",
        name="Headset",
        model="H",
        device_type=DeviceType.HEADSET,
        receiver_connected=True,
        device_connected=False,
    )
    out_disc = format_device_polybar(disc_state, DEFAULT_CONFIG, plain=False)
    assert "%{F#9399b2}󰋋 off%{F-}" in out_disc
