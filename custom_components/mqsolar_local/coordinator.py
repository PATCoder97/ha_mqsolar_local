"""Data coordinator for the Mạnh Quân Solar integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MQSolarApiError, MQSolarLocalApi
from .const import UPDATE_INTERVAL_SECONDS

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

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.async_get_data()
        except MQSolarApiError as err:
            raise UpdateFailed(str(err)) from err
