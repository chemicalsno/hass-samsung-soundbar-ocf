"""Config flow for Samsung Soundbar Local."""

from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .const import CONF_PSK_IDENTITY, CONF_PSK_KEY, DOMAIN
from .ocf_client import OcfError, OcfPskClient

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PSK_IDENTITY): str,  # owner UUID (the OwnerPSK identity)
        vol.Required(CONF_PSK_KEY): str,       # OwnerPSK hex, 32 chars
    }
)


def _validate_input(data: dict[str, Any]) -> dict:
    """Blocking: check the credential shape, then handshake and read /oic/d."""
    uuid.UUID(data[CONF_PSK_IDENTITY])
    key = bytes.fromhex(data[CONF_PSK_KEY])
    if len(key) not in (16, 32):
        raise ValueError("psk_key must be 16 or 32 bytes (32 or 64 hex chars)")
    client = OcfPskClient(data[CONF_HOST], data[CONF_PSK_IDENTITY], data[CONF_PSK_KEY])
    try:
        return client.device()
    finally:
        client.close()


class SoundbarLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the soundbar."""

    VERSION = 2

    async def async_step_user(self, user_input: dict | None = None) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                device = await self.hass.async_add_executor_job(_validate_input, user_input)
            except ValueError:  # bad UUID or hex
                errors["base"] = "invalid_credential"
            except OcfError:
                errors["base"] = "cannot_connect"
            else:
                di = device.get("di") or user_input[CONF_HOST]
                await self.async_set_unique_id(di)
                self._abort_if_unique_id_configured()
                title = device.get("n", "Samsung Soundbar")
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
