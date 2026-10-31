import os
import struct
import uuid
from pathlib import Path

import pytest

from soundswitch_format import (
    MAGIC, Project, read_trackmap, read_trackmap_with_warnings, read_venues, read_venues_with_warnings,
)

REAL = os.environ.get("NEXTRACK_SOUNDSWITCH_REAL")

G1 = "0026489d-4cb2-42ca-b2d9-9746823aaf0a"
G2 = "00dfbf8c-c5c0-46fd-8e18-3d44a648ff7a"
G3 = "1b5f4c0f-0b59-4715-becc-9c498727c9dd"
ENTRIES = [
    (5, G1, "Dançarina", "Pedro Sampaio", r"C:\Music\a.mp3", 126, 152000),
    (5, G2, "Voa Voa", "Chiclete com Banana", r"C:\Music\b.mp3", 100, 200500),
    (4, G3, "SoundSwitch 2.0 In-App Demo", "inMusic NZ Ltd", r"C:\Temp\demo.mp4", 0, 0),
]


# ------------------------------------------------------------------ TrackMap ----


def test_trackmap_reads_both_entry_kinds(trackmap_bytes):
    refs = read_trackmap(trackmap_bytes(ENTRIES))
    assert [r.guid for r in refs] == [G1, G2, G3]
    assert refs[0].title == "Dançarina" and refs[0].artist == "Pedro Sampaio"
    assert refs[0].path == r"C:\Music\a.mp3"
    assert (refs[0].bpm, refs[0].duration_ms) == (126, 152000)
    assert refs[2].title == "SoundSwitch 2.0 In-App Demo"
    assert (refs[2].bpm, refs[2].duration_ms) == (None, None)


def test_trackmap_clean_file_has_no_warnings(trackmap_bytes):
    assert read_trackmap_with_warnings(trackmap_bytes(ENTRIES))[1] == []


def test_trackmap_ignores_the_id_list_after_the_last_entry(trackmap_bytes):
    tail = bytes.fromhex("01000000" "0a000000") + "177891759\0".encode("utf-16le") + bytes(8)
    refs, warnings = read_trackmap_with_warnings(trackmap_bytes(ENTRIES[:2]) + tail)
    assert [r.guid for r in refs] == [G1, G2] and warnings == []


def test_trackmap_skips_a_corrupted_entry_with_a_warning(trackmap_bytes):
    good = trackmap_bytes(ENTRIES[:2])
    head = len(trackmap_bytes([]))
    data = bytearray(good)
    data[head + 4] = 7          # the entry's `u8 1` marker
    refs, warnings = read_trackmap_with_warnings(bytes(data))
    assert [r.guid for r in refs] == [G2]
    assert len(warnings) == 1 and f"{head:#x}" in warnings[0]


def test_trackmap_rejects_a_wrong_header():
    with pytest.raises(ValueError):
        read_trackmap(b"nope" + bytes(20))


def test_trackmap_header_is_magic_and_ints(trackmap_bytes):
    assert trackmap_bytes([]).startswith(MAGIC)
    assert read_trackmap(trackmap_bytes([])) == []


# -------------------------------------------------------------------- Venues ----


def _tree():
    rgb = {"id": 1820, "name": "RGB 01 - VORLANE VL-1000 RGBW v2", "look": 1725, "colour": 0xFF38BAC7}
    return [
        {"id": 1167, "name": "Mover 1", "look": 1087, "colour": 0xFFFFE100},
        {"id": 1818, "name": "VORLANE VL-1000 RGBW v2", "model": "VORLANE VL-1000 RGBW v2",
         "colour": 0xFF38BAC7, "children": [rgb]},
    ]


def test_venues_nodes_and_presets(venues_bytes):
    venues, presets = read_venues(venues_bytes(_tree(), ["Stage Left", "Cake"]))
    assert [v.name for v in venues] == ["DJ Renan", "Casa"]
    assert venues[0].guid == "0122adb8-e4b9-46c9-96c8-98a7e8f6a5a9"
    nodes = {n.id: n for n in venues[0].nodes}
    assert [n.id for n in venues[0].nodes] == [1167, 1818, 1820]
    assert nodes[1167].name == "Mover 1" and nodes[1167].parent is None
    assert (nodes[1167].look, nodes[1167].colour) == (1087, 0xFFFFE100)
    assert nodes[1818].look is None and nodes[1818].parent is None
    assert nodes[1820].name == "RGB 01 - VORLANE VL-1000 RGBW v2"
    assert nodes[1820].parent == 1818 and nodes[1820].look == 1725
    assert venues[1].nodes == []
    assert [p.name for p in presets] == ["Stage Left", "Cake"]
    assert presets[0].guid == str(uuid.UUID(int=1))


def test_venues_clean_file_has_no_warnings(venues_bytes):
    # the empty "Casa" venue (and its decoy anchor) must not warn
    assert read_venues_with_warnings(venues_bytes(_tree(), ["Stage Left", "Cake"]))[2] == []


def test_venues_corrupted_tree_warns_and_returns_the_venue_without_nodes(venues_bytes):
    data = bytearray(venues_bytes(_tree(), ["Cake"]))
    first = bytes(data).find(struct.pack("<II", 3, 2))
    data[first + 8:first + 12] = struct.pack("<I", 1167)   # keep the head
    data[first + 12:first + 16] = struct.pack("<I", 9)     # break the name tag
    venues, presets, warnings = read_venues_with_warnings(bytes(data))
    assert [v.name for v in venues] == ["DJ Renan", "Casa"] and venues[0].nodes == []
    assert [p.name for p in presets] == ["Cake"]
    assert len(warnings) == 1 and "DJ Renan" in warnings[0]


def test_venues_corrupted_second_preset_warns(venues_bytes):
    good = venues_bytes(_tree(), ["Stage Left", "Cake", "Up"])
    second = good.find("Cake".encode("utf-16le"))
    data = bytearray(good)
    data[second - 8:second - 4] = struct.pack("<I", 7)     # the name tag
    venues, presets, warnings = read_venues_with_warnings(bytes(data))
    assert [p.name for p in presets] == ["Stage Left"]
    assert len(warnings) == 1 and "1 preset" in warnings[0]


def test_venues_without_any_preset_warns(venues_bytes):
    assert len(read_venues_with_warnings(venues_bytes(_tree(), []))[2]) == 1


def test_venues_without_presets(venues_bytes):
    assert read_venues(venues_bytes(_tree(), []))[1] == []


def test_venues_rejects_a_wrong_header():
    with pytest.raises(ValueError):
        read_venues(b"nope" + bytes(20))


# ------------------------------------------------------------------- Project ----


@pytest.fixture
def project(tmp_path, trackmap_bytes, venues_bytes):
    entries = ENTRIES[:2] + [(5, str(uuid.UUID(int=7)), "Dançarina", "Outro Artista", "x", 120, 1000)]
    (tmp_path / "SoundSwitchTrackMap.bin").write_bytes(trackmap_bytes(entries))
    (tmp_path / "SoundSwitchVenues.bin").write_bytes(venues_bytes(_tree(), ["Cake"]))
    return Project(tmp_path)


def test_project_reads_both_files(project):
    assert len(project.trackmap()) == 3
    assert project.venues()[0][0].name == "DJ Renan"


def test_project_venue_warnings(project, tmp_path, venues_bytes):
    assert project.venue_warnings() == []
    bad = Project(tmp_path)
    (tmp_path / "SoundSwitchVenues.bin").write_bytes(venues_bytes(_tree(), []))
    assert len(bad.venue_warnings()) == 1


def test_script_path_is_the_braced_upper_case_guid(project, tmp_path):
    assert project.script_path(G1) == tmp_path / ("{" + G1.upper() + "}.ssfile")


def test_resolve_by_guid_and_prefix(project):
    assert project.resolve(G2).title == "Voa Voa"
    assert project.resolve("{" + G2.upper() + "}").title == "Voa Voa"
    assert project.resolve(G1[:8].upper()).guid == G1
    with pytest.raises(LookupError):
        project.resolve(G1[:5])


def test_resolve_by_artist_and_title_is_folded(project):
    assert project.resolve("pedro sampaio — DANCARINA").guid == G1
    assert project.resolve("Outro Artista - Dançarina").guid == str(uuid.UUID(int=7))


def test_resolve_ambiguous_lists_candidates(project):
    with pytest.raises(LookupError) as e:
        project.resolve("Dançarina")
    assert "Pedro Sampaio" in str(e.value) and "Outro Artista" in str(e.value)


def test_resolve_absent(project):
    with pytest.raises(LookupError):
        project.resolve("Nobody — Nothing")


# ----------------------------------------------------------------- real files ----


@pytest.mark.skipif(not REAL, reason="NEXTRACK_SOUNDSWITCH_REAL not set")
def test_real_project():
    proj = Project(Path(REAL))
    refs, warnings = read_trackmap_with_warnings((Path(REAL) / "SoundSwitchTrackMap.bin").read_bytes())
    assert len(refs) >= 480 and all(len(r.guid) == 36 for r in refs)
    assert any(r.title.startswith("SoundSwitch 2.0") for r in refs)
    venues, presets = proj.venues()
    dj = next(v for v in venues if v.name == "DJ Renan")
    ids = {n.id: n for n in dj.nodes}
    assert ids[1167].name == "Mover 1" and ids[1168].name == "Mover 2"
    assert ids[1818].name == "VORLANE VL-1000 RGBW v2"
    assert ids[1819].parent == 1818 and ids[1936].parent == 1934
    assert ids[1934].name == " Lig Light LL-HZ600K"
    assert ids[1820].name == "RGB 01 - VORLANE VL-1000 RGBW v2"
    assert next(v for v in venues if v.name == "Casa").nodes == []
    assert [p.name for p in presets] == [
        "Disco Ball", "Stage Left", "Stage Right", "Dance Floor Centre", "DJ Booth",
        "Crossed Over", "Up", "Down", "Stage Center", "Cake"]
    assert warnings == [] and proj.venue_warnings() == []
