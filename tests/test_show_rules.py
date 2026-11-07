"""The show rules: occurrences, the rules, their parameter checks, advice and `evaluate_show`."""
import copy
import dataclasses

import show_analysis as sa
from show_rules import ADVICE, EFFECT_KEYS, RULES, evaluate_show, occurrences, run_rules
from showdata import FILE_1, FILE_2, TRACK_1, TRACK_2, show_map, two_track_show

FOLDER = "lightshows/shows/teste"
PATH_1, PATH_2, SHOW_PATH = f"{FOLDER}/{FILE_1}", f"{FOLDER}/{FILE_2}", f"{FOLDER}/show.yml"
BREU = {"movers": "off", "matrix": "off", "hue": "dark"}
RULES_LINE = 40
ADVICE_LINE = 50
DARK = "leaves every fixture dark (movers off, matrix off, hue dark)"


def show(rules=None, looks=None, edit=None, advice=None):
    """`two_track_show` with extra `looks`, track files changed by `edit(first, second)`, `rules`
    and `advice`, then lines for the findings: a track file at 1, its cue i at 10 * i, its
    handover at 90; show.yml's `rules` at 40 and its i-th rule's mapping at 40 + i, its `advice`
    at 50 and its i-th rule's mapping at 50 + i.

    The base show: Dançarina has chegada 9-16 (look respiracao, arrival), espiral 17-20 (spiral,
    two sections), virada 21-24 (inline, moment virada, white and strobe accents) and the handover
    entrega 25-32 (look pulso, moment passagem, a white accent). Voa Voa has the bridge ponte 5-8,
    chegada 9-16 (look pulso, draw zigzag, arrival), subida 17-20 (look respiracao) and final
    21-32 (look pulso, moment final, a strobe roll)."""
    src, inp = two_track_show()
    src.show["looks"].update(looks or {})
    if edit is not None:
        edit(src.track_files[FILE_1], src.track_files[FILE_2])
    for data in src.track_files.values():
        data["__line__"] = 1
        for i, cue in enumerate(data["cues"], 1):
            cue["__line__"] = 10 * i
        if "handover" in data:
            data["handover"]["__line__"] = 90
    for key, given, line in (("rules", rules, RULES_LINE), ("advice", advice, ADVICE_LINE)):
        if given is not None:
            src.show[key] = {"__line__": line, **given}
            for i, name in enumerate(given, 1):
                if isinstance(given[name], dict):
                    given[name]["__line__"] = line + i
    return src, inp


def rule_findings(src, inp):
    compiled, source_found, found, _ = evaluate_show(src, inp)
    assert [f.message for f in source_found] == []
    assert compiled is not None and {f.rule for f in found} <= {"show-rules"}
    return [(f.path, f.line, f.message) for f in found]


def source_findings(src, inp):
    compiled, found, rule_found, advice = evaluate_show(src, inp)
    assert compiled is None and rule_found == [] and advice == []
    return [(f.path, f.line, f.rule, f.message) for f in found]


def table(compiled, key):
    return [(o.track, o.bar, o.origin.kind) for o in occurrences(compiled, key)]


# ------------------------------------------------------------- occurrences --


def test_occurrences_follow_the_table():
    compiled, _, _, _ = evaluate_show(*show())
    assert table(compiled, "respiracao") == [(TRACK_1, 9, "cue"), (TRACK_2, 17, "cue")]
    assert table(compiled, "pulso") == [(TRACK_1, 25, "handover"), (TRACK_2, 9, "cue"), (TRACK_2, 21, "cue")]
    assert table(compiled, "spiral") == [(TRACK_1, 17, "cue")]            # one cue, two sections
    assert table(compiled, "white-accent") == [(TRACK_1, 21, "cue"), (TRACK_1, 25, "handover")]
    assert table(compiled, "strobe") == [(TRACK_1, 21, "cue"), (TRACK_2, 21, "cue")]   # a hit, a roll
    assert table(compiled, "white-flash") == [] and table(compiled, "uv") == []
    assert all(o.key == "pulso" for o in occurrences(compiled, "pulso"))

    def edit(first, second):
        second["cues"][1] = {"at": "break.1", "name": "subida",
                             "look": {"movers": {"move": "hold", "position": "Up"}, "uv": "on",
                                      "white": {"accent": ["17.1", "18.3"]}}}
        second["cues"][2]["look"] = {"movers": {"move": "uv", "position": "Up"}, "white": {"flash": "1/8"}}

    compiled, _, _, _ = evaluate_show(*show(edit=edit))
    assert table(compiled, "white-accent") == [(TRACK_1, 21, "cue"), (TRACK_1, 25, "handover"),
                                               (TRACK_2, 17, "cue"), (TRACK_2, 18, "cue")]
    assert table(compiled, "white-flash") == [(TRACK_2, 21, "cue")]
    assert table(compiled, "uv") == [(TRACK_2, 17, "cue"), (TRACK_2, 21, "cue")]
    assert occurrences(compiled, "uv")[0].origin.path == PATH_2


def test_a_gesture_counts_once_per_cue():
    def edit(first, second):
        second["cues"][1] = {"at": "break.1", "name": "espiral", "gesture": "spiral", "with": {"bars": [2, 2]}}

    src, inp = show({"budget": {"spiral": {"max": 1}}}, edit=edit)
    assert rule_findings(src, inp) == [
        (PATH_2, 20, "budget: spiral is used 2 times, max 1: Dançarina 17, Voa Voa (Ao Vivo) 17")]


def test_bridges_never_count():
    def edit(first, second):
        second["cues"][0]["look"] = "respiracao"
        second["cues"][2]["look"] = "respiracao"

    src, inp = show({"budget": {"pulso": {"max": 1}}}, edit=edit)
    compiled, _, found, _ = evaluate_show(src, inp)
    assert found == []
    bridge = compiled.tracks[1].sections[0]
    assert (bridge.origin.kind, bridge.origin.look, bridge.bars) == ("bridge", "pulso", (5, 8))
    assert table(compiled, "pulso") == [(TRACK_1, 25, "handover")]
    assert rule_findings(*show({"budget": {"pulso": {"max": 0}}}, edit=edit)) == [
        (PATH_1, 90, "budget: pulso is used 1 time, max 0: Dançarina 25")]


def echo_show(rules=None, edit=None):
    """`show` with `bridge.bars: 4` and Dançarina on a 48-bar map (B 5, G 25): the handover
    entrega is 25-28 and the echo 29-48 copies Voa Voa's chegada, subida and final (9-28)."""
    src, inp = show(rules, edit=edit)
    src.show["bridge"]["bars"] = 4
    inp.maps[FILE_1[:-4]] = show_map(48, sections=[(1, 8, "intro"), (9, 16, "drop"), (17, 20, "break"),
                                                   (21, 32, "drop"), (33, 48, "outro")])
    return src, inp


def without_echoes(compiled):
    return dataclasses.replace(compiled, tracks=[
        dataclasses.replace(t, sections=[s for s in t.sections if s.origin.kind != "echo"]) for t in compiled.tracks])


def test_echo_sections_are_not_occurrences():
    def edit(first, second):
        second["cues"][1]["with"].update({"white": {"flash": "1/4"}, "uv": "on"})

    compiled, _, _, _ = evaluate_show(*echo_show(edit=edit))
    echo = [s for s in compiled.tracks[0].sections if s.origin.kind == "echo"]
    assert [(s.bars, s.origin.look) for s in echo] == [((29, 36), "pulso"), ((37, 40), "respiracao"),
                                                       ((41, 48), "pulso")]
    assert echo[1].layers["white"] == {"flash": "1/4"} and echo[1].layers["uv"] == "on"
    for key in ("pulso", "respiracao", "spiral", *EFFECT_KEYS):
        assert table(compiled, key) == table(without_echoes(compiled), key), key
    assert table(compiled, "pulso") == [(TRACK_1, 25, "handover"), (TRACK_2, 9, "cue"), (TRACK_2, 21, "cue")]
    assert table(compiled, "uv") == [(TRACK_2, 17, "cue")]
    budget = {"pulso": {"max": 3}, "respiracao": {"max": 2}, "white-flash": {"max": 1}, "uv": {"max": 1}}
    assert rule_findings(*echo_show({"budget": budget}, edit=edit)) == []


def test_rules_that_read_sections_skip_the_echo():
    def edit(first, second):
        second["cues"][1] = {"at": "break.1", "name": "subida", "look": dict(BREU)}   # inline: not in only
        second["cues"][2]["look"] = {"movers": {"move": "sweep", "every": "2bar"},   # no aim, a cloned matrix
                                     "matrix": {"draw": "solid", "rate": "1/8"}, "hue": "pulse"}

    rules = {"total-dark": {"only": ["spiral"]}, "movers-aim": True, "matrix-not-cloned": True}
    compiled, _, _, _ = evaluate_show(*echo_show(edit=edit))
    echo = [s for s in compiled.tracks[0].sections if s.origin.kind == "echo"]
    assert [(s.bars, s.name) for s in echo] == [((29, 36), "chegada"), ((37, 40), "subida"), ((41, 48), "final")]
    assert echo[1].layers == BREU and echo[2].layers["matrix"] == {"draw": "solid", "rate": "1/8"}
    found = rule_findings(*echo_show(rules, edit=edit))
    assert [(path, line, message.split(":")[0]) for path, line, message in found] == [
        (PATH_2, 20, "total-dark"),
        (PATH_2, 30, "matrix-not-cloned"),
        (PATH_2, 30, "movers-aim"),
        (PATH_1, 30, "matrix-not-cloned"),                             # virada, Dançarina 21-24
    ]
    named = ["Voa Voa (Ao Vivo) 17-20 (subida)", "Voa Voa (Ao Vivo) 21-32 (final)", "Voa Voa (Ao Vivo) 21-32 (final)",
             "Dançarina 21-24 (virada)"]
    assert all(where in message for where, (_, _, message) in zip(named, found, strict=True))


# ------------------------------------------------------------------ budget --


def test_budget_max_lists_every_occurrence():
    def edit(first, second):
        first["cues"][0]["look"] = "breu"
        first["cues"][1] = {"at": "break.1", "name": "breu", "look": "breu"}
        second["bridge"] = False
        second["cues"].insert(0, {"at": 5, "name": "breu", "look": "breu"})

    found = rule_findings(*show({"budget": {"breu": {"max": 2}}}, {"breu": BREU}, edit))
    assert found == [(PATH_2, 10, "budget: breu is used 3 times, max 2: Dançarina 9, Dançarina 17, "
                                  "Voa Voa (Ao Vivo) 5")]
    assert rule_findings(*show({"budget": {"breu": {"max": 3}}}, {"breu": BREU}, edit)) == []


def test_budget_moments_and_from():
    # strobe: the hit of virada (Dançarina 21, moment virada), the roll of final (Voa Voa 21, moment final)
    assert rule_findings(*show({"budget": {"strobe": {"max": 2, "moments": ["virada", "final"],
                                                      "from": TRACK_1}}})) == []
    found = rule_findings(*show({"budget": {"strobe": {"moments": ["final"], "from": TRACK_2}}}))
    assert found == [
        (PATH_1, 30, "budget: strobe in Dançarina 21 comes before Voa Voa (Ao Vivo), the first track "
                     "allowed to use it (from): remove it here, or set from to an earlier track"),
        (PATH_1, 30, "budget: strobe in Dançarina 21 is in moment 'virada', and strobe is allowed only in "
                     "final: give its cue one of those moments, or remove it"),
    ]

    def edit(first, second):
        second["cues"][0]["accents"] = ["strobe"]

    found = rule_findings(*show({"budget": {"strobe": {"moments": ["virada", "final"]}}}, edit=edit))
    assert found == [(PATH_2, 10, "budget: strobe in Voa Voa (Ao Vivo) 9 has no moment, and strobe is "
                                  "allowed only in virada, final: give its cue one of those moments, or remove it")]


def test_budget_unknown_key_is_a_source_finding():
    found = source_findings(*show({"budget": {"spirall": {"max": 1}}}))
    assert found == [(SHOW_PATH, 41, "show-source",
                      "rules.budget: unknown key 'spirall' (a look: pulso, respiracao; a gesture: sequence, "
                      "spiral; an effect: white-accent, white-flash, strobe, uv); did you mean 'spiral'?")]
    found = source_findings(*show({"budget": {"strobe": {"from": "Pedro Sampaio — Dancarina"}}}))
    assert found == [(SHOW_PATH, 41, "show-source",
                      "rules.budget: strobe.from 'Pedro Sampaio — Dancarina' is not a track of this show; "
                      "did you mean 'Pedro Sampaio — Dançarina'?")]
    found = source_findings(*show({"budget": {"pulso": {"max": -1, "moments": ["Virada"], "most": 2},
                                              "spiral": {}, "uv": 3}}, looks={"spiral": BREU}))
    assert found == [
        (SHOW_PATH, 41, "show-source", "rules.budget: 'spiral' is both a look and a gesture: rename the look"),
        (SHOW_PATH, 41, "show-source", "rules.budget: pulso.max -1 is not a whole number (0 or more)"),
        (SHOW_PATH, 41, "show-source",
         "rules.budget: pulso.moments ['Virada'] is not a non-empty list of moment names (kebab-case ids)"),
        (SHOW_PATH, 41, "show-source", "rules.budget: pulso: unexpected key 'most' (allowed: max, moments, from)"),
        (SHOW_PATH, 41, "show-source", "rules.budget: uv 3 is not a mapping of max?, moments?, from?"),
    ]


# -------------------------------------------------------------- total-dark --


def test_sequence_step_look_counts_and_passes_total_dark():
    def edit(first, second):
        first["cues"][1] = {"at": "break.1", "name": "respiro", "gesture": "sequence",
                            "with": {"steps": [{"bars": 2, "look": "breu"}, {"bars": 2, "look": "respiracao"}]}}

    looks = {"breu": BREU}
    src, inp = show({"budget": {"breu": {"max": 1}, "sequence": {"max": 1}}, "total-dark": {"only": ["breu"]}},
                    looks, edit)
    compiled, _, found, _ = evaluate_show(src, inp)
    assert found == []
    assert [(o.bar, o.origin.look, o.origin.gesture) for o in occurrences(compiled, "breu")] == [
        (17, "breu", "sequence")]
    assert [o.bar for o in occurrences(compiled, "sequence")] == [17]
    assert table(compiled, "respiracao") == [(TRACK_1, 9, "cue"), (TRACK_1, 19, "cue"), (TRACK_2, 17, "cue")]
    assert rule_findings(*show({"total-dark": {"only": ["sequence"]}}, looks, edit)) == []
    found = rule_findings(*show({"budget": {"breu": {"max": 0}}, "total-dark": {"only": ["respiracao"]}},
                                looks, edit))
    assert found == [
        (PATH_1, 20, "budget: breu is used 1 time, max 0: Dançarina 17"),
        (PATH_1, 20, f"total-dark: Dançarina 17-18 (respiro-1) {DARK} with look 'breu' of gesture "
                     "'sequence', which is not in only (respiracao): use one of those, or light a layer"),
    ]


def test_total_dark_sees_unquoted_off():
    looks = {"breu": BREU, "apagao": {"movers": False, "matrix": False, "hue": "dark"}}

    def edit(first, second):
        first["cues"][0]["look"] = "apagao"

    found = rule_findings(*show({"total-dark": {"only": ["breu"]}}, looks, edit))
    assert found == [(PATH_1, 10, f"total-dark: Dançarina 9-16 (chegada) {DARK} with look 'apagao', which is "
                                  "not in only (breu): use one of those, or light a layer")]
    compiled, _, found, _ = evaluate_show(*show({"total-dark": {"only": ["breu", "apagao"]}}, looks, edit))
    assert found == []
    # the rule itself reads a False layer as off, and a lit white is not dark
    compiled.data["rules"] = {"total-dark": {"only": ["breu"]}}
    section = compiled.tracks[0].sections[0]
    section.layers.update(movers=False, matrix=False)
    assert [f.line for f in run_rules(compiled)] == [10]
    section.layers["white"] = {"accent": ["9.1"]}
    assert run_rules(compiled) == []
    # an explicit auto or off is not lit; hue off is dark, as lightshow compiles it
    section.layers.update(white="auto", strobe="off", uv=False, hue="off")
    assert [f.line for f in run_rules(compiled)] == [10]
    section.layers["uv"] = True
    assert run_rules(compiled) == []


def test_total_dark_sees_the_bridge_copy_without_its_accents():
    # the handover is dark but for its white accent; the bridge copies it without the accent
    def edit(first, second):
        first["handover"] = {"look": "apagao", "accents": ["white"]}

    looks = {"breu": BREU, "apagao": BREU}
    found = rule_findings(*show({"total-dark": {"only": ["breu"]}}, looks, edit))
    assert found == [(PATH_1, 90, f"total-dark: Voa Voa (Ao Vivo) 5-8 (ponte, the bridge copying this handover) "
                                  f"{DARK} with look 'apagao', which is not in only (breu): use one of those, "
                                  "or light a layer")]


# ---------------------------------------------------------------- arrivals --


def test_arrivals_one_per_track_and_draws_differ():
    assert rule_findings(*show({"arrivals": {"draw_differs": True}})) == []

    def none_and_two(first, second):
        first["cues"][2]["role"] = "arrival"
        del second["cues"][0]["role"]

    assert rule_findings(*show({"arrivals": True}, edit=none_and_two)) == [
        (PATH_2, 1, "arrivals: Voa Voa (Ao Vivo) has no cue with role: arrival: give it to the cue that "
                    "shows the track (usually its first drop)"),
        (PATH_1, 30, "arrivals: Dançarina has 2 arrivals (chegada 9, virada 21): keep role: arrival on one cue"),
    ]

    def same_draw(first, second):
        second["cues"][0]["with"] = {"matrix": {"draw": "rows-up"}}

    assert rule_findings(*show({"arrivals": {"draw_differs": True}}, edit=same_draw)) == [
        (PATH_2, 10, "arrivals: Voa Voa (Ao Vivo) arrives at 9 with matrix draw 'rows-up', as Dançarina did "
                     "at 9: draw one of the two arrivals differently")]
    assert rule_findings(*show({"arrivals": {"draw_differs": False}}, edit=same_draw)) == []


# ------------------------------------------------------- movers and matrix --


def test_movers_aim():
    assert rule_findings(*show({"movers-aim": True})) == []

    def edit(first, second):
        second["cues"][1] = {"at": "break.1", "name": "subida",
                             "look": {"movers": {"move": "sweep", "every": "2bar"}}}

    assert rule_findings(*show({"movers-aim": True}, edit=edit)) == [
        (PATH_2, 20, "movers-aim: Voa Voa (Ao Vivo) 17-20 (subida) moves the movers (sweep) without position "
                     "or positions, so the autoscript picks a random preset every two bars: aim them")]


def test_matrix_not_cloned_honours_moments_through_bridges():
    # in the base show only virada draws without mirror or pingpong (a solid red)
    assert rule_findings(*show({"matrix-not-cloned": {"except_moments": ["virada"]}})) == []
    assert rule_findings(*show({"matrix-not-cloned": True})) == [
        (PATH_1, 30, "matrix-not-cloned: Dançarina 21-24 (virada) draws the matrix (solid) with neither mirror "
                     "nor pingpong, so both Vorlanes draw the same: add mirror: true or pingpong: true, or add "
                     "its moment 'virada' to except_moments")]

    # a peak handover in moment final: the bridge copies its layers and its moment
    def edit(first, second):
        first["handover"].update({"moment": "final", "with": {"matrix": {"mirror": None}}})

    assert rule_findings(*show({"matrix-not-cloned": {"except_moments": ["virada", "final"]}}, edit=edit)) == []
    tail = ("draws the matrix (centre-out) with neither mirror nor pingpong, so both Vorlanes draw the same: "
            "add mirror: true or pingpong: true, or add its moment 'final' to except_moments")
    assert rule_findings(*show({"matrix-not-cloned": {"except_moments": ["virada"]}}, edit=edit)) == [
        (PATH_1, 90, f"matrix-not-cloned: Dançarina 25-32 (entrega) {tail}"),
        (PATH_1, 90, f"matrix-not-cloned: Voa Voa (Ao Vivo) 5-8 (ponte, the bridge copying this handover) {tail}"),
    ]


# --------------------------------------------------------------- exclusive --


def test_exclusive():
    # Dançarina: the spiral at 17 and the strobe hit of virada at 21
    assert rule_findings(*show({"exclusive": {"keys": ["spiral", "strobe"]}})) == [
        (PATH_1, 30, "exclusive: Dançarina uses spiral (17) and strobe (21), and a track uses at most one of "
                     "spiral, strobe: keep one, or add the track to except_tracks")]
    for name in (TRACK_1, "Dançarina"):
        assert rule_findings(*show({"exclusive": {"keys": ["spiral", "strobe"], "except_tracks": [name]}})) == []
    assert rule_findings(*show({"exclusive": {"keys": ["spiral", "uv"]}})) == []


# ----------------------------------------------------------------- bridges --


def test_bridges_rule_measures_bridges_and_handovers():
    # the base show: the handover entrega Dançarina 25-32 (8 bars), its bridge ponte Voa Voa 5-8 (4 bars)
    assert rule_findings(*show({"bridges": {"max": 8}})) == []

    def long_bridge(first, second):
        del second["cues"][0]                     # Voa Voa opens with subida at 17: the bridge runs 5-16

    assert rule_findings(*show({"bridges": {"max": 8}}, edit=long_bridge)) == [
        (PATH_1, 90, "bridges: Voa Voa (Ao Vivo) 5-16 (ponte, the bridge copying this handover) lasts 12 bars, "
                     "max 8; the handover it copies, Dançarina 25-32 (entrega), lasts 8: start a cue of "
                     "Voa Voa (Ao Vivo) at or before bar 13")]
    # both too long: a finding per section, both at the handover, which owns the window
    assert rule_findings(*show({"bridges": {"max": 4}}, edit=long_bridge)) == [
        (PATH_1, 90, "bridges: Dançarina 25-32 (entrega) lasts 8 bars, max 4; its bridge, Voa Voa (Ao Vivo) "
                     "5-16 (ponte), lasts 12: end the handover by bar 28 (until: 29)"),
        (PATH_1, 90, "bridges: Voa Voa (Ao Vivo) 5-16 (ponte, the bridge copying this handover) lasts 12 bars, "
                     "max 4; the handover it copies, Dançarina 25-32 (entrega), lasts 8: start a cue of "
                     "Voa Voa (Ao Vivo) at or before bar 9"),
    ]

    # a handover that no bridge copies is measured alone
    def no_bridge(first, second):
        second["bridge"] = False

    assert rule_findings(*show({"bridges": {"max": 4}}, edit=no_bridge)) == [
        (PATH_1, 90, "bridges: Dançarina 25-32 (entrega) lasts 8 bars, max 4, and no bridge copies it: end the "
                     "handover by bar 28 (until: 29)")]

    def short_handover(first, second):
        no_bridge(first, second)
        first["handover"]["until"] = 29

    assert rule_findings(*show({"bridges": {"max": 4}}, edit=short_handover)) == []
    # a bridge whose handover is not in the show is measured alone too
    compiled = evaluate_show(*show({"bridges": {"max": 8}}, edit=long_bridge))[0]
    compiled.tracks[0].sections.pop()
    assert [f.message for f in run_rules(compiled)] == [
        "bridges: Voa Voa (Ao Vivo) 5-16 (ponte, the bridge copying this handover) lasts 12 bars, max 8: start a "
        "cue of Voa Voa (Ao Vivo) at or before bar 13"]


def test_bridges_parameters():
    assert source_findings(*show({"bridges": True})) == [
        (SHOW_PATH, 40, "show-source", "rules.bridges: true is not a mapping {max: 1-32}")]
    assert source_findings(*show({"bridges": {"max": 0, "min": 2}})) == [
        (SHOW_PATH, 41, "show-source", "rules.bridges: max 0 is not a whole number of bars from 1 to 32"),
        (SHOW_PATH, 41, "show-source", "rules.bridges: unexpected key 'min' (allowed: max)"),
    ]
    for top, shown in ((33, "33"), (True, "true"), ("16", "'16'"), (16.0, "16.0")):
        assert source_findings(*show({"bridges": {"max": top}})) == [
            (SHOW_PATH, 41, "show-source", f"rules.bridges: max {shown} is not a whole number of bars from 1 to 32")]
    assert source_findings(*show({"bridges": {}})) == [(SHOW_PATH, 41, "show-source", "rules.bridges: missing key max")]
    assert rule_findings(*show({"bridges": {"max": 32}})) == []
    assert rule_findings(*show({"bridges": {"max": 1}}))      # 1 is in bounds (and every window here is longer)


# ------------------------------------------------------------------ advice --


def test_advice_runs_rules_without_failing():
    def edit(first, second):
        first["cues"][1] = {"at": "break.1", "name": "breu", "look": "breu"}

    looks = {"breu": BREU}
    src, inp = show({"budget": {"breu": {"max": 1}}}, looks, edit, advice={"budget": {"breu": {"max": 0}}})
    compiled, source_found, found, advice = evaluate_show(src, inp)
    assert compiled is not None and source_found == [] and found == []
    assert [(f.path, f.line, f.rule, f.message) for f in advice] == [
        (PATH_1, 20, "show-advice", "budget: breu is used 1 time, max 0: Dançarina 17")]
    assert ADVICE == "show-advice"
    assert run_rules(compiled) == [] and run_rules(compiled, "advice") == advice
    # one rule id in both, with other parameters: a gate and a goal, each reported as itself
    src, inp = show({"budget": {"breu": {"max": 0}}}, looks, edit,
                    advice={"budget": {"breu": {"max": 0}}, "bridges": {"max": 4}})
    _, _, found, advice = evaluate_show(src, inp)
    assert [(f.rule, f.message) for f in found] == [("show-rules", "budget: breu is used 1 time, max 0: Dançarina 17")]
    assert [(f.path, f.line, f.rule, f.message.split(":")[0]) for f in advice] == [
        (PATH_1, 20, "show-advice", "budget"), (PATH_1, 90, "show-advice", "bridges")]
    # no advice, none run
    assert evaluate_show(*show({"budget": {"breu": {"max": 1}}}, looks, edit))[3] == []


def test_advice_parameters_are_checked():
    assert source_findings(*show(advice={"bridgez": {}})) == [
        (SHOW_PATH, 51, "show-source",
         "advice.bridgez: unknown rule 'bridgez'; rules: arrivals, bridges, budget, distinct-drops, drop-contrast, exclusive, follows-set, "
         "follows-track, main-drop, matrix-not-cloned, "
         "movers-aim, neighbours-differ, phrase-aligned, signatures, static-run, total-dark; did you mean 'bridges'?")]
    found = source_findings(*show({"bridges": {"max": 16}}, advice={"bridges": {"max": 40}, "budget": {"nada": {}}}))
    assert found == [
        (SHOW_PATH, 51, "show-source", "advice.bridges: max 40 is not a whole number of bars from 1 to 32"),
        (SHOW_PATH, 52, "show-source",
         "advice.budget: unknown key 'nada' (a look: pulso, respiracao; a gesture: sequence, spiral; "
         "an effect: white-accent, white-flash, strobe, uv)"),
    ]
    found = source_findings(*show(advice={"budget": {"strobe": {"from": "Pedro Sampaio — Dancarina"}}}))
    assert found == [(SHOW_PATH, 51, "show-source",
                      "advice.budget: strobe.from 'Pedro Sampaio — Dancarina' is not a track of this show; "
                      "did you mean 'Pedro Sampaio — Dançarina'?")]
    # an advice that is not a mapping is a schema problem of show.yml
    src, inp = show()
    src.show["advice"] = ["bridges"]
    assert source_findings(src, inp) == [(SHOW_PATH, 0, "show-source", "advice ['bridges'] is not a mapping")]


# ------------------------------------------------------------- parameters --


def test_unknown_rule_id_and_bad_params():
    assert source_findings(*show({"budjet": True})) == [
        (SHOW_PATH, 40, "show-source",
         "rules.budjet: unknown rule 'budjet'; rules: arrivals, bridges, budget, distinct-drops, drop-contrast, exclusive, follows-set, "
         "follows-track, main-drop, matrix-not-cloned, "
         "movers-aim, neighbours-differ, phrase-aligned, signatures, static-run, total-dark; did you mean 'budget'?")]
    found = source_findings(*show({
        "total-dark": {"only": ["breu"]},
        "arrivals": {"draw_differs": "sim"},
        "movers-aim": False,
        "matrix-not-cloned": {"except_moments": "virada"},
        "exclusive": {"keys": ["spiral"], "except_tracks": "Dançarina"},
        "budget": True,
    }))
    assert found == [
        (SHOW_PATH, 40, "show-source", "rules.budget: true is not a mapping of key -> {max?, moments?, from?}"),
        (SHOW_PATH, 40, "show-source",
         "rules.movers-aim: false is not true: movers-aim has no parameters; remove it from rules to not run it"),
        (SHOW_PATH, 41, "show-source",
         "rules.total-dark: only: 'breu' is neither a look nor a gesture (looks: pulso, respiracao; "
         "gestures: sequence, spiral)"),
        (SHOW_PATH, 42, "show-source", "rules.arrivals: draw_differs 'sim' is not true or false"),
        (SHOW_PATH, 44, "show-source",
         "rules.matrix-not-cloned: except_moments 'virada' is not a list of moment names (kebab-case ids)"),
        (SHOW_PATH, 45, "show-source",
         "rules.exclusive: except_tracks 'Dançarina' is not a list of tracks (Artist — Title, or the title)"),
        (SHOW_PATH, 45, "show-source", "rules.exclusive: keys ['spiral'] is not a list of two or more keys"),
    ]
    found = source_findings(*show({"total-dark": {}, "exclusive": {"keys": ["spiral", "nada"], "x": 1}}))
    assert found == [
        (SHOW_PATH, 41, "show-source", "rules.total-dark: missing key only"),
        (SHOW_PATH, 42, "show-source",
         "rules.exclusive: keys: unknown key 'nada' (a look: pulso, respiracao; a gesture: sequence, spiral; "
         "an effect: white-accent, white-flash, strobe, uv)"),
        (SHOW_PATH, 42, "show-source", "rules.exclusive: unexpected key 'x' (allowed: keys, except_tracks)"),
    ]


def test_every_rule_documents_itself():
    assert sorted(RULES) == ["arrivals", "bridges", "budget", "distinct-drops", "drop-contrast", "exclusive",
                             "follows-set", "follows-track", "main-drop", "matrix-not-cloned", "movers-aim",
                             "neighbours-differ", "phrase-aligned", "signatures", "static-run", "total-dark"]
    for name, rule in RULES.items():
        assert rule.name == name and rule.doc and rule.params and "\n" not in rule.params
        assert callable(rule.check) and callable(rule.fn)
    assert EFFECT_KEYS == ("white-accent", "white-flash", "strobe", "uv")


# ------------------------------------------------- identity and monotony --


def analysed(rules=None, advice=None, patch=None, signatures=()):
    """The base show compiled (with `signatures` declared at show.yml lines 61, 62, ...), its
    cached analysis changed by `patch(analysis, compiled)`, then its rules (or its advice) run:
    `(compiled, [(path, line, message)])`."""
    src, inp = show(rules, advice=advice)
    if signatures:
        src.show["identity"] = {"__line__": 60, "signatures": [
            {"__line__": 61 + i, "intent": "Uma assinatura.", **sig} for i, sig in enumerate(signatures)]}
    compiled = evaluate_show(src, inp)[0]
    assert compiled is not None
    analysis = sa.analyse(compiled)
    if patch is not None:
        patch(analysis, compiled)
    return compiled, [(f.path, f.line, f.message) for f in run_rules(compiled, "advice" if advice else "rules")]


def no_light(analysis, compiled):
    for te in analysis.energy:
        te.light = [None] * len(te.light)


AZUL = {"name": "azul", "is": {"movers.colour": ["azul"]}}
VERMELHO = {"name": "vermelho", "is": {"movers.colour": ["vermelho"]}}


def test_signatures_pass_inside_the_promised_share():
    assert analysed({"signatures": True}, signatures=[{**AZUL, "share": {"min": 0.0, "max": 1.0}}])[1] == []


def test_signatures_report_a_share_outside_its_bounds():
    compiled, found = analysed({"signatures": True}, signatures=[{**AZUL, "share": {"min": 0.99}},
                                                                 {**VERMELHO, "share": {"max": 0.05}}])
    shares = {c.name: c.share for c in sa.analyse(compiled).identity.signatures}
    assert shares["azul"] < 0.99 and shares["vermelho"] > 0.05
    assert found == [
        (SHOW_PATH, 61, f"signatures: azul holds {round(shares['azul'] * 100)}% of the night, min 99%"),
        (SHOW_PATH, 62, f"signatures: vermelho holds {round(shares['vermelho'] * 100)}% of the night, max 5%"),
    ]


def test_signatures_cannot_check_without_a_declaration_or_a_light():
    assert analysed({"signatures": True})[1] == [
        (SHOW_PATH, RULES_LINE, "signatures: cannot check: the show declares no identity signatures")]
    found = analysed({"signatures": True}, signatures=[{**AZUL, "share": {"min": 0.5}}], patch=no_light)[1]
    assert found == [(SHOW_PATH, RULES_LINE, "signatures: cannot check: no light is known on any bar of the night")]


def test_static_run_measures_the_long_runs():
    def patch(a, compiled):
        a.variety.static_runs = [sa.Run(0, TRACK_1, (9, 16), 128.0, "groove+drop"),
                                 sa.Run(1, TRACK_2, (5, 8), 119.0, "intro")]
    compiled, found = analysed({"static-run": {"max_seconds": 120}}, patch=patch)
    arrival = compiled.tracks[0].sections[0].origin
    assert found == [(arrival.path, arrival.line,
                      "static-run: Dançarina 9-16 holds one light for 2:08, max 2:00 (music: groove, drop)")]
    assert analysed({"static-run": {"max_seconds": 130}}, patch=patch)[1] == []


def test_static_run_cannot_check_without_a_light():
    found = analysed({"static-run": {"max_seconds": 60}}, patch=no_light)[1]
    assert found == [(SHOW_PATH, RULES_LINE + 1, "static-run: cannot check: no light is known on any bar of "
                                                 "the night")]


def test_neighbours_differ_points_at_the_arrival_of_the_second_track():
    def patch(a, compiled):
        a.variety.similarity = [(0, 0.91)]
    compiled, found = analysed({"neighbours-differ": {"max_similarity": 0.85}}, patch=patch)
    arrival = next(s for s in compiled.tracks[1].sections if s.origin.role == "arrival").origin
    assert found == [(arrival.path, arrival.line,
                      "neighbours-differ: Voa Voa (Ao Vivo) looks like Dançarina (similarity 0.91, max 0.85)")]
    assert analysed({"neighbours-differ": {"max_similarity": 0.91}}, patch=patch)[1] == []


def test_neighbours_differ_prints_enough_decimals_to_read_above_the_max():
    # the base show's real similarity, 0.6667, reads 0.67 at two decimals
    assert analysed({"neighbours-differ": {"max_similarity": 0.66}})[1][0][2] == (
        "neighbours-differ: Voa Voa (Ao Vivo) looks like Dançarina (similarity 0.67, max 0.66)")
    assert analysed({"neighbours-differ": {"max_similarity": 0.67}})[1] == []

    def close(value):
        def patch(a, compiled):
            a.variety.similarity = [(0, value)]
        return patch
    for value, shown in ((0.853, "0.853"), (0.8504, "0.8504"), (0.857, "0.86")):
        found = analysed({"neighbours-differ": {"max_similarity": 0.85}}, patch=close(value))[1]
        assert found[0][2].endswith(f"(similarity {shown}, max 0.85)")


def test_neighbours_differ_falls_back_to_the_first_section_and_cannot_check_without_pairs():
    def patch(a, compiled):
        a.variety.similarity = [(0, 0.9)]
        for section in compiled.tracks[1].sections:
            section.origin = dataclasses.replace(section.origin, role=None)
    compiled, found = analysed({"neighbours-differ": {"max_similarity": 0.5}}, patch=patch)
    first = compiled.tracks[1].sections[0].origin
    assert [(p, ln) for p, ln, _ in found] == [(first.path, first.line)]

    def none(a, compiled):
        a.variety.similarity = []
    found = analysed({"neighbours-differ": {"max_similarity": 0.5}}, patch=none)[1]
    assert found == [(SHOW_PATH, RULES_LINE + 1, "neighbours-differ: cannot check: no known light in a track of "
                                                 "Dançarina / Voa Voa (Ao Vivo)")]


def same_last_drop(first, second):
    """Voa Voa plays Dançarina's espiral and virada: both tracks' drop 21 has one template."""
    second["cues"][1] = copy.deepcopy(first["cues"][1])
    second["cues"][2] = {**copy.deepcopy(first["cues"][2]), "name": "final", "moment": "final",
                         "accents": ["strobe-roll"]}


def test_distinct_drops_compares_the_top_drops_in_clock_order():
    # no drop rises, so each track's main drop is its last: Dançarina 21 is top drop 1, Voa Voa 21
    # top drop 2 (the same salience, later on the clock), then Dançarina 9 and Voa Voa 9
    src, inp = show({"distinct-drops": {"top": 2}}, edit=same_last_drop)
    compiled = evaluate_show(src, inp)[0]
    assert [(d.track, d.bar, d.rank) for d in sa.analyse(compiled).drops] == [
        (TRACK_1, 21, 1), (TRACK_2, 21, 2), (TRACK_1, 9, 3), (TRACK_2, 9, 4)]
    assert rule_findings(src, inp) == [(PATH_2, 30, "distinct-drops: Voa Voa (Ao Vivo) 21 (top drop 2) repeats the "
                                                    "light of Dançarina 21 (top drop 1)")]
    assert rule_findings(*show({"distinct-drops": {"top": 0.5}}, edit=same_last_drop)) == [
        (PATH_2, 30, "distinct-drops: Voa Voa (Ao Vivo) 21 (top drop 2) repeats the light of Dançarina 21 "
                     "(top drop 1)")]                                                 # ceil(0.5 x 4) = 2
    assert rule_findings(*show({"distinct-drops": {"top": 2}})) == []                 # their own lights differ
    assert rule_findings(*show({"distinct-drops": {"top": 1}}, edit=same_last_drop)) == [
        (SHOW_PATH, RULES_LINE + 1, "distinct-drops: cannot check: fewer than two top drops")]


def test_static_run_without_a_section_at_its_first_bar_points_at_the_rule():
    def patch(a, compiled):
        a.variety.static_runs = [sa.Run(0, TRACK_1, (1, 5), 130.0, "")]     # no section holds bar 1
    found = analysed({"static-run": {"max_seconds": 120}}, patch=patch)[1]
    assert found == [(SHOW_PATH, RULES_LINE + 1, "static-run: Dançarina 1-5 holds one light for 2:10, max 2:00")]


def test_distinct_drops_cannot_check_when_every_drop_is_on_the_autoscript():
    def bare(first, second):
        for entry in (first, second):
            entry["cues"] = []
            entry.pop("handover", None)
    src, inp = show({"distinct-drops": {"top": 4}}, edit=bare)
    src.show.pop("handover")
    src.show.pop("bridge")
    compiled = evaluate_show(src, inp)[0]
    assert compiled.tracks[0].sections == compiled.tracks[1].sections == []
    assert len(sa.analyse(compiled).drops) == 4
    assert rule_findings(src, inp) == [
        (SHOW_PATH, RULES_LINE + 1, "distinct-drops: cannot check: no two of the top drops have a known light")]


def test_distinct_drops_cannot_check_without_drops():
    def patch(a, compiled):
        a.drops = []
    found = analysed({"distinct-drops": {"top": 3}}, patch=patch)[1]
    assert found == [(SHOW_PATH, RULES_LINE + 1, "distinct-drops: cannot check: the night has no drops")]


def set_changes(first, second=()):
    def patch(a, compiled):
        for te, bars in zip(a.energy, (first, second)):
            te.changes = [1 if te.first + i in bars else 0 for i in range(len(te.changes))]
    return patch


def test_phrase_aligned_lists_the_changes_off_the_lines():
    patch = set_changes((9, 10, 13, 15))      # a section starts at 9: 9 and 13 are on its 4-bar lines
    found = analysed({"phrase-aligned": {"min_share": 0.9}}, patch=patch)[1]
    assert found == [(SHOW_PATH, RULES_LINE + 1, "phrase-aligned: 50% of the light's changes are on phrase lines, "
                                                 "min 90%; off the lines: Dançarina 10, Dançarina 15")]
    assert analysed({"phrase-aligned": {"min_share": 0.5}}, patch=patch)[1] == []


def test_phrase_aligned_lists_at_most_five_and_reads_advice_lines():
    patch = set_changes((9, 10, 11, 12, 14, 15, 18))
    found = analysed(advice={"phrase-aligned": {"min_share": 1}}, patch=patch)[1]
    assert found == [(SHOW_PATH, ADVICE_LINE + 1,
                      "phrase-aligned: 14% of the light's changes are on phrase lines, min 100%; off the lines: "
                      "Dançarina 10, Dançarina 11, Dançarina 12, Dançarina 14, Dançarina 15, and 1 more")]


def test_phrase_aligned_cannot_check_without_changes():
    found = analysed({"phrase-aligned": {"min_share": 0.5}}, patch=set_changes(()))[1]
    assert found == [(SHOW_PATH, RULES_LINE + 1, "phrase-aligned: cannot check: the light never changes on a "
                                                 "known bar")]


def test_identity_and_monotony_parameters():
    assert source_findings(*show({"signatures": {"a": 1}})) == [
        (SHOW_PATH, 41, "show-source", "rules.signatures: {'a': 1} is not true: signatures has no parameters; "
                                       "remove it from rules to not run it")]
    for bad in (29, 601, True, "60", 60.0):
        assert source_findings(*show({"static-run": {"max_seconds": bad}}))[0][3].startswith(
            "rules.static-run: max_seconds")
    assert source_findings(*show({"static-run": {}})) == [(SHOW_PATH, 41, "show-source",
                                                          "rules.static-run: missing key max_seconds")]
    assert source_findings(*show({"static-run": 60})) == [
        (SHOW_PATH, 40, "show-source", "rules.static-run: 60 is not a mapping {max_seconds: 30-600}")]
    for bad in (-0.1, 1.5, True, "0.5"):
        assert source_findings(*show({"neighbours-differ": {"max_similarity": bad}}))[0][3].startswith(
            "rules.neighbours-differ: max_similarity")
        assert source_findings(*show({"phrase-aligned": {"min_share": bad}}))[0][3].startswith(
            "rules.phrase-aligned: min_share")
    for bad in (0, -1, 1.5, 0.0, True, "3"):
        assert source_findings(*show({"distinct-drops": {"top": bad}}))[0][3].startswith("rules.distinct-drops: top")
    for ok in (1, 4, 0.25, 1.0):
        assert evaluate_show(*show({"distinct-drops": {"top": ok}}))[0] is not None
    assert evaluate_show(*show({"static-run": {"max_seconds": 30}, "neighbours-differ": {"max_similarity": 1},
                                "phrase-aligned": {"min_share": 0}}))[0] is not None


# ---------------------------------------------------- drops and energy --


def drop_rows(**changes):
    """A patch that sets `field=[values per drop, in clock order]` on the four drops of the base
    show (Dançarina 9 and 21, Voa Voa 9 and 21). Their ranks: Dançarina 21 is 1, Voa Voa 21 is 2,
    Dançarina 9 is 3 and Voa Voa 9 is 4 (each track's main drop is its last)."""
    def patch(a, compiled):
        for field, values in changes.items():
            for d, value in zip(sorted(a.drops, key=lambda d: d.clock_s), values):
                setattr(d, field, value)
    return patch


def test_drop_contrast_reports_a_drop_without_contrast_or_change():
    patch = drop_rows(contrast=[None, 3.0, 0.0, 4.5], change=[9, 8, 1, 7])
    compiled, found = analysed({"drop-contrast": {"top": 4, "min_change": 2}}, patch=patch)
    first = compiled.tracks[0].sections[0].origin
    second = next(s for s in compiled.tracks[1].sections if s.bars == (9, 16)).origin
    final = compiled.tracks[1].sections[-1].origin
    assert found == [
        (first.path, first.line, "drop-contrast: Dançarina 9 (top drop 3) has no known contrast"),
        (second.path, second.line, "drop-contrast: Voa Voa (Ao Vivo) 9 (top drop 4) has contrast 0.0 (needs above "
                                   "0) and 1 change, min 2")]
    assert analysed({"drop-contrast": {"top": 0.5, "min_change": 8}}, patch=patch)[1] == [
        (final.path, final.line, "drop-contrast: Voa Voa (Ao Vivo) 21 (top drop 2) has 7 changes, min 8")]


def test_drop_contrast_names_the_criteria_a_real_drop_fails():
    # the base show as compiled: Dançarina 21 (+3.0, 8 changes) and Voa Voa 21 (+4.5, 7) pass;
    # Dançarina 9 follows the autoscript, Voa Voa 9 dims under its bridge with one change
    compiled, found = analysed({"drop-contrast": {"top": 4, "min_change": 2}})
    first = compiled.tracks[0].sections[0].origin
    second = next(s for s in compiled.tracks[1].sections if s.bars == (9, 16)).origin
    assert found == [
        (first.path, first.line, "drop-contrast: Dançarina 9 (top drop 3) has no known contrast"),
        (second.path, second.line, "drop-contrast: Voa Voa (Ao Vivo) 9 (top drop 4) has contrast -5.0 (needs above "
                                   "0) and 1 change, min 2")]


def test_drop_contrast_passes_and_cannot_check_without_drops():
    patch = drop_rows(contrast=[1.0, 3.0, 0.5, 4.5], change=[9, 8, 2, 7])
    assert analysed({"drop-contrast": {"top": 4, "min_change": 2}}, patch=patch)[1] == []

    def none(a, compiled):
        a.drops = []
    assert analysed({"drop-contrast": {"top": 4, "min_change": 2}}, patch=none)[1] == [
        (SHOW_PATH, RULES_LINE + 1, "drop-contrast: cannot check: the night has no drops")]


def test_main_drop_must_answer_at_least_as_well_as_an_earlier_drop():
    # Voa Voa: drop 9 answers 0.52, its main drop 21 answers 0.31
    patch = drop_rows(main=[False, True, False, True], response=[0.1, 0.8, 0.52, 0.31])
    compiled, found = analysed({"main-drop": True}, patch=patch)
    holder = compiled.tracks[1].sections[-1].origin
    assert found == [(holder.path, holder.line,
                      "main-drop: Voa Voa (Ao Vivo)'s main drop 21 answers 0.31, below its drop 9 (0.52)")]
    equal = drop_rows(main=[False, True, False, True], response=[0.1, 0.8, 0.31, 0.31])
    assert analysed({"main-drop": True}, patch=equal)[1] == []
    first_is_main = drop_rows(main=[True, False, True, False], response=[0.1, 0.9, 0.1, 0.9])
    assert analysed({"main-drop": True}, patch=first_is_main)[1] == []        # nothing earlier


def test_main_drop_cannot_check_without_a_response():
    def none(a, compiled):
        a.drops = []
    assert analysed({"main-drop": True}, patch=none)[1] == [
        (SHOW_PATH, RULES_LINE, "main-drop: cannot check: the night has no drops")]
    unknown = drop_rows(main=[True, True, True, True], response=[None, None, None, None])
    assert analysed({"main-drop": True}, patch=unknown)[1] == [
        (SHOW_PATH, RULES_LINE, "main-drop: cannot check: no main drop has a known response")]


def set_follows(first=None, second=None):
    def patch(a, compiled):
        for f, given in zip(a.follows, (first, second)):
            for key, value in (given or {}).items():
                setattr(f, key, value)
    return patch


def test_follows_track_points_at_the_first_missed_boundary():
    patch = set_follows({"rho": 0.12, "lag": 3, "missed": [sa.Boundary(19, 3.0, 0.0), sa.Boundary(21, 4.0, 0.0)]},
                        {"rho": 0.8, "lag": 0})
    compiled, found = analysed({"follows-track": {"min_rho": 0.3, "max_lag": 1}}, patch=patch)
    section = compiled.tracks[0].sections[2].origin
    assert found == [(section.path, section.line,
                      "follows-track: Dançarina: rho 0.12, min 0.30; lag 3 bars, max 1; missed boundaries 19, 21")]
    assert analysed({"follows-track": {"min_rho": 0.1}}, patch=patch)[1] == []
    only_lag = analysed({"follows-track": {"max_lag": 2}}, patch=patch)[1]
    assert [m for _, _, m in only_lag] == ["follows-track: Dançarina: lag 3 bars, max 2; missed boundaries 19, 21"]


def test_follows_track_falls_back_to_the_first_section_and_checks_a_negative_lag():
    patch = set_follows({"rho": 0.1, "lag": 0}, {"rho": 0.9, "lag": -2})
    compiled, found = analysed({"follows-track": {"min_rho": 0.3, "max_lag": 1}}, patch=patch)
    first = compiled.tracks[0].sections[0].origin
    second = compiled.tracks[1].sections[0].origin
    assert [(p, ln) for p, ln, _ in found][0] == (first.path, first.line)
    assert found[0][2].startswith("follows-track: Dançarina: rho 0.10, min 0.30")
    assert found[-1] == (second.path, second.line, "follows-track: Voa Voa (Ao Vivo): lag -2 bars, max 1")


def test_follows_track_cannot_check_a_track_without_the_measure():
    # the base show's v1 maps give a flat music: no rho, and no clear lag over 16 and 28 known bars
    compiled, found = analysed({"follows-track": {"min_rho": 0.3, "max_lag": 1}})
    assert [(f.lag, f.known_bars) for f in sa.analyse(compiled).follows] == [(None, 16), (None, 28)]
    assert found == [
        (SHOW_PATH, RULES_LINE + 1, "follows-track: cannot check Dançarina: no known rho "
                                    "(the light is unknown or too short)"),
        (SHOW_PATH, RULES_LINE + 1, "follows-track: cannot check Voa Voa (Ao Vivo): no known rho "
                                    "(the light is unknown or too short)")]
    assert analysed({"follows-track": {"max_lag": 1}})[1] == []                  # no clear lag is no finding
    short = set_follows({"rho": 0.9, "lag": None, "known_bars": 15}, {"rho": 0.9, "lag": 0})
    assert analysed({"follows-track": {"min_rho": 0.3, "max_lag": 1}}, patch=short)[1] == [
        (SHOW_PATH, RULES_LINE + 1, "follows-track: cannot check Dançarina: no known lag "
                                    "(the light is unknown or too short)")]


def test_follows_track_says_no_clear_lag_beside_a_failed_rho():
    patch = set_follows({"rho": 0.1, "lag": None, "known_bars": 20, "missed": []}, {"rho": 0.9, "lag": 0})
    compiled, found = analysed({"follows-track": {"min_rho": 0.3, "max_lag": 1}}, patch=patch)
    assert [m for _, _, m in found] == ["follows-track: Dançarina: rho 0.10, min 0.30; no clear lag"]


def set_arc(**values):
    def patch(a, compiled):
        for key, value in values.items():
            setattr(a.arc, key, value)
    return patch


def test_follows_set_reports_rho_and_headroom():
    found = analysed({"follows-set": {"min_rho": 0.5, "max_headroom": 0.8}}, patch=set_arc(rho=0.21, headroom=0.95))[1]
    assert found == [(SHOW_PATH, RULES_LINE + 1,
                      "follows-set: rho 0.21 between the owner's energy and the light per track, min 0.50; "
                      "headroom 0.95, max 0.80")]
    only = analysed({"follows-set": {"max_headroom": 0.8}}, patch=set_arc(rho=0.21, headroom=0.95))[1]
    assert [m for _, _, m in only] == ["follows-set: headroom 0.95, max 0.80"]
    assert analysed({"follows-set": {"min_rho": 0.2, "max_headroom": 0.95}},
                    patch=set_arc(rho=0.21, headroom=0.95))[1] == []


def test_follows_set_cannot_check_without_the_measure():
    found = analysed({"follows-set": {"min_rho": 0.5, "max_headroom": 0.8}}, patch=set_arc(rho=None, headroom=None))[1]
    assert found == [
        (SHOW_PATH, RULES_LINE + 1, "follows-set: cannot check rho: fewer than 3 tracks have an owner's energy "
                                    "and a known light"),
        (SHOW_PATH, RULES_LINE + 1, "follows-set: cannot check headroom: no track has an owner's energy and a "
                                    "known p90")]


def test_drop_and_follows_parameters():
    for bad in (0, -1, 1.5, True, "3"):
        assert source_findings(*show({"drop-contrast": {"top": bad, "min_change": 2}}))[0][3].startswith(
            "rules.drop-contrast: top")
    for bad in (0, 10, 2.0, True):
        assert source_findings(*show({"drop-contrast": {"top": 3, "min_change": bad}}))[0][3].startswith(
            "rules.drop-contrast: min_change")
    assert source_findings(*show({"drop-contrast": {"top": 3}}))[0][3] == "rules.drop-contrast: missing key min_change"
    assert source_findings(*show({"main-drop": {"a": 1}}))[0][3].startswith("rules.main-drop: {'a': 1} is not true")
    assert source_findings(*show({"follows-track": {}}))[0][3] == (
        "rules.follows-track: give at least one of min_rho, max_lag")
    assert source_findings(*show({"follows-set": {}}))[0][3] == (
        "rules.follows-set: give at least one of min_rho, max_headroom")
    for bad in (-1.1, 1.1, True, "0.5"):
        assert source_findings(*show({"follows-track": {"min_rho": bad}}))[0][3].startswith(
            "rules.follows-track: min_rho")
        assert source_findings(*show({"follows-set": {"min_rho": bad}}))[0][3].startswith("rules.follows-set: min_rho")
    for bad in (-1, 9, 1.5, True):
        assert source_findings(*show({"follows-track": {"max_lag": bad}}))[0][3].startswith(
            "rules.follows-track: max_lag")
    for bad in (-0.1, 1.1, True):
        assert source_findings(*show({"follows-set": {"max_headroom": bad}}))[0][3].startswith(
            "rules.follows-set: max_headroom")
    assert source_findings(*show({"follows-set": 3}))[0][3].startswith("rules.follows-set: 3 is not a mapping")
    assert evaluate_show(*show({"drop-contrast": {"top": 0.5, "min_change": 1}, "main-drop": True,
                                "follows-track": {"min_rho": -1, "max_lag": 8},
                                "follows-set": {"min_rho": 1, "max_headroom": 0}}))[0] is not None


# ---------------------------------------------------------------- evaluate --


def test_evaluate_show_skips_rules_on_source_findings():
    def rules():
        return {"matrix-not-cloned": True, "exclusive": {"keys": ["spiral", "strobe"]}}

    compiled, source_found, found, _ = evaluate_show(*show(rules()))
    assert compiled is not None and source_found == []
    assert [(f.path, f.line, f.rule, f.message.split(":")[0]) for f in found] == [
        (PATH_1, 30, "show-rules", "exclusive"), (PATH_1, 30, "show-rules", "matrix-not-cloned")]

    def bad_anchor(first, second):
        first["cues"][0]["at"] = "drop.9"

    compiled, source_found, found, _ = evaluate_show(*show(rules(), edit=bad_anchor))
    assert compiled is None and found == []
    assert [(f.path, f.line, f.rule) for f in source_found] == [(PATH_1, 10, "show-source")]
    # a rule parameter problem alone stops the rules too
    compiled, source_found, found, _ = evaluate_show(*show({**rules(), "budget": {"nada": {}}}))
    assert compiled is None and found == [] and [f.rule for f in source_found] == ["show-source"]
    # both kinds at once, sorted by path, line and message
    found = source_findings(*show({"budjet": True}, edit=bad_anchor))
    assert [(f[0], f[1]) for f in found] == [(PATH_1, 10), (SHOW_PATH, 40)]
    # a show without rules runs none
    assert rule_findings(*show()) == []
