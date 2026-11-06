"""show_views.py — the critic's views of a compiled show: the set clock, the light and music
levels, the voices, the night summary, the peak table, the hit checks and the strips.

Every view reads the compiled show (the sections `build` writes, with their provenance), the
maps inside it and, to name aims, the room. Nothing here reads a file or raises on bad
content. Every number comes from a function whose docstring states its formula: the spec's,
docs/superpowers/specs/2026-11-06-show-critic-design.md, sections 3 to 6.

**Two windows per track** (spec section 3, decision 10). The **leg** is `[B, G)`: the first
track plays from bar 1, the last runs to its last non-silent bar (`set_timeline.last_bar`).
It is the track's share of the night's time. The **sounding window** runs from the leg's
first bar to the track's last compiled bar, so it holds the handover that still sounds after
`G`. **States** (looks, colours, aims, zones, dark) are summed over legs, so no moment is
counted twice: during a mix the time belongs to the incoming track, whose bridge copies the
outgoing handover. **Events** (accents, strobe, UV, moments, map drops) are listed over
sounding windows, at their own clock.

Python API: `light_values`, `light_level`, `music_level`, `voices`, `TrackClock`, `ShowClock`,
`build_clock`, `section_aims`, `night_summary`, `peaks`, `hit_checks`, `strips`, `clock_text`.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import lightshow
import set_timeline
import show_room
import show_rules
from show_language import CompiledSection, CompiledShow, CompiledTrack, layer_word

COLOUR_GROUPS = ("movers", "matrix", "hue")     # the zones: movers east, Vorlanes west, lustre centre
VOICE_ORDER = ("kick", "bass", "vocals", "perc", "other")
MUSIC_VOICES = ("kick", "bass", "other")       # vocals are shown apart (spec section 5)
STEPS_PER_BAR = 16

# The light-level table (spec section 4): each layer's value in 0-1.
DEFAULT_LEVEL = 0.85                            # a movers mapping without `level`
MOVER_FACTORS = {"hold": 1.0, "sweep": 1.0, "pingpong": 0.5, "blink": 0.5}   # x level
MOVER_UV = 0.3
DRAW_SHARES = {"solid": 1.0, "fill-up": 0.6, "rows-down": 1 / 6, "rows-up": 1 / 6, "columns": 1 / 8,
               "centre-out": 0.25, "arrow-up": 0.15, "zigzag": 1 / 48}      # lit share of the colour cells
MATRIX_PINGPONG = 0.5
MATRIX_DECAY = 0.6                              # draws pulse and decay
HUE_VALUES = {"dark": 0.0, "off": 0.0, "pulse": 0.5, "bright": 0.85}
WEIGHTS = (0.4, 0.4, 0.2)                       # movers, matrix, hue

_BEAT_RE = re.compile(r"([0-9]+)\.([0-9]+)")
_ACCENT_ORDER = ("white", "flash", "strobe", "roll", "uv")


def _num(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _add(totals: dict, key: str, seconds: float) -> None:
    totals[key] = totals.get(key, 0.0) + seconds


# ------------------------------------------------------------------ levels --


def _mover_value(value: object) -> float | None:
    value = layer_word(value)
    if value == "off":
        return 0.0
    if not isinstance(value, dict):
        return None                             # auto, unset, or not a word of the table
    move = value.get("move")
    if move == "uv":
        return MOVER_UV
    level = value.get("level", DEFAULT_LEVEL)
    if move not in MOVER_FACTORS or not _num(level):
        return None
    return level * MOVER_FACTORS[move]


def _matrix_value(value: object) -> float | None:
    value = layer_word(value)
    if value == "off":
        return 0.0
    if not isinstance(value, dict) or not isinstance(value.get("draw"), str) or value["draw"] not in DRAW_SHARES:
        return None
    share = DRAW_SHARES[value["draw"]] * (MATRIX_PINGPONG if value.get("pingpong") is True else 1.0)
    return share * MATRIX_DECAY


def _hue_state(value: object) -> object:
    value = layer_word(value)
    return value.get("state") if isinstance(value, dict) else value


def _hue_value(value: object) -> float | None:
    state = _hue_state(value)
    return HUE_VALUES.get(state) if isinstance(state, str) else None


def light_values(layers: dict) -> tuple[float | None, float | None, float | None]:
    """The 0-1 values of a section's movers, matrix and hue layers, from the table in
    `light_level`'s docstring; None for a layer that is `auto`, unset or outside the table."""
    return (_mover_value(layers.get("movers")), _matrix_value(layers.get("matrix")),
            _hue_value(layers.get("hue")))


def light_level(layers: dict) -> int | None:
    """The light level of a section, an index from 0 to 9 and not a measurement (spec section
    4): `round(9 x (0.4 x movers + 0.4 x matrix + 0.2 x hue))`, rounded half up, each layer's
    value in 0-1 being (`light_values`):

        movers  off 0; hold, sweep: level (default 0.85); pingpong, blink: level x 0.5; uv: 0.3
        matrix  off 0; per draw, the lit share of the colour cells: solid 1, fill-up 0.6,
                rows-* 1/6, columns 1/8, centre-out 0.25, arrow-up 0.15, zigzag 1/48;
                x 0.5 with pingpong; then x 0.6 (draws pulse and decay)
        hue     dark, off 0; pulse 0.5; bright 0.85

    None (shown `~`: the autoscript decides) when the movers, the matrix or the hue is `auto`,
    unset or outside the table. The `white`, `strobe` and `uv` layers do not enter the level;
    they show as accents."""
    values = light_values(layers)
    if any(v is None for v in values):
        return None
    total = sum(w * v for w, v in zip(WEIGHTS, values))
    return max(0, min(9, math.floor(9 * total + 0.5 + 1e-9)))   # the 1e-9 keeps 4.4999... a half


def _bar_text(map_data: dict, voice: str) -> str:
    voices_ = map_data.get("voices") if isinstance(map_data, dict) else None
    entry = voices_.get(voice) if isinstance(voices_, dict) else None
    text = entry.get("bars") if isinstance(entry, dict) else None
    return text if isinstance(text, str) else ""


def _digit(char: str) -> int:
    return int(char) if len(char) == 1 and char in "0123456789" else 0


def music_level(map_data: dict, bar: int) -> int:
    """The music level of a bar, 0-9: the highest of its `kick`, `bass` and `other` levels in
    the map (`voices.<voice>.bars`, one digit per bar). Vocals are shown apart (`voices`). A
    bar outside the map is 0."""
    if bar < 1:
        return 0
    return max(_digit(_bar_text(map_data, v)[bar - 1:bar]) for v in MUSIC_VOICES)


def voices(map_data: dict, first: int, last: int) -> dict[str, int]:
    """The highest level of each voice over bars `first`..`last` (both included) of the map,
    `{"kick", "bass", "vocals", "perc", "other"}` in that order; 0 for a voice with no bar in
    that range (an empty range, or bars outside the map)."""
    lo = max(first, 1)
    return {v: max((_digit(c) for c in _bar_text(map_data, v)[lo - 1:max(last, 0)]), default=0)
            for v in VOICE_ORDER}


# ------------------------------------------------------------------- clock --


@dataclass
class TrackClock:
    index: int
    leg: tuple[int, int]            # [first, last] played bars: B..G-1 (the first from 1, the last to last_bar)
    sounding: tuple[int, int]       # [the leg's first bar, the last compiled bar (at least the leg's last)]
    start_s: float                  # set clock at the start of the leg's first bar
    tempo: tuple[float, float]      # the played tempo at the leg's first and last bar

    @property
    def played(self) -> int:
        """The leg's length in bars."""
        return max(self.leg[1] - self.leg[0] + 1, 0)

    def at(self, bar: int) -> float:
        """Seconds on the set clock at the start of `bar` of this track:
        `start_s + set_timeline.seconds(tempo, played, bar - first)`, `first` being the leg's
        first bar and `played` its length. Each bar takes 240 / tempo seconds, the tempo
        ramping linearly over the leg (each bar at its mid tempo) and keeping its end value
        past it: a bar at or after G (a handover event, the outgoing music during a mix) is
        clock(G) plus the bars from G at the end tempo. A bar before the leg, which the set
        never plays, counts back at the start tempo: `start_s - (first - bar) x 240 / t0`."""
        first = self.leg[0]
        if bar >= first:
            return self.start_s + set_timeline.seconds(self.tempo, self.played, bar - first)
        return self.start_s - (first - bar) * 240 / self.tempo[0]

    def span_s(self, first: int, last: int) -> float:
        """Seconds of bars `first`..`last` (both included): `at(last + 1) - at(first)`."""
        return self.at(last + 1) - self.at(first) if last >= first else 0.0

    def sounds(self, bar: int) -> bool:
        """Whether `bar` is inside the sounding window."""
        return self.sounding[0] <= bar <= self.sounding[1]


@dataclass
class ShowClock:
    tracks: list[TrackClock]

    def at(self, track_index: int, bar: int) -> float:
        """Seconds on the set clock at the start of `bar` of the track at `track_index` in set
        order, also past its G (see `TrackClock.at`)."""
        return self.tracks[track_index].at(bar)

    @property
    def total_s(self) -> float:
        """The night's length: the sum of the legs, the clock at the end of the last one."""
        if not self.tracks:
            return 0.0
        last = self.tracks[-1]
        return last.start_s + set_timeline.seconds(last.tempo, last.played, last.played)


def _cue_bar(map_data: dict, letter: str) -> int | None:
    """The bar of a stored hot cue (`bar.beat`, with or without a ms offset), as set_timeline
    counts it: the bar, whatever the beat; None when the map does not have it."""
    cues = map_data.get("hot_cues")
    if not isinstance(cues, dict) or letter not in cues:
        return None
    m = set_timeline.CUE_BAR_RE.fullmatch(str(cues[letter]))
    return int(m[1]) if m else None


def _tempo(given: object, map_data: dict) -> tuple[float, float]:
    """The played tempo from the block's tracklist, when it is two positive numbers; else the
    map's `bpm` at both ends."""
    if isinstance(given, (tuple, list)) and len(given) == 2 and all(_num(t) and t > 0 for t in given):
        return float(given[0]), float(given[1])
    bpm = float(map_data["grid"]["bpm"])
    return bpm, bpm


def build_clock(show: CompiledShow, tempos: dict[str, tuple[float, float]]) -> ShowClock:
    """The set clock, set_timeline's model (spec section 3). Track i (of n) plays bars
    `[first, stop)`: `first` is 1 for the first track and its hot cue B otherwise (1 without
    one); `stop` is its hot cue G, or `last_bar + 1` for the last track (and for a track
    without G). It starts when the track before reaches its G: `start_s` is the sum of the legs
    before it, a leg taking `set_timeline.seconds(tempo, played, played)`. `tempos` maps a show
    track ("Artist — Title") to its played tempo range (`check_repo.show_tempos`); without one,
    the map's `bpm` at both ends. The sounding window ends at the last compiled bar, or at the
    leg's last bar when that is later."""
    out: list[TrackClock] = []
    clock = 0.0
    n = len(show.tracks)
    for i, track in enumerate(show.tracks):
        data = track.map
        b, g = _cue_bar(data, "B"), _cue_bar(data, "G")
        first = 1 if i == 0 or b is None else b
        stop = g if i < n - 1 and g is not None else set_timeline.last_bar(data) + 1
        played = max(stop - first, 0)
        leg = (first, first + played - 1)
        compiled_last = max((s.bars[1] for s in track.sections), default=leg[1])
        tempo = _tempo(tempos.get(track.track), data)
        out.append(TrackClock(i, leg, (first, max(leg[1], compiled_last)), clock, tempo))
        clock += set_timeline.seconds(tempo, played, played)
    return ShowClock(out)


def clock_text(seconds: float) -> str:
    """`m:ss`, or `h:mm:ss` from an hour on, of the seconds rounded to the nearest second (as
    set_timeline's clock)."""
    s = round(seconds)
    sign, s = ("-", -s) if s < 0 else ("", s)
    hours, rest = divmod(s, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{sign}{hours}:{minutes:02d}:{secs:02d}" if hours else f"{sign}{minutes}:{secs:02d}"


# ----------------------------------------------------------------- helpers --


def _section_at(track: CompiledTrack, bar: int) -> CompiledSection | None:
    """The compiled section that holds `bar`, or None (the autoscript plays it)."""
    return next((s for s in track.sections if s.bars[0] <= bar <= s.bars[1]), None)


def _section_before(show: CompiledShow, clock: ShowClock, i: int,
                    bar: int) -> tuple[CompiledSection | None, CompiledTrack]:
    """The section that plays just before `bar` of track `i`, and the track that holds it: the
    section holding bar - 1 of the same track; but when bar - 1 is before the track's leg (its
    B, the bar it enters on) and a track comes before it, the previous track's section at the
    last bar of that track's leg (G - 1), which is what plays then."""
    if i > 0 and bar - 1 < clock.tracks[i].leg[0]:
        prev = show.tracks[i - 1]
        return _section_at(prev, clock.tracks[i - 1].leg[1]), prev
    return _section_at(show.tracks[i], bar - 1), show.tracks[i]


def _level(section: CompiledSection | None) -> int | None:
    return light_level(section.layers) if section is not None else None


def _look_name(section: CompiledSection) -> str:
    """A section's look for the summary: its gesture's name, else its look (a bridge has the
    look of the handover it copies), else `inline`."""
    return section.origin.gesture or section.origin.look or "inline"


def _palette_names(show: CompiledShow) -> dict[str, str]:
    palette = show.data.get("palette") if isinstance(show.data, dict) else None
    if not isinstance(palette, dict):
        return {}
    return {str(hexa).upper(): name for name, hexa in palette.items()}


def _colour_text(value: object, names: dict[str, str]) -> str:
    return names.get(value.upper(), value) if isinstance(value, str) else "autoscript"


def _lit_colour(group: str, value: object, names: dict[str, str]) -> str | None:
    """The colour a lit layer shows, by palette name (the hex when the palette has no name for
    it), or None when the layer is not lit: a zone is lit when its layer is neither `off`,
    `dark` nor `auto` (or unset). Movers in `move: uv` show `uv`; a matrix draw without a
    colour shows the draw's colour (`lightshow.DRAW_COLOURS`); movers or a hue without one keep
    the autoscript's colour (`autoscript`)."""
    value = layer_word(value)
    if group == "hue":
        state = _hue_state(value)
        if state not in ("pulse", "bright"):
            return None
        return _colour_text(value.get("colour") if isinstance(value, dict) else None, names)
    if not isinstance(value, dict):
        return None
    if group == "movers" and value.get("move") == "uv":
        return "uv"
    colour = value.get("colour")
    if colour is None and group == "matrix" and isinstance(value.get("draw"), str):
        colour = lightshow.DRAW_COLOURS.get(value["draw"])
    return _colour_text(colour, names)


def _aim_names(values: list[str], aims: tuple[str, ...], room: show_room.Room | None) -> list[str]:
    """Each compiled preset of `position` + `positions`, named by aim. The section's aim ids
    (`origin.aims`, in the order the compiler resolved them) are matched to the values they
    compiled to, from the last one back; any other value is a raw preset, named by its aim when
    exactly one configured aim uses it. Matching from the end gives an aim id to `positions`,
    the field the movers cycle, when a raw `position` compiled to the same preset (the compiled
    section cannot tell the two apart)."""
    reverse = show_room.preset_aims(room) if room is not None else {}
    resolved = [show_room.resolve_aim(room, a)[0] if room is not None else None for a in aims]
    out, k = [], len(aims) - 1
    for value in reversed(values):
        if k >= 0 and value == resolved[k]:
            out.append(aims[k])
            k -= 1
        else:
            out.append(reverse.get(value, value))
    return out[::-1]


def section_aims(section: CompiledSection, room: show_room.Room | None) -> list[str]:
    """The aims a section's movers cycle, in order, as the compiler reads them: `positions`,
    else `position`. A value the section named by aim id keeps that id (a pending aim too,
    though its fallback's preset plays); a raw preset is named by its aim id when exactly one
    configured aim of the room uses it (`show_room.preset_aims`), else by the preset itself.
    Empty when the movers are not a mapping or name no position."""
    movers = layer_word(section.layers.get("movers"))
    if not isinstance(movers, dict):
        return []
    position = [movers["position"]] if isinstance(movers.get("position"), str) else []
    positions = movers.get("positions")
    positions = [p for p in positions if isinstance(p, str)] if isinstance(positions, list) else []
    named = _aim_names(position + positions, tuple(section.origin.aims), room)
    return named[len(position):] if positions else named


def _beats(value: object) -> list[tuple[int, int]]:
    """`(bar, beat)` of each `bar.beat` of a list of beats."""
    if not isinstance(value, list):
        return []
    return [(int(m[1]), int(m[2])) for item in value if (m := _BEAT_RE.fullmatch(str(item)))]


def _roll(strobe: dict, section: CompiledSection) -> tuple[int, int]:
    roll = strobe.get("roll")
    if isinstance(roll, list) and len(roll) == 2 and all(isinstance(b, int) and not isinstance(b, bool) for b in roll):
        return roll[0], roll[1]
    return section.bars


def _accents(section: CompiledSection | None, bar: int, first_beat: bool = False) -> list[str]:
    """The accents at `bar` (with `first_beat`, on its first beat only), in this order:
    `white` (a white accent there), `flash` (a white flash over the section), `strobe` (a
    strobe hit there), `roll` (a strobe roll over the bar), `uv` (`uv: on` or `move: uv`)."""
    if section is None:
        return []
    layers, found = section.layers, set()
    white, strobe, movers = (layer_word(layers.get(k)) for k in ("white", "strobe", "movers"))

    def on(beats: object) -> bool:
        return any(b == bar and (not first_beat or beat == 1) for b, beat in _beats(beats))

    if isinstance(white, dict):
        if on(white.get("accent")):
            found.add("white")
        if "flash" in white:
            found.add("flash")
    if isinstance(strobe, dict):
        if on(strobe.get("hit")):
            found.add("strobe")
        if "roll" in strobe:
            a, b = _roll(strobe, section)
            if a <= bar <= b:
                found.add("roll")
    if layer_word(layers.get("uv")) == "on" or isinstance(movers, dict) and movers.get("move") == "uv":
        found.add("uv")
    return [a for a in _ACCENT_ORDER if a in found]


def _kick(map_data: dict, bar: int) -> str:
    """The kick onset strength on the bar's first 1/16 step (`onsets.kick`), `.` for none."""
    onsets = map_data.get("onsets") if isinstance(map_data, dict) else None
    kick = onsets.get("kick") if isinstance(onsets, dict) else None
    text = "".join(k for k in kick if isinstance(k, str)) if isinstance(kick, list) else kick
    step = (bar - 1) * STEPS_PER_BAR
    if not isinstance(text, str) or not 0 <= step < len(text):
        return "."
    return text[step]


def _first_of_cue(previous: CompiledSection | None, section: CompiledSection) -> bool:
    """Whether a section opens its cue (or handover): only a gesture makes several sections of
    one cue, and they share their gesture, file and line."""
    if previous is None or section.origin.gesture is None:
        return True
    p, o = previous.origin, section.origin
    return (p.kind, p.gesture, p.path, p.line) != (o.kind, o.gesture, o.path, o.line)


# ----------------------------------------------------------------- summary --


def _event_seconds(key: str, section: CompiledSection, clock: TrackClock) -> float:
    """Seconds of the occurrences of an effect key in one section, inside the sounding window:
    a white accent or a strobe hit lasts one beat (a quarter of its bar); a strobe roll its
    bars; a white flash and UV their section. Each occurrence is placed at the bar the budget
    counts it at (`show_rules.occurrences`)."""
    layers = section.layers
    white, strobe = layer_word(layers.get("white")), layer_word(layers.get("strobe"))
    a, b = section.bars
    total = 0.0

    def beats(value: object) -> float:
        return sum(clock.span_s(bar, bar) / 4 for bar, _ in _beats(value) if clock.sounds(bar))

    def span(first: int, last: int) -> float:
        lo, hi = max(first, clock.sounding[0]), min(last, clock.sounding[1])
        return clock.span_s(lo, hi) if clock.sounds(first) else 0.0

    if key == "white-accent" and isinstance(white, dict):
        total += beats(white.get("accent"))
    elif key == "white-flash" and isinstance(white, dict) and "flash" in white:
        total += span(a, b)
    elif key == "strobe" and isinstance(strobe, dict):
        total += beats(strobe.get("hit"))
        if "roll" in strobe:
            total += span(*_roll(strobe, section))
    elif key == "uv" and "uv" in _accents(section, a):
        total += span(a, b)
    return total


def night_summary(show: CompiledShow, clock: ShowClock, room: show_room.Room | None) -> dict:
    """The night summary (spec section 3), all times in seconds. States are summed over legs,
    a section's share being the seconds of its bars inside its track's leg
    (`TrackClock.span_s`); events are counted over sounding windows.

    - `total_s`: the sum of the legs (`ShowClock.total_s`).
    - `looks`: seconds per look (`origin.look`; a gesture's sections by gesture name; an
      inline look as `inline`); `autoscript_s`: leg bars no section holds.
    - `colours`: `{movers|matrix|hue: {colour: s}}`, the lit layers' colours by palette name
      (see `_lit_colour`).
    - `aims`: seconds per aim (`section_aims`); a section that cycles k aims gives each 1/k of
      its time (decision 12). `pending_aims`: `(aim, fallback)` for every pending aim any
      section names, in show order, the fallback being the configured aim that stood in.
    - `zones`: `{movers|matrix|hue: s}`, the seconds each zone is lit (movers east, Vorlanes
      west, lustre centre): its layer is neither `off`, `dark` nor `auto` (or unset).
    - `centre_dark_s`: seconds with hue `dark` or `off` (the share is `centre_dark_s / total_s`).
    - `total_dark`: `{s, count}`, the seconds and the number of total-dark sections (movers
      off, matrix off, hue dark, no lit white, strobe or uv: the `total-dark` rule's test).
    - `events`: `{key: {count, s}}` for each effect key (`show_rules.EFFECT_KEYS`). The count is
      the budget's occurrences (`show_rules.occurrences`, never a bridge) whose bar is inside
      its track's sounding window, so it equals the budget's count unless a cue starts before
      its track's B; the seconds are `_event_seconds`."""
    names = _palette_names(show)
    looks: dict[str, float] = {}
    colours: dict[str, dict[str, float]] = {g: {} for g in COLOUR_GROUPS}
    aims: dict[str, float] = {}
    zones = {g: 0.0 for g in COLOUR_GROUPS}
    autoscript = centre_dark = dark_s = 0.0
    dark_count = 0
    for track, tc in zip(show.tracks, clock.tracks):
        first, last = tc.leg
        held = [False] * tc.played
        for section in track.sections:
            lo, hi = max(section.bars[0], first), min(section.bars[1], last)
            if lo > hi:
                continue
            held[lo - first:hi - first + 1] = [True] * (hi - lo + 1)
            s = tc.span_s(lo, hi)
            _add(looks, _look_name(section), s)
            for group in COLOUR_GROUPS:
                colour = _lit_colour(group, section.layers.get(group), names)
                if colour is not None:
                    _add(colours[group], colour, s)
                    zones[group] += s
            cycled = section_aims(section, room)
            for aim in cycled:
                _add(aims, aim, s / len(cycled))
            if _hue_state(section.layers.get("hue")) in ("dark", "off"):
                centre_dark += s
            if show_rules._total_dark(section.layers):      # the total-dark rule's own test
                dark_s += s
                dark_count += 1
        autoscript += sum(tc.span_s(bar, bar) for bar, h in enumerate(held, first) if not h)
    return {
        "total_s": clock.total_s,
        "looks": looks,
        "autoscript_s": autoscript,
        "colours": colours,
        "aims": aims,
        "pending_aims": _pending_aims(show, room),
        "zones": zones,
        "centre_dark_s": centre_dark,
        "total_dark": {"s": dark_s, "count": dark_count},
        "events": _events(show, clock),
    }


def _pending_aims(show: CompiledShow, room: show_room.Room | None) -> list[tuple[str, str | None]]:
    out: list[tuple[str, str | None]] = []
    if room is None:
        return out
    for track in show.tracks:
        for section in track.sections:
            for aim in section.origin.aims:
                known = room.aims.get(aim)
                if known is None or known.status != "pending" or any(a == aim for a, _ in out):
                    continue
                preset, chain, _ = show_room.resolve_aim(room, aim)
                out.append((aim, chain[-1] if preset is not None else None))
    return out


def _events(show: CompiledShow, clock: ShowClock) -> dict[str, dict]:
    index = {track.track: i for i, track in enumerate(show.tracks)}
    out = {}
    for key in show_rules.EFFECT_KEYS:
        count = sum(1 for o in show_rules.occurrences(show, key)
                    if o.track in index and clock.tracks[index[o.track]].sounds(o.bar))
        seconds = sum(_event_seconds(key, section, tc)
                      for track, tc in zip(show.tracks, clock.tracks)
                      for section in track.sections if section.origin.kind != "bridge")
        out[key] = {"count": count, "s": seconds}
    return out


# ------------------------------------------------------------ peaks, hits --


def peaks(show: CompiledShow, clock: ShowClock) -> list[dict]:
    """The peak table (spec section 4): one row per map drop inside its track's sounding
    window (the outgoing music's drops during a mix included), sorted by clock. A row:
    `clock_s` (`ShowClock.at`), `index` and `track`, `bar`, `db` (the map's drop against the
    two bars before it, so a drop after a musical silence reads huge), `music`
    (`music_level`), `before` and `at` (`light_level` of the section that plays just before
    the bar and of the one holding it; None for `auto` or the autoscript), `accents`
    (`_accents` at the bar) and `moment` (of the section holding the bar; None for a bridge,
    whose moment is the copied handover's). The section before is the one holding bar - 1,
    except on the track's first leg bar (its B): there it is the previous track's section at
    the last bar of its leg (`_section_before`)."""
    rows = []
    for track, tc in zip(show.tracks, clock.tracks):
        for drop in track.map.get("drops") or []:
            bar = drop.get("bar") if isinstance(drop, dict) else None
            if not isinstance(bar, int) or isinstance(bar, bool) or not tc.sounds(bar):
                continue
            at = _section_at(track, bar)
            before, _ = _section_before(show, clock, tc.index, bar)
            moment = at.origin.moment if at is not None and at.origin.kind != "bridge" else None
            rows.append({"clock_s": tc.at(bar), "index": tc.index, "track": track.track, "bar": bar,
                         "db": drop.get("db"), "music": music_level(track.map, bar),
                         "before": _level(before), "at": _level(at),
                         "accents": _accents(at, bar), "moment": moment})
    return sorted(rows, key=lambda r: r["clock_s"])


def hit_checks(show: CompiledShow, clock: ShowClock) -> list[dict]:
    """The hit checks (spec section 6): one row per arrival (`role: arrival`) and per moment
    (the first section of a cue or handover with a `moment`; a bridge's copied moment is not
    one), inside the sounding window, in set order. A row: `clock_s`, `index`, `track`, `bar`
    (the section's first), `arrival` (bool), `moment` (or None), `kick` (the kick onset
    strength on the hit's first 1/16 step, `onsets.kick`, `.` = none), `before` and `at`
    (`light_level` of the section that plays just before the hit and of the hit's section),
    `accents` (`_accents` on the hit's first beat) and `dark`: when the section just before is
    total dark, `{track, bars, voices}`, the track that holds it, its bars and the voices'
    levels over them in that track's map (`voices`), else None. The section before is the one
    holding bar - 1, except on the track's first leg bar (its B, as with `bridge: false`):
    there it is the previous track's section at the last bar of its leg, and the voices are
    that track's, the music that plays then (`_section_before`)."""
    rows = []
    for track, tc in zip(show.tracks, clock.tracks):
        previous = None
        for section in track.sections:
            o, first = section.origin, _first_of_cue(previous, section)
            previous = section
            if o.kind == "bridge":
                continue
            arrival = o.role == "arrival"
            moment = o.moment if first else None
            bar = section.bars[0]
            if not (arrival or moment) or not tc.sounds(bar):
                continue
            before, holder = _section_before(show, clock, tc.index, bar)
            dark = None
            if before is not None and show_rules._total_dark(before.layers):
                dark = {"track": holder.track, "bars": tuple(before.bars), "voices": voices(holder.map, *before.bars)}
            rows.append({"clock_s": tc.at(bar), "index": tc.index, "track": track.track, "bar": bar,
                         "arrival": arrival, "moment": moment, "kick": _kick(track.map, bar),
                         "before": _level(before), "at": light_level(section.layers),
                         "accents": _accents(section, bar, first_beat=True), "dark": dark})
    return rows


def strips(track: CompiledTrack, clock: TrackClock) -> tuple[str, str]:
    """The music and light strips of a track (spec section 4): one character per bar of its
    leg, unwrapped. Music: `music_level` of the bar. Light: `light_level` of the section that
    holds the bar, `~` when it is unknown (`auto`) or no section holds it (the autoscript)."""
    first, last = clock.leg
    bars = range(first, last + 1)
    music = "".join(str(music_level(track.map, b)) for b in bars)
    light = "".join("~" if (lv := _level(_section_at(track, b))) is None else str(lv) for b in bars)
    return music, light
