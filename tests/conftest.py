"""Shared fixtures. Audio is always synthetic and lives under tmp_path only."""
import struct

import pytest
from mutagen.flac import FLAC
from mutagen.id3 import GEOB, ID3, TBPM, TIT2, TKEY, TPE1

# --------------------------------------------------------- synthetic audio ----


@pytest.fixture
def make_mp3():
    """Factory: an empty file plus an ID3v2.4 tag with a Serato GEOB frame."""

    def _make(path, *, title=None, artist=None, bpm=None, key=None):
        path.write_bytes(b"")
        tags = ID3()
        if title is not None:
            tags.add(TIT2(encoding=3, text=[title]))
        if artist is not None:
            tags.add(TPE1(encoding=3, text=[artist]))
        if bpm is not None:
            tags.add(TBPM(encoding=3, text=[str(bpm)]))
        if key is not None:
            tags.add(TKEY(encoding=3, text=[key]))
        tags.add(
            GEOB(
                encoding=0,
                mime="application/octet-stream",
                filename="",
                desc="Serato Markers2",
                data=b"\x01\x01cue",
            )
        )
        tags.save(path, v2_version=4)
        return path

    return _make


@pytest.fixture
def make_flac():
    """Factory: a minimal FLAC (STREAMINFO only) with the given Vorbis tags."""

    def _make(path, **tags):
        si = struct.pack(">HH", 4096, 4096) + b"\x00" * 6
        si += ((44100 << 44) | (1 << 41) | (15 << 36)).to_bytes(8, "big") + b"\x00" * 16
        path.write_bytes(b"fLaC" + bytes([0x80, 0, 0, 34]) + si)
        flac = FLAC(path)
        for name, value in tags.items():
            flac[name] = [value]
        flac.save()
        return path

    return _make


# ------------------------------------------------------- library + pool ------

POOL_ENTRIES = [
    # (title, artist, key, energy, status)
    ("Sóng A", "Artist One", "null", 6, "downloaded"),
    ("Song C", "Artist Three", "5A", 7, "downloaded"),
    ("Algo Parecido (Remix)", "Skank", "null", 7, "downloaded"),
    ("Tune", "Artist X", "null", 5, "downloaded"),
    ("Song Z", "Nobody", "null", 5, "to-download"),
]


@pytest.fixture
def library(tmp_path, make_mp3, make_flac):
    """Build a synthetic library and pool; return (audio_root, tracks_dir)."""
    audio_root = tmp_path / "library"
    alpha = audio_root / "alpha"
    alpha.mkdir(parents=True)

    make_mp3(alpha / "Artist One - Song A [NotSlider.nl].mp3",
             artist="Artist One", bpm="124.6", key="Am")
    make_mp3(alpha / "Artist Two - Song B - Tech House.mp3",
             title="Next Song", artist="Mix Tutorial")
    make_flac(alpha / "Artist Three - Song C.flac",
              title="Good Title", artist="Artist Three", bpm="128", initialkey="8A")
    (alpha / "Artist Four - Song D.wav").write_bytes(b"")
    make_mp3(alpha / "Skank, Dubdogz, Bruno Be - Algo Parecido (Extended).mp3",
             bpm="122", key="Fm")
    make_mp3(alpha / "Artist X, B - Tune (Remix).mp3", bpm="120")
    make_mp3(alpha / "Artist X, C - Tune (Edit).mp3", bpm="121")

    tracks_dir = tmp_path / "tracks"
    tracks_dir.mkdir()
    blocks = [
        f'- title: "{title}"\n'
        f'  artist: "{artist}"\n'
        "  genre: alpha\n"
        "  bpm: null\n"
        f"  key: {key}\n"
        f"  energy: {energy}\n"
        f"  status: {status}\n"
        for title, artist, key, energy, status in POOL_ENTRIES
    ]
    header = "# tracks/alpha.yml — pool (unordered).\n\n"
    (tracks_dir / "alpha.yml").write_text(header + "\n".join(blocks), encoding="utf-8")

    return audio_root, tracks_dir
