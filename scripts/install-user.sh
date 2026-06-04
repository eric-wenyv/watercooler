#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
BIN_HOME="$HOME/.local/bin"

APP_DIR="$DATA_HOME/watercooler"
VENV_DIR="$APP_DIR/venv"
DESKTOP_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
SYSTEMD_USER_DIR="$CONFIG_HOME/systemd/user"

mkdir -p "$APP_DIR" "$BIN_HOME" "$DESKTOP_DIR" "$ICON_DIR" "$SYSTEMD_USER_DIR"

"$PYTHON_BIN" -m venv --system-site-packages "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install --upgrade "$PROJECT_DIR"

ln -sfn "$VENV_DIR/bin/watercooler" "$BIN_HOME/watercooler"
install -m 0644 "$PROJECT_DIR/assets/watercooler.svg" "$ICON_DIR/watercooler.svg"

cat > "$DESKTOP_DIR/watercooler.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=WaterCooler
Comment=Control CoolingSystem BLE water cooler devices
Exec=$VENV_DIR/bin/watercooler
Icon=watercooler
Terminal=true
Categories=Utility;HardwareSettings;
StartupNotify=false
EOF

cat > "$SYSTEMD_USER_DIR/watercooler.service" <<EOF
[Unit]
Description=WaterCooler BLE controller
After=bluetooth.target graphical-session.target

[Service]
Type=simple
ExecStart=$VENV_DIR/bin/watercooler
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

systemctl --user daemon-reload >/dev/null 2>&1 || true

cat <<EOF
Installed WaterCooler.

Command:
  $BIN_HOME/watercooler

Desktop entry:
  $DESKTOP_DIR/watercooler.desktop

User service:
  $SYSTEMD_USER_DIR/watercooler.service

Run once interactively before enabling the service:
  $BIN_HOME/watercooler

Enable background autostart after the first successful device selection:
  systemctl --user enable --now watercooler.service
EOF
