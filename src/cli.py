"""PeripheralHub Command-Line Interface.

Provides subcommands for Polybar integration, desktop notifications,
status inspection, JSON exports, and background daemon execution.
"""

from __future__ import annotations
import sys
import os
import json
import argparse
import time
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from .battery import DeviceState, ChargingStatus, DeviceType
from .monitor import PeripheralMonitor, get_cache_file
from .notifications import NotificationManager

DEFAULT_CONFIG: Dict[str, Any] = {
    "poll_interval": 30,
    "separator": " | ",
    "use_colors": True,
    "colors": {
        "normal": "#a6e3a1",      # Green (Catppuccin Mocha)
        "low": "#fab387",         # Peach/Orange (< 20%)
        "critical": "#f38ba8",    # Red (< 10%)
        "charging": "#89b4fa",    # Blue
        "disconnected": "#9399b2" # Muted gray
    },
    "icons": {
        "mouse": "󰍽",
        "keyboard": "󰌌",
        "headset": "󰋋",
        "charging": "󱐋",
        "disconnected": "off"
    }
}


def get_user_config() -> Dict[str, Any]:
    """Load configuration from ~/.config/peripheralhub/config.json with defaults."""
    cfg_path = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "peripheralhub" / "config.json"
    config = dict(DEFAULT_CONFIG)
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                config.update(user_cfg)
        except Exception:
            pass
    return config


def format_device_polybar(state: DeviceState, config: Dict[str, Any], plain: bool = False) -> str:
    """Format single device status for Polybar using colors and Nerd Font icons."""
    icons = config.get("icons", DEFAULT_CONFIG["icons"])
    colors = config.get("colors", DEFAULT_CONFIG["colors"])

    dev_icon = icons.get(state.device_type.value, "󰋋")
    charging_icon = icons.get("charging", "󱐋")

    if not state.receiver_connected:
        text = f"{dev_icon} -"
        return text if plain else f"%{{F{colors['disconnected']}}}{text}%{{F-}}"

    if not state.device_connected:
        off_text = icons.get("disconnected", "off")
        text = f"{dev_icon} {off_text}"
        return text if plain else f"%{{F{colors['disconnected']}}}{text}%{{F-}}"

    bat = state.battery_percentage
    if bat is None:
        text = f"{dev_icon} ?"
        return text if plain else f"%{{F{colors['disconnected']}}}{text}%{{F-}}"

    is_charging = state.charging_status in (ChargingStatus.CHARGING, ChargingStatus.FULL)
    charge_suffix = f"{charging_icon}" if is_charging else ""
    text = f"{dev_icon} {bat}%{charge_suffix}"

    if plain:
        return text

    if is_charging:
        color = colors.get("charging", "#89b4fa")
    elif bat <= 10:
        color = colors.get("critical", "#f38ba8")
    elif bat <= 20:
        color = colors.get("low", "#fab387")
    else:
        color = colors.get("normal", "#a6e3a1")

    return f"%{{F{color}}}{text}%{{F-}}"


def cmd_status(args, config: Dict[str, Any]):
    """Output single-line string for Polybar."""
    states = PeripheralMonitor.load_cached_states()
    if states is None:
        # If cache is missing, do an immediate hardware poll
        monitor = PeripheralMonitor()
        states = monitor.poll_all()

    order = ["attack_shark_x11", "aula_f75", "razer_barracuda_x"]
    parts = []
    plain = args.plain or not config.get("use_colors", True)

    for dev_id in order:
        state = states.get(dev_id)
        if state:
            parts.append(format_device_polybar(state, config, plain=plain))

    sep = args.separator if args.separator is not None else config.get("separator", " | ")
    print(sep.join(parts))


def cmd_details(args, config: Dict[str, Any]):
    """Display detailed peripheral information in terminal and/or desktop notification."""
    states = PeripheralMonitor.load_cached_states()
    if states is None:
        monitor = PeripheralMonitor()
        states = monitor.poll_all()

    lines = []
    lines.append("PeripheralHub — Device Status")
    lines.append("=" * 45)

    order = ["attack_shark_x11", "aula_f75", "razer_barracuda_x"]
    for dev_id in order:
        st = states.get(dev_id)
        if not st:
            continue
        lines.append(f"Device: {st.name} ({st.model})")
        lines.append(f"  Type:          {st.device_type.value.capitalize()}")
        lines.append(f"  Dongle:        {'Connected' if st.receiver_connected else 'Missing'}")
        lines.append(f"  Device Link:   {'Connected' if st.device_connected else 'Disconnected / Asleep'}")
        lines.append(f"  Battery:       {st.formatted_battery}")
        lines.append(f"  Charging:      {st.charging_status.value.capitalize()}")
        if st.last_reading_time:
            dt = datetime.datetime.fromtimestamp(st.last_reading_time).strftime('%Y-%m-%d %H:%M:%S')
            lines.append(f"  Last Reading:  {dt}")
        if st.error_message:
            lines.append(f"  Note:          {st.error_message}")
        lines.append("-" * 45)

    output = "\n".join(lines)
    print(output)

    # If --notify flag or run from GUI without interactive terminal, dispatch desktop notification
    if args.notify or not sys.stdout.isatty():
        notif_lines = []
        for dev_id in order:
            st = states.get(dev_id)
            if not st:
                continue
            icon = "󰍽" if st.device_type == DeviceType.MOUSE else "󰌌" if st.device_type == DeviceType.KEYBOARD else "󰋋"
            notif_lines.append(f"{icon} {st.name}: {st.formatted_battery} ({st.charging_status.value})")

        notif_msg = "\n".join(notif_lines)
        notif = NotificationManager()
        notif.send_notification("PeripheralHub Status", notif_msg, urgency="normal", icon="devices")


def cmd_json(args, config: Dict[str, Any]):
    """Output machine-readable JSON."""
    states = PeripheralMonitor.load_cached_states()
    if states is None or args.fresh:
        monitor = PeripheralMonitor()
        states = monitor.poll_all()

    out = {dev_id: state.to_dict() for dev_id, state in states.items()}
    print(json.dumps(out, indent=2 if args.pretty else None))


def cmd_poll_once(args, config: Dict[str, Any]):
    """Perform immediate hardware poll and update cache."""
    monitor = PeripheralMonitor()
    states = monitor.poll_all()
    print(f"Polled {len(states)} devices. Cache updated at {get_cache_file()}")
    for dev_id, st in states.items():
        print(f"  - {st.name}: {st.formatted_battery} ({st.charging_status.value})")


def cmd_daemon(args, config: Dict[str, Any]):
    """Run monitoring daemon process."""
    interval = args.interval or config.get("poll_interval", 30)
    monitor = PeripheralMonitor()
    monitor.run_daemon(interval=interval)


def main():
    config = get_user_config()
    parser = argparse.ArgumentParser(
        prog="peripheralhub",
        description="Unified Linux Peripheral Battery Monitor for Polybar & i3",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # status
    p_status = subparsers.add_parser("status", help="Output single-line string for Polybar")
    p_status.add_argument("--plain", action="store_true", help="Omit Polybar formatting color tags")
    p_status.add_argument("--separator", type=str, default=None, help="Custom delimiter between devices")

    # details
    p_details = subparsers.add_parser("details", help="Show detailed status of all devices")
    p_details.add_argument("--notify", action="store_true", help="Send desktop notification with details")

    # json
    p_json = subparsers.add_parser("json", help="Export full device states as JSON")
    p_json.add_argument("--pretty", action="store_true", help="Pretty print JSON output")
    p_json.add_argument("--fresh", action="store_true", help="Poll hardware directly instead of reading cache")

    # poll-once
    subparsers.add_parser("poll-once", help="Poll devices once and update cache")

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="Run background monitoring service")
    p_daemon.add_argument("--interval", type=int, default=None, help="Polling interval in seconds (default: 30)")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args, config)
    elif args.command == "details":
        cmd_details(args, config)
    elif args.command == "json":
        cmd_json(args, config)
    elif args.command == "poll-once":
        cmd_poll_once(args, config)
    elif args.command == "daemon":
        cmd_daemon(args, config)
    else:
        # Default action when run without arguments is status
        cmd_status(argparse.Namespace(plain=False, separator=None), config)


if __name__ == "__main__":
    main()
