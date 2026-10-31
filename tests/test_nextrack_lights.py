import json
import re

import yaml

import nextrack_lights as nl
import soundswitch_format as ssf
from conftest import PROJECT_GUIDS, REPO_ROOT


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


# ------------------------------------------------------------------ render ----

HAPPIER = REPO_ROOT / "lightshows/tracks/marshmello-x-bastille-happier.yml"


def blob(html: str) -> dict:
    """The JSON the page embeds (after `const S = `)."""
    m = re.search(r"const S = (\{.*?\});\n", html, re.S)
    assert m, "no data blob in the page"
    return json.loads(m.group(1))


def render(capsys, project, tmp_path, *extra, track="Dançarina"):
    out = tmp_path / "out" / "sim.html"
    code, _, err = run(capsys, "--project", str(project), "render", track, *extra, "-o", str(out))
    return code, err, out


def test_render_writes_a_self_contained_page(make_project, tmp_path, capsys):
    code, err, out = render(capsys, make_project(), tmp_path)
    assert code == 0, err
    html = out.read_text(encoding="utf-8")
    assert "<html" in html and "/*__DATA__*/" not in html
    assert "http://" not in html and "https://" not in html
    data = blob(html)
    assert {"Mover 1", "Main"} <= set(data["before"])
    assert data["after"] is None and data["sections"] == []
    assert data["grid"] == [[0, 120.0]]
    assert data["before"]["Mover 1"]["k"][:3] == [[0, 0.0], [1, 1.0], [500, 0.0]]
    assert data["before"]["Mover 1"]["B"] == [[0, 16000]]
    assert data["rig"]["mover-ne"] == {"corner": "NE", "kind": "mover", "node": "Mover 1"}


def _happier_project(make_project, make_script):
    """The test project with Happier's grid (100 BPM at 0.158 s) on its first track."""
    project = make_project()
    path = project / ("{" + PROJECT_GUIDS[0].upper() + "}.ssfile")
    path.write_bytes(ssf.serialize_script(make_script()))
    return project


def test_render_with_choreo_adds_the_compiled_after(make_project, make_script, tmp_path, capsys):
    project = _happier_project(make_project, make_script)
    code, err, out = render(capsys, project, tmp_path, "--choreo", str(HAPPIER))
    assert code == 0, err
    data = blob(out.read_text(encoding="utf-8"))
    assert len(data["sections"]) == 15 and data["after"] is not None
    first = data["sections"][0]
    assert first["name"] == "intro-batida" and first["bars"] == [1, 8]
    assert first["start"] == 158 and first["end"] == 158 + 8 * 2400
    assert {"Mover 1", "Main"} <= set(data["after"])
    # intro: movers off in the compiled script, but the autoscript pulse in the base
    assert [k for k in data["after"]["Mover 1"]["k"] if k[0] < 5000 and k[1] > 0] == []
    assert any(k[1] > 0 for k in data["before"]["Mover 1"]["k"] if k[0] < 5000)
    assert any(c["fixture"] == "haze" for c in data["cues"])


def test_render_prefers_the_base_copy_as_before(make_project, make_script, tmp_path, capsys):
    project = _happier_project(make_project, make_script)
    base = make_script()
    ssf.track(base, 1167).lanes[0].keys = [ssf.Key(0, ssf.FULL), ssf.Key(9000, ssf.FULL)]
    folder = project.parent / "nextrack-backups" / "base"
    folder.mkdir(parents=True)
    (folder / ("{" + PROJECT_GUIDS[0].upper() + "}.ssfile")).write_bytes(ssf.serialize_script(base))
    _, _, out = render(capsys, project, tmp_path)
    assert blob(out.read_text(encoding="utf-8"))["before"]["Mover 1"]["k"] == [[0, 1.0], [9000, 1.0]]


def test_render_refuses_a_choreo_for_another_grid(make_project, tmp_path, capsys):
    code, err, out = render(capsys, make_project(), tmp_path, "--choreo", str(HAPPIER))
    assert code == 1 and "grid" in err and not out.exists()


def test_render_refuses_an_invalid_choreo(make_project, tmp_path, capsys):
    bad = tmp_path / "bad.yml"
    bad.write_text("track: x\n", encoding="utf-8")
    code, err, _ = render(capsys, make_project(), tmp_path, "--choreo", str(bad))
    assert code == 1 and "choreography" in err


def test_page_data_cannot_close_the_script_tag():
    html = nl.page_html({"title": "</script><b>x"})
    assert "</script><b>" not in html and blob(html)["title"] == "</script><b>x"


def test_sim_data_exports_names_levels_and_effective_lanes(make_script):
    script = make_script(tempo=[(0, 120.0)])
    ssf.track(script, 1167).positions = ssf.Positions(
        2, 1, [("11111111-2222-3333-4444-555555555555", 0)], [ssf.PositionFlag(1200, 0)])
    nodes = [ssf.VenueNode(1167, "Mover 1", None, 1, 0), ssf.VenueNode(1820, "RGB 01 - V", 1818, 1, 0)]
    venues = [ssf.VenueInfo("DJ Renan", "0122adb8-e4b9-46c9-96c8-98a7e8f6a5a9", nodes)]
    rig = nl.ls.load_rig(REPO_ROOT / "lightshows/rig.yml")
    d = nl.sim_data(script, venues, [ssf.Preset("Stage Left", "11111111-2222-3333-4444-555555555555")], rig)
    mover = d["before"]["Mover 1"]
    assert mover["k"] == [[1000, 0.0], [1001, 1.0], [1300, 0.0]]
    assert mover["C"] == [[1000, 2000, [0, 255, 55, 0], [55, 0, 255, 0]]]
    assert mover["G"][0][:3] == [1000, 2000, 2]
    assert mover["D"] == [[1200, "Stage Left"]]
    assert d["before"]["Main"]["k"] == [[0, 0.5], [10000, 0.5]]   # level / 2**32, to 4 places
    assert "RGB 01 - V" not in d["before"]   # only the nodes the rig names are exported
