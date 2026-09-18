"""Shared charger-control helpers."""

from __future__ import annotations

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

    config: dict[str, float | int] = {
        "chargeMode": int(source["chargeMode"]),
        "maxCurrent": float(source["maxCurrent"]),
        "maxVoltage": float(source["maxVoltage"]),
    }
    for key in ("maxChargeCurrent", "maxChargeVoltage"):
        if key in source:
            config[key] = float(source[key])
    return config


def _store_config(
    coordinator: MQSolarCoordinator, config: dict[str, float | int]
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
    response = await async_get_charger_config(hass, coordinator, topic_code)
    _store_config(coordinator, _parse_config(response))
    return response


async def async_change_config(
    hass: HomeAssistant,
    coordinator: MQSolarCoordinator,
    key: str,
    value: float,
) -> None:
    """Change one setting while preserving the other values read from hardware."""
    config = current_config(coordinator)
    if config is None:
        raise HomeAssistantError(
            "Read charger configuration before changing current, voltage or mode"
        )

    updated = dict(config)
    updated[key] = value
    await async_set_charger_config(
        hass,
        coordinator,
        DEFAULT_MQTT_TOPIC_CODE,
        int(updated["chargeMode"]),
        float(updated["maxCurrent"]),
        float(updated["maxVoltage"]),
    )
    _store_config(coordinator, updated)
