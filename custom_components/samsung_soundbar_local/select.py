"""Enumerated soundbar controls (EQ mode, spacefit, etc.)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
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
        SoundbarSelect(coordinator, spec.path, spec.prop, list(spec.options or ()), spec.write_extra)
        for spec in iter_specs(coordinator.data)
        if spec.kind == "select"
    )


class SoundbarSelect(SoundbarEntity, SelectEntity):
    def __init__(
        self,
        coordinator: SoundbarCoordinator,
        path: str,
        prop: str,
        options: list[str],
        write_extra: tuple[tuple[str, str], ...] | None = None,
    ) -> None:
        super().__init__(coordinator, path)
        self._prop = prop
        self._write_extra = dict(write_extra or ())
        name = short(prop)
        self._attr_name = "EQ Preset" if name == "EQname" else pretty(name)
        self._attr_unique_id = f"{coordinator.device.get('di')}_{name}"
        self._attr_options = options

    @property
    def current_option(self) -> str | None:
        val = self._rep.get(self._prop)
        return val if isinstance(val, str) else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_write(self._path, {self._prop: option, **self._write_extra})
