import os
import struct
from pathlib import Path

import pytest

from soundswitch_format import (
    FULL, MAGIC, Key, Lane, ParseError, Track, intensity, parse_script, serialize_script, track, tracks,
)

REAL = os.environ.get("NEXTRACK_SOUNDSWITCH_REAL")


def test_round_trip_is_byte_identical(make_script):
    data = serialize_script(make_script())
    assert serialize_script(parse_script(data)) == data


def test_parse_returns_the_model_that_was_serialized(make_script):
    s = make_script()
    assert parse_script(serialize_script(s)) == s


def test_header_offsets_and_tail_point_at_the_objects(make_script):
    data = serialize_script(make_script())
    off_a, off_b = struct.unpack_from("<II", data, 8)
    assert data[:4] == MAGIC and off_b == off_a + 30
    n = struct.unpack_from("<I", data, off_b + 4)[0]
    obj = struct.unpack_from("<I", data, off_b + 16)[0]
    assert n == 1 and struct.unpack_from("<I", data, obj)[0] == 0x80000001
    assert struct.unpack_from("<I", data, obj + 12)[0] == obj + 4      # self-pointer


def test_inserting_a_key_relocates_objects(make_script):
    s = make_script()
    intensity(track(s, 1167)).keys.insert(1, Key(1500, 0x80000000))
    data = serialize_script(s)
    assert parse_script(data) == s and len(data) == len(serialize_script(make_script())) + 17


def test_no_shapes_means_no_tail(make_script):
    s = make_script()
    track(s, 1167).shapes = None
    data = serialize_script(s)
    assert struct.unpack_from("<II", data, 8) == (0, 0) and parse_script(data) == s


def test_first_shape_gets_the_default_tail(make_script):
    s = make_script()
    shapes = track(s, 1167).shapes
    track(s, 1167).shapes = None
    s.tail_pre = s.tail_post = None
    track(s, 1167).shapes = shapes
    data = serialize_script(s)
    parsed = parse_script(data)
    assert parsed.tail_pre is not None and parsed.tail_post.endswith(b"Default")
    assert serialize_script(parsed) == data


def test_per_node_lists_follow_the_track_count(make_script):
    s = make_script()
    s.venues[1].tracks.append(Track(1900, [Lane(4, 1, None, [])], None, 1, None, None, None,
                                    None, None))
    parsed = parse_script(serialize_script(s))
    assert len(tracks(parsed)) == 3 and parsed.node_lists == [1, 1, 1]
    s.venues[0].tracks.pop()
    s.venues[0].tracks.pop()
    s.node_lists_ver = None
    parsed = parse_script(serialize_script(s))
    assert parsed.node_lists == [1] and parsed.node_lists_ver == 1


def test_bad_constant_names_the_offset():
    with pytest.raises(ParseError, match="0x"):
        parse_script(MAGIC + b"\x03\x00\x00\x00" + b"\x00" * 8 + b"\x0d\x00\x00\x00" + b"\xff" * 8)


def test_truncated_file_names_the_offset(make_script):
    data = serialize_script(make_script())
    with pytest.raises(ParseError, match="0x"):
        parse_script(data[:100])


def test_wrong_keyframe_constant_names_the_offset(make_script):
    s = make_script()
    data = bytearray(serialize_script(s))
    first_key = bytes(struct.pack("<IIII", 2, 1000, 1000, 0))
    at = bytes(data).index(first_key)
    data[at + 4:at + 8] = struct.pack("<I", 999)             # t2 != t
    with pytest.raises(ParseError, match="0x"):
        parse_script(bytes(data))


def test_track_lookup_by_node_ignores_position(make_script):
    s = make_script()
    s.venues[0].tracks.reverse()
    assert track(s, 1167).node == 1167 and track(s, 9999) is None
    assert [t.node for t in tracks(s)] == [1820, 1167]


def test_intensity_is_the_attr_4_lane(make_script):
    s = make_script()
    lane = intensity(track(s, 1167))
    assert lane.attr == 4 and lane.keys[1] == Key(1001, FULL)
    assert intensity(track(s, 1820)).keys == []


@pytest.mark.skipif(not REAL, reason="NEXTRACK_SOUNDSWITCH_REAL not set")
def test_real_scripts_round_trip():
    folder = Path(REAL)
    files = sorted(folder.glob("{*}.ssfile")) + sorted(folder.glob("SSAutoLoop*.ssfile"))
    assert files, "no .ssfile in NEXTRACK_SOUNDSWITCH_REAL"
    for path in files:
        data = path.read_bytes()
        assert serialize_script(parse_script(data)) == data, path.name
