"""nextrack_map.py: analyze, cues and show, with a synthetic project, library, repo, separator
and rekordbox reader. No model, no real database, no real audio."""
import contextlib
import importlib.util
import struct
import uuid

import pytest
import soundfile as sf

import musical_map as mm
import nextrack_map as nm
import soundswitch_format as ssf
import synth
from conftest import PROJECT_GUIDS
from mapdata import good_map
from rekordbox_cues import RbTrack

SR = 22050
MAP_REL = "lightshows/maps/pedro-sampaio-mc-pedrinho-dancarina.yml"


def write_audio(path, freq=440.0, channels=2):
    x = synth.clicks_on_beats(120, 16000, sr=SR) + synth.tone(freq, 16000, SR, amp=0.1)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, x if channels == 1 else synth.pan(x), SR, format="FLAC")


def fake_separator(calls):
    def separate(x, sr):
        calls.append((x.shape, sr))
        n = len(x)
        ms = n * 1000 / sr
        stems = {"drums": synth.clicks_on_beats(120, ms, sr=sr)[:n],
                 "bass": synth.tone(60, ms, sr)[:n],
                 "vocals": synth.tone(440, ms, sr, amp=0.2)[:n],
                 "other": synth.tone(880, ms, sr, amp=0.1)[:n]}
        return stems, sr

    return separate


class FakeReader:
    def __init__(self, tracks):
        self.tracks = tracks

    def playlist(self, name):
        if name != "Warm":
            raise LookupError(f"no playlist matches {name!r}")
        return list(self.tracks)

    def track_for_file(self, file_name):
        return next((t for t in self.tracks if t.path.replace("\\", "/").split("/")[-1] == file_name), None)


def rb(path, cues=None, title="Dançarina"):
    return RbTrack(title=title, artist="Pedro Sampaio", path=path, bpm=120.0, key="8A",
                   cues=cues if cues is not None else {"A": 0, "B": 4000})


def trackmap(entries):
    def s(x):
        return struct.pack("<I", len(x) + 1) + (x + "\0").encode("utf-16le")

    out = bytearray(ssf.MAGIC + struct.pack("<5I", 3, 0, 0, 1, 1))
    for kind, guid, title, artist, path, bpm, ms in entries:
        out += struct.pack("<IB", kind, 1) + uuid.UUID(guid).bytes_le
        for t in (title, artist, path):
            out += struct.pack("<I", 1) + s(t)
        out += struct.pack("<II", bpm, ms)
        out += bytes.fromhex("01" "ffffffff" "00000000" "00" "01000000")
    return bytes(out)


class Env:
    pass


@pytest.fixture
def env(tmp_path, make_project, mini_repo, monkeypatch):
    e = Env()
    e.project, e.repo, e.calls = make_project(), mini_repo, []
    e.root = tmp_path / "lib"
    write_audio(e.root / "Music" / "a.mp3")
    write_audio(e.root / "Music" / "b.mp3", freq=330.0)
    monkeypatch.setattr(nm, "make_separator", lambda device: fake_separator(e.calls))
    e.reader = FakeReader([rb(r"C:\Music\a.mp3"), rb(r"C:\Music\zzz.mp3", title="Unknown")])
    monkeypatch.setattr(nm, "open_rekordbox", lambda folder: contextlib.nullcontext(e.reader))

    def run(*args, rekordbox=True):
        argv = [args[0], "--project", str(e.project), "--repo", str(mini_repo.root)]
        if args[0] == "analyze":
            argv += ["--root", str(e.root)]
        if rekordbox:
            argv += ["--rekordbox", str(tmp_path / "rb")]
        return nm.main(argv + list(args[1:]))

    e.run = run
    return e


def test_analyze_writes_a_valid_map(env, capsys):
    assert env.run("analyze", "Dançarina") == 0
    path = env.repo.path(MAP_REL)
    assert f"written {path}" in capsys.readouterr().out
    data = mm.load_map(path)
    assert mm.problems_map(data) == []
    assert data["track"] == "Pedro Sampaio & MC Pedrinho — Dançarina"
    assert data["soundswitch"] == PROJECT_GUIDS[0].upper()
    assert data["hot_cues"] == {"A": "1.1", "B": "3.1"}
    assert env.repo.findings("musical-map") == []
    assert env.calls[0][0][1] == 2


def test_analyze_keeps_an_up_to_date_map_and_redoes_a_stale_one(env, capsys):
    path = env.repo.path(MAP_REL)
    env.run("analyze", "Dançarina")
    capsys.readouterr()
    before = path.read_bytes()
    assert env.run("analyze", "Dançarina") == 0
    assert f"kept {path}" in capsys.readouterr().out
    assert len(env.calls) == 1
    write_audio(env.root / "Music" / "a.mp3", freq=523.0)
    assert env.run("analyze", "Dançarina") == 0
    assert f"redone (stale) {path}" in capsys.readouterr().out
    assert path.read_bytes() != before
    assert env.run("analyze", "Dançarina") == 0
    assert "kept" in capsys.readouterr().out
    assert env.run("analyze", "Dançarina", "--force") == 0
    assert f"written {path}" in capsys.readouterr().out
    assert len(env.calls) == 3


def test_analyze_refuses_a_track_not_in_a_pool(env, capsys):
    pool = env.repo.read("tracks/alpha.yml").replace('title: "Dançarina"', 'title: "Outra"')
    env.repo.write("tracks/alpha.yml", pool)
    assert env.run("analyze", "Dançarina") == 1
    out = capsys.readouterr().out
    assert "refused Pedro Sampaio — Dançarina" in out and "add it to its pool first" in out
    assert not env.repo.path("lightshows/maps").exists()


def test_analyze_picks_the_exact_version_among_two_pool_entries(env):
    entry = '''\
- title: "{}"
  artist: "Bakermat"
  genre: alpha
  bpm: null
  key: null
  energy: 7
  status: downloaded
'''
    env.repo.write("tracks/alpha.yml", entry.format("Baianá (Jack Back Club Mix)") + "\n"
                   + entry.format("Baianá (Pablo Fierro Edit)"))
    (env.project / "SoundSwitchTrackMap.bin").write_bytes(trackmap([
        (5, PROJECT_GUIDS[0], "Baianá (Pablo Fierro Edit)", "Bakermat", r"C:\Music\a.mp3", 120, 16000)]))
    assert env.run("analyze", "Pablo Fierro", rekordbox=False) == 0
    assert env.repo.path("lightshows/maps/bakermat-baiana-pablo-fierro-edit.yml").is_file()
    assert not env.repo.path("lightshows/maps/bakermat-baiana-jack-back-club-mix.yml").exists()


def test_analyze_refuses_when_several_pool_entries_match(env, capsys):
    entry = '''\
- title: "Dançarina"
  artist: "Pedro Sampaio"
  genre: alpha
  bpm: null
  key: null
  energy: 7
  status: downloaded
'''
    env.repo.write("tracks/alpha.yml", entry + "\n" + entry.replace('"Dançarina"', '"Dançarina (Remix)"'))
    (env.project / "SoundSwitchTrackMap.bin").write_bytes(trackmap([
        (5, PROJECT_GUIDS[0], "Dançarina (Extended)", "Pedro Sampaio", r"C:\Music\a.mp3", 120, 16000)]))
    assert env.run("analyze", "Dançarina", rekordbox=False) == 1
    out = capsys.readouterr().out
    assert "refused" in out and "Dançarina (Remix)" in out


def test_analyze_playlist_skips_a_track_soundswitch_does_not_know(env, capsys):
    assert env.run("analyze", "--playlist", "Warm") == 1
    out = capsys.readouterr().out
    assert f"written {env.repo.path(MAP_REL)}" in out
    assert "refused Pedro Sampaio — Unknown" in out and "not in the SoundSwitch project" in out
    assert env.repo.path(MAP_REL).is_file()


def test_analyze_without_rekordbox_writes_a_note(env):
    assert env.run("analyze", "Dançarina", rekordbox=False) == 0
    data = mm.load_map(env.repo.path(MAP_REL))
    assert data["hot_cues"] is None and data["hot_cues_note"] == "rekordbox not configured"
    assert mm.problems_map(data) == []


def test_analyze_notes_a_track_missing_from_the_collection(env):
    env.reader.tracks = []
    assert env.run("analyze", "Dançarina") == 0
    data = mm.load_map(env.repo.path(MAP_REL))
    assert data["hot_cues"] is None and data["hot_cues_note"] == "not in the rekordbox collection"


def test_analyze_mono_file(env):
    write_audio(env.root / "Music" / "a.mp3", channels=1)
    assert env.run("analyze", "Dançarina") == 0
    assert env.calls[0][0][1] == 2
    assert mm.problems_map(mm.load_map(env.repo.path(MAP_REL))) == []


def test_analyze_refuses_a_missing_audio_file(env, capsys):
    (env.root / "Music" / "a.mp3").unlink()
    assert env.run("analyze", "Dançarina") == 1
    assert "refused Pedro Sampaio — Dançarina: no audio file" in capsys.readouterr().out


def test_analyze_keeps_stems_when_asked(env, tmp_path):
    keep = tmp_path / "stems"
    assert env.run("analyze", "Dançarina", "--keep-stems", str(keep)) == 0
    assert sorted(p.name for p in keep.rglob("*.flac")) == ["bass.flac", "drums.flac", "other.flac", "vocals.flac"]


def test_cues_rewrites_only_hot_cues(env, capsys):
    env.run("analyze", "Dançarina", rekordbox=False)
    path = env.repo.path(MAP_REL)
    before = path.read_text(encoding="utf-8").splitlines()
    capsys.readouterr()
    assert env.run("cues", "Dançarina") == 0
    assert f"cues {path}" in capsys.readouterr().out
    after = path.read_text(encoding="utf-8").splitlines()
    changed = [x for x in before if x not in after] + [x for x in after if x not in before]
    assert changed and all(x.startswith(("hot_cues", "hot_cues_note")) for x in changed)
    assert len(before) == len(after) + 1  # the note line is gone
    assert len(env.calls) == 1
    assert mm.load_map(path)["hot_cues"] == {"A": "1.1", "B": "3.1"}
    assert mm.problems_map(mm.load_map(path)) == []
    env.reader.tracks[0].cues = {"G": 8000}
    assert env.run("cues", "--playlist", "Warm") == 1  # the Unknown track is not in the project
    assert mm.load_map(path)["hot_cues"] == {"G": "5.1"}


def test_cues_without_a_map_is_refused(env, capsys):
    assert env.run("cues", "Dançarina") == 1
    assert "no map" in capsys.readouterr().out


def test_show_prints_the_map(tmp_path, capsys):
    path = tmp_path / "m.yml"
    path.write_text(mm.dump_map(good_map(4)), encoding="utf-8")
    assert nm.main(["show", str(path)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Pedro Sampaio — Dançarina  ·  120.0 BPM  ·  4 bars  ·  htdemucs",
        "bars 1-4",
        "         1",
        "cues     A..B",
        "vocals   5555",
        "kick     5555",
        "perc     5555",
        "bass     5555",
        "other    5555",
        "sections ggdd",
        "",
        "drops",
        "  bar 4  12.5 dB",
        "phrases",
        "  1.1 - 4.4  mid  level 8",
    ]


def test_show_finds_a_map_by_the_track_words(env, capsys):
    env.run("analyze", "Dançarina", rekordbox=False)
    capsys.readouterr()
    assert nm.main(["show", "sampaio", "--repo", str(env.repo.root)]) == 0
    assert "Pedro Sampaio" in capsys.readouterr().out
    assert nm.main(["show", "nobody", "--repo", str(env.repo.root)]) == 1


def test_demucs_needs_the_analysis_group(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda *a, **k: None)
    with pytest.raises(SystemExit) as e:
        nm.demucs_separator(None)
    assert "uv sync --group analysis" in str(e.value)


def test_a_missing_project_is_reported(capsys):
    assert nm.main(["analyze", "x"]) == 2
