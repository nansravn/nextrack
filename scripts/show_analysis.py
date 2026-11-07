"""show_analysis.py — what the energy series say about the night: whether the light follows the
music, how each drop is answered, whether the builds build (spec section A4 of
docs/superpowers/specs/2026-11-07-show-team-design.md, "follows", "drops" and "builds").

Every function reads `show_energy.night_energy`; it returns facts (numbers, lists), never a
verdict. A bar whose light is unknown (the autoscript plays) is left out of every statistic.
A result that cannot be computed is None or an empty list, never an exception.

Spearman. `spearman(a, b)` is the Pearson correlation of the average ranks (ties share their
mean rank); None below 3 pairs or when a side is constant.

follows (`follows`), per track, over the leg's bars (`TrackClock.leg`) with a known light:
    rho         `spearman(E_music, E_light)`, E_music at track scope
    boundaries  the map section starts `s` with `leg[0] + 4 <= s <= leg[1] - 3`. For each,
                `dm` = mean E_music over s..s+3 minus over s-4..s-1, and `dl` the same for
                E_light (known bars only; a boundary with no known light on a side is skipped)
    agreement   among the boundaries with `|dm| >= 2`, the share with `sign(dl) == sign(dm)`
                and `|dl| >= 1`; None when no boundary qualifies
    missed      boundaries with `|dm| >= 2` and `|dl| < 1`
    unmotivated boundaries with `|dl| >= 3` and `|dm| < 1` (for information)
    lag         the shift in [-8, 8] that maximises Pearson(music[t], light[t + shift]) over
                the leg's bars where both are known (a tie goes to the smaller |shift|);
                positive means the light is late. None below 16 known bars
    unknown_share  the share of the leg's bars whose light is unknown

drops (`drops`): every map drop `d` inside a track's sounding window.
    loud_rise     mean `mix.loudness` digit over d..d+3 minus over d-8..d-1 (a v1 map: the
                  track-scope E_music); 0 when nothing precedes d
    bass_return   `max(0, bass digit at d - min bass digit over d-8..d-1) / 9`
    density_rise  the same difference on `BarMusic.density` (steps with a kick or perc onset,
                  over 16)
    main          the track's drop with the largest `loud_rise`, or its last drop in the window
    salience      `S = 0.4 L + 0.3 bass_return + 0.2 D + 0.1 main`, with `x^ = max(0, x) /
                  max over the night's drops of max(0, x)` for L (loud_rise) and D
                  (density_rise), 0 when that max is <= 0. `rank` 1 is the biggest S (a tie
                  goes to the earlier on the clock)
    contrast      mean E_light over d..d+3 minus over d-2..d-1, known bars only; None when a
                  side has none. A bar before the leg's first reads the previous track's last
                  leg bars (the bar before the leg's first is the previous leg's last)
    change        `X(d)` (show_energy)
    freshness     the share of the nine `CHANGE_DIMENSIONS` values of the drop's section that
                  no other section sounding in the 600 s before the drop (on the set clock) has
    response      `0.5 clip01(contrast / 4) + 0.25 change / 9 + 0.25 freshness`; None when the
                  contrast or the freshness is
    template      `(signature at d - 1, signature at d)`, the section before as
                  `show_views._section_before` finds it
    holder        the section that holds the drop
`top` takes the first n (an int) or the first fraction (a float, at least 1) of the ranked drops.
`drop_agreement` is the Spearman of salience and response over the drops above the median
salience (strictly) that have a response.

builds (`builds`): each map `build` section of at least 4 bars, and the last `min(16, len)` bars
of each `break` of at least 4 bars that a `drop` section follows directly, clipped to the
sounding window (at least 4 bars must stay).
    music_slope      least-squares slope per bar of `T(b) = mean(L^, C^, D^)`, loudness,
                     brightness and density normalised over the track's leg bars
                     (`show_energy.normalise`); a v1 map: `D^` alone
    activity_slope   the same slope of the night's activity digits; brightness_slope of the
                     brightness digits (known bars; None below 2)
    into             with `d` = the window's end + 1: "dip" when `E_light(d-1) <= mean
                     E_light(d-9..d-2) - 1`; else "ramp" when the window's last 4 E_light do
                     not decrease and `E_light(d-1) > E_light(window start)`; else "flat";
                     "unknown" when the bars a test needs are unknown (autoscript)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

import show_energy
import show_views
from show_energy import CHANGE_DIMENSIONS, TrackEnergy, dimension_values, normalise, signature
from show_language import CompiledSection, CompiledShow
from show_views import ShowClock

LAG_MAX = 8
LAG_MIN_BARS = 16
BOUNDARY_SPAN = 4
MOVE_MUSIC = 2
MOVE_LIGHT = 1
BIG_LIGHT = 3
FRESH_WINDOW_S = 600.0
BUILD_MIN = 4
BUILD_TAIL = 16
WEIGHTS = {"loud": 0.4, "bass": 0.3, "density": 0.2, "main": 0.1}


# ------------------------------------------------------------------ stats --


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def _pearson(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2:
        return None
    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    x, y = x - x.mean(), y - y.mean()
    den = math.sqrt(float((x * x).sum()) * float((y * y).sum()))
    if den < 1e-12:
        return None
    return float((x * y).sum()) / den


def spearman(a: list[float], b: list[float]) -> float | None:
    """The Spearman rank correlation of `a` and `b` (module docstring): None below 3 pairs or
    for a constant side."""
    if len(a) != len(b) or len(a) < 3:
        return None
    return _pearson(_ranks(list(a)), _ranks(list(b)))


def _slope(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    x = np.arange(len(values), dtype=float)
    y = np.asarray(values, dtype=float)
    return float(((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum())


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def _known(te: TrackEnergy, series: str, first: int, last: int) -> list[float]:
    """The known values of `series` over bars first..last."""
    return [v for v in (te.at(series, b) for b in range(first, last + 1)) if v is not None]


def _sections(track) -> list[dict]:
    out = []
    for s in track.map.get("sections") or []:
        bars = s.get("bars") if isinstance(s, dict) else None
        if isinstance(bars, list) and len(bars) == 2 and all(isinstance(x, int) for x in bars):
            out.append({"bars": (bars[0], bars[1]), "kind": s.get("kind")})
    return out


# ---------------------------------------------------------------- follows --


@dataclass
class Boundary:
    bar: int
    music: float        # dm
    light: float        # dl


@dataclass
class Follow:
    index: int
    track: str
    rho: float | None
    agreement: float | None
    lag: int | None
    missed: list[Boundary]
    unmotivated: list[Boundary]
    unknown_share: float


def _lag(music: list[float | None], light: list[float | None]) -> int | None:
    best, best_r = None, None
    for shift in sorted(range(-LAG_MAX, LAG_MAX + 1), key=lambda s: (abs(s), s)):
        pairs = [(music[t], light[t + shift]) for t in range(len(music))
                 if music[t] is not None and 0 <= t + shift < len(light) and light[t + shift] is not None]
        if len(pairs) < LAG_MIN_BARS:
            continue
        r = _pearson([p[0] for p in pairs], [p[1] for p in pairs])
        if r is not None and (best_r is None or r > best_r + 1e-9):
            best, best_r = shift, r
    return best


def follows(show: CompiledShow, clock: ShowClock) -> list[Follow]:
    """One `Follow` per track (module docstring)."""
    energy = show_energy.night_energy(show, clock)
    out = []
    for track, tc, te in zip(show.tracks, clock.tracks, energy):
        first, last = tc.leg
        window = list(range(first, last + 1))
        music = [te.at("music", b) for b in window]
        light = [te.at("light", b) for b in window]
        pairs = [(m, v) for m, v in zip(music, light) if m is not None and v is not None]
        rho = spearman([p[0] for p in pairs], [p[1] for p in pairs])
        boundaries: list[Boundary] = []
        for sec in _sections(track):
            s = sec["bars"][0]
            if not first + BOUNDARY_SPAN <= s <= last - 3:
                continue
            m_after, m_before = _known(te, "music", s, s + 3), _known(te, "music", s - BOUNDARY_SPAN, s - 1)
            l_after, l_before = _known(te, "light", s, s + 3), _known(te, "light", s - BOUNDARY_SPAN, s - 1)
            if not (m_after and m_before and l_after and l_before):
                continue
            boundaries.append(Boundary(s, _mean(m_after) - _mean(m_before), _mean(l_after) - _mean(l_before)))
        moved = [b for b in boundaries if abs(b.music) >= MOVE_MUSIC]
        agreement = (sum(1 for b in moved if _sign(b.light) == _sign(b.music) and abs(b.light) >= MOVE_LIGHT)
                     / len(moved)) if moved else None
        missed = [b for b in moved if abs(b.light) < MOVE_LIGHT]
        unmotivated = [b for b in boundaries if abs(b.light) >= BIG_LIGHT and abs(b.music) < MOVE_LIGHT]
        unknown = sum(1 for v in light if v is None)
        out.append(Follow(te.index, te.track, rho, agreement, _lag(music, light), missed, unmotivated,
                          unknown / len(window) if window else 1.0))
    return out


# ------------------------------------------------------------------ drops --


@dataclass
class Drop:
    clock_s: float
    index: int
    track: str
    bar: int
    loud_rise: float
    bass_return: float
    density_rise: float
    main: bool
    salience: float
    rank: int
    contrast: float | None
    change: int
    freshness: float | None
    response: float | None
    template: tuple
    holder: CompiledSection | None


def _rise(value, d: int, last_bar: int) -> float:
    """Mean of `value(b)` over d..d+3 minus over d-8..d-1 (bars 1..last_bar, known values);
    0 when either side has none."""
    def mean(lo: int, hi: int) -> float | None:
        return _mean([v for v in (value(b) for b in range(max(lo, 1), min(hi, last_bar) + 1)) if v is not None])
    after, before = mean(d, d + 3), mean(d - 8, d - 1)
    return 0.0 if after is None or before is None else after - before


def _light_around(energy: list[TrackEnergy], clock: ShowClock, i: int, bars: range) -> list[float]:
    """The known E_light of `bars` of track `i`; a bar before the leg reads the previous track."""
    values = []
    leg_first = clock.tracks[i].leg[0]
    for b in bars:
        if b < leg_first and i > 0:
            v = energy[i - 1].at("light", clock.tracks[i - 1].leg[1] + 1 - (leg_first - b))
        else:
            v = energy[i].at("light", b)
        if v is not None:
            values.append(v)
    return values


def _freshness(show: CompiledShow, clock: ShowClock, section: CompiledSection, t: float,
               names: dict[str, str]) -> float:
    mine = dimension_values(section, show.room, names)
    seen: set[tuple[str, tuple]] = set()
    for track, tc in zip(show.tracks, clock.tracks):
        for other in track.sections:
            if other is section:
                continue
            a, b = max(other.bars[0], tc.sounding[0]), min(other.bars[1], tc.sounding[1])
            if a > b or not (tc.at(a) < t and tc.at(b + 1) > t - FRESH_WINDOW_S):
                continue
            for dim, value in dimension_values(other, show.room, names).items():
                seen.add((dim, value))
    return sum(1 for d in CHANGE_DIMENSIONS if (d, mine[d]) not in seen) / len(CHANGE_DIMENSIONS)


def _bass(map_data: dict, bars: int) -> list[int]:
    voices = map_data.get("voices") if isinstance(map_data.get("voices"), dict) else {}
    bass = voices.get("bass") if isinstance(voices.get("bass"), dict) else {}
    return show_energy._digits(bass.get("bars"), bars)


def drops(show: CompiledShow, clock: ShowClock) -> list[Drop]:
    """Every sounding map drop with its salience and its light response, sorted by rank
    (module docstring)."""
    energy = show_energy.night_energy(show, clock)
    names = show_views._palette_names(show)
    raw = []
    for track, tc, te in zip(show.tracks, clock.tracks, energy):
        mb = show_energy.music_bars(track.map)
        bass = _bass(track.map, len(mb))
        found = []
        for drop in track.map.get("drops") or []:
            d = drop.get("bar") if isinstance(drop, dict) else None
            if not isinstance(d, int) or isinstance(d, bool) or not tc.sounds(d) or not 1 <= d <= len(mb):
                continue
            if te.interim:
                loud = _rise(lambda b: te.at("music", b), d, len(mb))
            else:
                loud = _rise(lambda b: mb[b - 1].loudness, d, len(mb))
            before = bass[max(d - 9, 0):d - 1]
            ret = max(0, bass[d - 1] - min(before)) / 9 if before else 0.0
            found.append({"d": d, "loud": loud, "bass": ret, "density": _rise(lambda b: mb[b - 1].density, d, len(mb))})
        best = max((f["loud"] for f in found), default=0.0)
        for f in found:
            f["main"] = f["loud"] == best or f is found[-1]
            raw.append((track, tc, te, f))

    def biggest(key: str) -> float:
        return max([max(0.0, r[3][key]) for r in raw], default=0.0)
    max_loud, max_density = biggest("loud"), biggest("density")

    def hat(x: float, m: float) -> float:
        return max(0.0, x) / m if m > 0 else 0.0
    rows = []
    for track, tc, te, f in raw:
        i, d = tc.index, f["d"]
        s = (WEIGHTS["loud"] * hat(f["loud"], max_loud) + WEIGHTS["bass"] * f["bass"]
             + WEIGHTS["density"] * hat(f["density"], max_density) + WEIGHTS["main"] * f["main"])
        after = _known(te, "light", d, d + 3)
        before = _light_around(energy, clock, i, range(d - 2, d))
        contrast = _mean(after) - _mean(before) if after and before else None
        holder = show_energy._section_at(track, d)
        previous, _ = show_views._section_before(show, clock, i, d)
        t = tc.at(d)
        fresh = _freshness(show, clock, holder, t, names) if holder is not None else None
        change = te.at("changes", d) or 0
        response = None
        if contrast is not None and fresh is not None:
            response = 0.5 * min(1.0, max(0.0, contrast / 4)) + 0.25 * change / 9 + 0.25 * fresh
        rows.append(Drop(t, i, track.track, d, f["loud"], f["bass"], f["density"], bool(f["main"]), s, 0,
                         contrast, change, fresh, response,
                         (signature(previous, show.room, names), signature(holder, show.room, names)), holder))
    rows.sort(key=lambda r: (-r.salience, r.clock_s))
    for rank, row in enumerate(rows, 1):
        row.rank = rank
    return rows


def top(rows: list[Drop], n: int | float) -> list[Drop]:
    """The first `n` rows (an int), or the first `ceil(n x len(rows))` (a float, at least 1)."""
    if not rows:
        return []
    count = max(1, math.ceil(n * len(rows))) if isinstance(n, float) else n
    return rows[:count]


def drop_agreement(rows: list[Drop]) -> float | None:
    """`spearman(salience, response)` over the drops above the median salience that have a
    response; None when fewer than 3 remain."""
    if not rows:
        return None
    ordered = sorted(r.salience for r in rows)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    pick = [r for r in rows if r.salience > median and r.response is not None]
    return spearman([r.salience for r in pick], [r.response for r in pick])


# ----------------------------------------------------------------- builds --


@dataclass
class Build:
    index: int
    track: str
    bars: tuple[int, int]
    music_slope: float
    activity_slope: float | None
    brightness_slope: float | None
    into: str


def _into(te: TrackEnergy, bars: tuple[int, int]) -> str:
    a, b = bars
    last = te.at("light", b)
    earlier = _known(te, "light", b - 8, b - 1)
    dip = None if last is None or not earlier else last <= _mean(earlier) - 1
    tail = [te.at("light", x) for x in range(b - 3, b + 1)]
    start = te.at("light", a)
    ramp = None if None in tail or start is None else (all(y >= x for x, y in zip(tail, tail[1:])) and tail[-1] > start)
    if dip:
        return "dip"
    if ramp:
        return "ramp"
    return "unknown" if dip is None or ramp is None else "flat"


def builds(show: CompiledShow, clock: ShowClock) -> list[Build]:
    """The builds of the night in set order (module docstring)."""
    energy = show_energy.night_energy(show, clock)
    out = []
    for track, tc, te in zip(show.tracks, clock.tracks, energy):
        sections = _sections(track)
        mb = show_energy.music_bars(track.map)
        scope = mb[max(tc.leg[0] - 1, 0):max(tc.leg[1], 0)] or mb
        windows = []
        for k, sec in enumerate(sections):
            a, b = sec["bars"]
            if b - a + 1 < BUILD_MIN:
                continue
            if sec["kind"] == "build":
                windows.append((a, b))
            elif sec["kind"] == "break" and k + 1 < len(sections) and sections[k + 1]["kind"] == "drop" \
                    and sections[k + 1]["bars"][0] == b + 1:
                windows.append((max(a, b - min(BUILD_TAIL, b - a + 1) + 1), b))
        for a, b in windows:
            a, b = max(a, tc.sounding[0]), min(b, tc.sounding[1], len(mb))
            if b - a + 1 < BUILD_MIN:
                continue
            chunk = mb[a - 1:b]
            parts = [normalise([x.density for x in chunk], [x.density for x in scope])]
            if not any(x.loudness is None for x in chunk):
                for name in ("loudness", "brightness"):
                    parts.append(normalise([getattr(x, name) for x in chunk], [getattr(x, name) for x in scope]))
            tension = [sum(p[j] for p in parts) / len(parts) for j in range(len(chunk))]
            out.append(Build(te.index, te.track, (a, b), _slope(tension) or 0.0,
                             _slope(_known(te, "activity", a, b)), _slope(_known(te, "brightness", a, b)),
                             _into(te, (a, b))))
    return out
