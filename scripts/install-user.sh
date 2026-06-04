#!/usr/bin/env bash
set -euo pipefail

DEFAULT_GITHUB_REPO="eric-wenyv/watercooler"

PYTHON_BIN="${PYTHON:-python3}"
GITHUB_REPO="${WATERCOOLER_GITHUB_REPO:-$DEFAULT_GITHUB_REPO}"
GITHUB_REF="${WATERCOOLER_GITHUB_REF:-main}"
INSTALL_SOURCE="${WATERCOOLER_INSTALL_SOURCE:-}"
INSTALL_LOCAL="${WATERCOOLER_INSTALL_LOCAL:-0}"
RAW_BASE_URL="https://raw.githubusercontent.com/$GITHUB_REPO/$GITHUB_REF"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_HOME="$HOME/.local/bin"

APP_DIR="$DATA_HOME/watercooler"
VENV_DIR="$APP_DIR/venv"
DESKTOP_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"

PROJECT_DIR=""
SOURCE_PATH="${BASH_SOURCE[0]:-}"

if [[ -n "$SOURCE_PATH" && "$SOURCE_PATH" != "bash" && "$SOURCE_PATH" != /dev/fd/* && -f "$SOURCE_PATH" ]]; then
    CANDIDATE_PROJECT_DIR="$(cd "$(dirname "$SOURCE_PATH")/.." && pwd)"
    if [[ -f "$CANDIDATE_PROJECT_DIR/pyproject.toml" && -d "$CANDIDATE_PROJECT_DIR/src/watercooler" ]]; then
        PROJECT_DIR="$CANDIDATE_PROJECT_DIR"
    fi
fi

require_github_repo() {
    if [[ -z "$GITHUB_REPO" ]]; then
        cat >&2 <<EOF
This installer is not running inside a project checkout, and WATERCOOLER_GITHUB_REPO is not set.

Run it with the GitHub repository name:
  curl -fsSL https://raw.githubusercontent.com/eric-wenyv/watercooler/main/scripts/install-user.sh | bash

Or override WATERCOOLER_GITHUB_REPO for a fork.
EOF
        exit 1
    fi

    if [[ "$GITHUB_REPO" != */* ]]; then
        cat >&2 <<EOF
Invalid WATERCOOLER_GITHUB_REPO: $GITHUB_REPO

Expected the form:
  OWNER/REPO
EOF
        exit 1
    fi
}

if [[ -z "$INSTALL_SOURCE" ]]; then
    if [[ "$INSTALL_LOCAL" == "1" && -n "$PROJECT_DIR" ]]; then
        INSTALL_SOURCE="$PROJECT_DIR"
    else
        require_github_repo
        INSTALL_SOURCE="https://github.com/$GITHUB_REPO/archive/$GITHUB_REF.tar.gz"
    fi
fi

write_fallback_icon() {
    cat > "$ICON_DIR/watercooler.svg" <<'EOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="WaterCooler">
  <rect width="64" height="64" rx="12" fill="#111827"/>
  <circle cx="32" cy="32" r="22" fill="none" stroke="#38bdf8" stroke-width="4"/>
  <path d="M32 12v40M12 32h40" stroke="#38bdf8" stroke-width="4" stroke-linecap="round"/>
  <circle cx="32" cy="32" r="7" fill="#38bdf8"/>
  <path d="M20 20l24 24M44 20L20 44" stroke="#93c5fd" stroke-width="2" stroke-linecap="round" opacity=".9"/>
</svg>
EOF
    chmod 0644 "$ICON_DIR/watercooler.svg"
}

install_icon() {
    if [[ "$INSTALL_LOCAL" == "1" && -n "$PROJECT_DIR" && -f "$PROJECT_DIR/assets/watercooler.svg" ]]; then
        install -m 0644 "$PROJECT_DIR/assets/watercooler.svg" "$ICON_DIR/watercooler.svg"
        return
    fi

    ICON_URL="$RAW_BASE_URL/assets/watercooler.svg"
    if command -v curl >/dev/null 2>&1 && curl -fsSL "$ICON_URL" -o "$ICON_DIR/watercooler.svg"; then
        chmod 0644 "$ICON_DIR/watercooler.svg"
        return
    fi

    if command -v wget >/dev/null 2>&1 && wget -qO "$ICON_DIR/watercooler.svg" "$ICON_URL"; then
        chmod 0644 "$ICON_DIR/watercooler.svg"
        return
    fi

    write_fallback_icon
}

mkdir -p "$APP_DIR" "$BIN_HOME" "$DESKTOP_DIR" "$ICON_DIR"

"$PYTHON_BIN" -m venv --system-site-packages "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install --upgrade "$INSTALL_SOURCE"

ln -sfn "$VENV_DIR/bin/watercooler" "$BIN_HOME/watercooler"
install_icon

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

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

if [[ "$INSTALL_LOCAL" == "1" && -n "$PROJECT_DIR" && -f "$PROJECT_DIR/scripts/install-user-service.sh" ]]; then
    SERVICE_INSTALL_COMMAND="bash $PROJECT_DIR/scripts/install-user-service.sh"
elif [[ -n "$GITHUB_REPO" ]]; then
    SERVICE_INSTALL_COMMAND="curl -fsSL $RAW_BASE_URL/scripts/install-user-service.sh | bash"
else
    SERVICE_INSTALL_COMMAND="curl -fsSL https://raw.githubusercontent.com/eric-wenyv/watercooler/main/scripts/install-user-service.sh | bash"
fi

cat <<EOF
Installed WaterCooler.

Install source:
  $INSTALL_SOURCE

Command:
  $BIN_HOME/watercooler

Desktop entry:
  $DESKTOP_DIR/watercooler.desktop

Run once interactively before registering the background service:
  $BIN_HOME/watercooler

Register the optional background user service after the first successful device selection:
  $SERVICE_INSTALL_COMMAND

Uninstall:
  $BIN_HOME/watercooler --uninstall
EOF
