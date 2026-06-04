import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass
class TrayConfig:
    enabled: bool = False


@dataclass
class DeviceConfig:
    name: str
    address: str
    connected_at: datetime


@dataclass
class LEDConfig:
    mode: int
    r: int
    g: int
    b: int


@dataclass
class CoolerConfig:
    last_device: DeviceConfig
    led: LEDConfig
    tray: TrayConfig

    @classmethod
    def load(cls, filepath: str) -> "CoolerConfig":
        filepath = os.path.expanduser(filepath)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            led = data.get("led", {"mode": 2, "r": 255, "g": 0, "b": 0})
            led_obj = LEDConfig(**led)

            last_device = data.get("last_device", {})
            connected_at = last_device.get("connected_at")
            if isinstance(connected_at, str):
                connected_at = datetime.fromisoformat(connected_at)
            elif connected_at is None:
                connected_at = datetime.now()
            last_device_obj = DeviceConfig(
                name=last_device.get("name", ""),
                address=last_device.get("address", ""),
                connected_at=connected_at,
            )
            tray = data.get("tray", {})
            tray_obj = TrayConfig(**tray)
            return cls(last_device=last_device_obj, led=led_obj, tray=tray_obj)
        return cls(
            last_device=DeviceConfig(name="", address="", connected_at=datetime.now()),
            led=LEDConfig(2, 255, 0, 0),
            tray=TrayConfig(),
        )

    @classmethod
    def save(cls, filepath: str, config: "CoolerConfig") -> None:
        filepath = os.path.expanduser(filepath)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        def _serialize(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(
                f"Object of type {type(obj).__name__} is not JSON serializable"
            )

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(config), f, indent=2, default=_serialize)
