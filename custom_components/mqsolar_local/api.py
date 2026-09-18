"""Local HTTP client for Mạnh Quân Solar devices."""

from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import (
    API_CHARGER_DATA,
    API_INVERTER_DATA,
    API_STATUS,
    REQUEST_TIMEOUT,
)


class MQSolarApiError(Exception):
    """Base exception raised by the local API client."""


class MQSolarConnectionError(MQSolarApiError):
    """Raised when the device cannot be reached."""


class MQSolarInvalidResponseError(MQSolarApiError):
    """Raised when the device response is not usable."""


class MQSolarLocalApi:
    """Read data directly from one device over the LAN."""

    def __init__(self, host: str, session: ClientSession) -> None:
        self.host = host.strip().removeprefix("http://").removeprefix("https://").rstrip("/")
        self._session = session
        self._data_endpoint: str | None = None
        self.status: dict[str, Any] = {}

    async def _get_json(self, path: str, timeout: int = REQUEST_TIMEOUT) -> dict[str, Any]:
        try:
            async with asyncio.timeout(timeout):
                async with self._session.get(f"http://{self.host}{path}") as response:
                    if response.status != 200:
                        raise MQSolarInvalidResponseError(
                            f"GET {path} returned HTTP {response.status}"
                        )
                    data = await response.json(content_type=None)
        except MQSolarApiError:
            raise
        except (TimeoutError, ClientError) as err:
            raise MQSolarConnectionError(f"Unable to reach {self.host}: {err}") from err
        except (TypeError, ValueError) as err:
            raise MQSolarInvalidResponseError(f"Invalid JSON from {path}") from err

        if not isinstance(data, dict):
            raise MQSolarInvalidResponseError(f"GET {path} did not return a JSON object")
        return data

    async def async_get_status(self, timeout: int = REQUEST_TIMEOUT) -> dict[str, Any]:
        """Return device identity and connectivity information."""
        status = await self._get_json(API_STATUS, timeout)
        if not status.get("deviceId"):
            raise MQSolarInvalidResponseError("Status response has no deviceId")
        self.status = status
        return status

    async def _discover_data_endpoint(self) -> str:
        candidates = (API_CHARGER_DATA, API_INVERTER_DATA)
        for endpoint in candidates:
            try:
                await self._get_json(endpoint, 2)
            except MQSolarApiError:
                continue
            self._data_endpoint = endpoint
            return endpoint
        raise MQSolarInvalidResponseError("No supported local data endpoint found")

    @staticmethod
    def _normalize(data: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data)

        if "charger" not in normalized and "inverter" not in normalized:
            if "pvVoltage" in normalized or "pv_voltage" in normalized:
                normalized = {"charger": data}
            elif "dcVoltage" in normalized or "dc_voltage" in normalized:
                normalized = {"inverter": data}
            elif str(status.get("device_type")) == "1":
                normalized = {"inverter": data}
            else:
                normalized = {"charger": data}

        device_type = "Inverter" if "inverter" in normalized else "Charger"
        normalized["_device_id"] = str(status.get("deviceId", "unknown"))
        normalized["_device_type"] = device_type
        normalized["_status"] = status
        normalized["hasData"] = bool(data.get("hasData", True))
        return normalized

    async def async_get_data(self) -> dict[str, Any]:
        """Return normalized charger or inverter measurements."""
        status = await self.async_get_status()
        endpoint = self._data_endpoint or await self._discover_data_endpoint()
        try:
            data = await self._get_json(endpoint)
        except MQSolarInvalidResponseError:
            self._data_endpoint = None
            endpoint = await self._discover_data_endpoint()
            data = await self._get_json(endpoint)
        return self._normalize(data, status)
