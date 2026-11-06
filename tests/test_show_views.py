"""The critic's views (show_views.py): the set clock, light and music levels, voices, the night
summary, the peak table, the hit checks and the strips, on small synthetic shows.

The base show is `two_track_show` at 120 BPM, so a bar takes 2 s. Dançarina (B 5, G 25) plays
bars 1-24: the autoscript 1-8, chegada 9-16 (respiracao, arrival), the spiral 17-18 and 19-20
(hue dark), virada 21-24 (inline, moment virada, white and strobe on 21.1), and its handover
entrega 25-32 (pulso, moment passagem, white on 25.1) sounds past G. Voa Voa (B 5) plays bars
5-32 from 0:48: the bridge ponte 5-8 (a copy of entrega), chegada 9-16 (pulso, zigzag,
arrival), subida 17-20 (respiracao, pingpong, Up) and final 21-32 (pulso, moment final, a
strobe roll). The expected light digits below are worked by hand from the spec's table."""
import pytest

import check_repo
import set_timeline
import show_room
import show_views as sv
from show_language import compile_show
from show_rules import EFFECT_KEYS, occurrences
from showdata import FILE_1, FILE_2, TRACK_1, TRACK_2, put_show, show_map, two_track_show

KEY_1, KEY_2 = FILE_1[:-4], FILE_2[:-4]
TRACK_3 = "Anitta — Envolver"
FILE_3 = "anitta-envolver.yml"
GUID_3 = "89ABCDEF-89AB-CDEF-0123-456789ABCDEF"
BREU = {"movers": "off", "matrix": "off", "hue": "dark"}


def compiled(src, inp):
    show, findings = compile_show(src, inp)
    assert findings == [], findings
    return show


def base():
    return compiled(*two_track_show())


def three_track_show():
    """`two_track_show` plus a third track: Voa Voa gets a handover (so final is 21-24) and
    Envolver (B 5) opens with a bridge 5-8 and arrives at 9."""
    src, inp = two_track_show()
    src.track_files[FILE_2]["handover"] = {"look": "respiracao"}
    src.track_files[FILE_3] = {
        "track": TRACK_3, "story": "Envolver fecha a noite.",
        "cues": [{"at": "drop.1", "name": "chegada", "role": "arrival", "look": "pulso"}]}
    inp.maps[FILE_3[:-4]] = show_map(track=TRACK_3, soundswitch=GUID_3)
    inp.set_tracks.append(("Anitta", "Envolver"))
    return src, inp


def _aim(preset, status, fallback=None):
    out = {"figure": "uma figura", "preset": preset, "status": status, "targets": {"mover-ne": [1, 1, 1]}}
    if fallback:
        out["fallback"] = fallback
    return out


ROOM = show_room.load_room({
    "size": {"x": 5.0, "y": 4.0, "z": 2.6}, "assumed": True,
    "fixtures": {"mover-ne": [5, 4, 2.3]}, "booth": [2.5, 4, 1.2],
    "aims": {
        "coluna": _aim("Up", "configured"),
        "cruzado": _aim("Crossed Over", "configured"),
        "centro-da-pista": _aim("Dance Floor Centre", "configured"),
        "apice": _aim("Apex", "pending", fallback="coluna"),
    },
})


def bar_string(bars: int, levels: dict[int, str], default: str = "5") -> str:
    return "".join(levels.get(b, default) for b in range(1, bars + 1))


# ------------------------------------------------------------------ levels --


def test_light_level_table():
    # each entry of the spec's table, as the 0-1 value of its layer
    values = sv.light_values
    assert values({"movers": "off", "matrix": "off", "hue": "dark"}) == (0.0, 0.0, 0.0)
    assert values({"movers": {"move": "hold", "level": 0.5}, "matrix": "off", "hue": "off"})[0] == 0.5
    assert values({"movers": {"move": "sweep"}, "matrix": "off", "hue": "off"})[0] == 0.85
    assert values({"movers": {"move": "pingpong", "level": 0.6}, "matrix": "off", "hue": "off"})[0] == \
        pytest.approx(0.3)
    assert values({"movers": {"move": "blink"}, "matrix": "off", "hue": "off"})[0] == pytest.approx(0.425)
    assert values({"movers": {"move": "uv"}, "matrix": "off", "hue": "off"})[0] == 0.3
    shares = {"solid": 1, "fill-up": 0.6, "rows-down": 1 / 6, "rows-up": 1 / 6, "columns": 1 / 8,
              "centre-out": 0.25, "arrow-up": 0.15, "zigzag": 1 / 48}
    for draw, share in shares.items():
        layers = {"movers": "off", "matrix": {"draw": draw, "rate": "1/4"}, "hue": "off"}
        assert values(layers)[1] == pytest.approx(share * 0.6), draw
        layers["matrix"]["pingpong"] = True
        assert values(layers)[1] == pytest.approx(share * 0.5 * 0.6), draw
    assert values({"movers": "off", "matrix": "off", "hue": {"state": "pulse"}})[2] == 0.5
    assert values({"movers": "off", "matrix": "off", "hue": "bright"})[2] == 0.85
    assert values({"movers": "off", "matrix": "off", "hue": {"state": "dark", "colour": "#FF0A2A"}})[2] == 0.0
    # the digit: round(9 * (0.4 m + 0.4 x + 0.2 h)), halves up
    level = sv.light_level
    assert level(BREU) == 0
    assert level({"movers": {"move": "hold", "level": 1}, "matrix": "off", "hue": "off"}) == 4          # 3.6
    assert level({"movers": {"move": "sweep"}, "matrix": {"draw": "solid"}, "hue": "bright"}) == 7      # 6.75
    assert level({"movers": {"move": "hold", "level": 1}, "matrix": "off", "hue": "pulse"}) == 5        # 4.5
    assert level({"movers": {"move": "blink"}, "matrix": {"draw": "solid"}, "hue": {"state": "pulse"}}) == 5  # 4.59
    assert level({"movers": {"move": "uv"}, "matrix": {"draw": "zigzag"}, "hue": "dark"}) == 1          # 1.125
    # accents do not enter the level
    accented = {**BREU, "white": {"accent": ["1.1"]}, "strobe": {"roll": [1, 2]}, "uv": "on"}
    assert level(accented) == 0


def test_light_level_unknown_when_auto():
    lit = {"movers": {"move": "hold"}, "matrix": {"draw": "solid"}, "hue": "bright"}
    assert sv.light_level(lit) is not None
    for layer in ("movers", "matrix", "hue"):
        assert sv.light_level({**lit, layer: "auto"}) is None, layer
        assert sv.light_level({k: v for k, v in lit.items() if k != layer}) is None, layer
    assert sv.light_level({}) is None
    assert sv.light_level({**lit, "movers": {"move": "spin"}}) is None      # not a word of the table


def test_music_level_and_voices():
    data = show_map(bars=4, sections=[(1, 4, "drop")])
    for voice, bars in {"kick": "9000", "bass": "0800", "other": "0070", "vocals": "1119", "perc": "6666"}.items():
        data["voices"][voice]["bars"] = bars
    assert [sv.music_level(data, b) for b in (1, 2, 3, 4)] == [9, 8, 7, 0]   # vocals and perc left out
    assert sv.music_level(data, 5) == 0 and sv.music_level(data, 0) == 0     # outside the map: silent
    assert sv.voices(data, 1, 4) == {"kick": 9, "bass": 8, "vocals": 9, "perc": 6, "other": 7}
    assert list(sv.voices(data, 1, 4)) == ["kick", "bass", "vocals", "perc", "other"]
    assert sv.voices(data, 4, 4) == {"kick": 0, "bass": 0, "vocals": 9, "perc": 6, "other": 0}
    assert sv.voices(data, 3, 9) == sv.voices(data, 3, 4)
    assert sv.voices(data, 3, 2) == {"kick": 0, "bass": 0, "vocals": 0, "perc": 0, "other": 0}


# ------------------------------------------------------------------- clock --


def test_clock_first_and_last_tracks():
    src, inp = three_track_show()
    inp.maps[FILE_3[:-4]]["silences"] = [[1, 1], [30, 32]]     # Envolver's last non-silent bar is 29
    show = compiled(src, inp)
    clock = sv.build_clock(show, {})
    first, middle, last = clock.tracks
    # the first track plays from bar 1 (its B 5 is not used) to G - 1, from 0:00
    assert (first.index, first.leg, first.sounding, first.start_s, first.tempo) == (0, (1, 24), (1, 32), 0.0,
                                                                                    (120.0, 120.0))
    # a middle track plays [B, G) and starts when the one before reaches its G
    assert (middle.index, middle.leg, middle.sounding) == (1, (5, 24), (5, 32))
    assert middle.start_s == pytest.approx(48.0) == clock.at(0, 25)
    # the last runs to its last non-silent bar; its sounding window to its last compiled bar
    assert (last.index, last.leg, last.sounding) == (2, (5, 29), (5, 32))
    assert last.start_s == pytest.approx(88.0)
    assert clock.at(0, 1) == 0.0 and clock.at(2, 5) == pytest.approx(clock.at(1, 25))
    assert sv.clock_text(clock.at(2, 30)) == "2:18"                       # 88 + 25 bars of 2 s
    assert sv.night_summary(show, clock, None)["total_s"] == pytest.approx(138.0)


def test_clock_ramps_the_played_tempo():
    show = base()
    tempo = (120.0, 132.0)
    clock = sv.build_clock(show, {TRACK_2: tempo})
    assert clock.tracks[0].tempo == (120.0, 120.0)        # no tracklist tempo: the map's bpm
    assert clock.tracks[1].tempo == tempo
    for bar in (5, 6, 20, 32):
        assert clock.at(1, bar) == pytest.approx(48.0 + set_timeline.seconds(tempo, 28, bar - 5))
    assert sv.night_summary(show, clock, None)["total_s"] == pytest.approx(48.0 + set_timeline.seconds(tempo, 28, 28))


def test_clock_past_g_for_handover_events():
    show = base()
    tempo = (120.0, 128.0)
    clock = sv.build_clock(show, {TRACK_1: tempo})
    g = clock.at(0, 25)
    assert g == pytest.approx(set_timeline.seconds(tempo, 24, 24)) == pytest.approx(clock.tracks[1].start_s)
    # past G the outgoing track keeps its end tempo, as set_timeline.seconds does
    assert clock.at(0, 29) == pytest.approx(g + 4 * 240 / 128)
    assert clock.at(0, 29) == pytest.approx(set_timeline.seconds(tempo, 24, 28))


def test_clock_text():
    assert [sv.clock_text(s) for s in (0, 59.6, 1847, 3599.4)] == ["0:00", "1:00", "30:47", "59:59"]
    assert [sv.clock_text(s) for s in (3600, 3725)] == ["1:00:00", "1:02:05"]


def test_show_tempos_reads_the_block_tracklist(mini_repo):
    put_show(mini_repo)
    mini_repo.edit("blocks/alpha-festa.md", "Dançarina        · e8", "Dançarina · 8A · 120-124 · e8")
    repo = check_repo.load_repo(mini_repo.root)
    source = next(s for s in repo.shows if s.folder == "lightshows/shows/teste")
    # Voa Voa's line has no tempo: left out, the clock uses its map's bpm
    assert check_repo.show_tempos(repo, source) == {TRACK_1: (120.0, 124.0)}
    mini_repo.edit("blocks/alpha-festa.md", "Voa Voa    · e7", "Voa Voa · 9A · 126 · e7")
    repo = check_repo.load_repo(mini_repo.root)
    source = next(s for s in repo.shows if s.folder == "lightshows/shows/teste")
    assert check_repo.show_tempos(repo, source) == {TRACK_1: (120.0, 124.0), TRACK_2: (126.0, 126.0)}
    source.show["set"] = "sets/nao-existe.md"
    assert check_repo.show_tempos(repo, source) == {}


# ----------------------------------------------------------------- summary --


def test_summary_counts_states_over_legs():
    show = base()
    night = sv.night_summary(show, sv.build_clock(show, {}), None)
    assert night["total_s"] == pytest.approx(104.0)
    # the bridge ponte 5-8 counts in Voa Voa's leg; the handover entrega 25-32 (after G) does not
    assert night["looks"] == pytest.approx({"respiracao": 24.0, "spiral": 8.0, "inline": 8.0, "pulso": 48.0})
    assert night["autoscript_s"] == pytest.approx(16.0)                 # Dançarina 1-8 has no section
    colours = night["colours"]
    assert list(colours) == ["movers", "matrix", "hue"]
    assert colours["movers"] == pytest.approx({"azul": 28.0, "violeta": 4.0, "vermelho": 56.0})
    assert colours["matrix"] == pytest.approx({"azul": 28.0, "violeta": 4.0, "vermelho": 56.0})
    assert colours["hue"] == pytest.approx({"vermelho": 80.0})          # the spiral's hue is dark
    assert night["zones"] == pytest.approx({"movers": 88.0, "matrix": 88.0, "hue": 80.0})
    assert night["centre_dark_s"] == pytest.approx(8.0)
    assert night["total_dark"] == {"s": 0.0, "count": 0}

    src, inp = two_track_show()
    src.track_files[FILE_2]["cues"][1] = {"at": "break.1", "name": "breu", "look": BREU}
    show = compiled(src, inp)
    night = sv.night_summary(show, sv.build_clock(show, {}), None)
    assert night["total_dark"] == pytest.approx({"s": 8.0, "count": 1})
    assert night["centre_dark_s"] == pytest.approx(16.0)
    assert night["looks"]["inline"] == pytest.approx(16.0)


def test_summary_counts_events_over_sounding_windows():
    show = base()
    night = sv.night_summary(show, sv.build_clock(show, {}), None)
    events = night["events"]
    # the white accent on the handover at G (25.1) sounds past Dançarina's leg and is counted
    assert events["white-accent"] == pytest.approx({"count": 2, "s": 1.0})     # a beat each
    assert events["strobe"] == pytest.approx({"count": 2, "s": 0.5 + 24.0})    # a hit (a beat), a roll 21-32
    assert events["white-flash"] == {"count": 0, "s": 0.0} and events["uv"] == {"count": 0, "s": 0.0}
    for key in EFFECT_KEYS:
        assert events[key]["count"] == len(occurrences(show, key)), key

    src, inp = two_track_show()
    src.track_files[FILE_2]["cues"][1]["look"] = {"movers": {"move": "uv", "position": "Up"},
                                                 "white": {"flash": "1/8"}, "matrix": "off", "hue": "dark"}
    del src.track_files[FILE_2]["cues"][1]["with"]
    show = compiled(src, inp)
    events = sv.night_summary(show, sv.build_clock(show, {}), None)["events"]
    assert events["uv"] == pytest.approx({"count": 1, "s": 8.0})
    assert events["white-flash"] == pytest.approx({"count": 1, "s": 8.0})
    for key in EFFECT_KEYS:
        assert events[key]["count"] == len(occurrences(show, key)), key


def test_summary_splits_cycling_aims_evenly():
    show = base()
    clock = sv.build_clock(show, {})
    # chegada 9-16 cycles two presets (8 s each); the spiral's 17-18 two more (2 s each)
    assert sv.night_summary(show, clock, ROOM)["aims"] == pytest.approx(
        {"centro-da-pista": 12.0, "cruzado": 66.0, "coluna": 10.0})
    assert sv.night_summary(show, clock, None)["aims"] == pytest.approx(
        {"Dance Floor Centre": 12.0, "Crossed Over": 66.0, "Up": 10.0})        # no room: the raw presets
    assert sv.night_summary(show, clock, ROOM)["pending_aims"] == []

    src, inp = two_track_show()
    inp.room = ROOM
    # with both, the movers cycle `positions` (as the compiler reads them); `position` is unused
    src.track_files[FILE_1]["cues"][0]["with"] = {"movers": {"position": "coluna",
                                                             "positions": ["apice", "Crossed Over"]}}
    # subida keeps its raw `position: Up` (coluna's preset) and cycles `positions: [apice]` (also Up)
    src.track_files[FILE_2]["cues"][1]["with"]["movers"]["positions"] = ["apice"]
    show = compiled(src, inp)
    assert sv.section_aims(show.tracks[1].sections[2], ROOM) == ["apice"]
    night = sv.night_summary(show, sv.build_clock(show, {}), ROOM)
    # a pending aim keeps its own name, and the fallback that stood in for it is listed
    assert night["aims"] == pytest.approx({"apice": 16.0, "cruzado": 66.0, "coluna": 2.0, "centro-da-pista": 4.0})
    assert night["pending_aims"] == [("apice", "coluna")]
    chegada = show.tracks[0].sections[0]
    assert chegada.origin.aims == ("coluna", "apice")
    assert sv.section_aims(chegada, ROOM) == ["apice", "cruzado"]


# ------------------------------------------------------------ peaks, hits --


def test_peaks_include_drops_during_the_mix():
    src, inp = two_track_show()
    inp.maps[KEY_1]["drops"] = [{"bar": 9, "db": 12.5}, {"bar": 21, "db": 30.0}, {"bar": 27, "db": 6.0}]
    inp.maps[KEY_2]["drops"] = [{"bar": 3, "db": 4.0}, {"bar": 9, "db": 8.0}, {"bar": 21, "db": 10.0}]
    src.track_files[FILE_2]["cues"][0]["with"]["white"] = {"accent": ["9.3"]}     # any beat of the bar
    show = compiled(src, inp)
    rows = sv.peaks(show, sv.build_clock(show, {}))
    got = [(r["clock_s"], r["index"], r["bar"], r["db"], r["music"], r["before"], r["at"], r["accents"], r["moment"])
           for r in rows]
    assert got == [
        (16.0, 0, 9, 12.5, 5, None, 4, [], None),                       # bar 8 is the autoscript's
        (40.0, 0, 21, 30.0, 5, 2, 5, ["white", "strobe"], "virada"),
        (52.0, 0, 27, 6.0, 5, 3, 3, [], "passagem"),                    # Dançarina's handover, past G
        (56.0, 1, 9, 8.0, 5, 3, 2, ["white"], None),                    # bar 3 is before Voa Voa's B: left out
        (80.0, 1, 21, 10.0, 5, 3, 3, ["roll"], "final"),
    ]
    assert [r["track"] for r in rows] == [TRACK_1, TRACK_1, TRACK_1, TRACK_2, TRACK_2]


def test_hit_checks_report_voices_in_a_dark_bar_before():
    src, inp = two_track_show()
    src.track_files[FILE_1]["cues"][1] = {"at": "break.1", "name": "breu", "look": BREU}    # 17-20, total dark
    data = inp.maps[KEY_1]
    for voice, level in {"kick": "0", "bass": "0", "vocals": "9", "perc": "0", "other": "3"}.items():
        data["voices"][voice]["bars"] = bar_string(32, {b: level for b in range(17, 21)})
    kick = ["9..." * 4] * 32
    kick[9 - 1], kick[21 - 1] = "." + "..." + "9..." * 3, "7..." * 4
    data["onsets"]["kick"] = ["".join(kick[i:i + 8]) for i in range(0, 32, 8)]
    src.track_files[FILE_2]["cues"][0]["with"]["white"] = {"accent": ["9.3"]}     # not on the hit's beat
    show = compiled(src, inp)
    rows = sv.hit_checks(show, sv.build_clock(show, {}))
    got = [(r["clock_s"], r["index"], r["bar"], r["arrival"], r["moment"], r["kick"], r["before"], r["at"],
            r["accents"], r["dark"]) for r in rows]
    assert got == [
        (16.0, 0, 9, True, None, ".", None, 4, [], None),
        (40.0, 0, 21, False, "virada", "7", 0, 5, ["white", "strobe"],
         {"bars": (17, 20), "voices": {"kick": 0, "bass": 0, "vocals": 9, "perc": 0, "other": 3}}),
        (48.0, 0, 25, False, "passagem", "9", 5, 3, ["white"], None),   # the handover, at its own clock
        (56.0, 1, 9, True, None, "9", 3, 2, [], None),                  # the bridge's copied moment is no hit
        (80.0, 1, 21, False, "final", "9", 3, 3, ["roll"], None),
    ]


def test_strips_wrap_nothing_and_use_tilde_for_unknown():
    src, inp = two_track_show()
    sections = [(1, 8, "intro"), (9, 16, "drop"), (17, 20, "break"), (21, 80, "drop")]
    inp.maps[KEY_1] = show_map(bars=80, sections=sections, hot_cues={"A": "1.1", "B": "5.1", "G": "73.1"})
    src.track_files[FILE_2]["cues"][1]["with"]["matrix"] = "auto"
    show = compiled(src, inp)
    clock = sv.build_clock(show, {})
    music, light = sv.strips(show.tracks[0], clock.tracks[0])
    assert len(music) == len(light) == 72 and "\n" not in music + light     # bars 1-72, one string each
    assert music == "5" * 72
    assert light == "~" * 8 + "4" * 8 + "2" * 4 + "5" * 52                  # 1-8 is the autoscript's
    music, light = sv.strips(show.tracks[1], clock.tracks[1])
    assert light == "3" * 4 + "2" * 8 + "~" * 4 + "3" * 12                   # subida's matrix is auto


def test_views_take_bad_maps_without_raising():
    show = base()
    show.tracks[1].map["hot_cues"] = {"A": "1.1", "B": "x"}                  # an unreadable B: from bar 1
    clock = sv.build_clock(show, {})
    assert clock.tracks[1].leg == (1, 32)
    assert sv.night_summary(show, clock, ROOM)["total_s"] == pytest.approx(48.0 + 64.0)
