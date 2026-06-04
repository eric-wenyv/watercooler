import argparse
import asyncio
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from .config_manager import CoolerConfig, DeviceConfig
from .constant import CONFIG_FILE, RX_UUID, TX_UUID
from .light import set_head_led, turn_off_leds
from .tray_icon import TRAY_AVAILABLE, TrayIcon


def _data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")).expanduser()


def _config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser()


def _run_quiet(command: list[str]) -> None:
    try:
        subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        pass


def uninstall() -> None:
    data_home = _data_home()
    config_home = _config_home()
    bin_home = Path.home() / ".local/bin"

    _run_quiet(["systemctl", "--user", "disable", "--now", "watercooler.service"])

    for path in (
        config_home / "systemd/user/watercooler.service",
        data_home / "applications/watercooler.desktop",
        data_home / "icons/hicolor/scalable/apps/watercooler.svg",
        bin_home / "watercooler",
    ):
        try:
            path.unlink(missing_ok=True)
        except IsADirectoryError:
            shutil.rmtree(path, ignore_errors=True)

    shutil.rmtree(data_home / "watercooler", ignore_errors=True)

    if shutil.which("update-desktop-database"):
        _run_quiet(["update-desktop-database", str(data_home / "applications")])

    if shutil.which("gtk-update-icon-cache"):
        _run_quiet(["gtk-update-icon-cache", str(data_home / "icons/hicolor")])

    _run_quiet(["systemctl", "--user", "daemon-reload"])

    print("Uninstalled WaterCooler.")


def notification_handler(sender, data) -> None:
    print(f"Receive Data from {sender} : {data.hex().upper()} | Raw data: {data}")


async def shutdown(client) -> None:
    try:
        print("Shutting down...")
        await client.write_gatt_char(
            TX_UUID, bytearray([0xFE, 0x1C, 0x00, 0x00, 0x00, 0x00, 0x00, 0xEF])
        )
        await client.write_gatt_char(
            TX_UUID, bytearray([0xFE, 0x1B, 0x00, 0x00, 0x00, 0x00, 0x00, 0xEF])
        )
        await client.stop_notify(RX_UUID)
        print("Disconnected.")
    except Exception as e:
        print(f"Already disconnected: {e}")


def get_CPU_temperature() -> float:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_raw = f.read().strip()
            return float(temp_raw) / 1000.0
    except Exception as e:
        print(f"Error reading CPU temperature: {e}")
        return 40.0


def get_GPU_temperature() -> float:
    try:
        res = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=temperature.gpu",
                "--format=csv,noheader",
            ],
            stderr=subprocess.STDOUT,
        )
        return float(res.decode().strip())
    except Exception as e:
        print(f"Error reading CPU temperature: {e}")
        return 40.0


def cal_cooling_speed(current_temp: float) -> int:
    MIN_TEMP, MAX_TEMP = 40.0, 80.0
    MIN_SPEED, MAX_SPEED = 20, 90
    rate = (MAX_SPEED - MIN_SPEED) / (MAX_TEMP - MIN_TEMP)

    if current_temp < MIN_TEMP:
        return MIN_SPEED
    elif current_temp > MAX_TEMP:
        return MAX_SPEED
    else:
        return int(MIN_SPEED + (current_temp - MIN_TEMP) / rate)


async def rescan_devices() -> list[BLEDevice]:
    devices = await BleakScanner.discover()

    cooling_devices = []
    for d in devices:
        if d.name and "CoolingSystem" in d.name:
            cooling_devices.append(d)

    if not cooling_devices:
        print("Did not find any cooling devices.")
    return cooling_devices


async def initialize_cooler(client: BleakClient, config: CoolerConfig) -> None:
    # subscribe to RX notifications
    await client.start_notify(RX_UUID, notification_handler)

    print("Try to handshake with device ...")
    await client.write_gatt_char(TX_UUID, b"sw")
    await asyncio.sleep(1.0)

    print("Try to set head LED ...")
    led = config.led
    await set_head_led(client, led.r, led.g, led.b, led.mode)
    await asyncio.sleep(1.0)


async def main():
    loop = asyncio.get_event_loop()
    main_task = asyncio.current_task()
    command_queue = asyncio.Queue()

    def request_stop():
        if main_task and not main_task.done():
            loop.call_soon_threadsafe(main_task.cancel)

    def request_set_led_mode(mode: int):
        loop.call_soon_threadsafe(command_queue.put_nowait, ("set_led_mode", mode))

    def request_select_device(address: str):
        loop.call_soon_threadsafe(command_queue.put_nowait, ("select_device", address))

    def request_rescan_devices():
        loop.call_soon_threadsafe(command_queue.put_nowait, ("rescan_devices", None))

    tray = None
    config = CoolerConfig.load(CONFIG_FILE)
    if config.tray.enabled and TRAY_AVAILABLE:
        tray = TrayIcon(
            on_exit=request_stop,
            on_rescan_devices=request_rescan_devices,
            on_select_device=request_select_device,
            on_set_led_mode=request_set_led_mode,
        )
        tray.set_led_mode(config.led.mode)
        tray.start()

    # scan devices
    print("Scanning...")
    cooling_devices = await rescan_devices()
    known_devices = {d.address: d for d in cooling_devices}

    if tray:
        tray.set_scanned_devices(cooling_devices)

    if not cooling_devices:
        return

    target_device = None
    if config.last_device.address in known_devices:
        target_device = known_devices[config.last_device.address]
    else:
        if not config.last_device.address or config.last_device.address == "":
            print("No previous device found.")
        print("Select your new devices: ")
        for i, d in enumerate(cooling_devices):
            print(f"{i + 1}. {d.name} [{d.address}]")

        device_index = int(input("Enter the device number to connect: ")) - 1
        if device_index < 0 or device_index >= len(cooling_devices):
            print("Invalid device number.")
            return

        target_device = cooling_devices[device_index]

    target_name = target_device.name or target_device.address
    if (
        target_device.address != config.last_device.address
        or target_name != config.last_device.name
    ):
        config.last_device = DeviceConfig(
            name=target_name,
            address=target_device.address,
            connected_at=datetime.now(),
        )
        CoolerConfig.save(CONFIG_FILE, config)

    if tray:
        tray.set_device_status(target_name)

    # connect to device
    client = BleakClient(target_device.address)
    await client.connect()
    try:
        print(f"Connected to: {target_name}")

        if tray:
            tray.set_status(f"Connected to: {target_name}")

        await initialize_cooler(client, config)

        last_speed = 0

        try:
            while True:
                cpu_temp = get_CPU_temperature()
                gpu_temp = get_GPU_temperature()
                curr_temp = max(cpu_temp, gpu_temp)

                target_speed = cal_cooling_speed(curr_temp)
                print(f"Current temp: {curr_temp}°C, target speed: {target_speed}%")

                if tray:
                    tray.set_status(f"{curr_temp}°C | {target_speed}% ")

                if abs(target_speed - last_speed) >= 3:
                    fan_cmd = bytearray(
                        [0xFE, 0x1B, 0x01, target_speed, 0x00, 0x00, 0x00, 0xEF]
                    )
                    await client.write_gatt_char(TX_UUID, fan_cmd)
                    await asyncio.sleep(0.2)
                    last_speed = target_speed

                    voltage_code = 0x0B if target_speed >= 80 else 0x08
                    pump_cmd = bytearray(
                        [0xFE, 0x1C, 0x01, target_speed, voltage_code, 0x00, 0x00, 0xEF]
                    )
                    await client.write_gatt_char(TX_UUID, pump_cmd)
                else:
                    print(f"Fan speed: {target_speed}%, no change needed.")

                try:
                    async with asyncio.timeout(1.0):
                        cmd, payload = await command_queue.get()
                except asyncio.TimeoutError:
                    cmd, payload = None, None
                if cmd == "set_led_mode" and payload is not None:
                    led_mode = int(payload)
                    config.led.mode = led_mode
                    CoolerConfig.save(CONFIG_FILE, config)

                    led = config.led
                    await set_head_led(client, led.r, led.g, led.b, led.mode)

                    if tray:
                        tray.set_led_mode(led_mode)
                elif cmd == "select_device" and payload:
                    selected_address = str(payload)
                    selected_device = known_devices.get(selected_address)
                    selected_name = (
                        selected_device.name
                        if selected_device and selected_device.name
                        else selected_address
                    )

                    config.last_device = DeviceConfig(
                        name=selected_name,
                        address=selected_address,
                        connected_at=datetime.now(),
                    )
                    CoolerConfig.save(CONFIG_FILE, config)

                    await shutdown(client)
                    await client.disconnect()
                    await asyncio.sleep(0.1)

                    client = BleakClient(selected_address)
                    await client.connect()
                    await initialize_cooler(client, config)
                    last_speed = 0

                    if tray:
                        tray.set_device_status(selected_name)
                        tray.set_status(f"Connected to: {selected_name}")
                elif cmd == "rescan_devices":
                    devices = await rescan_devices()
                    known_devices = {d.address: d for d in devices}
                    if tray:
                        tray.set_scanned_devices(devices)

                await asyncio.sleep(5)

        except asyncio.CancelledError:
            pass
        finally:
            print("\n Closing device...")
            if tray:
                tray.stop()
            try:
                await turn_off_leds(client)
                await asyncio.sleep(0.1)
                await client.write_gatt_char(
                    TX_UUID, bytearray([0xFE, 0x1C, 0x00, 0x00, 0x00, 0x00, 0x00, 0xEF])
                )
                await client.write_gatt_char(
                    TX_UUID, bytearray([0xFE, 0x1B, 0x00, 0x00, 0x00, 0x00, 0x00, 0xEF])
                )
                await client.stop_notify(RX_UUID)
            except Exception as e:
                print(f"Error: {e}")
            print("Closed.")
    finally:
        try:
            await client.disconnect()
        except Exception as e:
            print(f"Disconnect error: {e}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Control CoolingSystem BLE water cooler devices")
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="remove the user installation, desktop entry, icon, and systemd user service",
    )
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    if args.uninstall:
        uninstall()
        return

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")


if __name__ == "__main__":
    run()
