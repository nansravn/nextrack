"""The report's six analysis sections (show_report.py) on the two-track show.

`two_track_show` at 120 BPM: Dançarina plays bars 1-24 (window 1-32), Voa Voa (Ao Vivo) bars
5-32; both maps have drops at 9 and 21 and a 4-bar break (17-20) before the last drop. The maps
are made version 2 (a `mix` block) unless a test says otherwise, so no track is `(interim)`.
Each test reads the real analysis (`show_analysis.analyse`) and checks a section's header and
one line it can name."""
import pytest

import show_analysis as sa
import show_report as sr
from show_language import compile_show
from showdata import FILE_1, TRACK_1, TRACK_2, two_track_show

TITLE_1, TITLE_2 = TRACK_1.split(" — ")[1], TRACK_2.split(" — ")[1]


def analysed(edit=None, v2=True, tweak=None):
    src, inp = two_track_show()
    if edit:
        edit(src)
    for data in inp.maps.values():
        if v2:
            data["map_version"] = 2
            data["mix"] = {"loudness": "4" * 8 + "8" * 8 + "3" * 4 + "9" * 12, "brightness": "5" * 32}
        if tweak:
            tweak(data)
    show, findings = compile_show(src, inp)
    assert findings == [], findings
    return sa.analyse(show), show


def test_sections_are_named_in_report_order():
    assert sr.REPORT_SECTIONS == ("summary", "tracks", "peaks", "hits", "follows", "drops", "builds", "variety",
                                  "arc", "identity", "budget", "arrivals", "advice", "decided", "findings")


def test_follows_prints_a_rho_line_per_track():
    a, show = analysed()
    lines = sr.select(sr.follows_items(a, show), None)
    assert lines[0] == "follows"
    for title in (TITLE_1, TITLE_2):
        line = next(l for l in lines if l.startswith(f"  {title} · "))
        assert " · rho " in line and " · lag " in line and " · unknown " in line
    rho = a.follows[0].rho
    assert f"rho {'-' if rho is None else f'{rho:.2f}'}" in next(l for l in lines if l.startswith(f"  {TITLE_1} · "))


def test_a_v1_map_marks_the_track_interim():
    a, show = analysed(v2=False)
    lines = sr.select(sr.follows_items(a, show), None)
    assert any(l.startswith(f"  {TITLE_1} (interim) · rho ") for l in lines)
    a, show = analysed()
    assert not any("(interim)" in l for l in sr.select(sr.follows_items(a, show), None))


def test_drops_print_rank_1_first_and_the_agreement():
    a, show = analysed()
    lines = sr.select(sr.drops_items(a, show), None)
    assert lines[0] == "drops"
    items = [l for l in lines if l.startswith("  rank ") and l[7].isdigit()]
    assert len(items) == len(a.drops) == 4
    first = a.drops[0]
    assert items[0].startswith(f"  rank 1 · ") and f"{first.track.split(' — ')[1]} {first.bar} · " in items[0]
    assert f"salience {first.salience:.2f}" in items[0] and "response " in items[0]
    assert lines[-1].startswith("  agreement: ")


def test_builds_print_each_build_and_how_the_light_goes_into_the_drop():
    a, show = analysed()
    lines = sr.select(sr.builds_items(a, show), None)
    assert lines[0] == "builds"
    line = next(l for l in lines if f"· {TITLE_1} 17-20 · " in l)
    assert " · music " in line and " · activity " in line and line.endswith(f"into {a.builds[0].into}")


def test_variety_prints_a_static_run_across_a_leg_with_both_tracks():
    def edit(src):
        src.track_files[FILE_1]["cues"][2]["look"] = "pulso"      # the last drop plays the handover's look
    a, show = analysed(edit=edit)
    lines = sr.select(sr.variety_items(a, show), None)
    assert lines[0] == "variety"
    assert any(f"· {TITLE_1} 21 – {TITLE_2} 8 · 0:16 · drop+intro" in l for l in lines)
    templates, drops = a.variety.templates
    assert f"  drop templates: {templates} distinct of {drops} drops" in lines
    assert any(l.startswith(f"  uses {TITLE_2}: looks ") for l in lines)


def test_variety_and_identity_leave_none_out():
    a, show = analysed()
    assert any(l.startswith("  dominant look: ") for l in sr.select(sr.variety_items(a, show), None))
    assert not any(l.startswith("  dominant ") and ": none " in l for l in sr.select(sr.variety_items(a, show), None))
    assert any(l.startswith("  undeclared look: ") for l in sr.select(sr.identity_items(a, show), None))
    assert not any(l.startswith("  undeclared gesture") for l in sr.select(sr.identity_items(a, show), None))


def test_arc_prints_a_line_per_track_and_the_checks():
    a, show = analysed()
    lines = sr.select(sr.arc_items(a, show), None)
    assert lines[0] == "arc"
    assert any(l.startswith(f"  0:00 · {TITLE_1} · e- · light ") for l in lines)     # no owner energy here
    assert any(l.startswith("  rho ") for l in lines) and any(l.startswith("  headroom ") for l in lines)


def test_identity_prints_the_declared_signatures_share():
    def edit(src):
        src.show["identity"] = {"signatures": [
            {"name": "azul-espaco", "intent": "O azul é o espaço.", "is": {"movers.colour": ["azul"]},
             "share": {"min": 0.9}}]}
    a, show = analysed(edit=edit)
    lines = sr.select(sr.identity_items(a, show), None)
    assert lines[0] == "identity"
    check = a.identity.signatures[0]
    line = next(l for l in lines if l.startswith("  signature azul-espaco"))
    assert f"holds {round(100 * check.share)}% of the night" in line and "wanted min 90%" in line
    assert "below min" in line
    _, track, (lo, hi), _ = check.occurrences[0]
    assert any(l.startswith("    ") and f"{track.split(' — ')[1]} {lo}-{hi}" in l for l in lines)


def test_identity_arc_falls_back_to_the_set():
    a, show = analysed()
    assert sr.select(sr.identity_items(a, show), None)[1] == "  arc: none"
    assert sr.select(sr.identity_items(a, show, set_arc="waves"), None)[1] == "  arc: waves (the set's)"

    def edit(src):
        src.show["identity"] = {"arc": "slow-burn", "signatures": []}
    a, show = analysed(edit=edit)
    assert sr.select(sr.identity_items(a, show, set_arc="waves"), None)[1] == "  arc: slow-burn (identity)"


@pytest.mark.parametrize("name", ["follows", "drops", "builds", "variety", "arc", "identity"])
def test_select_keeps_the_frame_and_the_lines_that_name_a_track(name):
    a, show = analysed()
    items = getattr(sr, f"{name}_items")(a, show)
    assert sr.select(items, None) == [t for t, _ in items]
    for index in (0, 1):
        kept = sr.select(items, index)
        named = [t for t, n in items if n is not None and index in n]
        assert [t for t in kept if t in named] == named
        if named:
            assert kept[0] == name
    assert sr.select([("x", None), ("night line", frozenset())], 0) == []


def test_an_autoscript_night_with_no_drops_prints_dashes_not_a_crash():
    def edit(src):
        for entry in src.track_files.values():
            entry["cues"] = []
            entry.pop("handover", None)
        src.show.pop("handover", None)
        src.show.pop("bridge", None)

    a, show = analysed(edit=edit, tweak=lambda data: data.update(drops=[]))
    assert sr.select(sr.drops_items(a, show), None)[2:] == ["  no map drop sounds"]
    assert all(" · rho - · agree - · lag - · " in l for l in sr.select(sr.follows_items(a, show), None)[2:])
    for name in ("builds", "variety", "arc", "identity"):
        assert sr.select(getattr(sr, f"{name}_items")(a, show), None)[0] == name
    assert "  no breather: -" in sr.select(sr.arc_items(a, show), None)
    assert sr.light_unknown_s(a.clock, a.energy) == pytest.approx(a.clock.total_s)


def test_light_unknown_counts_the_autoscripts_leg_seconds():
    a, show = analysed()
    # Dançarina's bars 1-8 are the autoscript's: 8 bars of 2 s
    assert sr.light_unknown_s(a.clock, a.energy) == pytest.approx(16.0)
