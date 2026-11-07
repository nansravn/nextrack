"""The zoom (show_zoom.py): a moment at 1/16 of a beat, the music lanes from the map on top and
the light lanes below, sampled with the compiler's own generators.

The base show is `two_track_show`, at 120 BPM from 61 ms: a beat is 500 ms, a 1/16 step 125 ms.
Dançarina plays the autoscript in bars 1-8, chegada 9-16 (look respiracao), the spiral 17-18
(pingpong 1/2, azul, Crossed Over and Up) and 19-20 (pingpong 1/4, violeta, Dance Floor
Centre), virada 21-24 (blink 1/4, solid 1/8, all vermelho, white and strobe on 21.1) and its
handover entrega 25-32. The palette's legend letters are a azul, v vermelho, i violeta (the
initial, else the next free letter of the name). The house rig is assumed: movers NE (mover 0)
and SE (mover 1), Vorlanes NW (unit 0) and SW (unit 1)."""
import pytest
import test_lightshow_compile as lc
from mapdata import chunks, good_map
from test_lightshow_compile import choreo, room  # noqa: F401  (room: the house venue fixture)

import lightshow as ls
import show_room
import show_zoom as sz
import soundswitch_format as ssf
from show_language import CompiledSection, CompiledShow, CompiledTrack, Provenance, compile_show
from showdata import FILE_1, show_map, two_track_show

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
    assert ("  white #, strobe x, uv u (blank: none); the strobe writes over the movers and the Vorlanes "
            "for its span; uv shows intent only (not compiled yet: a manual cue)") in text.splitlines()


def test_zoom_legend_gives_the_lustres_colour():
    show = with_look({"movers": "off", "matrix": "off", "hue": {"state": "pulse", "colour": "azul"}})
    text = sz.render_zoom(show, 0, 17, 2, 4, [], None)       # bars 15-21: azul, the dark spiral, vermelho
    assert "  lustre 0-9 (. dark): azul 15-16, vermelho 21" in text.splitlines()
    show = with_look({"movers": "off", "matrix": "off", "hue": "bright"})
    text = sz.render_zoom(show, 0, 12, 0, 0, [], None)       # no colour: Main keeps the autoscript's
    assert "  lustre 0-9 (. dark): autoscript colour 12" in text.splitlines()
    text = sz.render_zoom(base(), 0, 18, 0, 0, [], None)     # dark: no colour to name
    assert "  lustre 0-9 (. dark)" in text.splitlines()


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


@pytest.mark.parametrize("bpm, downbeat, ms", [(129.0, "0:00.025", 25), (132.0, "0:00.230", 230)])
def test_zoom_reads_inside_each_step_off_whole_milliseconds(bpm, downbeat, ms):
    """At 129 or 132 BPM a 1/16 step is not a whole number of ms, so the compiler's step and
    pulse times land up to 1 ms off the grid's (each rounded on its own), with a dark key 1 ms
    before every rise: the zoom reads 2 ms into each step, past both, never on the edge."""
    src, inp = two_track_show()
    for data in inp.maps.values():
        data["grid"] = {"bpm": bpm, "downbeat": downbeat, "anchors": [[ms, bpm]], "offset_ms": 0}
    src.track_files[FILE_1]["cues"] = [
        {"at": "drop.1", "name": "rapido", "look": {
            "movers": {"move": "pingpong", "every": "1/16", "colour": "azul", "position": "Up"},
            "matrix": {"draw": "solid", "rate": "1/16", "colour": "azul", "pingpong": True},
            "hue": {"state": "pulse", "colour": "vermelho"}}},
        {"at": "break.1", "name": "varrida", "look": {
            "movers": {"move": "sweep", "every": "1bar", "colour": "azul", "positions": ["Crossed Over", "Up"]},
            "matrix": "off", "hue": {"state": "pulse", "colour": "vermelho"}}},
    ]
    show = compiled(src, inp)
    out = rows(sz.render_zoom(show, 0, 9, 0, 15, [], None, room=ROOM))   # bars 9-24
    fast = slice(0, 8 * BAR)                                 # rapido, bars 9-16: 128 steps
    assert "".join(out["mover NE"])[fast] == "A." * 64
    assert "".join(out["mover SE"])[fast] == ".A" * 64
    assert "".join(out["vorl. NW"])[fast] == "A." * 64
    assert "".join(out["vorl. SW"])[fast] == ".A" * 64
    assert "".join(out["lustre"]) == "9742" * 64             # the hue's full pulse train, both sections
    assert out["aim"][8:] == ["cruzado".ljust(BAR), "coluna".ljust(BAR)] * 4   # it changes on the downbeat only


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
    # an echo's copied moment is not one: with bridge.bars 4 and a 48-bar Dançarina, its echo
    # 41-48 copies Voa Voa's final, and the target stays the cue that wrote it
    src, inp = two_track_show()
    src.show["bridge"]["bars"] = 4
    inp.maps[FILE_1[:-4]] = show_map(48, sections=[(1, 8, "intro"), (9, 16, "drop"), (17, 20, "break"),
                                                   (21, 32, "drop"), (33, 48, "outro")])
    show = compiled(src, inp)
    assert [(s.bars, s.origin.kind, s.origin.moment) for s in show.tracks[0].sections[-1:]] == [
        ((41, 48), "echo", "final")]
    assert sz.moment_names(show) == ["virada", "passagem", "final"]
    assert sz.moment_target(show, "final") == (1, 21)


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
# The house venue of tests/test_lightshow_compile.py (two movers, two Vorlanes with every
# cell, Main), compiled by lightshow.compile_choreography with the real rig at 129 BPM, so
# compiled times are rounded off the grid's. Every lane is read back from the compiled script
# at the zoom's own instants (`sample_times`).

CHECK_PALETTE = {"azul": "#0A2CFF", "vermelho": "#FF0A2A", "violeta": "#6A1CFF", "ciano": "#00B8FF"}
CHECK_SECTIONS = [
    ((3, 4), {"movers": {"move": "pingpong", "every": "1/8", "colour": "#FF0A2A",
                         "positions": ["Crossed Over", "Up"]},
              "matrix": {"draw": "columns", "rate": "1/8", "colour": "#0A2CFF", "pingpong": True, "mirror": True},
              "strobe": "off", "hue": "pulse"}),
    ((5, 6), {"movers": {"move": "blink", "every": "1/4", "colour": "#FF0A2A", "position": "Dance Floor Centre"},
              "matrix": {"draw": "solid", "rate": "1/8", "colour": "#FF0A2A", "with_white": True},
              "white": {"accent": ["5.1", "6.3"]}, "strobe": {"hit": ["5.1", "6.2"]}, "hue": "bright"}),
    ((7, 8), {"movers": {"move": "hold", "level": 0.4, "colour": "#6A1CFF"},
              "matrix": {"draw": "columns", "rate": "1/4", "mirror": True},     # the draw's own colour
              "white": {"flash": "1/2"}, "strobe": {"roll": [8, 8]}, "hue": "dark"}),
    ((9, 10), {"movers": {"move": "sweep", "every": "1bar", "level": 0.7, "colour": "#00B8FF",
                          "positions": ["Up", "Stage Left"]},
               "matrix": {"draw": "fill-up", "rate": "1/4", "colour": "#00B8FF"}, "hue": "off"}),
    ((11, 11), {"movers": "off", "matrix": "off", "hue": "pulse"}),
]
FIRST, LAST = 3, 11


def _case(glyph: str) -> str:
    """A light glyph as its level band: `U` at or above half, `l` below, `.` dark."""
    return "." if glyph == "." else "U" if glyph.isupper() else "l"


def _band(level: float) -> str:
    return "." if level <= 0 else "U" if level >= 0.5 else "l"


def _compile(room, layers_of):
    sections = [ls.Section(bars, "s", None, layers_of(layers)) for bars, layers in CHECK_SECTIONS]
    script, _ = ls.compile_choreography(choreo(*sections, grid={"bpm": 129, "downbeat": "0:00.158"}),
                                        room(tempo=((158, 129.0),)), lc.RIG, lc.VENUES, lc.PRESETS)
    return script


def _zoom_show() -> CompiledShow:
    data = good_map(12)
    data["grid"].update(bpm=129.0, downbeat="0:00.158", anchors=[[158, 129.0]])
    origin = Provenance("cue", "A — B", None, None, None, None, "x.yml", 1)
    track = CompiledTrack("A — B", "a-b", "x.yml", data, {},
                          [CompiledSection(bars, f"s{bars[0]}", None, layers, origin)
                           for bars, layers in CHECK_SECTIONS])
    return CompiledShow("x", "lightshows/shows/x", {"palette": CHECK_PALETTE}, [track], [])


def _legend_hex(text: str) -> dict[str, str]:
    """Each legend letter (both cases) -> the #RRGGBB it stands for."""
    head = text.split("legend: ", 1)[1].split(" (lower case", 1)[0]
    out = {}
    for entry in head.split(", "):
        pair, name = entry.split(" ", 1)
        for letter in pair.split("/"):
            out[letter] = CHECK_PALETTE.get(name, name)
    return out


def _aims_per_step(cells: list[str], text: str) -> list[str]:
    """The aim lane, one aim per step: a bar's name, or each digit through the `aims:` line."""
    line = next((l for l in text.splitlines() if l.startswith("aims: ")), "aims: ")
    digits = dict(entry.split(" ", 1) for entry in line[len("aims: "):].split(", ") if entry)
    out = []
    for cell in cells:
        name = "~" if cell == "~" * BAR else cell.strip()
        out += [digits[c] for c in cell] if cell.isdigit() else [name] * BAR
    return out


def _frame_cells(lines: list[str], beat: str) -> list[str]:
    """The 7 rows of a `--frames` beat, both units side by side."""
    at = next(i for i, l in enumerate(lines) if l.startswith(f"  {beat} · "))
    return [row[4:] for row in lines[at + 2:at + 9]]


def test_zoom_samples_what_compile_writes(room):
    script = _compile(room, dict)
    strobe_only = _compile(room, lambda layers: {"movers": "off", "matrix": "off", "white": "off", "hue": "dark",
                                                 **({"strobe": layers["strobe"]} if "strobe" in layers else {})})
    show = _zoom_show()
    data = show.tracks[0].map
    beats = [f"{b}.{beat}" for b in range(FIRST, LAST + 1) for beat in range(1, 5)]
    text = sz.render_zoom(show, 0, FIRST, 0, LAST - FIRST, beats, None, rig=lc.RIG)
    out, lines = rows(text), text.splitlines()
    samples = sz.sample_times(data, FIRST, LAST)
    letters = _legend_hex(text)

    def level(s, node: int, t: int) -> float:
        trk = s.main if node == 2 else ssf.track(s, node)
        return ssf.level_at(ssf.intensity(trk), t) / 2**32

    def colour(node: int, t: int) -> str:
        argb = lc.colour_at(ssf.track(script, node), t)
        return f"#{argb & 0xFFFFFF:06X}"

    def lane(label: str) -> str:
        return "".join(out[label])

    def node_of(unit: int, row: int, col: int) -> int:
        kind, n = ls.cell_zone(row, col)
        return lc.rgb(unit, n) if kind == "rgb" else lc.white(unit, n)

    colour_cells = {u: [node_of(u, r, c) for r in ls.COLOUR_ROWS for c in range(8)] for u in lc.UNITS}
    whites = [lc.white(u, n) for u in lc.UNITS for n in range(1, 9)]
    # movers: the level band and the colour letter
    for label, node in (("mover NE", 1167), ("mover SE", 1168)):
        glyphs = lane(label)
        assert [_case(g) for g in glyphs] == [_band(level(script, node, t)) for t in samples], label
        assert all(letters[g] == colour(node, t) for g, t in zip(glyphs, samples) if g != "."), label
    # Vorlanes: the brightest colour cell, and the colour of every lit cell
    for label, unit in (("vorl. NW", lc.UNITS[0]), ("vorl. SW", lc.UNITS[1])):
        glyphs = lane(label)
        assert [_case(g) for g in glyphs] == [
            _band(max(level(script, n, t) for n in colour_cells[unit])) for t in samples], label
        for g, t in zip(glyphs, samples):
            lit = [n for n in colour_cells[unit] if level(script, n, t) > 0]
            assert all(letters[g] == colour(n, t) for n in lit), (label, t)
    # white, lustre, strobe: the W cells, Main, and the movers of a compile with only the strobe
    assert lane("white") == "".join("#" if max(level(script, n, t) for n in whites) > 0 else " " for t in samples)
    assert lane("lustre") == "".join(sz._digit(level(script, 2, t)) for t in samples)
    auto = range(16 * (9 - FIRST), 16 * (LAST + 1 - FIRST))              # 9-11 leave the strobe to the autoscript
    strobe = lane("strobe")
    assert all(strobe[k] == "~" for k in auto)
    assert [g for k, g in enumerate(strobe) if k not in auto] == [
        "x" if level(strobe_only, 1167, t) > 0 else " " for k, t in enumerate(samples) if k not in auto]
    # aims: the compiled position flag in force, where the section names a position
    names = {p.guid: p.name for p in lc.PRESETS}
    mover = ssf.track(script, 1167)
    aims = _aims_per_step(out["aim"], text)
    for k, t in enumerate(samples):
        bar = FIRST + k // BAR
        if 7 <= bar <= 8:
            assert aims[k] == "~"                                            # hold without a position
        elif bar == 11:
            assert aims[k] == "-"                                            # movers off
        else:
            assert aims[k] == names[mover.positions.palette[ssf.active_flag(mover, t).preset][0]], (bar, k)
    # --frames: every cell of both units at every beat
    grid = ssf.Grid([(158, 129.0)])
    for beat in beats:
        b, n = (int(x) for x in beat.split("."))
        t = grid.ms(b, n) + sz.SAMPLE_OFFSET_MS
        want = ["  ".join("".join("#" if level(script, node_of(u, r, c), t) > 0 else "." for c in range(8))
                          for u in lc.UNITS) for r in range(7)]
        assert _frame_cells(lines, beat) == want, beat
    # every band, several colours, both aims of a cycle and both strobe forms are exercised
    assert set(_case(g) for g in lane("mover NE") + lane("vorl. NW")) == {"U", "l", "."}
    assert len(set(letters.values())) >= 4 and "x" in strobe and "#" in lane("white")
    assert {"Crossed Over", "Up", "Stage Left", "Dance Floor Centre"} <= set(aims)
