"""The room and its aim catalogue (lightshows/room.yml)."""
import copy
from pathlib import Path

import pytest
import yaml

from show_room import Aim, Room, load_room, preset_aims, problems_room, resolve_aim

ROOT = Path(__file__).resolve().parent.parent
RIG = {"mover-ne": "mover", "mover-se": "mover", "matrix-nw": "matrix", "matrix-sw": "matrix",
       "haze": "haze", "hue": "hue-chandelier"}


def repo_room():
    return yaml.safe_load((ROOT / "lightshows/room.yml").read_text(encoding="utf-8"))


def real_rig():
    data = yaml.safe_load((ROOT / "lightshows/rig.yml").read_text(encoding="utf-8"))
    return {k: v["kind"] for k, v in data["fixtures"].items()}


def good():
    return {
        "size": {"x": 5.0, "y": 4.0, "z": 2.6}, "assumed": True,
        "fixtures": {k: [1.0, 1.0, 1.0] for k in RIG},
        "booth": [2.5, 4.0, 1.2],
        "aims": {
            "a": {"figure": "f", "preset": "A", "status": "configured",
                  "targets": {"mover-ne": [1, 1, 1], "mover-se": [1, 1, 1]}},
        },
    }


def pending(fallback, preset="P"):
    return {"figure": "f", "preset": preset, "status": "pending", "fallback": fallback,
            "targets": {"mover-ne": [1, 1, 1], "mover-se": [1, 1, 1]}}


def msgs(data, rig=RIG):
    return [m for _, m in problems_room(data, rig)]


def test_the_repo_room_is_valid():
    data = repo_room()
    assert problems_room(data, real_rig()) == []
    room = load_room(data)
    assert len(room.aims) == 19
    assert sum(a.status == "configured" for a in room.aims.values()) == 7


def test_a_good_room_has_no_problems_and_no_rig_skips_cross_checks():
    assert msgs(good()) == []
    data = good()
    data["fixtures"]["ghost"] = [0, 0, 0]
    assert msgs(data, None) == []


def test_room_schema_problems():
    data = good(); del data["booth"]
    assert any("missing the key 'booth'" in m for m in msgs(data))
    data = good(); data["booth"] = [9, 1, 1]
    assert any("outside the room" in m for m in msgs(data))
    data = good(); data["fixtures"]["ghost"] = [0, 0, 0]
    assert any("'ghost' is not a fixture key" in m for m in msgs(data))
    data = good(); del data["fixtures"]["haze"]
    assert any("rig fixture 'haze' has no place" in m for m in msgs(data))
    data = good(); data["aims"]["a"]["status"] = "done"
    assert any("configured or pending" in m for m in msgs(data))
    data = good(); data["aims"]["a"]["fallback"] = "a"
    assert any("must not have a fallback" in m for m in msgs(data))
    data = good(); data["aims"]["b"] = pending("a"); del data["aims"]["b"]["fallback"]
    assert any("needs a fallback" in m for m in msgs(data))
    data = good(); del data["aims"]["a"]["targets"]["mover-se"]
    assert any("no point for the mover 'mover-se'" in m for m in msgs(data))
    data = good(); data["aims"]["a"]["targets"]["matrix-nw"] = [1, 1, 1]
    assert any("not a mover" in m for m in msgs(data))
    data = good(); data["size"]["x"] = 0
    assert any("three positive finite numbers" in m for m in msgs(data))
    data = good(); data["fixtures"]["hue"] = [True, 1, 1]
    assert any("three finite numbers" in m for m in msgs(data))
    data = good(); data["aims"]["Bad_Id"] = copy.deepcopy(data["aims"]["a"])
    assert any("kebab-case" in m for m in msgs(data))
    assert msgs([]) == ["room must be a mapping with size, assumed, fixtures, booth and aims"]


def test_fallback_chain_and_cycle():
    data = good()
    data["aims"]["c"] = data["aims"].pop("a")
    data["aims"]["b"] = pending("c")
    data["aims"]["a"] = pending("b")
    assert msgs(data) == []
    room = load_room(data)
    assert resolve_aim(room, "a") == ("A", ["a", "b", "c"], None)
    data["aims"]["c"] = pending("a")
    found = msgs(data)
    assert len(found) == 1 and "fallback cycle" in found[0]
    room = Room((1, 1, 1), True, {}, (0, 0, 0), {
        "a": Aim("a", "f", "P", "pending", "b", {}), "b": Aim("b", "f", "P", "pending", "a", {})})
    preset, chain, problem = resolve_aim(room, "a")
    assert preset is None and "cycle" in problem
    assert resolve_aim(room, "zzz")[2] is not None


def test_ring_points_follow_the_rule():
    room = load_room(repo_room())
    assert room.aims["anel-1"].targets["mover-ne"] == (2.5, 4.0, 2.2)
    assert room.aims["anel-1"].targets["mover-se"] == (2.5, 0.0, 2.2)
    assert room.aims["anel-3"].targets["mover-ne"] == (5.0, 2.0, 2.2)
    for k in range(1, 9):
        opposite = room.aims[f"anel-{(k + 3) % 8 + 1}"].targets["mover-ne"]
        assert room.aims[f"anel-{k}"].targets["mover-se"] == opposite


def test_preset_aims_reverse_map():
    room = load_room(repo_room())
    mapping = preset_aims(room)
    assert mapping["Up"] == "coluna"
    assert "Apex" not in mapping  # pending
    room.aims["twin"] = Aim("twin", "f", "Up", "configured", None, {})
    assert "Up" not in preset_aims(room)


def _odd_cases():
    def mutate(fn):
        data = good()
        fn(data)
        return data
    inf, nan = float("inf"), float("nan")
    return [
        None, "room", [], 3,
        mutate(lambda d: d.update(size={1: 2, "x": 3})),
        mutate(lambda d: d.update(size={"x": inf, "y": 1, "z": 1})),
        mutate(lambda d: d.update(size=[1, 2, 3])),
        mutate(lambda d: d.update(fixtures=[1])),
        mutate(lambda d: d.update(fixtures={1: [0, 0, 0], "hue": "x"})),
        mutate(lambda d: d.update(aims=[1])),
        mutate(lambda d: d["aims"].update(b="not a mapping")),
        mutate(lambda d: d["aims"].update({7: d["aims"]["a"], 8: pending(7)})),
        mutate(lambda d: d["aims"].update({7: pending(8), 8: pending(7)})),
        mutate(lambda d: d["aims"].update(b=pending(["a"]))),
        mutate(lambda d: d["aims"]["a"].update(targets=[1, 2])),
        mutate(lambda d: d["aims"]["a"].update(targets={"mover-ne": [True, 1, 1]})),
        mutate(lambda d: d["aims"]["a"].update(targets={"mover-ne": ["a", 1, 1]})),
        mutate(lambda d: d["aims"]["a"].update(targets={"mover-ne": [nan, 1, 1]})),
        mutate(lambda d: d["aims"]["a"].update(status=["x"], figure=5, preset=None)),
        mutate(lambda d: d.update(booth="x", assumed=[1])),
    ]


@pytest.mark.parametrize("data", _odd_cases(), ids=lambda d: repr(d)[:40])
def test_odd_inputs_never_raise(data):
    for rig in (RIG, None, {1: "mover", "x": 2}):
        problems_room(data, rig)


def test_non_finite_numbers_name_the_value():
    data = good()
    data["size"]["x"] = float("inf")
    assert any("inf" in m and "finite" in m for m in msgs(data))
    data = good()
    data["fixtures"]["hue"] = [float("nan"), 1, 1]
    assert any("nan" in m and "finite" in m for m in msgs(data))
