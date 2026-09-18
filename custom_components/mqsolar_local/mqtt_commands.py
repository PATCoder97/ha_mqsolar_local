"""MQTT commands reverse-engineered from Mạnh Quân Solar firmware v2.3.3."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from homeassistant.components.mqtt.client import async_publish, async_subscribe
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import JsonObjectType

from .const import MQTT_RESPONSE_TIMEOUT, MQTT_TOPIC_DISCOVERY_TIMEOUT
from .coordinator import MQSolarCoordinator
from .protocol import (
    mqtt_command_payload,
    mqtt_discovered_topic_base,
    mqtt_topic_base,
)


def _device_topic_type(coordinator: MQSolarCoordinator) -> str:
    return (
        "grid_tie_inverter"
        if coordinator.data.get("_device_type") == "Inverter"
        else "mppt_charger"
    )


def _fallback_topic_base(coordinator: MQSolarCoordinator, topic_code: str) -> str:
    device_id = coordinator.data["_device_id"]
    if coordinator.data.get("_device_type") != "Inverter":
        # Confirmed on MPPT Wi-Fi firmware v2.3.3 after /api/mqtt/config:
        # topic "45a" publishes at 45a_45a/<deviceId>/data.
        return mqtt_topic_base(topic_code, topic_code, device_id)
    return mqtt_topic_base(_device_topic_type(coordinator), topic_code, device_id)


def _store_topic_base(coordinator: MQSolarCoordinator, topic_base: str) -> None:
    data = dict(coordinator.data)
    data["_mqtt_topic_base"] = topic_base
    coordinator.async_set_updated_data(data)


async def _async_resolve_topic_base(
    hass: HomeAssistant,
    coordinator: MQSolarCoordinator,
    topic_code: str,
) -> str:
    """Discover the actual prefix from live device traffic.

    Firmware v2.3.3 can publish under a prefix different from the embedded
    device-type string. For example, a device configured with topic ``45a``
    was observed publishing below ``45a_45a/<deviceId>``.
    """
    cached = coordinator.data.get("_mqtt_topic_base")
    if isinstance(cached, str):
        return cached

    device_id = str(coordinator.data["_device_id"])
    discovered: asyncio.Future[str] = hass.loop.create_future()

    async def message_received(message: Any) -> None:
        if discovered.done():
            return
        topic_base = mqtt_discovered_topic_base(str(message.topic), device_id)
        if topic_base is not None:
            discovered.set_result(topic_base)

    unsubscribe = await async_subscribe(
        hass, f"+/{device_id}/#", message_received, qos=0
    )
    try:
        async with asyncio.timeout(MQTT_TOPIC_DISCOVERY_TIMEOUT):
            topic_base = await discovered
    except TimeoutError:
        # Retain the reverse-engineered prefix as a compatibility fallback for
        # devices that do not publish periodic telemetry.
        topic_base = _fallback_topic_base(coordinator, topic_code)
    finally:
        unsubscribe()

    _store_topic_base(coordinator, topic_base)
    return topic_base


async def _async_publish_command(
    hass: HomeAssistant,
    topic_base: str,
    command: str,
    parameter: dict[str, Any] | None = None,
) -> None:
    await async_publish(
        hass,
        f"{topic_base}/cmd",
        mqtt_command_payload(command, parameter),
        qos=0,
        retain=False,
    )


async def async_send_command(
    hass: HomeAssistant,
    coordinator: MQSolarCoordinator,
    topic_code: str,
    command: str,
    parameter: dict[str, Any] | None = None,
) -> None:
    """Publish one firmware command without retaining it."""
    topic_base = await _async_resolve_topic_base(hass, coordinator, topic_code)
    await _async_publish_command(hass, topic_base, command, parameter)


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
    topic_base = await _async_resolve_topic_base(hass, coordinator, topic_code)
    response_topic = f"{topic_base}/#"
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
        await _async_publish_command(hass, topic_base, "get_charger_config")
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
