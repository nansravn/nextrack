#!/usr/bin/env python3
"""nextrack_lights.py — read the SoundSwitch project (the owner's light shows).

The SoundSwitch project folder holds one `{GUID}.ssfile` per analysed track, plus
`SoundSwitchTrackMap.bin` (which GUID is which song) and `SoundSwitchVenues.bin` (the
rig). The folder comes from --project, or from $NEXTRACK_SOUNDSWITCH_PROJECT if unset.
These commands only read; nothing here writes to the project.

Subcommands:
  tracks   list the tracks of the project (GUID8, BPM, length, artist — title)
  dump     per 8-bar phrase and fixture: lit share, pulses, colours, positions, shapes
  analyze  the dump reduced to metrics: who overrides Main, white over colour, ...
  render   one HTML file: the room simulated before (the base script) and after (the
           choreography compiled onto it), with a timeline and an optional audio file

An "effective" value is what the fixture really shows: its own when one of its spans
covers the moment, else the Main track's. See scripts/README.md.

Grouped rows: the cells of a Vorlane fold into two rows, "<Vorlane> RGB" (cells named
`RGB nn …`) and "<Vorlane> W" (cells named `W n …`). For such a row `lit` is the share
of the phrase in which ANY cell is lit (union of the cells' lit time); `pulses` counts
rises on the pointwise maximum of the cells' effective curves, so cells pulsing in
unison count once and alternating cells count each step; colours, positions and shapes
are the union across the cells. Other fixtures are one row each.
"""
from __future__ import annotations

import argparse
import bisect
import copy
import dataclasses
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

import lightshow as ls
import soundswitch_format as ssf

PROJECT_ENV = "NEXTRACK_SOUNDSWITCH_PROJECT"  # machine-specific, so it lives outside the repo
SIM_TEMPLATE = Path(__file__).with_name("lightshow_sim.html")
DEFAULT_RIG = Path(__file__).resolve().parent.parent / "lightshows" / "rig.yml"
MAIN_NODE = 2
PHRASE_BARS = 8
LIT = 0.01      # "lit" = effective level above 1 %
LOW = 0.10      # a pulse rises from below 10 % ...
HIGH = 0.90     # ... to above 90 %

# ------------------------------------------------------------------- model ----


def effective_level(script: ssf.TrackScript, trk: ssf.Track, t: int) -> float:
    """The level (0..1) `trk` shows at `t`: its own inside its B spans, else Main's."""
    own = trk is script.main or trk.node == MAIN_NODE or ssf.covered(trk, t)
    return ssf.level_at(ssf.intensity(trk if own else script.main), t) / 2**32


def effective_curve(script: ssf.TrackScript, trk: ssf.Track,
                    extra: tuple[int, ...] | list[int] = ()) -> list[tuple[int, float]]:
    """`(t, level)` at every breakpoint; the level is linear in between."""
    ts = set(extra)
    lanes = [ssf.intensity(script.main)]
    if trk is not script.main:
        lanes.append(ssf.intensity(trk))
        for s in (trk.blocks.items if trk.blocks else []):
            ts.update((s.start - 1, s.start, s.end, s.end + 1))
    for lane in lanes:
        if lane:
            ts.update(k.t for k in lane.keys)
    return [(t, effective_level(script, trk, t)) for t in sorted(ts) if t >= 0]


def _lit_intervals(pts: list[tuple[int, float]], thr: float = LIT) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for (t0, a), (t1, b) in zip(pts, pts[1:]):
        if t1 <= t0:
            continue
        lo, hi = float(t0), float(t1)
        if a <= thr and b <= thr:
            continue
        if a <= thr:
            lo = t0 + (thr - a) / (b - a) * (t1 - t0)
        elif b <= thr:
            hi = t0 + (thr - a) / (b - a) * (t1 - t0)
        if out and out[-1][1] >= lo - 1e-9:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def _union(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for lo, hi in sorted(intervals):
        if out and out[-1][1] >= lo:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def _intersect(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = []
    for lo1, hi1 in a:
        for lo2, hi2 in b:
            lo, hi = max(lo1, lo2), min(hi1, hi2)
            if hi > lo:
                out.append((lo, hi))
    return _union(out)


def _length(intervals: list[tuple[float, float]]) -> float:
    return sum(hi - lo for lo, hi in intervals)


def _pulses(pts: list[tuple[int, float]]) -> int:
    count, armed = 0, bool(pts) and pts[0][1] < LOW
    for _, level in pts:
        if level < LOW:
            armed = True
        elif level > HIGH and armed:
            count, armed = count + 1, False
    return count


def _interp(pts: list[tuple[int, float]], t: int) -> float:
    i = bisect.bisect_right([p[0] for p in pts], t)
    if i == 0:
        return pts[0][1]
    if i == len(pts):
        return pts[-1][1]
    (t0, a), (t1, b) = pts[i - 1], pts[i]
    return a if t1 == t0 else a + (b - a) * (t - t0) / (t1 - t0)


def _max_curve(curves: list[list[tuple[int, float]]]) -> list[tuple[int, float]]:
    """The pointwise maximum of several curves, at the union of their breakpoints."""
    curves = [c for c in curves if c]
    if len(curves) <= 1:
        return curves[0] if curves else []
    times = sorted({t for c in curves for t, _ in c})
    xs = [[p[0] for p in c] for c in curves]
    out = []
    for t in times:
        level = 0.0
        for c, x in zip(curves, xs):
            i = bisect.bisect_left(x, t)
            level = max(level, c[i][1] if i < len(c) and x[i] == t else _interp(c, t))
        out.append((t, level))
    return out


def _between(pts: list[tuple[int, float]], start: int, end: int) -> list[tuple[int, float]]:
    return [(t, v) for t, v in pts if start <= t <= end]


def _overlaps(item, start: int, end: int) -> bool:
    return item.start < end and item.end >= start


def _effective_items(own: list, main: list, start: int, end: int) -> tuple[list, bool]:
    """Items shown in [start, end): the fixture's own, plus Main's where no own item is."""
    mine = [i for i in own if _overlaps(i, start, end)]
    gaps, at = [], float(start)
    for lo, hi in _union([(i.start, i.end) for i in mine]):
        if lo > at:
            gaps.append((at, lo))
        at = max(at, hi)
    if at < end:
        gaps.append((at, float(end)))
    followed = [i for i in main if _overlaps(i, start, end)
                and any(i.start < hi and i.end >= lo for lo, hi in gaps)]
    return mine + followed, bool(mine)


def _hex(colour: int) -> str:
    return f"#{colour & 0xFFFFFF:06X}"


def _dedupe(items) -> list:
    return list(dict.fromkeys(items))


def _colours(own: ssf.Track, main: ssf.Track, start: int, end: int) -> list[str]:
    items, _ = _effective_items(own.colours.items if own.colours else [],
                                main.colours.items if main.colours else [], start, end)
    out = []
    for b in sorted(items, key=lambda b: b.start):
        out += [_hex(b.colour)] + ([_hex(b.colour_end)] if b.colour_end != b.colour else [])
    return _dedupe(out)


def _shapes(own: ssf.Track, main: ssf.Track, start: int, end: int) -> list[str]:
    items, _ = _effective_items(own.shapes.items if own.shapes else [],
                                main.shapes.items if main.shapes else [], start, end)
    return _dedupe(f"kind {b.kind}" for b in sorted(items, key=lambda b: b.start))


def _flags(trk: ssf.Track, spans_only: bool) -> list[tuple[int, str]]:
    if trk.positions is None:
        return []
    out = []
    for f in trk.positions.flags:
        if spans_only and not (trk.position_blocks and any(
                s.start <= f.t <= s.end for s in trk.position_blocks.items)):
            continue
        if f.preset < len(trk.positions.palette):
            out.append((f.t, trk.positions.palette[f.preset][0]))
    return out


def position_changes(script: ssf.TrackScript, trk: ssf.Track, start: int, end: int) -> list[tuple[int, str]]:
    """`(t, preset guid)` of the position changes `trk` shows in [start, end)."""
    if trk is script.main:
        flags = _flags(trk, spans_only=False)
    else:
        own_spans = trk.position_blocks.items if trk.position_blocks else []
        flags = _flags(trk, spans_only=True) + [
            f for f in _flags(script.main, spans_only=False)
            if not any(s.start <= f[0] <= s.end for s in own_spans)]
    return sorted(f for f in flags if start <= f[0] < end)


def script_end(script: ssf.TrackScript, floor: int = 0) -> int:
    """The last moment anything happens in the script (or `floor`, e.g. the song length)."""
    end = floor
    for trk in [script.main, *ssf.tracks(script)]:
        for lane in trk.lanes:
            end = max(end, *(k.t for k in lane.keys), 0)
        for sec in (trk.blocks, trk.colours, trk.strobes, trk.position_blocks, trk.shapes):
            if sec is not None:
                end = max([end] + [i.end for i in sec.items])
    return end


# ------------------------------------------------------------------- venue ----


def names_for(script: ssf.TrackScript, venues: list[ssf.VenueInfo]) -> tuple[dict[int, ssf.VenueNode], str | None]:
    """The nodes of the venue that holds the script's node ids, by id."""
    ids = {t.node for t in ssf.tracks(script)}
    best = max(venues, key=lambda v: len(ids & {n.id for n in v.nodes}), default=None)
    if best is None or not ids & {n.id for n in best.nodes}:
        return {}, None
    return {n.id: n for n in best.nodes}, best.name


def _groups(script: ssf.TrackScript, nodes: dict[int, ssf.VenueNode]) -> list[tuple[str, list[ssf.Track], str | None]]:
    """Fixture rows: `(name, tracks, kind)`. Vorlane cells fold into "<Vorlane> RGB" / "W"."""
    order: dict[str, tuple[list[ssf.Track], str | None]] = {"Main": ([script.main], None)}
    for trk in ssf.tracks(script):
        node = nodes.get(trk.node)
        if node is None:
            order.setdefault(f"node {trk.node}", ([], None))[0].append(trk)
            continue
        parent = nodes.get(node.parent) if node.parent is not None else None
        kind = "RGB" if node.name.startswith("RGB ") else "W" if node.name.startswith("W ") else None
        if parent is not None and kind:
            order.setdefault(f"{parent.name} {kind}", ([], kind))[0].append(trk)
        else:
            order.setdefault(node.name, ([], None))[0].append(trk)
    return [(name, trks, kind) for name, (trks, kind) in order.items()]


# -------------------------------------------------------------------- dump ----


def phrase_bounds(script: ssf.TrackScript, end: int) -> list[tuple[int, int, int]]:
    """`(first bar, start ms, end ms)` per 8-bar phrase, the last clipped at `end`."""
    g = ssf.grid(script)
    bars = max(g.bar_at(end), 1)
    out = []
    for first in range(1, bars + 1, PHRASE_BARS):
        start, stop = g.ms(first), min(g.ms(first + PHRASE_BARS), end)
        if stop > start:
            out.append((first, start, stop))
    return out


def dump_data(script: ssf.TrackScript, venues: list[ssf.VenueInfo], presets: list[ssf.Preset],
              duration_ms: int = 0) -> dict:
    """Per phrase and fixture: lit share, pulses, colours, positions, shapes, source."""
    end = script_end(script, duration_ms)
    nodes, venue_name = names_for(script, venues)
    phrases = phrase_bounds(script, end)
    boundaries = [t for _, s, e in phrases for t in (s, e)]
    preset_name = {p.guid: p.name for p in presets}
    groups = _groups(script, nodes)
    curves = {id(t): effective_curve(script, t, boundaries)
              for _, trks, _ in groups for t in trks}
    out = []
    for first, start, stop in phrases:
        rows = []
        for name, trks, kind in groups:
            lit_sets, colours, shapes, flags, own = [], [], [], [], False
            cell_pts = []
            for trk in trks:
                pts = _between(curves[id(trk)], start, stop)
                cell_pts.append(pts)
                lit_sets.append(_lit_intervals(pts))
                colours += _colours(trk, script.main, start, stop)
                shapes += _shapes(trk, script.main, start, stop)
                flags += position_changes(script, trk, start, stop)
                own = own or trk is script.main or any(
                    _overlaps(s, start, stop) for s in (trk.blocks.items if trk.blocks else []))
            pulses = _pulses(_max_curve(cell_pts))
            flags = sorted(set(flags))   # cells of a group share their position changes
            lit = _union([iv for ivs in lit_sets for iv in ivs])
            rows.append({
                "fixture": name,
                "source": "own" if own else "main",
                "lit": round(_length(lit) / (stop - start), 3),
                "pulses": pulses,
                "colours": _dedupe(colours),
                "positions": _dedupe(preset_name.get(g, g[:8]) for _, g in flags),
                "shapes": _dedupe(shapes),
                "position_changes": len(flags),
                "_kind": kind,
                "_lit": lit,
            })
        main_pts = _between(curves[id(script.main)], start, stop)
        levels = [v for _, v in main_pts] or [0.0]
        out.append({"phrase": len(out) + 1, "bars": f"{first}-{first + PHRASE_BARS - 1}",
                    "start_ms": start, "end_ms": stop, "rows": rows,
                    "main_range": [round(min(levels), 3), round(max(levels), 3)]})
    return {"venue": venue_name, "end_ms": end, "phrases": out}


def _public(data: dict) -> dict:
    """The dump without the private working keys (`_kind`, `_lit`)."""
    return {**data, "phrases": [
        {**p, "rows": [{k: v for k, v in r.items() if not k.startswith("_")} for r in p["rows"]]}
        for p in data["phrases"]]}


def _clock(ms: float) -> str:
    s = int(ms // 1000)
    return f"{s // 60}:{s % 60:02d}"


def dump_text(ref: ssf.TrackRef, data: dict) -> str:
    lines = [f"{ref.artist} — {ref.title}  ({ref.guid[:8]}, venue {data['venue'] or '?'})"]
    for p in _public(data)["phrases"]:
        lines += ["", f"Phrase {p['phrase']}  bars {p['bars']}  {_clock(p['start_ms'])}-{_clock(p['end_ms'])}"]
        width = max(len(r["fixture"]) for r in p["rows"])
        lines.append(f"  {'fixture':<{width}}  src   lit  pulses  colours | positions | shapes")
        for r in p["rows"]:
            lines.append(
                f"  {r['fixture']:<{width}}  {r['source']:<4} {r['lit'] * 100:3.0f}%  {r['pulses']:>6}  "
                f"{' '.join(r['colours']) or '-'} | {', '.join(r['positions']) or '-'} | "
                f"{', '.join(r['shapes']) or '-'}")
    return "\n".join(lines)


def dump_yaml(ref: ssf.TrackRef, data: dict) -> str:
    doc = {"track": f"{ref.artist} — {ref.title}", "guid": ref.guid, **_public(data)}
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=100)


# ----------------------------------------------------------------- analyze ----


def analyze_data(data: dict) -> dict:
    """Reduce a dump to the metrics the choreography is judged by."""
    phrases = data["phrases"]
    own_any: dict[str, bool] = {}
    changes: dict[str, int] = {}
    colours: list[str] = []
    for p in phrases:
        for r in p["rows"]:
            if r["fixture"] != "Main":
                own_any[r["fixture"]] = own_any.get(r["fixture"], False) or r["source"] == "own"
            changes[r["fixture"]] = changes.get(r["fixture"], 0) + r["position_changes"]
            colours += r["colours"]
    bars = len(phrases) * PHRASE_BARS
    overlaps = []
    for name in dict.fromkeys(r["fixture"] for p in phrases for r in p["rows"]):
        if not name.endswith(" W"):
            continue
        vorlane = name[:-2]
        rgb_len = w_with_rgb = 0.0
        for p in phrases:
            rows = {r["fixture"]: r for r in p["rows"]}
            rgb, white = rows.get(f"{vorlane} RGB"), rows.get(name)
            if rgb and white:
                rgb_len += _length(rgb["_lit"])
                w_with_rgb += _length(_intersect(rgb["_lit"], white["_lit"]))
        overlaps.append({"vorlane": vorlane,
                         "overlap": round(w_with_rgb / rgb_len, 3) if rgb_len else None})
    return {
        "bars": bars,
        "overriding": [n for n, v in own_any.items() if v],
        "following": [n for n, v in own_any.items() if not v],
        "white_overlap": overlaps,
        "position_changes_per_bar": {n: round(c / bars, 2) for n, c in changes.items() if c and bars},
        "colours": _dedupe(colours),
        "main_range": [{"phrase": p["phrase"], "bars": p["bars"], "min": p["main_range"][0],
                        "max": p["main_range"][1]} for p in phrases],
    }


def analyze_markdown(ref: ssf.TrackRef, a: dict) -> str:
    def pct(x):
        return "n/a" if x is None else f"{x * 100:.0f} %"

    lines = [f"## {ref.artist} — {ref.title}", "",
             f"- Phrases: {len(a['main_range'])} ({a['bars']} bars)",
             f"- Overriding Main ({len(a['overriding'])}): {', '.join(a['overriding']) or '-'}",
             f"- Following Main ({len(a['following'])}): {', '.join(a['following']) or '-'}",
             f"- Colours used: {' '.join(a['colours']) or '-'}", "",
             "White over colour (share of the time the RGB cells are lit that the W cells are too):", ""]
    lines += [f"- {o['vorlane']}: {pct(o['overlap'])}" for o in a["white_overlap"]] or ["- none"]
    lines += ["", "Position changes per bar:", ""]
    lines += [f"- {n}: {c}" for n, c in a["position_changes_per_bar"].items()] or ["- none"]
    lines += ["", "Main intensity range per phrase:", "", "| Phrase | Bars | Min | Max |", "|---|---|---|---|"]
    lines += [f"| {m['phrase']} | {m['bars']} | {pct(m['min'])} | {pct(m['max'])} |" for m in a["main_range"]]
    return "\n".join(lines)


# ------------------------------------------------------------------ render ----


def _frac(level: int) -> float:
    return round(level / 2**32, 4)


def _rgbw(colour: int, ext: int) -> list[int]:
    """`[r, g, b, w]`; the extra word's second byte is read as a White level (unverified)."""
    return [(colour >> 16) & 255, (colour >> 8) & 255, colour & 255, (ext >> 8) & 255]


def _node_data(trk: ssf.Track, preset_name: dict[str, str]) -> dict:
    """One track as the page reads it: `k` intensity keys `[t, fraction]`, `B` intensity
    spans, `C` colour blocks `[start, end, rgbw, rgbw]`, `D` position flags `[t, preset name]`,
    `F` position spans, `G` shape blocks `[start, end, kind, size]`, `E` strobes
    `[start, end, rate, rate_end]`. Empty parts are left out."""
    lane = ssf.intensity(trk)
    flags = []
    if trk.positions:
        for f in trk.positions.flags:
            if f.preset < len(trk.positions.palette):
                guid = trk.positions.palette[f.preset][0]
                flags.append([f.t, preset_name.get(guid.lower(), guid[:8])])
    parts = {
        "k": [[k.t, _frac(k.level)] for k in lane.keys] if lane else [],
        "B": [[s.start, s.end] for s in trk.blocks.items] if trk.blocks else [],
        "C": [[b.start, b.end, _rgbw(b.colour, b.ext), _rgbw(b.colour_end, b.ext_end)]
              for b in trk.colours.items] if trk.colours else [],
        "D": flags,
        "F": [[s.start, s.end] for s in trk.position_blocks.items] if trk.position_blocks else [],
        "G": [[b.start, b.end, b.kind, round(b.params[0], 3)]
              for b in trk.shapes.items] if trk.shapes else [],
        "E": [[b.start, b.end, b.rate, b.rate_end] for b in trk.strobes.items] if trk.strobes else [],
    }
    return {key: value for key, value in parts.items() if value}


def _rig_data(fixtures: list[ls._Fixture], rig: ls.Rig, label_of) -> dict:
    """Rig fixture key -> corner, kind and the node labels the page looks its tracks up by.
    `label_of(track)` claims a track and returns its label; a fixture without a track gets
    `None` there (it follows Main)."""
    by_key = {f.key: f for f in fixtures}
    out = {}
    for key, fx in rig.fixtures.items():
        entry = {"corner": fx.corner, "kind": fx.kind}
        res = by_key.get(key)
        if fx.kind == "mover":
            entry["node"] = label_of(res.tracks.get("mover")) if res else None
        elif fx.kind == "matrix":
            entry["master"] = label_of(res.tracks.get("master")) if res else None
            entry["cells"] = [label_of(res.tracks.get((row, col)) if res else None)
                              for row in range(len(ls.COLOUR_ROWS) + 1) for col in range(ls.MATRIX_COLS)]
        elif fx.kind == "haze":
            entry["fan"] = label_of(res.tracks.get("fan")) if res else None
            entry["fog"] = label_of(res.tracks.get("fog")) if res else None
        else:
            entry["lamps"] = fx.extra.get("lamps", 7)
        out[key] = entry
    return out


def sim_data(script: ssf.TrackScript, venues: list[ssf.VenueInfo], presets: list[ssf.Preset],
             rig: ls.Rig, choreo: ls.Choreography | None = None, *,
             duration_ms: int = 0, title: str = "") -> dict:
    """What the simulator page draws. `before` is `script`; with `choreo`, `after` is the
    script compiled from it (the very bytes `apply` would write), else None. Both map a node
    label (its venue name; `name [id]` where the name repeats) to `_node_data`, and `Main` to
    the Main track. Only the nodes the rig names are exported; the rest of the venue follows Main.

    Keys: title, end (ms), grid ([[ms, bpm]]), sections ({name, bars, intent, start, end}),
    rig (see `_rig_data`), before, after, cues ({bar, t, fixture, what} the compiler left to
    the owner). Raises `lightshow.CompileError` when the choreography does not fit the script."""
    after, cues = None, []
    if choreo is not None:
        after, cues = ls.compile_choreography(choreo, script, rig, venues, presets)
    venue, trks = ls._venue_of(script, venues)
    fixtures = ls._resolve(rig, venue, {t.node: t for t in trks})
    names = [n.name for n in venue.nodes]
    labels: dict[int, str] = {}
    by_id = {n.id: n for n in venue.nodes}

    def label_of(trk: ssf.Track | None) -> str | None:
        if trk is None:
            return None
        node = by_id[trk.node]
        labels[trk.node] = node.name if names.count(node.name) == 1 and node.name != "Main" \
            else f"{node.name} [{node.id}]"
        return labels[trk.node]

    rig_out = _rig_data(fixtures, rig, label_of)
    preset_name = {p.guid.lower(): p.name for p in presets}

    def export(s: ssf.TrackScript) -> dict:
        out = {"Main": _node_data(s.main, preset_name)}
        for node_id, label in labels.items():
            trk = ssf.track(s, node_id)
            if trk is not None:
                out[label] = _node_data(trk, preset_name)
        return out

    g = ssf.grid(script)
    return {
        "title": title,
        "end": max(script_end(script, duration_ms), script_end(after) if after else 0),
        "grid": [[t, bpm] for t, bpm in script.tempo],
        "sections": [{"name": s.name, "bars": list(s.bars), "intent": s.intent,
                      "start": g.ms(s.bars[0]), "end": g.ms(s.bars[1] + 1)}
                     for s in (choreo.sections if choreo else [])],
        "rig": rig_out,
        "before": export(script),
        "after": export(after) if after else None,
        "cues": [{"bar": c.bar, "t": c.time_ms, "fixture": c.fixture, "what": c.what} for c in cues],
    }


def page_html(data: dict) -> str:
    """The simulator page with `data` inlined. Every `<` in the JSON is escaped, so nothing in
    a title or a cue can close the script tag."""
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c")
    template = SIM_TEMPLATE.read_text(encoding="utf-8")
    placeholder = "/*__DATA__*/null"
    assert template.count(placeholder) == 1, f"{SIM_TEMPLATE.name} needs exactly one {placeholder}"
    return template.replace(placeholder, blob)


# --------------------------------------------------------------------- CLI ----


def _base_path(project: ssf.Project, guid: str) -> Path:
    """Where `apply` keeps the track's base script: next to the project folder."""
    return project.folder.parent / "nextrack-backups" / "base" / project.script_path(guid).name


def _load(project: ssf.Project, text: str, prefer_base: bool = False) -> tuple[ssf.TrackRef, ssf.TrackScript]:
    ref = project.resolve(text)
    path = project.script_path(ref.guid)
    if prefer_base and _base_path(project, ref.guid).is_file():
        path = _base_path(project, ref.guid)
    if not path.is_file():
        raise LookupError(f"{ref.artist} — {ref.title}: no script file {path.name}")
    return ref, ssf.parse_script(path.read_bytes())


def cmd_tracks(project: ssf.Project, args) -> int:
    want = ssf._fold(args.match) if args.match else ""
    for r in project.trackmap():
        if want and want not in ssf._fold(f"{r.artist} {r.title}"):
            continue
        bpm = f"{r.bpm:>3}" if r.bpm else "  -"
        length = _clock(r.duration_ms) if r.duration_ms else "-:--"
        print(f"{r.guid[:8]}  {bpm}  {length:>5}  {r.artist} — {r.title}")
    return 0


def cmd_dump(project: ssf.Project, args) -> int:
    ref, script = _load(project, args.track)
    venues, presets = project.venues()
    data = dump_data(script, venues, presets, ref.duration_ms or 0)
    print((dump_yaml if args.yaml else dump_text)(ref, data))
    return 0


def cmd_analyze(project: ssf.Project, args) -> int:
    venues, presets = project.venues()
    blocks = []
    for text in args.tracks:
        ref, script = _load(project, text)
        blocks.append(analyze_markdown(ref, analyze_data(dump_data(script, venues, presets, ref.duration_ms or 0))))
    print("\n\n".join(blocks))
    return 0


def _yaml_checked(path: Path, problems) -> dict | None:
    """A YAML file that `problems` finds nothing wrong with, else None (problems on stderr)."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    found = problems(data)
    for p in found:
        print(f"{path}: {p}", file=sys.stderr)
    return None if found else data


def cmd_render(project: ssf.Project, args) -> int:
    rig_path = Path(args.rig) if args.rig else DEFAULT_RIG
    if _yaml_checked(rig_path, ls.problems_rig) is None:
        return 1
    rig = ls.load_rig(rig_path)
    choreo = None
    if args.choreo:
        if _yaml_checked(Path(args.choreo), ls.problems_choreography) is None:
            return 1
        choreo = ls.load_choreography(Path(args.choreo))
    ref, script = _load(project, args.track, prefer_base=True)
    venues, presets = project.venues()
    data = sim_data(script, venues, presets, rig, choreo, duration_ms=ref.duration_ms or 0,
                    title=f"{ref.artist} — {ref.title}")
    page = page_html(data)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    source = "base copy" if _base_path(project, ref.guid).is_file() else "project file"
    print(f"wrote {out} ({len(page):,} bytes); before = {source}"
          + (f", after = {args.choreo} compiled" if choreo else ""))
    for c in data["cues"]:
        print(f"manual cue, bar {c['bar']}: {c['fixture']}: {c['what']}")
    return 0


# ----------------------------------------------------------- compile / apply ----


class Refused(Exception):
    """A guard said no; the message is the one-line reason. Nothing has been written."""


WSL_INTEROP = Path("/proc/sys/fs/binfmt_misc/WSLInterop")


def soundswitch_running() -> bool:
    """True when `tasklist.exe` lists SoundSwitch.exe. False when it is absent and this is
    not WSL (nothing to check, e.g. CI). Any other failure raises `Refused`: a guard that
    passes when its own check fails is no guard."""
    cannot = "cannot verify that SoundSwitch is closed"
    try:
        done = subprocess.run(["tasklist.exe"], capture_output=True, text=True,
                              errors="replace", timeout=30)
    except FileNotFoundError as e:
        if WSL_INTEROP.exists():
            raise Refused(f"{cannot}: tasklist.exe not found under WSL") from e
        return False
    except (OSError, subprocess.SubprocessError) as e:
        raise Refused(f"{cannot}: {e}") from e
    if done.returncode != 0:
        raise Refused(f"{cannot}: tasklist.exe exited with {done.returncode}")
    return "SoundSwitch.exe" in (done.stdout or "")


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_atomic(path: Path, data: bytes) -> None:
    """Write `data` to a temp file next to `path`, then rename it over `path`."""
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _load_inputs(args) -> tuple[ls.Choreography, ls.Rig]:
    rig_path = Path(args.rig) if args.rig else DEFAULT_RIG
    if _yaml_checked(rig_path, ls.problems_rig) is None:
        raise Refused(f"{rig_path}: invalid rig")
    if _yaml_checked(Path(args.choreo), ls.problems_choreography) is None:
        raise Refused(f"{args.choreo}: invalid choreography")
    return ls.load_choreography(Path(args.choreo)), ls.load_rig(rig_path)


def _compile_checked(choreo, base: ssf.TrackScript, venues, presets, rig) -> tuple[bytes, list]:
    """Compile onto `base`, serialize, re-parse; refuse unless the bytes parse back to the
    compiled script and everything outside the venue's tracks and Main equals `base`."""
    try:
        out, cues = ls.compile_choreography(choreo, base, rig, venues, presets)
    except ls.CompileError as e:
        raise Refused(str(e)) from e
    data = ssf.serialize_script(out)
    again = ssf.parse_script(data)
    if again != out or ssf.serialize_script(again) != data:
        raise Refused("the compiled script does not survive serialize and re-parse")
    venue, _ = ls._venue_of(base, venues)
    ids = {n.id for n in venue.nodes}
    check = copy.deepcopy(again)
    check.main = base.main
    if len(check.venues) != len(base.venues):
        raise Refused("the compiled script changed the number of venues; untouched parts differ from the base")
    for cv, bv in zip(check.venues, base.venues):
        if [t.node for t in cv.tracks] != [t.node for t in bv.tracks]:
            raise Refused("the compiled script added or removed tracks; untouched parts differ from the base")
        cv.tracks = [b if b.node in ids else c for c, b in zip(cv.tracks, bv.tracks)]
    if check != base:
        raise Refused("the compiled script changed tracks the choreography does not touch; "
                      "untouched parts differ from the base")
    windows = _windows(choreo, base)
    pairs = [("Main", again.main, base.main)]
    for cv, bv in zip(again.venues, base.venues):
        pairs += [(f"node {c.node}", c, b) for c, b in zip(cv.tracks, bv.tracks) if b.node in ids]
    hue = any(ls.section_layers(sec)["hue"] != "auto" for sec in choreo.sections)
    if not hue and again.main != base.main:
        raise Refused("the compiled script changed Main although no section sets a hue; "
                      "untouched parts differ from the base")
    for name, c, b in pairs:
        problem = _outside_problem(c, b, windows)
        if problem:
            raise Refused(f"the compiled script changed {name} {problem} outside the sections; "
                          "untouched parts differ from the base")
    return data, cues


def _windows(choreo, base: ssf.TrackScript) -> list[tuple[int, int]]:
    """The sections' spans in ms, inclusive, as the compiler cuts them."""
    g = ssf.grid(base)
    return [(g.ms(sec.bars[0]), g.ms(sec.bars[1] + 1) - 1) for sec in choreo.sections]


def _inside(t: int, windows) -> bool:
    return any(s <= t <= e for s, e in windows)


def _next_to(t: int, windows) -> bool:
    return any(t == s - 1 or t == e + 1 for s, e in windows)


def _clip_outside(item, windows) -> list[tuple[int, int]]:
    """The pieces of [item.start, item.end] that lie outside every window."""
    pieces = [(item.start, item.end)]
    for s, e in windows:
        cut = []
        for a, b in pieces:
            if b < s or a > e:
                cut.append((a, b))
                continue
            if a < s:
                cut.append((a, s - 1))
            if b > e:
                cut.append((e + 1, b))
        pieces = cut
    return pieces


def _block_pieces(items, windows) -> list[tuple[int, int, str]]:
    """Blocks clipped to the complement of the windows, touching equal pieces merged."""
    pieces = []
    for it in items:
        sig = repr(dataclasses.replace(it, start=0, end=0))
        pieces += [(a, b, sig) for a, b in _clip_outside(it, windows)]
    merged: list[list] = []
    for a, b, sig in sorted(pieces):
        if merged and merged[-1][2] == sig and a <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b, sig])
    return [tuple(m) for m in merged]


def _outside_problem(out: ssf.Track, base: ssf.Track, windows) -> str | None:
    """What differs between the tracks outside the windows (None if nothing): intensity and
    every other lane's keys (a boundary key next to a window passes when it carries the base's
    level there), blocks B C E F G clipped to the complement, position flags."""
    if (out.node, out.link, len(out.lanes)) != (base.node, base.link, len(base.lanes)):
        return "its identity or lanes"
    for i, (lo, lb) in enumerate(zip(out.lanes, base.lanes)):
        if (lo.attr, lo.ver, lo.default) != (lb.attr, lb.ver, lb.default):
            return f"lane {i} header"
        old = {(k.t, k.level) for k in lb.keys if not _inside(k.t, windows)}
        new = {(k.t, k.level) for k in lo.keys if not _inside(k.t, windows)}
        for t, level in list(new - old):
            if _next_to(t, windows) and level == ssf.level_at(lb, t):
                new.discard((t, level))
        if old != new:
            return f"keys of lane {i}"
    for name in ("blocks", "colours", "strobes", "position_blocks", "shapes"):
        so, sb = getattr(out, name), getattr(base, name)
        if _block_pieces(so.items if so else [], windows) != _block_pieces(sb.items if sb else [], windows):
            return f"the {name} blocks"

    def flags(trk):
        pos = trk.positions
        return sorted((f.t, pos.palette[f.preset][0] if f.preset < len(pos.palette) else f.preset)
                      for f in (pos.flags if pos else []) if not _inside(f.t, windows))

    if flags(out) != flags(base):
        return "the position flags"
    return None


def _items(trk: ssf.Track) -> set[str]:
    out = {f"key {i} {k.t} {k.level}" for i, lane in enumerate(trk.lanes) for k in lane.keys}
    for name in ("blocks", "colours", "strobes", "position_blocks", "shapes"):
        sec = getattr(trk, name)
        out |= {f"{name} {item!r}" for item in (sec.items if sec else [])}
    if trk.positions:
        out |= {f"flag {f!r}" for f in trk.positions.flags}
    return out


def diff_summary(before: ssf.TrackScript, after: ssf.TrackScript, venues: list[ssf.VenueInfo]) -> list[str]:
    """One line per fixture whose track changed: keys and blocks added and removed."""
    nodes, _ = names_for(before, venues)
    a_tracks = {t.node: t for t in [after.main, *ssf.tracks(after)]}
    lines = []
    for b in [before.main, *ssf.tracks(before)]:
        old, new = _items(b), _items(a_tracks[b.node])
        if old != new:
            name = "Main" if b is before.main else (
                f"{nodes[b.node].name} [{b.node}]" if b.node in nodes else f"node {b.node}")
            lines.append(f"  {name}: +{len(new - old)} / -{len(old - new)} keys and blocks")
    return lines


def _plan_base(project: ssf.Project, ref: ssf.TrackRef, current: bytes, adopt: bool) -> tuple[bytes, bool]:
    """`(base bytes, whether the base file must be (re)written)`. Writes nothing."""
    guid = ref.guid
    base_path = _base_path(project, guid)
    root = base_path.parent.parent
    state_path = root / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    entry = state.get(guid) or {}
    if adopt:
        return current, True
    if entry.get("applied") and _sha(current) != entry["applied"]:
        raise Refused("the project file was edited in SoundSwitch since the last apply; "
                      "--adopt-current keeps those edits as the new base")
    if entry.get("base") and not base_path.is_file():
        first = sorted(p for p in root.glob("*/" + base_path.name) if p.parent.name != "base")
        hint = f"; the earliest backup is {first[0]}" if first else ""
        raise Refused(f"the base copy {base_path} is missing although state.json has one for this track{hint}; "
                      "restoring it is safer than re-basing (--adopt-current makes the current file the base)")
    if base_path.is_file():
        base = base_path.read_bytes()
        if entry.get("base") and _sha(base) != entry["base"]:
            raise Refused(f"the base copy {base_path} changed since it was made (state.json disagrees)")
        return base, False
    return current, True


def cmd_compile(project: ssf.Project, args) -> int:
    choreo, rig = _load_inputs(args)
    ref, base = _load(project, choreo.soundswitch, prefer_base=True)
    out = Path(args.out)
    if out.resolve() in (project.script_path(ref.guid).resolve(), _base_path(project, ref.guid).resolve()):
        raise Refused(f"{out} is the project's own file or its base; pick another -o")
    venues, presets = project.venues()
    data, cues = _compile_checked(choreo, base, venues, presets, rig)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f"wrote {out} ({len(data):,} bytes) for {ref.artist} — {ref.title}")
    for c in cues:
        print(f"manual cue, bar {c.bar}: {c.fixture}: {c.what}")
    return 0


def cmd_apply(project: ssf.Project, args) -> int:
    choreo, rig = _load_inputs(args)
    ref = project.resolve(choreo.soundswitch)
    target = project.script_path(ref.guid)
    if not target.is_file():
        raise Refused(f"{ref.artist} — {ref.title}: no script file {target.name}")
    if args.apply and soundswitch_running():
        raise Refused("SoundSwitch is running; close it before --apply")
    current = target.read_bytes()
    base_bytes, new_base = _plan_base(project, ref, current, args.adopt_current)
    try:
        base = ssf.parse_script(base_bytes)
        round_trips = ssf.serialize_script(base) == base_bytes
    except Exception as e:  # a corrupt file may fail in any way
        raise Refused(f"the base script cannot be parsed ({e}); nothing was written") from e
    if not round_trips:
        raise Refused("the base script does not round-trip (parse then serialize changes its bytes); "
                      "nothing was written")
    venues, presets = project.venues()
    data, cues = _compile_checked(choreo, base, venues, presets, rig)
    resized = len(data) != len(current)
    print(f"{ref.artist} — {ref.title}  ({ref.guid[:8]})")
    print(f"compiled from the {'current project file' if new_base else 'base copy'}; "
          f"size {len(current):,} -> {len(data):,} bytes")
    lines = diff_summary(base, ssf.parse_script(data), venues)
    print("fixtures touched:" if lines else "no fixture changes")
    for line in lines:
        print(line)
    for c in cues:
        print(f"manual cue, bar {c.bar}: {c.fixture}: {c.what}")
    if not args.apply:
        print("dry run: nothing written (add --apply to write)"
              + ("; the size change also needs --accept-resize" if resized and not args.accept_resize else ""))
        return 0
    if resized and not args.accept_resize:
        raise Refused(f"the output is {len(data):,} bytes, the project file {len(current):,}: "
                      "a resized file needs --accept-resize")
    root = _base_path(project, ref.guid).parent.parent
    base_path = _base_path(project, ref.guid)
    staged = target.with_name(target.name + ".tmp")
    try:
        staged.write_bytes(data)  # first, so an unwritable project leaves no base or backup behind
        _commit(project, ref, target, staged, root, base_path, base_bytes, new_base, current, data)
    finally:
        if staged.exists():
            staged.unlink()
    return 0


def _commit(project, ref, target, staged, root, base_path, base_bytes, new_base, current, data) -> None:
    base_path.parent.mkdir(parents=True, exist_ok=True)
    if new_base:
        _write_atomic(base_path, base_bytes)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    folder, n = root / stamp, 1
    while True:
        try:
            folder.mkdir()
            break
        except FileExistsError:
            n += 1
            folder = root / f"{stamp}-{n}"
    backup = folder / target.name
    backup.write_bytes(current)
    os.replace(staged, target)
    state_path = root / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    state[ref.guid] = {"base": _sha(base_bytes), "applied": _sha(data)}
    _write_atomic(state_path, json.dumps(state, indent=2, sort_keys=True).encode("utf-8"))
    print(f"wrote {target}")
    print(f"backup: {backup}")
    print(f'restore: cp "{backup}" "{target}"')


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project", default=argparse.SUPPRESS,
                        help=f"SoundSwitch project folder (default: ${PROJECT_ENV})")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=os.environ.get(PROJECT_ENV),
                    help=f"SoundSwitch project folder (default: ${PROJECT_ENV})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("tracks", parents=[common], help="list the project's tracks")
    t.add_argument("--match", help="only tracks whose artist or title contains this text")
    d = sub.add_parser("dump", parents=[common], help=(
        "per phrase and fixture: lit, pulses, colours, positions, shapes. Vorlane cells are "
        "grouped into '<Vorlane> RGB' and '<Vorlane> W' rows: lit = union of the cells' lit "
        "time, pulses = rises on the max of the cells' curves, the rest = union across cells"))
    d.add_argument("track", help="GUID, GUID prefix or 'Artist — Title'")
    d.add_argument("--yaml", action="store_true", help="print YAML instead of the text table")
    a = sub.add_parser("analyze", parents=[common], help="the dump reduced to metrics (Markdown)")
    a.add_argument("tracks", nargs="+", metavar="track")
    r = sub.add_parser("render", parents=[common], help=(
        "write the room simulator as one HTML file: before = the track's base script "
        "(<project parent>/nextrack-backups/base/) when it exists, else the project file; "
        "with --choreo, after = the choreography compiled onto it"))
    r.add_argument("track", help="GUID, GUID prefix or 'Artist — Title'")
    r.add_argument("--choreo", help="a lightshows/tracks/*.yml choreography")
    r.add_argument("--rig", help="the rig file (default: lightshows/rig.yml of this repo)")
    r.add_argument("-o", "--out", required=True, help="the HTML file to write")

    c = sub.add_parser("compile", parents=[common], help=(
        "compile a choreography onto the track's base script (else the project file) and write "
        "it to -o; the project is not touched"))
    c.add_argument("choreo", help="a lightshows/tracks/*.yml choreography")
    c.add_argument("--rig", help="the rig file (default: lightshows/rig.yml of this repo)")
    c.add_argument("-o", "--out", required=True, help="the .ssfile to write")
    ap_ = sub.add_parser("apply", parents=[common], help=(
        "dry-run by default: show what compiling the choreography would change. With --apply, "
        "back up the project file and replace it (SoundSwitch must be closed)"))
    ap_.add_argument("choreo", help="a lightshows/tracks/*.yml choreography")
    ap_.add_argument("--rig", help="the rig file (default: lightshows/rig.yml of this repo)")
    ap_.add_argument("--apply", action="store_true", help="really write the project file")
    ap_.add_argument("--accept-resize", action="store_true",
                     help="allow an output whose size differs from the project file")
    ap_.add_argument("--adopt-current", action="store_true",
                     help="make the project file as it is now the new base (keeps edits made in SoundSwitch)")

    args = ap.parse_args(argv)
    if not args.project:
        print(f"set --project or {PROJECT_ENV}", file=sys.stderr)
        return 2
    folder = Path(args.project)
    if not folder.is_dir():
        print(f"project folder not found: {folder}", file=sys.stderr)
        return 2
    project = ssf.Project(folder)
    try:
        code = {"tracks": cmd_tracks, "dump": cmd_dump, "analyze": cmd_analyze,
                "render": cmd_render, "compile": cmd_compile, "apply": cmd_apply}[args.cmd](project, args)
    except (Refused, LookupError, OSError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1
    for w in project.venue_warnings() if project._venues else []:
        print(f"warning: {w}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
