"""MQTT commands reverse-engineered from Mạnh Quân Solar firmware v2.3.3."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from homeassistant.components.mqtt.client import async_publish, async_subscribe
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import JsonObjectType

from .const import MQTT_RESPONSE_TIMEOUT
from .coordinator import MQSolarCoordinator
from .protocol import mqtt_command_payload, mqtt_topic_base


def _device_topic_type(coordinator: MQSolarCoordinator) -> str:
    return (
        "grid_tie_inverter"
        if coordinator.data.get("_device_type") == "Inverter"
        else "mppt_charger"
    )


def _topic_base(coordinator: MQSolarCoordinator, topic_code: str) -> str:
    device_id = coordinator.data["_device_id"]
    return mqtt_topic_base(_device_topic_type(coordinator), topic_code, device_id)


async def async_send_command(
    hass: HomeAssistant,
    coordinator: MQSolarCoordinator,
    topic_code: str,
    command: str,
    parameter: dict[str, Any] | None = None,
) -> None:
    """Publish one firmware command without retaining it."""
    await async_publish(
        hass,
        f"{_topic_base(coordinator, topic_code)}/cmd",
        mqtt_command_payload(command, parameter),
        qos=0,
        retain=False,
    )


async def async_restart(
    hass: HomeAssistant, coordinator: MQSolarCoordinator, topic_code: str
) -> None:
    """Restart the ESP8266 Wi-Fi module."""
    await async_send_command(hass, coordinator, topic_code, "restart")


async def async_reboot_charge(
    hass: HomeAssistant, coordinator: MQSolarCoordinator, topic_code: str
) -> None:
    """Restart the STM32 charger controller."""
    await async_send_command(hass, coordinator, topic_code, "reboot_charge")


async def async_get_charger_config(
    hass: HomeAssistant, coordinator: MQSolarCoordinator, topic_code: str
) -> JsonObjectType:
    """Request charger configuration and wait for its MQTT response."""
    # Firmware puts "charger_config_sync" in the JSON command field. The final
    # topic suffix is generated separately, so listen below the device topic and
    # filter by payload instead of assuming a suffix.
    response_topic = f"{_topic_base(coordinator, topic_code)}/#"
    response: asyncio.Future[JsonObjectType] = hass.loop.create_future()

    async def message_received(message: Any) -> None:
        if response.done():
            return
        try:
            data = json.loads(message.payload)
        except (TypeError, ValueError):
            return
        if isinstance(data, dict) and data.get("command") == "charger_config_sync":
            response.set_result(data)

    unsubscribe = await async_subscribe(hass, response_topic, message_received, qos=0)
    try:
        await async_send_command(hass, coordinator, topic_code, "get_charger_config")
        async with asyncio.timeout(MQTT_RESPONSE_TIMEOUT):
            return await response
    except TimeoutError as err:
        raise HomeAssistantError(
            f"No charger_config_sync response below {response_topic}"
        ) from err
    finally:
        unsubscribe()


async def async_set_charger_config(
    hass: HomeAssistant,
    coordinator: MQSolarCoordinator,
    topic_code: str,
    charge_mode: int,
    max_current: float,
    max_voltage: float,
) -> None:
    """Send charge mode, current and voltage to the STM32 controller."""
    await async_send_command(
        hass,
        coordinator,
        topic_code,
        "set_charger_config",
        {
            "chargeMode": charge_mode,
            "maxCurrent": max_current,
            "maxVoltage": max_voltage,
        },
    )
