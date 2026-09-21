"""Sensor platform for Mạnh Quân Solar."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MQSolarCoordinator
from .protocol import normalize_status_text


@dataclass(frozen=True, kw_only=True)
class MQSolarSensorDescription(SensorEntityDescription):
    """Describe one value inside a charger/inverter payload."""

    section: str | None = None
    status_key: bool = False
    path: tuple[str, ...] | None = None


CHARGER_SENSORS: tuple[MQSolarSensorDescription, ...] = (
    MQSolarSensorDescription(
        key="pvVoltage",
        translation_key="pv_voltage",
        section="charger",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MQSolarSensorDescription(
        key="pvCurrent",
        translation_key="pv_current",
        section="charger",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MQSolarSensorDescription(
        key="batVoltage",
        translation_key="battery_voltage",
        section="charger",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    MQSolarSensorDescription(
        key="batCurrent",
        translation_key="battery_current",
        section="charger",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MQSolarSensorDescription(
        key="chargingPower",
        translation_key="charging_power",
        section="charger",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MQSolarSensorDescription(
        key="powerToday",
        translation_key="energy_today",
        section="charger",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    MQSolarSensorDescription(
        key="powerTotal",
        translation_key="energy_total",
        section="charger",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    MQSolarSensorDescription(
        key="temperature",
        translation_key="temperature",
        section="charger",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MQSolarSensorDescription(
        key="statusText", translation_key="status", section="charger"
    ),
)

INVERTER_SENSORS: tuple[MQSolarSensorDescription, ...] = (
    MQSolarSensorDescription(
        key="dcVoltage",
        translation_key="dc_voltage",
        section="inverter",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MQSolarSensorDescription(
        key="acVoltage",
        translation_key="ac_voltage",
        section="inverter",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MQSolarSensorDescription(
        key="outputPower",
        translation_key="output_power",
        section="inverter",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MQSolarSensorDescription(
        key="limiterPower",
        translation_key="grid_power",
        section="inverter",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MQSolarSensorDescription(
        key="limiterToday",
        translation_key="grid_today",
        section="inverter",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    MQSolarSensorDescription(
        key="limiterTotal",
        translation_key="grid_total",
        section="inverter",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    MQSolarSensorDescription(
        key="temperature",
        translation_key="temperature",
        section="inverter",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MQSolarSensorDescription(
        key="energyToday",
        translation_key="energy_today",
        section="inverter",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    MQSolarSensorDescription(
        key="energyTotal",
        translation_key="energy_total",
        section="inverter",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    MQSolarSensorDescription(
        key="statusText", translation_key="status", section="inverter"
    ),
)

DIAGNOSTIC_SENSORS: tuple[MQSolarSensorDescription, ...] = (
    MQSolarSensorDescription(
        key="signalQuality",
        translation_key="signal_quality",
        status_key=True,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MQSolarSensorDescription(
        key="rssi",
        translation_key="wifi_rssi",
        status_key=True,
        native_unit_of_measurement="dBm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MQSolarSensorDescription(
        key="wifiSSID",
        translation_key="wifi_ssid",
        status_key=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MQSolarSensorDescription(
        key="espVersion",
        translation_key="esp_version",
        status_key=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MQSolarSensorDescription(
        key="wifiIP",
        translation_key="wifi_ip",
        status_key=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MQSolarSensorDescription(
        key="mqttHost",
        translation_key="mqtt_host",
        path=("_status", "mqtt", "host"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MQSolarSensorDescription(
        key="mqttPort",
        translation_key="mqtt_port",
        path=("_status", "mqtt", "port"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MQSolarSensorDescription(
        key="mqttTopic",
        translation_key="mqtt_topic",
        path=("_mqtt_topic_base",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for one local device."""
    coordinator: MQSolarCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_id = coordinator.data["_device_id"]
    entity_registry = er.async_get(hass)
    legacy_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{device_id}_stm32Version"
    )
    if legacy_entity_id is not None:
        entity_registry.async_remove(legacy_entity_id)

    measurements = (
        CHARGER_SENSORS if "charger" in coordinator.data else INVERTER_SENSORS
    )
    async_add_entities(
        MQSolarSensor(coordinator, description)
        for description in (*measurements, *DIAGNOSTIC_SENSORS)
    )


class MQSolarSensor(CoordinatorEntity[MQSolarCoordinator], SensorEntity):
    """Representation of one local MQ Solar value."""

    entity_description: MQSolarSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MQSolarCoordinator,
        description: MQSolarSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        device_id = coordinator.data["_device_id"]
        device_type = coordinator.data["_device_type"]
        status = coordinator.data.get("_status", {})
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=f"MQ {device_type} {device_id}",
            manufacturer="Mạnh Quân",
            model=device_type,
            sw_version=status.get("espVersion"),
        )

    @property
    def native_value(self) -> Any:
        """Return the latest local value."""
        description = self.entity_description
        if description.path is not None:
            value: Any = self.coordinator.data
            for key in description.path:
                if not isinstance(value, dict):
                    return None
                value = value.get(key)
            return value
        if description.status_key:
            return self.coordinator.data.get("_status", {}).get(description.key)
        if not self.coordinator.data.get("hasData", True):
            return None
        value = self.coordinator.data.get(description.section or "", {}).get(
            description.key
        )
        if description.key == "statusText":
            return normalize_status_text(value)
        return value
