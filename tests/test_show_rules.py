"""The show rules: occurrences, the rules, their parameter checks, advice and `evaluate_show`."""
import dataclasses

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
         "advice.bridgez: unknown rule 'bridgez'; rules: arrivals, bridges, budget, exclusive, matrix-not-cloned, "
         "movers-aim, total-dark; did you mean 'bridges'?")]
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
         "rules.budjet: unknown rule 'budjet'; rules: arrivals, bridges, budget, exclusive, matrix-not-cloned, "
         "movers-aim, total-dark; did you mean 'budget'?")]
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
    assert sorted(RULES) == ["arrivals", "bridges", "budget", "exclusive", "matrix-not-cloned", "movers-aim",
                             "total-dark"]
    for name, rule in RULES.items():
        assert rule.name == name and rule.doc and rule.params and "\n" not in rule.params
        assert callable(rule.check) and callable(rule.fn)
    assert EFFECT_KEYS == ("white-accent", "white-flash", "strobe", "uv")


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
