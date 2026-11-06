"""show_gestures.py — the gesture registry of the show language.

A gesture is a pure Python function that fills the bars of one cue with sections. It gets a
`GestureContext` (the span, the cue's name and intent, the map and `expand_look`) and its
parameters, validates them, and returns `(sections, problems)`; it never raises on bad input.
`run_gesture` calls one by name and checks the result: sections in order, contiguous, covering
exactly the span. Colours in the sections may still be palette names; the compiler resolves
them. See docs/superpowers/specs/2026-11-06-show-language-design.md ("Gestures").

Python API: `GESTURES`, `gesture`, `run_gesture`, `Gesture`, `GestureContext`, `GestureSection`.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from lightshow import RATE_RE

ID_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
RATE_HINT = "1/16, 1/8, 1/4, 1/2, <n>bar"


@dataclass
class GestureContext:
    start: int          # first bar the gesture fills
    end: int            # last bar (inclusive)
    cue_name: str
    intent: str | None
    map: dict
    expand_look: Callable[[object, object], tuple[dict | None, list[str]]]  # (look ref, with) -> layers, problems


@dataclass
class GestureSection:
    bars: tuple[int, int]
    name: str
    intent: str | None
    layers: dict[str, object]       # colours may still be palette names
    look: str | None = None         # the look name this section came from, for the provenance


@dataclass
class Gesture:
    name: str
    doc: str                        # the function's docstring
    params: dict[str, str]          # parameter -> one-line description (vocab prints it)
    example: dict                   # a valid `with` for the generic test, colours as #RRGGBB
    example_bars: int               # the span the example fills
    fn: Callable[[GestureContext, dict], tuple[list[GestureSection], list[str]]]


GESTURES: dict[str, Gesture] = {}


def gesture(name: str, *, params: dict[str, str], example: dict, example_bars: int):
    """Register the decorated function as the gesture `name`."""
    def register(fn):
        GESTURES[name] = Gesture(name, (fn.__doc__ or "").strip(), params, example, example_bars, fn)
        return fn
    return register


def _strip(value: object) -> object:
    """Parsed YAML without the loader's `__line__` keys."""
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k != "__line__"}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def run_gesture(name: str, ctx: GestureContext, params: object) -> tuple[list[GestureSection], list[str]]:
    """Run the gesture `name` over `ctx`; `([], problems)` when anything is wrong."""
    if name not in GESTURES:
        return [], [f"unknown gesture {name!r}; gestures: {', '.join(sorted(GESTURES))}"]
    g = GESTURES[name]
    params = _strip(params)
    if not isinstance(params, dict):
        return [], [f"{name}: parameters {params!r} are not a mapping"]
    unknown = [k for k in params if k not in g.params]
    if unknown:
        return [], [f"{name}: unknown parameter {unknown[0]!r}; parameters: {', '.join(g.params)}"]
    sections, problems = g.fn(ctx, params)
    if problems:
        return [], problems
    if not _covers(sections, ctx.start, ctx.end):
        return [], [f"gesture {name!r} returned sections that do not cover bars {ctx.start}-{ctx.end}"]
    return sections, []


def _covers(sections: list[GestureSection], start: int, end: int) -> bool:
    expect = start
    for s in sections:
        first, last = s.bars
        if first != expect or last < first:
            return False
        expect = last + 1
    return bool(sections) and expect == end + 1


def _bars_list(name: str, key: str, value: object) -> tuple[list[int], list[str]]:
    if not isinstance(value, list) or not value:
        return [], [f"{name}: {key} {value!r} is not a non-empty list of bar counts"]
    problems = [f"{name}: {key}[{i}] {v!r} is not a whole number of bars (1 or more)"
                for i, v in enumerate(value) if not _is_int(v) or v < 1]
    return ([] if problems else list(value)), problems


def _fill(name: str, ctx: GestureContext, bars: list[int]) -> list[str]:
    span = ctx.end - ctx.start + 1
    if sum(bars) != span:
        return [f"{name}: bars add up to {sum(bars)}, the cue spans {span} bars ({ctx.start}-{ctx.end})"]
    return []


def _spans(ctx: GestureContext, bars: list[int]) -> list[tuple[int, int]]:
    out, first = [], ctx.start
    for n in bars:
        out.append((first, first + n - 1))
        first += n
    return out


@gesture("sequence",
         params={"steps": "list of {bars, look, with?, name?}: one section per step, consecutive; "
                          "bars add up to the cue's span; name defaults to <cue name>-<i> from 1"},
         example={"steps": [{"bars": 1, "look": {"hue": "dark"}},
                            {"bars": 1, "look": {"hue": "pulse", "movers": "off"}, "name": "volta"}]},
         example_bars=2)
def sequence(ctx: GestureContext, params: dict) -> tuple[list[GestureSection], list[str]]:
    """Compose an effect in time from looks, with no new code.

    `steps` is a list of `{bars, look, with?, name?}`. One section per step, consecutive; the
    bars add up to the cue's span. `look` is a look name or a mapping of layers, `with` is
    merged on top. A step's name defaults to `<cue name>-<i>`, counted from 1; a step whose
    `look` is a name reports it as the section's look."""
    steps = params.get("steps")
    if not isinstance(steps, list) or not steps:
        return [], [f"sequence: steps {steps!r} is not a non-empty list of {{bars, look}} mappings"]
    problems, bars = [], []
    layers_of: list[dict | None] = []
    for i, step in enumerate(steps, 1):
        prefix = f"sequence: step {i}: "
        if not isinstance(step, dict):
            problems.append(f"{prefix}{step!r} is not a mapping")
            continue
        extra = [k for k in step if k not in ("bars", "look", "with", "name")]
        if extra:
            problems.append(f"{prefix}unknown key {extra[0]!r}; keys: bars, look, with, name")
        n = step.get("bars")
        if not _is_int(n) or n < 1:
            problems.append(f"{prefix}bars {n!r} is not a whole number of bars (1 or more)")
        else:
            bars.append(n)
        name = step.get("name")
        if name is not None and not (isinstance(name, str) and ID_RE.fullmatch(name)):
            problems.append(f"{prefix}name {name!r} is not an id (lowercase letters and digits joined by '-')")
        if "look" not in step:
            problems.append(f"{prefix}look is missing")
            continue
        layers, found = ctx.expand_look(step["look"], step.get("with"))
        problems += [f"{prefix}{p}" for p in found]
        layers_of.append(layers)
    if problems:
        return [], problems
    problems = _fill("sequence", ctx, bars)
    if problems:
        return [], problems
    sections = []
    for i, ((first, last), step, layers) in enumerate(zip(_spans(ctx, bars), steps, layers_of), 1):
        look = step["look"] if isinstance(step["look"], str) else None
        sections.append(GestureSection((first, last), step.get("name") or f"{ctx.cue_name}-{i}",
                                       ctx.intent, layers or {}, look))
    return sections, []


def _aim(value: object) -> tuple[str, list[str]] | tuple[None, str]:
    """The mover key and value for one aim: a preset name or a list of them."""
    if isinstance(value, str) and value:
        return "position", value
    if isinstance(value, list) and value and all(isinstance(v, str) and v for v in value):
        return "positions", list(value)
    return None, "is not a preset name or a list of them"


@gesture("spiral",
         params={"bars": "bars of each step (whole numbers, adding up to the cue's span)",
                 "rates": f"rate of each step ({RATE_HINT})",
                 "colours": "colour of each step (palette name or #RRGGBB)",
                 "aims": "movers aim of each step: a preset name or a list of them"},
         example={"bars": [1, 1], "rates": ["1/2", "1/4"], "colours": ["#0A2CFF", "#B0001E"],
                  "aims": [["Crossed Over", "Up"], "Dance Floor Centre"]},
         example_bars=2)
def spiral(ctx: GestureContext, params: dict) -> tuple[list[GestureSection], list[str]]:
    """v1 spiral: the two sides take turns, faster step by step, with the centre dark.

    Parameters `bars`, `rates`, `colours` and `aims` are four lists of the same length, one
    entry per step; the bars add up to the cue's span. One section per step: movers
    `pingpong` every <rate> in <colour> aimed at <aim>, matrix `columns` at <rate> in
    <colour> with `pingpong`, hue `dark`. Names are `<cue name>-<rate>` with the slash as a
    dash (`espiral-1-16`)."""
    lists, problems = {}, []
    for key in ("bars", "rates", "colours", "aims"):
        if key not in params:
            problems.append(f"spiral: {key} is missing")
        elif not isinstance(params[key], list) or not params[key]:
            problems.append(f"spiral: {key} {params[key]!r} is not a non-empty list")
        else:
            lists[key] = params[key]
    if problems:
        return [], problems
    sizes = {k: len(v) for k, v in lists.items()}
    if len(set(sizes.values())) > 1:
        return [], ["spiral: bars, rates, colours and aims must have the same length; got "
                    + ", ".join(f"{k} ({n})" for k, n in sizes.items())]
    bars, found = _bars_list("spiral", "bars", lists["bars"])
    problems += found
    for i, rate in enumerate(lists["rates"]):
        if not (isinstance(rate, str) and RATE_RE.fullmatch(rate)):
            problems.append(f"spiral: rates[{i}] {rate!r} is not a rate ({RATE_HINT})")
    for i, colour in enumerate(lists["colours"]):
        if not (isinstance(colour, str) and colour):
            problems.append(f"spiral: colours[{i}] {colour!r} is not a colour name or #RRGGBB")
    aims = []
    for i, value in enumerate(lists["aims"]):
        key, aim = _aim(value)
        if key is None:
            problems.append(f"spiral: aims[{i}] {value!r} {aim}")
        aims.append((key, aim))
    if not problems:
        problems = _fill("spiral", ctx, bars)
    if problems:
        return [], problems
    sections = []
    for (first, last), rate, colour, (key, aim) in zip(_spans(ctx, bars), lists["rates"],
                                                         lists["colours"], aims):
        sections.append(GestureSection((first, last), f"{ctx.cue_name}-{rate.replace('/', '-')}",
                                       ctx.intent,
                                       {"movers": {"move": "pingpong", "every": rate, "colour": colour, key: aim},
                                        "matrix": {"draw": "columns", "rate": rate, "colour": colour,
                                                   "pingpong": True},
                                        "hue": "dark"}))
    return sections, []
