"""Number entities for charger limits."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .control import async_change_config, current_config
from .coordinator import MQSolarCoordinator


@dataclass(frozen=True, kw_only=True)
class MQSolarNumberDescription(NumberEntityDescription):
    """Describe one charger configuration number."""

    limit_key: str
    fallback_max: float


NUMBERS = (
    MQSolarNumberDescription(
        key="maxCurrent",
        translation_key="max_current",
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_min_value=0.0,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        limit_key="maxChargeCurrent",
        fallback_max=200.0,
    ),
    MQSolarNumberDescription(
        key="maxVoltage",
        translation_key="max_voltage",
        device_class=NumberDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        native_min_value=0.0,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        limit_key="maxChargeVoltage",
        fallback_max=100.0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: MQSolarCoordinator = hass.data[DOMAIN][entry.entry_id]
    if "charger" in coordinator.data:
        async_add_entities(
            MQSolarNumber(coordinator, description) for description in NUMBERS
        )


class MQSolarNumber(CoordinatorEntity[MQSolarCoordinator], NumberEntity):
    """A charger current or voltage limit."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MQSolarCoordinator,
        description: MQSolarNumberDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        device_id = coordinator.data["_device_id"]
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, device_id)}}

    @property
    def available(self) -> bool:
        return super().available and current_config(self.coordinator) is not None

    @property
    def native_value(self) -> float | None:
        config = current_config(self.coordinator)
        return float(config[self.entity_description.key]) if config else None

    @property
    def native_max_value(self) -> float:
        config = current_config(self.coordinator)
        if config and self.entity_description.limit_key in config:
            return float(config[self.entity_description.limit_key])
        return self.entity_description.fallback_max

    async def async_set_native_value(self, value: float) -> None:
        await async_change_config(
            self.hass, self.coordinator, self.entity_description.key, value
        )
