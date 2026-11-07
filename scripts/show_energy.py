"""show_energy.py — energy per bar: the music's, the light's, and the light's change events
(spec sections A2 and A3 of docs/superpowers/specs/2026-11-07-show-team-design.md).

Every bar of a track's sounding window gets digits 0-9 (and, for the light, None when the
autoscript plays). The critic's analyses read these series; this module only measures.

Normalisation. `normalise(values, scope)` is `clip01((x - p5) / (p95 - p5))`, the percentiles
taken with `numpy.percentile` over `scope`, and 0.5 for every value when `p95 - p5 < 1e-9`.

Music energy, `E_music(b) = round(9 x sum(w x feature_hat))` (rounded half up), the features
of `BarMusic` normalised over a scope (the track's leg bars for the track views, every
track's leg bars for the night views), with `MUSIC_WEIGHTS`:
    loudness    the map's `mix.loudness` digit of the bar
    brightness  the map's `mix.brightness` digit (the share of power above 4 kHz)
    density     steps of the bar with a `kick` or `perc` onset of strength >= 3, over 16
    texture     voices (vocals, kick, perc, bass, other) whose bar digit is >= 6, 0-5
A map without `mix` (version 1) uses `INTERIM_WEIGHTS` (density 0.5, texture 0.5), and its
`TrackEnergy.interim` is True: the views mark the track `(interim)`.

Light per bar, from the 16 samples `show_zoom.sample_light` reads (the compiler's own
generators). The bar is unknown (`BarLight(None, None)`) when any sample has a None in
`movers`, `units` or `hue` (an `auto` layer, or no section). Otherwise each fixture group has a
level at every step (None counts 0):
    movers    mean of the movers' levels
    vorlanes  mean over the Vorlanes of level x coverage (brightness); for the rises, the
              share of a Vorlane's colour cells newly lit at the step (a column of eight
              lighting up is 1/8), averaged over the Vorlanes, because the highest cell
              hides a sweep of single columns
    lustre    the hue level
    white     the white strip's level
    strobe    1 when a strobe window is lit, else 0
`brightness` B is `sum(LIGHT_WEIGHTS x group mean level over the steps)`. A group's rise is a
step whose level is >= `RISE_LEVEL` (0.05) after a step below it (the first step compares
with the previous bar's last sample, `before`; with none, or an unknown one such as the
autoscript's, it counts no rise; at a leg's first bar `before` is the previous track's last
sample of its leg, what plays in the room then), and `activity`
A is `sum(LIGHT_WEIGHTS x group rises) / 16`. `E_light = round(9 x (0.5 x B_hat + 0.5 x A_hat))`
with B and A normalised over the night's known leg bars. `TrackEnergy.brightness` and
`.activity` are the night-normalised digits `round(9 x B_hat)` and `round(9 x A_hat)`.

Change events, `X(b)`: how many of `CHANGE_DIMENSIONS` (the identity dimensions after `look`
and `gesture`: movers.move, movers.rate, movers.colour, aim, matrix.draw, matrix.rate,
matrix.colour, hue.state, hue.colour) have a different value at bar b than at bar b - 1 of the
same track; 0 at the window's first bar. A dimension's value (`dimension_values`) is a tuple
of words: colours by palette name, `aim` the section's aim ids, `look` the origin's look else
its gesture else `inline`, `gesture` its gesture else `none`; an `auto` layer gives
`("auto",)`, an `off` layer `("off",)`, a missing key `("none",)`, and no section
`("auto",)` for every dimension. `signature` is the tuple of all the values, in the order of
`DIMENSIONS`.

Python API: `night_energy` (`TrackEnergy`), `music_bars` (`BarMusic`), `music_energy`,
`light_bars` (`BarLight`), `light_energy`, `normalise`, `dimension_values`, `signature`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

import show_views
import show_zoom
from show_language import IDENTITY_DIMENSIONS, CompiledSection, CompiledShow, layer_word

MUSIC_WEIGHTS = {"loudness": 0.4, "brightness": 0.2, "density": 0.2, "texture": 0.2}
INTERIM_WEIGHTS = {"density": 0.5, "texture": 0.5}
LIGHT_WEIGHTS = {"movers": 0.35, "vorlanes": 0.35, "lustre": 0.15, "white": 0.10, "strobe": 0.05}
DIMENSIONS = IDENTITY_DIMENSIONS
CHANGE_DIMENSIONS = IDENTITY_DIMENSIONS[2:]       # the nine layer dimensions (no look, no gesture)
RISE_LEVEL = 0.05
STEPS = 16
ONSET_MIN = 3
TEXTURE_MIN = 6
VOICES = ("vocals", "kick", "perc", "bass", "other")


@dataclass(frozen=True)
class BarMusic:
    loudness: int | None      # mix.loudness digit; None on a v1 map
    brightness: int | None
    density: float            # steps with a kick or perc onset >= 3, / 16
    texture: int              # voices whose bar digit is >= 6 (0-5)


@dataclass(frozen=True)
class BarLight:
    brightness: float | None  # weighted mean of level x coverage; None: unknown (auto)
    activity: float | None    # weighted dark->lit rises / 16


@dataclass
class TrackEnergy:
    index: int
    track: str
    first: int                # the bar of list index 0 (the sounding window's first bar)
    music: list[int]          # E_music, track scope
    music_night: list[int]    # E_music, night scope
    light: list[int | None]   # E_light, night scope
    brightness: list[int | None]   # night-normalised digits
    activity: list[int | None]
    changes: list[int]        # X(b)
    interim: bool

    def at(self, series: str, bar: int) -> int | None:
        """The value of `series` (an attribute name: music, music_night, light, brightness,
        activity, changes) at `bar`, None outside the window."""
        values = getattr(self, series)
        i = bar - self.first
        return values[i] if 0 <= i < len(values) else None


def _round(x: float) -> int:
    return math.floor(x + 0.5 + 1e-9)


def normalise(values: list[float], scope: list[float]) -> list[float]:
    """`clip01((x - p5) / (p95 - p5))` with the percentiles of `scope`; 0.5 for all when
    `p95 - p5 < 1e-9` (or the scope is empty)."""
    if not len(scope):
        return [0.5] * len(values)
    lo, hi = (float(p) for p in np.percentile(np.asarray(scope, dtype=float), [5, 95]))
    if hi - lo < 1e-9:
        return [0.5] * len(values)
    return [min(1.0, max(0.0, (float(x) - lo) / (hi - lo))) for x in values]


# ------------------------------------------------------------------- music --


def _digits(text: object, bars: int) -> list[int]:
    s = text if isinstance(text, str) else ""
    return [int(s[i]) if i < len(s) and s[i] in "0123456789" else 0 for i in range(bars)]


def _joined(chunks: object) -> str:
    return "".join(chunks) if isinstance(chunks, list) else ""


def music_bars(map_data: dict) -> list[BarMusic]:
    """One `BarMusic` per bar of the map (`bars`). `density` counts the steps with a kick or
    perc onset digit >= 3 (a `.` is no onset); `loudness` and `brightness` are None without
    the `mix` block."""
    n = map_data.get("bars") if isinstance(map_data.get("bars"), int) else 0
    onsets = map_data.get("onsets") if isinstance(map_data.get("onsets"), dict) else {}
    lanes = [_joined(onsets.get(v)) for v in ("kick", "perc")]
    voices = map_data.get("voices") if isinstance(map_data.get("voices"), dict) else {}
    levels = [_digits(voices[v].get("bars") if isinstance(voices.get(v), dict) else None, n) for v in VOICES]
    mix = map_data.get("mix") if isinstance(map_data.get("mix"), dict) else None
    loud = _digits(mix.get("loudness"), n) if mix else None
    bright = _digits(mix.get("brightness"), n) if mix else None
    out = []
    for b in range(n):
        hit = 0
        for j in range(b * STEPS, (b + 1) * STEPS):
            if any(j < len(lane) and lane[j] in "0123456789" and int(lane[j]) >= ONSET_MIN for lane in lanes):
                hit += 1
        out.append(BarMusic(loud[b] if loud else None, bright[b] if bright else None, hit / STEPS,
                            sum(1 for lv in levels if lv[b] >= TEXTURE_MIN)))
    return out


def music_energy(bars: list[BarMusic], scope: list[BarMusic]) -> list[int]:
    """`E_music` of each of `bars`, the features normalised over `scope` (module docstring).
    The interim weights apply when the bars carry no `mix`."""
    interim = any(b.loudness is None for b in bars)
    weights = INTERIM_WEIGHTS if interim else MUSIC_WEIGHTS
    total = [0.0] * len(bars)
    for name, w in weights.items():
        have = [getattr(b, name) for b in scope if getattr(b, name) is not None]
        hats = normalise([getattr(b, name) for b in bars], have)
        total = [t + w * h for t, h in zip(total, hats)]
    return [_round(9 * t) for t in total]


# ------------------------------------------------------------------- light --


def _levels(s: show_zoom.StepLight) -> dict[str, float]:
    movers = [x or 0.0 for x in s.movers]
    vor = [(u or 0.0) * (c or 0.0) for u, c in zip(s.units, s.coverage)]
    return {"movers": sum(movers) / len(movers) if movers else 0.0,
            "vorlanes": sum(vor) / len(vor) if vor else 0.0,
            "lustre": s.hue or 0.0, "white": s.white or 0.0, "strobe": 1.0 if s.strobe else 0.0}


def _unknown(s: show_zoom.StepLight) -> bool:
    return s.hue is None or None in s.movers or None in s.units


def _newly_lit(before: tuple, now: tuple) -> float | None:
    """The Vorlanes' rise at a step: the mean over the units of the share of their colour cells
    that are lit now and were dark before; None when either step has no cell flags."""
    if not before or not now or len(before) != len(now):
        return None
    shares = [sum(1 for a, b in zip(u0, u1) if b and not a) / len(u1) for u0, u1 in zip(before, now)]
    return sum(shares) / len(shares)


def light_bars(samples: list[show_zoom.StepLight], before: show_zoom.StepLight | None = None) -> list[BarLight]:
    """One `BarLight` per 16 samples (module docstring). `before` is the sample before the
    first one (the previous bar's last), against which the first step's rise is judged."""
    out = []
    known = before is not None and not _unknown(before)
    previous = _levels(before) if known else None
    last_cells = before.cells if known else ()
    for i in range(0, len(samples) - STEPS + 1, STEPS):
        chunk = samples[i:i + STEPS]
        levels = [_levels(s) for s in chunk]
        lit = [_newly_lit(a, b) for a, b in zip((last_cells,) + tuple(s.cells for s in chunk[:-1]),
                                                 (s.cells for s in chunk))]
        if any(_unknown(s) for s in chunk):
            out.append(BarLight(None, None))
        else:
            b = a = 0.0
            for g, w in LIGHT_WEIGHTS.items():
                b += w * sum(lv[g] for lv in levels) / STEPS
                last = previous[g] if previous is not None else None
                rises = 0.0
                for k, lv in enumerate(levels):
                    if g == "vorlanes" and lit[k] is not None:
                        rises += lit[k]
                    elif last is not None and last < RISE_LEVEL <= lv[g]:
                        rises += 1
                    last = lv[g]
                a += w * rises / STEPS
            out.append(BarLight(b, a))
        previous = levels[-1]
        last_cells = chunk[-1].cells
    return out


def _hats(bars: list[BarLight], scope: list[BarLight], field: str) -> list[float | None]:
    have = [getattr(b, field) for b in scope if getattr(b, field) is not None]
    known = [i for i, b in enumerate(bars) if getattr(b, field) is not None]
    hats = normalise([getattr(bars[i], field) for i in known], have)
    out: list[float | None] = [None] * len(bars)
    for i, h in zip(known, hats):
        out[i] = h
    return out


def light_energy(bars: list[BarLight], scope: list[BarLight]) -> list[int | None]:
    """`E_light` of each of `bars`, None where the bar is unknown; B and A normalised over the
    known bars of `scope`."""
    b_hat, a_hat = _hats(bars, scope, "brightness"), _hats(bars, scope, "activity")
    return [None if b is None or a is None else _round(9 * (0.5 * b + 0.5 * a)) for b, a in zip(b_hat, a_hat)]


def _digit_series(bars: list[BarLight], scope: list[BarLight], field: str) -> list[int | None]:
    return [None if h is None else _round(9 * h) for h in _hats(bars, scope, field)]


# ----------------------------------------------------------------- changes --


def _words(value: object, names: dict[str, str]) -> tuple[str, ...]:
    if value is None:
        return ("none",)
    items = value if isinstance(value, (list, tuple)) else [value]
    return tuple(names.get(x.upper(), x) if isinstance(x, str) else str(x) for x in items)


def dimension_values(section: CompiledSection | None, room: object, names: dict[str, str]) -> dict[str, tuple[str, ...]]:
    """The value of each of `DIMENSIONS` at a section, as tuples of words (module docstring).
    `names` maps `#RRGGBB` (upper case) to a palette name."""
    if section is None:
        return {d: ("auto",) for d in DIMENSIONS}
    origin = section.origin
    out: dict[str, tuple[str, ...]] = {"look": (origin.look or origin.gesture or "inline",),
                                       "gesture": (origin.gesture or "none",)}
    keys = {"movers": {"move": "move", "rate": "every", "colour": "colour"},
            "matrix": {"draw": "draw", "rate": "rate", "colour": "colour"},
            "hue": {"state": "state", "colour": "colour"}}
    for layer, mapping in keys.items():
        value = layer_word(section.layers.get(layer))
        for dim, key in mapping.items():
            name = f"{layer}.{dim}"
            if value in (None, "auto"):
                out[name] = ("auto",)
            elif value == "off":
                out[name] = ("off",)
            elif isinstance(value, dict):
                out[name] = _words(layer_word(value.get(key)), names)
            elif layer == "hue" and dim == "state":
                out[name] = (str(value),)        # a bare word: `dark`, `pulse`, `bright`
            else:
                out[name] = ("none",)
    movers = layer_word(section.layers.get("movers"))
    if movers in (None, "auto"):
        out["aim"] = ("auto",)
    elif movers == "off":
        out["aim"] = ("off",)
    else:
        out["aim"] = tuple(show_views.section_aims(section, room)) or ("none",)
    return {d: out[d] for d in DIMENSIONS}


def signature(section: CompiledSection | None, room: object, names: dict[str, str]) -> tuple:
    """All the dimension values of a section, in the order of `DIMENSIONS`: two sections with
    the same signature look the same to the critic."""
    values = dimension_values(section, room, names)
    return tuple(values[d] for d in DIMENSIONS)


# ------------------------------------------------------------------- night --


def _section_at(track, bar: int) -> CompiledSection | None:
    for s in track.sections:
        if s.bars[0] <= bar <= s.bars[1]:
            return s
    return None


def night_energy(show: CompiledShow, clock: show_views.ShowClock) -> list[TrackEnergy]:
    """The energy series of every track over its sounding window (clipped to the map's bars),
    with the track and night scopes of the module docstring. Memoised in `show.cache["energy"]`
    (for the clock whose legs are in `show.cache["energy_key"]`)."""
    key = tuple((c.leg, c.sounding) for c in clock.tracks)
    if show.cache.get("energy") is not None and show.cache.get("energy_key") == key:
        return show.cache["energy"]
    names = show_views._palette_names(show)
    music_all, light_all, windows = [], [], []
    for i, (track, tc) in enumerate(zip(show.tracks, clock.tracks)):
        mb = music_bars(track.map)
        first, last = max(tc.sounding[0], 1), min(tc.sounding[1], len(mb))
        samples = show_zoom.sample_light(track, max(first - 1, 1), last, show.rig, show.room) if last >= first else []
        before = None
        if first > 1 and samples:
            before, samples = samples[STEPS - 1], samples[STEPS:]
        prev_tc = clock.tracks[i - 1] if i > 0 else None
        if prev_tc is not None and first <= tc.leg[0] and 1 <= prev_tc.leg[1] <= len(music_all[i - 1]):
            # a leg's first bar: what plays just before is the previous track's last leg bar
            before = show_zoom.sample_light(show.tracks[i - 1], prev_tc.leg[1], prev_tc.leg[1],
                                            show.rig, show.room)[-1]
        music_all.append(mb)
        light_all.append(light_bars(samples, before))
        windows.append((first, last))

    night_music = [b for mb, tc in zip(music_all, clock.tracks) for b in mb[max(tc.leg[0] - 1, 0):max(tc.leg[1], 0)]]
    night_light = [b for lb, tc, (f, _) in zip(light_all, clock.tracks, windows)
                   for b in lb[max(tc.leg[0] - f, 0):max(tc.leg[1] - f + 1, 0)]]
    out = []
    for i, (track, tc, mb, lb, (first, last)) in enumerate(zip(show.tracks, clock.tracks, music_all, light_all, windows)):
        window = mb[first - 1:last]
        track_scope = mb[max(tc.leg[0] - 1, 0):max(tc.leg[1], 0)]
        lb = lb[:len(window)]
        values = [dimension_values(_section_at(track, b), show.room, names) for b in range(first, first + len(window))]
        changes = [0] + [sum(1 for d in CHANGE_DIMENSIONS if values[j][d] != values[j - 1][d])
                         for j in range(1, len(values))]
        out.append(TrackEnergy(
            i, track.track, first,
            music_energy(window, track_scope), music_energy(window, night_music),
            light_energy(lb, night_light), _digit_series(lb, night_light, "brightness"),
            _digit_series(lb, night_light, "activity"), changes[:len(window)],
            any(b.loudness is None for b in window)))
    show.cache["energy"] = out
    show.cache["energy_key"] = key
    return out
