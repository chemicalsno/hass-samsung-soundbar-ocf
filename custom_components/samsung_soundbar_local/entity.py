"""Shared base entity and helpers for the soundbar integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OCF_PROP_PREFIX
from .coordinator import SoundbarCoordinator


def short(prop: str) -> str:
    """x.com.samsung.networkaudio.bassboost -> bassboost."""
    return prop[len(OCF_PROP_PREFIX):] if prop.startswith(OCF_PROP_PREFIX) else prop


# Acronyms whose casing the title-caser would mangle, applied per word.
_ACRONYMS: dict[str, str] = {
    "bt": "Bluetooth",
    "wifi": "Wi-Fi",
    "mac": "MAC",
    "hdmi": "HDMI",
    "usb": "USB",
    "eq": "EQ",
    "ip": "IP",
    "id": "ID",
    "duid": "DUID",
    "micom": "MICOM",
}

# Smashed-together OCF keys the splitter cannot break on its own. Keyed by the
# property name normalized (separators dropped, lowercased) so camelCase and
# snake_case spellings of the same key both match.
_DISPLAY_NAMES: dict[str, str] = {
    "audiosync": "Audio Sync",
    "bassboost": "Bass Boost",
    "voiceamplifier": "Voice Amplifier",
    "nightmode": "Night Mode",
    "autoeqmode": "Auto EQ Mode",
    "currenteqmode": "Current EQ Mode",
    "calibrationstatus": "Calibration Status",
    "tunestatus": "Tune Status",
    "bluetoothmac": "Bluetooth MAC",
    "wifimac": "Wi-Fi MAC",
    "hwduid": "Hardware DUID",
    "micsupport": "Mic Support",
    "micomversion": "MICOM Version",
    "numofhdmi": "HDMI Count",
    "btappready": "Bluetooth App Ready",
    "uniquedevicenumber": "Unique Device Number",
    "eqname": "EQ Preset",
    "passthruenable": "Pass Through",
}


def pretty(name: str) -> str:
    """OCF property key -> human 'Title Case' label."""
    normalized = name.replace("_", "").replace("/", "").lower()
    if normalized in _DISPLAY_NAMES:
        return _DISPLAY_NAMES[normalized]
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i and not name[i - 1].isupper():
            out.append(" ")
        out.append(ch)
    words = "".join(out).replace("_", " ").replace("/", " ").split()
    return " ".join(_ACRONYMS.get(w.lower(), w.title()) for w in words)


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
