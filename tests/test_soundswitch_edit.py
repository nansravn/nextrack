"""Tempo grid and edit operations of the SoundSwitch model."""
from soundswitch_format import (FULL, ColourBlock, Key, PositionFlag, Span, check, covered,
                                grid, intensity, level_at, materialise_main, parse_script,
                                serialize_script, set_colour, set_intensity, set_main,
                                set_positions, track)


def roundtrip(s):
    assert parse_script(serialize_script(s)) == s


# --------------------------------------------------------------------- grid ----


def test_grid_single_anchor(make_script):
    g = grid(make_script())                       # 100 bpm: 600 ms beat, 2400 ms bar
    assert g.ms(1) == 158 and g.ms(2) == 158 + 2400 and g.ms(1, 3) == 158 + 1200
    assert g.bar_at(158) == 1 and g.bar_at(158 + 2399) == 1 and g.bar_at(158 + 2400) == 2
    assert g.beat_ms(1000) == 600


def test_grid_two_anchors(make_script):
    g = grid(make_script(tempo=[(158, 100.0), (158 + 4 * 2400, 120.0)]))
    assert g.ms(1) == 158 and g.ms(5) == 158 + 4 * 2400 and g.ms(6) == 158 + 4 * 2400 + 2000
    assert g.bar_at(158 + 4 * 2400 + 2001) == 6
    assert g.bar_at(158 + 4 * 2400 - 1) == 4
    assert g.beat_ms(158) == 600 and g.beat_ms(158 + 4 * 2400) == 500


def test_grid_anchor_off_the_bar_keeps_counting(make_script):
    # second anchor after 6 beats at 600 ms: bars keep counting by beats, not restarting
    g = grid(make_script(tempo=[(0, 100.0), (3600, 120.0)]))
    assert g.ms(2) == 2400 and g.ms(3) == 3600 + 2 * 500 and g.ms(2, 3) == 3600
    assert g.bar_at(3600) == 2 and g.bar_at(3600 + 999) == 2 and g.bar_at(3600 + 1000) == 3


# ------------------------------------------------------------------ helpers ----


def test_level_at_envelope(make_script):
    s = make_script()
    lane = intensity(track(s, 1167))
    assert level_at(lane, 0) == 0 and level_at(lane, 1000) == 0
    assert level_at(lane, 1001) == FULL and level_at(lane, 5000) == 0
    assert level_at(lane, 1150) == round(FULL * (1300 - 1150) / (1300 - 1001))


def test_covered_is_inclusive(make_script):
    t = track(make_script(), 1167)
    assert covered(t, 1000) and covered(t, 2000) and not covered(t, 999)
    assert not covered(t, 2001) and not covered(track(make_script(), 1820), 1500)


# ----------------------------------------------------------------- intensity ----


def test_set_intensity_keeps_outside_levels(make_script):
    s = make_script()
    t = track(s, 1167)
    lane = intensity(t)
    before = {x: level_at(lane, x) for x in (900, 1099, 1201, 1250)}
    set_intensity(t, 1100, 1200, [Key(1100, 0), Key(1200, 0)])
    assert level_at(intensity(t), 1150) == 0
    for x, v in before.items():
        assert level_at(intensity(t), x) == v
    assert check(s) == []
    roundtrip(s)


def test_set_intensity_span_cutting_a_ramp(make_script):
    s = make_script()
    t = track(s, 1167)
    t.lanes[0].keys = [Key(0, 0), Key(1000, 1000), Key(2000, 0)]
    expect = {x: level_at(t.lanes[0], x) for x in (400, 499, 701, 800, 1500)}
    set_intensity(t, 500, 700, [Key(500, 5), Key(700, 7)])
    lane = intensity(t)
    assert lane.keys == sorted(lane.keys, key=lambda k: k.t)
    for x, v in expect.items():
        assert level_at(lane, x) == v
    assert level_at(lane, 600) == 6
    assert check(s) == []


def test_set_intensity_merges_blocks(make_script):
    s = make_script()
    t = track(s, 1167)
    set_intensity(t, 1900, 3000, [Key(1900, FULL), Key(3000, FULL)])
    assert t.blocks.items == [Span(1000, 3000)]
    assert check(s) == []
    roundtrip(s)


def test_set_intensity_creates_section_and_lane(make_script):
    s = make_script()
    t = track(s, 1820)
    set_intensity(t, 0, 500, [Key(0, 10), Key(500, 20)])
    assert t.blocks.ver == 1 and t.blocks.items == [Span(0, 500)]
    assert level_at(intensity(t), 250) == 15
    assert check(s) == []
    roundtrip(s)


def test_set_intensity_rejects_keys_outside_span(make_script):
    import pytest
    t = track(make_script(), 1820)
    with pytest.raises(ValueError):
        set_intensity(t, 100, 200, [Key(99, 0)])


def test_set_main_replaces_keys_and_colour(make_script):
    s = make_script()
    set_main(s, 2000, 3000, [Key(2000, 0), Key(3000, FULL)], colour=0xFF112233)
    assert level_at(intensity(s.main), 1500) == 0x7FFFFFFF
    assert level_at(intensity(s.main), 3000) == FULL
    assert level_at(intensity(s.main), 10_000) == 0x7FFFFFFF
    assert s.main.blocks is None
    assert [(c.start, c.end, c.colour) for c in s.main.colours.items] == [(2000, 3000, 0xFF112233)]
    assert check(s) == []
    roundtrip(s)


# -------------------------------------------------------------------- colour ----


def test_set_colour_trims_and_splits(make_script):
    s = make_script()
    t = track(s, 1167)
    set_colour(t, 1200, 1300, 0xFFAA0000)
    assert [(c.start, c.end, c.colour) for c in t.colours.items] == [
        (1000, 1200, 0xFF00FF37), (1200, 1300, 0xFFAA0000), (1300, 2000, 0xFF00FF37)]
    assert check(s) == []
    roundtrip(s)


def test_set_colour_replaces_and_creates(make_script):
    s = make_script()
    t = track(s, 1167)
    set_colour(t, 900, 2100, 0xFF010203, 0xFF040506)
    assert t.colours.items == [ColourBlock(900, 2100, 0xFF010203, 0, 0xFF040506, 0)]
    e = track(s, 1820)
    set_colour(e, 0, 100, 0xFF111111)
    assert e.colours.ver == 1 and e.colours.items[0].colour_end == 0xFF111111
    assert check(s) == []
    roundtrip(s)


# ----------------------------------------------------------------- positions ----


def test_set_positions_drops_shapes_in_span(make_script):
    s = make_script()
    t = track(s, 1167)
    set_positions(t, 0, 10_000, [PositionFlag(500, 1)], s.main.positions.palette)
    assert (t.shapes is None or t.shapes.items == []) and check(s) == []
    assert t.position_blocks.items == [Span(0, 10_000)]
    assert (t.positions.ver, t.positions.x) == (2, 1)
    assert t.positions.palette == s.main.positions.palette
    assert t.positions.flags == [PositionFlag(500, 1)]
    roundtrip(s)


def test_set_positions_keeps_shapes_outside_span(make_script):
    s = make_script()
    t = track(s, 1167)
    set_positions(t, 3000, 4000, [PositionFlag(3500, 0)], s.main.positions.palette)
    assert len(t.shapes.items) == 1
    assert check(s) == []
    roundtrip(s)


def test_set_positions_replaces_flags_in_span(make_script):
    s = make_script()
    e = track(s, 1820)
    pal = s.main.positions.palette
    set_positions(e, 0, 1000, [PositionFlag(100, 0), PositionFlag(900, 1)], pal)
    set_positions(e, 500, 1500, [PositionFlag(700, 1)], pal)
    assert e.position_blocks.items == [Span(0, 1500)]
    assert [(f.t, f.preset) for f in e.positions.flags] == [(100, 0), (700, 1)]
    assert check(s) == []


# --------------------------------------------------------------- materialise ----


def test_materialise_copies_main_where_uncovered(make_script):
    s = make_script()
    t = track(s, 1820)                               # no blocks: follows Main
    materialise_main(s, t, 0, 5000)
    assert [(b.start, b.end) for b in t.blocks.items] == [(0, 5000)]
    assert level_at(intensity(t), 2500) == level_at(intensity(s.main), 2500)
    assert check(s) == []
    roundtrip(s)


def test_materialise_leaves_own_content(make_script):
    s = make_script()
    t = track(s, 1167)
    own = {x: level_at(intensity(t), x) for x in (1000, 1001, 1150, 1300, 2000)}
    materialise_main(s, t, 0, 5000, frozenset({"intensity"}))
    assert [(b.start, b.end) for b in t.blocks.items] == [(0, 5000)]
    for x, v in own.items():
        assert level_at(intensity(t), x) == v
    assert level_at(intensity(t), 500) == 0x7FFFFFFF
    assert level_at(intensity(t), 4000) == 0x7FFFFFFF
    assert check(s) == []
    roundtrip(s)


def test_materialise_colour_fills_gaps_only(make_script):
    s = make_script()
    set_main(s, 0, 10, [Key(0, 1), Key(10, 1)], colour=0xFF777777)
    s.main.colours.items = [ColourBlock(0, 3000, 0xFF777777, 0, 0xFF777777, 0)]
    t = track(s, 1167)
    materialise_main(s, t, 500, 5000, frozenset({"colour"}))
    assert [(c.start, c.end, c.colour) for c in t.colours.items] == [
        (500, 1000, 0xFF777777), (1000, 2000, 0xFF00FF37), (2000, 3000, 0xFF777777)]
    assert t.blocks.items == [Span(1000, 2000)]       # other lanes untouched
    assert check(s) == []
    roundtrip(s)


def test_materialise_positions_copies_flags_and_span(make_script):
    s = make_script()
    e = track(s, 1820)
    materialise_main(s, e, 0, 5000, frozenset({"position"}))
    assert e.position_blocks.items == [Span(1000, 2000)]
    assert e.positions.flags == [PositionFlag(1500, 1)]
    assert e.positions.palette == s.main.positions.palette
    assert e.blocks is None
    assert check(s) == []
    roundtrip(s)


def test_materialise_positions_skips_tracks_own_blocks(make_script):
    s = make_script()
    t = track(s, 1167)                                # own G block over 1000..2000
    materialise_main(s, t, 0, 5000, frozenset({"position"}))
    assert t.position_blocks is None or t.position_blocks.items == []
    assert len(t.shapes.items) == 1
    assert check(s) == []


# -------------------------------------------------------------------- check ----


def test_check_reports_violations(make_script):
    s = make_script()
    assert check(s) == []
    t = track(s, 1167)
    t.lanes[0].keys = [Key(5, 0), Key(3, 0)]
    t.blocks.items = [Span(0, 100), Span(50, 200)]
    t.position_blocks = type(t.blocks)(1, [Span(1500, 1600)])      # overlaps the G block
    s.main.positions.flags = [PositionFlag(5000, 0)]                # outside every F span
    problems = check(s)
    assert len(problems) == 4
    joined = "\n".join(problems)
    assert "1167" in joined and "node 2" in joined


def test_materialise_positions_carries_active_flag_at_the_cut(make_script):
    s = make_script()
    s.main.position_blocks.items = [Span(0, 10_000)]
    s.main.positions.flags = [PositionFlag(0, 0), PositionFlag(6000, 1)]
    e = track(s, 1820)
    set_positions(e, 0, 3000, [], s.main.positions.palette)
    materialise_main(s, e, 0, 10_000, frozenset({"position"}))
    assert e.position_blocks.items == [Span(0, 10_000)]    # copied 3001.. merges with own
    assert [(f.t, f.preset) for f in e.positions.flags] == [(3001, 0), (6000, 1)]
    assert check(s) == []
    roundtrip(s)
