from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from bleak.backends.device import BLEDevice

GLib: Any = None
Gtk: Any = None
AppIndicator: Any = None

try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import (
        GLib as _GLib,  # pyright: ignore[reportAttributeAccessIssue]
    )
    from gi.repository import Gtk as _Gtk  # pyright: ignore[reportAttributeAccessIssue]

    try:
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import (
            AppIndicator3 as _AppIndicator,  # pyright: ignore[reportAttributeAccessIssue]
        )
    except (ImportError, ValueError):
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import (
            AyatanaAppIndicator3 as _AppIndicator,  # pyright: ignore[reportAttributeAccessIssue]
        )

    GLib = _GLib
    Gtk = _Gtk
    AppIndicator = _AppIndicator
    APPINDICATOR_AVAILABLE = True
except Exception:
    APPINDICATOR_AVAILABLE = False

TRAY_AVAILABLE = APPINDICATOR_AVAILABLE


class TrayIcon:
    def __init__(
        self,
        on_exit: Optional[Callable[[], None]] = None,
        on_rescan_devices: Optional[Callable[[], None]] = None,
        on_select_device: Optional[Callable[[str], None]] = None,
        on_set_led_mode: Optional[Callable[[int], None]] = None,
    ):
        self._indicator = None
        self._loop = None
        self._on_exit = on_exit
        self._thread: Optional[threading.Thread] = None
        self._status_text = "WaterCooler"
        self._status_item = None
        self._device_status = "No Device"
        self._led_mode = None
        self._on_rescan_devices = on_rescan_devices
        self._on_select_device = on_select_device
        self._on_set_led_mode = on_set_led_mode
        self._devices: dict[str, str] = {}
        self._led_modes: dict[int, str] = {
            0: "Static",
            1: "Pulse",
            2: "Rainbow",
        }

    def set_status(self, text: str) -> None:
        self._status_text = text
        if self._indicator and APPINDICATOR_AVAILABLE:
            GLib.idle_add(self._update_appindicator_status, text)

    def _update_appindicator_status(self, text: str) -> bool:
        if self._indicator:
            self._indicator.set_title(text)
        if self._status_item:
            self._status_item.set_label(text)
        return False

    def _update_menu_state(self, update: Callable[[], None]) -> None:
        def update_and_rebuild() -> bool:
            update()
            if self._indicator:
                self._indicator.set_menu(self._build_gtk_menu())
            return False

        if self._indicator is not None and APPINDICATOR_AVAILABLE:
            GLib.idle_add(update_and_rebuild)
        else:
            update()

    def _build_gtk_menu(self):
        menu = Gtk.Menu.new()

        # Status item
        self._status_item = Gtk.MenuItem.new_with_label(self._status_text)
        self._status_item.set_sensitive(False)
        menu.append(self._status_item)

        menu.append(Gtk.SeparatorMenuItem.new())

        # Exit item
        exit_item = Gtk.MenuItem.new_with_label("Exit")
        exit_item.connect("activate", lambda *_: self._exit())
        menu.append(exit_item)

        menu.append(Gtk.SeparatorMenuItem.new())

        # LED Mode item
        led_mode_item = Gtk.MenuItem.new_with_label("LED Mode")
        led_mode_submenu = Gtk.Menu.new()
        led_mode_callback = self._on_set_led_mode
        for mode, name in self._led_modes.items():
            if mode == self._led_mode:
                item = Gtk.MenuItem.new_with_label(f"✓ {name}")
                item.set_sensitive(False)
            else:
                item = Gtk.MenuItem.new_with_label(name)
            if led_mode_callback is not None:
                item.connect(
                    "activate",
                    lambda *_args, mode=mode, callback=led_mode_callback: callback(
                        mode
                    ),
                )
            led_mode_submenu.append(item)
        led_mode_item.set_submenu(led_mode_submenu)
        menu.append(led_mode_item)

        menu.append(Gtk.SeparatorMenuItem.new())

        # Device item
        devices_item = Gtk.MenuItem.new_with_label("Devices")
        devices_submenu = Gtk.Menu.new()

        device_status_item = Gtk.MenuItem.new_with_label(self._device_status)
        device_status_item.set_sensitive(False)
        devices_submenu.append(device_status_item)

        device_rescan_item = Gtk.MenuItem.new_with_label("Rescan")
        device_rescan_callback = self._on_rescan_devices
        if device_rescan_callback is not None:
            device_rescan_item.connect(
                "activate", lambda *_, callback=device_rescan_callback: callback()
            )
        devices_submenu.append(device_rescan_item)

        device_select_callback = self._on_select_device
        for address, name in self._devices.items():
            item = Gtk.MenuItem.new_with_label(name)
            if device_select_callback is not None:
                item.connect(
                    "activate",
                    lambda *_args, address=address, callback=device_select_callback: (
                        callback(address)
                    ),
                )
            devices_submenu.append(item)
        devices_item.set_submenu(devices_submenu)
        menu.append(devices_item)

        menu.show_all()
        return menu

    def _exit(self, icon=None, item=None) -> None:
        if self._on_exit:
            self._on_exit()
        if self._indicator:
            self._indicator.set_status(AppIndicator.IndicatorStatus.PASSIVE)
        if self._loop:
            self._loop.quit()

    def _run_appindicator(self) -> None:
        initialized, _ = Gtk.init_check([])
        if not initialized:
            print("System tray unavailable: GTK could not be initialized.")
            return

        icon_dir = Path(
            os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")
        ).expanduser() / "icons/hicolor/scalable/apps"
        self._indicator = AppIndicator.Indicator.new(
            "watercooler",
            "watercooler",
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_icon_theme_path(str(icon_dir))
        self._indicator.set_icon_full("watercooler", "WaterCooler")
        self._indicator.set_title(self._status_text)
        self._indicator.set_menu(self._build_gtk_menu())
        self._indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)

        self._loop = GLib.MainLoop.new(None, False)
        self._loop.run()

    def start(self) -> None:
        if not TRAY_AVAILABLE:
            return

        self._thread = threading.Thread(target=self._run_appindicator, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        indicator = self._indicator
        loop = self._loop

        if indicator is None or not APPINDICATOR_AVAILABLE:
            return

        def stop_indicator() -> bool:
            indicator.set_status(AppIndicator.IndicatorStatus.PASSIVE)
            if loop is not None:
                loop.quit()
            return False

        GLib.idle_add(stop_indicator)

    def set_led_mode(self, mode: int) -> None:
        def update() -> None:
            self._led_mode = mode

        self._update_menu_state(update)

    def set_device_status(self, name: str) -> None:
        def update() -> None:
            self._device_status = name

        self._update_menu_state(update)

    def set_scanned_devices(self, devices: list[BLEDevice]) -> None:
        device_labels = {d.address: d.name or d.address for d in devices}

        def update() -> None:
            self._devices = device_labels

        self._update_menu_state(update)
