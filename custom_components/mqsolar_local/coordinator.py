"""Data coordinator for the Mạnh Quân Solar integration."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MQSolarApiError, MQSolarLocalApi
from .const import UPDATE_INTERVAL_SECONDS
from .protocol import mqtt_charger_measurements

_LOGGER = logging.getLogger(__name__)


class MQSolarCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll one local MQ Solar device."""

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"MQ Solar Local {host}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.host = host
        self.api = MQSolarLocalApi(host, async_get_clientsession(hass))
        self.mqtt_unsubscribe: Callable[[], None] | None = None

    def async_set_mqtt_data(self, payload: dict[str, Any], topic_base: str) -> None:
        """Merge one live MQTT telemetry payload into coordinator data."""
        data = dict(self.data)
        charger = dict(data.get("charger", {}))
        charger.update(mqtt_charger_measurements(payload))
        data["charger"] = charger
        data["hasData"] = True
        data["_mqtt_topic_base"] = topic_base
        data["_mqtt_last_seen_monotonic"] = time.monotonic()
        data["_mqtt_connected"] = True

        status = dict(data.get("_status", {}))
        if "signalQuality" in payload:
            status["signalQuality"] = payload["signalQuality"]
        if "firmwareVersion" in payload:
            status["espVersion"] = payload["firmwareVersion"]
        data["_status"] = status
        self.async_set_updated_data(data)

    def async_unsubscribe_mqtt(self) -> None:
        """Stop the MQTT telemetry subscription."""
        if self.mqtt_unsubscribe is not None:
            self.mqtt_unsubscribe()
            self.mqtt_unsubscribe = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.async_get_data()
            # MQTT state is independent of the HTTP measurement payload.
            # Preserve it across HTTP refreshes.
            if self.data:
                for key in (
                    "_charger_config",
                    "_mqtt_topic_base",
                    "_mqtt_last_seen_monotonic",
                ):
                    if key in self.data:
                        data[key] = self.data[key]
            last_seen = data.get("_mqtt_last_seen_monotonic")
            data["_mqtt_connected"] = bool(
                isinstance(last_seen, (int, float))
                and time.monotonic() - last_seen < 10
            )
            return data
        except MQSolarApiError as err:
            raise UpdateFailed(str(err)) from err
