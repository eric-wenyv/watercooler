import asyncio

from constant import LED_STATIC, TX_UUID


async def set_head_led(client, r: int, g: int, b: int, mode: int = LED_STATIC):
    cmd = bytearray([0xFE, 0x1E, 0x01, r, g, b, mode, 0xEF])
    await client.write_gatt_char(TX_UUID, cmd)


async def set_fan_led(client, r: int, g: int, b: int, mode: int = LED_STATIC):
    cmd = bytearray([0xFE, 0x33, 0x01, r, g, b, mode, 0xEF])
    await client.write_gatt_char(TX_UUID, cmd)


async def turn_off_leds(client):
    await client.write_gatt_char(
        TX_UUID, bytearray([0xFE, 0x1E, 0x00, 0x00, 0x00, 0x00, 0x00, 0xEF])
    )
    await asyncio.sleep(0.1)
    await client.write_gatt_char(
        TX_UUID, bytearray([0xFE, 0x33, 0x00, 0x00, 0x00, 0x00, 0x00, 0xEF])
    )
