"""Anchors, schema checks and looks of the show language."""
import copy

import pytest

from musical_map import problems_map
from show_language import (expand_look, flatten_looks, merge_layers, problems_show,
                           problems_track_file, resolve_anchor, resolve_colours)
from showdata import PALETTE, show_map


def test_show_map_is_a_valid_map():
    assert problems_map(show_map()) == []


def test_anchor_terms():
    m = show_map()
    assert resolve_anchor(16, m) == (16, None)
    assert resolve_anchor("B", m) == (5, None)
    assert resolve_anchor("drop.2", m) == (21, None)
    assert resolve_anchor("drop.1.end", m) == (16, None)
    assert resolve_anchor("break.1 - 1", m) == (16, None)
    assert resolve_anchor("end", m) == (32, None)
    assert resolve_anchor("end + 1", m, until=True) == (33, None)


def test_anchor_problems_name_what_the_map_has():
    m = show_map()
    assert resolve_anchor("drop.3", m)[1] == "drop.3: the map has 2 drop sections (9, 21)"
    assert resolve_anchor("H", m)[1] == "H: the map has no hot cue H (it has A, B, G)"
    assert "outside 1-32" in resolve_anchor("end + 1", m)[1]
    off_beat = show_map(hot_cues={"A": "1.1", "B": "5.3"})
    assert "not on a bar's first beat" in resolve_anchor("B", off_beat)[1]


def test_anchor_loose_forms():
    m = show_map()
    assert resolve_anchor("drop.2-1", m) == (20, None)
    assert resolve_anchor(" drop.2 - 1 ", m) == (20, None)
    for bad in ("Drop.2", "b", 16.0, True, None, "drop", "drop.0"):
        bar, problem = resolve_anchor(bad, m)
        assert bar is None and "anchor" in problem


def test_merge_layers_merges_mappings_and_null_removes():
    base = {"movers": {"move": "pingpong", "positions": ["Up", "Down"]}, "hue": "dark"}
    over = {"movers": {"positions": None, "position": "Up"}, "hue": {"state": "pulse"}}
    assert merge_layers(base, over) == {"movers": {"move": "pingpong", "position": "Up"},
                                        "hue": {"state": "pulse"}}


def test_flatten_looks_extends_and_cycles():
    flat, problems = flatten_looks({"breu": {"movers": "off", "hue": "dark"},
                                    "breu-inicial": {"extends": "breu"},
                                    "a": {"extends": "b"}, "b": {"extends": "a"}})
    assert flat["breu-inicial"] == {"movers": "off", "hue": "dark"}
    assert ("a", "extends cycle: a -> b -> a") in problems


def test_flatten_looks_unknown_base():
    flat, problems = flatten_looks({"x": {"extends": "nada"}})
    assert "x" not in flat and problems == [("x", "extends 'nada', which is not a look")]


def test_expand_look_reads_unquoted_off():
    layers, problems = expand_look({"movers": False, "matrix": {"draw": "solid", "mirror": True}}, None, {})
    assert problems == [] and layers == {"movers": "off", "matrix": {"draw": "solid", "mirror": True}}


def test_expand_look_by_name_with_override():
    looks = {"breu": {"movers": "off", "hue": "dark"}}
    layers, problems = expand_look("breu", {"hue": {"state": "pulse"}}, looks)
    assert problems == [] and layers == {"movers": "off", "hue": {"state": "pulse"}}
    assert looks == {"breu": {"movers": "off", "hue": "dark"}}


def test_expand_look_unknown_name_suggests():
    _, problems = expand_look("pulso-vermelhoo", None, {"pulso-vermelho": {}})
    assert problems == ["look 'pulso-vermelhoo' is not defined; did you mean 'pulso-vermelho'?"]


def test_resolve_colours_palette_and_hex():
    layers, problems = resolve_colours({"matrix": {"colour": "azul"}, "hue": {"state": "pulse", "colour": "#B0001E"}}, PALETTE)
    assert layers["matrix"]["colour"] == "#0A2CFF" and layers["hue"]["colour"] == "#B0001E"
    assert resolve_colours({"movers": {"colour": "roxo"}}, PALETTE)[1] == [
        "colour 'roxo' is not in the palette (azul, vermelho) nor #RRGGBB"]


SHOW = {"__line__": 1, "show_version": 1, "set": "sets/x.md", "story": "Uma noite.",
        "palette": {"__line__": 3, "azul": "#0A2CFF"},
        "looks": {"__line__": 5, "breu": {"__line__": 6, "movers": "off", "hue": "dark"},
                  "breu-inicial": {"__line__": 7, "extends": "breu"}},
        "gesture_defaults": {"spiral": {"rates": ["1/2"]}},
        "bridge": {"name": "ponte", "intent": "Ponte."},
        "handover": {"name": "entrega", "intent": "Entrega."},
        "rules": {"movers-aim": True}}
TRACK = {"__line__": 1, "track": "A — B", "story": "S.", "budget": "B.",
         "cues": [{"__line__": 4, "at": "drop.1", "name": "drop", "look": "breu", "role": "arrival",
                   "accents": ["white", "strobe-roll"], "moment": "virada"},
                  {"__line__": 8, "at": 20, "until": "end + 1", "name": "espiral", "gesture": "spiral",
                   "with": {"bars": [2]}}],
         "handover": {"look": "breu", "until": 30, "at": "G"}, "bridge": False}


def test_problems_show_valid_and_bad_values():
    assert problems_show(SHOW) == []

    def with_(**change):
        data = copy.deepcopy(SHOW)
        data.update(change)
        return problems_show(data)

    bad_palette = with_(palette={"__line__": 3, "azul": "#12345"})
    assert len(bad_palette) == 1 and "palette.azul '#12345'" in bad_palette[0][1] and bad_palette[0][0] == 3
    bad_look = with_(looks={"x": {"laser": "on"}})
    assert len(bad_look) == 1 and "'laser'" in bad_look[0][1]
    assert len(with_(show_version=2)) == 1
    assert len(with_(story="")) == 1
    assert len(with_(bridge={"name": "Ponte", "intent": "x"})) == 1
    assert len(with_(bridge={})) == 2
    assert len(with_(handover={"name": "entrega"})) == 1
    assert len(with_(handover={"name": "entrega", "intent": " "})) == 1
    assert len(with_(rules=[1])) == 1
    assert len(with_(extra=1)) == 1
    missing = copy.deepcopy(SHOW)
    del missing["palette"]
    assert problems_show(missing) == [(1, "show.yml: missing key palette")]


def test_problems_track_file_valid_and_bad_values():
    assert problems_track_file(TRACK) == []

    def cue_with(**change):
        data = copy.deepcopy(TRACK)
        data["cues"][0].update(change)
        return problems_track_file(data)

    both = cue_with(gesture="spiral")
    assert len(both) == 1 and "exactly one of look and gesture" in both[0][1] and both[0][0] == 4
    flash = cue_with(accents=["flash"])
    assert len(flash) == 1 and "'flash'" in flash[0][1]
    bad_name = cue_with(name="Drop 1")
    assert len(bad_name) == 1 and "'Drop 1'" in bad_name[0][1]
    assert len(cue_with(role="finale")) == 1
    assert len(cue_with(at=1.5)) == 1
    assert len(cue_with(colour="x")) == 1
    bridge = copy.deepcopy(TRACK)
    bridge["bridge"] = True
    assert len(problems_track_file(bridge)) == 1
    nothing = copy.deepcopy(TRACK)
    nothing["cues"][0].pop("look")
    assert len(problems_track_file(nothing)) == 1


def test_flatten_looks_and_expand_look_report_odd_looks():
    flat, problems = flatten_looks({"a": {"extends": ["x"]}, "b": 3, "c": {"extends": {}}})
    assert flat == {} and sorted(n for n, _ in problems) == ["a", "b", "c"]
    assert flatten_looks([1])[1] and flatten_looks(None)[0] == {}
    assert expand_look("breu", {"laser": "on"}, {"breu": {}})[1] == [
        "with has 'laser', which is not a layer (movers, matrix, white, uv, strobe, hue)"]
    assert expand_look("breu", 3, {"breu": {}})[1] == ["with 3 is not a mapping"]


ODD = [None, "x", 3, [1], {}, {"__line__": 2}, {"a": {"__line__": 1}}, [{"__line__": 1}],
       {"looks": 3, "palette": [1], "bridge": 1, "handover": [], "rules": None, "story": None},
       {"cues": [None, 3, {"at": [1], "name": {}, "look": [1], "with": 2, "accents": [[1]]}],
        "handover": {"look": 3, "at": {}}, "track": [1]}]


@pytest.mark.parametrize("odd", ODD)
def test_odd_inputs_never_raise(odd):
    assert problems_show(odd) or odd == {}
    problems_track_file(odd)
    flatten_looks(odd)
    flatten_looks({"x": odd, "y": {"extends": odd}})
    for ref in (odd, "x"):
        expand_look(ref, odd, {"x": odd})
    resolve_colours(odd, PALETTE)
    resolve_colours({"movers": odd, "hue": {"colour": odd}, "matrix": {"colour": "x"}}, odd)
    for hot in (None, odd):
        m = show_map(hot_cues=None)
        m["hot_cues"] = hot
        resolve_anchor("B", m)
        resolve_anchor(odd, m)
