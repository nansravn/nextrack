"""Tests for `nextrack_lights.py status`: which tracks are compliant (scripts/README.md).

The project is the synthetic one from conftest with Happier's grid and the haze machine on
its first track; the repo is the mini repo plus the real rig and that track's choreography.
"""
import hashlib
import re
import shutil

import pytest
import yaml

import nextrack_lights as nl
import soundswitch_format as ssf
from conftest import PROJECT_GUIDS, REPO_ROOT, _choreo_for_project, _happier_project, build_mini_repo

GUID0, GUID1 = PROJECT_GUIDS
POOL_DANCARINA = "Pedro Sampaio & MC Pedrinho — Dançarina"  # the mini repo's pool entry
HEADER = "track" + " " * 22 + "choreography  applied  haze  compliant  note"


def run(capsys, *argv):
    code = nl.main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def _edit_choreo(path, edit):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


@pytest.fixture
def room(make_project, make_script, tmp_path):
    """`(project, repo)`: the haze project, and a mini repo with the rig and the first track's
    choreography, whose `track:` names the pool entry (its artist differs from the track map's)."""
    project = _happier_project(make_project, make_script, haze=True)
    repo = build_mini_repo(tmp_path / "repo").root
    (repo / "lightshows" / "tracks").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "lightshows" / "rig.yml", repo / "lightshows" / "rig.yml")
    _edit_choreo(_choreo_for_project(repo / "lightshows" / "tracks"),
                 lambda d: d.update(track=POOL_DANCARINA))
    return project, repo


def _choreo(repo):
    return repo / "lightshows" / "tracks" / "choreo0.yml"


def _row(room, guid=GUID0, choreo="default", rig=None):
    project, repo = room
    rig = nl.ls.load_rig(rig or repo / "lightshows" / "rig.yml")
    return nl.track_status(ssf.Project(project), guid, _choreo(repo) if choreo == "default" else choreo,
                           rig, repo)


def _status(capsys, room, *flags):
    project, repo = room
    return run(capsys, "--project", str(project), "status", "--repo", str(repo), *flags)


def _apply(capsys, room):
    project, repo = room
    code, _, err = run(capsys, "--project", str(project), "apply", str(_choreo(repo)), "--apply", "--accept-resize")
    assert code == 0, err


def _edit_script(room, edit):
    """A hand edit in SoundSwitch: `edit` changes the first track's project script."""
    target = room[0] / ("{" + GUID0.upper() + "}.ssfile")
    script = ssf.parse_script(target.read_bytes())
    edit(script)
    target.write_bytes(ssf.serialize_script(script))


def _edit_mover(script):
    key = ssf.track(script, 1167).lanes[0].keys[0]
    key.level = 5 if key.level != 5 else 9


def _cells(line):
    return re.split(r" {2,}", line.rstrip())


def test_no_choreography(room):
    row = _row(room, GUID1, None)
    assert row["track"] == "Chiclete com Banana — Voa Voa"
    assert row["choreography"] is False and row["compliant"] is False


def test_never_applied(room):
    row = _row(room)
    assert row["choreography"] is True
    assert row["applied"] is False and row["haze"] is False and row["compliant"] is False


def test_applied_and_current_is_compliant(room, idle, capsys):
    _apply(capsys, room)
    assert _row(room) == {"track": "Pedro Sampaio — Dançarina", "choreography": True, "applied": True,
                          "haze": True, "note": None, "compliant": True}
    code, out, err = _status(capsys, room)
    assert code == 0, err
    assert out.splitlines() == [
        HEADER,
        "Pedro Sampaio — Dançarina  yes" + " " * 11 + "yes" + " " * 6 + "yes" + " " * 3 + "yes",
        "1 of 1 tracks compliant",
        "1 more track in the project has no choreography",
    ]


def test_hand_edit_keeps_compliance_with_a_note(room, idle, capsys):
    _apply(capsys, room)
    _edit_script(room, _edit_mover)
    row = _row(room)
    assert row["applied"] is True and row["haze"] is True and row["compliant"] is True
    assert row["note"] == "edited in SoundSwitch after the apply"


def test_hand_edit_that_breaks_the_haze(room, idle, capsys):
    _apply(capsys, room)

    def fog_off(script):
        ssf.intensity(ssf.track(script, 1936)).keys[0].level = 0

    _edit_script(room, fog_off)
    row = _row(room)
    assert row["haze"] is False and row["compliant"] is False


def test_accepted_edits_note(room, idle, capsys):
    _apply(capsys, room)
    _edit_script(room, _edit_mover)
    code, _, err = run(capsys, "--project", str(room[0]), "accept", GUID0, "--apply")
    assert code == 0, err
    row = _row(room)
    assert row["note"] == "hand edits accepted" and row["compliant"] is True


def test_yaml_change_after_apply(room, idle, capsys):
    _apply(capsys, room)
    _edit_choreo(_choreo(room[1]), lambda d: d.update(sections=d["sections"][:-1]))
    row = _row(room)
    assert row["applied"] is False and row["compliant"] is False


def test_rig_level_change(room, idle, capsys, tmp_path):
    _apply(capsys, room)
    rig = tmp_path / "rig.yml"
    text = (REPO_ROOT / "lightshows" / "rig.yml").read_text(encoding="utf-8")
    assert text.count("level: 0.5") == 1
    rig.write_text(text.replace("level: 0.5", "level: 0.4"), encoding="utf-8")
    row = _row(room, rig=rig)
    assert row["applied"] is False and row["haze"] is False and row["compliant"] is False
    code, out, err = _status(capsys, room, "--rig", str(rig))
    assert code == 0, err
    assert _cells(out.splitlines()[1])[1:5] == ["yes", "no", "no", "no"]


def test_compile_refusal_is_the_reason(room, idle, capsys):
    _apply(capsys, room)
    _edit_choreo(_choreo(room[1]), lambda d: d["grid"].update(bpm=90))
    row = _row(room)
    assert isinstance(row["applied"], str) and "grid" in row["applied"]
    assert row["compliant"] is False


def test_a_corrupt_base_copy_is_the_reason(room, idle, capsys):
    _apply(capsys, room)
    (room[0].parent / "nextrack-backups" / "base" / ("{" + GUID0.upper() + "}.ssfile")).write_bytes(b"junk")
    row = _row(room)
    assert isinstance(row["applied"], str) and "base copy" in row["applied"]
    assert row["compliant"] is False


def test_a_corrupt_project_script_is_the_reason(room, capsys):
    (room[0] / ("{" + GUID0.upper() + "}.ssfile")).write_bytes(b"junk")
    row = _row(room)
    assert isinstance(row["haze"], str) and "project file" in row["haze"]
    assert row["compliant"] is False
    code, out, err = _status(capsys, room, "--block", "alpha-festa")
    assert code == 0, err
    lines = out.splitlines()
    assert _cells(lines[1])[3] == row["haze"]
    assert _cells(lines[2])[0] == "Chiclete com Banana — Voa Voa"  # the other track goes on
    assert lines[-1] == "0 of 2 tracks compliant"


@pytest.mark.parametrize("text", ["{not json", "[1, 2]", '{"' + GUID0 + '": 5}'],
                         ids=["not-json", "not-a-mapping", "entry-not-a-mapping"])
def test_a_corrupt_state_file_is_the_reason(room, idle, capsys, text):
    _apply(capsys, room)
    (room[0].parent / "nextrack-backups" / "state.json").write_text(text, encoding="utf-8")
    row = _row(room)
    assert isinstance(row["applied"], str) and row["applied"].startswith("state.json unreadable: ")
    assert row["compliant"] is False
    code, out, err = _status(capsys, room)
    assert code == 0, err
    assert _cells(out.splitlines()[1])[2] == row["applied"]


def test_a_haze_check_error_is_the_reason(room, idle, capsys, monkeypatch):
    _apply(capsys, room)

    def fail(*args, **kwargs):
        raise nl.ls.CompileError("no venue holds this script's nodes")

    monkeypatch.setattr(nl.ls, "haze_problem", fail)
    row = _row(room)
    assert isinstance(row["haze"], str) and "no venue holds this script's nodes" in row["haze"]
    assert row["compliant"] is False
    code, out, err = _status(capsys, room)
    assert code == 0, err
    assert _cells(out.splitlines()[1])[3] == row["haze"]


def test_an_unreadable_venues_file_stops_status(room, capsys):
    (room[0] / "SoundSwitchVenues.bin").write_bytes(b"junk")
    code, out, err = _status(capsys, room)
    assert code == 1 and out == ""
    assert "SoundSwitchVenues.bin" in err and "no track can be judged" in err


def test_invalid_choreography_and_unknown_guid(room, capsys):
    tracks = room[1] / "lightshows" / "tracks"
    shutil.copy(_choreo(room[1]), tracks / "bad.yml")
    _edit_choreo(tracks / "bad.yml", lambda d: (d.update(soundswitch=GUID1.upper()), d.pop("story")))
    shutil.copy(_choreo(room[1]), tracks / "stranger.yml")
    stranger = "0000aaaa-0000-4000-8000-000000000000"
    _edit_choreo(tracks / "stranger.yml", lambda d: d.update(soundswitch=stranger.upper()))
    (tracks / "broken.yml").write_text("track: [unclosed\n", encoding="utf-8")

    bad = _row(room, GUID1, tracks / "bad.yml")
    assert bad["choreography"] is True and bad["applied"].startswith("invalid choreography: ")
    assert "story" in bad["applied"] and bad["compliant"] is False
    unknown = _row(room, stranger, tracks / "stranger.yml")
    assert unknown["applied"] == "its GUID is not in the project" and unknown["compliant"] is False
    assert unknown["track"] == POOL_DANCARINA

    code, out, err = _status(capsys, room)
    assert code == 0, err
    # the long reasons do not widen the applied column: only their own row is pushed
    assert out.splitlines()[0] == "track" + " " * 36 + "choreography  applied  haze  compliant  note"
    rows = {_cells(line)[0]: _cells(line) for line in out.splitlines()[1:-2]}
    assert rows["lightshows/tracks/broken.yml"][2].startswith("invalid choreography: ")
    assert rows["Chiclete com Banana — Voa Voa"][2] == bad["applied"]
    assert rows[POOL_DANCARINA][2] == "its GUID is not in the project"
    assert out.splitlines()[-2:] == ["0 of 4 tracks compliant",
                                     "0 more tracks in the project have no choreography"]


STATUS_BLOCK = """\
---
name: Alpha Status
function: peak
style: open-format
duration: 20m
genres: [alpha]
bpm: [100, 135]
energy: [7, 8]
key_journey: TBD
lightshow: null
---

## Tracklist
1. Pedro Sampaio & MC Pedrinho — Dançarina  · e8
2. Nobody — Song Z  · e5
3. Pedro Sampaio — Dançarina  · e8
4. Chiclete com Banana — Voa Voa  · e7
"""

BLOCK_ROWS = [
    ["Pedro Sampaio & MC Pedrinho — Dançarina", "yes", "yes", "yes", "yes"],  # only via the choreography
    ["Nobody — Song Z", "no", "no", "—", "no", "no SoundSwitch script found under this name"],
    ["Pedro Sampaio — Dançarina", "yes", "yes", "yes", "yes"],
    ["Chiclete com Banana — Voa Voa", "no", "no", "—", "no"],
]


def test_block_filter(room, idle, capsys):
    (room[1] / "blocks" / "alpha-status.md").write_text(STATUS_BLOCK, encoding="utf-8")
    _apply(capsys, room)
    code, out, err = _status(capsys, room, "--block", "alpha-status")
    assert code == 0, err
    lines = out.splitlines()
    assert lines[0] == "track" + " " * 36 + "choreography  applied  haze  compliant  note"
    assert [_cells(line) for line in lines[1:-1]] == BLOCK_ROWS
    assert lines[-1] == "2 of 4 tracks compliant"


def test_several_scripts_list_their_guid8s(room, trackmap_bytes, capsys):
    third = "00ee0000-0000-4000-8000-000000000003"
    (room[0] / "SoundSwitchTrackMap.bin").write_bytes(trackmap_bytes([
        (5, GUID0, "Dançarina", "Pedro Sampaio", r"C:\Music\a.mp3", 120, 16000),
        (5, GUID1, "Voa Voa", "Chiclete com Banana", r"C:\Music\b.mp3", 120, 16000),
        (5, third, "Voa Voa", "Chiclete com Banana", r"C:\Music\c.mp3", 120, 16000),
    ]))
    code, out, err = _status(capsys, room, "--block", "alpha-festa")
    assert code == 0, err
    assert _cells(out.splitlines()[2])[-1] == f"several scripts: {GUID1[:8]}, {third[:8]}"


def test_set_filter(room, capsys):
    (room[1] / "blocks" / "alpha-status.md").write_text(STATUS_BLOCK, encoding="utf-8")
    sets = room[1] / "sets"
    sets.mkdir()
    (sets / "night.md").write_text(
        "## Program\n1. [Status](../blocks/alpha-status.md) · 20m\n2. [Again](../blocks/alpha-status.md) · 20m\n",
        encoding="utf-8")
    code, out, err = _status(capsys, room, "--set", str(sets / "night.md"))
    assert code == 0, err
    lines = out.splitlines()
    assert lines.count("alpha-status") == 2
    first, second = (i for i, line in enumerate(lines) if line == "alpha-status")
    assert [_cells(line)[0] for line in lines[first + 2:first + 6]] == [r[0] for r in BLOCK_ROWS]
    assert lines[second + 2:second + 6] == lines[first + 2:first + 6]
    assert lines[-1] == "0 of 8 tracks compliant"


def _snapshot(root):
    return {p.relative_to(root).as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            if p.is_file() else None for p in sorted(root.rglob("*"))}


def test_status_writes_nothing(room, idle, capsys, monkeypatch, tmp_path):
    _apply(capsys, room)
    _edit_script(room, _edit_mover)
    (room[1] / "blocks" / "alpha-status.md").write_text(STATUS_BLOCK, encoding="utf-8")

    def never():
        raise AssertionError("status must not check whether SoundSwitch runs")

    monkeypatch.setattr(nl, "soundswitch_running", never)
    before = _snapshot(tmp_path)
    assert (room[0].parent / "nextrack-backups" / "state.json").relative_to(tmp_path).as_posix() in before
    for flags in ((), ("--block", "alpha-status")):
        code, _, err = _status(capsys, room, *flags)
        assert code == 0, err
    assert _snapshot(tmp_path) == before
