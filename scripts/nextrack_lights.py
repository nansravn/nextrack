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

An "effective" value is what the fixture really shows: its own when one of its spans
covers the moment, else the Main track's. See scripts/README.md.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

import soundswitch_format as ssf

PROJECT_ENV = "NEXTRACK_SOUNDSWITCH_PROJECT"  # machine-specific, so it lives outside the repo
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
            lit_sets, pulses, colours, shapes, flags, own = [], 0, [], [], [], False
            for trk in trks:
                pts = _between(curves[id(trk)], start, stop)
                lit_sets.append(_lit_intervals(pts))
                pulses += _pulses(pts)
                colours += _colours(trk, script.main, start, stop)
                shapes += _shapes(trk, script.main, start, stop)
                flags += position_changes(script, trk, start, stop)
                own = own or trk is script.main or any(
                    _overlaps(s, start, stop) for s in (trk.blocks.items if trk.blocks else []))
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


# --------------------------------------------------------------------- CLI ----


def _load(project: ssf.Project, text: str) -> tuple[ssf.TrackRef, ssf.TrackScript]:
    ref = project.resolve(text)
    path = project.script_path(ref.guid)
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
    d = sub.add_parser("dump", parents=[common], help="per phrase and fixture")
    d.add_argument("track", help="GUID, GUID prefix or 'Artist — Title'")
    d.add_argument("--yaml", action="store_true", help="print YAML instead of the text table")
    a = sub.add_parser("analyze", parents=[common], help="the dump reduced to metrics (Markdown)")
    a.add_argument("tracks", nargs="+", metavar="track")

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
        code = {"tracks": cmd_tracks, "dump": cmd_dump, "analyze": cmd_analyze}[args.cmd](project, args)
    except (LookupError, OSError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1
    for w in project.venue_warnings() if project._venues else []:
        print(f"warning: {w}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
