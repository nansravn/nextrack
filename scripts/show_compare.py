"""show_compare.py — the facts of two shows, side by side (`nextrack_show.py compare`).

`facts(show, rules, advice)` reads a compiled show into plain printable facts; `diff_facts`
says what changed between two of them. That is how a rework proves it kept the night's story.
No new measure lives here: every number comes from `show_analysis`, `show_views` or the
compiled sections, and the formulas are theirs. Only the rounding is this module's:

- arrivals: per track, `bar N: look, draw D, colour C` (colours by palette name);
- moments: per occurrence of a moment, `<track> bar N` (the first section of a cue or handover
  with a `moment`; never a bridge or an echo), keyed by the moment's name in clock order: the
  first `name`, the next ones `name #2`, `name #3`, ... (a tie goes to the earlier track, then
  the lower bar), so moving any occurrence is a difference;
- drops: per `<track> bar N`, `rank R, response X` (response rounded to 2; `~` unknown);
- signatures: per declared signature, its delivered share rounded to 2;
- looks: per look, the minutes of the night rounded to 0:05 (`FIVE_S` seconds);
- colours: per `<zone> <colour>`, the same rounding (zones `movers`, `matrix`, `hue`);
- windows: per track, the bars of its `handover` and of its `bridge`;
- findings: per rule name, the count of findings, and `advice <rule>` for the advice.

A track in only one show is `+ key` or `- key` in the facts that name it.
"""
from __future__ import annotations

import show_analysis
import show_language
import show_views
from show_language import CompiledShow, ShowFinding

FACTS = ("arrivals", "moments", "drops", "signatures", "looks", "colours", "windows", "findings")
FIVE_S = 5


def _title(track: str) -> str:
    return track.split(" — ", 1)[-1]


def _minutes(seconds: float) -> str:
    """Seconds rounded to the nearest 0:05, as `m:ss`."""
    return show_views.clock_text(round(seconds / FIVE_S) * FIVE_S)


def _arrivals(show: CompiledShow) -> dict[str, str]:
    names = show_views._palette_names(show)
    out: dict[str, str] = {}
    for track in show.tracks:
        for sec in track.sections:
            if sec.origin.role != "arrival" or sec.origin.kind == "echo":
                continue
            matrix = show_language.layer_word(sec.layers.get("matrix"))
            draw = matrix.get("draw") if isinstance(matrix, dict) else matrix
            colour = matrix.get("colour") if isinstance(matrix, dict) else None
            if isinstance(colour, list):
                colour = ",".join(names.get(str(c).upper(), str(c)) for c in colour)
            elif isinstance(colour, str):
                colour = names.get(colour.upper(), colour)
            out[track.track] = f"bar {sec.bars[0]}: {sec.origin.look or sec.name}, draw {draw}, colour {colour}"
    return out


def _moments(show: CompiledShow) -> dict[str, str]:
    """Every occurrence of a moment, in clock order: `name`, then `name #2`, `name #3`, ..."""
    clock = show_analysis.analyse(show).clock
    found = []
    for i, (track, tc) in enumerate(zip(show.tracks, clock.tracks)):
        previous = None
        for sec in track.sections:
            first = show_views._first_of_cue(previous, sec)
            previous = sec
            o = sec.origin
            if o.kind in ("bridge", "echo") or not first or not o.moment:
                continue
            found.append((tc.at(sec.bars[0]), i, sec.bars[0], o.moment, f"{_title(track.track)} bar {sec.bars[0]}"))
    out: dict[str, str] = {}
    seen: dict[str, int] = {}
    for _, _, _, name, where in sorted(found):
        seen[name] = seen.get(name, 0) + 1
        out[name if seen[name] == 1 else f"{name} #{seen[name]}"] = where
    return out


def _drops(show: CompiledShow) -> dict[str, str]:
    out = {}
    for d in show_analysis.analyse(show).drops:
        response = "~" if d.response is None else f"{d.response:.2f}"
        out[f"{_title(d.track)} bar {d.bar}"] = f"rank {d.rank}, response {response}"
    return out


def _signatures(show: CompiledShow) -> dict[str, str]:
    return {s.name: f"{s.share:.2f}" for s in show_analysis.analyse(show).identity.signatures}


def _looks(summary: dict) -> dict[str, str]:
    return {name: _minutes(s) for name, s in summary["looks"].items()}


def _colours(summary: dict) -> dict[str, str]:
    return {f"{zone} {colour}": _minutes(s)
            for zone, by in summary["colours"].items() for colour, s in by.items()}


def _windows(show: CompiledShow) -> dict[str, str]:
    out: dict[str, str] = {}
    for track in show.tracks:
        for kind in ("handover", "bridge"):
            bars = sum(s.bars[1] - s.bars[0] + 1 for s in track.sections if s.origin.kind == kind)
            if bars:
                out[f"{_title(track.track)} {kind}"] = f"{bars} bars"
    return out


def _rule_name(f: ShowFinding) -> str:
    head = f.message.split(":", 1)[0]
    return head if ":" in f.message and " " not in head else f.rule


def _findings(rules: list[ShowFinding], advice: list[ShowFinding]) -> dict[str, str]:
    counts: dict[str, int] = {}
    for prefix, found in (("", rules), ("advice ", advice)):
        for f in found:
            key = prefix + _rule_name(f)
            counts[key] = counts.get(key, 0) + 1
    return {k: str(v) for k, v in counts.items()}


def facts(show: CompiledShow, rules: list[ShowFinding], advice: list[ShowFinding],
          room=None) -> dict[str, dict[str, str]]:
    """Every fact of `FACTS` for a compiled show: a key (a track, a track and bar, a name)
    mapped to a printable value. `room` (optional) is `show_views.night_summary`'s."""
    summary = show_views.night_summary(show, show_analysis.analyse(show).clock, room)
    return {"arrivals": _arrivals(show), "moments": _moments(show), "drops": _drops(show),
            "signatures": _signatures(show), "looks": _looks(summary), "colours": _colours(summary),
            "windows": _windows(show), "findings": _findings(rules, advice)}


def diff_facts(a: dict, b: dict) -> dict[str, list[str]]:
    """Per fact, the lines that differ, sorted by key: `- key: value` (only in a), `+ key: value`
    (only in b), `~ key: a -> b`. An empty list is a fact that is the same."""
    out: dict[str, list[str]] = {}
    for fact in FACTS:
        x, y = a.get(fact, {}), b.get(fact, {})
        lines = []
        for key in sorted(set(x) | set(y)):
            if key not in y:
                lines.append(f"- {key}: {x[key]}")
            elif key not in x:
                lines.append(f"+ {key}: {y[key]}")
            elif x[key] != y[key]:
                lines.append(f"~ {key}: {x[key]} -> {y[key]}")
        out[fact] = lines
    return out
