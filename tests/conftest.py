"""Shared fixtures. Audio is always synthetic and lives under tmp_path only."""
import struct
from pathlib import Path

import pytest
from mutagen.flac import FLAC
from mutagen.id3 import GEOB, ID3, TBPM, TIT2, TKEY, TPE1

# -------------------------------------------------------------- environment ----


@pytest.fixture(autouse=True)
def no_owner_library(monkeypatch):
    """Hide the owner's NEXTRACK_AUDIO_ROOT (exported in ~/.bashrc) from every test, so
    that a test that forgets `--root` fails instead of touching the real library."""
    monkeypatch.delenv("NEXTRACK_AUDIO_ROOT", raising=False)


@pytest.fixture(autouse=True)
def no_owner_soundswitch(monkeypatch):
    """Likewise hide the owner's SoundSwitch project folder from every test."""
    monkeypatch.delenv("NEXTRACK_SOUNDSWITCH_PROJECT", raising=False)


# ------------------------------------------------------ SoundSwitch scripts ----


@pytest.fixture
def make_script():
    """Factory: a small valid TrackScript; `overrides` replace TrackScript fields."""
    import soundswitch_format as ssf

    def _make(**overrides):
        def empty_track(node, link=1):
            return ssf.Track(node=node, lanes=[ssf.Lane(4, 1, None, [])], blocks=None,
                             link=link, colours=None, positions=None, strobes=None,
                             position_blocks=None, shapes=None)

        mover = empty_track(1167)
        mover.lanes[0].keys = [ssf.Key(1000, 0), ssf.Key(1001, ssf.FULL), ssf.Key(1300, 0)]
        mover.blocks = ssf.Section(1, [ssf.Span(1000, 2000)])
        mover.colours = ssf.Section(1, [ssf.ColourBlock(1000, 2000, 0xFF00FF37, 0, 0xFF3700FF, 0)])
        mover.shapes = ssf.Shapes(1, 1, [ssf.ShapeBlock(
            1000, 2000, 0, 2, (0.5, 0.5, 0.5, 0.5), 0, 1, 2, 1)])

        main = ssf.Track(
            node=2,
            lanes=[ssf.Lane(4, 1, 0, [ssf.Key(0, 0x7FFFFFFF), ssf.Key(10000, 0x7FFFFFFF)])]
                  + [ssf.Lane(a, 1, None, []) for a in (2, 3, 5, 6, 7)],
            blocks=None, link=0, colours=None,
            positions=ssf.Positions(
                2, 1,
                [("11111111-2222-3333-4444-555555555555", 0),
                 ("66666666-7777-8888-9999-aaaaaaaaaaaa", 1)],
                [ssf.PositionFlag(1500, 1)]),
            strobes=None, position_blocks=ssf.Section(1, [ssf.Span(1000, 2000)]), shapes=None)

        fields = dict(
            container_ver=3, fmt=13,
            venues=[
                ssf.Venue(4, "0122adb8-e4b9-46c9-96c8-98a7e8f6a5a9", 3,
                          [mover, empty_track(1820)], (1, 0)),
                ssf.Venue(4, "d34c412f-48c1-4f75-9399-b35c069c8fdb", 3, [], (1, 0)),
            ],
            global_ver=1, tempo=[(158, 100.0)],
            post_tempo=bytes.fromhex("01" "01000000" "01000000" "00000000" "0000"),
            main=main, pre_cue=[1, 0, 0, 1, 1, 0, 1, 1],
            cue_palette=[("aaaaaaaa-0000-0000-0000-000000000001", 0)],
            cue_flags=[(2500, 0)], post_cue=bytes(10),
            node_lists_ver=1, node_lists=[1, 1],
            tail_pre=bytes.fromhex(ssf.DEFAULT_TAIL_PRE),
            tail_post=bytes.fromhex(ssf.DEFAULT_TAIL_POST),
        )
        fields.update(overrides)
        return ssf.TrackScript(**fields)

    return _make


# --------------------------------------- SoundSwitch TrackMap and Venues ----


def _ss_str(s):
    return struct.pack("<I", len(s) + 1) + (s + "\0").encode("utf-16le")


@pytest.fixture
def trackmap_bytes():
    """Factory: a SoundSwitchTrackMap.bin from `(kind, guid, title, artist, path, bpm, ms)`."""
    import uuid

    import soundswitch_format as ssf

    def _build(entries):
        out = bytearray(ssf.MAGIC + struct.pack("<5I", 3, 0, 0, 1, 1))
        for kind, guid, title, artist, path, bpm, ms in entries:
            out += struct.pack("<IB", kind, 1) + uuid.UUID(guid).bytes_le
            for s in (title, artist, path):
                out += struct.pack("<I", 1) + _ss_str(s)
            out += struct.pack("<II", bpm, ms)
            out += bytes.fromhex("01" "ffffffff" "00000000" "00" "01000000")
            if kind == 4:  # SoundSwitch's demo track carries extra bytes after the trailer
                out += bytes.fromhex("0400000000010000000100000000")
        return bytes(out)

    return _build


@pytest.fixture
def venues_bytes():
    """Factory: a SoundSwitchVenues.bin with venue "DJ Renan" (device `tree`), an empty
    venue "Casa" and position `presets` (names). A node is `{"id", "name", "look", "colour"}`
    (leaf) or `{"id", "name", "model", "colour", "children": [...]}` (group)."""
    import uuid

    import soundswitch_format as ssf

    def node(n, kind):
        out = struct.pack("<IIIII", kind, 3, 2, n["id"], 1) + _ss_str(n["name"])
        if "children" in n:
            out += struct.pack("<I", 1) + _ss_str(n["model"]) + struct.pack("<I", len(n["children"]))
            for c in n["children"]:
                out += node(c, 1 if "children" not in c else 0)
            return out + struct.pack("<I", n["colour"])
        return out + struct.pack("<II", n["look"], n["colour"])

    def venue(name, guid, body):
        return (struct.pack("<I", 4) + uuid.UUID(guid).bytes_le + struct.pack("<I", 1)
                + _ss_str(name) + struct.pack("<I", 15) + body)

    def _build(tree, presets):
        tree_body = struct.pack("<2I", 1937, len(tree)) + b"".join(
            node(n, 0 if "children" in n else 1) for n in tree)
        out = bytearray(ssf.MAGIC + struct.pack("<5I", 3, 0, 0, 11, 2))
        out += venue("DJ Renan", "0122adb8-e4b9-46c9-96c8-98a7e8f6a5a9",
                     struct.pack("<3I", 2, 1, 0) + tree_body)
        # An empty venue's body can hold the positions anchor itself; readers must not trust it.
        out += venue("Casa", "d34c412f-48c1-4f75-9399-b35c069c8fdb",
                     struct.pack("<3I", 2, 1, 0) + bytes.fromhex("02000000" "00000000" "02000000"))
        out += b"\x02\x00\x00\x00\x00\x00\x00\x00"
        for i, p in enumerate(presets):
            out += struct.pack("<II", 2, 1) + uuid.UUID("0122adb8-e4b9-46c9-96c8-98a7e8f6a5a9").bytes_le
            out += struct.pack("<II", 2, 1) + struct.pack("<4I", 1167, 1, 100, 200)
            out += struct.pack("<I", 1) + _ss_str(p) + struct.pack("<I", 0xFF112233)
            out += uuid.UUID(int=i + 1).bytes_le + struct.pack("<i", i + 1 if i + 1 < len(presets) else -1)
        out += struct.pack("<I", len(presets)) + b"".join(struct.pack("<I", i) for i in range(len(presets)))
        return bytes(out)

    return _build


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
