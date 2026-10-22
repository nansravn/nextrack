"""Shared fixtures. Audio is always synthetic and lives under tmp_path only."""
import struct
from pathlib import Path

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


# ------------------------------------------------------------- mini repo ----
# The smallest valid NEXTRACK repo, rebuilt under tmp_path for every test. The
# validator tests change one file and assert on the findings.

REPO_ROOT = Path(__file__).resolve().parent.parent

MINI_REPO_FILES = {
    "genres/graph.yml": """\
nodes:
  - id: alpha
    name: Alpha
    family: brazilian
    bpm: [100, 120]
    energy: [4, 8]
    feel: [warm]
    subgenres: [alpha-sub]
    neighbors:
      - {to: beta,  strength: strong, via: "blend on the break"}
      - {to: gamma, strength: weak,   via: "long echo out"}
  - id: beta
    name: Beta
    family: global
    bpm: [118, 126]
    energy: [5, 9]
    neighbors:
      - {to: alpha, strength: strong, via: "drop back to the groove"}
      - {to: gamma, strength: medium, via: "lift the tempo"}
  - id: gamma
    name: Gamma
    family: global
    bpm: [124, 130]
    energy: [6, 9]
    neighbors:
      - {to: beta,  strength: medium, via: "ease down"}
""",
    "docs/taxonomy.md": """\
# Taxonomy

### `alpha` — Alpha
A warm test genre.

### `beta`
A driving test genre.

### `gamma`
A peak test genre.
""",
    "docs/genre-graph.md": """\
# Genre graph

See the [taxonomy](taxonomy.md).

```mermaid
graph LR
  A["alpha"]
  B["beta"]
  G["gamma"]
  A --- B
  B -.-> G
```
""",
    "tracks/alpha.yml": """\
# tracks/alpha.yml — pool for `alpha` (unordered).

- title: "Dançarina"
  artist: "Pedro Sampaio & MC Pedrinho"
  genre: alpha
  bpm: 135
  key: 8A
  energy: 8
  status: downloaded
  tags: [funk, singalong]

- title: "Voa Voa (Ao Vivo)"
  artist: "Chiclete com Banana"
  genre: alpha
  bpm: null
  key: null
  energy: 7
  status: to-download
  notes: "opens the block"
""",
    "blocks/alpha-festa.md": """\
---
name: Alpha Festa
function: peak
style: open-format
duration: 30m
genres: [alpha]
bpm: [100, 135]
energy: [7, 8]
key_journey: TBD
lightshow: null
---

## Feel
Bloco de teste.

## Bridge in
← `beta`: hard cut no refrão.

## Tracklist (primary)
1. Pedro Sampaio — Dançarina        · e8  abre
2. Chiclete com Banana — Voa Voa    · e7

## Bridge out
- → `beta`: echo out.
- Ver `alpha-festa.md` (não é um node).
""",
    "README.md": """\
# Mini repo

Read the [genre graph](docs/genre-graph.md).
""",
}


class MiniRepo:
    """A repo on disk plus helpers to edit it and read the validator's findings."""

    def __init__(self, root):
        self.root = root

    def path(self, rel):
        return self.root / rel

    def read(self, rel):
        return self.path(rel).read_text(encoding="utf-8")

    def write(self, rel, text):
        path = self.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def edit(self, rel, old, new):
        """Replace `old` with `new` in a file; `old` must occur exactly once."""
        text = self.read(rel)
        assert text.count(old) == 1, f"{old!r} occurs {text.count(old)}x in {rel}"
        self.write(rel, text.replace(old, new))

    def line_of(self, rel, text):
        """The 1-based line where `text` occurs; it must occur exactly once."""
        content = self.read(rel)
        assert content.count(text) == 1, f"{text!r} occurs {content.count(text)}x in {rel}"
        return content[: content.index(text)].count("\n") + 1

    def findings(self, rule=None):
        """`(path, line, rule)` for every finding, or only those of one rule."""
        from check_repo import check  # deferred: tests/ must collect without it

        return [
            (f.path, f.line, f.rule)
            for f in check(self.root)
            if rule is None or f.rule == rule
        ]


def build_mini_repo(root):
    """Write MINI_REPO_FILES under `root` and return a MiniRepo for it."""
    repo = MiniRepo(root)
    for rel, text in MINI_REPO_FILES.items():
        repo.write(rel, text)
    return repo


@pytest.fixture
def mini_repo(tmp_path):
    return build_mini_repo(tmp_path / "repo")


@pytest.fixture
def mini_repo_at():
    """The builder itself, for tests that need the repo somewhere specific."""
    return build_mini_repo
