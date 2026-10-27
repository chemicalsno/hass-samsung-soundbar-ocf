"""Read-only soundbar state (firmware, network info, status fields)."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SoundbarCoordinator
from .discovery import iter_specs
from .entity import SoundbarEntity, pretty, short


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coordinator: SoundbarCoordinator = hass.data[DOMAIN][entry.entry_id]
    add(
        SoundbarSensor(coordinator, spec.path, spec.prop)
        for spec in iter_specs(coordinator.data)
        if spec.kind == "sensor"
    )


class SoundbarSensor(SoundbarEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SoundbarCoordinator, path: str, prop: str) -> None:
        super().__init__(coordinator, path)
        self._prop = prop
        name = short(prop)
        self._attr_name = pretty(name)
        self._attr_unique_id = f"{coordinator.device.get('di')}_{name}"

    @property
    def native_value(self) -> str | int | float | None:
        val = self._rep.get(self._prop)
        if isinstance(val, bool):
            return "on" if val else "off"
        if isinstance(val, (int, float, str)):
            return val
        return None
