"""show_rules.py — the show rules of the show language and `evaluate_show`, its one entry point.

A show rule is a Python function registered here with `show_rule`. It reads the compiled show
(every section with its provenance) and its parameters from the `rules:` mapping of `show.yml`,
and returns `show-rules` findings that point at the cue, the handover or the track file to fix.
The `advice:` mapping takes the same rule ids and parameters as design goals: their findings
carry the rule id `show-advice` and never fail a check. Each rule also checks its own
parameters; a bad parameter or an unknown rule id is a `show-source` finding at `rules:` (or
`advice:`) in `show.yml`. The budget and `exclusive` count **occurrences** (`occurrences`),
which never come from bridges or echoes. See
docs/superpowers/specs/2026-11-06-show-language-design.md ("Show rules") and
docs/superpowers/specs/2026-11-06-show-critic-design.md ("Advice").

Python API: `RULES`, `EFFECT_KEYS`, `ADVICE`, `show_rule`, `ShowRule`, `Occurrence`, `occurrences`,
`rule_param_findings`, `run_rules`, `evaluate_show`.
"""
from __future__ import annotations

import dataclasses
import difflib
import re
from collections.abc import Callable
from dataclasses import dataclass

from show_gestures import GESTURES
from show_language import (BRIDGE_BARS, ID_RE, CompiledSection, CompiledShow, CompiledTrack, Provenance,
                           ShowFinding, ShowInputs, ShowSource, clean, compile_show, layer_word)

SOURCE = "show-source"
RULE_ID = "show-rules"
ADVICE = "show-advice"
_KEYS = {"rules": RULE_ID, "advice": ADVICE}    # the show.yml mappings that name rules -> their findings' id
EFFECT_KEYS = ("white-accent", "white-flash", "strobe", "uv")
_BEAT_BAR_RE = re.compile(r"([0-9]+)\.[0-9]+")
_UNLIT = (None, "off", "auto")


@dataclass
class Occurrence:
    key: str
    track: str          # Artist — Title of the track it is in
    bar: int            # a section's or a gesture cue's first bar; a beat's or a roll's own bar
    origin: Provenance  # where a finding about it points


@dataclass
class ShowRule:
    name: str
    doc: str                                       # the function's docstring
    params: str                                    # one line: the parameter shape, for vocab
    check: Callable[[object, dict], list[str]]     # (params, clean show.yml) -> problems
    fn: Callable[[CompiledShow, object], list[ShowFinding]]


RULES: dict[str, ShowRule] = {}


def show_rule(name: str, *, params: str, check: Callable[[object, dict], list[str]]):
    """Register the decorated function as the show rule `name`."""
    def register(fn):
        RULES[name] = ShowRule(name, (fn.__doc__ or "").strip(), params, check, fn)
        return fn
    return register


# ----------------------------------------------------------------- helpers --


def _line(node: object) -> int:
    return node.get("__line__", 0) if isinstance(node, dict) else 0


def _title(track: str) -> str:
    return track.split(" — ", 1)[1] if " — " in track else track


def _shown(value: object) -> str:
    """A value as a message shows it: YAML words for booleans and null, `repr` otherwise."""
    if value is True or value is False:
        return "true" if value else "false"
    return "null" if value is None else repr(value)


def _listing(items) -> str:
    return ", ".join(str(i) for i in items) or "none"


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _span(section: CompiledSection) -> str:
    a, b = section.bars
    return f"{a}" if a == b else f"{a}-{b}"


def _where(track: CompiledTrack, section: CompiledSection) -> str:
    """A section as a finding names it: `Title a-b (name)`, and for a bridge that it is the copy
    of the handover the finding points at."""
    bridge = ", the bridge copying this handover" if section.origin.kind == "bridge" else ""
    return f"{_title(track.track)} {_span(section)} ({section.name}{bridge})"


def _finding(origin: Provenance, message: str) -> ShowFinding:
    return ShowFinding(origin.path, origin.line, RULE_ID, message)


def _sorted(findings: list[ShowFinding]) -> list[ShowFinding]:
    return sorted(findings, key=lambda f: (f.path, f.line, f.message))


def _looks(show: dict) -> dict:
    looks = show.get("looks") if isinstance(show, dict) else None
    return looks if isinstance(looks, dict) else {}


def _hint(name: str, known: list[str]) -> str:
    close = difflib.get_close_matches(name, known, n=1, cutoff=0.6)
    return f"; did you mean {close[0]!r}?" if close else ""


# ------------------------------------------------------------- occurrences --


def _beat_bar(beat: object, section: CompiledSection) -> int:
    m = _BEAT_BAR_RE.fullmatch(str(beat))
    return int(m[1]) if m else section.bars[0]


def _effect_bars(key: str, section: CompiledSection) -> list[int]:
    """The bars of the occurrences of an effect key in one section (spec's table)."""
    layers = section.layers
    white, strobe, movers = layers.get("white"), layers.get("strobe"), layers.get("movers")
    if key == "white-accent" and isinstance(white, dict) and isinstance(white.get("accent"), list):
        return [_beat_bar(beat, section) for beat in white["accent"]]
    if key == "white-flash" and isinstance(white, dict) and "flash" in white:
        return [section.bars[0]]
    if key == "strobe" and isinstance(strobe, dict):
        bars = [_beat_bar(beat, section) for beat in strobe["hit"]] if isinstance(strobe.get("hit"), list) else []
        if "roll" in strobe:
            roll = strobe["roll"]
            bars.append(roll[0] if isinstance(roll, list) and roll and _is_int(roll[0]) else section.bars[0])
        return bars
    if key == "uv" and (layer_word(layers.get("uv")) == "on"
                        or isinstance(movers, dict) and movers.get("move") == "uv"):
        return [section.bars[0]]
    return []


def occurrences(show: CompiledShow, key: str) -> list[Occurrence]:
    """What the budget and `exclusive` count for `key`, in show order; never a bridge or an
    echo (each copies light already counted where it was written).

    An effect key (`EFFECT_KEYS`) counts beats and sections as the spec's table says; a gesture
    name counts the cues that invoke it (distinct path and line), at their first bar; any
    other key is a look name and counts the sections whose provenance names it."""
    out: list[Occurrence] = []
    seen: set[tuple[str, int]] = set()
    for track in show.tracks:
        for section in track.sections:
            origin = section.origin
            if origin.kind in ("bridge", "echo"):
                continue
            if key in EFFECT_KEYS:
                out += [Occurrence(key, track.track, bar, origin) for bar in _effect_bars(key, section)]
            elif key in GESTURES:
                if origin.gesture == key and (origin.path, origin.line) not in seen:
                    seen.add((origin.path, origin.line))
                    out.append(Occurrence(key, track.track, section.bars[0], origin))
            elif origin.look == key:
                out.append(Occurrence(key, track.track, section.bars[0], origin))
    return out


# ------------------------------------------------------- parameter checks --


def _unexpected(params: dict, allowed: tuple[str, ...], where: str = "") -> list[str]:
    prefix = f"{where}: " if where else ""
    return [f"{prefix}unexpected key {k!r} (allowed: {', '.join(allowed)})" for k in params if k not in allowed]


def _ids_problem(value: object, where: str, *, empty: bool = True) -> list[str]:
    if (isinstance(value, list) and (empty or value)
            and all(isinstance(v, str) and ID_RE.fullmatch(v) for v in value)):
        return []
    what = "a list" if empty else "a non-empty list"
    return [f"{where} {_shown(value)} is not {what} of moment names (kebab-case ids)"]


def _key_problem(key: object, show: dict) -> str | None:
    """None when `key` is something occurrences count: a look of `show.yml`, a gesture or an
    effect. A look named like a gesture or an effect would be ambiguous."""
    looks = _looks(show)
    if not isinstance(key, str):
        return f"key {_shown(key)} is not a name"
    builtin = "an effect" if key in EFFECT_KEYS else "a gesture" if key in GESTURES else None
    if builtin and key in looks:
        return f"{key!r} is both a look and {builtin}: rename the look"
    if builtin or key in looks:
        return None
    known = sorted(looks) + sorted(GESTURES) + list(EFFECT_KEYS)
    return (f"unknown key {key!r} (a look: {_listing(sorted(looks))}; a gesture: {_listing(sorted(GESTURES))}; "
            f"an effect: {_listing(EFFECT_KEYS)}){_hint(key, known)}")


def _check_budget(params: object, show: dict) -> list[str]:
    if not isinstance(params, dict):
        return [f"{_shown(params)} is not a mapping of key -> {{max?, moments?, from?}}"]
    if not params:
        return ["names no key: write key -> {max?, moments?, from?}"]
    out = []
    for key, limits in params.items():
        problem = _key_problem(key, show)
        if problem:
            out.append(problem)
            continue
        if not isinstance(limits, dict):
            out.append(f"{key} {_shown(limits)} is not a mapping of max?, moments?, from?")
            continue
        out += _unexpected(limits, ("max", "moments", "from"), key)
        if "max" in limits and not (_is_int(limits["max"]) and limits["max"] >= 0):
            out.append(f"{key}.max {_shown(limits['max'])} is not a whole number (0 or more)")
        if "moments" in limits:
            out += _ids_problem(limits["moments"], f"{key}.moments", empty=False)   # max: 0 says never
        if "from" in limits and not (isinstance(limits["from"], str) and " — " in limits["from"]):
            out.append(f"{key}.from {_shown(limits['from'])} is not the 'Artist — Title' of a track of this show")
    return out


def _budget_from_problems(params: object, tracks: list[str]) -> list[str]:
    """A budget `from` must name a track of the show: one of its track files' `track`."""
    if not isinstance(params, dict):
        return []
    out = []
    for key, limits in params.items():
        start = limits.get("from") if isinstance(limits, dict) else None
        if isinstance(start, str) and " — " in start and start not in tracks:
            hint = _hint(start, tracks) or "; write the Artist — Title of one of its track files"
            out.append(f"{key}.from {start!r} is not a track of this show{hint}")
    return out


def _check_names(params: object, show: dict) -> list[str]:
    """total-dark: `{only: [look or gesture names]}`."""
    if not isinstance(params, dict):
        return [f"{_shown(params)} is not a mapping {{only: [look or gesture names]}}"]
    out = _unexpected(params, ("only",))
    if "only" not in params:
        return out + ["missing key only"]
    only = params["only"]
    if not (isinstance(only, list) and all(isinstance(n, str) for n in only)):
        return out + [f"only {_shown(only)} is not a list of look or gesture names"]
    looks = _looks(show)
    for name in only:
        if name not in looks and name not in GESTURES:
            out.append(f"only: {name!r} is neither a look nor a gesture (looks: {_listing(sorted(looks))}; "
                       f"gestures: {_listing(sorted(GESTURES))}){_hint(name, sorted(looks) + sorted(GESTURES))}")
    return out


def _check_arrivals(params: object, show: dict) -> list[str]:
    if params is True:
        return []
    if not isinstance(params, dict):
        return [f"{_shown(params)} is not true or {{draw_differs: true|false}}"]
    out = _unexpected(params, ("draw_differs",))
    if "draw_differs" in params and not isinstance(params["draw_differs"], bool):
        out.append(f"draw_differs {_shown(params['draw_differs'])} is not true or false")
    return out


def _check_true(params: object, show: dict) -> list[str]:
    if params is True:
        return []
    return [f"{_shown(params)} is not true: movers-aim has no parameters; remove it from rules to not run it"]


def _check_moments(params: object, show: dict) -> list[str]:
    if params is True:
        return []
    if not isinstance(params, dict):
        return [f"{_shown(params)} is not true or {{except_moments: [moment names]}}"]
    out = _unexpected(params, ("except_moments",))
    if "except_moments" in params:
        out += _ids_problem(params["except_moments"], "except_moments")
    return out


def _check_bridges(params: object, show: dict) -> list[str]:
    low, high = BRIDGE_BARS
    if not isinstance(params, dict):
        return [f"{_shown(params)} is not a mapping {{max: {low}-{high}}}"]
    out = []
    if "max" not in params:
        out.append("missing key max")
    elif not (_is_int(params["max"]) and low <= params["max"] <= high):
        out.append(f"max {_shown(params['max'])} is not a whole number of bars from {low} to {high}")
    return out + _unexpected(params, ("max",))


def _check_exclusive(params: object, show: dict) -> list[str]:
    if not isinstance(params, dict):
        return [f"{_shown(params)} is not a mapping {{keys: [keys], except_tracks?: [tracks]}}"]
    out = _unexpected(params, ("keys", "except_tracks"))
    if "keys" not in params:
        out.append("missing key keys")
    else:
        keys = params["keys"]
        if not isinstance(keys, list) or len(keys) < 2 or len(set(map(repr, keys))) < len(keys):
            out.append(f"keys {_shown(keys)} is not a list of two or more keys")
        else:
            out += [f"keys: {p}" for p in (_key_problem(k, show) for k in keys) if p]
    if "except_tracks" in params:
        tracks = params["except_tracks"]
        if not (isinstance(tracks, list) and all(isinstance(t, str) and t.strip() for t in tracks)):
            out.append(f"except_tracks {_shown(tracks)} is not a list of tracks (Artist — Title, or the title)")
    return out


# ------------------------------------------------------------------- rules --


@show_rule("budget", params="key -> {max?, moments?, from?}; a key is a look, a gesture, white-accent, "
                            "white-flash, strobe or uv",
           check=_check_budget)
def budget(show: CompiledShow, params: dict) -> list[ShowFinding]:
    """How much of each key the night may spend, and where.

    A key has more than `max` occurrences (one finding, at the first occurrence past the max,
    listing them all by track and bar); an occurrence whose cue has no `moment` in `moments`;
    an occurrence in a track before `from` (the "Artist — Title" of a show track) in set order.
    Bridges never count."""
    out = []
    order = {track.track: i for i, track in enumerate(show.tracks)}
    for key, limits in params.items():
        found = occurrences(show, key)
        top = limits.get("max")
        if top is not None and len(found) > top:
            listed = ", ".join(f"{_title(o.track)} {o.bar}" for o in found)
            times = "1 time" if len(found) == 1 else f"{len(found)} times"
            out.append(_finding(found[top].origin, f"budget: {key} is used {times}, max {top}: {listed}"))
        if "moments" in limits:
            moments = limits["moments"]
            for o in found:
                moment = o.origin.moment
                if moment in moments:
                    continue
                state = "has no moment" if moment is None else f"is in moment {moment!r}"
                node = "handover" if o.origin.kind == "handover" else "cue"
                out.append(_finding(o.origin, f"budget: {key} in {_title(o.track)} {o.bar} {state}, and {key} is "
                                              f"allowed only in {_listing(moments)}: give its {node} one of those "
                                              "moments, or remove it"))
        start = order.get(limits.get("from"))
        if start is not None:
            for o in found:
                if order.get(o.track, start) < start:
                    out.append(_finding(o.origin, f"budget: {key} in {_title(o.track)} {o.bar} comes before "
                                                  f"{_title(limits['from'])}, the first track allowed to use it "
                                                  "(from): remove it here, or set from to an earlier track"))
    return out


def _total_dark(layers: dict) -> bool:
    hue = layer_word(layers.get("hue"))
    return (layer_word(layers.get("movers")) == "off" and layer_word(layers.get("matrix")) == "off"
            and (hue in ("dark", "off") or isinstance(hue, dict) and hue.get("state") == "dark")
            and all(layer_word(layers.get(layer)) in _UNLIT for layer in ("white", "strobe", "uv")))


def _source(origin: Provenance) -> str:
    if origin.look and origin.gesture:
        return f"look {origin.look!r} of gesture {origin.gesture!r}"
    if origin.look:
        return f"look {origin.look!r}"
    return f"gesture {origin.gesture!r}" if origin.gesture else "an inline look"


@show_rule("total-dark", params="{only: [look or gesture names]}", check=_check_names)
def total_dark(show: CompiledShow, params: dict) -> list[ShowFinding]:
    """Total dark is rare and named.

    A compiled section (a bridge too, not an echo: its original is checked where it is written)
    with movers `off`, matrix `off`, hue `dark` (or `off`) and no lit white, strobe or uv has
    neither its `look` nor its `gesture` in `only`."""
    only = params["only"]
    out = []
    for track in show.tracks:
        for section in track.sections:
            origin = section.origin
            if (origin.kind == "echo" or not _total_dark(section.layers) or origin.look in only
                    or origin.gesture in only):
                continue
            out.append(_finding(origin, f"total-dark: {_where(track, section)} leaves every fixture dark (movers "
                                        f"off, matrix off, hue dark) with {_source(origin)}, which is not in only "
                                        f"({_listing(only)}): use one of those, or light a layer"))
    return out


def _draw(section: CompiledSection) -> object:
    matrix = layer_word(section.layers.get("matrix", "auto"))
    return matrix.get("draw") if isinstance(matrix, dict) else matrix


@show_rule("arrivals", params="true or {draw_differs?: true|false}", check=_check_arrivals)
def arrivals(show: CompiledShow, params: object) -> list[ShowFinding]:
    """Every track arrives once.

    A track has no cue with `role: arrival`, or more than one; with `draw_differs`, two
    consecutive tracks' arrival sections have the same matrix draw (a matrix word, such as
    `auto` when it is not written, compares as itself)."""
    differ = isinstance(params, dict) and params.get("draw_differs") is True
    out = []
    before: tuple[CompiledTrack, CompiledSection] | None = None
    for track in show.tracks:
        title = _title(track.track)
        found = [s for s in track.sections if s.origin.role == "arrival"]
        if not found:
            out.append(ShowFinding(track.path, 1, RULE_ID,     # no cue to point at: the track file's top
                                   f"arrivals: {title} has no cue with role: arrival: give it to the cue that "
                                   "shows the track (usually its first drop)"))
        elif len(found) > 1:
            listed = ", ".join(f"{s.name} {s.bars[0]}" for s in found)
            out.append(_finding(found[1].origin, f"arrivals: {title} has {len(found)} arrivals ({listed}): keep "
                                                 "role: arrival on one cue"))
        here = (track, found[0]) if len(found) == 1 else None
        if differ and before is not None and here is not None and _draw(before[1]) == _draw(here[1]):
            out.append(_finding(here[1].origin, f"arrivals: {title} arrives at {here[1].bars[0]} with matrix draw "
                                                f"{_draw(here[1])!r}, as {_title(before[0].track)} did at "
                                                f"{before[1].bars[0]}: draw one of the two arrivals differently"))
        before = here
    return out


@show_rule("movers-aim", params="true", check=_check_true)
def movers_aim(show: CompiledShow, params: object) -> list[ShowFinding]:
    """Every written movers layer aims.

    A compiled section's movers is a mapping without `position` or `positions` (the autoscript
    would pick a random preset every two bars). An echo is not checked: its original is."""
    out = []
    for track in show.tracks:
        for section in track.sections:
            movers = section.layers.get("movers")
            if (section.origin.kind != "echo" and isinstance(movers, dict) and "position" not in movers
                    and "positions" not in movers):
                out.append(_finding(section.origin, f"movers-aim: {_where(track, section)} moves the movers "
                                                    f"({movers.get('move')}) without position or positions, so the "
                                                    "autoscript picks a random preset every two bars: aim them"))
    return out


@show_rule("matrix-not-cloned", params="true or {except_moments?: [moment names]}", check=_check_moments)
def matrix_not_cloned(show: CompiledShow, params: object) -> list[ShowFinding]:
    """The two Vorlanes never draw the same thing, outside the excepted moments.

    A compiled section's matrix is a mapping with neither `mirror` nor `pingpong`, and its
    cue's moment is not in `except_moments`. A bridge carries the moment of the handover it
    copies, so the exception reaches the copy too. An echo is not checked: its original is."""
    excepted = params.get("except_moments", []) if isinstance(params, dict) else []
    out = []
    for track in show.tracks:
        for section in track.sections:
            matrix, moment = section.layers.get("matrix"), section.origin.moment
            if (section.origin.kind == "echo" or not isinstance(matrix, dict) or matrix.get("mirror")
                    or matrix.get("pingpong") or moment in excepted):
                continue
            fix = f", or add its moment {moment!r} to except_moments" if moment else ""
            out.append(_finding(section.origin, f"matrix-not-cloned: {_where(track, section)} draws the matrix "
                                                f"({matrix.get('draw')}) with neither mirror nor pingpong, so both "
                                                f"Vorlanes draw the same: add mirror: true or pingpong: true{fix}"))
    return out


@show_rule("exclusive", params="{keys: [two or more budget keys], except_tracks?: [Artist — Title, or the title]}",
           check=_check_exclusive)
def exclusive(show: CompiledShow, params: dict) -> list[ShowFinding]:
    """Some keys never share a track.

    A track has occurrences of more than one of `keys` (budget keys), unless the track is in
    `except_tracks` (its "Artist — Title" or its title). The finding points at the first
    occurrence of the second key the track uses."""
    keys, excepted = params["keys"], params.get("except_tracks") or []
    found = {key: occurrences(show, key) for key in keys}
    out = []
    for track in show.tracks:
        if track.track in excepted or _title(track.track) in excepted:
            continue
        used = [(key, [o for o in found[key] if o.track == track.track]) for key in keys]
        used = sorted(((key, occ) for key, occ in used if occ), key=lambda item: item[1][0].bar)
        if len(used) < 2:
            continue
        listed = _and([f"{key} ({', '.join(str(o.bar) for o in occ)})" for key, occ in used])
        out.append(_finding(used[1][1][0].origin, f"exclusive: {_title(track.track)} uses {listed}, and a track "
                                                  f"uses at most one of {', '.join(keys)}: keep one, or add the "
                                                  "track to except_tracks"))
    return out


def _length(section: CompiledSection) -> int:
    """A section's length in bars: `last - first + 1` (bars 25-32 last 8)."""
    first, last = section.bars
    return last - first + 1


def _plain(track: CompiledTrack, section: CompiledSection) -> str:
    return f"{_title(track.track)} {_span(section)} ({section.name})"


@show_rule("bridges", params="{max: 1-32}", check=_check_bridges)
def bridges(show: CompiledShow, params: dict) -> list[ShowFinding]:
    """No side of a mix window is longer than `max` bars.

    A compiled handover section, or the bridge section that copies it into the next track, is
    longer than `max` bars (`_length`). Both findings point at the handover's line in the
    outgoing track's file, which owns the window, and name both lengths and both tracks: the fix
    is in both."""
    top = params["max"]
    windows: dict[tuple[str, int], list] = {}   # the handover's (path, line) -> [handover, bridge]
    for track in show.tracks:
        for section in track.sections:
            kind = section.origin.kind
            if kind in ("handover", "bridge"):
                window = windows.setdefault((section.origin.path, section.origin.line), [None, None])
                window[kind == "bridge"] = (track, section)
    out = []
    for handover, bridge in windows.values():
        if handover is not None and _length(handover[1]) > top:
            track, section = handover
            a = section.bars[0]
            other = (f"; its bridge, {_plain(*bridge)}, lasts {_length(bridge[1])}" if bridge is not None
                     else ", and no bridge copies it")
            out.append(_finding(section.origin, f"bridges: {_where(track, section)} lasts {_length(section)} bars, "
                                                f"max {top}{other}: end the handover by bar {a + top - 1} "
                                                f"(until: {a + top})"))
        if bridge is not None and _length(bridge[1]) > top:
            track, section = bridge
            other = (f"; the handover it copies, {_plain(*handover)}, lasts {_length(handover[1])}"
                     if handover is not None else "")
            out.append(_finding(section.origin, f"bridges: {_where(track, section)} lasts {_length(section)} bars, "
                                                f"max {top}{other}: start a cue of {_title(track.track)} at or "
                                                f"before bar {section.bars[0] + top}"))
    return out


# ------------------------------------------- identity and monotony rules --
# These read `show_analysis.analyse` (the energy series and the measures on them), imported inside
# each rule: show_analysis imports show_views, which imports this module.


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_signatures(params: object, show: dict) -> list[str]:
    if params is True:
        return []
    return [f"{_shown(params)} is not true: signatures has no parameters; remove it from rules to not run it"]


def _check_one_key(key: str, ok: Callable[[object], bool], shape: str, wanted: str) -> Callable[[object, dict], list[str]]:
    """A `check` for a rule whose only parameter is `key`: a mapping `{key: value}`, `ok(value)`."""
    def check(params: object, show: dict) -> list[str]:
        if not isinstance(params, dict):
            return [f"{_shown(params)} is not a mapping {shape}"]
        out = [] if key in params else [f"missing key {key}"]
        if key in params and not ok(params[key]):
            out.append(f"{key} {_shown(params[key])} is not {wanted}")
        return out + _unexpected(params, (key,))
    return check


_check_static_run = _check_one_key("max_seconds", lambda v: _is_int(v) and 30 <= v <= 600,
                                   "{max_seconds: 30-600}", "a whole number of seconds from 30 to 600")
_check_neighbours = _check_one_key("max_similarity", lambda v: _is_number(v) and 0 <= v <= 1,
                                   "{max_similarity: 0-1}", "a number from 0 to 1")
_check_phrase = _check_one_key("min_share", lambda v: _is_number(v) and 0 <= v <= 1,
                               "{min_share: 0-1}", "a number from 0 to 1")
_check_distinct = _check_one_key("top", lambda v: (_is_int(v) and v >= 1) or (isinstance(v, float) and 0 < v <= 1),
                                 "{top: count or fraction}", "a whole number from 1 or a fraction above 0 up to 1")


def _rule_origin(show: CompiledShow, name: str) -> tuple[str, int]:
    """Where a finding about the rule itself points: its line in show.yml (`rules`, else `advice`)."""
    line = show.rule_lines.get(("rules", name)) or show.rule_lines.get(("advice", name)) or 0
    return f"{show.folder.rstrip('/')}/show.yml", line


def _at_rule(show: CompiledShow, name: str, message: str) -> ShowFinding:
    path, line = _rule_origin(show, name)
    return ShowFinding(path, line, RULE_ID, f"{name}: {message}")


def _unknown_light(analysis) -> bool:
    """True when no leg bar of the night has a known light (the autoscript plays everywhere)."""
    return not any(te.at("light", b) is not None
                   for te, tc in zip(analysis.energy, analysis.clock.tracks) for b in range(tc.leg[0], tc.leg[1] + 1))


def _percent(share: float) -> str:
    return f"{round(share * 100)}%"


def _clock(seconds: float) -> str:
    whole = round(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


@show_rule("signatures", params="true", check=_check_signatures)
def signatures(show: CompiledShow, params: object) -> list[ShowFinding]:
    """The night keeps the identity it declared.

    A signature of `identity:` whose measured time share (`show_analysis.identity`) is below its
    `share.min` or above its `share.max`. The finding points at the signature's line in
    show.yml. With no declared signature, or no known light on any bar, it says it cannot check."""
    from show_analysis import analyse

    analysis = analyse(show)
    if not analysis.identity.signatures:
        return [_at_rule(show, "signatures", "cannot check: the show declares no identity signatures")]
    if _unknown_light(analysis):
        return [_at_rule(show, "signatures", "cannot check: no light is known on any bar of the night")]
    path = f"{show.folder.rstrip('/')}/show.yml"
    out = []
    for check in analysis.identity.signatures:
        if check.ok:
            continue
        low = check.min is not None and check.share < check.min
        bound = f"min {_percent(check.min)}" if low else f"max {_percent(check.max)}"
        out.append(ShowFinding(path, show.rule_lines.get(("identity", check.name), 0), RULE_ID,
                               f"signatures: {check.name} holds {_percent(check.share)} of the night, {bound}"))
    return out


@show_rule("static-run", params="{max_seconds: 30-600}", check=_check_static_run)
def static_run(show: CompiledShow, params: dict) -> list[ShowFinding]:
    """No run of one identical light lasts longer than `max_seconds`.

    A run of consecutive leg bars with the same light signature (`show_analysis.variety`'s
    `static_runs`, the five longest; a run may cross a leg) lasts more than `max_seconds`. The
    finding points at the run's first section, and names the map's section kinds under it. With
    no known light it says it cannot check."""
    from show_analysis import analyse
    from show_energy import _section_at

    analysis = analyse(show)
    if _unknown_light(analysis):
        return [_at_rule(show, "static-run", "cannot check: no light is known on any bar of the night")]
    out = []
    for run in analysis.variety.static_runs:
        if run.seconds <= params["max_seconds"]:
            continue
        track = show.tracks[run.index]
        section = _section_at(track, run.bars[0])
        origin = section.origin if section is not None else None
        music = f" (music: {run.music.replace('+', ', ')})" if run.music else ""
        message = (f"static-run: {_title(run.track)} {run.bars[0]}-{run.bars[1]} holds one light for "
                   f"{_clock(run.seconds)}, max {_clock(params['max_seconds'])}{music}")
        out.append(_finding(origin, message) if origin is not None else _at_rule(show, "static-run", message[11:]))
    return out


@show_rule("neighbours-differ", params="{max_similarity: 0-1}", check=_check_neighbours)
def neighbours_differ(show: CompiledShow, params: dict) -> list[ShowFinding]:
    """Two consecutive tracks do not look alike.

    The cosine similarity of two consecutive tracks' vectors of time shares over every
    `(dimension, value)` pair (`show_analysis.variety`'s `similarity`) is above `max_similarity`.
    The finding points at the second track's arrival section, else its first section. With no
    pair of tracks that both have a known light it says it cannot check."""
    from show_analysis import analyse

    pairs = analyse(show).variety.similarity
    if not pairs:
        return [_at_rule(show, "neighbours-differ",
                         "cannot check: fewer than two consecutive tracks have a known light")]
    out = []
    for i, cosine in pairs:
        if cosine <= params["max_similarity"]:
            continue
        first, second = show.tracks[i], show.tracks[i + 1]
        sections = [s for s in second.sections if s.origin.kind != "echo"]
        section = next((s for s in sections if s.origin.role == "arrival"), sections[0] if sections else None)
        message = (f"neighbours-differ: {_title(second.track)} looks like {_title(first.track)} "
                   f"(similarity {cosine:.2f}, max {params['max_similarity']:g})")
        out.append(_finding(section.origin, message) if section is not None
                   else _at_rule(show, "neighbours-differ", message[19:]))
    return out


@show_rule("distinct-drops", params="{top: count or fraction}", check=_check_distinct)
def distinct_drops(show: CompiledShow, params: dict) -> list[ShowFinding]:
    """The top drops do not repeat the same light.

    Take the `top` drops by salience (`show_analysis.top`: a count, or a fraction of the night's
    drops), order them by the set clock, and compare each with the next: two with the same
    template (the signatures just before and at the drop) are a finding at the later drop's
    holder section. A drop whose light is unknown (no template) is skipped. With no drops it
    says it cannot check."""
    from show_analysis import analyse, top

    rows = analyse(show).drops
    if not rows:
        return [_at_rule(show, "distinct-drops", "cannot check: the night has no drops")]
    chosen = sorted(top(rows, params["top"]), key=lambda d: d.clock_s)
    out = []
    for before, after in zip(chosen, chosen[1:]):
        if None in before.template or None in after.template or before.template != after.template:
            continue
        message = (f"distinct-drops: {_title(after.track)} {after.bar} (top drop {after.rank}) repeats the light "
                   f"of {_title(before.track)} {before.bar} (top drop {before.rank})")
        out.append(_finding(after.holder.origin, message) if after.holder is not None
                   else _at_rule(show, "distinct-drops", message[16:]))
    return out


@show_rule("phrase-aligned", params="{min_share: 0-1}", check=_check_phrase)
def phrase_aligned(show: CompiledShow, params: dict) -> list[ShowFinding]:
    """The light changes on the phrase lines.

    Among the leg bars where the light changes (`X(b) > 0`), the share on a phrase line (the
    start of a map section, or a multiple of 4 bars after it; `show_analysis.off_phrase_bars`)
    is below `min_share`. The finding points at the rule's line in show.yml and lists the first
    five bars off the lines. With no change at all it says it cannot check."""
    from show_analysis import analyse, off_phrase_bars

    analysis = analyse(show)
    changed, off = off_phrase_bars(show, analysis.clock, analysis.energy)
    if not changed:
        return [_at_rule(show, "phrase-aligned", "cannot check: the light never changes on a known bar")]
    share = (changed - len(off)) / changed
    if share >= params["min_share"] - 1e-9:
        return []
    listed = ", ".join(f"{_title(show.tracks[i].track)} {b}" for i, b in off[:5])
    more = f", and {len(off) - 5} more" if len(off) > 5 else ""
    return [_at_rule(show, "phrase-aligned", f"{_percent(share)} of the light's changes are on phrase lines, "
                                             f"min {_percent(params['min_share'])}; off the lines: {listed}{more}")]


# --------------------------------------------------------------- the entry --


def rule_param_findings(source: ShowSource) -> list[ShowFinding]:
    """`show-source` findings for the `rules:` and the `advice:` of `show.yml`: an unknown rule
    id, a rule's bad parameters, a budget `from` that names none of the show's track files. Each
    message starts with `rules.<id>:` or `advice.<id>:`. They point at the rule's own mapping
    line, or at `rules:` (`advice:`) when the rule has no mapping."""
    data = source.show
    if not isinstance(data, dict) or source.parse_failed:
        return []
    path = f"{source.folder.rstrip('/')}/show.yml"
    show = clean(data)
    tracks = [d["track"] for d in source.track_files.values()
              if isinstance(d, dict) and isinstance(d.get("track"), str)]
    out = []
    for key in _KEYS:
        rules = data.get(key)
        if not isinstance(rules, dict):
            continue                      # problems_show reports one that is not a mapping
        for name, params in rules.items():
            if name == "__line__":
                continue
            line = _line(params) or _line(rules)
            if name not in RULES:
                known = ", ".join(sorted(RULES))
                out.append(ShowFinding(path, line, SOURCE, f"{key}.{name}: unknown rule {name!r}; rules: {known}"
                                                           f"{_hint(str(name), list(RULES))}"))
                continue
            problems = RULES[name].check(clean(params), show)
            if name == "budget":
                problems += _budget_from_problems(clean(params), tracks)
            out += [ShowFinding(path, line, SOURCE, f"{key}.{name}: {p}") for p in problems]
    return out


def run_rules(show: CompiledShow, key: str = "rules") -> list[ShowFinding]:
    """The findings of the rules that `show.yml` names under `key`, in its order, each in track
    order: `show-rules` findings for `rules`, `show-advice` (`ADVICE`) findings for `advice`. A
    rule whose parameters fail its check is skipped (`rule_param_findings` says why)."""
    rules = show.data.get(key) if isinstance(show.data, dict) else None
    if not isinstance(rules, dict):
        return []
    out = []
    for name, params in rules.items():
        rule = RULES.get(name)
        if rule is None or rule.check(params, show.data):
            continue
        out += rule.fn(show, params)
    rule_id = _KEYS[key]
    return [f if f.rule == rule_id else dataclasses.replace(f, rule=rule_id) for f in out]


def evaluate_show(source: ShowSource, inputs: ShowInputs) -> tuple[CompiledShow | None, list[ShowFinding],
                                                                    list[ShowFinding], list[ShowFinding]]:
    """Compile a show and run its rules and its advice: `(compiled, source findings, rule
    findings, advice findings)`, each list sorted by path, line and message. With any source
    finding (the compiler's, or the parameters of a rule or an advice), `compiled` is None and
    nothing runs. `check_repo.py` and `nextrack_show.py` both call this one entry; only the CLI
    shows the advice."""
    compiled, found = compile_show(source, inputs)
    found = found + rule_param_findings(source)
    if found or compiled is None:
        return None, _sorted(found), [], []
    return compiled, [], _sorted(run_rules(compiled)), _sorted(run_rules(compiled, "advice"))
