"""The show compiler: spans, bridges, handovers, gestures, accents, provenance, the choreography."""
import copy

import yaml

import lightshow
from check_repo import load_yaml
from musical_map import slug
from show_gestures import GESTURES, Gesture, GestureSection
from show_language import compile_show, problems_show
from showdata import (FILE_1, FILE_2, GUID_2, SET_TRACKS, TRACK_1, TRACK_2, inputs, show_map, source,
                      two_track_show)

FOLDER = "lightshows/shows/teste"
PATH_1, PATH_2 = f"{FOLDER}/{FILE_1}", f"{FOLDER}/{FILE_2}"
SHOW_PATH = f"{FOLDER}/show.yml"


def one_track(cues, handover=None, map_data=None, show_changes=None, **keys):
    """A show of one track (Dançarina) with these cues, on the show.yml of `two_track_show`."""
    show = two_track_show()[0].show
    show.update(show_changes or {})
    data = {"track": TRACK_1, "story": "Uma música de teste.", "cues": cues, **keys}
    if handover is not None:
        data["handover"] = handover
    return (source(show, {FILE_1: data}),
            inputs({slug(TRACK_1): map_data or show_map()}, [SET_TRACKS[0]]))


def compiled(src, inp):
    show, findings = compile_show(src, inp)
    assert [f.message for f in findings] == []
    return show


def spans(track):
    return [(s.bars, s.name) for s in track.sections]


def found(findings):
    return [(f.path, f.line, f.rule, f.message) for f in findings]


def section(track, name):
    return next(s for s in track.sections if s.name == name)


def test_cue_stack_spans():
    t = compiled(*one_track([{"at": 9, "name": "a", "look": "respiracao"},
                             {"at": "drop.2", "name": "b", "look": "pulso"}],
                            handover={"at": "G", "look": "pulso"})).tracks[0]
    assert spans(t) == [((9, 20), "a"), ((21, 24), "b"), ((25, 32), "entrega")]
    handover = t.sections[-1]
    assert handover.origin.kind == "handover" and handover.origin.look == "pulso"
    assert handover.intent == two_track_show()[0].show["handover"]["intent"]
    # `at` defaults to G and `until` (exclusive) may stop the handover before the map's end
    t = compiled(*one_track([{"at": 9, "name": "a", "look": "respiracao"}],
                            handover={"look": "pulso", "until": 31, "name": "fim"})).tracks[0]
    assert spans(t) == [((9, 24), "a"), ((25, 30), "fim")]


def test_until_leaves_a_gap():
    t = compiled(*one_track([{"at": 9, "until": 13, "name": "a", "look": "respiracao"},
                             {"at": 17, "name": "b", "look": "pulso"}])).tracks[0]
    assert spans(t) == [((9, 12), "a"), ((17, 32), "b")]
    covered = {bar for s in t.sections for bar in range(s.bars[0], s.bars[1] + 1)}
    assert not covered & set(range(13, 17))
    # `end + 1` runs a cue to the map's last bar
    t = compiled(*one_track([{"at": 9, "until": "end + 1", "name": "a", "look": "respiracao"}])).tracks[0]
    assert spans(t) == [((9, 32), "a")]


def test_until_must_fit_between_at_and_the_next_start():
    _, findings = compile_show(*one_track([{"at": 9, "until": 9, "name": "a", "look": "pulso", "__line__": 3},
                                           {"at": 17, "name": "b", "look": "pulso"}]))
    assert found(findings) == [(PATH_1, 3, "show-source", "cue 'a': until 9 is not after its at 9")]
    _, findings = compile_show(*one_track([{"at": 9, "until": 18, "name": "a", "look": "pulso", "__line__": 3},
                                           {"at": 17, "name": "b", "look": "pulso"}]))
    assert found(findings) == [(PATH_1, 3, "show-source",
                                "cue 'a': until 18 is after cue 'b' starts at 17; until is the first bar "
                                "after the cue, so at most 17")]


def test_cues_must_increase():
    cues = [{"at": 9, "name": "a", "look": "respiracao", "__line__": 4},
            {"at": 9, "name": "b", "look": "pulso", "__line__": 7}]
    show, findings = compile_show(*one_track(cues))
    assert show is None
    assert found(findings) == [(PATH_1, 7, "show-source", "cue 'b' at 9 does not come after cue 'a' at 9")]
    cues[1]["at"] = "drop.1"
    _, findings = compile_show(*one_track(cues))
    assert [f.message for f in findings] == ["cue 'b' at 9 (drop.1) does not come after cue 'a' at 9"]


def test_handover_must_come_after_the_last_cue():
    _, findings = compile_show(*one_track([{"at": 25, "name": "a", "look": "pulso"}],
                                          handover={"look": "pulso", "__line__": 9}))
    assert found(findings) == [(PATH_1, 9, "show-source", "handover at 25 (G) does not come after cue 'a' at 25")]


def test_bridge_copies_the_previous_handover_without_accents():
    show, findings = compile_show(*two_track_show())
    assert findings == []
    second = show.tracks[1]
    bridge, handover = second.sections[0], show.tracks[0].sections[-1]
    assert bridge.name == "ponte" and bridge.bars[0] == 5            # the second map's B
    assert bridge.layers == {k: v for k, v in handover.layers.items() if k not in ("white", "strobe")}
    assert bridge.origin.kind == "bridge" and bridge.origin.path == show.tracks[0].path
    assert bridge.origin.line == handover.origin.line and bridge.origin.moment == handover.origin.moment
    assert handover.layers["white"] == {"accent": ["25.1"]} and "white" not in bridge.layers
    assert bridge.bars == (5, 8) and bridge.origin.track == TRACK_2 and bridge.origin.look == "pulso"
    assert bridge.intent == two_track_show()[0].show["bridge"]["intent"]
    assert bridge.layers is not handover.layers


def test_a_bridge_never_copies_bar_numbers():
    src, inp = two_track_show()
    handover = src.track_files[FILE_1]["handover"]
    handover.update({"with": {"movers": {"faster_from": "end - 2", "faster_every": "1/8"}}, "__line__": 30})
    show, findings = compile_show(src, inp)
    assert show is None
    assert found(findings) == [(PATH_1, 30, "show-source",
                                "handover: movers.faster_from 30 would be copied by the bridge into Voa Voa (Ao Vivo), "
                                "where the bars of this track mean nothing: move it to a cue before the handover, "
                                f"or write bridge: false in {FILE_2}")]
    src.track_files[FILE_2]["bridge"] = False
    assert compile_show(src, inp)[1] == []
    # raw accent and strobe bars in the look count too; the handover's own `accents:` do not
    src, inp = two_track_show()
    src.track_files[FILE_1]["handover"].update({"with": {"strobe": {"roll": [31, 32]}}, "accents": ["white"]})
    _, findings = compile_show(src, inp)
    assert [f.path for f in findings] == [PATH_1]
    assert "strobe.roll [31, 32]" in findings[0].message and "white" not in findings[0].message


def test_first_cue_at_b_leaves_no_room_for_the_bridge():
    for at in ("B", 3):
        src, inp = two_track_show()
        src.track_files[FILE_2]["cues"][0].update({"at": at, "__line__": 6})
        show, findings = compile_show(src, inp)
        assert show is None
        assert [(f.path, f.line, f.rule) for f in findings] == [(PATH_2, 6, "show-source")]
        assert "no room for the bridge" in findings[0].message and "bridge: false" in findings[0].message


def test_no_b_with_a_handover_before_is_a_finding():
    src, inp = two_track_show()
    inp.maps[slug(TRACK_2)]["hot_cues"] = {"A": "1.1", "G": "25.1"}
    show, findings = compile_show(src, inp)
    assert show is None
    assert [(f.path, f.rule) for f in findings] == [(PATH_2, "show-source")]
    message = findings[0].message
    assert "the map has no hot cue B (it has A, G)" in message
    assert "nextrack_map.py cues" in message and "bridge: false" in message


def test_bridge_false_skips_the_bridge():
    src, inp = two_track_show()
    src.track_files[FILE_2]["bridge"] = False
    show = compiled(src, inp)
    assert show.tracks[1].sections[0].name == "chegada"
    assert not any("bridge" in d for d in show.decisions)
    inp.maps[slug(TRACK_2)]["hot_cues"] = {"A": "1.1"}          # no B is fine without a bridge
    assert compile_show(src, inp)[1] == []
    # a show without `bridge` makes none
    src, inp = two_track_show()
    del src.show["bridge"]
    assert [s.origin.kind for s in compiled(src, inp).tracks[1].sections] == ["cue"] * 3


def test_g_without_handover_before_a_bridged_track():
    src, inp = two_track_show()
    del src.track_files[FILE_1]["handover"]
    src.track_files[FILE_1]["__line__"] = 1
    show, findings = compile_show(src, inp)
    assert show is None
    assert [(f.path, f.line, f.rule) for f in findings] == [(PATH_1, 1, "show-source")]
    assert "G" in findings[0].message and "handover" in findings[0].message
    assert f"bridge: false in {FILE_2}" in findings[0].message
    src.track_files[FILE_2]["bridge"] = False                     # the next track takes no bridge
    show = compiled(src, inp)
    assert spans(show.tracks[0])[-1] == ((21, 32), "virada")
    src, inp = two_track_show()                                   # no G: nothing to hand over
    del src.track_files[FILE_1]["handover"]
    inp.maps[slug(TRACK_1)]["hot_cues"] = {"A": "1.1", "B": "5.1"}
    assert compile_show(src, inp)[1] == []


def bars_show(bars):
    """`two_track_show` with `bridge.bars`: B 5 and G 25 on both maps, Voa Voa's first cue at 9."""
    src, inp = two_track_show()
    src.show["bridge"]["bars"] = bars
    return src, inp


def test_bridge_bars_cuts_bridge_and_handover():
    show = compiled(*bars_show(4))
    assert spans(show.tracks[0])[-1] == ((25, 28), "entrega")       # G 25 for 4 bars
    assert spans(show.tracks[1])[0] == ((5, 8), "ponte")            # B 5 for 4 bars: the first cue is at 9
    assert "Dançarina: handover runs to bar 28 (bridge.bars 4)" in show.decisions
    # a wider window: the bridge stops at the first cue and the handover at the map's end, as without bars
    show = compiled(*bars_show(16))
    assert spans(show.tracks[0])[-1] == ((25, 32), "entrega") and spans(show.tracks[1])[0] == ((5, 8), "ponte")
    assert show.decisions == compiled(*two_track_show()).decisions
    # an until inside the window holds; a handover with an at opens its window there
    src, inp = bars_show(4)
    src.track_files[FILE_1]["handover"]["until"] = 27
    assert spans(compiled(src, inp).tracks[0])[-1] == ((25, 26), "entrega")
    src, inp = bars_show(4)
    src.track_files[FILE_1]["handover"]["at"] = 27
    assert spans(compiled(src, inp).tracks[0])[-2:] == [((21, 26), "virada"), ((27, 30), "entrega")]
    # a missing handover's finding names the window
    src, inp = bars_show(4)
    del src.track_files[FILE_1]["handover"]
    message = compile_show(src, inp)[1][0].message
    assert "add a handover here (its look plays from G for 4 bars (bridge.bars 4) and the bridge copies it)" in message


def test_bridge_bars_first_cue_too_late():
    src, inp = bars_show(3)
    src.track_files[FILE_2]["cues"][0]["__line__"] = 6
    show, findings = compile_show(src, inp)
    assert show is None
    assert found(findings) == [(PATH_2, 6, "show-source", "cue 'chegada' at 9 (drop.1): the bridge ends at bar 7 "
                                                          "(bridge.bars 3); start a cue at or before bar 8")]
    # a first cue at B + bars ends the bridge in time
    src.track_files[FILE_2]["cues"][0]["at"] = 8
    assert spans(compiled(src, inp).tracks[1])[:2] == [((5, 7), "ponte"), ((8, 16), "chegada")]
    # with no cue, the handover must start in time; with neither, the track file is where to start one
    src, inp = bars_show(4)
    second = src.track_files[FILE_2]
    second.update({"cues": [], "handover": {"look": "pulso", "__line__": 7}, "__line__": 1})
    assert found(compile_show(src, inp)[1]) == [
        (PATH_2, 7, "show-source", "handover at 25 (G): the bridge ends at bar 8 (bridge.bars 4); start a cue at or "
                                   "before bar 9")]
    del second["handover"]
    assert found(compile_show(src, inp)[1]) == [
        (PATH_2, 1, "show-source", "the bridge ends at bar 8 (bridge.bars 4); start a cue at or before bar 9")]


def test_bridge_bars_handover_until_too_late():
    src, inp = bars_show(4)
    src.track_files[FILE_1]["handover"].update({"until": "end - 2", "__line__": 30})
    show, findings = compile_show(src, inp)
    assert show is None
    assert found(findings) == [(PATH_1, 30, "show-source",
                                "handover: until 30 (end - 2): the handover ends at bar 28 (bridge.bars 4); write an "
                                "until at or before bar 29, or leave it out")]
    src.track_files[FILE_1]["handover"]["until"] = 29
    assert spans(compiled(src, inp).tracks[0])[-1] == ((25, 28), "entrega")


def test_bridge_bars_bounds():
    for bars in (0, 33, True, "4", 4.5):
        assert found(compile_show(*bars_show(bars))[1]) == [
            (SHOW_PATH, 0, "show-source", f"bridge.bars {bars!r} is not a whole number of bars from 1 to 32")]
    for bars in (1, 32):
        assert problems_show(bars_show(bars)[0].show) == []
    src, inp = two_track_show()
    src.show["handover"]["bars"] = 4                                # only the bridge takes bars
    assert found(compile_show(src, inp)[1]) == [
        (SHOW_PATH, 0, "show-source", "handover: unexpected key 'bars' (allowed: name, intent)")]


def test_gesture_sections_get_the_cue_provenance():
    src, inp = two_track_show()
    cues = src.track_files[FILE_1]["cues"]
    del cues[0]["role"]
    cues[1].update({"role": "arrival", "moment": "espiral", "__line__": 12})
    show = compiled(src, inp)
    spiral = [s for s in show.tracks[0].sections if s.origin.gesture == "spiral"]
    assert [(s.bars, s.name) for s in spiral] == [((17, 18), "espiral-1-2"), ((19, 20), "espiral-1-4")]
    assert [s.origin.role for s in spiral] == ["arrival", None]
    assert all(s.origin.moment == "espiral" and s.origin.kind == "cue" and s.origin.look is None
               and s.origin.path == PATH_1 and s.origin.line == 12 and s.origin.track == TRACK_1
               and s.intent == cues[1]["intent"] for s in spiral)
    # gesture_defaults are merged under `with`: the show's colours, resolved from the palette
    assert [s.layers["movers"]["colour"] for s in spiral] == ["#0A2CFF", "#6A1CFF"]
    # a sequence step with `look: <name>` reports it
    t = compiled(*one_track([{"at": 17, "until": 21, "name": "seq", "gesture": "sequence", "moment": "m",
                              "with": {"steps": [{"bars": 2, "look": "respiracao"},
                                                 {"bars": 2, "look": {"hue": "dark"}, "name": "escuro"}]}}])).tracks[0]
    assert [(s.name, s.origin.look, s.origin.gesture, s.origin.moment) for s in t.sections] == [
        ("seq-1", "respiracao", "sequence", "m"), ("escuro", None, "sequence", "m")]


def test_gesture_problems_point_at_the_cue():
    src, inp = two_track_show()
    src.track_files[FILE_1]["cues"][1].update({"with": {"bars": [2, 3]}, "__line__": 12})
    _, findings = compile_show(src, inp)
    assert found(findings) == [(PATH_1, 12, "show-source",
                                "cue 'espiral': spiral: bars add up to 5, the cue spans 4 bars (17-20)")]
    src.track_files[FILE_1]["cues"][1].update({"gesture": "espiral"})
    _, findings = compile_show(src, inp)
    assert found(findings) == [(PATH_1, 12, "show-source",
                                "cue 'espiral': unknown gesture 'espiral'; gestures: sequence, spiral")]


def test_a_gesture_bug_is_a_finding(monkeypatch):
    def raises(ctx, params):
        raise ZeroDivisionError("oops")

    def bad_layers(ctx, params):
        return [GestureSection((ctx.start, ctx.end), "x", None, ["hue"])], []

    for fn, says in ((raises, "failed (ZeroDivisionError('oops'))"), (bad_layers, "returned layers ['hue']")):
        monkeypatch.setitem(GESTURES, "bug-test", Gesture("bug-test", "A bug.", {}, {}, 1, fn))
        _, findings = compile_show(*one_track([{"at": 9, "name": "a", "gesture": "bug-test", "__line__": 4}]))
        assert [(f.line, f.rule) for f in findings] == [(4, "show-source")]
        assert says in findings[0].message and "a bug in scripts/show_gestures.py" in findings[0].message


def test_accents_land_on_the_first_section():
    show = compiled(*two_track_show())
    virada = section(show.tracks[0], "virada")
    assert virada.layers["white"] == {"accent": ["21.1"]} and virada.layers["strobe"] == {"hit": ["21.1"]}
    assert section(show.tracks[1], "final").layers["strobe"] == {"roll": [21, 32]}
    # on a gesture cue, only its first section
    src, inp = two_track_show()
    src.track_files[FILE_1]["cues"][1]["accents"] = ["white"]
    t = compiled(src, inp).tracks[0]
    assert section(t, "espiral-1-2").layers["white"] == {"accent": ["17.1"]}
    assert "white" not in section(t, "espiral-1-4").layers


def test_an_accent_on_a_layer_the_look_sets_is_a_finding():
    src, inp = two_track_show()
    cue = src.track_files[FILE_1]["cues"][2]
    cue["look"]["white"] = {"flash": "1/4"}
    cue["__line__"] = 20
    _, findings = compile_show(src, inp)
    assert [(f.path, f.line) for f in findings] == [(PATH_1, 20)]
    assert "accent 'white'" in findings[0].message and "remove the accent" in findings[0].message
    src, inp = two_track_show()
    src.track_files[FILE_1]["cues"][2]["accents"] = ["strobe", "strobe-roll"]
    _, findings = compile_show(src, inp)
    assert len(findings) == 1 and "accent 'strobe-roll'" in findings[0].message


def test_palette_and_faster_from_are_resolved():
    show = compiled(*two_track_show())
    chegada = section(show.tracks[0], "chegada")
    assert chegada.layers["movers"]["colour"] == "#0A2CFF" and chegada.layers["hue"]["colour"] == "#FF0A2A"
    subida = section(show.tracks[1], "subida")
    assert subida.layers["movers"] == {"move": "pingpong", "every": "1/2", "colour": "#0A2CFF",
                                       "faster_from": 19, "faster_every": "1/4", "position": "Up"}
    src, inp = two_track_show()
    cue = src.track_files[FILE_1]["cues"][2]
    cue["look"]["hue"]["colour"] = "rosa"
    cue["__line__"] = 9
    _, findings = compile_show(src, inp)
    assert found(findings) == [(PATH_1, 9, "show-source",
                                "cue 'virada': colour 'rosa' is not in the palette (azul, vermelho, violeta) "
                                "nor #RRGGBB")]
    src, inp = two_track_show()
    src.track_files[FILE_2]["cues"][1]["with"]["movers"]["faster_from"] = "drop.3"
    _, findings = compile_show(src, inp)
    assert [f.message for f in findings] == [
        "cue 'subida': faster_from drop.3: the map has 2 drop sections (9, 21)"]


def test_look_problems_point_at_the_cue():
    src, inp = two_track_show()
    src.track_files[FILE_2]["cues"][2].update({"look": "pulsoo", "__line__": 14})
    _, findings = compile_show(src, inp)
    assert found(findings) == [(PATH_2, 14, "show-source",
                                "cue 'final': look 'pulsoo' is not defined; did you mean 'pulso'?")]


def test_anchor_problems_point_at_the_cue():
    src, inp = two_track_show()
    src.track_files[FILE_2]["cues"][2].update({"at": "drop.4", "__line__": 14})
    _, findings = compile_show(src, inp)
    assert found(findings) == [(PATH_2, 14, "show-source",
                                "cue 'final': drop.4: the map has 2 drop sections (9, 21)")]
    _, findings = compile_show(*one_track([{"at": 9, "name": "a", "look": "pulso"}],
                                          handover={"look": "pulso", "__line__": 5},
                                          map_data=show_map(hot_cues={"A": "1.1", "B": "5.1"})))
    assert [(f.line, f.message) for f in findings] == [
        (5, "handover: G: the map has no hot cue G (it has A, B); a handover starts at G unless it has an at")]


def test_choreography_comes_from_the_map():
    show, _ = compile_show(*two_track_show())
    c = show.tracks[0].choreography
    assert c["soundswitch"] == show.tracks[0].map["soundswitch"] and c["base"] == "autoscript"
    assert c["grid"] == {"bpm": 120, "downbeat": show.tracks[0].map["grid"]["downbeat"]}
    assert lightshow.problems_choreography(c, None) == []
    assert isinstance(c["grid"]["bpm"], int)
    assert list(c) == ["track", "soundswitch", "grid", "story", "base", "sections"]
    second = show.tracks[1].choreography
    assert list(second) == ["track", "soundswitch", "grid", "story", "budget", "base", "sections"]
    assert second["soundswitch"] == show.tracks[1].map["soundswitch"] != c["soundswitch"]
    assert second["track"] == TRACK_2 and second["budget"] == two_track_show()[0].track_files[FILE_2]["budget"]
    assert lightshow.problems_choreography(second, None) == []
    assert list(c["sections"][-1]) == ["bars", "name", "intent", "movers", "matrix", "white", "hue"]
    assert c["sections"][-1]["bars"] == [25, 32]
    assert [list(s) for s in second["sections"]][0] == ["bars", "name", "intent", "movers", "matrix", "hue"]
    assert "intent" not in second["sections"][1]                  # chegada of Voa Voa has none
    t = show.tracks[0]
    assert (t.track, t.slug, t.path) == (TRACK_1, slug(TRACK_1), PATH_1)
    assert [s["bars"] for s in c["sections"]] == [list(s.bars) for s in t.sections]
    # a fractional bpm stays a float; a track with nothing gets no sections
    m = show_map(grid={"bpm": 123.5, "downbeat": "0:00.061", "anchors": [[61, 123.5]], "offset_ms": -5})
    t = compiled(*one_track([], map_data=m)).tracks[0]
    assert t.choreography["grid"]["bpm"] == 123.5 and t.choreography["sections"] == [] and t.sections == []


def test_the_track_must_be_its_maps():
    src, inp = two_track_show()
    src.track_files[FILE_1]["track"] = "Pedro Sampaio — Dancarina"
    _, findings = compile_show(src, inp)
    assert found(findings) == [(PATH_1, 0, "show-source",
                                "track 'Pedro Sampaio — Dancarina' is not written as in its map: "
                                f"write 'Pedro Sampaio — Dançarina' (lightshows/maps/{FILE_1})")]


def test_a_track_written_as_the_set_writes_it():
    # the block abbreviates the title; the file is named like the map, the track is not
    src, inp = two_track_show()
    src.track_files[FILE_2].update({"track": "Chiclete com Banana — Voa Voa", "__line__": 1})
    show, findings = compile_show(src, inp)
    assert show is None
    assert found(findings) == [(PATH_2, 1, "show-source",
                                "track 'Chiclete com Banana — Voa Voa' is not written as in its map: "
                                f"write {TRACK_2!r} (lightshows/maps/{FILE_2})")]
    inp.set_tracks, inp.set_problem = None, "no set"               # the same without the set's order
    assert [f.message for f in compile_show(src, inp)[1]][1:] == [findings[0].message]
    # misnamed too: the right name is the map's
    src, inp = two_track_show()
    src.track_files["voa-voa.yml"] = {**src.track_files.pop(FILE_2), "track": "Chiclete com Banana — Voa Voa"}
    _, findings = compile_show(src, inp)
    assert [f.message for f in findings] == [
        f"file name 'voa-voa.yml' does not match its track 'Chiclete com Banana — Voa Voa': rename it to {FILE_2}",
        f"track 'Chiclete com Banana — Voa Voa' is not written as in its map: write {TRACK_2!r} "
        f"(lightshows/maps/{FILE_2})"]
    # two maps that both match: name them, suggest neither
    src, inp = two_track_show()
    src.track_files[FILE_2]["track"] = "Chiclete com Banana — Voa Voa"
    inp.maps["chiclete-com-banana-voa-voa-remix"] = show_map(track="Chiclete com Banana — Voa Voa (Remix)",
                                                            soundswitch=GUID_2)
    _, findings = compile_show(src, inp)
    assert [f.message for f in findings] == [
        "track 'Chiclete com Banana — Voa Voa' matches 2 musical maps (lightshows/maps/"
        "chiclete-com-banana-voa-voa-ao-vivo.yml, lightshows/maps/chiclete-com-banana-voa-voa-remix.yml): "
        "write it as one of them does"]


TRACK_TEXT = """\
track: Pedro Sampaio — Dançarina
story: Teste.
cues:
  - at: 9
    name: chegada
    look: respiracao
  - at: 17
    name: errado
    look: espiral-errada
"""


def test_lightshow_problems_point_at_the_cue():
    show = two_track_show()[0].show
    show["looks"]["espiral-errada"] = {"matrix": {"draw": "spiral", "rate": "1bar", "colour": "azul"}}
    src = source(show, {FILE_1: load_yaml(TRACK_TEXT)})
    _, findings = compile_show(src, inputs({slug(TRACK_1): show_map()}, [SET_TRACKS[0]]))
    draws = ", ".join(lightshow.MATRIX_DRAWS)
    assert found(findings) == [(PATH_1, 7, "show-source",
                                f"cue 'errado': matrix: draw 'spiral' is not one of {draws}")]
    # a section a gesture made names itself
    src, inp = two_track_show()
    src.track_files[FILE_1]["cues"][1].update({"gesture": "sequence", "__line__": 12, "with": {"steps": [
        {"bars": 2, "look": "respiracao"}, {"bars": 2, "look": {"matrix": {"draw": "spiral"}}, "name": "torto"}]}})
    _, findings = compile_show(src, inp)
    assert found(findings) == [(PATH_1, 12, "show-source",
                                f"cue 'espiral' (section 'torto'): matrix: draw 'spiral' is not one of {draws}")]


def test_track_files_against_the_set():
    src, inp = two_track_show()                                   # missing file
    del src.track_files[FILE_2]
    show, findings = compile_show(src, inp)
    assert show is None
    assert found(findings) == [(SHOW_PATH, 0, "show-source",
                                f"set track 2, Chiclete com Banana — Voa Voa, has no track file: add {FILE_2} "
                                f"with track: {TRACK_2}")]
    src, inp = two_track_show()                                   # extra file
    src.track_files["pedro-sampaio-outra.yml"] = {"track": "Pedro Sampaio — Outra", "story": "x", "cues": []}
    _, findings = compile_show(src, inp)
    assert [(f.path, f.rule) for f in findings] == [(f"{FOLDER}/pedro-sampaio-outra.yml", "show-source")]
    assert "'Pedro Sampaio — Outra' is not in the set sets/teste.md" in findings[0].message
    src, inp = two_track_show()                                   # wrong file name
    src.track_files["voa-voa.yml"] = src.track_files.pop(FILE_2)
    _, findings = compile_show(src, inp)
    assert found(findings) == [(f"{FOLDER}/voa-voa.yml", 0, "show-source",
                                f"file name 'voa-voa.yml' does not match its track {TRACK_2!r}: rename it to {FILE_2}")]
    src, inp = two_track_show()                                   # a track twice in the set
    inp.set_tracks.append(SET_TRACKS[0])
    _, findings = compile_show(src, inp)
    assert [(f.path, f.rule) for f in findings] == [(SHOW_PATH, "show-source")]
    assert "set track 3, Pedro Sampaio — Dançarina, is set track 1 again" in findings[0].message
    src, inp = two_track_show()                                   # two files for one set track
    src.track_files["pedro-sampaio-dancarina-remix.yml"] = {"track": "Pedro Sampaio — Dançarina (Remix)",
                                                            "story": "x", "cues": []}
    _, findings = compile_show(src, inp)
    assert found(findings) == [(SHOW_PATH, 0, "show-source",
                                "set track 1, Pedro Sampaio — Dançarina, has 2 track files "
                                f"(pedro-sampaio-dancarina-remix.yml, {FILE_1}): keep one")]


def test_schema_problems_are_findings_at_their_file():
    src, inp = two_track_show()
    src.show["looks"]["pulso"]["extends"] = "nada"
    _, findings = compile_show(src, inp)
    assert found(findings) == [(SHOW_PATH, 0, "show-source", "looks.pulso: extends 'nada', which is not a look")]
    src, inp = two_track_show()
    src.show["gesture_defaults"]["espiral"] = {}
    _, findings = compile_show(src, inp)
    assert found(findings) == [(SHOW_PATH, 0, "show-source",
                                "gesture_defaults.espiral: unknown gesture 'espiral'; gestures: sequence, spiral")]
    src, inp = two_track_show()
    del src.show["story"]
    src.track_files[FILE_2]["cues"][0]["role"] = "chegada"
    _, findings = compile_show(src, inp)
    assert found(findings) == [(SHOW_PATH, 0, "show-source", "show.yml: missing key story"),
                               (PATH_2, 0, "show-source", "cues[1].role 'chegada' is not one of arrival")]
    src, inp = two_track_show()
    src.track_files[FILE_2]["story"] = ""                          # lightshow: a non-empty story
    _, findings = compile_show(src, inp)
    assert found(findings) == [(PATH_2, 0, "show-source", "story '' is not a non-empty string")]


def test_a_handover_needs_a_name_and_an_intent():
    src, inp = one_track([{"at": 9, "name": "a", "look": "pulso"}], handover={"look": "pulso", "__line__": 5})
    del src.show["handover"]
    _, findings = compile_show(src, inp)
    assert [(f.line, f.message) for f in findings] == [
        (5, "handover: needs a name and an intent, and show.yml has no handover to take them from: "
            "add handover: {name, intent} to show.yml or write them here")]
    t = compiled(*one_track([{"at": 9, "name": "a", "look": "pulso"}],
                            handover={"look": "pulso", "name": "fim", "intent": "O fim."},
                            show_changes={"handover": {"name": "x", "intent": "y"}})).tracks[0]
    assert (t.sections[-1].name, t.sections[-1].intent) == ("fim", "O fim.")


def test_missing_or_unreadable_inputs():
    src, inp = two_track_show()
    del inp.maps[slug(TRACK_2)]
    show, findings = compile_show(src, inp)
    assert show is None
    assert found(findings) == [(PATH_2, 0, "show-source",
                                f"no musical map for {TRACK_2}: run uv run scripts/nextrack_map.py analyze "
                                f"\"{TRACK_2}\"")]
    src, inp = two_track_show()
    inp.set_tracks, inp.set_problem = None, "set sets/teste.md does not exist"
    show, findings = compile_show(src, inp)
    assert show is None
    assert found(findings) == [(SHOW_PATH, 0, "show-source", "set sets/teste.md does not exist")]
    # without the set, each track still compiles alone: its own problems are reported
    src.track_files[FILE_2]["cues"][0]["look"] = "pulsoo"
    assert [f.path for f in compile_show(src, inp)[1]] == [SHOW_PATH, PATH_2]


def test_decisions_name_bridges_and_default_ends():
    show = compiled(*two_track_show())
    assert show.decisions == [
        "Dançarina: cue 'virada' runs to bar 24 (the handover)",
        "Voa Voa (Ao Vivo): bridge 5-8 copies the handover of Dançarina (look pulso)",
        "Voa Voa (Ao Vivo): cue 'final' runs to bar 32 (the map's end)",
    ]
    src, inp = two_track_show()
    src.track_files[FILE_1]["handover"]["look"] = {"hue": "dark"}
    src.track_files[FILE_2]["cues"][2]["until"] = "end + 1"
    assert compiled(src, inp).decisions == [
        "Dançarina: cue 'virada' runs to bar 24 (the handover)",
        "Voa Voa (Ao Vivo): bridge 5-8 copies the handover of Dançarina (inline)",
    ]


def test_the_compiled_show():
    src, inp = two_track_show()
    show = compiled(src, inp)
    assert (show.show_id, show.folder) == ("teste", FOLDER)
    assert show.data == src.show and show.data is not src.show
    assert [t.track for t in show.tracks] == [TRACK_1, TRACK_2]
    assert spans(show.tracks[0]) == [((9, 16), "chegada"), ((17, 18), "espiral-1-2"), ((19, 20), "espiral-1-4"),
                                     ((21, 24), "virada"), ((25, 32), "entrega")]
    assert spans(show.tracks[1]) == [((5, 8), "ponte"), ((9, 16), "chegada"), ((17, 20), "subida"),
                                     ((21, 32), "final")]
    assert [s.origin.role for s in show.tracks[1].sections] == [None, "arrival", None, None]
    assert section(show.tracks[1], "chegada").layers["matrix"] == {"draw": "zigzag", "rate": "1/8",
                                                                  "colour": "#FF0A2A", "mirror": True}


def test_line_keys_and_yaml_words_never_reach_the_layers():
    src, inp = two_track_show()
    src.show["looks"]["breu"] = {"movers": "off", "matrix": "off", "hue": "dark"}
    src.track_files[FILE_2]["cues"].insert(2, {"at": 20, "name": "breu", "look": "breu"})
    show_text = yaml.safe_dump(src.show, allow_unicode=True).replace("'off'", "off")
    files = {name: load_yaml(yaml.safe_dump(data, allow_unicode=True)) for name, data in src.track_files.items()}
    loaded = source(load_yaml(show_text), files)
    assert loaded.show["looks"]["breu"]["movers"] is False         # YAML 1.1 read the unquoted word
    show = compiled(loaded, inp)
    assert "__line__" not in repr([t.choreography for t in show.tracks] + [t.sections for t in show.tracks])
    assert "__line__" not in repr(show.data)
    breu = section(show.tracks[1], "breu")
    assert breu.layers == {"movers": "off", "matrix": "off", "hue": "dark"} and breu.bars == (20, 20)
    assert breu.origin.line > 0
    assert show.tracks[0].choreography == compiled(*two_track_show()).tracks[0].choreography


def test_every_gesture_example_compiles():
    for name, g in GESTURES.items():
        src, inp = one_track([{"at": 1, "until": 1 + g.example_bars, "name": "gesto", "gesture": name,
                               "with": copy.deepcopy(g.example)}])
        del src.show["gesture_defaults"]
        show, findings = compile_show(src, inp)
        assert findings == [], name
        t = show.tracks[0]
        assert t.sections[0].bars[0] == 1 and t.sections[-1].bars[1] == g.example_bars, name
        assert lightshow.problems_choreography(t.choreography, None) == [], name


def _defaults_at(src, line=20):
    """Give `gesture_defaults` and its `spiral` mapping the lines the loader would."""
    defaults = src.show["gesture_defaults"]
    defaults["__line__"] = line
    defaults["spiral"]["__line__"] = line + 1


def test_an_unknown_gesture_defaults_key_is_one_finding_at_show_yml():
    src, inp = two_track_show()
    _defaults_at(src)
    spiral = src.show["gesture_defaults"]["spiral"]
    spiral["rate"] = spiral.pop("rates")
    _, findings = compile_show(src, inp)
    assert found(findings) == [(SHOW_PATH, 21, "show-source",
                                "gesture_defaults.spiral: unknown parameter 'rate'; did you mean 'rates'?")]
    # a gesture no cue calls is checked too; without a close match, the parameters are listed
    src, inp = two_track_show()
    src.show["gesture_defaults"]["sequence"] = {"__line__": 30, "pasos": []}
    _, findings = compile_show(src, inp)
    assert found(findings) == [(SHOW_PATH, 30, "show-source",
                                "gesture_defaults.sequence: unknown parameter 'pasos'; parameters: steps")]


def _spiral_in_both_tracks(src):
    """The second track calls the spiral too (its break, 17-20), with only its bars."""
    src.track_files[FILE_2]["cues"][1] = {"at": "break.1", "name": "espiral", "gesture": "spiral",
                                          "with": {"bars": [2, 2]}, "__line__": 9}


def test_a_bad_gesture_default_is_reported_once_at_show_yml():
    src, inp = two_track_show()
    _defaults_at(src)
    _spiral_in_both_tracks(src)
    src.show["gesture_defaults"]["spiral"]["rates"] = ["1/3", "1/4"]
    _, findings = compile_show(src, inp)
    assert found(findings) == [(SHOW_PATH, 21, "show-source",
                                "spiral: rates[0] '1/3' is not a rate (1/16, 1/8, 1/4, 1/2, <n>bar) "
                                "(from gesture_defaults.spiral in show.yml)")]
    # a palette name in the defaults that the palette lacks: the same, once, at show.yml
    src, inp = two_track_show()
    _defaults_at(src)
    _spiral_in_both_tracks(src)
    src.show["gesture_defaults"]["spiral"]["colours"] = ["azul", "rosa"]
    _, findings = compile_show(src, inp)
    assert found(findings) == [(SHOW_PATH, 21, "show-source",
                                "colour 'rosa' is not in the palette (azul, vermelho, violeta) nor #RRGGBB "
                                "(from gesture_defaults.spiral in show.yml)")]


def test_a_cue_that_overrides_a_bad_default_has_no_finding():
    src, inp = two_track_show()
    src.show["gesture_defaults"]["spiral"].update(rates=["1/3", "1/4"], colours=["azul", "rosa"])
    src.track_files[FILE_1]["cues"][1]["with"].update(rates=["1/2", "1/4"], colours=["azul", "violeta"])
    assert compile_show(src, inp)[1] == []
    # the cue's own bad value stays a finding at the cue
    src.track_files[FILE_1]["cues"][1].update({"__line__": 12})
    src.track_files[FILE_1]["cues"][1]["with"]["rates"] = ["1/5", "1/4"]
    _, findings = compile_show(src, inp)
    assert found(findings) == [(PATH_1, 12, "show-source",
                                "cue 'espiral': spiral: rates[0] '1/5' is not a rate (1/16, 1/8, 1/4, 1/2, <n>bar)")]


def test_an_invalid_map_is_not_a_missing_one():
    src, inp = two_track_show()
    del inp.maps[slug(TRACK_2)]
    inp.invalid_maps = {slug(TRACK_2)}
    show, findings = compile_show(src, inp)
    assert show is None
    assert found(findings) == [(PATH_2, 0, "show-source",
                                f"lightshows/maps/{FILE_2} is not a valid map: fix its musical-map finding "
                                "(or redo it with uv run scripts/nextrack_map.py analyze)")]


def test_a_section_number_out_of_range_points_at_the_track_file(monkeypatch):
    import show_language

    for message in ("section 99 (x): matrix: boom", "section 0: matrix: boom"):
        monkeypatch.setattr(show_language, "problems_choreography", lambda c, r, m=message: [m])
        _, findings = compile_show(*one_track([{"at": 9, "name": "a", "look": "pulso"}], __line__=2))
        assert found(findings) == [(PATH_1, 2, "show-source", message)]
