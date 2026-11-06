"""set_timeline.py: transitions, arrivals, peaks and the set clock from hand-built maps."""
import pytest
import yaml

import set_timeline as st
from mapdata import cue_ms, timeline_map


def leg(name, bars, cues, tempo=None, **kw):
    hot = {k: f"{v}.1" for k, v in cues.items()}
    return st.Leg(name, timeline_map(bars, hot=hot, **kw), {k: cue_ms(v) for k, v in cues.items()}, tempo)


def three():
    a = leg("A", 100, {"G": 80}, silences=[(98, 100)])
    b = leg("B", 120, {"B": 9, "G": 100}, drops=[(8, 5.0), (30, 9.0), (50, 12.0), (110, 20.0)],
            sections=[{"bars": [1, 16], "kind": "intro"}, {"bars": [17, 120], "kind": "groove"}])
    c = leg("C", 90, {"B": 17}, drops=[(40, 8.0)])
    return [a, b, c]


def test_offsets_overlaps_arrivals_and_peaks():
    (t1, t2), total, warnings = st.timeline(three())
    assert warnings == []
    # A: last bar 97 (98-100 is silence), G 80 -> overlap 18; B's B is 9 -> offset -71
    assert (t1.out_name, t1.in_name) == ("A", "B")
    assert (t1.g_bar, t1.b_bar, t1.offset_bars, t1.overlap_bars) == (80, 9, -71, 18)
    assert t1.overlap_sections == [("intro", 9, 16), ("groove", 17, 26)]
    # arrival: first drop >= 97 - 71 + 1 = 27 -> 30; peak: biggest drop with 9 < bar < 100 -> 50
    assert (t1.arrival_bar, t1.peak_bar) == (30, 50)
    # B: last bar 120, G 100 -> overlap 21; C's B is 17 -> offset -83
    assert (t2.g_bar, t2.b_bar, t2.offset_bars, t2.overlap_bars) == (100, 17, -83, 21)
    # arrival: first drop >= 120 - 83 + 1 = 38 -> 40; the last leg's peak looks at all drops
    assert (t2.arrival_bar, t2.peak_bar) == (40, 40)
    assert t2.overlap_drops == []


def test_arrival_none_lists_drops_in_the_overlap():
    a = leg("A", 60, {"G": 20})
    b = leg("B", 80, {"B": 5, "G": 70}, drops=[(10, 6.0), (30, 3.0)])
    (t,), _, _ = st.timeline([a, b])
    # overlap 41 bars covers B's bars 5..45; the arrival would be at bar 46
    assert t.arrival_bar is None and t.peak_bar == 10
    assert t.overlap_drops == [(10, 6.0), (30, 3.0)]


def test_peak_ignores_drops_at_or_before_b():
    a = leg("A", 60, {"G": 50})
    b = leg("B", 80, {"B": 10, "G": 70}, drops=[(3, 30.0), (10, 25.0), (40, 6.0)])
    (t,), _, _ = st.timeline([a, b])
    assert t.peak_bar == 40


def test_set_clock_constant_and_ramped():
    first = leg("A", 20, {"G": 8})                      # bars [1, 8): 14 s
    _, total, _ = st.timeline([first, leg("B", 8, {"B": 1}, tempo=(120, 120))])
    assert total == pytest.approx(14.0 + 16.0)
    expected = sum(240 / (120 + 8 * (k + 0.5) / 8) for k in range(8))
    assert expected == pytest.approx(15.47, abs=0.05)
    _, total, _ = st.timeline([first, leg("R", 8, {"B": 1}, tempo=(120, 128))])
    assert total == pytest.approx(14.0 + expected, abs=0.05)


def test_clock_across_legs():
    a = leg("A", 20, {"G": 8})                              # bars [1, 8): 14 s
    b = leg("B", 30, {"B": 5, "G": 12}, drops=[(9, 9.0)])   # bars [5, 12): 14 s
    c = leg("C", 30, {"B": 3})                              # bars 3..30: 28 bars
    ts, total, _ = st.timeline([a, b, c])
    assert ts[0].clock_g_s == pytest.approx(14.0)
    # last A bar 20, offset -3 -> arrival >= 18; B has no such drop
    assert ts[0].arrival_bar is None and ts[0].clock_arrival_s is None
    assert ts[1].clock_g_s == pytest.approx(28.0)
    assert total == pytest.approx(28.0 + 28 * 2.0)


def test_clock_arrival():
    a = leg("A", 12, {"G": 8})
    b = leg("B", 40, {"B": 1, "G": 30}, drops=[(10, 9.0)])
    (t,), _, _ = st.timeline([a, b])
    # last A bar 12, offset -7 -> arrival >= 6 -> 10; B starts at 14 s and 9 bars have passed
    assert t.arrival_bar == 10
    assert t.clock_arrival_s == pytest.approx(14.0 + 9 * 2.0)


def test_missing_g_skips_the_transition_and_warns():
    ts, _, warnings = st.timeline([leg("A", 20, {}), leg("B", 20, {"B": 2})])
    assert ts == []
    assert any(w.startswith("A:") and "no G cue" in w for w in warnings)


def test_missing_b_skips_the_transition_and_warns():
    ts, _, warnings = st.timeline([leg("A", 20, {"G": 8}), leg("B", 20, {})])
    assert ts == []
    assert any(w.startswith("B:") and "no B cue" in w for w in warnings)


def test_moved_cue_warns():
    a = leg("A", 200, {"G": 80})
    a.cues["G"] = cue_ms(82)
    _, _, warnings = st.timeline([a, leg("B", 20, {"B": 2})])
    assert "A: hot cue G moved since the map (map 80.1, rekordbox 82.1); run cues" in warnings


def test_cue_off_the_beat_warns():
    a = leg("A", 200, {"G": 80})
    a.cues["G"] += 300
    _, _, warnings = st.timeline([a, leg("B", 20, {"B": 2})])
    assert any(w.startswith("A: hot cue G is not on a beat") for w in warnings)


def test_a_cue_off_beat_one_warns_and_keeps_its_bar():
    a = leg("A", 200, {"G": 137})
    a.cues["G"] = cue_ms(137, 3)
    a.map["hot_cues"]["G"] = "137.3"
    b = leg("B", 20, {"B": 2})
    (t,), _, warnings = st.timeline([a, b])
    assert warnings == ["A: hot cue G at 137.3: the timeline assumes cues on beat 1"]
    assert t.g_bar == 137 and t.clock_g_s == pytest.approx(136 * 2.0)


BLOCK = """---
id: x
---
## Tracklist

1. Artist One — Song One  · 8A · 122 · e6
2. Artist Two — Song Two  · 8A · 122-125 · e6
3. Artist Three — Song Three  · 8A · e6

## Bridge in
"""


def test_block_tempos():
    assert st.block_tempos(BLOCK) == [
        ("Artist One", "Song One", (122.0, 122.0)),
        ("Artist Two", "Song Two", (122.0, 125.0)),
        ("Artist Three", "Song Three", None),
    ]


def test_render_markdown_has_one_row_per_transition():
    text = st.render_markdown(*st.timeline(three()))
    rows = [ln for ln in text.splitlines() if ln.startswith("| ") and not ln.startswith("| #")]
    assert len(rows) == 2
    assert "A G80 → B B9" in rows[0]
    short = [leg("A", 60, {"G": 20}), leg("B", 80, {"B": 5, "G": 70}, drops=[(10, 6.0)])]
    assert "none (drops in overlap: bar 10 6.0 dB)" in st.render_markdown(*st.timeline(short))


def test_render_yaml_round_trips():
    ts, total, warnings = st.timeline(three())
    data = yaml.safe_load(st.render_yaml(ts, total, warnings))
    assert len(data["transitions"]) == 2 and data["transitions"][0]["out"] == "A"
    assert data["total_s"] == pytest.approx(total, abs=0.01)


def test_g_is_the_start_of_its_bar():
    ts, _, _ = st.timeline([leg("A", 200, {"G": 169}), leg("B", 50, {"B": 1})])
    assert ts[0].clock_g_s == pytest.approx(168 * 2.0)  # 5:36


def test_a_cue_before_the_first_anchor_parses_and_a_misplaced_one_warns():
    a = leg("A", 200, {"G": 80})
    b = leg("B", 20, {"B": 2})
    b.map["hot_cues"]["B"] = "1.1-2000ms"
    b.cues["B"] = -2000
    ts, _, warnings = st.timeline([a, b])
    assert ts[0].b_bar == 1
    assert any("B: hot cue B is not on a beat" in w for w in warnings)
