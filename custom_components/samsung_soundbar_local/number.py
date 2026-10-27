"""Numeric soundbar controls (woofer level, EQ bands, boosts)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SoundbarCoordinator
from .discovery import iter_specs
from .entity import SoundbarEntity, pretty, short

# Known device ranges; anything else gets a permissive default and the device
# rejects out-of-range writes.
RANGES: dict[str, tuple[float, float, float]] = {
    "woofer": (-12, 6, 1),
    "channelVolume": (-6, 6, 1),
    "bass": (-6, 6, 1),
    "treble": (-6, 6, 1),
}
DEFAULT_RANGE = (-100.0, 100.0, 1.0)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coordinator: SoundbarCoordinator = hass.data[DOMAIN][entry.entry_id]
    add(
        SoundbarNumber(coordinator, spec.path, spec.prop)
        for spec in iter_specs(coordinator.data)
        if spec.kind == "number"
    )


class SoundbarNumber(SoundbarEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: SoundbarCoordinator, path: str, prop: str) -> None:
        super().__init__(coordinator, path)
        self._prop = prop
        name = short(prop)
        self._attr_translation_key = name
        self._attr_name = pretty(name)
        self._attr_unique_id = f"{coordinator.device.get('di')}_{name}"
        lo, hi, step = RANGES.get(name, DEFAULT_RANGE)
        self._attr_native_min_value = lo
        self._attr_native_max_value = hi
        self._attr_native_step = step

    @property
    def native_value(self) -> float | None:
        val = self._rep.get(self._prop)
        return float(val) if isinstance(val, (int, float)) else None

    async def async_set_native_value(self, value: float) -> None:
        payload = int(value) if float(value).is_integer() else value
        await self.coordinator.async_write(self._path, {self._prop: payload})
