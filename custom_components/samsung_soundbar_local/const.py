"""Constants for the Samsung Soundbar Local (OCF/DTLS-PSK) integration."""

from __future__ import annotations

DOMAIN = "samsung_soundbar_local"

PLATFORMS = ["media_player", "number", "select", "switch", "sensor"]

CONF_PSK_IDENTITY = "psk_identity"  # owner UUID, carried as 16 raw bytes
CONF_PSK_KEY = "psk_key"            # OwnerPSK, hex of 16 bytes

DEFAULT_POLL_INTERVAL = 30  # seconds, for control resources
SLOW_POLL_FACTOR = 20       # diagnostics poll every Nth cycle (~10 min)

# Resources present on HW-Q900C fw HW-Q900CWWB-1002.0 (Q900C_NETWORKAUDIO_VOCAB.md,
# swept 2026-08-15). Probed at runtime; absent ones are simply skipped.
NETWORKAUDIO_RESOURCES: tuple[str, ...] = (
    "/sec/networkaudio/activeVoiceAmplifier",
    "/sec/networkaudio/advancedaudio",
    "/sec/networkaudio/audio",
    "/sec/networkaudio/audioPrompt",
    "/sec/networkaudio/audiosync",
    "/sec/networkaudio/autoPowerDown",
    "/sec/networkaudio/autoUpdate",
    "/sec/networkaudio/autoeq",
    "/sec/networkaudio/btPairingMode",
    "/sec/networkaudio/channelVolume",
    "/sec/networkaudio/currentEQMode",
    "/sec/networkaudio/deviceinfo",
    "/sec/networkaudio/eq",
    "/sec/networkaudio/feature",
    "/sec/networkaudio/infoLink",
    "/sec/networkaudio/installationType",
    "/sec/networkaudio/lastConnections",
    "/sec/networkaudio/mic",
    "/sec/networkaudio/mode",
    "/sec/networkaudio/musicinfo",
    "/sec/networkaudio/networkInfo",
    "/sec/networkaudio/passThrough",
    "/sec/networkaudio/playback",
    "/sec/networkaudio/soundFrom",
    "/sec/networkaudio/soundmode",
    "/sec/networkaudio/spacefitSound",
    "/sec/networkaudio/speakerStatus",
    "/sec/networkaudio/surroundspeaker",
    "/sec/networkaudio/swUpdate",
    "/sec/networkaudio/switch/binary",
    "/sec/networkaudio/symphony",
    "/sec/networkaudio/tone",
    "/sec/networkaudio/versionInfo",
    "/sec/networkaudio/woofer",
)

OCF_PROP_PREFIX = "x.com.samsung.networkaudio."

# Representation keys that are never user controls (OCF plumbing / link metadata).
NON_CONTROL_KEYS: frozenset[str] = frozenset(
    {"rt", "if", "n", "id", "p", "eps", "links", "di", "icv", "dmv"}
)

# Resources the media_player reads directly; always fast-polled.
MEDIA_PLAYER_PATHS: frozenset[str] = frozenset(
    {
        "/sec/networkaudio/switch/binary",
        "/sec/networkaudio/audio",
        "/sec/networkaudio/soundFrom",
        "/sec/networkaudio/soundmode",
    }
)

# Of those, the ones the media_player owns exclusively, so the generic factories
# skip them to avoid duplicate entities. soundmode is intentionally excluded: it
# also gets its own Sound Mode select while the media_player keeps reading it.
MEDIA_PLAYER_SKIP_PATHS: frozenset[str] = MEDIA_PLAYER_PATHS - {"/sec/networkaudio/soundmode"}

# Property -> sibling property holding the enum of valid values, for select mapping.
SUPPORTED_SUFFIX = "supported"
