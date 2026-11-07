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

All the shares below are of time summed over legs (`TrackClock.span_s` of the leg bars a section
holds; an echo, past its track's G, adds none) and over the night (`ShowClock.total_s`); a leg
bar no section holds (the autoscript) counts in no value.

variety (`variety`):
    static_runs   consecutive leg bars with the same `signature`, merged across a leg boundary;
                  the top 5 by seconds (a tie goes to the earlier). `track` is the run's first
                  track, `bars` its first bar to its last bar (the last bar may lie in a later
                  track); `music` joins, in order, the kinds of the map sections under the run
                  with `+`
    window        for minute m of the night (m = 0 .. ceil(total / 60) - 1) the signatures' time
                  shares over the clock window `[60 m - 120, 60 m + 120)`; `H = -sum(p log2 p) /
                  log2(k)` with k distinct signatures, 0 when k <= 1, digit `round(9 H)` (half
                  up); None when the window holds no signed bar
    dominance     per identity dimension, the value (not `auto`) with the largest time share (a
                  value of several words, such as the aims of a section, gives each word an
                  equal part of the seconds); `declared` when a signature's `is` names that
                  dimension and that value
    similarity    `(i, cosine)` of track i's and track i + 1's vectors of time shares over every
                  `(dimension, value)` pair (each track's shares of its own signed time, the bars of a bridge section left
                  out); skipped when a track has no such bar
    templates     `(distinct drop templates, number of drops)` of `drops`
    phrase_share  among the leg bars with `X(b) > 0`, the share that start a map section or have
                  `(b - section start) % 4 == 0`; None without such bars
    usage         per track, the looks, colours (movers, matrix, hue; palette names), aims and
                  gestures its leg sections use (not `auto`, `off` or `none`), and the number of
                  distinct drop templates of its drops

arc (`arc`), the night against the owner's energy plan (`CompiledShow.energies`, 1-10):
    mean, p90     the mean and the 90th percentile (`numpy.percentile`, linear) of the night's
                  E_light over the leg's known bars; activity: the mean of the activity digits
    warm          the share of the leg's time where the movers' or the lustre's lit colour has an
                  HSV hue within 30 degrees of red (a grey has no hue)
    rare          counts per track of the `occurrences` of strobe, white-accent, white-flash and
                  uv whose bar is inside the sounding window; `total-dark` (sections over the
                  leg); `gestures` (the gesture calls)
    rho, rho90    `spearman(energy, mean)` and `spearman(energy, p90)` over the tracks with both
    headroom      the max p90 over the tracks before the first one at the night's max energy,
                  over the night's max p90; None without such tracks or with a max of 0
    staircase     the tracks whose p90 exceeds every earlier p90 while their energy is below an
                  earlier energy
    steps         for consecutive tracks, "jump" when `|d mean| >= 2` and `d energy == 0`, "flat"
                  when `|d mean| < 1` and `d energy >= 1` (the index is the second track's)
    breathers     each drop of `top(drops, 0.25)` (`(index, bar)`, in rank order) with known light
                  after it and none of the bars starting within 180 s after it has E_light <= the
                  night's median E_light (known leg bars)
    labels        the tracks whose rank by owner energy and by mean night E_music (rank 1 the
                  highest, ties share the mean rank) differ by 3 or more
    target        `(clock_s at the leg's start, owner energy)` of each track with an energy

identity (`identity`): a section carries a signature when, for every dimension its `is` lists, one
of the section's words for that dimension is a listed value. `share` is the time share of the
carrying leg bars; `ok` is `min <= share <= max` (a missing bound passes); `occurrences` are the
maximal runs of carrying leg bars inside one track, `(index, track, (first, last), seconds)`.
`undeclared` is, per dimension, the top value (not `auto`) that no signature lists, with its
share. `arc` is the identity's own `arc`, None when it names none.

`analyse(show)` bundles the energy series and every analysis; it is memoised in
`show.cache["analysis"]`.
"""
from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass

import numpy as np

import show_energy
import show_views
from show_energy import CHANGE_DIMENSIONS, TrackEnergy, dimension_values, normalise, signature
from show_language import IDENTITY_DIMENSIONS, CompiledSection, CompiledShow, layer_word
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


def map_drops(maps: list[dict], clock: ShowClock) -> list[dict]:
    """The map-only part of `drops` (module docstring): for every map drop inside a track's
    sounding window, in set order, `{"index", "d", "loud", "bass", "density", "main", "salience"}`
    with `loud_rise`, `bass_return`, `density_rise`, `main` and `S = 0.4 L^ + 0.3 bass_return +
    0.2 D^ + 0.1 main` (`L^`, `D^`: divided by the night's largest, 0 when that is <= 0). A track
    with no `mix` takes `loud_rise` from its track-scope E_music (the interim formula). `maps` are
    the maps of the tracks in set order; no show is needed."""
    raw = []
    for i, (data, tc) in enumerate(zip(maps, clock.tracks)):
        mb = show_energy.music_bars(data)
        bass = _bass(data, len(mb))
        first, last = max(tc.sounding[0], 1), min(tc.sounding[1], len(mb))
        window = mb[first - 1:last]
        interim = any(b.loudness is None for b in window)
        music = show_energy.music_energy(window, mb[max(tc.leg[0] - 1, 0):max(tc.leg[1], 0)]) if interim else []

        def interim_at(b: int) -> int | None:
            return music[b - first] if 0 <= b - first < len(music) else None
        found = []
        for drop in data.get("drops") or []:
            d = drop.get("bar") if isinstance(drop, dict) else None
            if not isinstance(d, int) or isinstance(d, bool) or not tc.sounds(d) or not 1 <= d <= len(mb):
                continue
            loud = _rise(interim_at, d, len(mb)) if interim else _rise(lambda b: mb[b - 1].loudness, d, len(mb))
            before = bass[max(d - 9, 0):d - 1]
            ret = max(0, bass[d - 1] - min(before)) / 9 if before else 0.0
            found.append({"index": i, "d": d, "loud": loud, "bass": ret,
                          "density": _rise(lambda b: mb[b - 1].density, d, len(mb))})
        best = max((f["loud"] for f in found), default=0.0)
        for f in found:
            f["main"] = f["loud"] == best or f is found[-1]
            raw.append(f)

    def biggest(key: str) -> float:
        return max([max(0.0, r[key]) for r in raw], default=0.0)
    max_loud, max_density = biggest("loud"), biggest("density")

    def hat(x: float, m: float) -> float:
        return max(0.0, x) / m if m > 0 else 0.0
    for f in raw:
        f["salience"] = (WEIGHTS["loud"] * hat(f["loud"], max_loud) + WEIGHTS["bass"] * f["bass"]
                         + WEIGHTS["density"] * hat(f["density"], max_density) + WEIGHTS["main"] * f["main"])
    return raw


def drops(show: CompiledShow, clock: ShowClock) -> list[Drop]:
    """Every sounding map drop with its salience and its light response, sorted by rank
    (module docstring; the salience is `map_drops`)."""
    energy = show_energy.night_energy(show, clock)
    names = show_views._palette_names(show)
    rows = []
    for f in map_drops([t.map for t in show.tracks], clock):
        track, tc, te = show.tracks[f["index"]], clock.tracks[f["index"]], energy[f["index"]]
        i, d = tc.index, f["d"]
        s = f["salience"]
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


# ---------------------------------------------------------------- leg bars --

RUNS_TOP = 5
WINDOW_HALF_S = 120.0
BREATHER_S = 180.0
WARM_DEGREES = 30
STEP_JUMP = 2
STEP_FLAT = 1
LABEL_GAP = 3
_NEUTRAL = ("auto", "off", "none")


@dataclass
class _LegBar:
    index: int
    bar: int
    start_s: float
    seconds: float
    values: dict | None          # dimension_values of the holding section, None without one
    sig: tuple | None
    bridge: bool = False         # the holding section is a bridge (the copy of a handover)


def _leg_bars(show: CompiledShow, clock: ShowClock) -> list[_LegBar]:
    names = show_views._palette_names(show)
    out = []
    for i, (track, tc) in enumerate(zip(show.tracks, clock.tracks)):
        memo: dict[int, tuple] = {}
        for b in range(tc.leg[0], tc.leg[1] + 1):
            sec = show_energy._section_at(track, b)
            values = sig = None
            if sec is not None:
                if id(sec) not in memo:
                    v = dimension_values(sec, show.room, names)
                    memo[id(sec)] = (v, tuple(v[d] for d in IDENTITY_DIMENSIONS))
                values, sig = memo[id(sec)]
            out.append(_LegBar(i, b, tc.at(b), tc.span_s(b, b), values, sig, sec is not None and sec.origin.kind == "bridge"))
    return out


def _shares(bars: list[_LegBar], total: float) -> dict[tuple[str, str], float]:
    """Time share of each `(dimension, word)` over `bars`, `total` seconds being 1."""
    out: dict[tuple[str, str], float] = {}
    for lb in bars:
        for dim, words in (lb.values or {}).items():
            for w in words:
                out[(dim, w)] = out.get((dim, w), 0.0) + lb.seconds / len(words) / total
    return out


def _declared(show: CompiledShow) -> list[dict]:
    block = show.data.get("identity") if isinstance(show.data, dict) else None
    sigs = block.get("signatures") if isinstance(block, dict) else None
    out = []
    for sig in sigs if isinstance(sigs, list) else []:
        if isinstance(sig, dict) and isinstance(sig.get("is"), dict):
            out.append({"name": sig.get("name", ""), "intent": sig.get("intent", ""),
                        "is": {d: [str(x) for x in (v if isinstance(v, list) else [v])] for d, v in sig["is"].items()},
                        "share": sig.get("share") if isinstance(sig.get("share"), dict) else {}})
    return out


def _top_value(shares: dict[tuple[str, str], float], dim: str, skip=lambda w: False) -> tuple[str, float] | None:
    mine = {w: v for (d, w), v in shares.items() if d == dim and w != "auto" and not skip(w)}
    if not mine:
        return None
    value = max(mine, key=lambda w: (mine[w], w))
    return value, mine[value]


# ---------------------------------------------------------------- variety --


@dataclass
class Run:
    index: int
    track: str
    bars: tuple[int, int]
    seconds: float
    music: str


@dataclass
class Dominant:
    value: str
    share: float
    declared: bool


@dataclass
class Usage:
    index: int
    track: str
    looks: list[str]
    colours: dict[str, list[str]]
    aims: list[str]
    gestures: list[str]
    templates: int


@dataclass
class Variety:
    static_runs: list[Run]
    window: list[int | None]
    dominance: dict[str, Dominant]
    similarity: list[tuple[int, float]]
    templates: tuple[int, int]
    phrase_share: float | None
    usage: list[Usage]


def _static_runs(show: CompiledShow, bars: list[_LegBar]) -> list[Run]:
    runs: list[list[_LegBar]] = []
    for lb in bars:
        if lb.sig is None:
            runs.append([])          # a bar with no section ends the run
        elif runs and runs[-1] and runs[-1][-1].sig == lb.sig:
            runs[-1].append(lb)
        else:
            runs.append([lb])
    out = []
    for r in filter(None, runs):
        kinds: list[str] = []
        for index in sorted({x.index for x in r}):
            mine = [x.bar for x in r if x.index == index]
            for sec in _sections(show.tracks[index]):
                if sec["bars"][0] <= max(mine) and sec["bars"][1] >= min(mine) and str(sec["kind"]) not in kinds:
                    kinds.append(str(sec["kind"]))
        out.append(Run(r[0].index, show.tracks[r[0].index].track, (r[0].bar, r[-1].bar),
                       sum(x.seconds for x in r), "+".join(kinds)))
    out.sort(key=lambda r: -r.seconds)       # stable: a tie goes to the earlier
    return out[:RUNS_TOP]


def _entropy_digit(shares: dict[tuple, float]) -> int:
    k = len(shares)
    if k <= 1:
        return 0
    total = sum(shares.values())
    h = -sum((v / total) * math.log2(v / total) for v in shares.values() if v > 0) / math.log2(k)
    return math.floor(9 * h + 0.5 + 1e-9)


def _window(bars: list[_LegBar], total_s: float) -> list[int | None]:
    out = []
    for m in range(math.ceil(total_s / 60)):
        lo, hi = 60.0 * m - WINDOW_HALF_S, 60.0 * m + WINDOW_HALF_S
        shares: dict[tuple, float] = {}
        for lb in bars:
            overlap = min(lb.start_s + lb.seconds, hi) - max(lb.start_s, lo)
            if lb.sig is not None and overlap > 0:
                shares[lb.sig] = shares.get(lb.sig, 0.0) + overlap
        out.append(_entropy_digit(shares) if shares else None)
    return out


def _cosine(a: dict, b: dict) -> float | None:
    na, nb = math.sqrt(sum(v * v for v in a.values())), math.sqrt(sum(v * v for v in b.values()))
    if na < 1e-12 or nb < 1e-12:
        return None
    return sum(v * b.get(k, 0.0) for k, v in a.items()) / (na * nb)


def off_phrase_bars(show: CompiledShow, clock: ShowClock, energy: list[TrackEnergy]) -> tuple[int, list[tuple[int, int]]]:
    """The leg bars with `X(b) > 0`: how many there are, and the `(track index, bar)` of those
    off a phrase line (that neither start a map section nor sit a multiple of 4 bars after its
    start), in set order."""
    changed = 0
    off: list[tuple[int, int]] = []
    for i, (track, tc, te) in enumerate(zip(show.tracks, clock.tracks, energy)):
        spans = [s["bars"] for s in _sections(track)]
        for b in range(tc.leg[0], tc.leg[1] + 1):
            if (te.at("changes", b) or 0) <= 0:
                continue
            changed += 1
            if not any(a <= b <= z and (b - a) % 4 == 0 for a, z in spans):
                off.append((i, b))
    return changed, off


def _phrase_share(show: CompiledShow, clock: ShowClock, energy: list[TrackEnergy]) -> float | None:
    changed, off = off_phrase_bars(show, clock, energy)
    return (changed - len(off)) / changed if changed else None


def variety(show: CompiledShow, clock: ShowClock) -> Variety:
    """Monotony and variety (module docstring)."""
    energy = show_energy.night_energy(show, clock)
    bars = _leg_bars(show, clock)
    total = clock.total_s
    declared = _declared(show)
    shares = _shares(bars, total) if total > 0 else {}
    dominance = {}
    for dim in IDENTITY_DIMENSIONS:
        top_value = _top_value(shares, dim)
        if top_value:
            dominance[dim] = Dominant(top_value[0], top_value[1], any(top_value[0] in s["is"].get(dim, []) for s in declared))
    vectors = []
    for i in range(len(show.tracks)):
        mine = [lb for lb in bars if lb.index == i and lb.values is not None and not lb.bridge]
        secs = sum(lb.seconds for lb in mine)
        vectors.append(_shares(mine, secs) if secs > 0 else {})
    similarity = [(i, c) for i in range(len(vectors) - 1) if (c := _cosine(vectors[i], vectors[i + 1])) is not None]
    rows = drops(show, clock)
    usage = []
    for i, track in enumerate(show.tracks):
        used: dict[str, set[str]] = {d: set() for d in IDENTITY_DIMENSIONS}
        for lb in bars:
            for dim, words in (lb.values or {}).items() if lb.index == i else ():
                used[dim] |= {w for w in words if w not in _NEUTRAL}
        usage.append(Usage(i, track.track, sorted(used["look"]),
                           {"movers": sorted(used["movers.colour"]), "matrix": sorted(used["matrix.colour"]),
                            "hue": sorted(used["hue.colour"])},
                           sorted(used["aim"]), sorted(used["gesture"]),
                           len({r.template for r in rows if r.index == i})))
    return Variety(_static_runs(show, bars), _window(bars, total), dominance, similarity,
                   (len({r.template for r in rows}), len(rows)), _phrase_share(show, clock, energy), usage)


# -------------------------------------------------------------------- arc --


@dataclass
class ArcTrack:
    index: int
    track: str
    energy: int | None
    mean: float | None
    p90: float | None
    activity: float | None
    warm: float | None
    rare: dict[str, int]


@dataclass
class Arc:
    tracks: list[ArcTrack]
    rho: float | None
    rho90: float | None
    headroom: float | None
    staircase: list[int]
    steps: list[tuple[int, str]]
    breathers: list[tuple[int, int]]
    labels: list[str]
    target: list[tuple[float, int]]


def _warm_hex(value: object) -> bool:
    if not (isinstance(value, str) and len(value) == 7 and value.startswith("#")):
        return False
    try:
        r, g, b = (int(value[k:k + 2], 16) / 255 for k in (1, 3, 5))
    except ValueError:
        return False
    h, s, _ = colorsys.rgb_to_hsv(r, g, b)
    degrees = h * 360
    return s > 0 and min(degrees, 360 - degrees) <= WARM_DEGREES


def _warm_section(section: CompiledSection) -> bool:
    for group in ("movers", "hue"):
        layer = layer_word(section.layers.get(group))
        if isinstance(layer, dict) and _warm_hex(layer.get("colour")) and layer.get("state") != "dark":
            return True
    return False


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    return float(ordered[mid]) if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def _arc_stats(tracks: list[ArcTrack]) -> tuple[float | None, float | None, float | None, list[int], list[tuple[int, str]]]:
    """`rho`, `rho90`, `headroom`, the staircase breaks and the steps (module docstring)."""
    both = [t for t in tracks if t.energy is not None and t.mean is not None]
    rho = spearman([t.energy for t in both], [t.mean for t in both])
    both90 = [t for t in tracks if t.energy is not None and t.p90 is not None]
    rho90 = spearman([t.energy for t in both90], [t.p90 for t in both90])
    headroom = None
    with_e = [t for t in tracks if t.energy is not None]
    p90s = [t.p90 for t in tracks if t.p90 is not None]
    if with_e and p90s and max(p90s) > 0:
        peak = max(t.energy for t in with_e)
        first = next(t.index for t in with_e if t.energy == peak)
        before = [t.p90 for t in tracks if t.index < first and t.p90 is not None]
        headroom = max(before) / max(p90s) if before else None
    stairs = []
    for k, t in enumerate(tracks):
        p_before = [e.p90 for e in tracks[:k] if e.p90 is not None]
        e_before = [e.energy for e in tracks[:k] if e.energy is not None]
        if t.energy is not None and t.p90 is not None and p_before and e_before \
                and t.p90 > max(p_before) and t.energy < max(e_before):
            stairs.append(t.index)
    steps = []
    for a, b in zip(tracks, tracks[1:]):
        if None in (a.mean, b.mean, a.energy, b.energy):
            continue
        dm, de = b.mean - a.mean, b.energy - a.energy
        if abs(dm) >= STEP_JUMP and de == 0:
            steps.append((b.index, "jump"))
        elif abs(dm) < STEP_FLAT and de >= 1:
            steps.append((b.index, "flat"))
    return rho, rho90, headroom, stairs, steps


def _label_questions(rows: list[tuple[str, int | None, float | None]]) -> list[str]:
    """`rows` are `(track, owner energy, mean night E_music)`; the label-check questions of the
    module docstring, in set order."""
    have = [r for r in rows if r[1] is not None and r[2] is not None]
    n = len(have)
    by_energy = [n + 1 - r for r in _ranks([float(r[1]) for r in have])]
    by_music = [n + 1 - r for r in _ranks([float(r[2]) for r in have])]
    out = []
    for (track, e, _), r_e, r_m in zip(have, by_energy, by_music):
        if abs(r_e - r_m) >= LABEL_GAP:
            title = track.split(" — ", 1)[-1]
            out.append(f"{title}: owner energy e{e} ranks {r_e:g}, measured music ranks {r_m:g}: check the label")
    return out


def _breathers(clock: ShowClock, rows: list[Drop], energy: list[TrackEnergy]) -> list[tuple[int, int]]:
    known = [(tc.at(b), v) for tc, te in zip(clock.tracks, energy) for b in range(tc.leg[0], tc.leg[1] + 1)
             if (v := te.at("light", b)) is not None]
    if not known:
        return []
    median = _median([v for _, v in known])
    out = []
    for d in top(rows, 0.25):
        after = [v for t, v in known if d.clock_s < t <= d.clock_s + BREATHER_S]
        if after and not any(v <= median for v in after):
            out.append((d.index, d.bar))
    return out


def arc(show: CompiledShow, clock: ShowClock) -> Arc:
    """The night against the owner's energy plan (module docstring)."""
    import show_rules          # deferred: show_views imports show_rules
    from show_gestures import GESTURES

    energy = show_energy.night_energy(show, clock)
    counted = {k: show_rules.occurrences(show, k) for k in (*show_rules.EFFECT_KEYS, *GESTURES)}
    tracks, music = [], []
    for track, tc, te in zip(show.tracks, clock.tracks, energy):
        light = _known(te, "light", tc.leg[0], tc.leg[1])
        leg_s = tc.span_s(*tc.leg)
        warm_s = sum(tc.span_s(max(s.bars[0], tc.leg[0]), min(s.bars[1], tc.leg[1]))
                     for s in track.sections if _warm_section(s))
        rare = {k: sum(1 for o in counted[k] if o.track == track.track and tc.sounds(o.bar))
                for k in show_rules.EFFECT_KEYS}
        rare["total-dark"] = sum(1 for s in track.sections if s.bars[0] <= tc.leg[1] and s.bars[1] >= tc.leg[0]
                                 and show_rules._total_dark(s.layers))
        rare["gestures"] = sum(1 for k in GESTURES for o in counted[k] if o.track == track.track)
        e = show.energies.get(track.track)
        tracks.append(ArcTrack(te.index, track.track, e, _mean(light),
                               float(np.percentile(light, 90)) if light else None,
                               _mean(_known(te, "activity", tc.leg[0], tc.leg[1])),
                               warm_s / leg_s if leg_s > 0 else None, rare))
        music.append((track.track, e, _mean(_known(te, "music_night", tc.leg[0], tc.leg[1]))))
    rho, rho90, headroom, stairs, steps = _arc_stats(tracks)
    target = [(tc.start_s, t.energy) for tc, t in zip(clock.tracks, tracks) if t.energy is not None]
    return Arc(tracks, rho, rho90, headroom, stairs, steps, _breathers(clock, drops(show, clock), energy),
               _label_questions(music), target)


# --------------------------------------------------------------- identity --


@dataclass
class SignatureCheck:
    name: str
    intent: str
    share: float
    min: float | None
    max: float | None
    ok: bool
    occurrences: list[tuple[int, str, tuple[int, int], float]]


@dataclass
class Identity:
    arc: str | None
    signatures: list[SignatureCheck]
    undeclared: dict[str, tuple[str, float]]


def _bound(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def identity(show: CompiledShow, clock: ShowClock) -> Identity:
    """The declared identity, promised against delivered (module docstring)."""
    bars = _leg_bars(show, clock)
    total = clock.total_s
    block = show.data.get("identity") if isinstance(show.data, dict) else None
    arc_name = block.get("arc") if isinstance(block, dict) and isinstance(block.get("arc"), str) else None
    declared = _declared(show)
    checks = []
    for sig in declared:
        seconds = 0.0
        runs: list[list] = []          # [index, first bar, last bar, seconds]
        for lb in bars:
            if lb.values is None or not all(any(w in wanted for w in lb.values.get(dim, ()))
                                            for dim, wanted in sig["is"].items()):
                continue
            seconds += lb.seconds
            if runs and runs[-1][0] == lb.index and runs[-1][2] == lb.bar - 1:
                runs[-1][2], runs[-1][3] = lb.bar, runs[-1][3] + lb.seconds
            else:
                runs.append([lb.index, lb.bar, lb.bar, lb.seconds])
        share = seconds / total if total > 0 else 0.0
        lo, hi = _bound(sig["share"].get("min")), _bound(sig["share"].get("max"))
        ok = (lo is None or share >= lo - 1e-9) and (hi is None or share <= hi + 1e-9)
        checks.append(SignatureCheck(str(sig["name"]), str(sig["intent"]), share, lo, hi, ok,
                                     [(r[0], show.tracks[r[0]].track, (r[1], r[2]), r[3]) for r in runs]))
    shares = _shares(bars, total) if total > 0 else {}
    undeclared = {}
    for dim in IDENTITY_DIMENSIONS:
        found = _top_value(shares, dim, lambda w: any(w in s["is"].get(dim, []) for s in declared))
        if found:
            undeclared[dim] = found
    return Identity(arc_name, checks, undeclared)


# ---------------------------------------------------------------- analyse --


@dataclass
class Analysis:
    clock: ShowClock
    energy: list[TrackEnergy]
    follows: list[Follow]
    drops: list[Drop]
    builds: list[Build]
    variety: Variety
    arc: Arc
    identity: Identity


def analyse(show: CompiledShow) -> Analysis:
    """Every analysis of the night on `build_clock(show)`, memoised in `show.cache["analysis"]`."""
    cached = show.cache.get("analysis")
    if cached is not None:
        return cached
    clock = show_views.build_clock(show)
    result = Analysis(clock, show_energy.night_energy(show, clock), follows(show, clock), drops(show, clock),
                      builds(show, clock), variety(show, clock), arc(show, clock), identity(show, clock))
    show.cache["analysis"] = result
    return result
