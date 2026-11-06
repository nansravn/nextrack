"""The compiler: a choreography onto a copy of a SoundSwitch script, plus manual cues.

The room is the owner's real venue shape (public node names and ids from the spec):
Mover 1/2, two Vorlanes with MASTER, RGB 01-48 and W 1-8 children, and the haze with its
two channels. The script is synthetic: every node follows Main unless a test says so.
The last test reads the owner's real project from $NEXTRACK_SOUNDSWITCH_REAL and is
skipped without it."""
import copy
import os
from pathlib import Path

import pytest
from conftest import REPO_ROOT

import lightshow as ls
import soundswitch_format as ssf
from soundswitch_format import FULL, Key, check, covered, intensity, level_at

RIG = ls.load_rig(REPO_ROOT / "lightshows/rig.yml")
HAPPIER = REPO_ROOT / "lightshows/tracks/marshmello-x-bastille-happier.yml"
REAL = os.environ.get("NEXTRACK_SOUNDSWITCH_REAL")   # a read-only copy of the project folder

VENUE_GUID = "0122adb8-e4b9-46c9-96c8-98a7e8f6a5a9"
CASA_GUID = "d34c412f-48c1-4f75-9399-b35c069c8fdb"
VL = "VORLANE VL-1000 RGBW v2"
HAZE = " Lig Light LL-HZ600K"
UNITS = (1818, 1876)
MAIN_LEVEL = 0x7FFFFFFF
MAIN_COLOUR = 0xFF123456
STALE = 999                          # a node of an older venue layout
BAR = 2400                           # 100 BPM
PRESET_NAMES = ["Disco Ball", "Stage Left", "Stage Right", "Dance Floor Centre", "DJ Booth",
                "Crossed Over", "Up", "Down", "Stage Center", "Cake"]
PRESETS = [ssf.Preset(name, f"{9 - i:08x}-0000-0000-0000-000000000000")
           for i, name in enumerate(PRESET_NAMES)]


def ms(bar, beat=1):
    return 158 + (bar - 1) * BAR + (beat - 1) * 600


def span(first, last):
    return ms(first), ms(last + 1) - 1


def rgb(unit, n):
    return unit + 1 + n             # RGB 01 is the node after MASTER


def white(unit, n):
    return unit + 49 + n


def master(unit):
    return unit + 1


def venue_nodes(drop=()):
    nodes = [ssf.VenueNode(1166, "Group 4", None, None, 0),
             ssf.VenueNode(1167, "Mover 1", None, 1087, 0),
             ssf.VenueNode(1168, "Mover 2", None, 1088, 0)]
    for unit in UNITS:
        nodes.append(ssf.VenueNode(unit, VL, None, None, 0))
        nodes.append(ssf.VenueNode(master(unit), f"MASTER - {VL}", unit, 1, 0))
        nodes += [ssf.VenueNode(rgb(unit, n), f"RGB {n:02d} - {VL}", unit, 1, 0) for n in range(1, 49)]
        nodes += [ssf.VenueNode(white(unit, n), f"W {n} - {VL}", unit, 1, 0) for n in range(1, 9)]
    nodes += [ssf.VenueNode(1934, HAZE, None, None, 0),
              ssf.VenueNode(1935, f"Main - {HAZE}", 1934, 1, 0),
              ssf.VenueNode(1936, f"Main - {HAZE} - 2", 1934, 1, 0)]
    return [n for n in nodes if n.id not in drop]


VENUES = [ssf.VenueInfo("DJ Renan", VENUE_GUID, venue_nodes()), ssf.VenueInfo("Casa", CASA_GUID, [])]


def empty(node):
    return ssf.Track(node=node, lanes=[ssf.Lane(4, 1, None, [])], blocks=None, link=1,
                     colours=None, positions=None, strobes=None, position_blocks=None, shapes=None)


@pytest.fixture
def room(make_script):
    """A script with a track per venue node, a stale node and a Main that is lit and
    coloured all along; Mover 1 has own pulses at 3000 and 20000 ms."""
    def _build(tempo=((158, 100.0),)):
        trks = [empty(n.id) for n in venue_nodes()] + [empty(STALE)]
        mover = next(t for t in trks if t.node == 1167)
        mover.lanes[0].keys = [Key(3000, 0), Key(3001, FULL), Key(3500, 0),
                               Key(20000, 0), Key(20001, FULL), Key(21000, 0)]
        mover.blocks = ssf.Section(1, [ssf.Span(3000, 3500), ssf.Span(20000, 21000)])
        palette = sorted((p.guid, i) for i, p in enumerate(PRESETS))
        main = ssf.Track(
            node=2,
            lanes=[ssf.Lane(4, 1, 0, [Key(0, MAIN_LEVEL), Key(400_000, MAIN_LEVEL)])]
                  + [ssf.Lane(a, 1, None, []) for a in (2, 3, 5, 6, 7)],
            blocks=None, link=0,
            colours=ssf.Section(1, [ssf.ColourBlock(0, 400_000, MAIN_COLOUR, 0, MAIN_COLOUR, 0)]),
            # as in the real scripts, Main's position flags have no position block (F)
            positions=ssf.Positions(2, 1, palette, [ssf.PositionFlag(0, 0), ssf.PositionFlag(9758, 4)]),
            strobes=None, position_blocks=None, shapes=None)
        return make_script(
            venues=[ssf.Venue(4, VENUE_GUID, 3, trks, (1, 0)), ssf.Venue(4, CASA_GUID, 3, [], (1, 0))],
            tempo=list(tempo), main=main, node_lists=[1] * len(trks))
    return _build


def section(first, last, **layers):
    return ls.Section((first, last), "s", None, layers)


def choreo(*sections, grid=None):
    return ls.Choreography(track="A — B", soundswitch="F41EB9E9-B82B-4F58-A40C-B039222EBB0E",
                           grid=grid or {"bpm": 100, "downbeat": "0:00.158"}, story="x",
                           budget=None, base="autoscript", sections=list(sections))


def compile_(script, *sections, venues=VENUES, grid=None):
    return ls.compile_choreography(choreo(*sections, grid=grid), script, RIG, venues, PRESETS)


HAZE_NODES = (1934, 1935, 1936)      # the haze group and its fan and fog channels


def section_cues(cues):
    """`cues` without the one whole-track haze cue that every compile gives."""
    assert [c.fixture for c in cues].count("haze") == 1, cues
    return [c for c in cues if c.fixture != "haze"]


def without_haze(script):
    """`script` without the haze nodes' tracks, which every compile writes."""
    out = copy.deepcopy(script)
    for v in out.venues:
        v.tracks = [t for t in v.tracks if t.node not in HAZE_NODES]
    return out


def lvl(script, node, t):
    trk = script.main if node == 2 else ssf.track(script, node)
    return level_at(intensity(trk), t)


def colour_at(trk, t):
    hits = [c.colour for c in (trk.colours.items if trk.colours else []) if c.start <= t <= c.end]
    return hits[-1] if hits else None


# ------------------------------------------------------------------ refusals ----


def test_more_than_eight_tempo_anchors_is_refused(room):
    anchors = [(158 + i * 8 * BAR, 100.0) for i in range(9)]
    with pytest.raises(ls.CompileError, match="anchors"):
        compile_(room(anchors), section(1, 2, hue="dark"))
    compile_(room(anchors[:8]), section(1, 2, hue="dark"))


def test_grid_must_match_the_first_anchor(room):
    with pytest.raises(ls.CompileError, match="grid"):
        compile_(room(), section(1, 2, hue="dark"), grid={"bpm": 100, "downbeat": "0:00.161"})
    with pytest.raises(ls.CompileError, match="grid"):
        compile_(room(), section(1, 2, hue="dark"), grid={"bpm": 100.02, "downbeat": "0:00.158"})
    compile_(room(), section(1, 2, hue="dark"), grid={"bpm": 100.01, "downbeat": "0:00.160"})


def test_no_venue_for_the_script_is_refused(room):
    with pytest.raises(ls.CompileError, match="venue"):
        compile_(room(), section(1, 2, hue="dark"), venues=[VENUES[1]])


# ---------------------------------------------------------------- the basics ----


def test_returns_an_edited_copy(room):
    script = room()
    before = ssf.serialize_script(script)
    out, _ = compile_(script, section(2, 3, movers="off", hue="dark"))
    assert ssf.serialize_script(script) == before
    assert out is not script and lvl(out, 2, ms(2) + 100) == 0
    assert ssf.parse_script(ssf.serialize_script(out)) == out
    assert check(out) == []


def test_movers_off_zeroes_both_movers_across_the_span_only(room):
    script = room()
    out, cues = compile_(script, section(2, 3, movers="off"))
    start, end = span(2, 3)
    assert section_cues(cues) == []
    for node in (1167, 1168):
        trk = ssf.track(out, node)
        assert all(lvl(out, node, t) == 0 and covered(trk, t)
                   for t in (start, 3001, 3200, (start + end) // 2, end))
    m1, orig = ssf.track(out, 1167), ssf.track(script, 1167)
    for t in (start - 1, end + 1, 20_001, 20_500, 21_000):
        assert lvl(out, 1167, t) == lvl(script, 1167, t)
        assert covered(m1, t) == covered(orig, t)
    assert not covered(ssf.track(out, 1168), start - 1) and not covered(ssf.track(out, 1168), end + 1)
    assert out.main == script.main


# ------------------------------------------------------------------------ hue ----


GROUPS = (1166, *UNITS, 1934)        # group nodes: they never carry content in real scripts


def test_hue_dark_materialises_main_into_every_leaf_node(room):
    script = room()
    out, _ = compile_(script, section(2, 3, hue="dark"))
    start, end = span(2, 3)
    mid = (start + end) // 2
    assert lvl(out, 2, mid) == 0 and lvl(out, 2, start) == 0 and lvl(out, 2, end) == 0
    assert lvl(out, 2, start - 1) == MAIN_LEVEL and lvl(out, 2, end + 1) == MAIN_LEVEL
    # every leaf but the haze channels, which hold the rig's level (see the haze tests)
    for node in (rgb(1818, 1), rgb(1876, 48), white(1818, 1), master(1818), 1168):
        trk = ssf.track(out, node)
        assert covered(trk, start) and covered(trk, end) and lvl(out, node, mid) == MAIN_LEVEL
        assert trk.colours is None                     # no hue colour: colour lane untouched
    # Mover 1 keeps its own pulse inside the span; the gaps around it are Main's
    assert lvl(out, 1167, 3001) == FULL and lvl(out, 1167, 3500) == 0
    assert lvl(out, 1167, 5000) == MAIN_LEVEL and covered(ssf.track(out, 1167), 5000)
    assert ssf.track(out, STALE) == ssf.track(script, STALE)


def test_hue_leaves_group_nodes_untouched(room):
    script = room()
    out, _ = compile_(script, section(2, 3, hue={"state": "bright", "colour": "#FF0000"},
                                      movers="off", matrix={"draw": "solid"}))
    for node in GROUPS:
        assert ssf.track(out, node) == ssf.track(script, node), node


def test_hue_with_colour_also_materialises_colour(room):
    out, _ = compile_(room(), section(2, 3, hue={"state": "dark", "colour": "#FF0000"}))
    start, end = span(2, 3)
    mid = (start + end) // 2
    assert colour_at(out.main, mid) == 0xFFFF0000
    assert colour_at(out.main, start - 10) == MAIN_COLOUR
    cell = ssf.track(out, rgb(1818, 1))
    assert [(c.start, c.end, c.colour) for c in cell.colours.items] == [(start, end, MAIN_COLOUR)]
    assert lvl(out, rgb(1818, 1), mid) == MAIN_LEVEL


def test_hue_off_is_dark_and_bright_and_pulse_levels(room):
    out, _ = compile_(room(), section(1, 1, hue="off"), section(2, 2, hue="bright"),
                      section(3, 3, hue="pulse"))
    assert lvl(out, 2, ms(1) + 500) == 0
    assert lvl(out, 2, ms(2) + 500) == ls.level_of(0.85)
    assert lvl(out, 2, ms(3)) == FULL and lvl(out, 2, ms(3) + 599) == 0
    assert lvl(out, 2, ms(3, 2)) == FULL


def test_layers_own_their_lanes_under_a_hue_change(room):
    hue = {"state": "dark", "colour": "#FF0000"}
    out, _ = compile_(room(), section(2, 3, hue=hue, movers={"move": "hold"},
                                      matrix={"draw": "solid", "colour": "#00FF00"}))
    start, end = span(2, 3)
    m2 = ssf.track(out, 1168)                    # writes intensity only: keeps Main's old colour
    assert [(c.start, c.end, c.colour) for c in m2.colours.items] == [(start, end, MAIN_COLOUR)]
    assert lvl(out, 1168, start + 100) == ls.level_of(0.85)
    cell = ssf.track(out, rgb(1818, 9))          # writes both: its own colour
    assert [(c.start, c.end, c.colour) for c in cell.colours.items] == [(start, end, 0xFF00FF00)]


# --------------------------------------------------------------------- movers ----


def test_mover_hold_sets_level_colour_and_position(room):
    script = room()
    out, cues = compile_(script, section(2, 3, movers={"move": "hold", "position": "DJ Booth",
                                                       "colour": "#FFB347", "level": 0.5}))
    start, end = span(2, 3)
    assert section_cues(cues) == []
    for node in (1167, 1168):
        trk = ssf.track(out, node)
        assert lvl(out, node, start + 10) == ls.level_of(0.5)
        assert colour_at(trk, start + 10) == 0xFFFFB347
        assert [(s.start, s.end) for s in trk.position_blocks.items] == [(start, end)]
        (flag,) = trk.positions.flags
        guid = next(p.guid for p in PRESETS if p.name == "DJ Booth")
        assert flag.t == start and trk.positions.palette[flag.preset][0] == guid


def shape(start, end):
    return ssf.ShapeBlock(start, end, 0, 2, (0.5, 0.5, 0.5, 0.5), 0, 1, 2, 1)


def test_shape_block_straddling_the_section_is_a_cue(room):
    script = room()
    start, end = span(2, 3)
    ssf.track(script, 1167).shapes = ssf.Shapes(1, 1, [shape(start - 1000, start + 1000),
                                                       shape(start + 2000, start + 3000)])
    out, cues = compile_(script, section(2, 3, movers={"move": "hold", "position": "DJ Booth"}))
    cues = section_cues(cues)
    assert len(cues) == 1
    assert cues[0].fixture == "mover-ne" and "shape block" in cues[0].what
    assert f"{start - 1000}–{start + 1000} ms" in cues[0].what
    assert ssf.track(out, 1167).shapes.items == []        # both removed: the cue says so


@pytest.mark.parametrize("neighbour, cue", [
    ({"move": "hold", "position": "Up"}, False),           # the next section aims the movers itself
    ({"move": "pingpong", "every": "1/4", "position": "Crossed Over"}, False),
    ("off", False),                                       # the movers are dark there: no movement shows
    ({"move": "pingpong", "every": "1/4"}, True),         # no aim: the autoscript's movement is lost there
    ("auto", True),
    ({"move": "uv"}, True),                               # a UV wash writes nothing: a manual cue
])
def test_a_cut_shape_block_is_a_cue_only_where_its_movement_is_lost(room, neighbour, cue):
    script = room()
    border = ms(4)                                        # bars 2-3 | bars 4-5
    ssf.track(script, 1167).shapes = ssf.Shapes(1, 1, [shape(border - 1000, border + 1000)])
    out, cues = compile_(script, section(2, 3, movers={"move": "hold", "position": "DJ Booth"}),
                         section(4, 5, movers=neighbour))
    shape_cues = [c for c in section_cues(cues) if "shape block" in c.what]
    assert bool(shape_cues) == cue
    assert ssf.track(out, 1167).shapes.items == []        # removed whole either way


def test_a_cut_shape_block_is_a_cue_next_to_a_preset_the_script_palette_lacks(room):
    """The venue has the preset but this script's palette does not: the neighbour writes no
    position, the autoscript's movement stays there, so the removed movement would show."""
    script = room()
    border = ms(4)
    ssf.track(script, 1167).shapes = ssf.Shapes(1, 1, [shape(border - 1000, border + 1000)])
    presets = PRESETS + [ssf.Preset("Laser Wall", "aaaaaaaa-0000-0000-0000-000000000000")]
    sections = [section(2, 3, movers={"move": "hold", "position": "DJ Booth"}),
                section(4, 5, movers={"move": "hold", "position": "Laser Wall"})]
    _, cues = ls.compile_choreography(choreo(*sections), script, RIG, VENUES, presets)
    assert any("shape block" in c.what for c in section_cues(cues))


def test_a_duplicate_preset_name_resolves_like_the_compiler(room):
    """Two venue presets named `Up`: the compiler takes the first, which this palette lacks,
    so the neighbour writes no position and the cut is a real loss."""
    script = room()
    border = ms(4)
    ssf.track(script, 1167).shapes = ssf.Shapes(1, 1, [shape(border - 1000, border + 1000)])
    presets = [ssf.Preset("Up", "bbbbbbbb-0000-0000-0000-000000000000")] + PRESETS
    sections = [section(2, 3, movers={"move": "hold", "position": "DJ Booth"}),
                section(4, 5, movers={"move": "hold", "position": "Up"})]
    _, cues = ls.compile_choreography(choreo(*sections), script, RIG, VENUES, presets)
    assert any("shape block" in c.what for c in section_cues(cues))


def test_a_cut_shape_block_covered_on_one_side_only_is_a_cue(room):
    script = room()                                       # bar 1 unchoreographed | bars 2-3 | bars 4-5
    ssf.track(script, 1167).shapes = ssf.Shapes(1, 1, [shape(ms(2) - 1000, ms(4) + 1000)])
    _, cues = compile_(script, section(2, 3, movers={"move": "hold", "position": "DJ Booth"}),
                       section(4, 5, movers={"move": "hold", "position": "Up"}))
    assert any("shape block" in c.what for c in section_cues(cues))


def test_a_cut_shape_block_reaching_a_gap_between_aimed_sections_is_a_cue(room):
    script = room()
    border = ms(4)                                        # bars 2-3 | bar 4 unchoreographed | bars 5-6
    ssf.track(script, 1167).shapes = ssf.Shapes(1, 1, [shape(border - 1000, border + BAR + 1000)])
    out, cues = compile_(script, section(2, 3, movers={"move": "hold", "position": "DJ Booth"}),
                         section(5, 6, movers={"move": "hold", "position": "Up"}))
    assert any("shape block" in c.what for c in section_cues(cues))


def test_mover_sweep_steps_through_its_positions(room):
    out, _ = compile_(room(), section(1, 4, movers={"move": "sweep", "every": "1bar",
                                                    "positions": ["Up", "Cake"]}))
    trk = ssf.track(out, 1167)
    names = {p.guid: p.name for p in PRESETS}
    got = [(f.t, names[trk.positions.palette[f.preset][0]]) for f in trk.positions.flags]
    assert got == [(ms(1), "Up"), (ms(2), "Cake"), (ms(3), "Up"), (ms(4), "Cake")]


def test_a_position_section_keeps_the_preset_in_force_after_it(room):
    script = room()
    palette = script.main.positions.palette
    index = {p.name: next(i for i, (g, _) in enumerate(palette) if g == p.guid) for p in PRESETS}
    mover = ssf.track(script, 1167)                  # autoscript: Up from bar 1, Cake from bar 3
    mover.positions = ssf.Positions(2, 1, list(palette), [ssf.PositionFlag(ms(1), index["Up"]),
                                                          ssf.PositionFlag(ms(3), index["Cake"])])
    mover.position_blocks = ssf.Section(1, [ssf.Span(ms(1), ms(9) - 1)])
    out, _ = compile_(script, section(2, 3, movers={"move": "hold", "position": "DJ Booth"}))
    trk = ssf.track(out, 1167)
    names = {p.guid: p.name for p in PRESETS}

    def at(t):
        return names[trk.positions.palette[ssf.active_flag(trk, t).preset][0]]

    assert [at(t) for t in (ms(2) - 1, ms(2), ms(4) - 1, ms(4), ms(9) - 1)] == [
        "Up", "DJ Booth", "DJ Booth", "Cake", "Cake"]
    assert check(out) == []


def test_unknown_preset_name_is_a_manual_cue(room):
    out, cues = compile_(room(), section(2, 3, movers={"move": "hold", "position": "Nowhere"}))
    cues = section_cues(cues)
    assert len(cues) == 1 and "Nowhere" in cues[0].what
    assert (cues[0].bar, cues[0].time_ms) == (2, ms(2))
    assert lvl(out, 1167, ms(2) + 10) == ls.level_of(0.85)
    assert ssf.track(out, 1167).position_blocks is None


def test_pingpong_faster_from_is_an_absolute_bar_and_rises_sharply(room):
    move = {"move": "pingpong", "every": "1bar", "faster_from": 27, "faster_every": "1/2"}
    out, _ = compile_(room(), section(21, 28, movers=move))
    assert lvl(out, 1167, ms(21) + 1200) == FULL and lvl(out, 1168, ms(21) + 1200) == 0
    assert lvl(out, 1167, ms(22) + 1200) == 0          # dark step: no ramp up to the next one
    assert lvl(out, 1168, ms(22) + 1200) == FULL
    assert lvl(out, 1167, ms(27) + 600) == FULL        # bar 27: half-bar steps
    assert lvl(out, 1167, ms(27) + 1800) == 0
    assert lvl(out, 1168, ms(27) + 1800) == FULL


def test_movers_uv_is_a_manual_cue(room):
    script = room()
    out, cues = compile_(script, section(2, 3, movers={"move": "uv"}))
    cues = section_cues(cues)
    assert len(cues) == 1 and "UV" in cues[0].what
    assert ssf.track(out, 1168) == ssf.track(script, 1168)


def test_missing_node_is_a_manual_cue_and_is_skipped(room):
    venues = [ssf.VenueInfo("DJ Renan", VENUE_GUID, venue_nodes(drop={1168}))]
    script = room()
    out, cues = compile_(script, section(2, 3, movers="off"), venues=venues)
    cues = section_cues(cues)
    assert len(cues) == 1 and cues[0].fixture == "mover-se" and "Mover 2" in cues[0].what
    assert lvl(out, 1167, ms(2) + 10) == 0
    assert ssf.track(out, 1168) == ssf.track(script, 1168)


# --------------------------------------------------------------------- matrix ----


def test_matrix_solid_keeps_white_off_and_master_full(room):
    out, cues = compile_(room(), section(1, 2, matrix={"draw": "solid"}))
    start, end = span(1, 2)
    assert section_cues(cues) == []
    for unit in UNITS:
        for n in range(1, 9):
            trk = ssf.track(out, white(unit, n))
            assert covered(trk, start) and covered(trk, end)
            assert all(lvl(out, white(unit, n), t) == 0 for t in (start, start + 300, end))
        assert all(lvl(out, master(unit), t) == FULL for t in (start, (start + end) // 2, end))
        assert covered(ssf.track(out, master(unit)), end)
        cell = ssf.track(out, rgb(unit, 30))
        assert lvl(out, rgb(unit, 30), start) == FULL and lvl(out, rgb(unit, 30), ms(1, 2)) == FULL
        assert lvl(out, rgb(unit, 30), ms(1, 2) - 1) < FULL // 100
        assert colour_at(cell, start + 10) == 0xFF00C8FF


def test_matrix_fill_up_by_bar(room):
    out, _ = compile_(room(), section(1, 4, matrix={"draw": "fill-up", "rate": "1bar"}))
    for unit in UNITS:
        for n in range(41, 49):                        # row 6 (bottom): from bar 1
            assert lvl(out, rgb(unit, n), ms(1)) == FULL
        for n in range(17, 25):                        # row 2: only from bar 4
            assert all(lvl(out, rgb(unit, n), t) == 0 for t in (ms(1), ms(2), ms(3), ms(4) - 1))
            assert lvl(out, rgb(unit, n), ms(4)) == FULL
        assert colour_at(ssf.track(out, rgb(unit, 41)), ms(1)) == 0xFFFF2D95


def test_matrix_mirror_flips_the_second_unit(room):
    out, _ = compile_(room(), section(1, 1, matrix={"draw": "columns", "rate": "1/4", "mirror": True}))
    assert lvl(out, rgb(1818, 1), ms(1)) == FULL and lvl(out, rgb(1818, 8), ms(1)) == 0
    assert lvl(out, rgb(1876, 8), ms(1)) == FULL and lvl(out, rgb(1876, 1), ms(1)) == 0


def test_matrix_pingpong_alternates_the_units(room):
    out, _ = compile_(room(), section(1, 1, matrix={"draw": "solid", "rate": "1/4", "pingpong": True}))
    assert lvl(out, rgb(1818, 1), ms(1)) == FULL and lvl(out, rgb(1876, 1), ms(1)) == 0
    assert lvl(out, rgb(1818, 1), ms(1, 2)) == 0 and lvl(out, rgb(1876, 1), ms(1, 2)) == FULL


def test_matrix_with_white_draws_the_strip_capped(room):
    out, _ = compile_(room(), section(1, 1, matrix={"draw": "solid", "with_white": True}))
    level = lvl(out, white(1818, 1), ms(1))
    assert 0 < level <= RIG.white_max * 2**32


def test_matrix_off_zeroes_the_colour_cells(room):
    out, _ = compile_(room(), section(1, 1, matrix="off"))
    assert lvl(out, rgb(1818, 5), ms(1) + 100) == 0 and covered(ssf.track(out, rgb(1818, 5)), ms(1))
    assert lvl(out, white(1818, 5), ms(1) + 100) == 0           # white defaults to off
    assert ssf.track(out, master(1818)).blocks is None


# ---------------------------------------------------------------------- white ----


def test_white_accent_on_the_beat_capped(room):
    out, _ = compile_(room(), section(1, 4, white={"accent": ["2.1"]}))
    for unit in UNITS:
        node = white(unit, 3)
        assert 0 < lvl(out, node, ms(2)) <= RIG.white_max * 2**32
        assert lvl(out, node, ms(1)) == 0 and lvl(out, node, ms(2) - 1) == 0
        assert lvl(out, node, ms(3)) == 0
    assert ssf.track(out, rgb(1818, 1)).blocks is None           # colour cells still follow Main


def test_white_accent_outside_the_section_is_a_cue(room):
    _, cues = compile_(room(), section(1, 4, white={"accent": ["9.1"]}))
    cues = section_cues(cues)
    assert len(cues) == 1 and "9.1" in cues[0].what


def test_white_flash(room):
    out, _ = compile_(room(), section(1, 1, white={"flash": "1/4"}))
    level = ls.level_of(RIG.white_max)
    assert [lvl(out, white(1818, 1), ms(1, b)) for b in (1, 2, 3, 4)] == [level] * 4


# ---------------------------------------------------------------- strobe, uv ----


def test_strobe_roll_pulses_movers_and_colour_cells(room):
    script = room()
    out, _ = compile_(script, section(1, 4, strobe={"roll": [2, 2]}))
    step = 150                                                  # 1/16 at 100 BPM
    for node in (1167, rgb(1818, 1), rgb(1876, 48)):
        assert lvl(out, node, ms(2)) == FULL and lvl(out, node, ms(2) + step) == FULL
        assert lvl(out, node, ms(2) + step - 1) < FULL // 100
        assert not covered(ssf.track(out, node), ms(3) + 10)
    assert ssf.track(out, white(1818, 1)) == ssf.track(script, white(1818, 1))


def test_uv_on_is_one_manual_cue(room):
    script = room()
    out, cues = compile_(script, section(3, 4, uv="on"))
    cues = section_cues(cues)
    assert len(cues) == 1
    assert (cues[0].bar, cues[0].time_ms) == (3, ms(3))
    assert without_haze(out) == without_haze(script)


# ----------------------------------------------------------------------- haze ----

L = ls.level_of(0.5)


def flat_haze(out, end):
    for node in (1935, 1936):
        trk = ssf.track(out, node)
        assert trk.blocks.items == [ssf.Span(0, end)]
        assert {k.level for k in intensity(trk).keys} == {L}


def test_haze_holds_the_level_over_the_whole_track(room):
    script = room()                                     # haze nodes follow Main; give 1936 own keys
    fog = ssf.track(script, 1936); fog.lanes[0].keys = [Key(5000, FULL), Key(9000, 0)]
    fog.blocks = ssf.Section(1, [ssf.Span(5000, 9000)])
    out, cues = compile_(script, section(3, 4, movers="off"))
    flat_haze(out, ssf.script_end(script))
    assert [(c.bar, c.time_ms, c.fixture, c.what) for c in cues] == [
        (1, 0, "haze", "haze at 0.5, whole track: experimental: confirm the machine reacts")]
    assert ls.haze_problem(out, RIG, VENUES) is None


def test_haze_stays_flat_under_a_hue_section(room):          # materialise must not leak in
    out, _ = compile_(room(), section(1, 8, hue="pulse"))
    flat_haze(out, ssf.script_end(out))


def test_haze_covers_a_section_past_the_script_end(room):    # Review Focus 2
    out, _ = compile_(room(), section(200, 201, movers="off"))   # room() ends at 400_000 ms
    flat_haze(out, ssf.script_end(out)); assert ssf.script_end(out) >= ms(202) - 1


def test_haze_end_honours_the_track_length(room):
    out, _ = ls.compile_choreography(choreo(section(1, 2)), room(), RIG, VENUES, PRESETS,
                                     duration_ms=500_000)
    flat_haze(out, 500_000)


def test_no_sections_skips_the_grid_checks(room):
    many = tuple((158 + i * 1000, 100.0 + i) for i in range(9))      # 9 anchors
    script = room(tempo=many)
    out, _ = ls.compile_choreography(choreo(grid={"bpm": 90, "downbeat": "0:01.000"}),
                                     script, RIG, VENUES, PRESETS)
    changed = [t.node for t, b in zip(ssf.tracks(out), ssf.tracks(script)) if t != b]
    assert changed == [1935, 1936] and out.main == script.main
    with pytest.raises(ls.CompileError):
        compile_(script, section(1, 2))


def test_no_sections_needs_no_tempo_map(room):
    out, _ = ls.compile_choreography(choreo(), room(tempo=()), RIG, VENUES, PRESETS)
    flat_haze(out, 400_000)
    with pytest.raises(ls.CompileError, match="tempo map"):
        compile_(room(tempo=()), section(1, 2))


def test_a_haze_channel_the_venue_lacks_is_the_one_cue(room):
    venues = [ssf.VenueInfo("DJ Renan", VENUE_GUID, venue_nodes(drop={1936}))]
    script = room()
    out, cues = compile_(script, section(1, 2), venues=venues)
    assert [(c.bar, c.time_ms, c.fixture, c.what) for c in cues] == [
        (1, 0, "haze", "haze, whole track: skipped 'Main -  Lig Light LL-HZ600K - 2' is not in venue 'DJ Renan'")]
    assert ssf.track(out, 1936) == ssf.track(script, 1936)
    assert ssf.track(out, 1935).blocks.items == [ssf.Span(0, 400_000)]
    assert ls.haze_problem(out, RIG, venues) is None


def test_haze_problem_names_the_node(room):
    assert ls.haze_problem(room(), RIG, VENUES).startswith("haze node 1935:")   # follows Main
    out, _ = compile_(room(), section(1, 2))
    assert ls.haze_problem(out, RIG, VENUES, duration_ms=500_000).startswith("haze node 1935:")
    ssf.track(out, 1936).lanes[0].keys[-1].level = ls.level_of(0.4)
    assert ls.haze_problem(out, RIG, VENUES) == (
        "haze node 1936: intensity 0.4 at 400000 ms is not the rig's level 0.5")


def test_a_rig_without_haze_writes_none(room):
    rig = ls.Rig({k: f for k, f in RIG.fixtures.items() if f.kind != "haze"}, RIG.matrix_rows,
                 RIG.zone_order, RIG.white_max)
    script = room()
    out, cues = ls.compile_choreography(choreo(section(1, 2)), script, rig, VENUES, PRESETS)
    assert ssf.track(out, 1936) == ssf.track(script, 1936)
    assert [(c.fixture, c.what) for c in cues] == [
        ("haze", "haze, whole track: the rig has no haze; not compiled")]
    assert ls.haze_tracks(out, rig, VENUES) == [] and ls.haze_problem(out, rig, VENUES) is None


# ------------------------------------------------------------------- layers ----


def test_white_defaults_to_off_under_a_drawing():
    assert ls.section_layers(section(1, 2, matrix={"draw": "solid"}))["white"] == "off"
    assert ls.section_layers(section(1, 2, matrix="off"))["white"] == "off"
    assert ls.section_layers(section(1, 2, matrix="auto"))["white"] == "auto"
    assert ls.section_layers(section(1, 2))["movers"] == "auto"
    assert ls.section_layers(section(1, 2, matrix={"draw": "solid"}, white="auto"))["white"] == "auto"


def test_cells_resolve_by_name_under_their_unit():
    cells = ls.unit_cells(venue_nodes(), 1876)
    assert cells["master"] == master(1876)
    assert ls.cell_node(cells, 0, 0) == rgb(1876, 1)
    assert ls.cell_node(cells, 2, 7) == rgb(1876, 24)
    assert ls.cell_node(cells, 3, 0) == white(1876, 1)
    assert ls.cell_node(cells, 4, 0) == rgb(1876, 25)
    assert ls.cell_node(cells, 6, 7) == rgb(1876, 48)
    partial = ls.unit_cells([n for n in venue_nodes() if n.id != rgb(1876, 2)], 1876)
    assert ls.cell_node(partial, 0, 1) is None


# ------------------------------------------------------------------ Happier ----


def test_happier_compiles_on_a_synthetic_script(room):
    script = room()
    out, cues = ls.compile_choreography(ls.load_choreography(HAPPIER), script, RIG, VENUES, PRESETS)
    assert check(out) == []
    assert ssf.parse_script(ssf.serialize_script(out)) == out
    assert [(c.bar, c.fixture) for c in cues] == [(1, "haze")]
    assert lvl(out, 1167, ms(4)) == 0                          # intro: movers off
    assert lvl(out, 2, ms(68) + 1200) == 0                     # silence: even the chandelier
    assert lvl(out, rgb(1818, 1), ms(68) + 1200) == 0


def effective(script, trk, t):
    """What `trk` shows at `t`: its own level inside its spans, else Main's."""
    own = trk is script.main or covered(trk, t)
    return level_at(intensity(trk if own else script.main), t)


def moments(script, trk, start, end):
    """Every 10 ms of [start, end] plus every breakpoint of `trk` and Main inside it."""
    ts = set(range(start, end + 1, 10)) | {end}
    for lane in (intensity(trk), intensity(script.main)):
        ts |= {k.t for k in (lane.keys if lane else []) if start <= k.t <= end}
    return sorted(ts)


@pytest.mark.skipif(not REAL, reason="NEXTRACK_SOUNDSWITCH_REAL not set")
def test_happier_compiles_on_the_real_script():
    project = ssf.Project(Path(REAL))
    venues, presets = project.venues()
    choreo = ls.load_choreography(HAPPIER)
    script = ssf.parse_script(project.script_path(choreo.soundswitch).read_bytes())
    out, cues = ls.compile_choreography(choreo, script, RIG, venues, presets)
    assert check(out) == []
    assert ssf.parse_script(ssf.serialize_script(out)) == out
    g = ssf.grid(out)
    dj = next(v for v in venues if v.name == "DJ Renan")
    mover1 = ssf.track(out, next(n.id for n in dj.nodes if n.name == "Mover 1"))
    intro = (g.ms(1), g.ms(9) - 1)                             # bars 1–8: movers off
    assert all(effective(out, mover1, t) == 0 for t in moments(out, mover1, *intro))
    silence = (g.ms(68), g.ms(69) - 1)                         # bar 68: even the chandelier
    assert all(effective(out, out.main, t) == 0 for t in moments(out, out.main, *silence))
    kinds = {"haze" if c.fixture == "haze" else "uv" if "UV" in c.what else c.what for c in cues}
    assert kinds <= {"uv", "haze"}, cues
