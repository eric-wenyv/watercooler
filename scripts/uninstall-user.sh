#!/usr/bin/env bash
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
BIN_HOME="$HOME/.local/bin"

systemctl --user disable --now watercooler.service >/dev/null 2>&1 || true

rm -f "$CONFIG_HOME/systemd/user/watercooler.service"
rm -f "$DATA_HOME/applications/watercooler.desktop"
rm -f "$DATA_HOME/icons/hicolor/scalable/apps/watercooler.svg"
rm -f "$BIN_HOME/watercooler"
rm -rf "$DATA_HOME/watercooler"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

systemctl --user daemon-reload >/dev/null 2>&1 || true

echo "Uninstalled WaterCooler."
