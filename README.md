# Samsung Soundbar Local (OCF/DTLS-PSK)

[![Validate](https://github.com/chemicalsno/hass-samsung-soundbar-ocf/actions/workflows/validate.yml/badge.svg)](https://github.com/chemicalsno/hass-samsung-soundbar-ocf/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Release](https://img.shields.io/github/v/release/chemicalsno/hass-samsung-soundbar-ocf)](https://github.com/chemicalsno/hass-samsung-soundbar-ocf/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Cloud-free local control for Samsung Wi-Fi soundbars that expose the OCF
`/sec/networkaudio` interface (verified on the 2023 **HW-Q900C**). Home Assistant
talks straight to the bar over the LAN with DTLS, authenticated by the device's own
per-appliance pre-shared key (OwnerPSK). No Samsung cloud is contacted at runtime.

> This targets the OCF `sct=1` soundbars. It is unrelated to the older TCP-1516
> JSON-RPC approach used for the 2024 D-line models.

## How it works

1. Reads the bar's ephemeral secure DTLS port from the unsecured `/oic/res` (it rotates
   per boot, so it is re-read every session).
2. Opens a DTLS 1.2 `TLS_ECDHE_PSK_WITH_AES_128_CBC_SHA256` session using your OwnerPSK.
   The identity is carried by length, so an identity containing a NUL byte works (OpenSSL
   cannot do this; a vendored pure-Python engine is used instead).
3. Reads and writes the `/sec/networkaudio/*` resources over CoAP.

Each operation uses a short-lived session closed with `close_notify`, because the bar
frees a DTLS peer slot only on `close_notify` and has no idle timeout.

## Entities

Created by runtime discovery of whatever the bar exposes:

- **media_player**: power, volume, mute, source (read-only), sound mode.
- **number**: woofer level, bass, treble, bass boost, voice amplifier, night mode, audio sync.
- **select**: sound mode, EQ preset, language.
- **switch**: auto power down, auto update, pass through.
- **sensor** (diagnostic): read-only state (firmware, network info, status fields).

Only known-safe control properties are writable; everything else reachable is exposed
read-only, so no status or capability field is written by accident. Control resources poll
every 30 s; diagnostics poll every ~10 min.

## Requirements

- A Samsung soundbar that answers OCF `/sec/networkaudio` over DTLS with `sct=1`
  (confirmed on the HW-Q900C; other models below).
- The bar's **OwnerPSK**: an identity UUID and a 16-byte key as hex. See below.
- Home Assistant with the `cryptography` library (bundled with HA OS and Container).

### Is my soundbar supported?

Confirmed on the **HW-Q900C** (2023). The quickest check for any other model is to add
the integration anyway: setup does a live DTLS handshake and reads `/oic/d`, so an
incompatible device is rejected immediately.

Other 2023 "C" generation Samsung soundbars with built-in Wi-Fi share the same platform
and most likely speak the same OCF interface, but none have been tested. If you have one,
try it and please report back in the issues:

- HW-Q990C
- HW-Q930C
- HW-Q800C

The HW-Q700C, HW-Q600C and HW-Q60C have no built-in Wi-Fi, so this cannot reach them. The
2024 "D" line (HW-Q990D and siblings) uses a different TCP-1516 JSON-RPC API, not this one.

### Getting the OwnerPSK

This is the hard part and is device-specific. The key is not derivable; it is provisioned
during SmartThings onboarding and must be recovered from the SmartThings Android app, or
provisioned by you if you already hold owner access. This is advanced and out of scope for
this README. See the upstream acquisition work:

- https://github.com/mbillow/localthings/issues/435 (acquisition discussion)
- https://github.com/KRZ303/locathings-oven-psk-retrieval (reference scripts)

Keep your OwnerPSK private. Do not commit it or paste it anywhere public. If you remove and
re-add the bar in SmartThings, the key changes and must be recovered again.

## Installation

### HACS (custom repository)

1. HACS -> three dots -> Custom repositories -> add this repo as an Integration.
2. Install "Samsung Soundbar Local", then restart Home Assistant.

### Manual

1. Copy `custom_components/samsung_soundbar_local/` into your HA `config/custom_components/`.
2. Restart Home Assistant.

### Configure

Settings -> Devices & Services -> Add Integration -> **Samsung Soundbar Local**, then enter:

- **IP address** of the bar.
- **OwnerPSK identity** (the owner UUID).
- **OwnerPSK key** (hex: 32 or 64 characters).

The config flow validates by doing a live handshake and reading `/oic/d`, so a wrong key or
IP is rejected immediately.

## Notes and known behavior

- **Secure port rotation** on reboot is handled automatically (re-read each session).
- **Brief state lag:** right after a write, the entity may read the old value until the next
  poll completes, then it settles.
- **Reboots** do not affect the credential; it persists until a deliberate SmartThings
  re-onboard, which resets the bar's credential store.
- The integration keeps working with the bar still owned by SmartThings; both coexist.

## Credits and license

- DTLS 1.2 ECDHE-PSK engine vendored from
  [QuiteYellow/SmartThings-Local](https://github.com/QuiteYellow/SmartThings-Local) (MIT).
- OwnerPSK acquisition method from the localthings community (links above).
- Home Assistant component scaffold based on
  [ZtF/hass-samsung-soundbar-local](https://github.com/ZtF/hass-samsung-soundbar-local).

MIT, see `LICENSE`.
