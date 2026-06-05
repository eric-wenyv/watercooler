#!/usr/bin/env bash
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"

APP_DIR="$DATA_HOME/watercooler"
VENV_DIR="$APP_DIR/venv"
SYSTEMD_USER_DIR="$CONFIG_HOME/systemd/user"
SERVICE_FILE="$SYSTEMD_USER_DIR/watercooler.service"
LOG_DIR="$STATE_HOME/watercooler"
LOG_FILE="$LOG_DIR/watercooler.service.log"

if [[ ! -x "$VENV_DIR/bin/watercooler" ]]; then
    cat >&2 <<EOF
WaterCooler is not installed at:
  $VENV_DIR/bin/watercooler

Run the normal user install first.

From a local checkout:
  bash scripts/install-user.sh

From GitHub:
  curl -fsSL https://raw.githubusercontent.com/eric-wenyv/watercooler/main/scripts/install-user.sh | bash
EOF
    exit 1
fi

mkdir -p "$SYSTEMD_USER_DIR" "$LOG_DIR"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=WaterCooler BLE controller
After=bluetooth.target graphical-session.target

[Service]
Type=simple
ExecStart=$VENV_DIR/bin/watercooler
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1
StandardOutput=append:$LOG_FILE
StandardError=append:$LOG_FILE

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload >/dev/null 2>&1 || true

cat <<EOF
Registered WaterCooler user service.

User service:
  $SERVICE_FILE

Service log:
  $LOG_FILE

Enable background autostart:
  systemctl --user enable --now watercooler.service
EOF
