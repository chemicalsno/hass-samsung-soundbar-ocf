"""Boolean soundbar controls (night mode, voice amplifier, etc.)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SoundbarCoordinator
from .discovery import iter_specs
from .entity import SoundbarEntity, pretty, short


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coordinator: SoundbarCoordinator = hass.data[DOMAIN][entry.entry_id]
    add(
        SoundbarSwitch(coordinator, spec.path, spec.prop)
        for spec in iter_specs(coordinator.data)
        if spec.kind == "switch"
    )


class SoundbarSwitch(SoundbarEntity, SwitchEntity):
    def __init__(self, coordinator: SoundbarCoordinator, path: str, prop: str) -> None:
        super().__init__(coordinator, path)
        self._prop = prop
        name = short(prop)
        self._attr_name = pretty(name)
        self._attr_unique_id = f"{coordinator.device.get('di')}_{name}"

    @property
    def is_on(self) -> bool | None:
        val = self._rep.get(self._prop)
        return bool(val) if isinstance(val, bool) else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_write(self._path, {self._prop: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_write(self._path, {self._prop: False})
