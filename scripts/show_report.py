"""show_report.py — the report's section names and the text of its six analysis sections:
follows, drops, builds, variety, arc and identity (spec section A4 of
docs/superpowers/specs/2026-11-07-show-team-design.md).

Every number comes from `show_analysis.analyse` (its docstring states each formula); this
module only prints it, as facts and never as a verdict. Shares print as whole percents
(`round(100 x share)`), correlations and 0-1 scores with two decimals, slopes with a sign.
A value that cannot be computed prints `-`. A track whose map has no `mix` block (version 1)
is named `<title> (interim)` wherever its music energy enters a number.

Each `*_items` function returns `Line`s, `(text, names)`: `names` is None for the section's
frame (its header and its column legend), else the set of track indices (set order, from 0)
the line names, empty for a night-level line. `select` cuts a section to one track; each
`*_lines` function returns the texts alone, header first.

Python API: `REPORT_SECTIONS`, `Line`, `select`, `light_unknown_s`, `follows_lines`,
`drops_lines`, `builds_lines`, `variety_lines`, `arc_lines`, `identity_lines` and their
`*_items`.
"""
from __future__ import annotations

import show_analysis
from show_analysis import BREATHER_S, Analysis, Run
from show_language import CompiledShow
from show_views import ShowClock, clock_text

REPORT_SECTIONS = ("summary", "tracks", "peaks", "hits", "follows", "drops", "builds", "variety", "arc",
                   "identity", "budget", "arrivals", "advice", "decided", "findings")

Line = tuple[str, "frozenset[int] | None"]


def select(lines: list[Line], index: int | None) -> list[str]:
    """The texts of a section's lines. With a track `index`: the frame and the lines that name
    that track, or nothing when no line names it."""
    if index is None:
        return [text for text, _ in lines]
    if not any(names is not None and index in names for _, names in lines):
        return []
    return [text for text, names in lines if names is None or index in names]


def light_unknown_s(clock: ShowClock, energy: list) -> float:
    """Seconds of the legs whose E_light is unknown (the autoscript decides): the sum of
    `TrackClock.span_s(b, b)` over the leg bars with no light value."""
    return sum(tc.span_s(b, b) for tc, te in zip(clock.tracks, energy)
               for b in range(tc.leg[0], tc.leg[1] + 1) if te.at("light", b) is None)


# ----------------------------------------------------------------- helpers --


def _title(track: str) -> str:
    return track.split(" — ", 1)[-1]


def _label(a: Analysis, index: int, track: str) -> str:
    """The track's title, `(interim)` when its music energy uses the interim formula."""
    interim = 0 <= index < len(a.energy) and a.energy[index].interim
    return _title(track) + (" (interim)" if interim else "")


def _pct(share: float | None) -> str:
    return "-" if share is None else f"{round(100 * share)}%"


def _fixed(value: float | None, digits: int = 2, sign: bool = False) -> str:
    if value is None:
        return "-"
    return f"{value:+.{digits}f}" if sign else f"{value:.{digits}f}"


def _frame(*texts: str) -> list[Line]:
    return [(t, None) for t in texts]


def _item(text: str, *indices: int) -> Line:
    return text, frozenset(indices)


def _texts(lines: list[Line]) -> list[str]:
    return [text for text, _ in lines]


def _words(values: list[str]) -> str:
    return ", ".join(values) or "-"


def _lag(lag: int | None) -> str:
    """`0`, a signed shift (`+3`, the light is late), `(beyond 1)` past one bar, `-` for none."""
    if lag is None:
        return "-"
    return "0" if lag == 0 else f"{lag:+d}" + (" (beyond 1)" if abs(lag) > 1 else "")


def _boundaries(items: list) -> str:
    """`bar (music dm, light dl)` per boundary, `-` for none."""
    return ", ".join(f"{b.bar} (music {b.music:+.1f}, light {b.light:+.1f})" for b in items) or "-"


# ---------------------------------------------------------------- follows --


def follows_items(a: Analysis, show: CompiledShow) -> list[Line]:
    """`follows`: one line per track, `rho` (Spearman of E_music and E_light over the leg), the
    agreement at the map's section boundaries, the lag, the missed boundaries, the unmotivated
    light changes and the share of the leg whose light is unknown."""
    out = _frame("follows",
                 "  track · rho of E_music and E_light over the leg · agree: share of the boundaries where the "
                 "music moves 2+ that the light follows by 1+ · lag in bars (+ the light is late) · missed "
                 "boundaries · unmotivated light changes · unknown light")
    for f in a.follows:
        out.append(_item(f"  {_label(a, f.index, f.track)} · rho {_fixed(f.rho)} · agree {_pct(f.agreement)} · "
                         f"lag {_lag(f.lag)} · missed {_boundaries(f.missed)} · "
                         f"unmotivated {_boundaries(f.unmotivated)} · unknown {_pct(f.unknown_share)}", f.index))
    return out


def follows_lines(a: Analysis, show: CompiledShow) -> list[str]:
    return _texts(follows_items(a, show))


# ------------------------------------------------------------------ drops --


def drops_items(a: Analysis, show: CompiledShow) -> list[Line]:
    """`drops`: every sounding map drop in salience rank, with what makes it salient and the
    light's response, then the rank agreement of salience and response."""
    out = _frame("drops",
                 "  rank · clock · track bar · salience (loudness rise, bass return, onset density rise, main) · "
                 "response (contrast of E_light against the 2 bars before, dimensions changed, freshness)")
    for d in a.drops:
        main = ", main" if d.main else ""
        out.append(_item(f"  rank {d.rank} · {clock_text(d.clock_s)} · {_label(a, d.index, d.track)} {d.bar} · "
                         f"salience {d.salience:.2f} (loud {d.loud_rise:+.1f}, bass {d.bass_return:.2f}, "
                         f"density {d.density_rise:+.2f}{main}) · response {_fixed(d.response)} "
                         f"(contrast {_fixed(d.contrast, 1, sign=True)}, changes {d.change}, "
                         f"fresh {_fixed(d.freshness)})", d.index))
    if a.drops:
        rho = show_analysis.drop_agreement(a.drops)
        out.append(_item(f"  agreement: rho {_fixed(rho)} of salience and response over the drops above the "
                         "median salience"))
    else:
        out.append(_item("  no map drop sounds"))
    return out


def drops_lines(a: Analysis, show: CompiledShow) -> list[str]:
    return _texts(drops_items(a, show))


# ----------------------------------------------------------------- builds --


def builds_items(a: Analysis, show: CompiledShow) -> list[Line]:
    """`builds`: each build with the music's tension slope, the light's activity and brightness
    slopes, and how the light goes into the drop (dip, ramp, flat or unknown)."""
    out = _frame("builds",
                 "  clock · track bars · music tension slope per bar (0-1) · light activity and brightness "
                 "slopes (digits per bar) · into the drop: dip, ramp, flat or unknown")
    for b in a.builds:
        clock = a.clock.at(b.index, b.bars[0])
        out.append(_item(f"  {clock_text(clock)} · {_label(a, b.index, b.track)} {b.bars[0]}-{b.bars[1]} · "
                         f"music {b.music_slope:+.3f} · activity {_fixed(b.activity_slope, sign=True)} · "
                         f"brightness {_fixed(b.brightness_slope, sign=True)} · into {b.into}", b.index))
    if not a.builds:
        out.append(_item("  no build of 4 bars or more"))
    return out


def builds_lines(a: Analysis, show: CompiledShow) -> list[str]:
    return _texts(builds_items(a, show))


# ---------------------------------------------------------------- variety --


def _run_last(clock: ShowClock, run: Run) -> int:
    """The index of the track where a static run ends: the last track whose leg starts before
    the run's end on the set clock (legs follow each other on the clock)."""
    end = clock.at(run.index, run.bars[0]) + run.seconds
    return max((i for i, tc in enumerate(clock.tracks) if i >= run.index and tc.start_s < end - 1e-6),
               default=run.index)


def variety_items(a: Analysis, show: CompiledShow) -> list[Line]:
    """`variety`: the longest static runs, the windowed variety per minute, each dimension's
    dominant value, the neighbours' similarity, the drop templates, the phrase alignment of the
    changes and what each track uses."""
    v = a.variety
    out = _frame("variety")
    runs: list[Line] = []
    for run in v.static_runs:
        last = _run_last(a.clock, run)
        if last == run.index:
            where = f"{_title(run.track)} {run.bars[0]}-{run.bars[1]}"
        else:                          # across a leg boundary: name both tracks
            where = f"{_title(run.track)} {run.bars[0]} – {_title(show.tracks[last].track)} {run.bars[1]}"
        runs.append(_item(f"  {clock_text(a.clock.at(run.index, run.bars[0]))} · {where} · "
                          f"{clock_text(run.seconds)} · {run.music or '-'}", *range(run.index, last + 1)))
    if runs:
        named = frozenset().union(*(names for _, names in runs))
        out += [("  static runs, the longest stretches of one light signature: clock · bars · length · "
                 "music under it", named), *runs]
    strip = "".join("~" if d is None else str(d) for d in v.window)
    out.append(_item(f"  per minute, 0-9, the entropy of the signatures over 4 minutes: |{strip}|"))
    for dim, dom in v.dominance.items():
        out.append(_item(f"  dominant {dim}: {dom.value} {_pct(dom.share)}" + (" (declared)" if dom.declared else "")))
    for i, cosine in v.similarity:
        out.append(_item(f"  similarity {_title(show.tracks[i].track)} / {_title(show.tracks[i + 1].track)} "
                         f"{cosine:.2f}", i, i + 1))
    distinct, count = v.templates
    out.append(_item(f"  drop templates: {distinct} distinct of {count} drops"))
    out.append(_item(f"  phrase lines: {_pct(v.phrase_share)} of the light's changes start a map section or "
                     "fall on a 4-bar line from one"))
    for u in v.usage:
        colours = "; ".join(f"{zone} {_words(names)}" for zone, names in u.colours.items())
        out.append(_item(f"  uses {_title(u.track)}: looks {_words(u.looks)} · colours {colours} · "
                         f"aims {_words(u.aims)} · gestures {_words(u.gestures)} · drop templates {u.templates}",
                         u.index))
    return out


def variety_lines(a: Analysis, show: CompiledShow) -> list[str]:
    return _texts(variety_items(a, show))


# -------------------------------------------------------------------- arc --


def arc_items(a: Analysis, show: CompiledShow) -> list[Line]:
    """`arc`: per track the owner's energy against the light, then the checks: rho, headroom,
    the staircase, the steps, the top drops with no breather and the label questions."""
    arc = a.arc
    out = _frame("arc",
                 "  clock · track · owner energy · E_light mean and 90th percentile · activity mean · warm "
                 "colour share · rare resources")
    for t in arc.tracks:
        rare = ", ".join(f"{k} {n}" for k, n in t.rare.items() if n) or "-"
        energy = "-" if t.energy is None else t.energy
        out.append(_item(f"  {clock_text(a.clock.tracks[t.index].start_s)} · {_label(a, t.index, t.track)} · "
                         f"e{energy} · light {_fixed(t.mean, 1)}, p90 {_fixed(t.p90, 1)} · "
                         f"activity {_fixed(t.activity, 1)} · warm {_pct(t.warm)} · rare {rare}", t.index))
    out.append(_item(f"  rho {_fixed(arc.rho)} (mean) and {_fixed(arc.rho90)} (p90): the owner's energy against "
                     "the light per track"))
    out.append(_item(f"  headroom {_fixed(arc.headroom)}: the highest p90 before the first track at the night's "
                     "top energy, over the night's highest"))
    tracks = {t.index: t for t in arc.tracks}
    checks: dict[str, list[Line]] = {"staircase": [], "step": [], "no breather": [], "label": []}
    for i in arc.staircase:
        t = tracks[i]
        checks["staircase"].append(_item(f"  staircase: {_title(t.track)} sets a new light p90 ({_fixed(t.p90, 1)}) "
                                         f"at e{t.energy}, below an earlier energy", i))
    for i, kind in arc.steps:
        before, now = tracks[i - 1], tracks[i]
        checks["step"].append(_item(f"  step {kind}: {_title(before.track)} -> {_title(now.track)}: energy "
                                    f"e{before.energy} -> e{now.energy}, light mean {_fixed(before.mean, 1)} -> "
                                    f"{_fixed(now.mean, 1)}", i - 1, i))
    ranks = {(d.index, d.bar): d.rank for d in a.drops}
    for i, bar in arc.breathers:
        checks["no breather"].append(_item(
            f"  no breather: {_title(show.tracks[i].track)} {bar} (drop rank {ranks.get((i, bar), '-')}): no bar "
            f"within {clock_text(BREATHER_S)} after it at or below the night's median E_light", i))
    titles = {_title(t.track): i for i, t in enumerate(show.tracks)}
    for question in arc.labels:
        names = [i for title, i in titles.items() if question.startswith(f"{title}: ")]
        checks["label"].append(_item(f"  label: {question}", *names))
    for name, lines in checks.items():
        out += lines or [_item(f"  {name}: -")]
    return out


def arc_lines(a: Analysis, show: CompiledShow) -> list[str]:
    return _texts(arc_items(a, show))


# --------------------------------------------------------------- identity --


def identity_items(a: Analysis, show: CompiledShow, set_arc: str | None = None) -> list[Line]:
    """`identity`: the arc (the identity's own, else `set_arc`, the set's front matter, else
    none), each declared signature's measured share against its wanted bounds with its
    occurrences on the clock, and the most present undeclared value per dimension."""
    ident = a.identity
    if ident.arc is not None:
        arc = f"{ident.arc} (identity)"
    else:
        arc = f"{set_arc} (the set's)" if set_arc else "none"
    out = _frame("identity")
    out.append(_item(f"  arc: {arc}"))
    for sig in ident.signatures:
        wanted = ", ".join(x for x in (f"min {_pct(sig.min)}" if sig.min is not None else "",
                                       f"max {_pct(sig.max)}" if sig.max is not None else "") if x) or "-"
        where = "in range" if sig.ok else "below min" if sig.min is not None and sig.share < sig.min else "above max"
        named = frozenset(o[0] for o in sig.occurrences)
        out.append((f"  signature {sig.name}: holds {_pct(sig.share)} of the night, wanted {wanted}: {where} · "
                    f"{sig.intent}", named))
        for index, track, (lo, hi), seconds in sig.occurrences:
            out.append(_item(f"    {clock_text(a.clock.at(index, lo))} · {_title(track)} {lo}-{hi} · "
                             f"{clock_text(seconds)}", index))
    if not ident.signatures:
        out.append(_item("  signatures: none declared"))
    for dim, (value, share) in ident.undeclared.items():
        out.append(_item(f"  undeclared {dim}: {value} {_pct(share)}"))
    return out


def identity_lines(a: Analysis, show: CompiledShow, set_arc: str | None = None) -> list[str]:
    return _texts(identity_items(a, show, set_arc))
