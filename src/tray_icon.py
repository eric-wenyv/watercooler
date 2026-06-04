from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable, Optional

try:
    from PIL import Image, ImageDraw

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk

    try:
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3 as AppIndicator
    except (ImportError, ValueError):
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as AppIndicator

    APPINDICATOR_AVAILABLE = True
except Exception:
    APPINDICATOR_AVAILABLE = False

TRAY_AVAILABLE = PIL_AVAILABLE and APPINDICATOR_AVAILABLE


def _create_icon(size: int = 64) -> "Image.Image":
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    cx, cy = size // 2, size // 2
    r = size // 2 - 2

    # outer ring
    draw.ellipse(
        [cx - r, cy - r, cx + r, cy + r],
        outline=(66, 165, 245),
        width=max(1, size // 16),
    )

    # cross blades
    blade = r - size // 8
    draw.line(
        [(cx, cy - blade), (cx, cy + blade)],
        fill=(66, 165, 245),
        width=max(1, size // 20),
    )
    draw.line(
        [(cx - blade, cy), (cx + blade, cy)],
        fill=(66, 165, 245),
        width=max(1, size // 20),
    )

    # center dot
    cr = max(2, size // 10)
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(66, 165, 245))

    return image


def _icon_cache_dir() -> Path:
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")).expanduser()
    return cache_home / "watercooler" / "icons"


def _ensure_icon_file() -> tuple[str, str]:
    icon_dir = _icon_cache_dir()
    icon_dir.mkdir(parents=True, exist_ok=True)
    icon_name = "watercooler"
    icon_path = icon_dir / f"{icon_name}.png"

    if not icon_path.exists():
        _create_icon().save(icon_path, "PNG")

    return str(icon_dir), icon_name


class TrayIcon:
    def __init__(self, on_exit: Optional[Callable[[], None]] = None):
        self._indicator = None
        self._loop = None
        self._on_exit = on_exit
        self._thread: Optional[threading.Thread] = None
        self._status_text = "WaterCooler"
        self._status_item = None

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

    def _build_gtk_menu(self):
        menu = Gtk.Menu.new()

        self._status_item = Gtk.MenuItem.new_with_label(self._status_text)
        self._status_item.set_sensitive(False)
        menu.append(self._status_item)

        menu.append(Gtk.SeparatorMenuItem.new())

        exit_item = Gtk.MenuItem.new_with_label("Exit")
        exit_item.connect("activate", lambda *_: self._exit())
        menu.append(exit_item)

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

        icon_dir, icon_name = _ensure_icon_file()
        self._indicator = AppIndicator.Indicator.new(
            "watercooler",
            icon_name,
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_icon_theme_path(icon_dir)
        self._indicator.set_icon_full(icon_name, "WaterCooler")
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
        if self._indicator and APPINDICATOR_AVAILABLE:
            GLib.idle_add(
                lambda: (
                    self._indicator.set_status(AppIndicator.IndicatorStatus.PASSIVE),
                    self._loop.quit() if self._loop else None,
                    False,
                )[-1]
            )
