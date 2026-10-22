import pytest

from nextrack_tags import (
    _desired_tags,
    clean_stem,
    is_junk_artist,
    is_junk_title,
    normalize,
    parse_artist_title,
    parse_pool,
    strip_sitejunk,
    to_bpm,
    to_camelot,
)

ROOTS = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

POOL_TEXT = """\
# header comment
- title: "Sóng A"
  artist: 'Artist One'
  bpm: null
  key: 8A

- title: Plain Title
  artist: Artist Two
  bpm: 120
  key: null
"""

JUNK_EMB = {"title": "Next Song", "artist": "Mix Tutorial"}


@pytest.mark.parametrize(
    "stem, expected",
    [
        ("Artist - Title [NotSlider.nl]", "Artist - Title"),
        ("Artist - Title [vk.com Music]", "Artist - Title"),
        ("Artist - Title - Tech House", "Artist - Title"),
        ("Artist - Title - Slap House", "Artist - Title"),
        ("Artist - Title - Música 2", "Artist - Title"),
        ("Artist - Title (infantil)", "Artist - Title"),
        ("Artist - Title [slider.kz] - Tech House", "Artist - Title"),
        ("Artist - Title [www.site.ru] Deep House", "Artist - Title"),
        ("Artist - Title (Extended Mix)", "Artist - Title (Extended Mix)"),
        ("Artist - Title [Salsa Version]", "Artist - Title [Salsa Version]"),
    ],
)
def test_clean_stem(stem, expected):
    assert clean_stem(stem) == expected


def test_parse_artist_title():
    assert parse_artist_title("A - B - C") == ("A", "B - C")
    assert parse_artist_title("Solo") == (None, "Solo")


def test_normalize():
    assert normalize("Dançarina!  (Remix)") == "dancarina remix"
    assert normalize(None) == ""


def test_to_camelot_covers_the_wheel():
    assert {to_camelot(r) for r in ROOTS} == {f"{n}B" for n in range(1, 13)}
    assert {to_camelot(r + "m") for r in ROOTS} == {f"{n}A" for n in range(1, 13)}


@pytest.mark.parametrize(
    "key, expected",
    [
        ("C", "8B"),
        ("Am", "8A"),
        ("Fm", "4A"),
        ("Ebm", "2A"),
        ("F#m", "11A"),
        ("Gbm", "11A"),
        ("A#", "6B"),
        ("F♯m", "11A"),
        ("B♭", "6B"),
        ("8a", "8A"),
        ("12B", "12B"),
        ("c", "8B"),
        ("cm", "5A"),
        ("H", None),
        ("", None),
        (None, None),
        ("Cmaj", None),
    ],
)
def test_to_camelot_examples(key, expected):
    assert to_camelot(key) == expected


def test_to_bpm():
    assert to_bpm("123.9") == 124
    assert to_bpm("124.6") == 125
    assert to_bpm(128) == 128
    assert to_bpm("abc") is None
    assert to_bpm(None) is None


@pytest.mark.parametrize(
    "value, expected",
    [
        ("", True),
        ("  ", True),
        ("ab", True),
        ("Next Song", True),
        ("current song", True),
        ("abc", False),
    ],
)
def test_is_junk_title(value, expected):
    assert is_junk_title(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("", True),
        ("Mix Tutorial", True),
        ("next song", True),
        ("Ivete", False),
    ],
)
def test_is_junk_artist(value, expected):
    assert is_junk_artist(value) is expected


def test_strip_sitejunk():
    assert strip_sitejunk("Title [slider.kz]") == "Title"
    assert strip_sitejunk(None) == ""


@pytest.mark.parametrize(
    "emb, f_artist, f_title, yaml_hit, overwrite, expected",
    [
        (
            {"title": "Real", "artist": "A; B"},
            "A", "File Title", None, False,
            ("Real", "A; B"),
        ),
        (
            JUNK_EMB,
            "FA", "FT", {"title": "Y T", "artist": "Y A"}, False,
            ("Y T", "Y A"),
        ),
        (
            JUNK_EMB,
            "FA", "FT", None, False,
            ("FT", "FA"),
        ),
        (
            {"title": "Real", "artist": "A; B"},
            "FA", "FT", None, True,
            ("FT", "FA"),
        ),
        (
            {"title": "Real [NotSlider.nl]", "artist": "A"},
            "FA", "FT", None, False,
            ("Real", "A"),
        ),
    ],
)
def test_desired_tags(emb, f_artist, f_title, yaml_hit, overwrite, expected):
    assert _desired_tags(emb, f_artist, f_title, yaml_hit, overwrite) == expected


def test_parse_pool(tmp_path):
    pool = tmp_path / "pool.yml"
    pool.write_text(POOL_TEXT, encoding="utf-8")
    assert parse_pool(pool) == [
        {"title": "Sóng A", "artist": "Artist One", "bpm_line": 3, "bpm_val": "null", "key_line": 4, "key_val": "8A"},
        {"title": "Plain Title", "artist": "Artist Two", "bpm_line": 8, "bpm_val": "120", "key_line": 9, "key_val": "null"},
    ]
