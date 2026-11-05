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
