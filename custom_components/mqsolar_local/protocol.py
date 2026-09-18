"""Pure helpers for the reverse-engineered MQTT wire format."""

from __future__ import annotations

import json
from typing import Any


def mqtt_topic_base(device_type: str, topic_code: str, device_id: str) -> str:
    """Build the topic base used by firmware v2.3.3."""
    return f"{device_type}_{topic_code}/{device_id}"


def mqtt_command_payload(
    command: str, parameter: dict[str, Any] | None = None
) -> str:
    """Build the compact command envelope parsed by the firmware."""
    payload: dict[str, Any] = {"command": command}
    if parameter is not None:
        payload["parameter"] = parameter
    return json.dumps(payload, separators=(",", ":"))
