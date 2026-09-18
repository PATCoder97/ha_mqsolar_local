"""Shared charger-control helpers."""

from __future__ import annotations

import asyncio
import math
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_MQTT_TOPIC_CODE
from .coordinator import MQSolarCoordinator
from .mqtt_commands import async_get_charger_config, async_set_charger_config

CONFIG_KEY = "_charger_config"
REQUIRED_KEYS = ("chargeMode", "maxCurrent", "maxVoltage")


def current_config(coordinator: MQSolarCoordinator) -> dict[str, float | int] | None:
    """Return the cached charger configuration."""
    value = coordinator.data.get(CONFIG_KEY)
    return value if isinstance(value, dict) else None


def _parse_config(response: dict[str, Any]) -> dict[str, float | int]:
    candidates = [response]
    for key in ("parameter", "data"):
        nested = response.get(key)
        if isinstance(nested, dict):
            candidates.insert(0, nested)

    source = next(
        (
            candidate
            for candidate in candidates
            if all(key in candidate for key in REQUIRED_KEYS)
        ),
        None,
    )
    if source is None:
        raise HomeAssistantError(
            "Charger configuration response is missing required values"
        )

    try:
        mode = float(source["chargeMode"])
        if mode not in (0, 1, 2):
            raise ValueError("Invalid charge mode")
        config: dict[str, float | int] = {
            "chargeMode": int(mode),
            "maxCurrent": float(source["maxCurrent"]),
            "maxVoltage": float(source["maxVoltage"]),
        }
        for key in ("maxChargeCurrent", "maxChargeVoltage"):
            if key in source:
                config[key] = float(source[key])
        if any(not math.isfinite(value) or value < 0 for value in config.values()):
            raise ValueError("Invalid configuration value")
    except (TypeError, ValueError, OverflowError) as err:
        raise HomeAssistantError("Invalid charger configuration response") from err
    return config


def _store_config(
    coordinator: MQSolarCoordinator, config: dict[str, float | int] | None
) -> None:
    data = dict(coordinator.data)
    data[CONFIG_KEY] = config
    coordinator.async_set_updated_data(data)


async def async_refresh_config(
    hass: HomeAssistant,
    coordinator: MQSolarCoordinator,
    topic_code: str = DEFAULT_MQTT_TOPIC_CODE,
) -> dict[str, Any]:
    """Read and cache configuration from the charger over MQTT."""
    async with coordinator.config_lock:
        return await _read_config(hass, coordinator, topic_code)


async def _read_config(
    hass: HomeAssistant, coordinator: MQSolarCoordinator, topic_code: str,
) -> dict[str, Any]:
    if coordinator.data.get("_device_type") != "Charger":
        raise HomeAssistantError("Charger configuration is only supported on chargers")
    try:
        response = await async_get_charger_config(hass, coordinator, topic_code)
        _store_config(coordinator, _parse_config(response))
        return response
    except BaseException:
        _store_config(coordinator, None)
        raise


async def _write_and_verify(
    hass: HomeAssistant, coordinator: MQSolarCoordinator, topic_code: str,
    updated: dict[str, float | int], limits: dict[str, float | int],
) -> None:
    for key, limit_key, fallback in (
        ("maxCurrent", "maxChargeCurrent", 200.0),
        ("maxVoltage", "maxChargeVoltage", 100.0),
    ):
        value = updated[key]
        if not math.isfinite(value) or not 0 <= value <= limits.get(limit_key, fallback):
            raise HomeAssistantError(f"{key} is outside the device limit")
    if updated["chargeMode"] not in (0, 1, 2):
        raise HomeAssistantError("Invalid charge mode")
    # No optimistic state: a sent command is not confirmation of hardware state.
    _store_config(coordinator, None)
    await async_set_charger_config(
        hass, coordinator, topic_code, int(updated["chargeMode"]),
        float(updated["maxCurrent"]), float(updated["maxVoltage"]),
    )
    # Allow the controller time to apply the command, without sending it again.
    for attempt in range(3):
        if attempt:
            await asyncio.sleep(0.3)
        await _read_config(hass, coordinator, topic_code)
        actual = current_config(coordinator)
        assert actual is not None
        if all(math.isclose(actual[key], updated[key], rel_tol=0, abs_tol=1e-6)
               for key in REQUIRED_KEYS):
            return
    raise HomeAssistantError(
        "Charger read-back differs from the requested settings; "
        "displaying values read from the device. Read configuration again "
        "before retrying; the device may still be applying the command."
    )


async def async_write_config(
    hass: HomeAssistant, coordinator: MQSolarCoordinator, topic_code: str,
    charge_mode: int, max_current: float, max_voltage: float,
) -> None:
    """Serialize service writes and verify the device's configuration."""
    async with coordinator.config_lock:
        await _read_config(hass, coordinator, topic_code)
        limits = current_config(coordinator)
        assert limits is not None
        await _write_and_verify(hass, coordinator, topic_code, {
            "chargeMode": charge_mode, "maxCurrent": max_current,
            "maxVoltage": max_voltage,
        }, limits)


async def async_change_config(
    hass: HomeAssistant,
    coordinator: MQSolarCoordinator,
    key: str,
    value: float,
) -> None:
    """Change one setting while preserving the other values read from hardware."""
    if key not in REQUIRED_KEYS:
        raise HomeAssistantError("Unsupported charger setting")
    async with coordinator.config_lock:
        await _read_config(hass, coordinator, DEFAULT_MQTT_TOPIC_CODE)
        config = current_config(coordinator)
        assert config is not None
        updated = dict(config)
        updated[key] = value
        await _write_and_verify(
            hass, coordinator, DEFAULT_MQTT_TOPIC_CODE, updated, config
        )
