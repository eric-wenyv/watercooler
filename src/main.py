import asyncio
import subprocess
from datetime import datetime

from bleak import BleakClient, BleakScanner

from config_manager import CoolerConfig, DeviceConfig
from constant import CONFIG_FILE, RX_UUID, TX_UUID
from light import set_head_led, turn_off_leds


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


async def main():
    # scan devices
    print("Scanning...")
    devices = await BleakScanner.discover()
    target_device = None

    cooling_devices = []
    for d in devices:
        if d.name and "CoolingSystem" in d.name:
            target_device = d
            cooling_devices.append(d)

    if not cooling_devices:
        print("Did not find any cooling devices.")
        return

    config = CoolerConfig.load(CONFIG_FILE)
    target_device = None
    if config.last_device.address in cooling_devices:
        target_device = config.last_device
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

    if target_device.address != config.last_device.address:
        config.last_device = DeviceConfig(
            name=target_device.name,
            address=target_device.address,
            connected_at=datetime.now(),
        )
        CoolerConfig.save(CONFIG_FILE, config)

    # connect to device
    async with BleakClient(target_device.address) as client:
        print(f"Connected to: {target_device.name}")

        # subscribe to RX notifications
        await client.start_notify(RX_UUID, notification_handler)

        print("Try to handshake with device ...")
        await client.write_gatt_char(TX_UUID, b"sw")
        await asyncio.sleep(1.0)

        print("Try to set head LED ...")
        led = config.led
        await set_head_led(client, led.r, led.g, led.b, led.mode)
        await asyncio.sleep(1.0)

        last_speed = 0
        try:
            while True:
                cpu_temp = get_CPU_temperature()
                gpu_temp = get_GPU_temperature()
                curr_temp = max(cpu_temp, gpu_temp)

                target_speed = cal_cooling_speed(curr_temp)
                print(f"Current temp: {curr_temp}°C, target speed: {target_speed}%")

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

                await asyncio.sleep(5)

        except asyncio.CancelledError:
            pass
        finally:
            print("\n Closing device...")
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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
