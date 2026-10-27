"""Core media_player: power, volume, mute, source, sound mode."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, OCF_PROP_PREFIX
from .coordinator import SoundbarCoordinator
from .discovery import _supported_options
from .entity import SoundbarEntity

POWER = "/sec/networkaudio/switch/binary"
AUDIO = "/sec/networkaudio/audio"
SOUND_FROM = "/sec/networkaudio/soundFrom"
SOUND_MODE = "/sec/networkaudio/soundmode"
VOLUME_MAX = 100


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coordinator: SoundbarCoordinator = hass.data[DOMAIN][entry.entry_id]
    add([SoundbarMediaPlayer(coordinator)])


class SoundbarMediaPlayer(SoundbarEntity, MediaPlayerEntity):
    _attr_name = None  # the device name is the entity name

    def __init__(self, coordinator: SoundbarCoordinator) -> None:
        super().__init__(coordinator, AUDIO)
        self._attr_unique_id = f"{coordinator.device.get('di')}_media_player"

    def _rep_of(self, path: str) -> dict:
        return self.coordinator.data.get(path, {})

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(self.coordinator.data)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        data = self.coordinator.data
        feat = MediaPlayerEntityFeature(0)
        if AUDIO in data:
            feat |= MediaPlayerEntityFeature.VOLUME_SET | MediaPlayerEntityFeature.VOLUME_MUTE
        if POWER in data:
            feat |= MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
        if self.source_list:
            feat |= MediaPlayerEntityFeature.SELECT_SOURCE
        if self.sound_mode_list:
            feat |= MediaPlayerEntityFeature.SELECT_SOUND_MODE
        return feat

    @property
    def state(self) -> MediaPlayerState:
        power = self._rep_of(POWER).get("value")
        if power is False:
            return MediaPlayerState.OFF
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        vol = self._rep_of(AUDIO).get("volume")
        return vol / VOLUME_MAX if isinstance(vol, (int, float)) else None

    @property
    def is_volume_muted(self) -> bool | None:
        mute = self._rep_of(AUDIO).get("mute")
        return bool(mute) if isinstance(mute, bool) else None

    @property
    def source(self) -> str | None:
        # soundFrom is a complex object on this bar, not an enum; show the input label.
        sf = self._rep_of(SOUND_FROM).get(OCF_PROP_PREFIX + "soundFrom")
        if isinstance(sf, dict):
            return sf.get("connectionType") or sf.get("name")
        return sf if isinstance(sf, str) else None

    @property
    def source_list(self) -> list[str] | None:
        # No supported-values list is advertised, so source is read-only (no SELECT_SOURCE).
        return None

    @property
    def sound_mode(self) -> str | None:
        return self._rep_of(SOUND_MODE).get(OCF_PROP_PREFIX + "soundmode")

    @property
    def sound_mode_list(self) -> list[str] | None:
        opts = _supported_options(self._rep_of(SOUND_MODE), "soundmode")
        return list(opts) if opts else None

    async def async_set_volume_level(self, volume: float) -> None:
        await self.coordinator.async_write(AUDIO, {"volume": round(volume * VOLUME_MAX)})

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.async_write(AUDIO, {"mute": mute})

    async def async_turn_on(self) -> None:
        await self.coordinator.async_write(POWER, {"value": True})

    async def async_turn_off(self) -> None:
        await self.coordinator.async_write(POWER, {"value": False})

    async def async_select_source(self, source: str) -> None:
        await self.coordinator.async_write(SOUND_FROM, {OCF_PROP_PREFIX + "soundFrom": source})

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        await self.coordinator.async_write(SOUND_MODE, {OCF_PROP_PREFIX + "soundmode": sound_mode})
