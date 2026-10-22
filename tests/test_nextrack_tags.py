import pytest
import yaml
from mutagen.flac import FLAC
from mutagen.id3 import ID3

from nextrack_tags import (
    _desired_tags,
    clean_stem,
    is_junk_artist,
    is_junk_title,
    main,
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
    # bpm_line / key_line are 0-based line indices (parse_pool uses enumerate).
    assert parse_pool(pool) == [
        {"title": "Sóng A", "artist": "Artist One", "bpm_line": 3, "bpm_val": "null", "key_line": 4, "key_val": "8A"},
        {"title": "Plain Title", "artist": "Artist Two", "bpm_line": 8, "bpm_val": "120", "key_line": 9, "key_val": "null"},
    ]


# ----------------------------------------------------- commands (synthetic) ----

SONG_A_JUNK = "Artist One - Song A [NotSlider.nl].mp3"
SONG_B_JUNK = "Artist Two - Song B - Tech House.mp3"
SERATO_CUE = b"\x01\x01cue"


def run(capsys, *argv):
    """Run nextrack_tags.main(argv) and return what it printed."""
    main(list(argv))
    return capsys.readouterr().out


def snapshot(base):
    """{path: (bytes, mtime_ns)} for every file under base."""
    return {
        p: (p.read_bytes(), p.stat().st_mtime_ns)
        for p in sorted(base.rglob("*"))
        if p.is_file()
    }


def test_dry_runs_change_nothing(tmp_path, library, capsys):
    root, tracks = library
    before = snapshot(tmp_path)
    assert before  # the library was actually built

    run(capsys, "audit", "--root", str(root))
    run(capsys, "clean-names", "--root", str(root))
    run(capsys, "fix-tags", "--root", str(root), "--tracks-dir", str(tracks))
    run(capsys, "pull-bpm", "--root", str(root), "--tracks-dir", str(tracks))

    assert snapshot(tmp_path) == before


def test_clean_names_apply_renames_and_logs(library, capsys):
    root, _ = library
    alpha = root / "alpha"

    run(capsys, "clean-names", "--root", str(root), "--apply")

    assert (alpha / "Artist One - Song A.mp3").is_file()
    assert (alpha / "Artist Two - Song B.mp3").is_file()
    assert not (alpha / SONG_A_JUNK).exists()
    assert not (alpha / SONG_B_JUNK).exists()

    log = (root / "_nextrack_rename_log.tsv").read_text(encoding="utf-8")
    lines = log.splitlines()
    assert len(lines) == 2
    assert [line.split("\t") for line in lines] == [
        [str(alpha / SONG_A_JUNK), str(alpha / "Artist One - Song A.mp3")],
        [str(alpha / SONG_B_JUNK), str(alpha / "Artist Two - Song B.mp3")],
    ]


def test_clean_names_skips_existing_target(library, capsys):
    root, _ = library
    alpha = root / "alpha"
    (alpha / "Artist One - Song A.mp3").write_bytes(b"")

    out = run(capsys, "clean-names", "--root", str(root), "--apply")

    assert (alpha / SONG_A_JUNK).exists()
    assert "SKIP (target exists)" in out


def test_fix_tags_apply(library, capsys):
    root, tracks = library
    alpha = root / "alpha"

    out = run(capsys, "fix-tags", "--root", str(root), "--tracks-dir", str(tracks), "--apply")

    song_a = ID3(alpha / SONG_A_JUNK)
    assert song_a["TIT2"].text == ["Sóng A"]  # curated YAML wins over the filename
    assert song_a["TPE1"].text == ["Artist One"]
    song_b = ID3(alpha / SONG_B_JUNK)
    assert song_b["TIT2"].text == ["Song B"]
    assert song_b["TPE1"].text == ["Artist Two"]
    assert FLAC(alpha / "Artist Three - Song C.flac")["title"] == ["Good Title"]
    # mutagen rewrote only the tag block: Serato's GEOB frame survives, still v2.4
    assert song_a["GEOB:Serato Markers2"].data == SERATO_CUE
    assert song_a.version == (2, 4, 0)
    assert "SKIP wav" in out


def test_fix_tags_overwrite_lets_curated_value_win(library, capsys):
    root, tracks = library
    alpha = root / "alpha"

    run(capsys, "fix-tags", "--root", str(root), "--tracks-dir", str(tracks),
        "--apply", "--overwrite")

    assert FLAC(alpha / "Artist Three - Song C.flac")["title"] == ["Song C"]


def test_pull_bpm_apply(library, capsys):
    root, tracks = library
    pool = tracks / "alpha.yml"
    titles_before = [e["title"] for e in yaml.safe_load(pool.read_text(encoding="utf-8"))]

    out = run(capsys, "pull-bpm", "--root", str(root), "--tracks-dir", str(tracks),
              "--apply", "-v")

    text = pool.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "# tracks/alpha.yml — pool (unordered)."
    entries = {e["title"]: e for e in yaml.safe_load(text)}
    assert list(entries) == titles_before
    assert (entries["Sóng A"]["bpm"], entries["Sóng A"]["key"]) == (125, "8A")
    assert (entries["Song C"]["bpm"], entries["Song C"]["key"]) == (128, "5A")  # key kept
    assert (entries["Algo Parecido (Remix)"]["bpm"], entries["Algo Parecido (Remix)"]["key"]) == (122, "4A")
    assert (entries["Tune"]["bpm"], entries["Tune"]["key"]) == (None, None)  # two versions: ambiguous
    assert (entries["Song Z"]["bpm"], entries["Song Z"]["key"]) == (None, None)
    assert "2 null entries unmatched" in out


def test_missing_root_exits_with_hint(monkeypatch):
    monkeypatch.delenv("NEXTRACK_AUDIO_ROOT", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        main(["audit"])
    assert "NEXTRACK_AUDIO_ROOT" in str(exc_info.value.code)
