"""Shared base entity and helpers for the soundbar integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OCF_PROP_PREFIX
from .coordinator import SoundbarCoordinator


def short(prop: str) -> str:
    """x.com.samsung.networkaudio.bassboost -> bassboost."""
    return prop[len(OCF_PROP_PREFIX):] if prop.startswith(OCF_PROP_PREFIX) else prop


def pretty(name: str) -> str:
    """camelCase/path tail -> 'Title Case' label."""
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i and not name[i - 1].isupper():
            out.append(" ")
        out.append(ch)
    return "".join(out).replace("_", " ").replace("/", " ").strip().title()


class SoundbarEntity(CoordinatorEntity[SoundbarCoordinator]):
    """Base: device info and availability tied to the resource being present."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SoundbarCoordinator, path: str) -> None:
        super().__init__(coordinator)
        self._path = path

    @property
    def device_info(self) -> DeviceInfo:
        dev = self.coordinator.device
        di = dev.get("di", "")
        return DeviceInfo(
            identifiers={(DOMAIN, di)},
            name=dev.get("n", "Samsung Soundbar"),
            manufacturer="Samsung",
            model=dev.get("n", "Soundbar"),
            sw_version=dev.get("dmv"),
        )

    @property
    def _rep(self) -> dict:
        return self.coordinator.data.get(self._path, {})

    @property
    def available(self) -> bool:
        return super().available and self._path in self.coordinator.data
