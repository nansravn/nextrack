"""set_timeline.py — the timeline of a set from musical maps and rekordbox cues.

A pure library (no I/O): `timeline` turns an ordered list of legs (a map, the live rekordbox
cues B and G, the played tempo) into transitions (offset, overlap, the incoming sections in
the overlap, arrival, peak) and the set clock. `nextrack_map.py timeline` feeds it.

Bars are the maps' bars. The clock is the concatenation of the played bars: the first leg
plays bars [1, G), middle legs [B, G), the last [B, its last non-silent bar]: a hot cue is a point
at the start of its bar, so the incoming B begins when the outgoing G begins. Each leg runs at
its played tempo (a linear ramp over its bars). `clock_g_s` is the clock at the start of bar G.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

import check_repo
import musical_map as mm
import soundswitch_format as ssf

CUE_BAR_RE = re.compile(r"([0-9]+)\.([1-4])([+-][0-9]+ms)?")
TEMPO_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)(?:-([0-9]+(?:\.[0-9]+)?))?")


@dataclass
class Leg:
    name: str
    map: dict
    cues: dict[str, int]
    tempo: tuple[float, float] | None = None


@dataclass
class Transition:
    out_name: str
    in_name: str
    g_bar: int
    b_bar: int
    offset_bars: int
    overlap_bars: int
    overlap_sections: list[tuple[str, int, int]]
    arrival_bar: int | None
    peak_bar: int | None
    clock_g_s: float
    clock_arrival_s: float | None
    overlap_drops: list[tuple[int, float]] = field(default_factory=list)
    relative: bool = False  # the clocks count from the start of a chain that follows a missing map


def _grid(data: dict) -> ssf.Grid:
    return ssf.Grid([(int(ms), float(bpm)) for ms, bpm in data["grid"]["anchors"]])


def last_bar(data: dict) -> int:
    """The map's bars minus the silence that ends the track."""
    last = data["bars"]
    for a, b in sorted(data.get("silences") or [], reverse=True):
        if b >= last:
            last = min(last, a - 1)
    return max(last, 1)


def _cue_bars(leg: Leg, warnings: list[str]) -> dict[str, int]:
    """Bar of each of the leg's B and G cues; warns on a moved cue, one off the beat, and one
    off beat 1 (its bar is kept: the timeline counts whole bars from the start of it)."""
    grid = _grid(leg.map)
    stored = leg.map.get("hot_cues") or {}
    bars: dict[str, int] = {}
    for letter in ("B", "G"):
        if letter not in leg.cues:
            continue
        text = mm.cue_text(leg.cues[letter], grid)
        parsed = CUE_BAR_RE.fullmatch(text)
        bars[letter] = int(parsed[1])
        if parsed[3]:
            warnings.append(f"{leg.name}: hot cue {letter} is not on a beat (rekordbox {text})")
        if parsed[2] != "1":
            warnings.append(f"{leg.name}: hot cue {letter} at {text}: the timeline assumes cues on beat 1")
        if stored.get(letter) != text:
            warnings.append(f"{leg.name}: hot cue {letter} moved since the map "
                            f"(map {stored.get(letter, 'none')}, rekordbox {text}); run cues")
    return bars


def _tempo(leg: Leg) -> tuple[float, float]:
    if leg.tempo is not None:
        return leg.tempo
    bpm = float(leg.map["grid"]["anchors"][0][1])
    return bpm, bpm


def _seconds(tempo: tuple[float, float], played: int, bars: int) -> float:
    """Seconds of the first `bars` bars of a leg that plays `played` bars, the tempo ramping
    linearly over them (each bar at its mid tempo; bars past the end keep the end tempo)."""
    t0, t1 = tempo
    total = 0.0
    for k in range(bars):
        frac = min((k + 0.5) / played, 1.0) if played else 1.0
        total += 240 / (t0 + (t1 - t0) * frac)
    return total


def timeline(legs: list[Leg]) -> tuple[list[Transition], float, list[str]]:
    warnings: list[str] = []
    cue_bars = [_cue_bars(leg, warnings) for leg in legs]
    n = len(legs)
    lasts = [last_bar(leg.map) for leg in legs]
    for i, leg in enumerate(legs):
        if i > 0 and "B" not in cue_bars[i]:
            warnings.append(f"{leg.name}: no B cue; the transition into it is skipped")
        if i < n - 1 and "G" not in cue_bars[i]:
            warnings.append(f"{leg.name}: no G cue; the transition out of it is skipped")
    # the played range of each leg and the clock at which it starts
    first = [1 if i == 0 else cue_bars[i].get("B", 1) for i in range(n)]
    stops = [cue_bars[i].get("G", lasts[i] + 1) if i < n - 1 else lasts[i] + 1 for i in range(n)]
    played = [max(stops[i] - first[i], 0) for i in range(n)]  # bars [first, stop)
    starts: list[float] = []
    clock = 0.0
    for i, leg in enumerate(legs):
        starts.append(clock)
        clock += _seconds(_tempo(leg), played[i], played[i])
    transitions: list[Transition] = []
    for i in range(n - 1):
        out, inc = legs[i], legs[i + 1]
        if "G" not in cue_bars[i] or "B" not in cue_bars[i + 1]:
            continue
        g, b = cue_bars[i]["G"], cue_bars[i + 1]["B"]
        overlap = max(lasts[i] - g + 1, 0)
        sections = []
        for s in inc.map["sections"]:
            lo, hi = max(s["bars"][0], b), min(s["bars"][1], b + overlap - 1)
            if lo <= hi:
                sections.append((s["kind"], lo, hi))
        drops = [(d["bar"], d["db"]) for d in inc.map["drops"]]
        arrival = next((bar for bar, _ in sorted(drops) if bar >= b + overlap), None)
        own_g = cue_bars[i + 1].get("G") if i + 1 < n - 1 else None
        candidates = [d for d in drops if d[0] > b and (own_g is None or d[0] < own_g)]
        peak = max(candidates, key=lambda d: (d[1], -d[0]))[0] if candidates else None
        clock_arrival = None
        if arrival is not None:
            clock_arrival = starts[i + 1] + _seconds(_tempo(inc), played[i + 1], arrival - b)
        transitions.append(Transition(
            out_name=out.name, in_name=inc.name, g_bar=g, b_bar=b, offset_bars=b - g,
            overlap_bars=overlap, overlap_sections=sections, arrival_bar=arrival, peak_bar=peak,
            clock_g_s=starts[i + 1], clock_arrival_s=clock_arrival,
            overlap_drops=[d for d in sorted(drops) if b <= d[0] < b + overlap]))
    return transitions, clock, warnings


def block_tempos(block_text: str) -> list[tuple[str, str, tuple[float, float] | None]]:
    """`(artist, title, played tempo)` per tracklist line of a block: the field after the key,
    `122` or a ramp `122-125`; anything else is None."""
    body = [(i, line) for i, line in enumerate(block_text.splitlines(), 1)]
    out = []
    for _, text in check_repo.section(body, check_repo.TRACKLIST_HEADING) or []:
        parsed = check_repo.TRACK_LINE_RE.match(text)
        if not parsed:
            continue
        fields = [f.strip() for f in text.split("·")]
        tempo = None
        if len(fields) > 2 and (m := TEMPO_RE.fullmatch(fields[2])):
            tempo = (float(m[1]), float(m[2] or m[1]))
        out.append((parsed["artist"], parsed["title"], tempo))
    return out


# ---------------------------------------------------------------- rendering ----


def _clock(seconds: float, relative: bool = False) -> str:
    s = round(seconds)
    return ("+" if relative else "") + f"{s // 60}:{s % 60:02d}"


def _arrival_text(t: Transition) -> str:
    if t.arrival_bar is not None:
        return f"bar {t.arrival_bar} ({_clock(t.clock_arrival_s, t.relative)})"
    if t.overlap_drops:
        listed = ", ".join(f"bar {bar} {db} dB" for bar, db in t.overlap_drops)
        return f"none (drops in overlap: {listed})"
    return "none"


def render_markdown(transitions: list[Transition], total_s: float, warnings: list[str],
                    incomplete: int = 0) -> str:
    lines = ["| # | out G → in B | clock | overlap | in-sections | arrival | peak |",
             "|---|---|---|---|---|---|---|"]
    for i, t in enumerate(transitions, 1):
        secs = ", ".join(f"{k} {a}-{b}" for k, a, b in t.overlap_sections) or "-"
        peak = "none" if t.peak_bar is None else (
            f"bar {t.peak_bar}" + (" (= arrival)" if t.peak_bar == t.arrival_bar else ""))
        lines.append(f"| {i} | {t.out_name} G{t.g_bar} → {t.in_name} B{t.b_bar} "
                     f"(offset {t.offset_bars:+d}) | {_clock(t.clock_g_s, t.relative)} | "
                     f"{t.overlap_bars} bars | {secs} | {_arrival_text(t)} | {peak} |")
    note = f" (incomplete: {incomplete} track{'s' if incomplete != 1 else ''} without a map)" if incomplete else ""
    lines += ["", f"Set length: {_clock(total_s)}{note}"]
    if warnings:
        lines += ["", "Warnings"] + [f"- {w}" for w in warnings]
    return "\n".join(lines)


def render_yaml(transitions: list[Transition], total_s: float, warnings: list[str],
                incomplete: int = 0) -> str:
    data = {
        "transitions": [{
            "out": t.out_name, "in": t.in_name, "g_bar": t.g_bar, "b_bar": t.b_bar,
            "offset_bars": t.offset_bars, "overlap_bars": t.overlap_bars,
            "overlap_sections": [{"kind": k, "bars": [a, b]} for k, a, b in t.overlap_sections],
            "overlap_drops": [{"bar": bar, "db": db} for bar, db in t.overlap_drops],
            "arrival_bar": t.arrival_bar, "peak_bar": t.peak_bar,
            "clock_g_s": round(t.clock_g_s, 2),
            "clock_arrival_s": None if t.clock_arrival_s is None else round(t.clock_arrival_s, 2),
            "clock_relative": t.relative,
        } for t in transitions],
        "total_s": round(total_s, 2),
        "tracks_without_map": incomplete,
        "warnings": warnings,
    }
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
