"""show_room.py — the room and its aim catalogue (`lightshows/room.yml`).

The room holds the nominal size of the venue in metres, the place of every rig fixture,
the DJ booth and the aims: named figures the movers draw, each tied to a SoundSwitch
position preset (`configured`) or still to be created there (`pending`, with a `fallback`
aim). `problems_room` is a pure schema check of parsed YAML (possibly with the loader's
`__line__` keys) returning `(line, message)` items; `load_room` builds a `Room` from a valid
file; `resolve_aim` walks the fallback chain to the first configured aim's preset;
`preset_aims` maps a preset back to its aim. Nothing here raises on bad content or reads a
file. See docs/superpowers/specs/2026-11-06-show-critic-design.md, section 8.

Python API: `Aim`, `Room`, `problems_room`, `load_room`, `resolve_aim`, `preset_aims`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

AIM_ID_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
STATUSES = ("configured", "pending")
AIM_KEYS = ("figure", "preset", "status", "fallback", "targets")
ROOM_KEYS = ("size", "assumed", "fixtures", "booth", "aims")
AXES = ("x", "y", "z")

Point = tuple[float, float, float]


@dataclass
class Aim:
    id: str
    figure: str
    preset: str
    status: str                       # "configured" | "pending"
    fallback: str | None
    targets: dict[str, Point]         # rig mover key -> point


@dataclass
class Room:
    size: Point
    assumed: bool
    fixtures: dict[str, Point]
    booth: Point
    aims: dict[str, Aim]


def _keys(node: dict) -> list[str]:
    return [k for k in node if k != "__line__"]


def _line(node: object, default: int = 0) -> int:
    return node.get("__line__", default) if isinstance(node, dict) else default


def _num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _clean(v: object) -> object:
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items() if k != "__line__"}
    return v


def _size_problems(size: object, line: int) -> tuple[list[tuple[int, str]], Point | None]:
    if not isinstance(size, dict) or sorted(_keys(size)) != sorted(AXES):
        return [(line, f"size {_clean(size)!r} must be a mapping with x, y and z")], None
    vals = [size[a] for a in AXES]
    if not all(_num(v) and v > 0 for v in vals):
        return [(_line(size, line), f"size {_clean(size)!r} must hold three positive numbers")], None
    return [], (float(vals[0]), float(vals[1]), float(vals[2]))


def _point_problem(point: object, size: Point | None, where: str) -> str | None:
    if not isinstance(point, list) or len(point) != 3 or not all(_num(v) for v in point):
        return f"{where} {point!r} must be a list of three numbers [x, y, z]"
    if size is not None:
        for v, hi, axis in zip(point, size, AXES):
            if not 0 <= v <= hi:
                return f"{where} {point!r} lies outside the room (axis {axis} must be within 0..{hi:g})"
    return None


def problems_room(data: object, rig_fixtures: dict[str, str] | None) -> list[tuple[int, str]]:
    """Schema problems of a parsed `room.yml` as `(line, message)`. `rig_fixtures` maps each
    rig fixture key to its kind; None (the rig is missing or invalid) skips the cross-checks.
    Fallback chains must end on a configured aim with no cycle."""
    if not isinstance(data, dict):
        return [(0, "room must be a mapping with size, assumed, fixtures, booth and aims")]
    top = _line(data)
    out: list[tuple[int, str]] = []
    for key in ROOM_KEYS:
        if key not in data:
            out.append((top, f"room is missing the key {key!r}"))
    for key in _keys(data):
        if key not in ROOM_KEYS:
            out.append((top, f"room has the unknown key {key!r} (allowed: {', '.join(ROOM_KEYS)})"))
    size = None
    if "size" in data:
        found, size = _size_problems(data["size"], top)
        out.extend(found)
    if "assumed" in data and not isinstance(data["assumed"], bool):
        out.append((top, f"assumed {data['assumed']!r} must be true or false"))
    if "fixtures" in data:
        fixtures = data["fixtures"]
        if not isinstance(fixtures, dict) or not _keys(fixtures):
            out.append((top, "fixtures must be a non-empty mapping of rig fixture key to point"))
        else:
            here = _line(fixtures, top)
            for key in _keys(fixtures):
                bad = _point_problem(fixtures[key], size, f"fixture {key!r} place")
                if bad:
                    out.append((here, bad))
                if rig_fixtures is not None and key not in rig_fixtures:
                    out.append((here, f"fixture {key!r} is not a fixture key of lightshows/rig.yml"))
            if rig_fixtures is not None:
                for key in rig_fixtures:
                    if key not in fixtures:
                        out.append((here, f"rig fixture {key!r} has no place in fixtures"))
    if "booth" in data:
        bad = _point_problem(data["booth"], size, "booth")
        if bad:
            out.append((top, bad))
    if "aims" in data:
        out.extend(_aims_problems(data["aims"], size, rig_fixtures, top))
    return out


def _aims_problems(aims: object, size: Point | None, rig_fixtures: dict[str, str] | None,
                   top: int) -> list[tuple[int, str]]:
    if not isinstance(aims, dict) or not _keys(aims):
        return [(top, "aims must be a non-empty mapping of aim id to aim")]
    out: list[tuple[int, str]] = []
    movers = sorted(k for k, kind in (rig_fixtures or {}).items() if kind == "mover")
    for aim_id in _keys(aims):
        aim = aims[aim_id]
        where = f"aim {aim_id!r}"
        if not (isinstance(aim_id, str) and AIM_ID_RE.fullmatch(aim_id)):
            out.append((_line(aims, top), f"aim id {aim_id!r} must be kebab-case (lowercase letters and digits joined by single '-')"))
        if not isinstance(aim, dict):
            out.append((_line(aims, top), f"{where} must be a mapping with {', '.join(AIM_KEYS)}"))
            continue
        line = _line(aim, top)
        for key in ("figure", "preset", "status", "targets"):
            if key not in aim:
                out.append((line, f"{where} is missing the key {key!r}"))
        for key in _keys(aim):
            if key not in AIM_KEYS:
                out.append((line, f"{where} has the unknown key {key!r} (allowed: {', '.join(AIM_KEYS)})"))
        for key in ("figure", "preset"):
            if key in aim and not (isinstance(aim[key], str) and aim[key].strip()):
                out.append((line, f"{where}: {key} {aim[key]!r} must be a non-empty string"))
        status = aim.get("status")
        if "status" in aim and status not in STATUSES:
            out.append((line, f"{where}: status {status!r} must be configured or pending"))
        if status == "configured" and "fallback" in aim:
            out.append((line, f"{where} is configured, so it must not have a fallback (remove it)"))
        if status == "pending":
            fb = aim.get("fallback")
            if "fallback" not in aim:
                out.append((line, f"{where} is pending, so it needs a fallback: another aim id"))
            elif not isinstance(fb, str) or fb not in aims or fb == aim_id:
                out.append((line, f"{where}: fallback {fb!r} must be another aim id of this file"))
        targets = aim.get("targets")
        if "targets" in aim:
            if not isinstance(targets, dict):
                out.append((line, f"{where}: targets must be a mapping of rig mover key to point"))
            else:
                for key in _keys(targets):
                    bad = _point_problem(targets[key], size, f"{where}: target {key!r}")
                    if bad:
                        out.append((line, bad))
                    if rig_fixtures is not None and rig_fixtures.get(key) != "mover":
                        out.append((line, f"{where}: target {key!r} is not a mover of lightshows/rig.yml"))
                if rig_fixtures is not None:
                    for key in movers:
                        if key not in targets:
                            out.append((line, f"{where}: targets has no point for the mover {key!r}"))
    out.extend(_chain_problems(aims, top))
    return out


def _chain_problems(aims: dict, top: int) -> list[tuple[int, str]]:
    """A fallback cycle is one finding naming it (a chain that dead-ends on an unknown aim
    is reported by the fallback check)."""
    out: list[tuple[int, str]] = []
    reported: set[frozenset] = set()
    for start in _keys(aims):
        chain = [start]
        while True:
            aim = aims.get(chain[-1])
            if not isinstance(aim, dict) or aim.get("status") != "pending":
                break
            nxt = aim.get("fallback")
            if not isinstance(nxt, str) or nxt not in aims:
                break
            if nxt in chain:
                cycle = chain[chain.index(nxt):] + [nxt]
                if frozenset(cycle) not in reported:
                    reported.add(frozenset(cycle))
                    out.append((_line(aims.get(nxt), top), "fallback cycle: " + " -> ".join(cycle)))
                break
            chain.append(nxt)
    return out


def _point(v: list) -> Point:
    return (float(v[0]), float(v[1]), float(v[2]))


def load_room(data: dict) -> Room:
    """Build a `Room` from a parsed `room.yml`. Run `problems_room` first: this assumes a
    valid file. The loader's `__line__` keys are dropped."""
    size = data["size"]
    aims = {}
    for aim_id in _keys(data["aims"]):
        a = data["aims"][aim_id]
        aims[aim_id] = Aim(
            aim_id, a["figure"], a["preset"], a["status"], a.get("fallback"),
            {k: _point(a["targets"][k]) for k in _keys(a["targets"])},
        )
    return Room(
        (float(size["x"]), float(size["y"]), float(size["z"])),
        data["assumed"],
        {k: _point(data["fixtures"][k]) for k in _keys(data["fixtures"])},
        _point(data["booth"]),
        aims,
    )


def resolve_aim(room: Room, aim_id: str) -> tuple[str | None, list[str], str | None]:
    """`(preset, chain, problem)`: the preset of the first configured aim along the fallback
    chain starting at `aim_id`, the aim ids walked (the start included), and why there is no
    preset (an unknown aim, or a cycle) or None."""
    chain: list[str] = []
    current: str | None = aim_id
    while current is not None:
        if current not in room.aims:
            return None, chain, f"aim {current!r} is not in the room's catalogue"
        if current in chain:
            return None, chain, "fallback cycle: " + " -> ".join(chain + [current])
        chain.append(current)
        aim = room.aims[current]
        if aim.status == "configured":
            return aim.preset, chain, None
        current = aim.fallback
    return None, chain, f"aim {aim_id!r} has no configured aim at the end of its fallback chain"


def preset_aims(room: Room) -> dict[str, str]:
    """Preset -> aim id, only for presets used by exactly one configured aim."""
    seen: dict[str, list[str]] = {}
    for aim in room.aims.values():
        if aim.status == "configured":
            seen.setdefault(aim.preset, []).append(aim.id)
    return {preset: ids[0] for preset, ids in seen.items() if len(ids) == 1}
