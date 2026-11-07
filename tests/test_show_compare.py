import copy
from dataclasses import dataclass

from showdata import FILE_1, FILE_2, two_track_show

import show_compare
import show_rules


def _compile(src, inp):
    compiled, found, rules, advice = show_rules.evaluate_show(src, inp)
    assert compiled is not None, found
    return compiled, rules, advice


def _facts(src, inp):
    return show_compare.facts(*_compile(src, inp))


def test_a_show_compared_with_itself_is_the_same_everywhere():
    a = _facts(*two_track_show())
    b = _facts(*two_track_show())
    assert set(a) == set(show_compare.FACTS)
    assert all(a[f] for f in ("arrivals", "moments", "drops", "looks", "colours", "windows"))
    assert show_compare.diff_facts(a, b) == {f: [] for f in show_compare.FACTS}


def test_moving_an_arrival_is_a_difference_in_arrivals():
    a = _facts(*two_track_show())
    src, inp = two_track_show()
    src.track_files[FILE_1]["cues"][0]["at"] = "10"
    diff = show_compare.diff_facts(a, _facts(src, inp))
    assert len(diff["arrivals"]) == 1
    assert diff["arrivals"][0].startswith("~ Pedro Sampaio — Dançarina: bar 9")
    assert "-> bar 10" in diff["arrivals"][0]
    assert diff["moments"] == []


def _virada_twice(src, moved=False):
    """Voa Voa's final cue names the moment `virada` too; `moved` starts Dançarina's virada a bar
    later, at 22 (its espiral then spans 17-21)."""
    if moved:
        src.track_files[FILE_1]["cues"][1]["with"]["bars"] = [2, 3]
        src.track_files[FILE_1]["cues"][2]["at"] = "22"
    src.track_files[FILE_2]["cues"][2]["moment"] = "virada"
    return src


def test_every_occurrence_of_a_moment_is_a_fact_in_clock_order():
    src, inp = two_track_show()
    assert _facts(src, inp)["moments"] == {"virada": "Dançarina bar 21", "passagem": "Dançarina bar 25",
                                           "final": "Voa Voa (Ao Vivo) bar 21"}
    src, inp = two_track_show()
    twice = _facts(_virada_twice(src), inp)["moments"]
    assert twice == {"virada": "Dançarina bar 21", "passagem": "Dançarina bar 25",
                     "virada #2": "Voa Voa (Ao Vivo) bar 21"}
    src, inp = two_track_show()
    moved = _facts(_virada_twice(src, moved=True), inp)["moments"]
    assert show_compare.diff_facts({"moments": twice}, {"moments": moved})["moments"] == [
        "~ virada: Dançarina bar 21 -> Dançarina bar 22"]


def test_a_track_in_only_one_show_is_listed_as_added_or_removed():
    compiled, rules, advice = _compile(*two_track_show())
    fewer = copy.copy(compiled)
    fewer.tracks = compiled.tracks[:1]
    fewer.cache = {}
    diff = show_compare.diff_facts(show_compare.facts(compiled, rules, advice),
                                   show_compare.facts(fewer, rules, advice))
    assert any(line.startswith("- Voa Voa (Ao Vivo) bar") for line in diff["drops"])
    assert any(line.startswith("- Chiclete com Banana — Voa Voa (Ao Vivo):") for line in diff["arrivals"])
    back = show_compare.diff_facts(show_compare.facts(fewer, rules, advice),
                                   show_compare.facts(compiled, rules, advice))
    assert any(line.startswith("+ Chiclete com Banana — Voa Voa (Ao Vivo):") for line in back["arrivals"])


def test_the_minutes_round_to_five_seconds():
    assert show_compare._minutes(62.4) == "1:00"
    assert show_compare._minutes(63) == "1:05"


@dataclass
class _F:
    path: str
    line: int
    rule: str
    message: str


def test_findings_count_per_rule_name():
    rules = [_F("p", 1, "show-rules", "budget: x"), _F("p", 2, "show-rules", "budget: y")]
    advice = [_F("p", 3, "show-advice", "variety: z")]
    compiled, _, _ = _compile(*two_track_show())
    assert show_compare.facts(compiled, rules, advice)["findings"] == {"budget": "2", "advice variety": "1"}


def test_diff_lines_use_plus_minus_and_tilde():
    diff = show_compare.diff_facts({"looks": {"a": "1:00", "b": "2:00"}}, {"looks": {"b": "2:05", "c": "0:05"}})
    assert diff["looks"] == ["- a: 1:00", "~ b: 2:00 -> 2:05", "+ c: 0:05"]
