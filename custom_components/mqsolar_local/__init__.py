"""Mạnh Quân Solar local-only integration."""

from __future__ import annotations

import logging
from typing import cast

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CHARGE_MODE,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_CONFIRM,
    ATTR_MAX_CURRENT,
    ATTR_MAX_VOLTAGE,
    ATTR_TOPIC_CODE,
    CONF_HOST,
    DEFAULT_MQTT_TOPIC_CODE,
    DOMAIN,
    SERVICE_GET_CHARGER_CONFIG,
    SERVICE_REBOOT_CHARGE,
    SERVICE_RESTART,
    SERVICE_SET_CHARGER_CONFIG,
)
from .control import async_refresh_config, async_write_config
from .coordinator import MQSolarCoordinator
from .mqtt_commands import (
    async_reboot_charge,
    async_restart,
    async_subscribe_telemetry,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]

BASE_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_TOPIC_CODE, default=DEFAULT_MQTT_TOPIC_CODE): cv.string,
    }
)

SET_CHARGER_CONFIG_SCHEMA = BASE_COMMAND_SCHEMA.extend(
    {
        vol.Required(ATTR_CONFIRM): vol.All(cv.boolean, vol.Equal(True)),
        vol.Required(ATTR_CHARGE_MODE): vol.All(vol.Coerce(int), vol.In((0, 1, 2))),
        vol.Required(ATTR_MAX_CURRENT): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=200.0)
        ),
        vol.Required(ATTR_MAX_VOLTAGE): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=100.0)
        ),
    }
)


def _coordinator_for_call(hass: HomeAssistant, call: ServiceCall) -> MQSolarCoordinator:
    entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError("Mạnh Quân Solar config entry not found")
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError("Mạnh Quân Solar config entry is not loaded")
    try:
        return cast(MQSolarCoordinator, hass.data[DOMAIN][entry_id])
    except KeyError as err:
        raise ServiceValidationError("Mạnh Quân Solar coordinator not found") from err


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register MQTT command actions."""
    hass.data.setdefault(DOMAIN, {})

    async def handle_restart(call: ServiceCall) -> None:
        await async_restart(
            hass,
            _coordinator_for_call(hass, call),
            call.data[ATTR_TOPIC_CODE],
        )

    async def handle_reboot_charge(call: ServiceCall) -> None:
        await async_reboot_charge(
            hass,
            _coordinator_for_call(hass, call),
            call.data[ATTR_TOPIC_CODE],
        )

    async def handle_get_charger_config(call: ServiceCall) -> ServiceResponse:
        return await async_refresh_config(
            hass,
            _coordinator_for_call(hass, call),
            call.data[ATTR_TOPIC_CODE],
        )

    async def handle_set_charger_config(call: ServiceCall) -> None:
        await async_write_config(
            hass,
            _coordinator_for_call(hass, call),
            call.data[ATTR_TOPIC_CODE],
            call.data[ATTR_CHARGE_MODE],
            call.data[ATTR_MAX_CURRENT],
            call.data[ATTR_MAX_VOLTAGE],
        )

    hass.services.async_register(
        DOMAIN, SERVICE_RESTART, handle_restart, schema=BASE_COMMAND_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REBOOT_CHARGE,
        handle_reboot_charge,
        schema=BASE_COMMAND_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_CHARGER_CONFIG,
        handle_get_charger_config,
        schema=BASE_COMMAND_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CHARGER_CONFIG,
        handle_set_charger_config,
        schema=SET_CHARGER_CONFIG_SCHEMA,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a local device from a config entry."""
    coordinator = MQSolarCoordinator(hass, entry.data[CONF_HOST])
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    try:
        coordinator.mqtt_unsubscribe = await async_subscribe_telemetry(
            hass, coordinator
        )
    except HomeAssistantError:
        _LOGGER.warning(
            "MQTT telemetry is unavailable; continuing with local HTTP polling",
            exc_info=True,
        )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        if coordinator := hass.data[DOMAIN].get(entry.entry_id):
            coordinator.async_unsubscribe_mqtt()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
