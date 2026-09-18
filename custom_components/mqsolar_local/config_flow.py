"""Config flow for local Mạnh Quân Solar devices."""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MQSolarApiError, MQSolarLocalApi
from .const import CONF_HOST, DOMAIN, SCAN_CONCURRENCY, SCAN_TIMEOUT


def _local_ipv4() -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return str(sock.getsockname()[0])
    except OSError:
        return None
    finally:
        sock.close()


async def _validate_host(hass: HomeAssistant, host: str) -> dict[str, Any]:
    api = MQSolarLocalApi(host, async_get_clientsession(hass))
    return await api.async_get_status()


async def _scan_network(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    local_ip = await hass.async_add_executor_job(_local_ipv4)
    if not local_ip or local_ip.startswith("127."):
        return {}

    prefix = local_ip.rsplit(".", 1)[0]
    session = async_get_clientsession(hass)
    semaphore = asyncio.Semaphore(SCAN_CONCURRENCY)

    async def check(index: int) -> tuple[str, dict[str, Any]] | None:
        host = f"{prefix}.{index}"
        async with semaphore:
            try:
                status = await MQSolarLocalApi(host, session).async_get_status(
                    SCAN_TIMEOUT
                )
            except MQSolarApiError:
                return None
        return host, status

    results = await asyncio.gather(*(check(index) for index in range(1, 255)))
    return {result[0]: result[1] for result in results if result is not None}


class MQSolarLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a local MQ Solar device."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        """Show the local-only setup methods."""
        return self.async_show_menu(step_id="user", menu_options=["scan", "manual"])

    async def _create_entry(self, host: str, status: dict[str, Any]) -> Any:
        device_id = str(status["deviceId"])
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        device_type = "Inverter" if str(status.get("device_type")) == "1" else "MPPT"
        return self.async_create_entry(
            title=f"MQ {device_type} {device_id}", data={CONF_HOST: host}
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> Any:
        """Configure a device by IP address or hostname."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                status = await _validate_host(self.hass, host)
            except MQSolarApiError:
                errors["base"] = "cannot_connect"
            else:
                return await self._create_entry(host, status)

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_scan(self, user_input: dict[str, Any] | None = None) -> Any:
        """Scan the current /24 subnet and let the user choose a device."""
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                status = await _validate_host(self.hass, host)
            except MQSolarApiError:
                return self.async_show_form(
                    step_id="scan",
                    data_schema=vol.Schema(
                        {vol.Required(CONF_HOST): vol.In(self._discovered_devices)}
                    ),
                    errors={"base": "cannot_connect"},
                )
            return await self._create_entry(host, status)

        discovered = await _scan_network(self.hass)
        if not discovered:
            return self.async_abort(reason="no_devices_found")

        self._discovered_devices = {
            host: f"{status.get('deviceId', 'Unknown')} ({host})"
            for host, status in discovered.items()
        }
        return self.async_show_form(
            step_id="scan",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST): vol.In(self._discovered_devices)}
            ),
        )
