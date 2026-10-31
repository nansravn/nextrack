"""lightshow.py — the rig and choreography models, the light vocabulary and their schema checks.

`lightshows/rig.yml` describes the room, `lightshows/tracks/*.yml` the light script of
one track, `lightshows/sets/*.md` the effect budget of a set. This module loads the first
two into dataclasses and holds the pure `problems_*` checks that `check_repo.py` wraps
into rules. The checks take parsed YAML (possibly with the loader's `__line__` keys) and
return messages; they never raise on bad content. See lightshows/README.md.

The generators (`matrix_frames`, `mover_keys`, `hue_keys`, …) turn the vocabulary into
keyframes, and `compile_choreography` applies a choreography to a copy of a SoundSwitch
track script, returning the edited copy and the manual cues it could not write.

Python API: `load_rig`, `load_choreography`, `problems_rig`, `problems_choreography`,
`problems_plan`, `section_layers`, `compile_choreography` (`ManualCue`, `CompileError`).
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from soundswitch_format import (FULL, Grid, Key, PositionFlag, Preset, Track, TrackScript,
                                VenueInfo, VenueNode, check, grid, materialise_main, set_colour,
                                set_intensity, set_main, set_positions)

LAYERS = ("movers", "matrix", "white", "uv", "strobe", "hue", "haze")
MOVER_MOVES = ("hold", "pingpong", "sweep", "blink", "uv")
MATRIX_DRAWS = (
    "solid", "rows-down", "rows-up", "columns", "zigzag", "centre-out", "arrow-up", "fill-up",
)  # fmt: skip
HUE_STATES = ("dark", "pulse", "bright")

FIXTURE_KINDS = ("mover", "matrix", "haze", "hue-chandelier")
CORNERS = ("NE", "SE", "NW", "SW", "centre")
FRONTS = ("N", "E", "S", "W")
MATRIX_ROW_KINDS = ("colour", "white")
BUDGET_KEYS = LAYERS + ("white-accent",)

RATE_RE = re.compile(r"1/16|1/8|1/4|1/2|[1-9][0-9]*bar")
COLOUR_RE = re.compile(r"#[0-9A-Fa-f]{6}")
GUID_RE = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")
BEAT_RE = re.compile(r"[1-9][0-9]*\.[1-9][0-9]*")  # "<bar>.<beat>"
SECONDS_RE = re.compile(r"[1-9][0-9]*s")
DOWNBEAT_RE = re.compile(r"[0-9]+:[0-5][0-9](\.[0-9]+)?")

# --------------------------------------------------------------------- models --


@dataclass
class RigFixture:
    key: str
    kind: str
    node: str | None
    index: int | None
    corner: str | None
    extra: dict = field(default_factory=dict)


@dataclass
class Rig:
    fixtures: dict[str, RigFixture]
    matrix_rows: list[str]
    zone_order: str
    white_max: float


@dataclass
class Section:
    bars: tuple[int, int]
    name: str
    intent: str | None
    layers: dict[str, object]


@dataclass
class Choreography:
    track: str
    soundswitch: str
    grid: dict
    story: str
    budget: str | None
    base: str
    sections: list[Section]


def _clean(mapping: dict) -> dict:
    """`mapping` without the loader's `__line__` bookkeeping."""
    return {k: v for k, v in mapping.items() if k != "__line__"}


def _layer_value(value):
    """YAML 1.1 reads an unquoted `off` / `on` as False / True: give the words back."""
    if value is False:
        return "off"
    if value is True:
        return "on"
    return value


def load_rig(path: Path) -> Rig:
    """Load `rig.yml`. Run `problems_rig` first: this assumes a valid file."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    fixtures = {}
    for key, spec in data["fixtures"].items():
        known = ("kind", "node", "index", "corner")
        fixtures[key] = RigFixture(
            key=key,
            kind=spec["kind"],
            node=spec.get("node"),
            index=spec.get("index"),
            corner=spec.get("corner"),
            extra={k: v for k, v in spec.items() if k not in known},
        )
    matrix = data["matrix"]
    return Rig(fixtures, list(matrix["rows"]), matrix["zone_order"], float(matrix["white_max"]))


def load_choreography(path: Path) -> Choreography:
    """Load a choreography. Run `problems_choreography` first: this assumes a valid file."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    sections = []
    for raw in data["sections"]:
        layers = {k: _layer_value(raw[k]) for k in LAYERS if k in raw}
        sections.append(Section(tuple(raw["bars"]), raw["name"], raw.get("intent"), layers))
    return Choreography(
        track=data["track"],
        soundswitch=data["soundswitch"],
        grid=data["grid"],
        story=data["story"],
        budget=data.get("budget"),
        base=data["base"],
        sections=sections,
    )


# ------------------------------------------------------------------- checks --


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_str(v) -> bool:
    return isinstance(v, str) and bool(v)


def _show(v) -> str:
    return "a mapping" if isinstance(v, dict) else repr(v)


def _key_msgs(mapping: dict, allowed: tuple[str, ...], required: tuple[str, ...]) -> list[str]:
    out = [f"missing key {key!r}" for key in required if key not in mapping]
    out += [f"unknown key {k!r}" for k in mapping if k != "__line__" and k not in allowed]
    return out


def _keys(mapping: dict, allowed: tuple[str, ...], required: tuple[str, ...], where: str):
    return [f"{where}: {m}" for m in _key_msgs(mapping, allowed, required)]


def problems_rig(data: object) -> list[str]:
    """Schema problems of a parsed `rig.yml`."""
    if not isinstance(data, dict):
        return ["rig must be a mapping with room, fixtures and matrix"]
    out = list(_keys(data, ("room", "fixtures", "matrix"), ("room", "fixtures", "matrix"), "rig"))
    room = data.get("room")
    if "room" in data:
        if not isinstance(room, dict):
            out.append(f"room {_show(room)} is not a mapping")
        else:
            out.extend(_keys(room, ("shape", "front"), ("shape", "front"), "room"))
            if "shape" in room and not _is_str(room["shape"]):
                out.append(f"room shape {_show(room['shape'])} is not a non-empty string")
            if "front" in room and room["front"] not in FRONTS:
                out.append(f"room front {_show(room['front'])} is not one of {', '.join(FRONTS)}")
    fixtures = data.get("fixtures")
    if "fixtures" in data:
        if not isinstance(fixtures, dict) or not _clean(fixtures):
            out.append("fixtures must be a non-empty mapping")
        else:
            for key, spec in _clean(fixtures).items():
                out.extend(_fixture_problems(str(key), spec))
    if "matrix" in data:
        out.extend(_matrix_problems(data["matrix"]))
    return out


FIXTURE_KEYS = ("node", "index", "corner", "kind", "aim", "fan", "fog", "lamps", "follows")


def _fixture_problems(key: str, spec: object) -> list[str]:
    where = f"fixture {key!r}"
    if not isinstance(spec, dict):
        return [f"{where} is not a mapping"]
    out = list(_keys(spec, FIXTURE_KEYS, ("kind",), where))
    kind = spec.get("kind")
    if "kind" in spec and kind not in FIXTURE_KINDS:
        out.append(f"{where}: kind {_show(kind)} is not one of {', '.join(FIXTURE_KINDS)}")
    if "corner" in spec and spec["corner"] not in CORNERS:
        out.append(f"{where}: corner {_show(spec['corner'])} is not one of {', '.join(CORNERS)}")
    if kind in FIXTURE_KINDS and kind != "hue-chandelier" and "node" not in spec:
        out.append(f"{where}: missing key 'node'")
    for name in ("node", "fan", "fog", "follows", "aim"):
        if name in spec and not _is_str(spec[name]):
            out.append(f"{where}: {name} {_show(spec[name])} is not a non-empty string")
    for name in ("index", "lamps"):
        if name in spec and not (_is_int(spec[name]) and spec[name] >= 1):
            out.append(f"{where}: {name} {_show(spec[name])} is not a positive integer")
    return out


def _matrix_problems(matrix: object) -> list[str]:
    if not isinstance(matrix, dict):
        return [f"matrix {_show(matrix)} is not a mapping"]
    keys = ("rows", "zone_order", "white_max")
    out = list(_keys(matrix, keys, keys, "matrix"))
    rows = matrix.get("rows")
    if "rows" in matrix and not (
        isinstance(rows, list) and rows and all(r in MATRIX_ROW_KINDS for r in rows)
    ):
        out.append(f"matrix rows {_show(rows)} is not a non-empty list of 'colour' or 'white'")
    if "zone_order" in matrix and not _is_str(matrix["zone_order"]):
        out.append(f"matrix zone_order {_show(matrix['zone_order'])} is not a non-empty string")
    white_max = matrix.get("white_max")
    if "white_max" in matrix and not (_is_num(white_max) and 0 < white_max <= 1):
        out.append(f"matrix white_max {_show(white_max)} is not a number in (0, 1]")
    return out


CHOREO_REQUIRED = ("track", "soundswitch", "grid", "story", "base", "sections")
CHOREO_KEYS = CHOREO_REQUIRED + ("budget",)
SECTION_KEYS = ("bars", "name", "intent") + LAYERS

MOVER_KEYS = (
    "move", "every", "colour", "level", "position", "positions", "faster_from", "faster_every",
)  # fmt: skip
MATRIX_KEYS = ("draw", "rate", "colour", "mirror", "pingpong", "with_white")


def problems_choreography(data: object, rig: Rig | None = None) -> list[str]:
    """Schema problems of a parsed choreography. `track` resolution against the pools is
    done by the rule, which has them. `rig` is accepted so that layers can be checked
    against the room later; the v1 vocabulary needs nothing from it."""
    if not isinstance(data, dict):
        return ["choreography must be a mapping"]
    out = list(_keys(data, CHOREO_KEYS, CHOREO_REQUIRED, "choreography"))
    for key in ("track", "story"):
        if key in data and not _is_str(data[key]):
            out.append(f"{key} {_show(data[key])} is not a non-empty string")
    if "budget" in data and data["budget"] is not None and not _is_str(data["budget"]):
        out.append(f"budget {_show(data['budget'])} is not a string")
    if "soundswitch" in data and not (
        isinstance(data["soundswitch"], str) and GUID_RE.fullmatch(data["soundswitch"])
    ):
        out.append(f"soundswitch {_show(data['soundswitch'])} is not a GUID")
    if "base" in data and data["base"] != "autoscript":
        out.append(f"base {_show(data['base'])} is not 'autoscript'")
    if "grid" in data:
        out.extend(_grid_problems(data["grid"]))
    if "sections" in data:
        sections = data["sections"]
        if not isinstance(sections, list) or not sections:
            out.append("sections must be a non-empty list")
        else:
            last_end = 0
            for i, section in enumerate(sections, 1):
                last_end = _section_problems(i, section, last_end, out)
    return out


def _grid_problems(grid: object) -> list[str]:
    if not isinstance(grid, dict):
        return [f"grid {_show(grid)} is not a mapping"]
    out = list(_keys(grid, ("bpm", "downbeat"), ("bpm", "downbeat"), "grid"))
    if "bpm" in grid and not (_is_num(grid["bpm"]) and grid["bpm"] > 0):
        out.append(f"grid bpm {_show(grid['bpm'])} is not a positive number")
    if "downbeat" in grid and not (
        isinstance(grid["downbeat"], str) and DOWNBEAT_RE.fullmatch(grid["downbeat"])
    ):
        out.append(f"grid downbeat {_show(grid['downbeat'])} is not a time such as '0:00.158'")
    return out


def _section_problems(i: int, section: object, last_end: int, out: list[str]) -> int:
    """Append the problems of section number `i`; return the end bar to compare the next to."""
    if not isinstance(section, dict):
        out.append(f"section {i} is not a mapping")
        return last_end
    name = section.get("name")
    where = f"section {i}" + (f" ({name})" if isinstance(name, str) else "")
    out.extend(_keys(section, SECTION_KEYS, ("bars", "name"), where))
    if "name" in section and not _is_str(name):
        out.append(f"{where}: name {_show(name)} is not a non-empty string")
    if "intent" in section and not _is_str(section["intent"]):
        out.append(f"{where}: intent {_show(section['intent'])} is not a non-empty string")
    bars = section.get("bars")
    if "bars" in section:
        if not (
            isinstance(bars, list) and len(bars) == 2 and all(_is_int(b) for b in bars)
            and 1 <= bars[0] <= bars[1]
        ):  # fmt: skip
            out.append(f"{where}: bars {_show(bars)} is not [a, b] with 1 <= a <= b")
        else:
            if bars[0] <= last_end:
                out.append(
                    f"{where}: bars {bars} are not after the previous section (ends at bar "
                    f"{last_end}): sections must be sorted and must not overlap"
                )
            last_end = max(last_end, bars[1])
    for layer in LAYERS:
        if layer in section:
            out.extend(f"{where}: {p}" for p in _layer_problems(layer, section[layer]))
    return last_end


SCALARS = {  # words a layer takes besides a mapping
    "movers": ("auto", "off"),
    "matrix": ("auto", "off"),
    "white": ("auto", "off"),
    "uv": ("auto", "off", "on"),
    "strobe": ("auto", "off"),
    "hue": ("auto", "off") + HUE_STATES,
    "haze": ("auto", "off", "on"),
}


def _layer_problems(layer: str, value: object) -> list[str]:
    value = _layer_value(value)
    if isinstance(value, str):
        if value in SCALARS[layer]:
            return []
        return [f"{layer} {_show(value)} is not one of {', '.join(SCALARS[layer])} or a mapping"]
    if not isinstance(value, dict):
        return [f"{layer} {_show(value)} is not a word or a mapping"]
    if layer == "uv":
        return ["uv takes on, off or auto"]
    return [f"{layer}: {p}" for p in _MAPPING_CHECKS[layer](_clean(value))]


def _bad_rate(mapping: dict, key: str) -> list[str]:
    if key in mapping and not (isinstance(mapping[key], str) and RATE_RE.fullmatch(mapping[key])):
        yield f"{key} {_show(mapping[key])} is not a rate (1/16, 1/8, 1/4, 1/2 or <n>bar)"


def _bad_colour(mapping: dict) -> list[str]:
    if "colour" in mapping and not (
        isinstance(mapping["colour"], str) and COLOUR_RE.fullmatch(mapping["colour"])
    ):
        yield f"colour {_show(mapping['colour'])} is not #RRGGBB"


def _bad_bools(mapping: dict, keys: tuple[str, ...]) -> list[str]:
    for key in keys:
        if key in mapping and not isinstance(mapping[key], bool):
            yield f"{key} {_show(mapping[key])} is not true or false"


def _movers(m: dict) -> list[str]:
    out = _key_msgs(m, MOVER_KEYS, ("move",))
    if "move" in m and m["move"] not in MOVER_MOVES:
        out.append(f"move {_show(m['move'])} is not one of {', '.join(MOVER_MOVES)}")
    for key in ("every", "faster_every"):
        out.extend(_bad_rate(m, key))
    out.extend(_bad_colour(m))
    if "level" in m and not (_is_num(m["level"]) and 0 < m["level"] <= 1):
        out.append(f"level {_show(m['level'])} is not a number in (0, 1]")
    if "position" in m and not _is_str(m["position"]):
        out.append(f"position {_show(m['position'])} is not a non-empty string")
    if "positions" in m and not (
        isinstance(m["positions"], list) and m["positions"] and all(_is_str(p) for p in m["positions"])
    ):  # fmt: skip
        out.append(f"positions {_show(m['positions'])} is not a non-empty list of names")
    if "faster_from" in m and not (_is_int(m["faster_from"]) and m["faster_from"] >= 1):
        out.append(f"faster_from {_show(m['faster_from'])} is not a bar number")
    return out


def _matrix(m: dict) -> list[str]:
    out = _key_msgs(m, MATRIX_KEYS, ("draw",))
    if "draw" in m and m["draw"] not in MATRIX_DRAWS:
        out.append(f"draw {_show(m['draw'])} is not one of {', '.join(MATRIX_DRAWS)}")
    out.extend(_bad_rate(m, "rate"))
    out.extend(_bad_colour(m))
    out.extend(_bad_bools(m, ("mirror", "pingpong", "with_white")))
    return out


def _white(m: dict) -> list[str]:
    out = _key_msgs(m, ("accent", "flash"), ())
    if len([k for k in ("accent", "flash") if k in m]) != 1:
        out.append("takes exactly one of accent or flash")
    if "accent" in m and not (
        isinstance(m["accent"], list) and m["accent"]
        and all(isinstance(a, str) and BEAT_RE.fullmatch(a) for a in m["accent"])
    ):  # fmt: skip
        out.append(f"accent {_show(m['accent'])} is not a non-empty list of '<bar>.<beat>'")
    out.extend(_bad_rate(m, "flash"))
    return out


def _strobe(m: dict) -> list[str]:
    out = _key_msgs(m, ("hit", "roll"), ())
    if len([k for k in ("hit", "roll") if k in m]) != 1:
        out.append("takes exactly one of hit or roll")
    if "hit" in m and not (
        isinstance(m["hit"], list) and m["hit"]
        and all(isinstance(a, str) and BEAT_RE.fullmatch(a) for a in m["hit"])
    ):  # fmt: skip
        out.append(f"hit {_show(m['hit'])} is not a non-empty list of '<bar>.<beat>'")
    roll = m.get("roll")
    if "roll" in m and not (
        isinstance(roll, list) and len(roll) == 2 and all(_is_int(b) for b in roll)
        and 1 <= roll[0] <= roll[1]
    ):  # fmt: skip
        out.append(f"roll {_show(roll)} is not [a, b] with 1 <= a <= b")
    return out


def _hue(m: dict) -> list[str]:
    out = _key_msgs(m, ("state", "colour"), ("state",))
    if "state" in m and m["state"] not in HUE_STATES:
        out.append(f"state {_show(m['state'])} is not one of {', '.join(HUE_STATES)}")
    out.extend(_bad_colour(m))
    return out


def _haze(m: dict) -> list[str]:
    out = _key_msgs(m, ("burst",), ("burst",))
    if "burst" in m and not (isinstance(m["burst"], str) and SECONDS_RE.fullmatch(m["burst"])):
        out.append(f"burst {_show(m['burst'])} is not seconds such as '4s'")
    return out


_MAPPING_CHECKS = {
    "movers": _movers,
    "matrix": _matrix,
    "white": _white,
    "strobe": _strobe,
    "hue": _hue,
    "haze": _haze,
}


def problems_plan(front: dict, root: Path) -> list[str]:
    """Problems of a show plan's front matter: `set` must exist (relative to the repo
    `root`) and `budget` must map vocabulary effects to lists of block or track ids."""
    if not isinstance(front, dict):
        return ["front matter must be a mapping"]
    out = list(_keys(front, ("set", "budget"), ("set", "budget"), "plan"))
    if "set" in front:
        path = front["set"]
        if not _is_str(path):
            out.append(f"set {_show(path)} is not a path")
        elif Path(path).is_absolute():
            out.append(f"set {_show(path)} is not a path relative to the repo")
        elif not (Path(root) / path).exists():
            out.append(f"set {_show(path)} does not exist")
    budget = front.get("budget")
    if "budget" in front:
        if not isinstance(budget, dict):
            out.append(f"budget {_show(budget)} is not a mapping")
        else:
            for effect, where in _clean(budget).items():
                if effect not in BUDGET_KEYS:
                    out.append(f"budget key {_show(effect)} is not one of {', '.join(BUDGET_KEYS)}")
                if not (isinstance(where, list) and all(_is_str(w) for w in where)):
                    out.append(f"budget {effect}: {_show(where)} is not a list of names")
    return out


# ---------------------------------------------------------------- generators --

STEADY = 0.85  # steady level of a held mover or a bright hue
COLOUR_ROWS = [0, 1, 2, 4, 5, 6]
WHITE_ROW = 3
MATRIX_COLS = 8


def level_of(fraction: float) -> int:
    """A 0..1 brightness as the u32 level the script format stores."""
    return FULL if fraction >= 1 else int(fraction * 2**32)


def rate_ms(rate: str, beat_ms: float) -> float:
    """Length in ms of a rate: `1/4` is one beat, `1/16` a quarter beat, `<n>bar` n bars of 4."""
    if rate.endswith("bar"):
        return int(rate[:-3]) * 4 * beat_ms
    num, den = rate.split("/")
    return beat_ms * 4 * int(num) / int(den)


def cell_zone(row: int, col: int) -> tuple[str, int]:
    """The zone of the cell at (`row`, `col`), row-major from the top left: rows 0-2 are
    `("rgb", 1..24)`, row 3 is `("w", 1..8)`, rows 4-6 are `("rgb", 25..48)`."""
    if row == WHITE_ROW:
        return "w", col + 1
    return "rgb", (row if row < WHITE_ROW else row - 1) * MATRIX_COLS + col + 1


def cell_node(unit_nodes: dict | None, row: int, col: int) -> int | None:
    """The node of the cell at (`row`, `col`). `unit_nodes` is a Vorlane's table from
    `unit_cells` (`"rgb"` / `"w"` → {zone number: node id}); `None` when the unit has no
    node for that zone. Without a table the zone number itself is returned."""
    kind, number = cell_zone(row, col)
    table = unit_nodes.get(kind) if unit_nodes else None
    if table is None:
        return number
    return table.get(number)


_ZONE_RE = re.compile(r"(RGB|W) ([0-9]+)\b")


def unit_cells(nodes: list[VenueNode], unit: int) -> dict:
    """The children of the Vorlane group node `unit`, by name: `"master"` → the id of
    `MASTER - …` (or `None`), `"rgb"` → {n: id of `RGB nn - …`}, `"w"` → {n: id of
    `W n - …`}. Other venues' units with the same names are told apart by `unit`."""
    out: dict = {"master": None, "rgb": {}, "w": {}}
    for n in nodes:
        if n.parent != unit:
            continue
        if n.name.startswith("MASTER") and out["master"] is None:
            out["master"] = n.id
        m = _ZONE_RE.match(n.name)
        if m:
            out[m.group(1).lower()].setdefault(int(m.group(2)), n.id)
    return out


def matrix_frames(
    draw: str,
    start: int,
    end: int,
    step_ms: float,
    unit: int,
    mirror: bool,
    *,
    with_white: bool = False,
) -> list[tuple[int, set[tuple[int, int]]]]:
    """One `(time, lit cells)` frame per step in [start, end). Cells are `(row, col)`, rows
    0-6 from the top (row 3 is the white strip, lit only when `with_white`), cols 0-7.
    Draws, over the lit rows R (the six colour rows, or all seven with `with_white`):

    - `solid`: every cell. `columns`: col k mod 8 of every row.
    - `rows-down` / `rows-up`: row R[k mod n] / R reversed. `fill-up`: the last k+1 rows
      of R, holding at all of R once full.
    - `centre-out`: cols 3-q and 4+q (q = k mod 4) of every row.
    - `zigzag`: one cell per step in snake order: R[0] left to right, R[1] right to left,
      and so on; wraps.
    - `arrow-up`: an upward chevron "^". With the apex on R[a]: cols 3,4 on R[a], cols
      2,5 on R[a+1], cols 1,6 on R[a+2], cols 0,7 on R[a+3]; cells past the bottom row
      are dropped. The apex starts at the bottom row and rises one row per step, wrapping.

    On unit 1 with `mirror`, columns are flipped (`7 - col`) so the two bars draw
    symmetrically across the room."""
    rows = COLOUR_ROWS if not with_white else sorted(COLOUR_ROWS + [WHITE_ROW])
    n = len(rows)
    flip = mirror and unit == 1
    out = []
    k = 0
    while start + k * step_ms < end:
        t = int(round(start + k * step_ms))
        if draw == "solid":
            cells = {(r, c) for r in rows for c in range(MATRIX_COLS)}
        elif draw == "columns":
            cells = {(r, k % MATRIX_COLS) for r in rows}
        elif draw == "rows-down":
            cells = {(rows[k % n], c) for c in range(MATRIX_COLS)}
        elif draw == "rows-up":
            cells = {(rows[n - 1 - k % n], c) for c in range(MATRIX_COLS)}
        elif draw == "fill-up":
            cells = {(r, c) for r in rows[n - min(k + 1, n):] for c in range(MATRIX_COLS)}
        elif draw == "centre-out":
            q = k % 4
            cells = {(r, c) for r in rows for c in (3 - q, 4 + q)}
        elif draw == "zigzag":
            i = k % (n * MATRIX_COLS)
            row, pos = divmod(i, MATRIX_COLS)
            cells = {(rows[row], pos if row % 2 == 0 else MATRIX_COLS - 1 - pos)}
        elif draw == "arrow-up":
            apex = n - 1 - k % n
            cells = set()
            for d in range(4):
                if apex + d < n:
                    cells |= {(rows[apex + d], 3 - d), (rows[apex + d], 4 + d)}
        else:
            raise ValueError(f"unknown matrix draw {draw!r}")
        if flip:
            cells = {(r, MATRIX_COLS - 1 - c) for r, c in cells}
        out.append((t, cells))
        k += 1
    return out


def pulse_keys(
    times: list[int], decay_ms: float, level: int = FULL, end: int | None = None
) -> list[Key]:
    """The autoscript's pulse: `Key(t, level)` then `Key(t + decay - 1, 0)`. A decay that
    would run into the next pulse ends one ms before it, so keys stay sorted and unique.
    With `end`, pulses starting at or after it are dropped and no decay runs past it."""
    keys: list[Key] = []
    for i, t in enumerate(times):
        if end is not None and t >= end:
            break
        stop = t + int(decay_ms) - 1
        if i + 1 < len(times):
            stop = min(stop, times[i + 1] - 1)
        if end is not None:
            stop = min(stop, end)
        keys.append(Key(t, level))
        if stop > t:
            keys.append(Key(stop, 0))
    return keys


def _steps(
    move: dict, start: int, end: int, beat_ms: float, first_bar: int = 1
) -> list[tuple[int, int]]:
    """`(begin, finish)` of each step of a mover move. `first_bar` is the absolute bar
    number at `start`; `faster_from` is an absolute bar, from which `faster_every`
    replaces `every` (at or before `first_bar`: fast from the start)."""
    slow = rate_ms(move.get("every", "1/4"), beat_ms)
    fast = rate_ms(move["faster_every"], beat_ms) if "faster_every" in move else slow
    faster_from = move.get("faster_from")
    steps = []
    t = float(start)
    while t < end:
        bar = first_bar + int((t - start) // (4 * beat_ms))
        length = fast if faster_from is not None and bar >= faster_from else slow
        steps.append((int(round(t)), min(int(round(t + length)), end)))
        t += length
    return steps


def mover_keys(
    move: dict, start: int, end: int, beat_ms: float, mover_index: int, first_bar: int = 1
) -> list[Key]:
    """The brightness envelope of one mover over [start, end] for a `movers` mapping.
    `first_bar` is the absolute bar number at `start`; `faster_from` in `move` is an
    ABSOLUTE bar, so the step changes at `start + (faster_from - first_bar) * bar_ms`
    (`faster_from` <= `first_bar` means fast from the start)."""
    kind = move["move"]
    if kind in ("hold", "sweep"):
        lvl = level_of(move.get("level", STEADY))
        return [Key(start, lvl), Key(end, lvl)]
    steps = _steps(move, start, end, beat_ms, first_bar)
    if kind == "blink":
        every = rate_ms(move.get("every", "1/4"), beat_ms)
        return pulse_keys([s for s, _ in steps], every, end=end)
    if kind == "pingpong":
        keys: list[Key] = []
        for i, (s, e) in enumerate(steps):
            if i % 2 == mover_index % 2:
                keys += [Key(s, FULL), Key(e - 1, FULL), Key(e, 0)]
        if not keys or keys[0].t > start:
            keys.insert(0, Key(start, 0))
        if keys[-1].t < end:
            keys.append(Key(end, 0))
        return keys
    raise ValueError(f"no mover keys for move {kind!r}")


def hue_keys(state: str, start: int, end: int, beat_ms: float) -> list[Key]:
    """The envelope of a hue state: `dark` 0, `bright` steady 0.85, `pulse` a pulse per beat."""
    if state == "dark":
        return [Key(start, 0), Key(end, 0)]
    if state == "bright":
        lvl = level_of(STEADY)
        return [Key(start, lvl), Key(end, lvl)]
    if state == "pulse":
        times = []
        t = float(start)
        while t < end:
            times.append(int(round(t)))
            t += beat_ms
        return pulse_keys(times, beat_ms, end=end)
    raise ValueError(f"unknown hue state {state!r}")


# ------------------------------------------------------------------ compiler --
# A section's span is its bars through the script's tempo map: from bar `a` beat 1 to one
# ms before bar `b + 1`. Each layer turns into `_Edit`s on fixture tracks; `hue` edits Main.

MAX_ANCHORS = 8               # beyond this, bar numbers would not follow the music
GRID_BPM_TOLERANCE = 0.01
GRID_MS_TOLERANCE = 2
DEFAULT_RATE = "1/4"
STROBE_RATE = "1/16"
DRAW_COLOURS = {
    "columns": "#FFB347", "fill-up": "#FF2D95", "rows-down": "#00C8FF", "rows-up": "#00C8FF",
    "centre-out": "#8A5CFF", "solid": "#00C8FF", "zigzag": "#FFB347", "arrow-up": "#FF2D95",
}  # fmt: skip
HAZE_WARNING = "experimental: confirm the machine reacts"
UV_WARNING = "not compiled yet (X3); set the movers' UV in SoundSwitch"


@dataclass
class ManualCue:
    """Something the compiler did not write; the owner adds it in SoundSwitch."""

    bar: int
    time_ms: int
    fixture: str
    what: str


class CompileError(ValueError):
    """The choreography cannot be compiled onto this script; the message says why."""


def section_layers(section: Section) -> dict[str, object]:
    """Every layer of a section with the defaults filled in: an unset layer is `auto`,
    except `white`, which is `off` under a `matrix` other than `auto` (the white strip
    never sits under a drawing by default). A draw with `with_white` writes the strip
    itself, so there an unset `white` stays `auto`."""
    out = {name: section.layers.get(name, "auto") for name in LAYERS}
    matrix = out["matrix"]
    if "white" not in section.layers and matrix != "auto":
        if not (isinstance(matrix, dict) and matrix.get("with_white")):
            out["white"] = "off"
    return out


def downbeat_ms(text: str) -> int:
    """`M:SS.mmm` in milliseconds."""
    minutes, seconds = text.split(":")
    return round((int(minutes) * 60 + float(seconds)) * 1000)


def _argb(colour: str) -> int:
    """`#RRGGBB` as the opaque ARGB word the script stores."""
    return 0xFF000000 | int(colour[1:], 16)


def _ticks(start: int, end: int, step: float) -> list[int]:
    """Times from `start`, every `step` ms, before `end`."""
    out, k = [], 0
    while start + k * step < end:
        out.append(int(round(start + k * step)))
        k += 1
    return out


def _shape(keys: list[Key], start: int, end: int) -> list[Key]:
    """`keys` fitted to [start, end]: dark until the first key, held after the last, and
    every rise from dark made sharp with a dark key 1 ms before it (levels are linear
    between keys, so without it a fixture would fade up through its dark step)."""
    out = [] if keys and keys[0].t <= start else [Key(start, 0)]
    for k in keys:
        prev = out[-1] if out else None
        if prev is not None and prev.level == 0 and k.level > 0 and k.t - prev.t > 1:
            out.append(Key(k.t - 1, 0))
        out.append(Key(k.t, k.level))
    if out[-1].t < end:
        out.append(Key(end, out[-1].level))
    return out


def _dark(start: int, end: int) -> list[Key]:
    return [Key(start, 0), Key(end, 0)]


@dataclass
class _Window:
    """A section's bars (inclusive), its span in ms (inclusive) and the beat at its start."""

    first: int
    last: int
    start: int
    end: int
    beat: float

    @property
    def bars(self) -> str:
        return f"bar {self.first}" if self.first == self.last else f"bars {self.first}–{self.last}"


@dataclass
class _Fixture:
    """A rig fixture resolved in the venue: its tracks by role (`"mover"`; `"master"` and
    `(row, col)` for a Vorlane; `"fan"` and `"fog"` for the haze) and what is missing."""

    key: str
    kind: str
    tracks: dict = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)

    def cell_items(self) -> list[tuple[tuple[int, int], Track]]:
        """The Vorlane's `((row, col), track)` pairs, top-left first."""
        return sorted(((r, t) for r, t in self.tracks.items() if isinstance(r, tuple)),
                      key=lambda item: item[0])

    def cells(self, white: bool) -> list[Track]:
        """The W row's cell tracks (`white=True`) or the colour rows' (`white=False`)."""
        return [t for (row, _), t in self.cell_items() if (row == WHITE_ROW) == white]


@dataclass
class _Edit:
    """One fixture track's share of a layer: intensity keys, a colour and position flags
    (indices into `palette`), over the whole section (`span` None) or a part of it."""

    trk: Track
    keys: list[Key] | None = None
    colour: int | None = None
    flags: list[PositionFlag] | None = None
    palette: list[tuple[str, int]] | None = None
    span: tuple[int, int] | None = None

    def lanes(self) -> set[str]:
        """The lanes this edit writes across the whole section."""
        if self.span is not None:
            return set()
        written = {"intensity": self.keys, "colour": self.colour, "position": self.flags}
        return {lane for lane, value in written.items() if value is not None}

    def apply(self, w: _Window) -> None:
        start, end = self.span or (w.start, w.end)
        if self.keys is not None:
            set_intensity(self.trk, start, end, _shape(self.keys, start, end))
        if self.colour is not None:
            set_colour(self.trk, start, end, self.colour)
        if self.flags is not None:
            set_positions(self.trk, start, end, self.flags, self.palette)


@dataclass
class _Job:
    script: TrackScript           # the copy being edited
    grid: Grid
    rig: Rig
    venue: VenueInfo
    tracks: list[Track]           # the script's tracks of the venue's nodes
    fixtures: list[_Fixture]
    presets: list[Preset]
    cues: list[ManualCue] = field(default_factory=list)

    def cue(self, bar: int, t: int, fixture: str, what: str) -> None:
        self.cues.append(ManualCue(bar, t, fixture, what))

    def kind(self, kind: str, w: _Window, layer: str) -> list[_Fixture]:
        """The rig's fixtures of `kind`, with a cue for each part the venue lacks."""
        found = [f for f in self.fixtures if f.kind == kind]
        if not found:
            self.cue(w.first, w.start, layer, f"{layer}, {w.bars}: the rig has no {kind}; not compiled")
        for f in found:
            if f.missing:
                self.cue(w.first, w.start, f.key, f"{layer}, {w.bars}: skipped {'; '.join(f.missing)}")
        return found

    def beat_time(self, w: _Window, text: str, layer: str) -> int | None:
        """The time of `<bar>.<beat>` when it falls inside the section, else a cue."""
        bar, beat = (int(x) for x in text.split("."))
        t = self.grid.ms(bar, beat)
        if w.start <= t < w.end:
            return t
        self.cue(bar, t, layer, f"{layer} {text} is outside {w.bars} of its section; not compiled")
        return None


def compile_choreography(
    choreo: Choreography,
    script: TrackScript,
    rig: Rig,
    venues: list[VenueInfo],
    presets: list[Preset],
) -> tuple[TrackScript, list[ManualCue]]:
    """Apply `choreo` to a copy of `script`; the input is never changed.

    Refuses (`CompileError`) a script with more than 8 tempo anchors, a `grid` that is not
    the script's first anchor (within 0.01 BPM and 2 ms), a script no venue holds, and a
    result that breaks `soundswitch_format.check`. Fixtures are found by node name in the
    venue that holds the script's node ids; what cannot be written becomes a `ManualCue`.

    Per section: when `hue` changes a Main lane (intensity; colour too when `hue` has a
    `colour`), Main's current content in that lane is first materialised into every leaf
    node of the venue (groups carry no content) whose own layer in this section does not
    write that lane, so only the chandelier changes; then Main is edited; then movers,
    matrix, white, strobe and haze write their nodes (white last over the W cells). `uv`
    is always a manual cue."""
    _check_grid(choreo, script)
    out = copy.deepcopy(script)
    venue, trks = _venue_of(out, venues)
    fixtures = _resolve(rig, venue, {t.node: t for t in trks})
    job = _Job(out, grid(out), rig, venue, trks, fixtures, presets)
    for section in choreo.sections:
        _compile_section(job, section)
    problems = check(out)
    if problems:
        raise CompileError("the compiled script breaks the format's rules:\n  " + "\n  ".join(problems))
    return out, job.cues


def _check_grid(choreo: Choreography, script: TrackScript) -> None:
    if not script.tempo:
        raise CompileError("the script has no tempo map")
    if len(script.tempo) > MAX_ANCHORS:
        raise CompileError(
            f"the script's tempo map has {len(script.tempo)} anchors (at most {MAX_ANCHORS} "
            "compile): bar numbers would not follow the music"
        )
    t0, bpm0 = script.tempo[0]
    bpm, downbeat = float(choreo.grid["bpm"]), str(choreo.grid["downbeat"])
    if abs(bpm - bpm0) > GRID_BPM_TOLERANCE + 1e-9 or abs(downbeat_ms(downbeat) - t0) > GRID_MS_TOLERANCE:
        raise CompileError(
            f"grid {bpm:g} BPM at {downbeat} does not match the script's first tempo anchor "
            f"({bpm0:g} BPM at {t0} ms): the choreography was written for another version of the track"
        )


def _venue_of(script: TrackScript, venues: list[VenueInfo]) -> tuple[VenueInfo, list[Track]]:
    """The venue holding most of the script's node ids, and the script's tracks of its
    nodes (taken from the script venue with the same GUID when there is one)."""
    best, best_tracks = None, []
    for info in venues:
        ids = {n.id for n in info.nodes}
        same = [v for v in script.venues if v.guid.lower() == info.guid.lower()]
        trks = [t for v in (same or script.venues) for t in v.tracks if t.node in ids]
        if len(trks) > len(best_tracks):
            best, best_tracks = info, trks
    if best is None:
        raise CompileError("no venue holds this script's nodes: compile it with its own project's venues")
    return best, best_tracks


def _find(nodes: list[VenueNode], name: str, index: int = 1, parent: int | None = None) -> VenueNode | None:
    """The `index`-th node (1-based, venue order) named `name`, under `parent` if given."""
    hits = [n for n in nodes if n.name == name and (parent is None or n.parent == parent)]
    return hits[index - 1] if 1 <= index <= len(hits) else None


def _want(res: _Fixture, role, node_id: int | None, label: str, by_node: dict[int, Track],
          venue: VenueInfo) -> None:
    if node_id is None:
        res.missing.append(f"{label} is not in venue {venue.name!r}")
    elif node_id not in by_node:
        res.missing.append(f"{label} (node {node_id}) has no track in this script")
    else:
        res.tracks[role] = by_node[node_id]


def _resolve(rig: Rig, venue: VenueInfo, by_node: dict[int, Track]) -> list[_Fixture]:
    """Each rig fixture (but the chandelier, which is Main) with its tracks, by node name."""
    out = []
    for fx in rig.fixtures.values():
        if fx.kind == "hue-chandelier":
            continue
        res = _Fixture(fx.key, fx.kind)
        out.append(res)
        index = fx.index or 1
        node = _find(venue.nodes, fx.node, index)
        if node is None:
            res.missing.append(f"node {fx.node!r}" + (f" #{index}" if fx.index else "")
                               + f" is not in venue {venue.name!r}")
            continue
        if fx.kind == "mover":
            _want(res, "mover", node.id, repr(fx.node), by_node, venue)
        elif fx.kind == "matrix":
            table = unit_cells(venue.nodes, node.id)
            _want(res, "master", table["master"], f"MASTER of {fx.node!r}", by_node, venue)
            lost = []
            for row in range(len(COLOUR_ROWS) + 1):
                for col in range(MATRIX_COLS):
                    nid = cell_node(table, row, col)
                    if nid in by_node:
                        res.tracks[(row, col)] = by_node[nid]
                    else:
                        kind, number = cell_zone(row, col)
                        lost.append(f"{kind.upper()} {number}")
            if lost:
                res.missing.append(f"cells {', '.join(lost)} of {fx.node!r} have no node or track")
        elif fx.kind == "haze":
            for role in ("fan", "fog"):
                name = fx.extra.get(role)
                if name is None:
                    res.missing.append(f"the rig names no {role} channel")
                    continue
                child = _find(venue.nodes, name, 1, parent=node.id)
                _want(res, role, child.id if child else None, repr(name), by_node, venue)
    return out


def _compile_section(job: _Job, section: Section) -> None:
    first, last = section.bars
    start, end = job.grid.ms(first), job.grid.ms(last + 1) - 1
    w = _Window(first, last, start, end, job.grid.beat_ms(start))
    layers = section_layers(section)
    edits = (_compile_movers(job, w, layers["movers"]) + _compile_matrix(job, w, layers["matrix"])
             + _compile_white(job, w, layers["white"]) + _compile_strobe(job, w, layers["strobe"])
             + _compile_haze(job, w, layers["haze"]))  # fmt: skip
    if layers["uv"] != "auto":
        job.cue(first, start, "movers", f"UV {layers['uv']}, {w.bars}: {UV_WARNING}")
    if layers["hue"] != "auto":
        state, colour = _compile_hue(layers["hue"])
        changed = {"intensity"} | ({"colour"} if colour is not None else set())
        owned: dict[int, set[str]] = {}
        for e in edits:
            owned.setdefault(e.trk.node, set()).update(e.lanes())
        groups = _group_ids(job.venue)
        for trk in job.tracks:
            if trk.node in groups:
                continue                # groups carry no content; their leaves are materialised
            lanes = changed - owned.get(trk.node, set())
            if lanes:
                materialise_main(job.script, trk, start, end, frozenset(lanes))
        set_main(job.script, start, end, _shape(hue_keys(state, start, end, w.beat), start, end), colour)
    for e in edits:
        e.apply(w)


def _group_ids(venue: VenueInfo) -> set[int]:
    """The venue's group nodes: a node with children, or one without a look (an empty
    group such as "Group 4"). Real scripts never give them content."""
    return {n.id for n in venue.nodes if n.look is None} | {
        n.parent for n in venue.nodes if n.parent is not None}


def _compile_hue(value) -> tuple[str, int | None]:
    """`(state, colour or None)` of a hue layer; `off` is `dark`."""
    if isinstance(value, dict):
        return value["state"], (_argb(value["colour"]) if "colour" in value else None)
    return ("dark" if value == "off" else value), None


def _compile_movers(job: _Job, w: _Window, value) -> list[_Edit]:
    if value == "auto":
        return []
    if isinstance(value, dict) and value["move"] == "uv":
        job.cue(w.first, w.start, "movers", f"UV wash, {w.bars}: {UV_WARNING}")
        return []
    fixtures = [f for f in job.kind("mover", w, "movers") if "mover" in f.tracks]
    if value == "off":
        return [_Edit(f.tracks["mover"], keys=_dark(w.start, w.end)) for f in fixtures]
    colour = _argb(value["colour"]) if "colour" in value else None
    named = _preset_guids(job, w, value)
    edits = []
    for i, f in enumerate(fixtures):
        trk = f.tracks["mover"]
        keys = mover_keys(value, w.start, w.end, w.beat, i, first_bar=w.first)
        flags, palette = _position_flags(job, w, value, named, trk, f.key)
        if flags is not None:
            _cue_cut_shapes(job, w, trk, f.key)
        edits.append(_Edit(trk, keys=keys, colour=colour, flags=flags, palette=palette))
    return edits


def _cue_cut_shapes(job: _Job, w: _Window, trk: Track, who: str) -> None:
    """`set_positions` removes every shape block (G) that overlaps the span whole, so a
    block reaching outside the section loses its outer part too: say so."""
    for g in trk.shapes.items if trk.shapes else []:
        overlaps = g.end > w.start and g.start < w.end
        if overlaps and (g.start < w.start or g.end > w.end):
            bars = f"bars {job.grid.bar_at(g.start)}–{job.grid.bar_at(g.end)}"
            job.cue(w.first, w.start, who,
                    f"shape block {g.start}–{g.end} ms ({bars}) extends outside {w.bars} of its "
                    "section and is removed whole; restore its movement outside the section in SoundSwitch")


def _preset_guids(job: _Job, w: _Window, move: dict) -> list[tuple[str, str]]:
    """`(name, guid)` of the move's positions in order; an unknown name becomes a cue."""
    names = move.get("positions") or ([move["position"]] if "position" in move else [])
    by_name: dict[str, str] = {}
    for p in job.presets:
        by_name.setdefault(p.name, p.guid)
    out, reported = [], set()
    for name in names:
        if name in by_name:
            out.append((name, by_name[name]))
        elif name not in reported:
            reported.add(name)
            job.cue(w.first, w.start, "movers",
                    f"position preset {name!r}, {w.bars}: not a preset of the venue; aim the movers by hand")
    return out


def _position_flags(job: _Job, w: _Window, move: dict, named: list[tuple[str, str]], trk: Track,
                    who: str) -> tuple[list[PositionFlag] | None, list[tuple[str, int]] | None]:
    """Flags for a mover: one at the start for a single position, else one per step,
    cycling through the positions. They index the track's own palette, else Main's."""
    if not named:
        return None, None
    main = job.script.main.positions
    palette = (trk.positions.palette if trk.positions and trk.positions.palette
               else main.palette if main else [])
    where: dict[str, int] = {}
    for i, (guid, _) in enumerate(palette):
        where.setdefault(guid.lower(), i)
    usable = []
    for name, guid in named:
        if guid.lower() in where:
            usable.append(where[guid.lower()])
        else:
            job.cue(w.first, w.start, who,
                    f"position preset {name!r}, {w.bars}: not in this script's palette; set it in SoundSwitch")
    if not usable:
        return None, None
    times = [w.start] if len(usable) == 1 else [s for s, _ in _steps(move, w.start, w.end, w.beat, w.first)]
    return [PositionFlag(t, usable[i % len(usable)]) for i, t in enumerate(times)], palette


def _compile_matrix(job: _Job, w: _Window, value) -> list[_Edit]:
    """A draw: per-cell pulses (decay = one step) from the frames, the draw's colour on
    the colour cells and the unit's MASTER held at full. `off`: the colour cells dark."""
    if value == "auto":
        return []
    units = job.kind("matrix", w, "matrix")
    if value == "off":
        return [_Edit(t, keys=_dark(w.start, w.end)) for u in units for t in u.cells(white=False)]
    draw = value["draw"]
    step = rate_ms(value.get("rate", DEFAULT_RATE), w.beat)
    with_white = bool(value.get("with_white", False))
    mirror = bool(value.get("mirror", False))
    colour = _argb(value.get("colour", DRAW_COLOURS[draw]))
    white_level = level_of(job.rig.white_max)
    edits = []
    for u, unit in enumerate(units):
        frames = matrix_frames(draw, w.start, w.end, step, u, mirror, with_white=with_white)
        if value.get("pingpong"):
            frames = [f for k, f in enumerate(frames) if k % 2 == u % 2]
        lit: dict[tuple[int, int], list[int]] = {}
        for t, cells in frames:
            for cell in cells:
                lit.setdefault(cell, []).append(t)
        if "master" in unit.tracks:
            edits.append(_Edit(unit.tracks["master"], keys=[Key(w.start, FULL), Key(w.end, FULL)]))
        for cell, trk in unit.cell_items():
            is_white = cell[0] == WHITE_ROW
            if is_white and not with_white:
                continue
            keys = pulse_keys(lit.get(cell, []), step, white_level if is_white else FULL, end=w.end)
            edits.append(_Edit(trk, keys=keys, colour=None if is_white else colour))
    return edits


def _compile_white(job: _Job, w: _Window, value) -> list[_Edit]:
    """The W cells: dark (`off`), a one-beat flash per accent, or flashes at a rate; never
    above `white_max`."""
    if value == "auto":
        return []
    units = job.kind("matrix", w, "white")
    level = level_of(job.rig.white_max)
    if value == "off":
        keys = _dark(w.start, w.end)
    elif "accent" in value:
        times = [job.beat_time(w, hit, "white") for hit in value["accent"]]
        keys = pulse_keys(sorted({t for t in times if t is not None}), w.beat, level, end=w.end)
    else:
        step = rate_ms(value["flash"], w.beat)
        keys = pulse_keys(_ticks(w.start, w.end, step), step, level, end=w.end)
    return [_Edit(t, keys=keys) for u in units for t in u.cells(white=True)]


def _compile_strobe(job: _Job, w: _Window, value) -> list[_Edit]:
    """v1 strobe: 1/16 pulses on the movers and the colour cells, one beat per `hit`, the
    `roll` bars clipped to the section. `off` cannot remove SoundSwitch's own strobe
    blocks yet, so it is a cue where the span has some."""
    if value == "auto":
        return []
    if value == "off":
        busy = [f.key for f in job.fixtures if any(
            t.strobes and any(s.start <= w.end and s.end >= w.start for s in t.strobes.items)
            for t in f.tracks.values())]
        if busy:
            job.cue(w.first, w.start, "strobe",
                    f"strobe off, {w.bars}: remove the strobe blocks of {', '.join(busy)} in SoundSwitch")
        return []
    movers = [f.tracks["mover"] for f in job.kind("mover", w, "strobe") if "mover" in f.tracks]
    targets = movers + [t for u in job.kind("matrix", w, "strobe") for t in u.cells(white=False)]
    windows = []
    for hit in value.get("hit", []):
        t = job.beat_time(w, hit, "strobe")
        if t is not None:
            bar, beat = (int(x) for x in hit.split("."))
            windows.append((t, min(job.grid.ms(bar, beat + 1) - 1, w.end)))
    if "roll" in value:
        a, b = value["roll"]
        want = (job.grid.ms(a), job.grid.ms(b + 1) - 1)
        lo, hi = max(want[0], w.start), min(want[1], w.end)
        if (lo, hi) != want:
            job.cue(a, want[0], "strobe", f"strobe roll {a}–{b} runs outside {w.bars} of its section; "
                                          + ("clipped to it" if lo < hi else "not compiled"))
        if lo < hi:
            windows.append((lo, hi))
    step = rate_ms(STROBE_RATE, w.beat)
    edits = []
    for lo, hi in windows:
        keys = pulse_keys(_ticks(lo, hi, step), step, end=hi)
        edits += [_Edit(t, keys=keys, span=(lo, hi)) for t in targets]
    return edits


def _compile_haze(job: _Job, w: _Window, value) -> list[_Edit]:
    """Fog and fan levels (both typed Intensity in the venue): `on` full, `off` dark,
    `burst` fog full for N seconds with the fan on across the section. Experimental."""
    if value == "auto":
        return []
    full = [Key(w.start, FULL), Key(w.end, FULL)]
    if value == "off":
        fog = fan = _dark(w.start, w.end)
    elif value == "on":
        fog = fan = full
    else:
        stop = min(w.start + int(value["burst"][:-1]) * 1000 - 1, w.end)
        fog = [Key(w.start, FULL), Key(stop, FULL)] + ([Key(stop + 1, 0)] if stop < w.end else [])
        fan = full
    what = value if isinstance(value, str) else f"burst {value['burst']}"
    edits = []
    for f in job.kind("haze", w, "haze"):
        job.cue(w.first, w.start, f.key, f"haze {what}, {w.bars}: {HAZE_WARNING}")
        edits += [_Edit(f.tracks[role], keys=keys) for role, keys in (("fog", fog), ("fan", fan))
                  if role in f.tracks]
    return edits
