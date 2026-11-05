import importlib.util

import pytest

import rekordbox_cues as rc


def test_cues_from_rows():
    rows = [(0, 100), (1, 61), (2, 112000), (8, 272000), (4, 5)]
    assert rc.cues_from_rows(rows) == {"A": 61, "B": 112000, "G": 272000}


def test_cues_from_rows_keeps_the_first_of_a_letter():
    assert rc.cues_from_rows([(1, 5), (1, 9)]) == {"A": 5}


NAMES = ["Warm up", "Sunset set", "Sunset b2b"]


def test_pick_playlist_exact():
    assert rc.pick_playlist(NAMES, "Warm up") == "Warm up"


def test_pick_playlist_unique_substring():
    assert rc.pick_playlist(NAMES, "WARM") == "Warm up"


def test_pick_playlist_none():
    with pytest.raises(LookupError):
        rc.pick_playlist(NAMES, "zzz")


def test_pick_playlist_two_substrings_names_both():
    with pytest.raises(LookupError) as e:
        rc.pick_playlist(NAMES, "sunset")
    assert "Sunset set" in str(e.value) and "Sunset b2b" in str(e.value)


def test_open_rekordbox_without_the_analysis_group(monkeypatch, tmp_path):
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda n, *a: None if n == "pyrekordbox" else real(n, *a))
    with pytest.raises(SystemExit) as e:
        with rc.open_rekordbox(tmp_path):
            pass
    assert str(e.value) == "the analysis tools are not installed: run uv sync --group analysis"


class Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_pick_playlist_row_skips_a_folder_with_the_same_name():
    folder = Row(Name="Set", Attribute=1, Songs=[])
    playlist = Row(Name="Set", Attribute=0, Songs=[object()])
    assert rc.pick_playlist_row([folder, playlist], "Set") is playlist
    assert rc.pick_playlist_row([playlist, folder], "Set") is playlist


def test_pick_playlist_row_refuses_two_playlists_with_one_name():
    rows = [Row(Name="Set", Attribute=0, Songs=[1]), Row(Name="Set", Attribute=0, Songs=[2])]
    with pytest.raises(LookupError) as e:
        rc.pick_playlist_row(rows, "Set")
    assert str(e.value).count("Set") >= 3


def test_pick_content_row():
    a = Row(FolderPath="C:/M/g/A.flac")
    b = Row(FolderPath="C:\\M\\g\\B.flac")
    assert rc.pick_content_row([a, b], "b.FLAC") is b
    assert rc.pick_content_row([a, b], "z.flac") is None


def test_pick_content_row_refuses_duplicates():
    rows = [Row(FolderPath="C:/M/one/A.flac"), Row(FolderPath="C:/M/two/A.flac")]
    with pytest.raises(LookupError) as e:
        rc.pick_content_row(rows, "A.flac")
    assert "one" in str(e.value) and "two" in str(e.value)


def test_open_rekordbox_needs_a_master_db(monkeypatch, tmp_path):
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda n, *a: object() if n == "pyrekordbox" else real(n, *a))
    with pytest.raises(LookupError, match="no master.db"):
        with rc.open_rekordbox(tmp_path):
            pass
