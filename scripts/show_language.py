"""show_language.py — the show language: anchors, schema checks, looks and the compiler.

A show (`lightshows/shows/<name>/`) is a `show.yml` plus one cue list per track. This module
resolves an anchor (`drop.2 - 1`, `B`, `end`) to a bar of a musical map, holds the pure
`problems_*` schema checks of `show.yml` and of a track file, the look algebra (`extends`,
`with` overrides, palette colours), and `compile_show`, which turns a show, its maps and the
set's track order into one choreography per track. The checks take parsed YAML (possibly with
the loader's `__line__` keys) and return `(line, message)` items; nothing here raises on bad
content or reads a file. See docs/superpowers/specs/2026-11-06-show-language-design.md.

Python API: `clean`, `layer_word`, `resolve_anchor`, `problems_show`, `problems_track_file`,
`merge_layers`, `flatten_looks`, `expand_look`, `resolve_colours`, `compile_show` and its
types `ShowSource`, `ShowInputs`, `ShowFinding`, `CompiledShow`, `CompiledTrack`,
`CompiledSection`, `Provenance`, and the emitter `emit_choreography`, `owner_of`, `LAYER_KEYS`;
`BRIDGE_BARS`, the bounds of `bridge.bars`.
"""
from __future__ import annotations

import copy
import difflib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import PurePosixPath, PureWindowsPath

import yaml

import lightshow
from lightshow import COLOUR_RE, LAYERS, problems_choreography
from musical_map import slug
from show_gestures import GESTURES, GestureContext, run_gesture

SHOW_VERSION = 1
BRIDGE_BARS = (1, 32)        # the bounds of `bridge.bars`, the mix window, in bars
SECTION_KINDS = ("intro", "groove", "break", "build", "drop", "outro")
ACCENTS = ("white", "strobe", "strobe-roll")
ROLES = ("arrival",)
ID_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
COLOUR_LAYERS = ("movers", "matrix", "hue")

_ANCHOR_RE = re.compile(
    r"\s*(?:(?P<n>[0-9]+)|(?P<hot>[A-H])|(?P<kind>" + "|".join(SECTION_KINDS) + r")"
    r"\.(?P<i>[1-9][0-9]*)(?P<end>\.end)?|(?P<last>end))"
    r"(?:\s*(?P<sign>[+-])\s*(?P<d>[0-9]+))?\s*"
)
_FORMS = "a bar number, a hot cue A-H, <kind>.<i>, <kind>.<i>.end or end, plus or minus a number"
_BEAT_RE = re.compile(r"([0-9]+)\.([0-9]+)")


def clean(value: object) -> object:
    """A deep copy of parsed YAML without the loader's `__line__` keys."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if k != "__line__"}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return copy.deepcopy(value)


def layer_word(value: object) -> object:
    """YAML 1.1 reads an unquoted `off` / `on` as False / True: give the words back."""
    if value is False:
        return "off"
    if value is True:
        return "on"
    return value


def _listing(items) -> str:
    return ", ".join(str(i) for i in items) or "none"


def resolve_anchor(value: object, map_data: dict, *, until: bool = False) -> tuple[int | None, str | None]:
    """Resolve an anchor to a bar of the map: `(bar, None)` or `(None, problem)`. With
    `until`, the bar may also be `bars + 1`."""
    bad = f"anchor {value!r} is not {_FORMS}"
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None, bad
    m = _ANCHOR_RE.fullmatch(str(value))
    if not m:
        return None, bad
    bars = map_data["bars"]
    if m["n"] is not None:
        bar = int(m["n"])
    elif m["hot"] is not None:
        cues = map_data.get("hot_cues") or {}
        name = m["hot"]
        if not isinstance(cues, dict):
            return None, f"{name}: the map's hot_cues is not a mapping"
        if name not in cues:
            return None, f"{name}: the map has no hot cue {name} (it has {_listing(sorted(cues))})"
        where = _BEAT_RE.fullmatch(str(cues[name]))
        if not where or where[2] != "1":
            return None, f"{name}: hot cue {name} ({cues[name]}) is not on a bar's first beat"
        bar = int(where[1])
    elif m["last"] is not None:
        bar = bars
    else:
        kind, i = m["kind"], int(m["i"])
        found = [s["bars"] for s in map_data["sections"] if s["kind"] == kind]
        if not 1 <= i <= len(found):
            return None, (f"{kind}.{i}: the map has {len(found)} {kind} sections "
                          f"({_listing(b[0] for b in found)})" if found
                          else f"{kind}.{i}: the map has no {kind} section")
        bar = found[i - 1][1] if m["end"] else found[i - 1][0]
    if m["sign"]:
        bar += int(m["d"]) if m["sign"] == "+" else -int(m["d"])
    top = bars + 1 if until else bars
    if not 1 <= bar <= top:
        return None, f"{str(value).strip()}: bar {bar} is outside 1-{top}"
    return bar, None


# ------------------------------------------------------------------ schema --


def _line(node: object) -> int:
    return node.get("__line__", 0) if isinstance(node, dict) else 0


def _keys(node: dict) -> list:
    return [k for k in node if k != "__line__"]


def _is_id(value: object) -> bool:
    return isinstance(value, str) and ID_RE.fullmatch(value) is not None


def _repo_relative(path: str) -> bool:
    """Neither absolute (`/x`, `\\x`, `C:...`) nor climbing out with a `..` part."""
    posix = PurePosixPath(path.replace("\\", "/"))
    return not (posix.is_absolute() or PureWindowsPath(path).drive or ".." in posix.parts)


def _check_keys(node: dict, required: tuple, optional: tuple, where: str) -> list[tuple[int, str]]:
    out = [(_line(node), f"{where}: missing key {k}") for k in required if k not in node]
    allowed = required + optional
    out += [(_line(node), f"{where}: unexpected key {k!r} (allowed: {', '.join(allowed)})")
            for k in _keys(node) if k not in allowed]
    return out


def _check_naming(node: dict, where: str) -> list[tuple[int, str]]:
    """`name` (an id) and `intent` (a string) of a bridge or handover mapping."""
    out = []
    if "name" in node and not _is_id(node["name"]):
        out.append((_line(node), f"{where}.name {node['name']!r} is not a kebab-case id"))
    if "intent" in node and not isinstance(node["intent"], str):
        out.append((_line(node), f"{where}.intent {node['intent']!r} is not a string"))
    return out


def problems_show(data: object) -> list[tuple[int, str]]:
    """Schema of `show.yml` alone: `(line, message)` items, line 0 when unknown."""
    if not isinstance(data, dict):
        return [(0, "show.yml is not a mapping")]
    out = _check_keys(data, ("show_version", "set", "story", "palette"),
                      ("plan", "looks", "gesture_defaults", "bridge", "handover", "rules", "advice"), "show.yml")
    version = data.get("show_version")
    if "show_version" in data and (version != SHOW_VERSION or isinstance(version, bool)):
        out.append((_line(data), f"show_version {version!r} is not {SHOW_VERSION}"))
    for key, example in (("set", "sets/<name>.md"), ("plan", "lightshows/sets/<name>.md")):
        if key in data and not (isinstance(data[key], str) and data[key].strip()):
            out.append((_line(data), f"{key} {data[key]!r} is not a path string"))
        elif key in data and not _repo_relative(data[key]):
            out.append((_line(data), f"{key} {data[key]!r} must be a repo-relative path such as {example}"))
    if "story" in data and not (isinstance(data["story"], str) and data["story"].strip()):
        out.append((_line(data), f"story {data['story']!r} is not a non-empty string"))
    if "palette" in data:
        out += _palette(data["palette"])
    if "looks" in data:
        out += _looks(data["looks"])
    if "gesture_defaults" in data:
        out += _gesture_defaults(data["gesture_defaults"])
    if "bridge" in data:
        bridge = data["bridge"]
        out += _naming_block(bridge, "bridge", ("bars",))
        low, high = BRIDGE_BARS
        bars = bridge.get("bars") if isinstance(bridge, dict) else None
        if (isinstance(bridge, dict) and "bars" in bridge
                and not (isinstance(bars, int) and not isinstance(bars, bool) and low <= bars <= high)):
            out.append((_line(bridge), f"bridge.bars {bars!r} is not a whole number of bars from {low} to {high}"))
    if "handover" in data:
        out += _naming_block(data["handover"], "handover")
    for key in ("rules", "advice"):
        if key in data and not isinstance(data[key], dict):
            out.append((_line(data), f"{key} {data[key]!r} is not a mapping"))
    return out


def _palette(palette: object) -> list[tuple[int, str]]:
    if not isinstance(palette, dict):
        return [(0, f"palette {palette!r} is not a mapping")]
    out = []
    for name in _keys(palette):
        if not _is_id(name):
            out.append((_line(palette), f"palette name {name!r} is not a kebab-case id"))
        value = palette[name]
        if not (isinstance(value, str) and COLOUR_RE.fullmatch(value)):
            out.append((_line(palette), f"palette.{name} {value!r} is not #RRGGBB"))
    return out


def _looks(looks: object) -> list[tuple[int, str]]:
    if not isinstance(looks, dict):
        return [(0, f"looks {looks!r} is not a mapping")]
    out = []
    for name in _keys(looks):
        look = looks[name]
        if not _is_id(name):
            out.append((_line(looks), f"look name {name!r} is not a kebab-case id"))
        if not isinstance(look, dict):
            out.append((_line(looks), f"looks.{name} {look!r} is not a mapping of layers"))
            continue
        for key in _keys(look):
            if key == "extends":
                if not isinstance(look[key], str):
                    out.append((_line(look), f"looks.{name}.extends {look[key]!r} is not a look name"))
            elif key not in LAYERS:
                out.append((_line(look),
                            f"looks.{name}: {key!r} is not a layer ({', '.join(LAYERS)}) nor extends"))
    return out


def _gesture_defaults(defaults: object) -> list[tuple[int, str]]:
    if not isinstance(defaults, dict):
        return [(0, f"gesture_defaults {defaults!r} is not a mapping")]
    return [(_line(defaults), f"gesture_defaults.{name} {defaults[name]!r} is not a mapping")
            for name in _keys(defaults) if not isinstance(defaults[name], dict)]


def _naming_block(node: object, where: str, optional: tuple = ()) -> list[tuple[int, str]]:
    if not isinstance(node, dict):
        return [(0, f"{where} {node!r} is not a mapping")]
    out = _check_keys(node, ("name", "intent"), optional, where) + _check_naming(node, where)
    if isinstance(node.get("intent"), str) and not node["intent"].strip():
        out.append((_line(node), f"{where}.intent is empty"))
    return out


def _anchor_type(node: dict, key: str, where: str) -> list[tuple[int, str]]:
    value = node[key]
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return [(_line(node), f"{where}.{key} {value!r} is not an anchor (a bar number or a string)")]
    return []


def _extras(node: dict, where: str) -> list[tuple[int, str]]:
    """The checks that cues and the handover share: with, moment, accents."""
    out = []
    if "with" in node and not isinstance(node["with"], dict):
        out.append((_line(node), f"{where}.with {node['with']!r} is not a mapping"))
    if "moment" in node and not _is_id(node["moment"]):
        out.append((_line(node), f"{where}.moment {node['moment']!r} is not a kebab-case id"))
    if "accents" in node:
        accents = node["accents"]
        if not isinstance(accents, list):
            out.append((_line(node), f"{where}.accents {accents!r} is not a list"))
        else:
            out += [(_line(node), f"{where}.accents {a!r} is not one of {', '.join(ACCENTS)}")
                    for a in accents if a not in ACCENTS]
    return out


def problems_track_file(data: object) -> list[tuple[int, str]]:
    """Schema of one track file: `(line, message)` items, line 0 when unknown."""
    if not isinstance(data, dict):
        return [(0, "track file is not a mapping")]
    out = _check_keys(data, ("track", "story", "cues"), ("budget", "handover", "bridge"), "track file")
    if "track" in data and not (isinstance(data["track"], str) and " — " in data["track"]):
        out.append((_line(data), f"track {data['track']!r} is not 'Artist — Title'"))
    for key in ("story", "budget"):
        if key in data and not isinstance(data[key], str):
            out.append((_line(data), f"{key} {data[key]!r} is not a string"))
    if "bridge" in data and data["bridge"] is not False:
        out.append((_line(data), f"bridge {data['bridge']!r} can only be false"))
    if "cues" in data:
        if not isinstance(data["cues"], list):
            out.append((_line(data), f"cues {data['cues']!r} is not a list"))
        else:
            for n, cue in enumerate(data["cues"], 1):
                out += _cue(cue, n)
    if "handover" in data:
        out += _handover(data["handover"])
    return out


def _cue(cue: object, n: int) -> list[tuple[int, str]]:
    where = f"cues[{n}]"
    if not isinstance(cue, dict):
        return [(0, f"{where} {cue!r} is not a mapping")]
    out = _check_keys(cue, ("at", "name"),
                      ("until", "intent", "look", "gesture", "with", "role", "moment", "accents"), where)
    for key in ("at", "until"):
        if key in cue:
            out += _anchor_type(cue, key, where)
    if "name" in cue and not _is_id(cue["name"]):
        out.append((_line(cue), f"{where}.name {cue['name']!r} is not a kebab-case id"))
    if "intent" in cue and not isinstance(cue["intent"], str):
        out.append((_line(cue), f"{where}.intent {cue['intent']!r} is not a string"))
    if ("look" in cue) == ("gesture" in cue):
        out.append((_line(cue), f"{where}: needs exactly one of look and gesture"))
    if "look" in cue and not isinstance(cue["look"], (str, dict)):
        out.append((_line(cue), f"{where}.look {cue['look']!r} is not a look name or a mapping of layers"))
    if "gesture" in cue and not _is_id(cue["gesture"]):
        out.append((_line(cue), f"{where}.gesture {cue['gesture']!r} is not a gesture name"))
    if "role" in cue and cue["role"] not in ROLES:
        out.append((_line(cue), f"{where}.role {cue['role']!r} is not one of {', '.join(ROLES)}"))
    return out + _extras(cue, where)


def _handover(node: object) -> list[tuple[int, str]]:
    if not isinstance(node, dict):
        return [(0, f"handover {node!r} is not a mapping")]
    out = _check_keys(node, (), ("look", "with", "at", "until", "name", "intent", "moment", "accents"),
                      "handover")
    if "look" not in node:
        out.append((_line(node), "handover: missing key look"))
    elif not isinstance(node["look"], (str, dict)):
        out.append((_line(node), f"handover.look {node['look']!r} is not a look name or a mapping of layers"))
    for key in ("at", "until"):
        if key in node:
            out += _anchor_type(node, key, "handover")
    return out + _check_naming(node, "handover") + _extras(node, "handover")


# ------------------------------------------------------------------- looks --


def merge_layers(base: dict, override: dict) -> dict:
    """Merge per layer: two mappings merge their keys (the override wins, `None` removes a key);
    anything else is replaced by the override, and a `None` layer is removed."""
    out = copy.deepcopy(base)
    for layer, value in override.items():
        if value is None:
            out.pop(layer, None)
        elif isinstance(value, dict):
            merged = out[layer] if isinstance(out.get(layer), dict) else {}
            for key, item in value.items():
                if item is None:
                    merged.pop(key, None)
                else:
                    merged[key] = copy.deepcopy(item)
            out[layer] = merged
        else:
            out[layer] = copy.deepcopy(value)
    return out


def flatten_looks(looks: dict) -> tuple[dict[str, dict], list[tuple[str, str]]]:
    """Every look with its `extends` chain merged in, and `(look name, problem)` for an unknown
    base or a cycle. A look with a problem, or built on one, is left out."""
    flat: dict[str, dict] = {}
    problems: list[tuple[str, str]] = []
    if not isinstance(looks, dict):
        return flat, [("looks", f"looks {looks!r} is not a mapping")]
    looks = clean(looks)

    def build(name: str, chain: list[str]) -> dict | None:
        if name in flat:
            return flat[name]
        raw = looks[name]
        if not isinstance(raw, dict):
            problems.append((name, f"look {raw!r} is not a mapping of layers"))
            return None
        own = {k: v for k, v in raw.items() if k != "extends"}
        base_name = raw.get("extends")
        if base_name is not None and not isinstance(base_name, str):
            problems.append((name, f"extends {base_name!r} is not a look name"))
            return None
        if base_name is None:
            flat[name] = own
            return own
        if base_name in chain:
            cycle = chain[chain.index(base_name):] + [base_name]
            problems.append((base_name, "extends cycle: " + " -> ".join(cycle)))
            return None
        if base_name not in looks:
            problems.append((name, f"extends {base_name!r}, which is not a look"))
            return None
        base = build(base_name, chain + [base_name])
        if base is None:
            return None
        flat[name] = merge_layers(base, own)
        return flat[name]

    for name in looks:
        build(name, [name])
    return flat, problems


def expand_look(ref: object, with_: object, looks: dict[str, dict]) -> tuple[dict | None, list[str]]:
    """The layers of a cue's `look` (a name in `looks`, or a mapping) with `with_` merged on top;
    `layer_word` applied to every top-level layer."""
    if not isinstance(looks, dict):
        return None, [f"looks {looks!r} is not a mapping"]
    if isinstance(ref, str):
        if ref not in looks:
            close = difflib.get_close_matches(ref, list(looks), n=1, cutoff=0.6)
            hint = (f"did you mean {close[0]!r}?" if close
                    else f"defined: {', '.join(sorted(looks)) or 'none'}")
            return None, [f"look {ref!r} is not defined; {hint}"]
        if not isinstance(looks[ref], dict):
            return None, [f"look {ref!r} is not a mapping of layers"]
        layers = clean(looks[ref])
    elif isinstance(ref, dict):
        layers = clean(ref)
        bad = [k for k in layers if k not in LAYERS]
        if bad:
            return None, [f"look has {bad[0]!r}, which is not a layer ({', '.join(LAYERS)})"]
    else:
        return None, [f"look {ref!r} is not a look name or a mapping of layers"]
    if with_ is not None:
        if not isinstance(with_, dict):
            return None, [f"with {with_!r} is not a mapping"]
        bad = [k for k in clean(with_) if k not in LAYERS]
        if bad:
            return None, [f"with has {bad[0]!r}, which is not a layer ({', '.join(LAYERS)})"]
        layers = merge_layers(layers, clean(with_))
    return {k: layer_word(v) for k, v in layers.items()}, []


def resolve_colours(layers: dict, palette: dict[str, str]) -> tuple[dict, list[str]]:
    """Replace palette names in the `colour` of movers, matrix and hue by their `#RRGGBB`."""
    if not isinstance(layers, dict):
        return layers, [f"layers {layers!r} is not a mapping"]
    if not isinstance(palette, dict):
        return layers, [f"palette {palette!r} is not a mapping"]
    out = copy.deepcopy(layers)
    problems = []
    for layer in COLOUR_LAYERS:
        value = out.get(layer)
        if not isinstance(value, dict) or not isinstance(value.get("colour"), str):
            continue
        colour = value["colour"]
        if colour in palette:
            value["colour"] = palette[colour]
        elif not COLOUR_RE.fullmatch(colour):
            problems.append(f"colour {colour!r} is not in the palette ({', '.join(palette)}) nor #RRGGBB")
    return out, problems


# ---------------------------------------------------------------- compiler --

SOURCE = "show-source"
MAPS_DIR = "lightshows/maps"
_SECTION_RE = re.compile(r"section (?P<i>[0-9]+)(?: \([^)]*\))?: (?P<rest>.*)", re.S)
_ACCENT_LAYER = {"white": "white", "strobe": "strobe", "strobe-roll": "strobe"}
_BAR_VALUES = (("movers", "faster_from"), ("white", "accent"), ("strobe", "hit"), ("strobe", "roll"))
# A gesture names a bad parameter value first: `<gesture>: <param>[<i>] <value> is not ...`. A
# problem of the cue's span (`bars add up to ...`) or of several parameters does not match.
_VALUE_PROBLEM_RE = re.compile(r"(?P<gesture>[a-z0-9-]+): (?P<param>[a-z_]+)(?:\[[0-9]+\])? .+? is not ", re.S)


def _strings(value: object) -> set[str]:
    """Every string in parsed YAML."""
    if isinstance(value, str):
        return {value}
    items = value.values() if isinstance(value, dict) else value if isinstance(value, list) else ()
    return set().union(*(_strings(v) for v in items))


def _names_a_colour_of(problem: str, params: dict) -> bool:
    """Whether a `resolve_colours` problem is about a colour written in `params`."""
    return any(problem.startswith(f"colour {s!r} ") for s in _strings(params))


@dataclass
class Provenance:
    """Where a compiled section came from. Rules read it; their findings point at `path:line`."""
    kind: str                 # "cue" | "bridge" | "handover"
    track: str                # Artist — Title of the choreography that holds the section
    look: str | None
    gesture: str | None
    role: str | None          # "arrival" only on the first section of its cue
    moment: str | None
    path: str                 # file a finding points at (for a bridge: the outgoing track's file)
    line: int                 # the cue's or handover's line there


@dataclass
class CompiledSection:
    bars: tuple[int, int]
    name: str
    intent: str | None
    layers: dict[str, object]  # final IR values: colours #RRGGBB, anchors resolved, words normalised
    origin: Provenance


@dataclass
class CompiledTrack:
    track: str
    slug: str
    path: str                  # the track file
    map: dict
    choreography: dict         # track, soundswitch, grid {bpm, downbeat}, story, [budget], base, sections
    sections: list[CompiledSection]


@dataclass
class CompiledShow:
    show_id: str
    folder: str                # e.g. "lightshows/shows/hi-ibiza-pulso"
    data: dict                 # clean(show.yml)
    tracks: list[CompiledTrack]  # set order
    decisions: list[str]       # what the compiler inferred, one line each (bridges, default ends)


@dataclass
class ShowFinding:
    path: str
    line: int
    rule: str                  # "show-source" | "show-rules" | "show-compiled"
    message: str


@dataclass
class ShowSource:
    show_id: str
    folder: str
    show: object               # parsed show.yml (with __line__)
    track_files: dict[str, object]   # file name ("<slug>.yml") -> parsed YAML
    parse_failed: bool = False


@dataclass
class ShowInputs:
    maps: dict[str, dict]              # slug -> valid map
    set_tracks: list[tuple[str, str]] | None   # (artist, title) in set order
    set_problem: str | None            # why set_tracks is None
    same_track: Callable[[str, str, str, str], bool]
    invalid_maps: set[str] = field(default_factory=set)   # slugs of maps that exist but fail their check


@dataclass
class _Show:
    """What every track reads from a valid `show.yml`."""
    folder: str
    palette: dict
    looks: dict                # flattened: `extends` merged in
    bridge: dict | None        # {name, intent}; None: no bridges
    handover: dict             # the default {name, intent} of a handover, or {}
    defaults: dict             # gesture name -> parameters
    default_lines: dict = field(default_factory=dict)   # gesture name -> its line in show.yml


@dataclass
class _Prev:
    """The previous track in set order, as the next track's bridge sees it."""
    title: str
    has_handover: bool
    layers: dict | None = None         # its handover's resolved layers without the accents
    origin: Provenance | None = None   # its handover's provenance


@dataclass
class _Part:
    """A section being built: `label` names its cue in findings, `accented` the layers its
    accents added (the bridge leaves them out). For a gesture's section, `defaults` holds the
    parameters that came only from `gesture_defaults` and `own` the cue's `with`."""
    bars: tuple[int, int]
    name: str
    intent: str | None
    layers: dict
    origin: Provenance
    label: str
    accented: set = field(default_factory=set)
    defaults: dict = field(default_factory=dict)
    own: dict = field(default_factory=dict)


def _title(track: str) -> str:
    return track.split(" — ", 1)[1] if " — " in track else track


def _cue_label(cue: dict) -> str:
    return f"cue {cue['name']!r}"


def _shown(bar: int, raw: object) -> str:
    """A resolved bar, plus the anchor it came from when that is not the bar itself."""
    if isinstance(raw, int) and not isinstance(raw, bool):
        return str(bar)
    return f"{bar} ({str(raw).strip()})"


def _ordered(layers: dict) -> dict:
    """Layers in the vocabulary's order (anything else after, for the validator to name), with
    the YAML 1.1 words given back."""
    out = {k: layer_word(layers[k]) for k in LAYERS if k in layers}
    out.update((k, layer_word(v)) for k, v in layers.items() if k not in out)
    return out


def _section_dict(part: _Part) -> dict:
    out = {"bars": list(part.bars), "name": part.name}
    if part.intent is not None:
        out["intent"] = part.intent
    out.update(copy.deepcopy(part.layers))
    return out


class _TrackCompiler:
    """One track file against its map, steps 1-7 of the spec's "Compiling". `run` returns the
    compiled track, or None with the reasons in `findings`. Each step runs only when the ones
    before it found nothing, so one mistake is reported once."""

    def __init__(self, show: _Show, name: str, data: dict, map_key: str, map_data: dict, prev: _Prev | None):
        self.show, self.data, self.map, self.prev = show, data, map_data, prev
        self.name, self.map_key = name, map_key
        self.path = f"{show.folder}/{name}"
        self.track = map_data["track"]
        self.title = _title(self.track)
        self.cues: list[dict] = data["cues"]
        self.handover: dict | None = data.get("handover")
        self.window: int | None = (show.bridge or {}).get("bars")   # bridge.bars: the mix window, or None
        self.findings: list[ShowFinding] = []
        self.decisions: list[str] = []
        self.parts: list[_Part] = []
        self.groups: list[tuple[dict, list[_Part]]] = []   # each cue (and the handover) and its sections
        self.h_start = self.h_until = self.h_span = self.bridge_span = None
        self.handover_part: _Part | None = None
        self.resolved = False

    def find(self, line: int, message: str, path: str | None = None) -> None:
        finding = ShowFinding(path or self.path, line, SOURCE, message)
        if finding not in self.findings:
            self.findings.append(finding)

    def run(self) -> CompiledTrack | None:
        if self.data["track"] != self.track:
            self.find(_line(self.data), f"track {self.data['track']!r} is not written as in its map: "
                                        f"write {self.track!r} ({MAPS_DIR}/{self.map_key}.yml)")
        for step in (self._anchors, self._spans, self._expand, self._accents, self._resolve):
            before = len(self.findings)
            step()
            if len(self.findings) > before:
                return None
        self.resolved = True
        choreography = self._choreography()
        self._validate(choreography)
        if self.findings:
            return None
        self._decide()
        sections = [CompiledSection(p.bars, p.name, p.intent, p.layers, p.origin) for p in self.parts]
        return CompiledTrack(self.track, self.map_key, self.path, self.map, choreography, sections)

    def next_prev(self) -> _Prev:
        """What the next track's bridge reads of this one."""
        part = self.handover_part
        if part is None or not self.resolved:
            return _Prev(self.title, self.handover is not None)
        layers = {k: copy.deepcopy(v) for k, v in part.layers.items() if k not in part.accented}
        return _Prev(self.title, True, layers, part.origin)

    # step 1
    def _anchor(self, node: dict, key: str, label: str, *, until: bool = False) -> int | None:
        bar, problem = resolve_anchor(node[key], self.map, until=until)
        if problem:
            self.find(_line(node), f"{label}: {problem}")
        return bar

    def _anchors(self) -> None:
        """Every `at` and `until` to a bar (an `until` may be bars + 1); the handover's `at`
        defaults to G and its `until` to bars + 1, or with `bridge.bars` to `at + bars` (at most
        bars + 1): the handover is the outgoing side of the mix window."""
        self.starts = [self._anchor(c, "at", _cue_label(c)) for c in self.cues]
        self.untils = [self._anchor(c, "until", f"{_cue_label(c)}: until", until=True) if "until" in c else None
                       for c in self.cues]
        h = self.handover
        if h is None:
            return
        if "at" in h:
            self.h_start = self._anchor(h, "at", "handover")
        else:
            self.h_start, problem = resolve_anchor("G", self.map)
            if problem:
                self.find(_line(h), f"handover: {problem}; a handover starts at G unless it has an at")
        if "until" in h:
            self.h_until = self._anchor(h, "until", "handover: until", until=True)
        elif self.window is not None and self.h_start is not None:
            self.h_until = min(self.h_start + self.window, self.map["bars"] + 1)
        else:
            self.h_until = self.map["bars"] + 1

    # step 2
    def _spans(self) -> None:
        """A cue runs to the bar before the next start, or to `until - 1`; the last one to the
        bar before the handover, or to the map's end. The handover runs from its `at`, and with
        `bridge.bars` an `until` past `at + bars` is a finding at the handover."""
        cues, starts, untils, h = self.cues, self.starts, self.untils, self.handover
        for i in range(1, len(cues)):
            if starts[i] <= starts[i - 1]:
                self.find(_line(cues[i]), f"{_cue_label(cues[i])} at {_shown(starts[i], cues[i]['at'])} does not "
                          f"come after {_cue_label(cues[i - 1])} at {_shown(starts[i - 1], cues[i - 1]['at'])}")
        if h is not None and cues and self.h_start <= starts[-1]:
            self.find(_line(h), f"handover at {_shown(self.h_start, h.get('at', 'G'))} does not come after "
                      f"{_cue_label(cues[-1])} at {_shown(starts[-1], cues[-1]['at'])}")
        nexts = [(starts[i + 1], _cue_label(cues[i + 1])) for i in range(len(cues) - 1)]
        nexts.append((self.h_start, "the handover") if h is not None else (self.map["bars"] + 1, "the map's end"))
        self.spans = []
        for cue, start, until, (nxt, what) in zip(cues, starts, untils, nexts):
            if until is not None and until <= start:
                self.find(_line(cue), f"{_cue_label(cue)}: until {_shown(until, cue['until'])} is not after "
                          f"its at {_shown(start, cue['at'])}")
            elif until is not None and until > nxt:
                self.find(_line(cue), f"{_cue_label(cue)}: until {_shown(until, cue['until'])} is after {what} "
                          f"starts at {nxt}; until is the first bar after the cue, so at most {nxt}")
            self.spans.append((start, (nxt if until is None else until) - 1))
        if h is not None:
            if self.h_until <= self.h_start:
                self.find(_line(h), f"handover: until {self.h_until} is not after its at {self.h_start}")
            elif self.window is not None and self.h_until > self.h_start + self.window:
                end = self.h_start + self.window - 1
                self.find(_line(h), f"handover: until {_shown(self.h_until, h['until'])}: the handover ends at bar "
                          f"{end} (bridge.bars {self.window}); write an until at or before bar {end + 1}, or "
                          "leave it out")
            self.h_span = (self.h_start, self.h_until - 1)
        self._bridge_span()

    def _bridge_span(self) -> None:
        """With a bridge in the show and a handover before, this track opens with a bridge from
        B to the bar before its first cue (or its handover, or the map's end). With `bridge.bars`,
        that start must come by `B + bars`: a later one is a finding there (the bridge would end
        at `B + bars - 1` and leave the bars after it to the autoscript)."""
        prev = self.prev
        if self.show.bridge is None or prev is None or not prev.has_handover or self.data.get("bridge") is False:
            return
        b, problem = resolve_anchor("B", self.map)
        if problem:
            self.find(_line(self.data), f"bridge from {prev.title}: {problem}; add hot cue B in rekordbox and "
                      "run uv run scripts/nextrack_map.py cues, or write bridge: false")
            return
        if self.cues:
            node, first, label = self.cues[0], self.starts[0], _cue_label(self.cues[0])
        elif self.handover is not None:
            node, first, label = self.handover, self.h_start, "handover"
        else:
            node, first, label = None, self.map["bars"] + 1, None
        if first <= b:
            self.find(_line(node), f"{label} at {first} is not after hot cue B ({b}): no room for the bridge "
                      f"from {prev.title}; start it after bar {b}, or write bridge: false")
            return
        if self.window is not None and first > b + self.window:
            end = b + self.window - 1
            where = f"{label} at {_shown(first, node.get('at', 'G'))}: " if node is not None else ""
            self.find(_line(node) if node is not None else _line(self.data),
                      f"{where}the bridge ends at bar {end} (bridge.bars {self.window}); start a cue at or before "
                      f"bar {end + 1}")
            return
        self.bridge_span = (b, first - 1)
        self._bar_values_copied()

    def _bar_values_copied(self) -> None:
        """A bar number of the outgoing track means nothing in this one: a handover whose layers
        hold one (not from its `accents:`, which the bridge leaves out) is a finding there."""
        prev = self.prev
        if prev.layers is None:
            return
        values = [f"{layer}.{key} {prev.layers[layer][key]!r}" for layer, key in _BAR_VALUES
                  if isinstance(prev.layers.get(layer), dict) and key in prev.layers[layer]]
        if values:
            them = "it" if len(values) == 1 else "them"
            self.find(prev.origin.line, f"handover: {', '.join(values)} would be copied by the bridge into "
                      f"{self.title}, where the bars of this track mean nothing: move {them} to a cue before "
                      f"the handover, or write bridge: false in {self.name}", path=prev.origin.path)

    # step 3
    def _expand(self) -> None:
        """The bridge's copy, each cue's look or gesture, the handover's look."""
        prev = self.prev
        if self.bridge_span is not None and prev.layers is not None:
            o = prev.origin
            self.parts.append(_Part(self.bridge_span, self.show.bridge["name"], self.show.bridge["intent"],
                                    copy.deepcopy(prev.layers),
                                    Provenance("bridge", self.track, o.look, None, None, o.moment, o.path, o.line),
                                    "bridge"))
        for cue, span in zip(self.cues, self.spans):
            parts = self._gesture(cue, span) if "gesture" in cue else self._look(cue, span, "cue")
            self.groups.append((cue, parts))
            self.parts += parts
        if self.handover is not None:
            parts = self._look(self.handover, self.h_span, "handover")
            self.groups.append((self.handover, parts))
            self.parts += parts
            self.handover_part = parts[0] if parts else None

    def _look(self, node: dict, span: tuple[int, int], kind: str) -> list[_Part]:
        label = _cue_label(node) if kind == "cue" else "handover"
        layers, problems = expand_look(node["look"], node.get("with"), self.show.looks)
        for p in problems:
            self.find(_line(node), f"{label}: {p}")
        name, intent = node.get("name"), node.get("intent")
        if kind == "handover":
            name = node.get("name", self.show.handover.get("name"))
            intent = node.get("intent", self.show.handover.get("intent"))
            if name is None or intent is None:
                self.find(_line(node), "handover: needs a name and an intent, and show.yml has no handover to "
                          "take them from: add handover: {name, intent} to show.yml or write them here")
                return []
        if layers is None:
            return []
        look = node["look"] if isinstance(node["look"], str) else None
        origin = Provenance(kind, self.track, look, None, node.get("role"), node.get("moment"), self.path,
                            _line(node))
        return [_Part(span, name, intent, layers, origin, label)]

    def _gesture(self, cue: dict, span: tuple[int, int]) -> list[_Part]:
        """Run the cue's gesture with the show's `gesture_defaults` under its `with` (the cue wins,
        a null removes a default)."""
        label, name = _cue_label(cue), cue["gesture"]
        own = clean(cue.get("with") or {})
        params = {**self.show.defaults.get(name, {}), **own}
        params = {k: v for k, v in params.items() if v is not None}
        defaults = {k: v for k, v in params.items() if k not in own}
        ctx = GestureContext(span[0], span[1], cue["name"], cue.get("intent"), self.map,
                             lambda ref, with_: expand_look(ref, with_, self.show.looks))
        try:
            sections, problems = run_gesture(name, ctx, params)
        except Exception as exc:  # noqa: BLE001 — a bug in a gesture is a finding, not a crash
            sections, problems = [], [f"gesture {name!r} failed ({exc!r}): a bug in scripts/show_gestures.py"]
        problems = problems + [f"gesture {name!r} returned layers {s.layers!r} for section {s.name!r}, "
                               "not a mapping: a bug in scripts/show_gestures.py"
                               for s in sections if not isinstance(s.layers, dict)]
        for p in problems:
            m = _VALUE_PROBLEM_RE.match(p)
            if m is not None and m["gesture"] == name and m["param"] in defaults:
                self._find_default(name, p)
            else:
                self.find(_line(cue), f"{label}: {p}")
        if problems:
            return []
        return [_Part(tuple(s.bars), s.name, s.intent, clean(s.layers),
                      Provenance("cue", self.track, s.look, name, cue.get("role") if i == 0 else None,
                                 cue.get("moment"), self.path, _line(cue)), label,
                      defaults=defaults, own=own)
                for i, s in enumerate(sections)]

    def _find_default(self, gesture: str, problem: str) -> None:
        """A problem of a parameter only `gesture_defaults` gave: once, at show.yml, for every
        cue that calls the gesture without overriding it."""
        self.find(self.show.default_lines.get(gesture, 0),
                  f"{problem} (from gesture_defaults.{gesture} in show.yml)", path=f"{self.show.folder}/show.yml")

    # step 4
    def _accents(self) -> None:
        """A cue's accents go on its first section: `white` and `strobe` on its first beat,
        `strobe-roll` over the whole section."""
        for node, parts in self.groups:
            if not parts:
                continue
            first = parts[0]
            a, b = first.bars
            for accent in node.get("accents") or []:
                layer = _ACCENT_LAYER[accent]
                if layer in first.layers:
                    by = "an earlier accent" if layer in first.accented else "its look"
                    self.find(first.origin.line, f"{first.label}: accent {accent!r} sets {layer} on bar {a}, "
                              f"which {by} already sets; remove the accent or that layer")
                    continue
                first.layers[layer] = ({"accent": [f"{a}.1"]} if accent == "white"
                                       else {"hit": [f"{a}.1"]} if accent == "strobe" else {"roll": [a, b]})
                first.accented.add(layer)

    # step 5
    def _resolve(self) -> None:
        """Palette names to `#RRGGBB` and `faster_from` anchors to bars."""
        for part in self.parts:
            if part.origin.kind == "bridge":
                continue          # a copy of layers the previous track resolved
            layers, problems = resolve_colours(part.layers, self.show.palette)
            movers = layers.get("movers")
            if isinstance(movers, dict) and "faster_from" in movers:
                bar, problem = resolve_anchor(movers["faster_from"], self.map)
                if problem:
                    problems.append(f"faster_from {problem}")
                else:
                    movers["faster_from"] = bar
            for p in problems:
                if _names_a_colour_of(p, part.defaults) and not _names_a_colour_of(p, part.own):
                    self._find_default(part.origin.gesture, p)
                else:
                    self.find(part.origin.line, f"{part.label}: {p}")
            part.layers = _ordered(layers)

    # step 6
    def _choreography(self) -> dict:
        """The low-level choreography, keys in the order of the file."""
        grid = self.map["grid"]
        bpm = grid["bpm"]
        if isinstance(bpm, float) and bpm.is_integer():
            bpm = int(bpm)
        out = {"track": self.track, "soundswitch": self.map["soundswitch"],
               "grid": {"bpm": bpm, "downbeat": grid["downbeat"]}, "story": self.data["story"]}
        if "budget" in self.data:
            out["budget"] = self.data["budget"]
        out["base"] = "autoscript"
        out["sections"] = [_section_dict(p) for p in self.parts]
        return out

    # step 7
    def _validate(self, choreography: dict) -> None:
        """`lightshow`'s own check; a section's problem points at the cue that made it."""
        for message in problems_choreography(choreography, None):
            m = _SECTION_RE.fullmatch(message)
            index = int(m["i"]) - 1 if m is not None else -1
            if not 0 <= index < len(self.parts):   # no section, or one this track does not have
                self.find(_line(self.data), message)
                continue
            part = self.parts[index]
            if part.origin.kind == "bridge":
                continue          # the handover it copies reports the same problem in its own track
            where = part.label + (f" (section {part.name!r})" if part.origin.gesture is not None else "")
            self.find(part.origin.line, f"{where}: {m['rest']}")

    def _decide(self) -> None:
        """What the compiler inferred for this track: its bridge, the end of its last cue, and the
        end of a handover that `bridge.bars` cut before the map's end."""
        if self.parts and self.parts[0].origin.kind == "bridge":
            (a, b), look = self.parts[0].bars, self.parts[0].origin.look
            self.decisions.append(f"{self.title}: bridge {a}-{b} copies the handover of {self.prev.title} "
                                  f"({'look ' + look if look else 'inline'})")
        if self.cues and self.untils[-1] is None:
            until = "the handover" if self.handover is not None else "the map's end"
            self.decisions.append(f"{self.title}: {_cue_label(self.cues[-1])} runs to bar {self.spans[-1][1]} "
                                  f"({until})")
        h = self.handover
        if h is not None and "until" not in h and self.window is not None and self.h_until <= self.map["bars"]:
            self.decisions.append(f"{self.title}: handover runs to bar {self.h_until - 1} (bridge.bars {self.window})")


def _show_context(source: ShowSource, folder: str) -> tuple[_Show | None, list[ShowFinding]]:
    """`show.yml` checked and prepared for the tracks, or None with its findings."""
    data = source.show
    problems = problems_show(data)
    flat: dict[str, dict] = {}
    if not problems:
        looks = data.get("looks", {})
        flat, found = flatten_looks(looks)
        problems = [(_line(looks.get(name)) or _line(looks), f"looks.{name}: {p}") for name, p in found]
        defaults = data.get("gesture_defaults", {})
        problems += _default_keys(defaults)
    if problems:
        return None, [ShowFinding(f"{folder}/show.yml", line, SOURCE, m) for line, m in problems]
    defaults = data.get("gesture_defaults", {})
    lines = {name: _line(defaults[name]) or _line(defaults) for name in _keys(defaults)}
    return _Show(folder, clean(data["palette"]), flat, clean(data.get("bridge")),
                 clean(data.get("handover", {})), clean(defaults), lines), []


def _default_keys(defaults: dict) -> list[tuple[int, str]]:
    """Each `gesture_defaults.<gesture>` names a registered gesture and only its parameters."""
    out = []
    for name in _keys(defaults):
        if name not in GESTURES:
            out.append((_line(defaults), f"gesture_defaults.{name}: unknown gesture {name!r}; "
                                         f"gestures: {', '.join(sorted(GESTURES))}"))
            continue
        params = list(GESTURES[name].params)
        for key in _keys(defaults[name]):
            if key not in params:
                close = difflib.get_close_matches(str(key), params, n=1, cutoff=0.6)
                hint = f"did you mean {close[0]!r}?" if close else f"parameters: {', '.join(params)}"
                out.append((_line(defaults[name]) or _line(defaults),
                            f"gesture_defaults.{name}: unknown parameter {key!r}; {hint}"))
    return out


def _matching_maps(artist: str, title: str, maps: dict[str, dict], same: Callable) -> list[str]:
    """The keys of the maps whose track `same` matches, sorted."""
    out = []
    for name in sorted(maps):
        track = maps[name].get("track")
        if isinstance(track, str) and " — " in track and same(artist, title, *track.split(" — ", 1)):
            out.append(name)
    return out


def _map_key(track: str, maps: dict[str, dict], same: Callable) -> tuple[str | None, list[str]]:
    """The key of a track's map: its slug, or else the one map `same` matches (a set may
    abbreviate a title that the map writes in full). Also every key `same` matches."""
    if slug(track) in maps:
        return slug(track), [slug(track)]
    hits = _matching_maps(*track.split(" — ", 1), maps, same)
    return (hits[0] if len(hits) == 1 else None), hits


def _file_hint(artist: str, title: str, maps: dict[str, dict], same: Callable) -> str:
    hits = _matching_maps(artist, title, maps, same)
    if hits:
        return f": add {hits[0]}.yml with track: {maps[hits[0]]['track']}"
    return ": add one, named <slug>.yml like the track's musical map"


def _match(source: ShowSource, folder: str, files: dict[str, tuple[object, bool]],
           inputs: ShowInputs) -> tuple[list[tuple[str, dict] | None], list[ShowFinding]]:
    """Each set track's one track file, as `(file name, data)` per set position (None when it
    has none, several, or one that fails its schema), plus the findings. `files` maps a file
    name to `(data, schema ok)`."""
    show_path, show_line = f"{folder}/show.yml", _line(source.show)
    set_tracks, same = inputs.set_tracks, inputs.same_track
    out = []

    def at_show(message: str) -> None:
        out.append(ShowFinding(show_path, show_line, SOURCE, message))

    again: dict[int, int] = {}            # set position -> the earlier position of the same track
    for j, (artist, title) in enumerate(set_tracks):
        first = next((i for i in range(j) if i not in again and same(*set_tracks[i], artist, title)), None)
        if first is not None:
            again[j] = first
            at_show(f"set track {j + 1}, {artist} — {title}, is set track {first + 1} again: a track has one "
                    "choreography; play it once in the set")
    claims: dict[int, list[str]] = {}
    unreadable = False                    # a file without a readable track may be the missing one
    for name, (data, _) in files.items():
        track = data.get("track") if isinstance(data, dict) else None
        if not (isinstance(track, str) and " — " in track):
            unreadable = True
            continue
        path, line = f"{folder}/{name}", _line(data)
        key, map_hits = _map_key(track, inputs.maps, same)
        expected = f"{key or slug(track)}.yml"
        # never onto a file that exists (two files for one track: that finding says it), and not
        # when several maps match (that finding says it)
        if name != expected and expected not in files and not (key is None and map_hits):
            out.append(ShowFinding(path, line, SOURCE,
                                   f"file name {name!r} does not match its track {track!r}: rename it to {expected}"))
        hits = [i for i, (a, t) in enumerate(set_tracks) if i not in again and same(a, t, *track.split(" — ", 1))]
        if not hits:
            close = difflib.get_close_matches(track, [f"{a} — {t}" for a, t in set_tracks], n=1, cutoff=0.6)
            hint = f"did you mean {close[0]!r}? Otherwise delete this file" if close else "delete this file"
            out.append(ShowFinding(path, line, SOURCE,
                                   f"track {track!r} is not in the set {source.show.get('set')}: {hint}"))
        elif len(hits) > 1:
            listed = ", ".join(f"{i + 1}. {set_tracks[i][0]} — {set_tracks[i][1]}" for i in hits)
            out.append(ShowFinding(path, line, SOURCE, f"track {track!r} matches {len(hits)} set tracks "
                                                       f"({listed}): write it as its map does"))
        else:
            claims.setdefault(hits[0], []).append(name)
    order: list[tuple[str, dict] | None] = []
    for i, (artist, title) in enumerate(set_tracks):
        names = claims.get(i, [])
        if len(names) > 1:
            at_show(f"set track {i + 1}, {artist} — {title}, has {len(names)} track files "
                    f"({', '.join(names)}): keep one")
        elif not names and i not in again and not unreadable:
            at_show(f"set track {i + 1}, {artist} — {title}, has no track file"
                    + _file_hint(artist, title, inputs.maps, same))
        ok = len(names) == 1 and files[names[0]][1]
        order.append((names[0], files[names[0]][0]) if ok else None)
    return order, out


def _no_map(track: str, hits: list[str], invalid: str | None) -> str:
    """Why a track file has no map: several match, its map fails its check, or there is none."""
    if hits:
        listed = ", ".join(f"{MAPS_DIR}/{k}.yml" for k in hits)
        return f"track {track!r} matches {len(hits)} musical maps ({listed}): write it as one of them does"
    if invalid is not None:
        return (f"{MAPS_DIR}/{invalid}.yml is not a valid map: fix its musical-map finding "
                "(or redo it with uv run scripts/nextrack_map.py analyze)")
    return f"no musical map for {track}: run uv run scripts/nextrack_map.py analyze \"{track}\""


def _compile_tracks(show: _Show, order: list[tuple[str, dict] | None], inputs: ShowInputs,
                    linked: bool) -> tuple[list[CompiledTrack], list[str], list[ShowFinding], list]:
    """Compile the tracks in order. With `linked`, each track sees the one before it (bridges)."""
    tracks, decisions, findings, entries = [], [], [], []
    prev: _Prev | None = None
    for entry in order:
        if entry is None:
            entries.append(None)
            prev = None
            continue
        name, data = entry
        key, hits = _map_key(data["track"], inputs.maps, inputs.same_track)
        map_data = inputs.maps[key] if key is not None else None
        entries.append((name, data, map_data))
        if map_data is None:
            # the file is named like its map, so its stem names an invalid map as well as the slug does
            invalid = next((k for k in (slug(data["track"]), name.removesuffix(".yml"))
                            if k in inputs.invalid_maps), None)
            findings.append(ShowFinding(f"{show.folder}/{name}", _line(data), SOURCE,
                                        _no_map(data["track"], hits, invalid)))
            prev = _Prev(_title(data["track"]), "handover" in data) if linked else None
            continue
        compiler = _TrackCompiler(show, name, data, key, map_data, prev)
        track = compiler.run()
        findings += [f for f in compiler.findings if f not in findings]   # a show.yml finding once
        decisions += compiler.decisions
        if track is not None:
            tracks.append(track)
        prev = compiler.next_prev() if linked else None
    return tracks, decisions, findings, entries


def _missing_handovers(show: _Show, entries: list) -> list[ShowFinding]:
    """A track whose map has G, followed by a track that would take a bridge, needs a handover."""
    if show.bridge is None:
        return []
    out = []
    for here, after in zip(entries, entries[1:]):
        if here is None or after is None or here[2] is None or after[2] is None:
            continue
        (name, data, map_data), (next_name, next_data, next_map) = here, after
        hot = map_data.get("hot_cues")
        if "handover" in data or not (isinstance(hot, dict) and "G" in hot):
            continue
        if next_data.get("bridge") is False or resolve_anchor("B", next_map)[1] is not None:
            continue
        window = show.bridge.get("bars")
        plays = "to the end" if window is None else f"for {window} bars (bridge.bars {window})"
        out.append(ShowFinding(f"{show.folder}/{name}", _line(data), SOURCE,
                               f"the map has hot cue G ({hot['G']}) and the next track, "
                               f"{_title(next_data['track'])}, opens with a bridge: add a handover here (its look "
                               f"plays from G {plays} and the bridge copies it), or write bridge: false in "
                               f"{next_name}"))
    return out


def compile_show(source: ShowSource, inputs: ShowInputs) -> tuple[CompiledShow | None, list[ShowFinding]]:
    """Compile a show into one choreography per set track (spec, "Compiling"). Returns
    `(show, [])`, or `(None, findings)` (all `show-source`) when anything is wrong. Pure: the
    files, the maps and the set's order come in `source` and `inputs`."""
    folder = source.folder.rstrip("/")
    show_path = f"{folder}/show.yml"
    if source.parse_failed:
        return None, [ShowFinding(show_path, 0, SOURCE, "a file of this show does not parse: fix its parse-error")]
    show, findings = _show_context(source, folder)
    files: dict[str, tuple[object, bool]] = {}
    for name in sorted(source.track_files):
        data = source.track_files[name]
        problems = problems_track_file(data)
        findings += [ShowFinding(f"{folder}/{name}", line, SOURCE, m) for line, m in problems]
        files[name] = (data, not problems)
    if show is None:
        return None, findings
    if inputs.set_tracks is None:            # no order: each track alone, no bridges
        findings.append(ShowFinding(show_path, _line(source.show), SOURCE,
                                    inputs.set_problem or "the set's track order could not be read"))
        order, linked = [(name, data) for name, (data, ok) in files.items() if ok], False
    else:
        order, found = _match(source, folder, files, inputs)
        findings += found
        linked = True
    tracks, decisions, found, entries = _compile_tracks(show, order, inputs, linked)
    findings += found
    if linked:
        findings += _missing_handovers(show, entries)
    if findings:
        return None, findings
    return CompiledShow(source.show_id, folder, clean(source.show), tracks, decisions), []


# --- The emitter -----------------------------------------------------------------------------
# One deterministic text per choreography (spec, "The emitted file"): fixed key order, flow-style
# layers, a header naming the show that owns the file.

HEADER_RE = re.compile(r"# Generated by scripts/nextrack_show\.py build from (?P<folder>.+)/\.$")
_PLAIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9 ._-]*")
_YAML_WORDS = frozenset(("y", "n", "yes", "no", "on", "off", "true", "false", "null"))
_FOLD_WIDTH = 96
LAYER_KEYS = {  # the keys of each layer that takes a mapping, in the emitted order
    "movers": lightshow.MOVER_KEYS, "matrix": lightshow.MATRIX_KEYS,
    "hue": ("state", "colour"), "white": ("accent", "flash"), "strobe": ("hit", "roll"),
}


def _quoted(text: str) -> str:
    out = []
    for ch in text:
        if ch in '\\"':
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 0x20 or 0x7F <= ord(ch) < 0xA0 or ch in "  ﻿":
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _scalar(value: object) -> str:
    if value is True or value is False:
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if value is None:
        return "null"
    text = str(value)
    if _PLAIN_RE.fullmatch(text) and text == text.rstrip() and text.lower() not in _YAML_WORDS:
        return text
    return _quoted(text)


def _flow(value: object) -> str:
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {_flow(v)}" for k, v in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_flow(v) for v in value) + "]"
    return _scalar(value)


def _layer(name: str, value: object) -> str:
    if isinstance(value, dict):
        known = LAYER_KEYS.get(name, ())
        keys = [k for k in known if k in value] + sorted(k for k in value if k not in known)
        value = {k: value[k] for k in keys}
    return f"{name}: {_flow(value)}"


def _folded(key: str, text: str) -> str:
    """`key: >-` folded at 96 columns when that parses back to `text`, else a quoted scalar."""
    lines, line = [], ""
    for word in text.split(" "):
        if line and len(line) + 1 + len(word) > _FOLD_WIDTH - 2:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    lines.append(line)
    block = f"{key}: >-\n" + "\n".join(f"  {ln}" for ln in lines)
    try:
        if text and yaml.safe_load(block) == {key: text}:
            return block
    except yaml.YAMLError:
        pass
    return f"{key}: {_quoted(text)}"


def emit_choreography(choreo: dict, folder: str) -> str:
    """The text of one generated choreography, headed by the ownership lines for `folder`."""
    out = [f"# Generated by scripts/nextrack_show.py build from {folder.rstrip('/')}/.",
           "# Do not edit by hand: change the show and run the build again.",
           f"track: {_quoted(choreo['track'])}",
           f"soundswitch: {_scalar(choreo['soundswitch'])}",
           f"grid: {_flow(choreo['grid'])}",
           _folded("story", choreo["story"])]
    if "budget" in choreo:
        out.append(_folded("budget", choreo["budget"]))
    out.append(f"base: {_scalar(choreo['base'])}")
    sections = choreo["sections"]
    out.append("sections:" if sections else "sections: []")
    blocks = []
    for sec in sections:
        lines = [f"  - bars: {_flow(sec['bars'])}", f"    name: {_scalar(sec['name'])}"]
        if "intent" in sec:
            lines.append(f"    intent: {_quoted(sec['intent'])}")
        lines += [f"    {_layer(name, sec[name])}" for name in lightshow.LAYERS if name in sec]
        blocks.append("\n".join(lines))
    return "\n".join(out) + ("\n" + "\n\n".join(blocks) if blocks else "") + "\n"


def owner_of(text: str) -> str | None:
    """The show folder named by the ownership header (first line only), or None."""
    m = HEADER_RE.fullmatch(text.split("\n", 1)[0].rstrip("\r"))
    return m["folder"] if m else None
