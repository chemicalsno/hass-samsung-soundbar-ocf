"""Turn discovered OCF resource representations into entity specs.

'Everything reachable': every scalar control property becomes an entity, typed
from its value and the resource interface. Writable actuators (oic.if.a /
oic.if.rw) become switch / number / select; read-only properties become
sensors. Non-scalar values (lists, maps) are left for a future pass.
"""

from __future__ import annotations

from dataclasses import dataclass

from .const import MEDIA_PLAYER_PATHS, OCF_PROP_PREFIX


@dataclass(frozen=True)
class EntitySpec:
    kind: str          # "switch" | "number" | "select" | "sensor"
    path: str
    prop: str          # full OCF property key
    options: tuple[str, ...] | None = None
    write_extra: tuple[tuple[str, str], ...] | None = None  # extra fields to POST on write


# Properties that are genuine user controls. A writable OCF resource also
# carries status/capability fields (isSupported, calibrationstatus, MACs,
# versions); writing those is wrong and can wedge the endpoint, so only these
# become switch/number/select. Everything else reachable becomes a sensor.
CONTROL_PROPS: frozenset[str] = frozenset(
    {
        "woofer",
        "channelVolume",
        "bass",
        "treble",
        "bassboost",
        "voiceamplifier",
        "nightmode",
        "audiosync",
        "autoPowerDown",
        "autoUpdate",
        "passThruEnable",
        "symphony",
        "language",
        "EQname",
    }
)

# Some writes need companion fields (e.g. the EQ preset is applied only with an action).
WRITE_EXTRA: dict[str, tuple[tuple[str, str], ...]] = {
    "EQname": ((OCF_PROP_PREFIX + "action", "setEQmode"),),
}


def _writable(rep: dict) -> bool:
    ifaces = rep.get("if", [])
    return "oic.if.a" in ifaces or "oic.if.rw" in ifaces


def _supported_options(rep: dict, short_name: str) -> tuple[str, ...] | None:
    cap = OCF_PROP_PREFIX + "supported" + short_name[:1].upper() + short_name[1:]
    for key in (cap, OCF_PROP_PREFIX + "supportedList"):
        val = rep.get(key)
        if isinstance(val, list) and val and all(isinstance(v, str) for v in val):
            return tuple(val)
    return None


def iter_specs(data: dict[str, dict]) -> list[EntitySpec]:
    specs: list[EntitySpec] = []
    for path, rep in data.items():
        if path in MEDIA_PLAYER_PATHS:
            continue
        writable = _writable(rep)
        for prop, value in rep.items():
            if not prop.startswith(OCF_PROP_PREFIX):
                continue
            short_name = prop[len(OCF_PROP_PREFIX):]
            if short_name.startswith("supported") or short_name == "action":
                continue  # supported* are select options; action is a command trigger
            controllable = writable and short_name in CONTROL_PROPS
            if isinstance(value, bool):
                specs.append(EntitySpec("switch" if controllable else "sensor", path, prop))
            elif isinstance(value, (int, float)):
                specs.append(EntitySpec("number" if controllable else "sensor", path, prop))
            elif isinstance(value, str):
                options = _supported_options(rep, short_name) if controllable else None
                if options:
                    specs.append(EntitySpec("select", path, prop, options, WRITE_EXTRA.get(short_name)))
                else:
                    specs.append(EntitySpec("sensor", path, prop))
            # lists / dicts: skipped for now

    # One entity per property name: a control wins over a sensor, else first seen.
    priority = {"switch": 0, "number": 0, "select": 0, "sensor": 1}
    best: dict[str, EntitySpec] = {}
    for spec in specs:
        name = spec.prop[len(OCF_PROP_PREFIX):]
        if name not in best or priority[spec.kind] < priority[best[name].kind]:
            best[name] = spec
    return list(best.values())


def control_paths(data: dict[str, dict]) -> set[str]:
    """Resources that back a control (media_player or a writable entity): poll these often."""
    paths = {p for p in MEDIA_PLAYER_PATHS if p in data}
    paths.update(spec.path for spec in iter_specs(data) if spec.kind != "sensor")
    return paths
