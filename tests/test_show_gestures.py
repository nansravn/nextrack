"""The gesture registry: `sequence`, `spiral` and the span check of `run_gesture`."""
import pytest

from show_gestures import GESTURES, Gesture, GestureContext, GestureSection, gesture, run_gesture
from show_language import expand_look
from showdata import show_map

SPIRAL = {"bars": [2, 2, 2, 1], "rates": ["1/2", "1/4", "1/8", "1/16"],
          "colours": ["azul", "violeta", "violeta", "vermelho"],
          "aims": [["Crossed Over", "Up"], ["Crossed Over", "Up"], "Dance Floor Centre", "Dance Floor Centre"]}


def spiral_ctx(intent=None):
    return GestureContext(41, 47, "espiral", intent, show_map(64), lambda r, w: ({}, []))


def test_spiral_makes_one_section_per_step():
    sections, problems = run_gesture("spiral", spiral_ctx("gira"), SPIRAL)
    assert problems == []
    assert [(s.bars, s.name) for s in sections] == [((41, 42), "espiral-1-2"), ((43, 44), "espiral-1-4"),
                                                    ((45, 46), "espiral-1-8"), ((47, 47), "espiral-1-16")]
    first = sections[0].layers
    assert first["movers"] == {"move": "pingpong", "every": "1/2", "colour": "azul", "positions": ["Crossed Over", "Up"]}
    assert first["matrix"] == {"draw": "columns", "rate": "1/2", "colour": "azul", "pingpong": True}
    assert first["hue"] == "dark"
    assert sections[2].layers["movers"]["position"] == "Dance Floor Centre"
    assert all(s.intent == "gira" for s in sections)


def test_spiral_strips_line_keys():
    params = {**SPIRAL, "aims": [["Up"]] * 4, "__line__": 2}
    params["bars"] = [2, 2, 2, 1]
    sections, problems = run_gesture("spiral", spiral_ctx(), params)
    assert problems == []
    assert "__line__" not in repr([s.layers for s in sections])


def test_spiral_bars_must_fill_the_span():
    _, problems = run_gesture("spiral", spiral_ctx(), {"bars": [2, 2, 2], "rates": ["1/2"] * 3,
                                                       "colours": ["azul"] * 3, "aims": ["Up"] * 3})
    assert problems == ["spiral: bars add up to 6, the cue spans 7 bars (41-47)"]


def test_spiral_lists_must_have_the_same_length():
    sections, problems = run_gesture("spiral", spiral_ctx(), {"bars": [7], "rates": ["1/2", "1/4"],
                                                              "colours": ["azul"] * 3, "aims": ["Up"] * 4})
    assert sections == []
    assert len(problems) == 1 and problems[0].startswith("spiral: ")
    for n in ("bars (1)", "rates (2)", "colours (3)", "aims (4)"):
        assert n in problems[0]


def test_spiral_rejects_a_bad_rate():
    params = {**SPIRAL, "rates": ["1/2", "1/3", "1/8", "1/16"]}
    _, problems = run_gesture("spiral", spiral_ctx(), params)
    assert problems == ["spiral: rates[1] '1/3' is not a rate (1/16, 1/8, 1/4, 1/2, <n>bar)"]


@pytest.mark.parametrize("params", [
    {**SPIRAL, "bars": [[1], 2, 2, 2]},
    {**SPIRAL, "bars": [True, 2, 2, 2]},
    {**SPIRAL, "bars": "2222"},
    {**SPIRAL, "bars": [2, 2, 2, 0]},
    {**SPIRAL, "colours": "azul"},
    {**SPIRAL, "aims": [3, "Up", "Up", "Up"]},
    {**SPIRAL, "aims": [[], "Up", "Up", "Up"]},
    {**SPIRAL, "rates": [{"a": 1}, "1/2", "1/2", "1/2"]},
    {k: v for k, v in SPIRAL.items() if k != "aims"},
])
def test_spiral_bad_params_never_raise(params):
    sections, problems = run_gesture("spiral", spiral_ctx(), params)
    assert sections == [] and problems and all(p.startswith("spiral: ") for p in problems)


def test_unknown_parameter_is_reported():
    _, problems = run_gesture("spiral", spiral_ctx(), {**SPIRAL, "speed": 3})
    assert len(problems) == 1 and problems[0].startswith("spiral: unknown parameter 'speed'; parameters: ")


def seq_ctx(looks=None):
    return GestureContext(1, 4, "corte", None, show_map(), lambda r, w: expand_look(r, w, looks or {}))


def test_sequence_expands_looks_and_reports_them():
    looks = {"breu": {"movers": "off", "matrix": "off", "hue": "dark"}}
    steps = [{"bars": 1, "look": "breu"},
             {"bars": 3, "look": {"hue": "pulse", "__line__": 4}, "name": "volta"}]
    sections, problems = run_gesture("sequence", seq_ctx(looks), {"steps": steps})
    assert problems == []
    assert [(s.bars, s.name, s.look) for s in sections] == [((1, 1), "corte-1", "breu"), ((2, 4), "volta", None)]
    assert "__line__" not in repr(sections)


def test_sequence_step_problems_are_prefixed():
    _, problems = run_gesture("sequence", seq_ctx({"breu": {"hue": "dark"}}),
                              {"steps": [{"bars": 2, "look": "breu"}, {"bars": 2, "look": "x"}]})
    assert len(problems) == 1
    assert problems[0].startswith("sequence: step 2: look 'x' is not defined; ")


def test_sequence_bars_must_fill_the_span():
    _, problems = run_gesture("sequence", seq_ctx({"b": {"hue": "dark"}}), {"steps": [{"bars": 2, "look": "b"}]})
    assert problems == ["sequence: bars add up to 2, the cue spans 4 bars (1-4)"]


@pytest.mark.parametrize("params", [
    {"steps": "breu"},
    {"steps": []},
    {"steps": ["breu"]},
    {"steps": [{"bars": "2", "look": "b"}]},
    {"steps": [{"bars": True, "look": "b"}]},
    {"steps": [{"bars": 4}]},
    {"steps": [{"bars": 4, "look": "b", "name": 3}]},
    {"steps": [{"bars": 4, "look": "b", "extra": 1}]},
    {"steps": [{"bars": 4, "look": "b", "with": "x"}]},
    {},
])
def test_sequence_bad_params_never_raise(params):
    sections, problems = run_gesture("sequence", seq_ctx({"b": {"hue": "dark"}}), params)
    assert sections == [] and problems and all(p.startswith("sequence: ") for p in problems)


def test_unknown_gesture_lists_the_registry():
    _, problems = run_gesture("espiral", seq_ctx(), {})
    assert problems == ["unknown gesture 'espiral'; gestures: sequence, spiral"]


def test_params_must_be_a_mapping():
    _, problems = run_gesture("spiral", spiral_ctx(), [1])
    assert len(problems) == 1 and problems[0].startswith("spiral: ")


@pytest.fixture
def throwaway():
    added = []
    yield added
    for name in added:
        GESTURES.pop(name, None)


def test_a_gesture_that_misses_its_span_is_reported(throwaway):
    throwaway.append("broken-test")

    @gesture("broken-test", params={"x": "x"}, example={}, example_bars=1)
    def broken(ctx, params):
        """Covers one bar too few."""
        return [GestureSection((ctx.start, ctx.end - 1), "a", None, {})], []

    ctx = GestureContext(3, 6, "c", None, show_map(), lambda r, w: ({}, []))
    sections, problems = run_gesture("broken-test", ctx, {})
    assert sections == []
    assert problems == ["gesture 'broken-test' returned sections that do not cover bars 3-6"]


def test_every_gesture_documents_itself():
    assert {"sequence", "spiral"} <= set(GESTURES)
    for g in GESTURES.values():
        assert isinstance(g, Gesture)
        assert g.doc.strip() and g.params and g.example_bars >= 1
        ctx = GestureContext(1, g.example_bars, "exemplo", None, show_map(max(g.example_bars, 32)),
                             lambda r, w: expand_look(r, w, {}))
        sections, problems = run_gesture(g.name, ctx, g.example)
        assert problems == [] and sections
