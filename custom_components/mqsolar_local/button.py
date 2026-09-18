"""Button entities for MQ Solar Local."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_MQTT_TOPIC_CODE, DOMAIN
from .control import async_refresh_config
from .coordinator import MQSolarCoordinator
from .mqtt_commands import async_reboot_charge, async_restart

_LOGGER = logging.getLogger(__name__)

ButtonAction = Callable[[HomeAssistant, MQSolarCoordinator], Awaitable[None]]


async def _restart(hass: HomeAssistant, coordinator: MQSolarCoordinator) -> None:
    await async_restart(hass, coordinator, DEFAULT_MQTT_TOPIC_CODE)


async def _reboot_charger(hass: HomeAssistant, coordinator: MQSolarCoordinator) -> None:
    await async_reboot_charge(hass, coordinator, DEFAULT_MQTT_TOPIC_CODE)


@dataclass(frozen=True, kw_only=True)
class MQSolarButtonDescription(ButtonEntityDescription):
    """Describe an MQTT command button."""

    action: ButtonAction


RESTART_WIFI = MQSolarButtonDescription(
    key="restart_wifi",
    translation_key="restart_wifi",
    device_class=ButtonDeviceClass.RESTART,
    entity_category=EntityCategory.CONFIG,
    action=_restart,
)

CHARGER_BUTTONS = (
    MQSolarButtonDescription(
        key="reboot_charger",
        translation_key="reboot_charger",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        action=_reboot_charger,
    ),
    MQSolarButtonDescription(
        key="read_charger_config",
        translation_key="read_charger_config",
        entity_category=EntityCategory.CONFIG,
        action=async_refresh_config,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: MQSolarCoordinator = hass.data[DOMAIN][entry.entry_id]
    descriptions = (RESTART_WIFI,)
    if "charger" in coordinator.data:
        descriptions += CHARGER_BUTTONS
    async_add_entities(
        MQSolarButton(coordinator, description) for description in descriptions
    )

    if "charger" in coordinator.data:

        async def initial_refresh() -> None:
            try:
                await async_refresh_config(hass, coordinator)
            except Exception:  # Device may still use its factory cloud broker.
                _LOGGER.debug(
                    "Initial charger configuration read failed", exc_info=True
                )

        hass.async_create_task(initial_refresh())


class MQSolarButton(CoordinatorEntity[MQSolarCoordinator], ButtonEntity):
    """Representation of one MQTT command button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MQSolarCoordinator,
        description: MQSolarButtonDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        device_id = coordinator.data["_device_id"]
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, device_id)}}

    async def async_press(self) -> None:
        await self.entity_description.action(self.hass, self.coordinator)
