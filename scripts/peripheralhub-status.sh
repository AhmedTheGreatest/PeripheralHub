#!/usr/bin/env bash
# PeripheralHub Polybar status wrapper
set -euo pipefail

BIN="$HOME/.local/bin/peripheralhub"

if [ -x "$BIN" ]; then
    exec "$BIN" status "$@"
else
    echo "󰍽 - | 󰌌 - | 󰋋 -"
fi
