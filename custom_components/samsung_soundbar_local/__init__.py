"""Samsung Soundbar Local: cloud-free OCF/DTLS-PSK control."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_PSK_IDENTITY,
    CONF_PSK_KEY,
    DOMAIN,
    NETWORKAUDIO_RESOURCES,
    PLATFORMS,
)
from .coordinator import SoundbarCoordinator
from .discovery import control_paths
from .ocf_client import OcfError, OcfPskClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a soundbar from a config entry."""
    client = OcfPskClient(
        host=entry.data[CONF_HOST],
        identity=entry.data[CONF_PSK_IDENTITY],
        key=entry.data[CONF_PSK_KEY],
    )

    def _probe() -> tuple[dict, dict[str, dict]]:
        device = client.device()
        reps = client.discover(NETWORKAUDIO_RESOURCES)
        return device, reps

    try:
        device, reps = await hass.async_add_executor_job(_probe)
    except OcfError as err:
        await hass.async_add_executor_job(client.close)
        raise ConfigEntryNotReady(f"cannot reach soundbar: {err}") from err

    fast = control_paths(reps)
    slow = set(reps) - fast
    coordinator = SoundbarCoordinator(hass, client, fast, slow, device, reps)
    coordinator.async_set_updated_data(reps)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: SoundbarCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await hass.async_add_executor_job(coordinator.client.close)
    return unload_ok
