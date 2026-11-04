# PeripheralHub — Unified Linux Peripheral Battery Monitor

A lightweight Linux peripheral battery monitoring service and Polybar status module specifically engineered for **Xubuntu 24.04 + i3wm + Polybar**.

Provides real-time battery percentages, charging indicators, and low-battery alerts for wireless mice, keyboards, and headsets connected over proprietary 2.4 GHz USB wireless receivers.

---

## Supported Hardware

| Peripheral | Model | USB Receiver VID:PID | Connection Mode | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Mouse** | **Attack Shark X11** | `1d57:fa60` (Wired: `1d57:fa55`) | 2.4 GHz USB Dongle | ✅ Fully Supported (EP 0x83) |
| **Keyboard** | **AULA F75** | `3554:fa09` (Wired: `258a:010c`) | 2.4 GHz USB Dongle | ✅ Fully Supported (Report 0x13) |
| **Headphones** | **Razer Barracuda X (2022)** | `1532:0552` | 2.4 GHz USB-C Dongle | ✅ Fully Supported (Report 0x01) |

> [!NOTE]
> All battery readings are queried directly from physical hardware without mock or fabricated values. If a device is turned off, asleep, or disconnected, the module accurately reflects its state as `off` or `-`.

---

## Features

- **Lightweight & Fast**: CLI queries read from a local JSON cache (`~/.cache/peripheralhub/state.json`) in `< 1ms` with near-zero CPU and memory usage.
- **Polybar Integration**: Ready-to-use single-line status formatted with Catppuccin Mocha colors and Nerd Font icons.
- **Intelligent Low-Battery Desktop Notifications**:
  - Low battery alert when dropping below `20%`.
  - Critical warning when dropping below `10%`.
  - Fully charged alert upon reaching `100%`.
  - Deduplicated state machine to prevent notification spamming.
- **Independent Hardware Adapters**: Each device is isolated in its own backend module (`src/devices/`).
- **Non-Root Operation**: Uses narrowly scoped udev rules (`/etc/udev/rules.d/99-peripheralhub.rules`) so users never need `sudo` or root privileges to monitor peripherals.
- **Zero Input Interference**: Does not interfere with standard mouse movement, keyboard typing, or headset audio.

---

## Architecture Overview

```
PeripheralBattery/
├── config/
│   ├── config.json                     # User configuration (colors, icons, thresholds)
│   ├── polybar/
│   │   └── peripheralhub.ini           # Ready-to-use Polybar module snippet
│   ├── udev/
│   │   └── 99-peripheralhub.rules      # Non-root USB & hidraw permission rules
│   └── systemd/
│       └── peripheralhub.service       # User systemd service unit
├── scripts/
│   ├── install.sh                      # Automated installer
│   ├── uninstall.sh                    # Clean uninstallation script
│   └── peripheralhub-status.sh         # Shell wrapper
├── src/
│   ├── battery.py                      # DeviceState data models and enums
│   ├── monitor.py                      # Monitoring engine, caching, and daemon loop
│   ├── notifications.py                # Desktop notification manager
│   ├── cli.py                          # CLI entrypoints (status, details, json, etc.)
│   └── devices/
│       ├── base.py                     # BasePeripheralAdapter abstract interface
│       ├── attack_shark.py             # Attack Shark X11 adapter (pyusb interface 2)
│       ├── aula_f75.py                 # AULA F75 adapter (hidraw report 0x13)
│       └── razer_barracuda.py          # Razer Barracuda X adapter (hidraw report 0x01)
└── tests/                              # Pytest test suite
```

---

## Quick Installation

Run the automated installer:

```bash
cd ~/Dev/PeripheralBattery
./scripts/install.sh
```

The script will:
1. Create a Python virtual environment at `~/.local/share/peripheralhub-venv`.
2. Install Python dependencies (`pyusb`, `hidapi`).
3. Set up the `~/.local/bin/peripheralhub` executable in your `$PATH`.
4. Install and reload the udev rules to enable non-root hardware access.
5. Enable and start the background systemd service (`systemctl --user enable --now peripheralhub.service`).

---

## Polybar Setup

### 1. Include the Module

Open your Polybar configuration file (typically `~/.config/polybar/config.ini`):

```ini
include-file = ~/Dev/PeripheralBattery/config/polybar/peripheralhub.ini
```

Or copy the snippet directly:

```ini
[module/peripheralhub]
type = custom/script
exec = ~/.local/bin/peripheralhub status
interval = 5
click-left = ~/.local/bin/peripheralhub details
click-right = ~/.local/bin/peripheralhub poll-once
format = <label>
label = %output%
format-foreground = ${colors.foreground}
```

### 2. Add to Bar Modules

Add `peripheralhub` to your bar's module list (e.g. `modules-right`):

```ini
modules-right = peripheralhub pulseaudio wlan date
```

### 3. Reload Polybar

Restart Polybar:

```bash
~/.config/polybar/launch.sh
```

---

## CLI Usage

### Check Status (Polybar Format)
```bash
peripheralhub status
```
Output:
```text
%{F#a6e3a1}󰍽 89%%{F-} | %{F#a6e3a1}󰌌 100%%{F-} | %{F#9399b2}󰋋 off%{F-}
```

### Plain Text Output (No Colors)
```bash
peripheralhub status --plain
```
Output:
```text
󰍽 89% | 󰌌 100% | 󰋋 off
```

### Device Details & Overview
```bash
peripheralhub details
```
Output:
```text
PeripheralHub — Device Status
=============================================
Device: Attack Shark X11 (X11 Wireless Gaming Mouse)
  Type:          Mouse
  Dongle:        Connected
  Device Link:   Connected
  Battery:       89%
  Charging:      Discharging
  Last Reading:  2026-11-04 19:14:00
---------------------------------------------
Device: AULA F75 (F75 Mechanical Keyboard)
  Type:          Keyboard
  Dongle:        Connected
  Device Link:   Connected
  Battery:       100%
  Charging:      Discharging
  Last Reading:  2026-11-04 19:14:00
---------------------------------------------
Device: Razer Barracuda X (Barracuda X (2022))
  Type:          Headset
  Dongle:        Connected
  Device Link:   Disconnected / Asleep
  Battery:       Off / Disconnected
  Charging:      Unknown
  Note:          Headset is disconnected or powered off
---------------------------------------------
```

### Export JSON
```bash
peripheralhub json --pretty
```

### Trigger Desktop Notification
```bash
peripheralhub details --notify
```

### Force Immediate Poll
```bash
peripheralhub poll-once
```

---

## Configuration

Custom configuration is located at `~/.config/peripheralhub/config.json`:

```json
{
  "poll_interval": 30,
  "separator": " | ",
  "use_colors": true,
  "colors": {
    "normal": "#a6e3a1",
    "low": "#fab387",
    "critical": "#f38ba8",
    "charging": "#89b4fa",
    "disconnected": "#9399b2"
  },
  "icons": {
    "mouse": "󰍽",
    "keyboard": "󰌌",
    "headset": "󰋋",
    "charging": "󱐋",
    "disconnected": "off"
  }
}
```

---

## Systemd Service Management

View service status:
```bash
systemctl --user status peripheralhub.service
```

View live daemon logs:
```bash
journalctl --user -fu peripheralhub.service
```

Restart service:
```bash
systemctl --user restart peripheralhub.service
```

---

## Running Tests

Run the test suite with pytest:

```bash
~/.local/share/peripheralhub-venv/bin/pytest tests/
```

---

## Uninstallation

To completely remove the service and launcher:

```bash
cd ~/Dev/PeripheralBattery
./scripts/uninstall.sh
```
