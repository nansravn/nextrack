import bisect
import datetime
import hashlib
import json
import os
import re
from pathlib import Path

import pytest
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


# ------------------------------------------------------------ compile / apply ----

GUID0 = PROJECT_GUIDS[0]


@pytest.fixture
def idle(monkeypatch):
    """SoundSwitch is not running."""
    monkeypatch.setattr(nl, "soundswitch_running", lambda: False)


def _target(project):
    return project / ("{" + GUID0.upper() + "}.ssfile")


def _choreo_for_project(tmp_path, drop_last=0):
    """Happier's choreography pointed at the test project's first track."""
    data = yaml.safe_load(HAPPIER.read_text(encoding="utf-8"))
    data["soundswitch"] = GUID0.upper()
    if drop_last:
        data["sections"] = data["sections"][:-drop_last]
    path = tmp_path / f"choreo{drop_last}.yml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _backups(project):
    return project.parent / "nextrack-backups"


def _apply(capsys, project, choreo, *flags):
    return run(capsys, "--project", str(project), "apply", str(choreo), *flags)


def _compiled(project, choreo, base_bytes):
    script = ssf.parse_script(base_bytes)
    venues, presets = ssf.Project(project).venues()
    out, _ = nl.ls.compile_choreography(nl.ls.load_choreography(choreo), script,
                                        nl.ls.load_rig(nl.DEFAULT_RIG), venues, presets)
    return ssf.serialize_script(out)


def test_compile_writes_only_the_output(make_project, make_script, tmp_path, capsys):
    project = _happier_project(make_project, make_script)
    before = _target(project).read_bytes()
    choreo = _choreo_for_project(tmp_path)
    out = tmp_path / "o" / "x.ssfile"
    code, stdout, err = run(capsys, "--project", str(project), "compile", str(choreo), "-o", str(out))
    assert code == 0, err
    assert out.read_bytes() == _compiled(project, choreo, before)
    assert _target(project).read_bytes() == before and not _backups(project).exists()
    assert "manual cue" in stdout


def test_compile_starts_from_the_base_when_there_is_one(make_project, make_script, tmp_path, capsys, idle):
    project = _happier_project(make_project, make_script)
    choreo = _choreo_for_project(tmp_path)
    assert _apply(capsys, project, choreo, "--apply", "--accept-resize")[0] == 0
    out = tmp_path / "x.ssfile"
    code, _, err = run(capsys, "--project", str(project), "compile", str(choreo), "-o", str(out))
    base = (_backups(project) / "base" / _target(project).name).read_bytes()
    assert code == 0, err
    assert out.read_bytes() == _compiled(project, choreo, base)


def test_apply_dry_run_writes_nothing(make_project, make_script, tmp_path, capsys):
    project = _happier_project(make_project, make_script)
    before = _target(project).read_bytes()
    code, out, err = _apply(capsys, project, _choreo_for_project(tmp_path))
    assert code == 0, err
    assert _target(project).read_bytes() == before and not _backups(project).exists()
    assert "dry run" in out and "Mover 1" in out and "bytes" in out and "manual cue" in out


def test_apply_refuses_while_soundswitch_runs(make_project, make_script, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(nl, "soundswitch_running", lambda: True)
    project = _happier_project(make_project, make_script)
    before = _target(project).read_bytes()
    code, _, err = _apply(capsys, project, _choreo_for_project(tmp_path), "--apply", "--accept-resize")
    assert code == 1 and "SoundSwitch" in err
    assert _target(project).read_bytes() == before and not _backups(project).exists()


class _Done:
    def __init__(self, out, code=0):
        self.stdout, self.returncode = out, code


@pytest.mark.parametrize("listed", ["SoundSwitch.exe", "SOUNDSWITCH.EXE", "soundswitch.exe",
                                    "SoundSwitch64.exe"])
def test_soundswitch_running_reads_tasklist(listed, monkeypatch, tmp_path):
    monkeypatch.setattr(nl.subprocess, "run", lambda *a, **k: _Done(f"x\n{listed}  12 Console\n"))
    assert nl.soundswitch_running() is True
    monkeypatch.setattr(nl.subprocess, "run", lambda *a, **k: _Done("x\nnotepad.exe\n"))
    assert nl.soundswitch_running() is False


def test_missing_tasklist_outside_wsl_means_nothing_to_check(monkeypatch, tmp_path):
    def missing(*a, **k):
        raise FileNotFoundError("tasklist.exe")

    monkeypatch.setattr(nl.subprocess, "run", missing)
    monkeypatch.setattr(nl, "WSL_INTEROP", tmp_path / "no-such-interop")
    assert nl.soundswitch_running() is False


@pytest.mark.parametrize("how", ["oserror", "exit", "timeout", "missing-under-wsl"])
def test_apply_refuses_when_it_cannot_verify_soundswitch_is_closed(
        how, make_project, make_script, tmp_path, capsys, monkeypatch):
    def fail(*a, **k):
        if how == "oserror":
            raise OSError("boom")
        if how == "timeout":
            raise nl.subprocess.TimeoutExpired("tasklist.exe", 30)
        if how == "missing-under-wsl":
            raise FileNotFoundError("tasklist.exe")
        return _Done("", 1)

    interop = tmp_path / "interop"
    interop.write_text("")
    monkeypatch.setattr(nl, "WSL_INTEROP", interop)
    monkeypatch.setattr(nl.subprocess, "run", fail)
    project = _happier_project(make_project, make_script)
    before = _target(project).read_bytes()
    code, _, err = _apply(capsys, project, _choreo_for_project(tmp_path), "--apply", "--accept-resize")
    assert code == 1 and "cannot verify that SoundSwitch is closed" in err
    assert _target(project).read_bytes() == before and not _backups(project).exists()


def test_a_missing_base_with_a_state_entry_is_refused(make_project, make_script, tmp_path, capsys, idle):
    project = _happier_project(make_project, make_script)
    choreo = _choreo_for_project(tmp_path)
    assert _apply(capsys, project, choreo, "--apply", "--accept-resize")[0] == 0
    (_backups(project) / "base" / _target(project).name).unlink()
    applied = _target(project).read_bytes()
    code, _, err = _apply(capsys, project, choreo, "--apply", "--accept-resize")
    assert code == 1 and "base copy" in err and "earliest backup" in err
    assert _target(project).read_bytes() == applied
    code, _, err = _apply(capsys, project, choreo, "--apply", "--accept-resize", "--adopt-current")
    assert code == 0, err


def test_a_base_without_a_state_entry_must_match_the_project_file(
        make_project, make_script, tmp_path, capsys, idle):
    project = _happier_project(make_project, make_script)
    choreo = _choreo_for_project(tmp_path)
    assert _apply(capsys, project, choreo, "--apply", "--accept-resize")[0] == 0
    edited = ssf.parse_script(_target(project).read_bytes())
    ssf.track(edited, 1167).lanes[0].keys.append(ssf.Key(15000, 0))     # a hand edit
    _target(project).write_bytes(ssf.serialize_script(edited))
    hand = _target(project).read_bytes()
    (_backups(project) / "state.json").unlink()
    code, _, err = _apply(capsys, project, choreo, "--apply", "--accept-resize")
    assert code == 1 and "state.json" in err and "--adopt-current" in err
    assert _target(project).read_bytes() == hand


def test_a_base_without_a_state_entry_is_used_when_the_project_file_matches_it(
        make_project, make_script, tmp_path, capsys, idle):
    project = _happier_project(make_project, make_script)
    current = _target(project).read_bytes()
    (_backups(project) / "base").mkdir(parents=True)
    (_backups(project) / "base" / _target(project).name).write_bytes(current)
    choreo = _choreo_for_project(tmp_path)
    code, _, err = _apply(capsys, project, choreo, "--apply", "--accept-resize")
    assert code == 0, err
    assert _target(project).read_bytes() == _compiled(project, choreo, current)
    state = json.loads((_backups(project) / "state.json").read_text(encoding="utf-8"))
    assert state[GUID0]["base"] == hashlib.sha256(current).hexdigest()


def test_a_base_that_changed_since_it_was_made_is_refused(
        make_project, make_script, tmp_path, capsys, idle):
    project = _happier_project(make_project, make_script)
    choreo = _choreo_for_project(tmp_path)
    assert _apply(capsys, project, choreo, "--apply", "--accept-resize")[0] == 0
    applied = _target(project).read_bytes()
    other = make_script()
    ssf.track(other, 1167).lanes[0].keys.append(ssf.Key(15000, 0))
    (_backups(project) / "base" / _target(project).name).write_bytes(ssf.serialize_script(other))
    code, _, err = _apply(capsys, project, choreo, "--apply", "--accept-resize")
    assert code == 1 and "changed since it was made" in err
    assert _target(project).read_bytes() == applied


def _fail_replacing(monkeypatch, target):
    """`os.replace` fails when it would replace `target`, and only then."""
    real = nl.os.replace

    def replace(src, dst):
        if Path(dst) == target:
            raise OSError("disk full")
        return real(src, dst)

    monkeypatch.setattr(nl.os, "replace", replace)


def test_a_failed_replace_leaves_no_new_base_and_no_state(
        make_project, make_script, tmp_path, capsys, idle, monkeypatch):
    project = _happier_project(make_project, make_script)
    before = _target(project).read_bytes()
    _fail_replacing(monkeypatch, _target(project))
    code, _, err = _apply(capsys, project, _choreo_for_project(tmp_path), "--apply", "--accept-resize")
    assert code == 1 and "disk full" in err
    assert _target(project).read_bytes() == before
    assert list(project.glob("*.tmp")) == [] and list(_backups(project).rglob("*.tmp")) == []
    assert not (_backups(project) / "state.json").exists()
    assert not (_backups(project) / "base" / _target(project).name).exists()


def test_a_failed_replace_keeps_the_base_that_was_there(
        make_project, make_script, tmp_path, capsys, idle, monkeypatch):
    project = _happier_project(make_project, make_script)
    original = _target(project).read_bytes()
    choreo = _choreo_for_project(tmp_path)
    assert _apply(capsys, project, choreo, "--apply", "--accept-resize")[0] == 0
    state = (_backups(project) / "state.json").read_bytes()
    edited = ssf.parse_script(_target(project).read_bytes())
    ssf.track(edited, 1167).lanes[0].keys.append(ssf.Key(15000, 0))
    _target(project).write_bytes(ssf.serialize_script(edited))
    hand = _target(project).read_bytes()
    _fail_replacing(monkeypatch, _target(project))
    code, _, err = _apply(capsys, project, choreo, "--apply", "--accept-resize", "--adopt-current")
    assert code == 1 and "disk full" in err
    assert _target(project).read_bytes() == hand
    assert (_backups(project) / "base" / _target(project).name).read_bytes() == original
    assert (_backups(project) / "state.json").read_bytes() == state


@pytest.mark.parametrize("where", ["own file, other case", "project, other case", "backups"])
def test_compile_and_render_refuse_an_output_in_the_project_or_its_backups(
        where, make_project, make_script, tmp_path, capsys):
    project = _happier_project(make_project, make_script)
    before = {p: p.read_bytes() for p in project.iterdir()}
    folder = {"own file, other case": project, "project, other case": project.parent / project.name.upper(),
              "backups": _backups(project) / "base"}[where]
    for cmd, args, name in (("compile", [str(_choreo_for_project(tmp_path))], "{" + GUID0.lower() + "}.ssfile"),
                            ("render", [GUID0[:8]], "sim.html")):
        out = folder / name
        code, _, err = run(capsys, "--project", str(project), cmd, *args, "-o", str(out))
        assert code == 1 and "pick another -o" in err, (cmd, err)
        assert not out.exists()
    assert {p: p.read_bytes() for p in project.iterdir()} == before
    assert not _backups(project).exists() and not (project.parent / project.name.upper()).exists()


def _meddle(monkeypatch, edit):
    real = nl.ls.compile_choreography

    def meddling(*a, **k):
        out, cues = real(*a, **k)
        edit(out)
        return out, cues

    monkeypatch.setattr(nl.ls, "compile_choreography", meddling)


def test_a_change_outside_every_section_is_refused(make_project, make_script, tmp_path, capsys, idle, monkeypatch):
    project = _happier_project(make_project, make_script)
    before = _target(project).read_bytes()

    def edit(out):  # a key at 1 ms, before bar 1, on a venue track
        trk = ssf.track(out, 1167)
        trk.lanes[0].keys.insert(0, ssf.Key(1, ssf.FULL))

    _meddle(monkeypatch, edit)
    code, _, err = _apply(capsys, project, _choreo_for_project(tmp_path), "--apply", "--accept-resize")
    assert code == 1 and "outside the sections" in err
    assert _target(project).read_bytes() == before and not (_backups(project) / "state.json").exists()


def test_a_block_change_outside_every_section_is_refused(make_project, make_script, tmp_path, capsys, idle, monkeypatch):
    project = _happier_project(make_project, make_script)
    before = _target(project).read_bytes()

    def edit(out):
        ssf.track(out, 1167).blocks.items.append(ssf.Span(1, 10))

    _meddle(monkeypatch, edit)
    code, _, err = _apply(capsys, project, _choreo_for_project(tmp_path), "--apply", "--accept-resize")
    assert code == 1 and "outside the sections" in err
    assert _target(project).read_bytes() == before


def test_main_must_equal_the_base_when_no_section_sets_a_hue(make_project, make_script, tmp_path, capsys, idle, monkeypatch):
    project = _happier_project(make_project, make_script)
    before = _target(project).read_bytes()
    data = yaml.safe_load(HAPPIER.read_text(encoding="utf-8"))
    data["soundswitch"] = GUID0.upper()
    for sec in data["sections"]:
        sec.pop("hue", None)
    choreo = tmp_path / "nohue.yml"
    choreo.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    _meddle(monkeypatch, lambda out: out.main.lanes[0].keys.append(ssf.Key(99999, 0)))
    code, _, err = _apply(capsys, project, choreo, "--apply", "--accept-resize")
    assert code == 1 and "Main" in err
    assert _target(project).read_bytes() == before


# The guard on its own: one section, bars 2-3 (2558-7357 ms at 100 BPM from 158 ms), on
# make_script's script, in a venue with Mover 1 and one Vorlane cell.
GUARD_VENUES = [ssf.VenueInfo("DJ Renan", "0122adb8-e4b9-46c9-96c8-98a7e8f6a5a9", [
    ssf.VenueNode(1167, "Mover 1", None, 1087, 0), ssf.VenueNode(1820, "RGB 01 - V", 1818, 1, 0)])]
GUARD_PRESETS = [ssf.Preset("A", "11111111-2222-3333-4444-555555555555"),
                 ssf.Preset("B", "66666666-7777-8888-9999-aaaaaaaaaaaa")]
AFTER = 7358                                       # the first moment after the section


def _guard(script, **layers):
    choreo = nl.ls.Choreography(
        track="A — B", soundswitch=GUID0.upper(), grid={"bpm": 100, "downbeat": "0:00.158"}, story="x",
        budget=None, base="autoscript", sections=[nl.ls.Section((2, 3), "s", None, layers)])
    return nl._compile_checked(choreo, script, GUARD_VENUES, GUARD_PRESETS, nl.ls.load_rig(nl.DEFAULT_RIG))


def _main_gradient(make_script):
    script = make_script()
    script.main.colours = ssf.Section(1, [ssf.ColourBlock(0, 20_000, 0xFF000000, 0, 0xFFFFFFFF, 0x0000FF00)])
    return script


RED_HUE = {"state": "bright", "colour": "#FF0000"}


def test_the_guard_accepts_a_gradient_cut_by_a_hue_colour(make_script):
    data, _ = _guard(_main_gradient(make_script), hue=RED_HUE)
    left = ssf.parse_script(data).main.colours.items[0]
    assert (left.start, left.end) == (0, 2558) and left.colour_end != 0xFFFFFFFF


def test_the_guard_refuses_a_gradient_that_shows_other_colours_outside(make_script, monkeypatch):
    def edit(out):  # the old cut: the pieces around the section keep the stored colours
        left, _, right = out.main.colours.items
        left.colour_end, left.ext_end = 0xFFFFFFFF, 0x0000FF00
        right.colour, right.ext = 0xFF000000, 0

    _meddle(monkeypatch, edit)
    with pytest.raises(nl.Refused, match="Main the colours"):
        _guard(_main_gradient(make_script), hue=RED_HUE)


def _mover_with_positions(make_script):
    """Mover 1 in one position block over 0-20000 ms: preset A from 0, B from 5000."""
    script = make_script()
    mover = ssf.track(script, 1167)
    mover.shapes = None
    mover.positions = ssf.Positions(2, 1, list(script.main.positions.palette),
                                    [ssf.PositionFlag(0, 0), ssf.PositionFlag(5000, 1)])
    mover.position_blocks = ssf.Section(1, [ssf.Span(0, 20_000)])
    return script


HOLD_A = {"move": "hold", "position": "A"}


def test_the_guard_accepts_the_preset_carried_past_a_section(make_script):
    data, _ = _guard(_mover_with_positions(make_script), movers=HOLD_A)
    mover = ssf.track(ssf.parse_script(data), 1167)
    assert ssf.active_flag(mover, AFTER - 1).preset == 0 and ssf.active_flag(mover, AFTER).preset == 1


@pytest.mark.parametrize("how", ["dropped", "another preset"])
def test_the_guard_refuses_a_preset_changed_after_a_section(how, make_script, monkeypatch):
    def edit(out):
        flags = ssf.track(out, 1167).positions.flags
        i = next(i for i, f in enumerate(flags) if f.t == AFTER)
        if how == "dropped":
            del flags[i]
        else:
            flags[i] = ssf.PositionFlag(AFTER, 0)

    _meddle(monkeypatch, edit)
    with pytest.raises(nl.Refused, match="node 1167 the position"):
        _guard(_mover_with_positions(make_script), movers=HOLD_A)


def test_first_apply_backs_up_writes_and_records(make_project, make_script, tmp_path, capsys, idle):
    project = _happier_project(make_project, make_script)
    old = _target(project).read_bytes()
    choreo = _choreo_for_project(tmp_path)
    code, out, err = _apply(capsys, project, choreo, "--apply", "--accept-resize")
    assert code == 0, err
    new = _target(project).read_bytes()
    assert new == _compiled(project, choreo, old) and new != old
    ssf.parse_script(new)
    root = _backups(project)
    assert (root / "base" / _target(project).name).read_bytes() == old
    stamped = [p for p in root.iterdir() if p.is_dir() and p.name != "base"]
    assert len(stamped) == 1 and re.fullmatch(r"\d{8}-\d{6}(-\d+)?", stamped[0].name)
    assert (stamped[0] / _target(project).name).read_bytes() == old
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    assert state[GUID0] == {"base": hashlib.sha256(old).hexdigest(),
                            "applied": hashlib.sha256(new).hexdigest()}
    assert list(project.glob("*.tmp")) == []
    assert f'cp "{stamped[0] / _target(project).name}" "{_target(project)}"' in out


def test_two_applies_in_one_second_get_distinct_backup_folders(
        make_project, make_script, tmp_path, capsys, idle, monkeypatch):
    monkeypatch.setattr(nl, "_now", lambda: datetime.datetime(2026, 10, 31, 12, 0, 0))
    project = _happier_project(make_project, make_script)
    assert _apply(capsys, project, _choreo_for_project(tmp_path), "--apply", "--accept-resize")[0] == 0
    assert _apply(capsys, project, _choreo_for_project(tmp_path, 1), "--apply", "--accept-resize")[0] == 0
    names = sorted(p.name for p in _backups(project).iterdir() if p.name not in ("base", "state.json"))
    assert names == ["20261031-120000", "20261031-120000-2"]


def test_reapply_after_deleting_a_section_reverts_that_span(make_project, make_script, tmp_path, capsys, idle):
    project = _happier_project(make_project, make_script)
    base = _target(project).read_bytes()
    assert _apply(capsys, project, _choreo_for_project(tmp_path), "--apply", "--accept-resize")[0] == 0
    first = _target(project).read_bytes()
    shorter = _choreo_for_project(tmp_path, 1)
    code, _, err = _apply(capsys, project, shorter, "--apply", "--accept-resize")
    assert code == 0, err
    second = _target(project).read_bytes()
    assert second == _compiled(project, shorter, base) and second != first


def test_edit_since_last_apply_is_refused_then_adopted(make_project, make_script, tmp_path, capsys, idle):
    project = _happier_project(make_project, make_script)
    choreo = _choreo_for_project(tmp_path)
    assert _apply(capsys, project, choreo, "--apply", "--accept-resize")[0] == 0
    edited = ssf.parse_script(_target(project).read_bytes())
    ssf.track(edited, 1167).lanes[0].keys.append(ssf.Key(15000, 0))
    _target(project).write_bytes(ssf.serialize_script(edited))
    hand = _target(project).read_bytes()
    code, _, err = _apply(capsys, project, choreo, "--apply", "--accept-resize")
    assert code == 1 and "edited in SoundSwitch" in err
    assert _target(project).read_bytes() == hand
    code, _, err = _apply(capsys, project, choreo, "--apply", "--accept-resize", "--adopt-current")
    assert code == 0, err
    assert (_backups(project) / "base" / _target(project).name).read_bytes() == hand
    assert _target(project).read_bytes() == _compiled(project, choreo, hand)


def test_a_script_that_does_not_round_trip_is_refused(make_project, make_script, tmp_path, capsys, idle, monkeypatch):
    project = _happier_project(make_project, make_script)
    before = _target(project).read_bytes()
    real = ssf.serialize_script
    monkeypatch.setattr(ssf, "serialize_script", lambda s: real(s) + b"\0")
    code, _, err = _apply(capsys, project, _choreo_for_project(tmp_path), "--apply", "--accept-resize")
    assert code == 1 and "round-trip" in err
    assert _target(project).read_bytes() == before
    assert not (_backups(project) / "state.json").exists()
    assert not (_backups(project) / "base").exists()


def test_a_bad_base_is_refused_and_left_alone(make_project, make_script, tmp_path, capsys, idle):
    project = _happier_project(make_project, make_script)
    before = _target(project).read_bytes()
    base = _backups(project) / "base"
    base.mkdir(parents=True)
    (base / _target(project).name).write_bytes(before[:len(before) // 2])
    code, _, err = _apply(capsys, project, _choreo_for_project(tmp_path), "--apply", "--accept-resize")
    assert code == 1 and "base" in err
    assert _target(project).read_bytes() == before
    assert not (_backups(project) / "state.json").exists()


def test_size_change_needs_accept_resize(make_project, make_script, tmp_path, capsys, idle):
    project = _happier_project(make_project, make_script)
    before = _target(project).read_bytes()
    code, _, err = _apply(capsys, project, _choreo_for_project(tmp_path), "--apply")
    assert code == 1 and "--accept-resize" in err
    assert _target(project).read_bytes() == before
    assert not (_backups(project) / "state.json").exists()


def test_apply_refuses_an_output_that_changes_an_untouched_part(
        make_project, make_script, tmp_path, capsys, idle, monkeypatch):
    project = _happier_project(make_project, make_script)
    before = _target(project).read_bytes()
    real = nl.ls.compile_choreography

    def meddling(*a, **k):
        out, cues = real(*a, **k)
        out.cue_flags = [(1, 2)]
        return out, cues

    monkeypatch.setattr(nl.ls, "compile_choreography", meddling)
    code, _, err = _apply(capsys, project, _choreo_for_project(tmp_path), "--apply", "--accept-resize")
    assert code == 1 and "untouched" in err
    assert _target(project).read_bytes() == before
    assert not (_backups(project) / "state.json").exists()


def test_apply_refuses_an_unfit_choreography_without_touching_anything(make_project, tmp_path, capsys, idle):
    project = make_project()  # 120 BPM, Happier's grid is 100
    before = _target(project).read_bytes()
    code, _, err = _apply(capsys, project, _choreo_for_project(tmp_path), "--apply", "--accept-resize")
    assert code == 1 and "grid" in err
    assert _target(project).read_bytes() == before and not _backups(project).exists()


# ------------------------------------------------------- the real project ----
# Skipped unless $NEXTRACK_SOUNDSWITCH_REAL points at a read-only copy of the project folder.

REAL = os.environ.get("NEXTRACK_SOUNDSWITCH_REAL")


class _Look:
    """What one track shows at a moment: its own intensity, colour and position inside its
    own blocks, else Main's (`main`; None for Main itself, whose flags hold all along)."""

    def __init__(self, trk: ssf.Track, main: "_Look | None" = None):
        self.main = main
        lane = ssf.intensity(trk)
        self.keys = lane.keys if lane else []
        self.key_ts = [k.t for k in self.keys]
        self.spans = [(s.start, s.end) for s in trk.blocks.items] if trk.blocks else []
        self.colours = sorted(trk.colours.items, key=lambda c: c.start) if trk.colours else []
        self.colour_ts = [c.start for c in self.colours]
        self.flags = sorted(trk.positions.flags, key=lambda f: f.t) if trk.positions else []
        self.flag_ts = [f.t for f in self.flags]
        self.palette = trk.positions.palette if trk.positions else []
        self.fspans = [(s.start, s.end) for s in trk.position_blocks.items] if trk.position_blocks else []

    def level(self, t):
        if self.main is not None and not any(a <= t <= b for a, b in self.spans):
            return self.main.level(t)
        i = bisect.bisect_right(self.key_ts, t)
        if i == 0:
            return 0
        if i == len(self.keys):
            return self.keys[-1].level
        a, b = self.keys[i - 1], self.keys[i]
        return round(a.level + (b.level - a.level) * (t - a.t) / (b.t - a.t))

    def colour(self, t):
        i = bisect.bisect_right(self.colour_ts, t)
        for c in self.colours[max(0, i - 3):i]:       # a block owns [start, end)
            if c.start <= t < c.end or c.start == c.end == t:
                f = 0 if c.end == c.start else (t - c.start) / (c.end - c.start)
                return tuple(sum(round(((x >> s) & 255) + (((y >> s) & 255) - ((x >> s) & 255)) * f) << s
                                 for s in (0, 8, 16, 24))
                             for x, y in ((c.colour, c.colour_end), (c.ext, c.ext_end)))
        return self.main.colour(t) if self.main is not None else None

    def preset(self, t):
        lo = None
        if self.main is not None:
            holding = [a for a, b in self.fspans if a <= t <= b]
            if not holding:
                return self.main.preset(t)
            lo = min(holding)
        i = bisect.bisect_right(self.flag_ts, t)
        if i == 0 or (lo is not None and self.flag_ts[i - 1] < lo):
            return self.main.preset(t) if self.main is not None else None
        return self.palette[self.flags[i - 1].preset][0].lower()

    def moments(self) -> set[int]:
        """Every moment where what the track itself shows may change, and its neighbours."""
        ts = set()
        for t in self.key_ts + self.flag_ts:
            ts |= {t - 1, t, t + 1}
        for a, b in self.spans + self.fspans + [(c.start, c.end) for c in self.colours]:
            ts |= {a - 1, a, a + 1, (a + b) // 2, b - 1, b, b + 1}
        return ts


def _near(x, y, step):
    """Equal within `step` (an intensity level), or within `step` per byte (a colour)."""
    if x is None or y is None:
        return x == y
    if isinstance(x, int):
        return abs(x - y) <= step
    return all(abs(((p >> s) & 255) - ((q >> s) & 255)) <= step for p, q in zip(x, y) for s in (0, 8, 16, 24))


def _real_cases():
    happier = nl.ls.load_choreography(HAPPIER)

    def choreo(guid, grid, *sections):
        return nl.ls.Choreography("x — y", guid, grid, "probe", None, "autoscript",
                                  [nl.ls.Section(bars, name, None, layers) for bars, name, layers in sections])

    return {
        "happier": happier,
        # a hue colour over Main's gradients, a mover colour, a sweep between autoscript flags
        "hue-colour": choreo(happier.soundswitch, happier.grid,
                             ((10, 12), "hold", {"movers": {"move": "hold", "position": "DJ Booth",
                                                            "colour": "#FFB347", "level": 0.5}}),
                             ((22, 25), "hue", {"hue": {"state": "bright", "colour": "#FF0000"}}),
                             ((34, 36), "sweep", {"movers": {"move": "sweep", "every": "1bar",
                                                             "positions": ["Up", "Stage Left"]}})),
        # a hold that ends between two autoscript flags of Mover 1's position block
        "position-after": choreo("0026489D-4CB2-42CA-B2D9-9746823AAF0A", {"bpm": 154.0, "downbeat": "0:00.032"},
                                 ((33, 34), "hold", {"movers": {"move": "hold", "position": "Stage Left"}})),
    }


@pytest.mark.skipif(not REAL, reason="NEXTRACK_SOUNDSWITCH_REAL not set")
@pytest.mark.parametrize("case", ["happier", "hue-colour", "position-after"])
def test_real_apply_output_shows_the_same_room_outside_the_sections(case):
    """Through the apply guard, every venue node and Main show the base's intensity (within
    one level step), colour (within one step per byte) and position outside the sections;
    group nodes are not touched at all."""
    project = ssf.Project(Path(REAL))
    choreo = _real_cases()[case]
    path = project.script_path(choreo.soundswitch)
    if not path.is_file():
        pytest.skip(f"{path.name} is not in this copy of the project")
    venues, presets = project.venues()
    base = ssf.parse_script(path.read_bytes())
    data, _ = nl._compile_checked(choreo, base, venues, presets, nl.ls.load_rig(nl.DEFAULT_RIG))
    out = ssf.parse_script(data)
    g = ssf.grid(base)
    windows = [(g.ms(s.bars[0]), g.ms(s.bars[1] + 1) - 1) for s in choreo.sections]
    venue, _ = nl.ls._venue_of(base, venues)
    ids = {n.id for n in venue.nodes}
    groups = {n.id for n in venue.nodes if n.look is None} | {n.parent for n in venue.nodes}
    edges = {t for s, e in windows for t in (s - 2, s - 1, e + 1, e + 2)}
    looks = [(_Look(base.main), _Look(out.main))]
    main_ts = looks[0][0].moments() | looks[0][1].moments() | edges
    pairs = [(b, o) for vb, vo in zip(base.venues, out.venues) for b, o in zip(vb.tracks, vo.tracks)
             if b.node in ids]
    checked = 0
    for b, o in [(base.main, out.main)] + pairs:
        lb, lo = (looks[0] if b is base.main else (_Look(b, looks[0][0]), _Look(o, looks[0][1])))
        if b.node in groups and b is not base.main:
            assert o == b, f"group node {b.node} changed"
        for t in sorted(lb.moments() | lo.moments() | main_ts):
            if t < 0 or any(s <= t <= e for s, e in windows):
                continue
            checked += 1
            assert _near(lb.level(t), lo.level(t), 1), (case, b.node, t, "level")
            assert _near(lb.colour(t), lo.colour(t), 1), (case, b.node, t, "colour")
            assert lb.preset(t) == lo.preset(t), (case, b.node, t, "position")
    assert checked > 1000
