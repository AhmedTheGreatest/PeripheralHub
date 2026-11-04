#!/usr/bin/env bash
# PeripheralHub Installation Script for Xubuntu 24.04 / i3wm
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$HOME/.local/share/peripheralhub-venv"
BIN_DIR="$HOME/.local/bin"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
CONFIG_DIR="$HOME/.config/peripheralhub"

echo "=== Installing PeripheralHub ==="

# 1. Ensure Python venv
echo "-> Setting up Python virtual environment..."
mkdir -p "$BIN_DIR" "$SYSTEMD_USER_DIR" "$CONFIG_DIR"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# 2. Install dependencies
echo "-> Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet pyusb hidapi
"$VENV_DIR/bin/pip" install --quiet -e "$SCRIPT_DIR"

# 3. Create ~/.local/bin/peripheralhub wrapper
echo "-> Creating CLI launcher at $BIN_DIR/peripheralhub..."
cat << EOF > "$BIN_DIR/peripheralhub"
#!/usr/bin/env bash
export PYTHONPATH="$SCRIPT_DIR:\${PYTHONPATH:-}"
exec "$VENV_DIR/bin/python3" -m src.cli "\$@"
EOF
chmod +x "$BIN_DIR/peripheralhub"
chmod +x "$SCRIPT_DIR/scripts/peripheralhub-status.sh"

# 4. Install default config if not present
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    echo "-> Installing default configuration to $CONFIG_DIR/config.json..."
    cp "$SCRIPT_DIR/config/config.json" "$CONFIG_DIR/config.json"
fi

# 5. Install udev rules if needed
echo "-> Checking udev permissions..."
if [ ! -f "/etc/udev/rules.d/99-peripheralhub.rules" ]; then
    echo "-> Installing udev rules to /etc/udev/rules.d/99-peripheralhub.rules..."
    if command -v pkexec >/dev/null 2>&1; then
        pkexec cp "$SCRIPT_DIR/config/udev/99-peripheralhub.rules" /etc/udev/rules.d/99-peripheralhub.rules
        pkexec udevadm control --reload-rules
        pkexec udevadm trigger
    elif command -v sudo >/dev/null 2>&1; then
        sudo cp "$SCRIPT_DIR/config/udev/99-peripheralhub.rules" /etc/udev/rules.d/99-peripheralhub.rules
        sudo udevadm control --reload-rules
        sudo udevadm trigger
    else
        echo "WARNING: Could not install udev rules automatically. Please copy $SCRIPT_DIR/config/udev/99-peripheralhub.rules to /etc/udev/rules.d/ manually."
    fi
fi

# 6. Install and enable systemd user service
echo "-> Configuring systemd user service..."
cp "$SCRIPT_DIR/config/systemd/peripheralhub.service" "$SYSTEMD_USER_DIR/peripheralhub.service"
systemctl --user daemon-reload
systemctl --user enable peripheralhub.service
systemctl --user restart peripheralhub.service

# 7. Initial poll
echo "-> Running initial device poll..."
"$BIN_DIR/peripheralhub" poll-once || true

echo ""
echo "=== PeripheralHub Installed Successfully! ==="
echo "Status output for Polybar:"
"$BIN_DIR/peripheralhub" status
echo ""
echo "Next step: Add the module to your Polybar configuration."
echo "See config/polybar/peripheralhub.ini for details."
