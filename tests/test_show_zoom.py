"""The zoom (show_zoom.py): a moment at 1/16 of a beat, the music lanes from the map on top and
the light lanes below, sampled with the compiler's own generators.

The base show is `two_track_show`, at 120 BPM from 61 ms: a beat is 500 ms, a 1/16 step 125 ms.
Dançarina plays the autoscript in bars 1-8, chegada 9-16 (look respiracao), the spiral 17-18
(pingpong 1/2, azul, Crossed Over and Up) and 19-20 (pingpong 1/4, violeta, Dance Floor
Centre), virada 21-24 (blink 1/4, solid 1/8, all vermelho, white and strobe on 21.1) and its
handover entrega 25-32. The palette's legend letters are a azul, v vermelho, i violeta (the
initial, else the next free letter of the name). The house rig is assumed: movers NE (mover 0)
and SE (mover 1), Vorlanes NW (unit 0) and SW (unit 1)."""
import test_lightshow_compile as lc
from mapdata import chunks, good_map
from test_lightshow_compile import choreo, room  # noqa: F401  (room: the house venue fixture)

import lightshow as ls
import show_room
import show_zoom as sz
import soundswitch_format as ssf
from show_language import CompiledSection, CompiledShow, CompiledTrack, Provenance, compile_show
from showdata import FILE_1, two_track_show

BAR = 16


def compiled(src, inp):
    show, findings = compile_show(src, inp)
    assert findings == [], findings
    return show


def base():
    return compiled(*two_track_show())


def with_look(look: dict, cue: int = 0):
    """`two_track_show` with Dançarina's cue `cue` (0: chegada, 9-16) playing an inline look."""
    src, inp = two_track_show()
    entry = src.track_files[FILE_1]["cues"][cue]
    entry["look"] = look
    entry.pop("with", None)
    return compiled(src, inp)


def rows(text: str) -> dict[str, list[str]]:
    """Each lane of a zoom by its label: the bar cells between the `|` marks."""
    out = {}
    for line in text.splitlines():
        if "|" in line:
            label, *cells = line.split("|")
            out[label.strip()] = cells
    return out


def _aim(preset, status="configured", fallback=None):
    out = {"figure": "uma figura", "preset": preset, "status": status, "targets": {"mover-ne": [1, 1, 1]}}
    return out | ({"fallback": fallback} if fallback else {})


ROOM = show_room.load_room({
    "size": {"x": 5.0, "y": 4.0, "z": 2.6}, "assumed": True,
    "fixtures": {"mover-ne": [5, 4, 2.3]}, "booth": [2.5, 4, 1.2],
    "aims": {"coluna": _aim("Up"), "cruzado": _aim("Crossed Over"),
             "centro-da-pista": _aim("Dance Floor Centre"), "apice": _aim("Apex", "pending", "coluna")},
})


# ------------------------------------------------------------------- music --


def test_zoom_music_lanes_come_from_the_map():
    show = base()
    data = show.tracks[0].map
    n = 32 * BAR
    lanes = {
        "kick": ("onsets", "".join("9..7"[i % 4] if i % 3 else "." for i in range(n))),
        "perc": ("onsets", "".join(".5"[i % 2] for i in range(n))),
        "bass": ("steps", "".join(str(i % 10) for i in range(n))),
        "vocals": ("steps", "".join(str((i // BAR) % 10) for i in range(n))),
        "other": ("steps", "".join(str((i * 7) % 10) for i in range(n))),
    }
    for voice, (group, text) in lanes.items():
        data[group][voice] = chunks(text)
    out = rows(sz.render_zoom(show, 0, 21, 3, 1, [], None))
    assert out[""] == [str(b).ljust(BAR) for b in range(18, 23)]
    for voice, (_, text) in lanes.items():
        assert out[voice] == [text[(b - 1) * BAR:b * BAR] for b in range(18, 23)], voice


# ---------------------------------------------------------------- the light --


def test_zoom_movers_pingpong_alternate():
    show = with_look({"movers": {"move": "pingpong", "every": "1/8", "colour": "vermelho", "position": "Up"},
                      "matrix": "off", "hue": "dark"})
    out = rows(sz.render_zoom(show, 0, 12, 1, 1, [], None))
    assert out["section"] == ["chegada".ljust(BAR)] * 3
    assert out["mover NE"] == ["VV..VV..VV..VV.."] * 3      # mover 0: the even steps
    assert out["mover SE"] == ["..VV..VV..VV..VV"] * 3      # mover 1: the odd ones
    assert out["vorl. NW"] == out["vorl. SW"] == ["." * BAR] * 3
    assert out["lustre"] == ["." * BAR] * 3


def test_zoom_matrix_pingpong_alternates_units():
    show = with_look({"movers": "off",
                      "matrix": {"draw": "columns", "rate": "1/8", "colour": "azul", "pingpong": True},
                      "hue": "dark"})
    out = rows(sz.render_zoom(show, 0, 12, 1, 1, [], None))
    # a cell pulses for one step of the draw (1/8, two 1/16 steps): full, then below half
    assert out["vorl. NW"] == ["Aa..Aa..Aa..Aa.."] * 3      # unit 0: the even steps
    assert out["vorl. SW"] == ["..Aa..Aa..Aa..Aa"] * 3      # unit 1: the odd ones
    assert out["mover NE"] == ["." * BAR] * 3


def test_zoom_accents_and_strobe_steps():
    text = sz.render_zoom(base(), 0, 21, 0, 0, [], None)
    out = rows(text)
    assert out["white"] == ["####" + " " * 12]              # one beat of white from 21.1
    assert out["strobe"] == ["xxxx" + " " * 12]             # 1/16 pulses for one beat
    # the strobe writes over the movers and the colour cells during its beat
    assert out["mover NE"] == out["mover SE"] == ["VVVV" + "VVvv" * 3]   # blink 1/4: one beat of decay
    assert out["vorl. NW"] == ["VVVV" + "Vv" * 6]           # solid 1/8: a pulse every two steps
    assert out["lustre"] == ["9742" * 4]                    # hue pulse: a beat of decay, 0-9
    assert "v/V vermelho" in text and "a/A azul" not in text   # the legend lists the colours shown


def test_zoom_marks_auto():
    out = rows(sz.render_zoom(base(), 0, 9, 2, 0, [], None))
    assert out["section"][:2] == ["~".ljust(BAR)] * 2      # bars 7-8: no section, the autoscript plays
    for lane in ("mover NE", "mover SE", "aim", "uv", "vorl. NW", "vorl. SW", "lustre", "white", "strobe"):
        assert out[lane][:2] == ["~" * BAR] * 2, lane
    assert out["uv"][2] == out["strobe"][2] == "~" * BAR    # chegada leaves uv and strobe to the autoscript
    assert out["white"][2] == " " * BAR                     # under a drawn matrix, white is off
    show = with_look({"movers": "auto", "matrix": "off", "hue": {"state": "bright", "colour": "azul"}})
    out = rows(sz.render_zoom(show, 0, 12, 0, 0, [], None))
    assert out["mover NE"] == out["mover SE"] == out["aim"] == ["~" * BAR]
    assert out["lustre"] == ["8" * BAR]                     # bright: 0.85 x 9, rounded half up


def test_zoom_shows_uv_sections():
    src, inp = two_track_show()
    cues = src.track_files[FILE_1]["cues"]
    cues[0]["look"] = {"movers": {"move": "hold", "colour": "azul", "position": "Up"}, "uv": "on",
                       "matrix": "off", "hue": "dark"}
    cues[2]["look"]["movers"] = {"move": "uv"}
    out = rows(sz.render_zoom(compiled(src, inp), 0, 16, 0, 5, [], None))
    assert out["uv"] == ["u" * BAR] + ["~" * BAR] * 4 + ["u" * BAR]
    assert out["mover NE"][5][4:] == "~" * 12              # move uv: the compiler writes nothing on the movers


def test_zoom_aim_lane_names_and_digits():
    text = sz.render_zoom(base(), 0, 17, 1, 3, [], None, room=ROOM)
    out = rows(text)
    assert out["aim"] == [
        "cruzado".ljust(BAR),                               # sweep every 2bar from 9: bars 15-16 aim the 2nd
        "1" * 8 + "2" * 8, "1" * 8 + "2" * 8,               # pingpong 1/2 cycles two aims inside a bar
        "centro-da-pista".ljust(BAR), "centro-da-pista".ljust(BAR)]
    assert "aims: 1 cruzado, 2 coluna" in text
    show = with_look({"movers": "off", "matrix": "off", "hue": "dark"})
    assert rows(sz.render_zoom(show, 0, 12, 0, 0, [], None))["aim"] == ["-".ljust(BAR)]
    assert "pending" not in text


def test_zoom_names_a_pending_aim_and_its_fallback():
    src, inp = two_track_show()
    inp.room = ROOM
    src.track_files[FILE_1]["cues"][0]["look"] = {"movers": {"move": "hold", "colour": "azul", "position": "apice"},
                                                  "matrix": "off", "hue": "dark"}
    text = sz.render_zoom(compiled(src, inp), 0, 12, 0, 0, [], None, room=ROOM)
    assert rows(text)["aim"] == ["apice".ljust(BAR)]
    assert "pending aims, played by their fallback: apice -> coluna" in text.splitlines()


def test_zoom_steps_follow_the_anchors():
    show = base()
    data = show.tracks[0].map
    data["grid"]["anchors"] = [[61, 120.0], [32061, 60.0]]   # bar 17 on: 60 BPM, a bar of 4 s
    grid = ssf.Grid([(61, 120.0), (32061, 60.0)])
    assert sz.step_times(data, 16, 17) == [grid.ms(b, 1 + j / 4) for b in (16, 17) for j in range(BAR)]
    assert sz.step_times(data, 17, 17) == [32061 + 250 * j for j in range(BAR)]
    out = rows(sz.render_zoom(show, 0, 17, 0, 0, [], None))
    # the spiral's 1/2 pingpong at the section's own tempo: 2 s a step, eight 1/16 steps
    assert out["mover NE"] == ["A" * 8 + "." * 8]
    assert out["mover SE"] == ["." * 8 + "A" * 8]


def test_zoom_frames_draw_both_vorlanes():
    show = with_look({"movers": "off", "matrix": {"draw": "columns", "rate": "1/4", "colour": "azul", "mirror": True},
                      "hue": "dark"})
    lines = sz.render_zoom(show, 0, 12, 0, 0, ["12.1", "12.2", "3.1", "12.x"], None).splitlines()
    col = ["    ....#...  ...#...."] * 3                      # step 12: column 4, mirrored to 3 on SW
    assert lines[lines.index("  12.1 · chegada"):][:9] == [
        "  12.1 · chegada", "    vorl. NW  vorl. SW", *col, "    ........  ........", *col]
    nxt = ["    .....#..  ..#....."] * 3
    assert lines[lines.index("  12.2 · chegada"):][:9] == [
        "  12.2 · chegada", "    vorl. NW  vorl. SW", *nxt, "    ........  ........", *nxt]
    auto = lines[lines.index("  3.1 · ~"):][:9]
    assert auto[2:] == ["    ~~~~~~~~  ~~~~~~~~"] * 7
    assert "  12.x: not <bar>.<beat>" in lines


def test_zoom_header_names_the_target_and_the_clock():
    import show_views

    show = base()
    clock = show_views.build_clock(show, {})
    head = sz.render_zoom(show, 0, 21, 3, 1, [], clock, label="virada").splitlines()[0]
    start, end = show_views.clock_text(clock.at(0, 18)), show_views.clock_text(clock.at(0, 23))
    assert head == f"Dançarina · virada (bar 21) · bars 18-22 · {start}-{end}"
    assert sz.render_zoom(show, 0, 2, 3, 40, [], None).splitlines()[0] == "Dançarina · bar 2 · bars 1-32"


def test_zoom_moment_targets():
    show = base()
    assert sz.moment_names(show) == ["virada", "passagem", "final"]   # a bridge's copied moment is not one
    assert sz.moment_target(show, "passagem") == (0, 25)
    assert sz.moment_target(show, "final") == (1, 21)
    assert sz.moment_target(show, "nada") is None


def test_zoom_odd_input_never_raises():
    show = base()
    assert sz.render_zoom(show, 5, 21, 3, 1, [], None) == "track 5 is not a track of the show\n"
    show.tracks[0].map["grid"]["anchors"] = []
    text = sz.render_zoom(show, 0, 21, -2, -1, ["21.1"], None)
    assert text.splitlines() == ["Dançarina · bar 21 · bars 21-21", "  nothing to zoom: the map has no tempo anchors"]
    assert sz.step_times(show.tracks[0].map, 1, 2) == []
    assert sz.render_zoom(base(), 0, 40, 0, 0, [], None).splitlines()[-1] == "  nothing to zoom: the map has 32 bars"


def test_colour_letters_are_unique():
    assert sz.colour_letters(["azul-profundo", "azul-gelo", "ciano", "violeta", "carmim", "vermelho"]) == {
        "azul-profundo": "a", "azul-gelo": "g", "ciano": "c", "violeta": "v", "carmim": "r", "vermelho": "e"}
    many = sz.colour_letters([f"x{i}" for i in range(30)])
    assert len(set(many.values()) - {"?"}) == 26 and list(many.values())[-1] == "?"


# --------------------------------------------- against the compiler itself --


def _case(glyph: str) -> str:
    """A light glyph as its level band: `U` at or above half, `l` below, `.` dark."""
    return "." if glyph == "." else "U" if glyph.isupper() else "l"


def _band(level: float) -> str:
    return "." if level <= 0 else "U" if level >= 0.5 else "l"


def test_zoom_samples_what_compile_writes(room):
    """Every step of every light lane equals the level the compiled script holds there: the
    house venue of tests/test_lightshow_compile.py, compiled with the real rig at 100 BPM."""
    sections = [
        ls.Section((3, 4), "a", None, {
            "movers": {"move": "pingpong", "every": "1/8", "colour": "#FF0A2A"},
            "matrix": {"draw": "columns", "rate": "1/8", "colour": "#0A2CFF", "pingpong": True},
            "hue": "pulse"}),
        ls.Section((5, 6), "b", None, {
            "movers": {"move": "blink", "every": "1/4", "colour": "#FF0A2A"},
            "matrix": {"draw": "solid", "rate": "1/8", "colour": "#FF0A2A", "with_white": True},
            "white": {"accent": ["5.1", "6.3"]}, "strobe": {"hit": ["5.1"]}, "hue": "bright"}),
        ls.Section((7, 8), "c", None, {
            "movers": {"move": "hold", "level": 0.4, "colour": "#6A1CFF"},
            "matrix": {"draw": "rows-up", "rate": "1bar", "mirror": True},
            "white": {"flash": "1/2"}, "strobe": {"roll": [8, 8]}, "hue": "dark"}),
    ]
    script, _ = ls.compile_choreography(choreo(*sections), room(), lc.RIG, lc.VENUES, lc.PRESETS)
    data = good_map(10)
    data["grid"].update(bpm=100.0, downbeat="0:00.158", anchors=[[158, 100.0]])
    origin = Provenance("cue", "A — B", None, None, None, None, "x.yml", 1)
    track = CompiledTrack("A — B", "a-b", "x.yml", data, {},
                          [CompiledSection(s.bars, s.name, None, s.layers, origin) for s in sections])
    show = CompiledShow("x", "lightshows/shows/x", {"palette": {"azul": "#0A2CFF"}}, [track], [])
    out = rows(sz.render_zoom(show, 0, 5, 2, 3, [], None, rig=lc.RIG))
    times = sz.step_times(data, 3, 8)

    def level(node: int, t: int) -> float:
        trk = script.main if node == 2 else ssf.track(script, node)
        return ssf.level_at(ssf.intensity(trk), t) / 2**32

    def lane(label: str) -> str:
        return "".join(out[label])

    cells = {unit: [lc.rgb(unit, n) for n in range(1, 49)] for unit in lc.UNITS}
    whites = [lc.white(unit, n) for unit in lc.UNITS for n in range(1, 9)]
    for label, node in (("mover NE", 1167), ("mover SE", 1168)):
        assert [_case(g) for g in lane(label)] == [_band(level(node, t)) for t in times], label
    for label, unit in (("vorl. NW", lc.UNITS[0]), ("vorl. SW", lc.UNITS[1])):
        assert [_case(g) for g in lane(label)] == [_band(max(level(n, t) for n in cells[unit])) for t in times], label
    assert lane("white") == "".join("#" if max(level(n, t) for n in whites) > 0 else " " for t in times)
    assert lane("lustre") == "".join(sz._digit(level(2, t)) for t in times)
    bands = set(_case(g) for g in lane("mover NE") + lane("vorl. NW"))
    assert bands == {"U", "l", "."}                         # every band is exercised
