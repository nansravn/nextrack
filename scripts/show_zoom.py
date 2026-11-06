"""show_zoom.py — the zoom: a moment of a compiled show at 1/16 of a beat (spec section 7 of
docs/superpowers/specs/2026-11-06-show-critic-design.md).

One column per 1/16 step, a `|` at each bar line, the music on top and the light below. The
music lanes come straight from the map's step data: `onsets.kick`, `onsets.perc`, and
`steps.bass`, `steps.vocals`, `steps.other`. The light lanes are what `compile` would write.
Each section's envelopes come from the compiler's own generators (`lightshow.mover_keys`,
`lightshow.matrix_frames`, `lightshow.hue_keys`, `lightshow.pulse_keys`), called the way
`lightshow.compile_choreography` calls them:
- the mover index and the matrix unit, in the rig's order;
- the matrix's `mirror` and `pingpong` step parity (the first Vorlane the even steps);
- a white accent of one beat, and the strobe's 1/16 pulses written over the movers and the
  colour cells (a hit for one beat, a roll over its bars).
They are shaped as the compiler shapes them and timed with its own steps and ticks (its
private helpers `lightshow._shape`, `_steps` and `_ticks`, read, never changed). They are
sampled at the start of each step on the map's grid (`soundswitch_format.Grid` on the map's
tempo anchors), taking the level in force there: linear between keys, as
`soundswitch_format.level_at` reads a lane. A section keeps the beat of its first step, as the
compiler does, so across a tempo anchor inside a section the light drifts from the grid there
too. `tests/test_show_zoom.py` checks every lane against a script compiled by
`lightshow.compile_choreography`.

The zoom needs no SoundSwitch project, so it assumes every rig fixture is in the venue and
every preset is in the script's palette. Where the compiler would leave a manual cue instead,
the zoom still draws the light. Nothing here reads a file or raises on bad content.

Python API: `render_zoom`, `step_times`, `colour_letters`, `moment_names`, `moment_target`.
"""
from __future__ import annotations

import bisect
import math
import re
import string
from collections.abc import Callable
from dataclasses import dataclass

import lightshow
import show_room
import show_views
import soundswitch_format as ssf
from show_language import CompiledSection, CompiledShow, CompiledTrack, layer_word
from soundswitch_format import Key

STEPS_PER_BAR = 16
LABEL_WIDTH = 11
MUSIC_LANES = (("kick", "onsets"), ("perc", "onsets"), ("bass", "steps"), ("vocals", "steps"),
               ("other", "steps"))
HOUSE_RIG = (("mover", "NE"), ("mover", "SE"), ("matrix", "NW"), ("matrix", "SW"))   # lightshows/rig.yml's order
HOUSE_WHITE_MAX = 0.6                    # the house rig's white strip ceiling, used without a rig
AUTOSCRIPT_COLOUR = "autoscript colour"  # a lit layer that writes no colour keeps the autoscript's
AIM_DIGITS = "123456789"
FRAME_RE = re.compile(r"([1-9][0-9]*)\.([1-4])")      # a beat of `--frames`: <bar>.<beat>
COLOUR_CELLS = [(r, c) for r in lightshow.COLOUR_ROWS for c in range(lightshow.MATRIX_COLS)]
WHITE_CELLS = [(lightshow.WHITE_ROW, c) for c in range(lightshow.MATRIX_COLS)]
_BEAT_RE = re.compile(r"([0-9]+)\.([0-9]+)")


# --------------------------------------------------------------- envelopes --


class _Envelope:
    """Intensity keys as a lane holds them, read at any time."""

    def __init__(self, keys: list[Key]):
        self.keys = keys
        self.times = [k.t for k in keys]

    def at(self, t: float) -> float:
        """The level at `t`, from 0 to 1 (the u32 level / 2**32), as `soundswitch_format.level_at`
        reads a lane: 0 before the first key, linear between two keys, the last level after
        the last key."""
        i = bisect.bisect_right(self.times, t)
        if i == 0:
            return 0.0
        if i == len(self.keys):
            return self.keys[-1].level / 2**32
        a, b = self.keys[i - 1], self.keys[i]
        return (a.level + (b.level - a.level) * (t - a.t) / (b.t - a.t)) / 2**32


def _shaped(keys: list[Key], start: int, end: int) -> _Envelope:
    """`keys` fitted to [start, end] the way the compiler writes them (`lightshow._shape`)."""
    return _Envelope(lightshow._shape(keys, start, end))


def _grid(map_data: dict) -> ssf.Grid | None:
    """The map's grid: its tempo anchors `[ms, bpm]`, as `set_timeline` reads them; None when
    the map has none."""
    grid = map_data.get("grid") if isinstance(map_data, dict) else None
    anchors = grid.get("anchors") if isinstance(grid, dict) else None
    try:
        return ssf.Grid([(int(ms), float(bpm)) for ms, bpm in anchors])
    except (TypeError, ValueError):
        return None


def step_times(map_data: dict, first: int, last: int) -> list[int]:
    """The start, in ms, of every 1/16 step of bars `first`..`last` on the map's grid: step j
    (0-15) of bar b is `Grid.ms(b, 1 + j / 4)` on the map's tempo anchors. [] without a grid."""
    grid = _grid(map_data)
    if grid is None:
        return []
    return [grid.ms(b, 1 + j / 4) for b in range(first, last + 1) for j in range(STEPS_PER_BAR)]


def _beat(text: object) -> tuple[int, int] | None:
    m = _BEAT_RE.fullmatch(str(text))
    return (int(m[1]), int(m[2])) if m else None


# ------------------------------------------------------------ the sections --


@dataclass
class _Light:
    """A section as the compiler writes it: the envelope of each lane (None where the layer is
    `auto` and the compiler writes nothing, so the autoscript plays) and the legend key of
    each fixture group's colour."""
    name: str
    movers: list[_Envelope] | None
    mover_colour: str
    units: list[dict] | None             # per unit, {(row, col): envelope} of the colour cells
    unit_white: list[dict]               # per unit, the W cells a `with_white` draw writes
    matrix_colour: str
    white: _Envelope | None              # the white layer's W cells
    strobe: list[tuple[int, int, _Envelope]] | None   # the windows the strobe writes over
    hue: _Envelope | None
    aims: list[tuple[int, str]] | None   # (time, aim) as the movers' position flags; [] dark
    uv: str                              # the uv lane's glyph over the section

    def strobe_at(self, t: int) -> _Envelope | None:
        """The strobe window that writes at `t`, the last one when two overlap."""
        for lo, hi, env in reversed(self.strobe or []):
            if lo <= t <= hi:
                return env
        return None

    def mover(self, i: int, t: int) -> tuple[float | None, str]:
        env = self.strobe_at(t)
        if env is not None:
            return env.at(t), self.mover_colour
        if self.movers is None:
            return None, ""
        return self.movers[i].at(t), self.mover_colour

    def unit(self, u: int, t: int) -> tuple[float | None, str]:
        """The highest level of the unit's colour cells at `t`."""
        env = self.strobe_at(t)
        if env is not None:
            return env.at(t), self.matrix_colour
        if self.units is None:
            return None, ""
        return max(e.at(t) for e in self.units[u].values()), self.matrix_colour

    def cell(self, u: int, cell: tuple[int, int], t: int) -> bool | None:
        """Whether a cell of unit `u` is lit at `t`; None when the autoscript decides."""
        if cell[0] == lightshow.WHITE_ROW:
            if self.white is not None:
                return self.white.at(t) > 0
            if self.unit_white:
                return self.unit_white[u][cell].at(t) > 0
            return None
        env = self.strobe_at(t)
        if env is not None:
            return env.at(t) > 0
        if self.units is None:
            return None
        return self.units[u][cell].at(t) > 0

    def white_glyph(self, t: int) -> str:
        if self.white is not None:
            return "#" if self.white.at(t) > 0 else " "
        if self.unit_white:
            return "#" if any(e.at(t) > 0 for cells in self.unit_white for e in cells.values()) else " "
        return "~"

    def strobe_glyph(self, t: int) -> str:
        if self.strobe is None:
            return "~"
        env = self.strobe_at(t)
        return "x" if env is not None and env.at(t) > 0 else " "

    def aim_at(self, t: int) -> str:
        """The aim of the last position flag at or before `t` (the first flag is at the
        section's start); call it only when `aims` is not empty."""
        i = bisect.bisect_right([at for at, _ in self.aims], t)
        return self.aims[max(i - 1, 0)][1]


@dataclass
class _Context:
    grid: ssf.Grid
    movers: int
    units: int
    white_max: float
    colour_key: Callable[[object], str]   # a layer's `colour` (#RRGGBB or None) -> its legend key
    room: show_room.Room | None


def _light(section: CompiledSection, ctx: _Context) -> _Light:
    """The section's lanes, as `lightshow._compile_section` writes them: its span is bar `a`
    beat 1 to one ms before bar `b + 1`, the beat is the grid's at the span's start, and the
    layers get the compiler's defaults (`lightshow.section_layers`)."""
    grid = ctx.grid
    first, last = section.bars
    start, end = grid.ms(first), grid.ms(last + 1) - 1
    beat = grid.beat_ms(start)
    raw = {k: layer_word(v) for k, v in section.layers.items()}
    layers = lightshow.section_layers(lightshow.Section(tuple(section.bars), section.name, section.intent, raw))
    dark = _shaped([], start, end)
    mv, mx, wh, st, hu, uv = (layers[k] for k in ("movers", "matrix", "white", "strobe", "hue", "uv"))
    moving = isinstance(mv, dict) and mv.get("move") != "uv"     # `move: uv` writes nothing yet

    movers, mover_colour, aims = None, AUTOSCRIPT_COLOUR, None
    if mv == "off":
        movers, aims = [dark] * ctx.movers, []
    elif moving:
        movers = [_shaped(lightshow.mover_keys(mv, start, end, beat, i, first_bar=first), start, end)
                  for i in range(ctx.movers)]
        mover_colour = ctx.colour_key(mv.get("colour"))
        names = show_views.section_aims(section, ctx.room)
        if len(names) == 1:
            aims = [(start, names[0])]            # one flag at the start
        elif names:                               # one flag per step, cycling
            steps = lightshow._steps(mv, start, end, beat, first)
            aims = [(s, names[i % len(names)]) for i, (s, _) in enumerate(steps)]

    units, unit_white, matrix_colour = None, [], AUTOSCRIPT_COLOUR
    if mx == "off":
        units = [{cell: dark for cell in COLOUR_CELLS} for _ in range(ctx.units)]
    elif isinstance(mx, dict):
        draw = mx["draw"]
        step = lightshow.rate_ms(mx.get("rate", lightshow.DEFAULT_RATE), beat)
        with_white = bool(mx.get("with_white", False))
        matrix_colour = ctx.colour_key(mx.get("colour", lightshow.DRAW_COLOURS[draw]))
        units = []
        for u in range(ctx.units):
            frames = lightshow.matrix_frames(draw, start, end, step, u, bool(mx.get("mirror", False)),
                                             with_white=with_white)
            if mx.get("pingpong"):
                frames = [f for k, f in enumerate(frames) if k % 2 == u % 2]
            lit: dict[tuple[int, int], list[int]] = {}
            for t, cells in frames:
                for cell in cells:
                    lit.setdefault(cell, []).append(t)

            def pulses(cell: tuple[int, int], level: int) -> _Envelope:
                return _shaped(lightshow.pulse_keys(lit.get(cell, []), step, level, end=end), start, end)

            units.append({cell: pulses(cell, ssf.FULL) for cell in COLOUR_CELLS})
            if with_white:
                unit_white.append({cell: pulses(cell, lightshow.level_of(ctx.white_max)) for cell in WHITE_CELLS})

    white = None
    if wh == "off":
        white = dark
    elif isinstance(wh, dict):
        level = lightshow.level_of(ctx.white_max)
        if "accent" in wh:
            hits = [grid.ms(*b) for b in map(_beat, wh["accent"]) if b is not None]
            keys = lightshow.pulse_keys(sorted({t for t in hits if start <= t < end}), beat, level, end=end)
        else:
            flash = lightshow.rate_ms(wh["flash"], beat)
            keys = lightshow.pulse_keys(lightshow._ticks(start, end, flash), flash, level, end=end)
        white = _shaped(keys, start, end)

    strobe = None
    if st == "off":
        strobe = []
    elif isinstance(st, dict):
        windows = []
        for b in map(_beat, st.get("hit", [])):
            t = grid.ms(*b) if b is not None else None
            if t is not None and start <= t < end:
                windows.append((t, min(grid.ms(b[0], b[1] + 1) - 1, end)))
        if "roll" in st:
            a, b = st["roll"]
            lo, hi = max(grid.ms(a), start), min(grid.ms(b + 1) - 1, end)
            if lo < hi:
                windows.append((lo, hi))
        sixteenth = lightshow.rate_ms(lightshow.STROBE_RATE, beat)
        strobe = [(lo, hi, _shaped(lightshow.pulse_keys(lightshow._ticks(lo, hi, sixteenth), sixteenth, end=hi),
                                   lo, hi)) for lo, hi in windows]

    hue = None
    if hu != "auto":
        state = hu["state"] if isinstance(hu, dict) else ("dark" if hu == "off" else hu)
        hue = _shaped(lightshow.hue_keys(state, start, end, beat), start, end)

    if uv == "on" or isinstance(mv, dict) and mv.get("move") == "uv":
        uv_glyph = "u"                            # the UV the choreography writes (spec section 9)
    else:
        uv_glyph = " " if uv == "off" else "~"
    return _Light(section.name, movers, mover_colour, units, unit_white, matrix_colour, white, strobe, hue,
                  aims, uv_glyph)


# ------------------------------------------------------------------ glyphs --


def colour_letters(names: list[str]) -> dict[str, str]:
    """One unique lower-case letter per colour name, in order: the first free letter among the
    initials of the name's words, then the name's other letters, then a-z ('?' past 26)."""
    out: dict[str, str] = {}
    used: set[str] = set()
    for name in names:
        lower = name.lower()
        words = [w for w in re.split(r"[^a-z]+", lower) if w]
        candidates = [w[0] for w in words] + [c for c in lower if c in string.ascii_lowercase]
        letter = next((c for c in candidates + list(string.ascii_lowercase) if c not in used), "?")
        used.add(letter)
        out[name] = letter
    return out


def _glyph(level: float | None, colour: str, letters: dict[str, str]) -> str:
    """A mover's or a Vorlane's glyph: `~` unknown (the autoscript), `.` dark, else the
    colour's letter, upper case at or above half level and lower case below it."""
    if level is None:
        return "~"
    if level <= 0:
        return "."
    letter = letters.get(colour, "?")
    return letter.upper() if level >= 0.5 else letter


def _digit(level: float | None) -> str:
    """The lustre's glyph: `~` unknown, `.` dark, else the level 0-9, `round(9 x level)`
    rounded half up."""
    if level is None:
        return "~"
    if level <= 0:
        return "."
    return str(min(9, math.floor(9 * level + 0.5)))


def _voice(map_data: dict, group: str, voice: str) -> str:
    """A step string of the map (`onsets.<voice>` or `steps.<voice>`), its chunks joined."""
    node = map_data.get(group) if isinstance(map_data, dict) else None
    value = node.get(voice) if isinstance(node, dict) else None
    if isinstance(value, list):
        return "".join(v for v in value if isinstance(v, str))
    return value if isinstance(value, str) else ""


def _row(label: str, cells: list[str]) -> str:
    return label.ljust(LABEL_WIDTH) + "|" + "|".join(cells)


# ----------------------------------------------------------------- targets --


def moment_names(show: CompiledShow) -> list[str]:
    """The show's moments, each once, in set order: the `moment` of a cue or a handover (a
    bridge's copied moment is not one)."""
    out: list[str] = []
    for track in show.tracks:
        for s in track.sections:
            if s.origin.kind != "bridge" and s.origin.moment and s.origin.moment not in out:
                out.append(s.origin.moment)
    return out


def moment_target(show: CompiledShow, name: str) -> tuple[int, int] | None:
    """`(track index, bar)` of the first cue or handover with that `moment` (its first bar), or
    None."""
    for i, track in enumerate(show.tracks):
        for s in track.sections:
            if s.origin.kind != "bridge" and s.origin.moment == name:
                return i, s.bars[0]
    return None


# ------------------------------------------------------------------ render --


def _fixtures(rig: lightshow.Rig | None) -> tuple[list[str], list[str], float]:
    """The movers' and the Vorlanes' corners in the rig's order (the compiler's mover index
    and matrix unit) and the white strip's ceiling; the house rig without one."""
    if rig is None:
        pairs = list(HOUSE_RIG)
        white_max = HOUSE_WHITE_MAX
    else:
        pairs = [(f.kind, f.corner or f.key) for f in rig.fixtures.values()]
        white_max = rig.white_max
    return ([c for k, c in pairs if k == "mover"], [c for k, c in pairs if k == "matrix"], white_max)


def _section_at(track: CompiledTrack, bar: int) -> int | None:
    return next((i for i, s in enumerate(track.sections) if s.bars[0] <= bar <= s.bars[1]), None)


def render_zoom(show: CompiledShow, track_index: int, bar: int, before: int, after: int, frames: list[str],
                clock: show_views.ShowClock | None, *, rig: lightshow.Rig | None = None,
                room: show_room.Room | None = None, label: str | None = None) -> str:
    """The zoom of bars `bar - before` .. `bar + after` (inside the map) of the track at
    `track_index`, one column per 1/16 step and a `|` at each bar line (spec section 7):

    - a header: the track's title, the target (`label (bar N)`, or `bar N`), the bars and,
      with a clock, their span on the set clock (`show_views.clock_text`);
    - the bar numbers and the section that holds each bar (`~`: none, the autoscript plays);
    - `music`: `onsets.kick`, `onsets.perc`, `steps.bass`, `steps.vocals`, `steps.other`;
    - `light`, sampled at each step's start (see the module docstring). A mover or a Vorlane
      (whether any of its colour cells is lit) shows the colour's legend letter, upper case at
      or above half level, lower case below, `.` dark. The lustre shows its level 0-9 (`.`
      dark). `white` (`#`), `strobe` (`x`) and `uv` (`u`) mark the steps their layer fills.
      The aim lane names the aim in force (`show_views.section_aims`, aim ids through
      `room`), one change per movers step for `positions`; a bar where it changes, or whose
      name is longer than a bar, shows a legend digit per aim; `-` when the movers are dark.
      A layer at `auto` (or no section) is `~` all along;
    - the legend: each colour shown, one unique letter per palette colour (`colour_letters`);
    - with `frames` (`<bar>.<beat>` texts), both Vorlanes' 8x7 cells at each beat, side by
      side, rows top to bottom, `#` lit, `.` dark, `~` unknown.

    `rig` gives the fixtures' order and corners (the house rig without one): movers and
    Vorlanes in rig order are the compiler's mover index and matrix unit."""
    if not 0 <= track_index < len(show.tracks):
        return f"track {track_index} is not a track of the show\n"
    track = show.tracks[track_index]
    data = track.map
    title = track.track.split(" — ", 1)[-1]
    total = data.get("bars") if isinstance(data.get("bars"), int) else 0
    first, last = max(1, bar - max(before, 0)), min(total, bar + max(after, 0))
    target = f"{label} (bar {bar})" if label else f"bar {bar}"
    head = [title, target, f"bars {first}-{last}"]
    if clock is not None and track_index < len(clock.tracks) and first <= last:
        head.append(f"{show_views.clock_text(clock.at(track_index, first))}-"
                    f"{show_views.clock_text(clock.at(track_index, last + 1))}")
    out = [" · ".join(head)]
    grid = _grid(data)
    if grid is None or first > last:
        out.append(f"  nothing to zoom: {'the map has no tempo anchors' if grid is None else f'the map has {total} bars'}")
        return "\n".join(out) + "\n"

    mover_corners, unit_corners, white_max = _fixtures(rig)
    palette = show.data.get("palette") if isinstance(show.data, dict) else None
    palette = palette if isinstance(palette, dict) else {}
    hex_names = {str(h).upper(): str(n) for n, h in palette.items()}

    def colour_key(value: object) -> str:
        return hex_names.get(str(value).upper(), str(value).upper()) if isinstance(value, str) else AUTOSCRIPT_COLOUR

    ctx = _Context(grid, len(mover_corners), len(unit_corners), white_max, colour_key, room)
    lights: dict[int, _Light] = {}

    def light_of(b: int) -> _Light | None:
        i = _section_at(track, b)
        if i is None:
            return None
        if i not in lights:
            lights[i] = _light(track.sections[i], ctx)
        return lights[i]

    bars = list(range(first, last + 1))
    times = {b: [grid.ms(b, 1 + j / 4) for j in range(STEPS_PER_BAR)] for b in bars}
    held = {b: light_of(b) for b in bars}
    blank = "~" * STEPS_PER_BAR

    def sampled(sample) -> list[list[tuple[float | None, str]]]:
        return [[sample(held[b], t) if held[b] is not None else (None, "") for t in times[b]] for b in bars]

    colour_lanes = [(f"mover {c}", sampled(lambda lt, t, i=i: lt.mover(i, t))) for i, c in enumerate(mover_corners)]
    unit_lanes = [(f"vorl. {c}", sampled(lambda lt, t, u=u: lt.unit(u, t))) for u, c in enumerate(unit_corners)]
    used = {colour for _, lane in colour_lanes + unit_lanes for cells in lane for level, colour in cells
            if level is not None and level > 0}
    order = [str(name) for name in palette]          # every palette colour: stable letters per show
    order += sorted(c for c in used if c not in order and c != AUTOSCRIPT_COLOUR)   # hex colours off the palette
    order += [AUTOSCRIPT_COLOUR] if AUTOSCRIPT_COLOUR in used else []
    letters = colour_letters(order)

    def glyphs(lane) -> list[str]:
        return ["".join(_glyph(level, colour, letters) for level, colour in cells) for cells in lane]

    def per_step(glyph) -> list[str]:
        return ["".join(glyph(held[b], t) for t in times[b]) if held[b] is not None else blank for b in bars]

    digits: dict[str, str] = {}
    aims_shown: list[str] = []

    def aim_cell(b: int) -> str:
        lt = held[b]
        if lt is None or lt.aims is None:
            return blank
        if not lt.aims:
            return "-".ljust(STEPS_PER_BAR)
        names = [lt.aim_at(t) for t in times[b]]
        aims_shown.extend(n for n in dict.fromkeys(names) if n not in aims_shown)
        if len(set(names)) == 1 and len(names[0]) <= STEPS_PER_BAR:
            return names[0].ljust(STEPS_PER_BAR)
        for name in names:
            digits.setdefault(name, AIM_DIGITS[len(digits)] if len(digits) < len(AIM_DIGITS) else "+")
        return "".join(digits[name] for name in names)

    out.append(_row("", [str(b).ljust(STEPS_PER_BAR) for b in bars]))
    out.append(_row("section", [(held[b].name if held[b] else "~")[:STEPS_PER_BAR].ljust(STEPS_PER_BAR)
                                for b in bars]))
    out.append("music")
    for voice, group in MUSIC_LANES:
        text = _voice(data, group, voice)
        out.append(_row(f"  {voice}", [text[(b - 1) * STEPS_PER_BAR:b * STEPS_PER_BAR].ljust(STEPS_PER_BAR)
                                       for b in bars]))
    out.append("light")
    out += [_row(f"  {name}", glyphs(lane)) for name, lane in colour_lanes]
    out.append(_row("  aim", [aim_cell(b) for b in bars]))
    out.append(_row("  uv", [held[b].uv * STEPS_PER_BAR if held[b] else blank for b in bars]))
    out += [_row(f"  {name}", glyphs(lane)) for name, lane in unit_lanes]
    out.append(_row("  lustre", per_step(lambda lt, t: _digit(lt.hue.at(t) if lt.hue is not None else None))))
    if unit_corners:
        out.append(_row("  white", per_step(lambda lt, t: lt.white_glyph(t))))
    out.append(_row("  strobe", per_step(lambda lt, t: lt.strobe_glyph(t))))

    shown = [name for name in order if name in used]
    legend = []
    if shown:
        legend.append(", ".join(f"{letters[n]}/{letters[n].upper()} {n}" for n in shown)
                      + " (lower case: below half level; . dark)")
    legend += ["lustre 0-9 (. dark)", "white #, strobe x, uv u (blank: none)", "~ autoscript (auto, or no section)"]
    out.append("legend: " + "; ".join(legend))
    if digits:
        out.append("aims: " + ", ".join(f"{d} {name}" for name, d in digits.items()))
    pending = _pending(aims_shown, room)
    if pending:
        out.append("pending aims, played by their fallback: " + ", ".join(pending))
    if frames:
        out += _frames(frames, total, grid, light_of, unit_corners)
    return "\n".join(out) + "\n"


def _pending(aims: list[str], room: show_room.Room | None) -> list[str]:
    """`aim -> fallback` for each pending aim of the room among `aims`: the aim lane names the
    aim, while its fallback's preset is the one that plays (`show_room.resolve_aim`)."""
    out = []
    for aim in aims:
        known = room.aims.get(aim) if room is not None else None
        if known is not None and known.status == "pending":
            preset, chain, _ = show_room.resolve_aim(room, aim)
            out.append(f"{aim} -> {chain[-1] if preset is not None else 'no fallback'}")
    return out


def _frames(frames: list[str], total: int, grid: ssf.Grid, light_of: Callable[[int], _Light | None],
            unit_corners: list[str]) -> list[str]:
    """Both Vorlanes' 8x7 cells at each `<bar>.<beat>`, side by side, rows top to bottom."""
    out = ["", "frames: the Vorlanes' cells, rows top to bottom (the 4th is the white strip); "
               "# lit, . dark, ~ autoscript"]
    if not unit_corners:
        return out + ["  the rig has no Vorlane"]
    for text in frames:
        m = FRAME_RE.fullmatch(str(text).strip())
        if not m:
            out.append(f"  {text}: not <bar>.<beat>")
            continue
        b, beat = int(m[1]), int(m[2])
        if not 1 <= b <= total:
            out.append(f"  {text}: bar {b} is outside 1-{total}")
            continue
        t = grid.ms(b, beat)
        lt = light_of(b)
        out.append(f"  {b}.{beat} · {lt.name if lt else '~'}")
        out.append("    " + "  ".join(f"vorl. {c}".ljust(lightshow.MATRIX_COLS) for c in unit_corners))
        for row in range(len(lightshow.COLOUR_ROWS) + 1):
            out.append("    " + "  ".join(
                "".join(_cell(lt, u, (row, col), t) for col in range(lightshow.MATRIX_COLS))
                for u in range(len(unit_corners))))
    return out


def _cell(lt: _Light | None, u: int, cell: tuple[int, int], t: int) -> str:
    lit = lt.cell(u, cell, t) if lt is not None else None
    return "~" if lit is None else "#" if lit else "."
