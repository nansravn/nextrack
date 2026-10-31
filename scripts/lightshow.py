"""lightshow.py — the rig and choreography models, the light vocabulary and their schema checks.

`lightshows/rig.yml` describes the room, `lightshows/tracks/*.yml` the light script of
one track, `lightshows/sets/*.md` the effect budget of a set. This module loads the first
two into dataclasses and holds the pure `problems_*` checks that `check_repo.py` wraps
into rules. The checks take parsed YAML (possibly with the loader's `__line__` keys) and
return messages; they never raise on bad content. See lightshows/README.md.

Python API: `load_rig`, `load_choreography`, `problems_rig`, `problems_choreography`,
`problems_plan`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from soundswitch_format import FULL, Key

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


def cell_node(rig_unit_nodes: dict, row: int, col: int) -> int:
    """The node number of the cell at (`row`, `col`), row-major: rows 0-2 are RGB 01-24,
    row 3 is W 1-8, rows 4-6 are RGB 25-48. `rig_unit_nodes` may map `"rgb"` / `"w"` to a
    dict or list that renames these numbers; without it the number itself is returned."""
    if row == WHITE_ROW:
        kind, number = "w", col + 1
    else:
        kind, number = "rgb", (row if row < WHITE_ROW else row - 1) * MATRIX_COLS + col + 1
    table = rig_unit_nodes.get(kind) if rig_unit_nodes else None
    if table is None:
        return number
    return table[number] if isinstance(table, dict) else table[number - 1]


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


def pulse_keys(times: list[int], decay_ms: float, level: int = FULL) -> list[Key]:
    """The autoscript's pulse: `Key(t, level)` then `Key(t + decay - 1, 0)`. A decay that
    would run into the next pulse ends one ms before it, so keys stay sorted and unique."""
    keys: list[Key] = []
    for i, t in enumerate(times):
        stop = t + int(decay_ms) - 1
        if i + 1 < len(times):
            stop = min(stop, times[i + 1] - 1)
        keys.append(Key(t, level))
        if stop > t:
            keys.append(Key(stop, 0))
    return keys


def _steps(move: dict, start: int, end: int, beat_ms: float) -> list[tuple[int, int]]:
    """`(begin, finish)` of each step of a mover move. `faster_from` is a bar number counted
    from `start` (1 = first bar of the span); from there `faster_every` replaces `every`."""
    slow = rate_ms(move.get("every", "1/4"), beat_ms)
    fast = rate_ms(move["faster_every"], beat_ms) if "faster_every" in move else slow
    faster_from = move.get("faster_from")
    steps = []
    t = float(start)
    while t < end:
        bar = int((t - start) // (4 * beat_ms)) + 1
        length = fast if faster_from is not None and bar >= faster_from else slow
        steps.append((int(round(t)), min(int(round(t + length)), end)))
        t += length
    return steps


def mover_keys(move: dict, start: int, end: int, beat_ms: float, mover_index: int) -> list[Key]:
    """The brightness envelope of one mover over [start, end] for a `movers` mapping."""
    kind = move["move"]
    if kind in ("hold", "sweep"):
        lvl = level_of(move.get("level", STEADY))
        return [Key(start, lvl), Key(end, lvl)]
    steps = _steps(move, start, end, beat_ms)
    if kind == "blink":
        return pulse_keys([s for s, _ in steps], rate_ms(move.get("every", "1/4"), beat_ms))
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
        return pulse_keys(times, beat_ms)
    raise ValueError(f"unknown hue state {state!r}")
