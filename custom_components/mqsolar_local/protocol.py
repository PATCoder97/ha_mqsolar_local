"""Pure helpers for the reverse-engineered MQTT wire format."""

from __future__ import annotations

import json
from typing import Any

MQTT_CHARGER_FIELDS = {
    "pv_voltage": "pvVoltage",
    "pv_current": "pvCurrent",
    "bat_voltage": "batVoltage",
    "bat_current": "batCurrent",
    "charge_power": "chargingPower",
    "today_kwh": "powerToday",
    "total_kwh": "powerTotal",
    "temperature": "temperature",
}

STATUS_TEXT_MAP = {
    "CHARGING": "Charging",
    "UNKNOWN": "Not charging",
    "FAULT_LOW": "Low voltage fault",
    "FAULT_HIGH": "High voltage fault",
}


def mqtt_topic_base(device_type: str, topic_code: str, device_id: str) -> str:
    """Build the topic base used by firmware v2.3.3."""
    return f"{device_type}_{topic_code}/{device_id}"


def mqtt_discovered_topic_base(message_topic: str, device_id: str) -> str | None:
    """Extract a device base from a live MQTT topic."""
    parts = message_topic.split("/")
    if len(parts) < 3 or parts[1] != device_id:
        return None
    return "/".join(parts[:2])


def mqtt_charger_measurements(payload: dict[str, Any]) -> dict[str, Any]:
    """Map MQTT field names to the field names used by sensor entities."""
    return {
        target: payload[source]
        for source, target in MQTT_CHARGER_FIELDS.items()
        if source in payload
    }


def normalize_status_text(value: Any) -> str | None:
    """Return readable English text for a firmware charger status."""
    if value is None:
        return None
    return STATUS_TEXT_MAP.get(str(value).strip().upper(), "Unknown")


def mqtt_command_payload(command: str, parameter: dict[str, Any] | None = None) -> str:
    """Build the compact command envelope parsed by the firmware."""
    payload: dict[str, Any] = {"command": command}
    if parameter is not None:
        payload["parameter"] = parameter
    return json.dumps(payload, separators=(",", ":"))
