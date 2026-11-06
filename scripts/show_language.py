"""show_language.py — the show language: anchors, schema checks and looks.

A show (`lightshows/shows/<name>/`) is a `show.yml` plus one cue list per track. This module
holds the first layer of it: resolving an anchor (`drop.2 - 1`, `B`, `end`) to a bar of a
musical map, the pure `problems_*` schema checks of `show.yml` and of a track file, and the
look algebra (`extends`, `with` overrides, palette colours). The checks take parsed YAML
(possibly with the loader's `__line__` keys) and return `(line, message)` items; they never
raise on bad content. See docs/superpowers/specs/2026-11-06-show-language-design.md.

Python API: `clean`, `layer_word`, `resolve_anchor`, `problems_show`, `problems_track_file`,
`merge_layers`, `flatten_looks`, `expand_look`, `resolve_colours`.
"""
from __future__ import annotations

import copy
import difflib
import re

from lightshow import COLOUR_RE, LAYERS

SHOW_VERSION = 1
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
                      ("plan", "looks", "gesture_defaults", "bridge", "handover", "rules"), "show.yml")
    version = data.get("show_version")
    if "show_version" in data and (version != SHOW_VERSION or isinstance(version, bool)):
        out.append((_line(data), f"show_version {version!r} is not {SHOW_VERSION}"))
    for key in ("set", "plan"):
        if key in data and not (isinstance(data[key], str) and data[key].strip()):
            out.append((_line(data), f"{key} {data[key]!r} is not a path string"))
    if "story" in data and not (isinstance(data["story"], str) and data["story"].strip()):
        out.append((_line(data), f"story {data['story']!r} is not a non-empty string"))
    if "palette" in data:
        out += _palette(data["palette"])
    if "looks" in data:
        out += _looks(data["looks"])
    if "gesture_defaults" in data:
        out += _gesture_defaults(data["gesture_defaults"])
    for key in ("bridge", "handover"):
        if key in data:
            out += _naming_block(data[key], key)
    if "rules" in data and not isinstance(data["rules"], dict):
        out.append((_line(data), f"rules {data['rules']!r} is not a mapping"))
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


def _naming_block(node: object, where: str) -> list[tuple[int, str]]:
    if not isinstance(node, dict):
        return [(0, f"{where} {node!r} is not a mapping")]
    return _check_keys(node, (), ("name", "intent"), where) + _check_naming(node, where)


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
    looks = clean(looks)
    flat: dict[str, dict] = {}
    problems: list[tuple[str, str]] = []

    def build(name: str, chain: list[str]) -> dict | None:
        if name in flat:
            return flat[name]
        raw = looks[name]
        own = {k: v for k, v in raw.items() if k != "extends"}
        base_name = raw.get("extends")
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
    if isinstance(ref, str):
        if ref not in looks:
            close = difflib.get_close_matches(ref, list(looks), n=1, cutoff=0.6)
            hint = (f"did you mean {close[0]!r}?" if close
                    else f"defined: {', '.join(sorted(looks)) or 'none'}")
            return None, [f"look {ref!r} is not defined; {hint}"]
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
        layers = merge_layers(layers, clean(with_))
    return {k: layer_word(v) for k, v in layers.items()}, []


def resolve_colours(layers: dict, palette: dict[str, str]) -> tuple[dict, list[str]]:
    """Replace palette names in the `colour` of movers, matrix and hue by their `#RRGGBB`."""
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
