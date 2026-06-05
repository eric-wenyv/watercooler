# WaterCooler

[English](README.md) | [简体中文](README.zh-CN.md)

WaterCooler is a Linux desktop utility for controlling `CoolingSystem` BLE water cooler devices.

The project is developed for Users who want a simple and lightweight app to control water cooler on Linux desktop. My laptop is MECHREVO and I test it on Fedora. It should work on other distributions with similar watercooler system.

## tl;dr
use AI to read documentation.

## Overview

When started, WaterCooler scans nearby BLE devices and looks for device names containing `CoolingSystem`. On first run, it asks you to select the target device from the terminal. The selected device is saved and reused on later launches.

At runtime, the app reads:

- CPU temperature from `/sys/class/thermal/thermal_zone0/temp`
- NVIDIA GPU temperature from `nvidia-smi`

It uses the higher of the two values to calculate a target speed, then writes fan and pump commands to the cooler. On shutdown, it attempts to turn off LEDs, fan control, and pump control before disconnecting.

## Installation

### 1. Install WaterCooler

From GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/eric-wenyv/watercooler/main/scripts/install-user.sh | bash
```

It creates:

- Command: `~/.local/bin/watercooler`
- Desktop launcher: `~/.local/share/applications/watercooler.desktop`
- Icon: `~/.local/share/icons/hicolor/scalable/apps/watercooler.svg`
- Desktop log: `~/.local/state/watercooler/watercooler.log`
- Private virtual environment: `~/.local/share/watercooler/venv`

### 2. Run Once Interactively

Run WaterCooler once from a terminal so you can select the BLE device:

```bash
watercooler
```

After a device is saved, the desktop launcher starts WaterCooler without a terminal
and appends output to the desktop log.

The selected device and LED settings are saved to:

```text
~/.config/watercooler/settings.json
```

### 3. Optional: Register User Service

After the first successful device selection, register the systemd user service:

```bash
curl -fsSL https://raw.githubusercontent.com/eric-wenyv/watercooler/main/scripts/install-user-service.sh | bash
```

The service writes to:

```text
~/.local/state/watercooler/watercooler.service.log
```

### 4. Uninstall

```bash
watercooler --uninstall
```

## Project Structure

Core application code lives in `src/watercooler`:

- `main.py`: scans BLE devices, connects to the cooler, reads temperatures, calculates target speed, and sends fan/pump commands.
- `light.py`: wraps LED control commands.
- `config_manager.py`: loads and saves user configuration.
- `constant.py`: stores BLE UUIDs and the config file path.
- `tray_icon.py`: optional system tray menu support.

After installation, the `watercooler` command runs the Python package entry point:

```bash
python -m watercooler
```

## Additional Notes

The tray icon requires system GTK/AppIndicator bindings. GNOME users may also need
an AppIndicator/KStatusNotifierItem shell extension. Tray support is controlled by
`tray.enabled` in `~/.config/watercooler/settings.json`.
