"""Tests for scripts/lightshow.py: the models, the loaders and the schema checks."""
import copy

import pytest
import yaml
from conftest import REPO_ROOT

import lightshow as ls

HAPPIER = REPO_ROOT / "lightshows/tracks/marshmello-x-bastille-happier.yml"
RIG = REPO_ROOT / "lightshows/rig.yml"

GUID = "F41EB9E9-B82B-4F58-A40C-B039222EBB0E"


def choreo(**overrides):
    data = {
        "track": "Artist One — Song A",
        "soundswitch": GUID,
        "grid": {"bpm": 100, "downbeat": "0:00.158"},
        "story": "Uma história.",
        "base": "autoscript",
        "sections": [{"bars": [1, 8], "name": "intro", "hue": "pulse"}],
    }
    data.update(overrides)
    return data


def with_section(**section):
    return choreo(sections=[{"bars": [1, 8], "name": "s", **section}])


# ------------------------------------------------------------------ loaders ----


def test_load_choreography_reads_the_happier_example():
    c = ls.load_choreography(HAPPIER)
    assert len(c.sections) == 15
    assert c.sections[0].bars == (1, 8)
    assert c.sections[0].name == "intro-batida"
    assert c.track == "Marshmello x Bastille — Happier"
    assert c.base == "autoscript"


def test_load_choreography_turns_yaml_booleans_into_words():
    c = ls.load_choreography(HAPPIER)
    first = c.sections[0].layers
    assert first["movers"] == "off" and first["matrix"] == "off" and first["hue"] == "pulse"
    assert "white" not in first


def test_load_rig_reads_the_real_rig():
    rig = ls.load_rig(RIG)
    assert rig.white_max == 0.6
    assert rig.zone_order == "row-major-top-left"
    assert rig.matrix_rows == ["colour"] * 3 + ["white"] + ["colour"] * 3
    nw, sw = rig.fixtures["matrix-nw"], rig.fixtures["matrix-sw"]
    assert (nw.node, nw.index, nw.corner) == (sw.node, 1, "NW")
    assert sw.index == 2 and nw.extra == {"aim": "centre"}
    assert rig.fixtures["haze"].node == " Lig Light LL-HZ600K"
    assert rig.fixtures["haze"].extra["fan"] == "Main -  Lig Light LL-HZ600K"
    assert rig.fixtures["hue"].node is None and rig.fixtures["hue"].extra["lamps"] == 7


def test_the_real_files_have_no_problems():
    assert ls.problems_rig(yaml.safe_load(RIG.read_text(encoding="utf-8"))) == []
    data = yaml.safe_load(HAPPIER.read_text(encoding="utf-8"))
    assert ls.problems_choreography(data, ls.load_rig(RIG)) == []


# --------------------------------------------------------------------- rig ----


def rig_data():
    return copy.deepcopy(yaml.safe_load(RIG.read_text(encoding="utf-8")))


@pytest.mark.parametrize("data", [None, [], "x"])
def test_rig_must_be_a_mapping(data):
    assert len(ls.problems_rig(data)) == 1


def test_rig_unknown_kind_corner_and_white_max():
    data = rig_data()
    data["fixtures"]["mover-ne"]["kind"] = "laser"
    data["fixtures"]["mover-se"]["corner"] = "up"
    data["matrix"]["white_max"] = 0
    problems = ls.problems_rig(data)
    assert len(problems) == 3
    assert any("laser" in p for p in problems)
    assert any("'up'" in p for p in problems)
    assert any("white_max" in p for p in problems)


@pytest.mark.parametrize("value", [1.5, True, "0.6", -0.1])
def test_rig_white_max_must_be_in_range(value):
    data = rig_data()
    data["matrix"]["white_max"] = value
    assert len(ls.problems_rig(data)) == 1


def test_rig_white_max_one_is_fine():
    data = rig_data()
    data["matrix"]["white_max"] = 1
    assert ls.problems_rig(data) == []


def test_rig_missing_and_unknown_keys():
    data = rig_data()
    del data["room"]
    data["extra"] = 1
    data["fixtures"]["mover-ne"]["colour"] = "red"
    del data["fixtures"]["mover-se"]["node"]
    assert len(ls.problems_rig(data)) == 4


# ------------------------------------------------------------- choreography ----


def test_a_minimal_choreography_is_clean():
    assert ls.problems_choreography(choreo(), None) == []


def test_choreography_ignores_loader_line_keys():
    data = choreo()
    data["__line__"] = 1
    data["sections"][0]["__line__"] = 9
    assert ls.problems_choreography(data) == []


def test_choreography_missing_and_unknown_top_keys():
    data = choreo(extra=1)
    del data["story"]
    assert len(ls.problems_choreography(data)) == 2


@pytest.mark.parametrize("guid", ["nope", 5, "F41EB9E9B82B4F58A40CB039222EBB0E"])
def test_choreography_soundswitch_must_be_a_guid(guid):
    assert len(ls.problems_choreography(choreo(soundswitch=guid))) == 1


def test_choreography_grid_and_base():
    assert len(ls.problems_choreography(choreo(grid={"bpm": 0, "downbeat": "0:00"}))) == 1
    assert len(ls.problems_choreography(choreo(grid={"bpm": 100, "downbeat": "soon"}))) == 1
    assert len(ls.problems_choreography(choreo(base="copy"))) == 1


def test_sections_overlapping_or_unsorted():
    sections = [{"bars": [1, 8], "name": "a"}, {"bars": [8, 12], "name": "b"}]
    assert len(ls.problems_choreography(choreo(sections=sections))) == 1
    sections = [{"bars": [9, 12], "name": "a"}, {"bars": [1, 8], "name": "b"}]
    assert len(ls.problems_choreography(choreo(sections=sections))) == 1
    sections = [{"bars": [1, 8], "name": "a"}, {"bars": [9, 12], "name": "b"}]
    assert ls.problems_choreography(choreo(sections=sections)) == []


@pytest.mark.parametrize("bars", [[0, 4], [5, 4], [1], [1, 2, 3], "1-4", [1.0, 4], [True, 4]])
def test_section_bars_must_be_an_ordered_pair_from_one(bars):
    data = choreo(sections=[{"bars": bars, "name": "a"}])
    assert len(ls.problems_choreography(data)) == 1


def test_section_unknown_layer_and_missing_name():
    problems = ls.problems_choreography(choreo(sections=[{"bars": [1, 2], "lasers": "on"}]))
    assert len(problems) == 2


@pytest.mark.parametrize(
    "layers",
    [
        {"movers": {"move": "spin"}},
        {"movers": {"every": "1/4"}},
        {"movers": {"move": "hold", "colour": "red"}},
        {"movers": {"move": "hold", "colour": "#FFF"}},
        {"movers": {"move": "hold", "level": 0}},
        {"movers": {"move": "hold", "level": 1.5}},
        {"movers": {"move": "pingpong", "every": "1/3"}},
        {"movers": {"move": "pingpong", "every": "0bar"}},
        {"movers": {"move": "hold", "tilt": 3}},
        {"movers": {"move": "sweep", "positions": []}},
        {"movers": {"move": "sweep", "positions": "Up"}},
        {"movers": {"move": "pingpong", "faster_from": 0}},
        {"movers": "on"},
        {"matrix": {"draw": "spiral"}},
        {"matrix": {"rate": "1/4"}},
        {"matrix": {"draw": "solid", "mirror": "yes"}},
        {"matrix": {"draw": "solid", "rate": "fast"}},
        {"matrix": {"draw": "solid", "glow": True}},
        {"white": {"accent": ["17"]}},
        {"white": {"accent": []}},
        {"white": {"accent": ["1.1"], "flash": "1/8"}},
        {"white": {}},
        {"white": {"flash": "slow"}},
        {"white": "on"},
        {"uv": {"move": "uv"}},
        {"uv": "blue"},
        {"strobe": {"hit": ["x"]}},
        {"strobe": {"roll": [4, 2]}},
        {"strobe": {"roll": [1]}},
        {"strobe": {"hit": ["1.1"], "roll": [1, 2]}},
        {"hue": "dim"},
        {"hue": {"state": "dim"}},
        {"hue": {"colour": "#FFFFFF"}},
        {"hue": {"state": "pulse", "colour": "white"}},
        {"haze": {"burst": "4"}},
        {"haze": {"burst": "4s", "fan": 1}},
        {"haze": {}},
        {"matrix": 3},
        {"hue": ["pulse"]},
    ],
)
def test_bad_layer_values_are_problems(layers):
    assert len(ls.problems_choreography(with_section(**layers))) >= 1


@pytest.mark.parametrize(
    "layers",
    [
        {"movers": "auto", "matrix": "auto", "white": "auto", "uv": "auto", "strobe": "auto"},
        {"movers": "off", "matrix": "off", "white": "off", "uv": "off", "strobe": "off"},
        {"movers": False, "matrix": False, "white": False, "uv": False, "strobe": False},
        {"uv": True, "haze": True, "hue": "off"},
        {"haze": "auto", "hue": "auto"},
        {"movers": {"move": "hold", "position": "DJ Booth", "colour": "#ffb347", "level": 1}},
        {"movers": {"move": "sweep", "every": "2bar", "positions": ["Up", "Down"]}},
        {"movers": {"move": "pingpong", "every": "1/16", "faster_from": 27, "faster_every": "1/2"}},
        {"matrix": {"draw": "fill-up", "rate": "1bar", "mirror": True, "pingpong": False}},
        {"matrix": {"draw": "rows-down", "with_white": True, "colour": "#00C8FF"}},
        {"white": {"accent": ["17.1", "20.3"]}},
        {"white": {"flash": "1/8"}},
        {"strobe": {"hit": ["81.1"]}},
        {"strobe": {"roll": [3, 4]}},
        {"hue": "dark"},
        {"hue": {"state": "bright", "colour": "#FFAA00"}},
        {"haze": {"burst": "6s"}},
    ],
)
def test_good_layer_values_are_clean(layers):
    assert ls.problems_choreography(with_section(**layers)) == []


# -------------------------------------------------------------------- plan ----


def test_plan_front_matter(tmp_path):
    (tmp_path / "sets").mkdir()
    (tmp_path / "sets/a.md").write_text("x", encoding="utf-8")
    good = {"set": "sets/a.md", "budget": {"white-accent": ["peak-1"], "strobe": ["final"]}}
    assert ls.problems_plan(good, tmp_path) == []
    assert len(ls.problems_plan({**good, "set": "sets/b.md"}, tmp_path)) == 1
    assert len(ls.problems_plan({**good, "budget": {"lasers": ["x"]}}, tmp_path)) == 1
    assert len(ls.problems_plan({**good, "budget": {"uv": "x"}}, tmp_path)) == 1
    assert len(ls.problems_plan({"set": "sets/a.md"}, tmp_path)) == 1
    assert len(ls.problems_plan(None, tmp_path)) == 1
