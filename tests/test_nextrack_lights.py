import yaml

import nextrack_lights as nl
import soundswitch_format as ssf
from conftest import PROJECT_GUIDS


def run(capsys, *argv):
    code = nl.main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_tracks_lists_both_tracks(make_project, capsys):
    code, out, _ = run(capsys, "--project", str(make_project()), "tracks")
    assert code == 0
    assert out.splitlines() == [
        "0026489d  120   0:16  Pedro Sampaio — Dançarina",
        "00dfbf8c  120   0:16  Chiclete com Banana — Voa Voa",
    ]


def test_tracks_match_folds_accents(make_project, capsys):
    _, out, _ = run(capsys, "--project", str(make_project()), "tracks", "--match", "dancarina")
    assert out.splitlines() == ["0026489d  120   0:16  Pedro Sampaio — Dançarina"]


def test_missing_project_exits_2(capsys):
    code, _, err = run(capsys, "tracks")
    assert code == 2 and "set --project or NEXTRACK_SOUNDSWITCH_PROJECT" in err


def test_project_from_the_environment(make_project, monkeypatch, capsys):
    monkeypatch.setenv("NEXTRACK_SOUNDSWITCH_PROJECT", str(make_project()))
    assert run(capsys, "tracks")[0] == 0


def test_unknown_track_exits_1(make_project, capsys):
    code, _, err = run(capsys, "--project", str(make_project()), "dump", "Nobody")
    assert code == 1 and "no track matches" in err


def _rows(capsys, project, track):
    _, out, _ = run(capsys, "--project", str(project), "dump", track, "--yaml")
    doc = yaml.safe_load(out)
    return {r["fixture"]: r for r in doc["phrases"][0]["rows"]}, doc


def test_dump_reports_the_movers_eight_pulses(make_project, capsys):
    rows, doc = _rows(capsys, make_project(), "Dançarina")
    assert len(doc["phrases"]) == 1 and doc["phrases"][0]["bars"] == "1-8"
    assert rows["Mover 1"]["pulses"] == 8 and rows["Mover 1"]["source"] == "own"
    assert abs(rows["Mover 1"]["lit"] - 0.25) < 0.01
    assert rows["Main"]["lit"] == 1.0 and rows["Main"]["pulses"] == 0


def test_dump_text_table_names_phrase_and_fixtures(make_project, capsys):
    _, out, _ = run(capsys, "--project", str(make_project()), "dump", PROJECT_GUIDS[0][:8])
    assert "Phrase 1  bars 1-8" in out and "Mover 1" in out and "Main" in out


def test_dump_groups_vorlane_cells(make_project, capsys):
    rows, _ = _rows(capsys, make_project(), "Voa Voa")
    assert set(rows) == {"Main", "VORLANE VL-1000 RGBW v2 RGB", "VORLANE VL-1000 RGBW v2 W"}
    assert rows["VORLANE VL-1000 RGBW v2 RGB"]["lit"] == 1.0
    assert abs(rows["VORLANE VL-1000 RGBW v2 W"]["lit"] - 0.5) < 0.01


def test_fixture_without_its_own_span_follows_main(make_script):
    script = make_script(tempo=[(0, 120.0)])
    mover = ssf.track(script, 1167)
    mover.blocks = None
    assert nl.effective_level(script, mover, 5000) == 0x7FFFFFFF / 2**32
    mover.blocks = ssf.Section(1, [ssf.Span(0, 100)])
    assert nl.effective_level(script, mover, 5000) == 0x7FFFFFFF / 2**32
    assert nl.effective_level(script, mover, 1) == 0.0


def test_analyze_reports_the_white_overlap(make_project, capsys):
    code, out, _ = run(capsys, "--project", str(make_project()), "analyze", "Voa Voa")
    assert code == 0
    assert "## Chiclete com Banana — Voa Voa" in out
    assert "VORLANE VL-1000 RGBW v2: 50 %" in out
    assert "Overriding Main (2)" in out


def test_analyze_two_tracks_and_main_range(make_project, capsys):
    _, out, _ = run(capsys, "--project", str(make_project()), "analyze", "Dançarina", "Voa Voa")
    assert out.count("## ") == 2
    assert "| 1 | 1-8 | 50 % | 50 % |" in out
    assert "Overriding Main (1): Mover 1" in out


def _vorlane_pulses(make_script, offsets):
    """Pulses reported for a Vorlane RGB group whose cells pulse 8 times, shifted by `offsets`."""
    def cell(node, shift):
        keys = [k for i in range(8) for k in (
            (i * 2000 + shift, 0), (i * 2000 + shift + 1, ssf.FULL), (i * 2000 + shift + 500, 0))]
        return ssf.Track(node=node, lanes=[ssf.Lane(4, 1, None, [ssf.Key(t, v) for t, v in keys])],
                         blocks=ssf.Section(1, [ssf.Span(0, 16000)]), link=1, colours=None,
                         positions=None, strobes=None, position_blocks=None, shapes=None)

    script = make_script(tempo=[(0, 120.0)])
    script.venues[0].tracks = [cell(1820 + i, s) for i, s in enumerate(offsets)]
    nodes = [ssf.VenueNode(1818, "VORLANE", None, None, 0)] + [
        ssf.VenueNode(1820 + i, f"RGB {i + 1:02d} - VORLANE", 1818, 1, 0) for i in range(len(offsets))]
    data = nl.dump_data(script, [ssf.VenueInfo("V", "g", nodes)], [], 16000)
    return {r["fixture"]: r for r in data["phrases"][0]["rows"]}["VORLANE RGB"]["pulses"]


def test_group_pulses_count_once_for_cells_in_unison(make_script):
    assert _vorlane_pulses(make_script, [0, 0]) == 8


def test_group_pulses_alternating_cells_count_both_steps(make_script):
    assert _vorlane_pulses(make_script, [0, 1000]) == 16
