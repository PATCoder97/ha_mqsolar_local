"""Diagnostic binary sensors for MQ Solar Local."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MQSolarCoordinator


@dataclass(frozen=True, kw_only=True)
class MQSolarBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a boolean diagnostic value."""

    configured: bool = False


BINARY_SENSORS = (
    MQSolarBinarySensorDescription(
        key="mqtt_connected",
        translation_key="mqtt_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MQSolarBinarySensorDescription(
        key="mqtt_configured",
        translation_key="mqtt_configured",
        entity_category=EntityCategory.DIAGNOSTIC,
        configured=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: MQSolarCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MQSolarBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class MQSolarBinarySensor(CoordinatorEntity[MQSolarCoordinator], BinarySensorEntity):
    """Representation of one MQTT boolean diagnostic."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MQSolarCoordinator,
        description: MQSolarBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        device_id = coordinator.data["_device_id"]
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, device_id)}}

    @property
    def is_on(self) -> bool:
        if self.entity_description.configured:
            mqtt = self.coordinator.data.get("_status", {}).get("mqtt", {})
            return bool(mqtt.get("configured"))
        return bool(self.coordinator.data.get("_mqtt_connected"))
