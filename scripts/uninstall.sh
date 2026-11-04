#!/usr/bin/env bash
# PeripheralHub Uninstallation Script
set -euo pipefail

echo "=== Uninstalling PeripheralHub ==="

# Stop and disable systemd service
if systemctl --user is-active --quiet peripheralhub.service 2>/dev/null; then
    echo "-> Stopping peripheralhub.service..."
    systemctl --user stop peripheralhub.service
fi

if systemctl --user is-enabled --quiet peripheralhub.service 2>/dev/null; then
    echo "-> Disabling peripheralhub.service..."
    systemctl --user disable peripheralhub.service
fi

rm -f "$HOME/.config/systemd/user/peripheralhub.service"
systemctl --user daemon-reload

# Remove CLI launcher
echo "-> Removing $HOME/.local/bin/peripheralhub..."
rm -f "$HOME/.local/bin/peripheralhub"

# Remove cache
echo "-> Cleaning cache..."
rm -rf "$HOME/.cache/peripheralhub"

# Ask about venv and udev
echo "-> Note: Virtual environment at $HOME/.local/share/peripheralhub-venv and /etc/udev/rules.d/99-peripheralhub.rules were retained."
echo "To remove them, run:"
echo "  rm -rf ~/.local/share/peripheralhub-venv ~/.config/peripheralhub"
echo "  pkexec rm /etc/udev/rules.d/99-peripheralhub.rules && pkexec udevadm control --reload-rules"

echo "=== PeripheralHub Uninstalled Successfully ==="
