"""Polling coordinator for the soundbar's OCF resources.

Control resources poll every interval; diagnostic resources (firmware, MACs,
network info) poll every SLOW_POLL_FACTOR-th cycle and are cached between, to
keep the DTLS traffic and device load light.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_POLL_INTERVAL, DOMAIN, SLOW_POLL_FACTOR
from .ocf_client import OcfError, OcfPskClient

_LOGGER = logging.getLogger(__name__)


class SoundbarCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Holds the DTLS client and the latest representation of each resource."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: OcfPskClient,
        fast_paths: set[str],
        slow_paths: set[str],
        device: dict,
        initial: dict[str, dict],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
        )
        self.client = client
        self.device = device
        self.fast_paths = sorted(fast_paths)
        self.slow_paths = sorted(slow_paths)
        self.paths = sorted(fast_paths | slow_paths)
        self._slow_cache = {p: initial[p] for p in self.slow_paths if p in initial}
        self._cycle = 0

    async def _async_update_data(self) -> dict[str, dict]:
        self._cycle += 1
        try:
            fast = await self.hass.async_add_executor_job(self.client.poll, self.fast_paths)
        except OcfError as err:
            raise UpdateFailed(str(err)) from err
        if not fast:
            raise UpdateFailed("no control resources answered this poll")

        if self.slow_paths and self._cycle % SLOW_POLL_FACTOR == 1:
            try:
                slow = await self.hass.async_add_executor_job(self.client.poll, self.slow_paths)
            except OcfError as err:
                _LOGGER.debug("diagnostic poll failed, keeping cached values: %s", err)
            else:
                if slow:
                    self._slow_cache = slow

        return {**self._slow_cache, **fast}

    async def async_write(self, path: str, properties: dict) -> None:
        """POST an update, then refresh so entities reflect the new state."""
        await self.hass.async_add_executor_job(self.client.write, path, properties)
        await self.async_request_refresh()
