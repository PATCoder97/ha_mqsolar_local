"""Select entity for the charger mode."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .control import async_change_config, current_config
from .coordinator import MQSolarCoordinator

OPTIONS = ["0", "1"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: MQSolarCoordinator = hass.data[DOMAIN][entry.entry_id]
    if "charger" in coordinator.data:
        async_add_entities([MQSolarChargeModeSelect(coordinator)])


class MQSolarChargeModeSelect(CoordinatorEntity[MQSolarCoordinator], SelectEntity):
    """Firmware charge mode selector."""

    _attr_has_entity_name = True
    _attr_translation_key = "charge_mode"
    _attr_options = OPTIONS
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: MQSolarCoordinator) -> None:
        super().__init__(coordinator)
        device_id = coordinator.data["_device_id"]
        self._attr_unique_id = f"{device_id}_chargeMode"
        self._attr_device_info = {"identifiers": {(DOMAIN, device_id)}}

    @property
    def available(self) -> bool:
        return super().available and current_config(self.coordinator) is not None

    @property
    def current_option(self) -> str | None:
        config = current_config(self.coordinator)
        return str(int(config["chargeMode"])) if config else None

    async def async_select_option(self, option: str) -> None:
        await async_change_config(
            self.hass, self.coordinator, "chargeMode", int(option)
        )
