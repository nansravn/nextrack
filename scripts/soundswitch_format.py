"""SoundSwitch per-track lighting scripts (`{GUID}.ssfile`): typed model, parser, serializer.

`parse_script` turns the bytes into a `TrackScript`; `serialize_script` writes them back.
Every derived field (header offsets, object ids, self-pointers, the tail table) is
recomputed on write, so an edited model always serializes to a consistent file. Parsing
checks every constant that is the same in all known files and raises `ParseError` with
the offset in hex when one differs.

Section letters follow docs/soundswitch/file-format.md: B intensity blocks, C colour
blocks, D position flags, E strobe blocks, F position blocks, G movement shape blocks.
Times are milliseconds from the start of the track. A level is a 0.32 fixed-point
fraction (`level / 2**32`).
"""
from __future__ import annotations

import math
import struct
import uuid
from dataclasses import dataclass, field, replace

MAGIC = b"\xaa\xaa\x09\x55"
MARK = 0x80808080         # in front of every present node section C..G
END = 0xFFFFFFFF          # ends a lane list
FULL = 0xFFFFFFA0         # the level the autoscript writes for 100 %
OBJ_TAG = 0x80000000      # object tag = OBJ_TAG | id
DEFAULT_TAIL_PRE = "010001000000ffffffffe8b47929ce7c51418bbe716a8dd523fd00000000"
DEFAULT_TAIL_POST = "ffffffff0700000044656661756c74"
TAIL_PRE_SIZE = 30
POST_TEMPO_SIZE = 15
POST_CUE_SIZE = 10
FMT_NODE_LISTS = 13       # from this format revision on, each node has a trailing list

_KEY = struct.Struct("<IIIIB")
_SPAN = struct.Struct("<IIII")
_COLOUR = struct.Struct("<IIIIIIIII")
_FLAG = struct.Struct("<IIIII")
_STROBE = struct.Struct("<IIIIIdd")
_CUE = struct.Struct("<IIII")
_TEMPO = struct.Struct("<IId")
_SHAPE_HEAD = struct.Struct("<II4dBIII")
_SHAPE_OBJ = struct.Struct("<IIII")


class ParseError(ValueError):
    """The bytes are not a script this module understands; the message names the offset."""


# ------------------------------------------------------------------- model ----


@dataclass
class Key:
    t: int
    level: int


@dataclass
class Lane:
    attr: int
    ver: int
    default: int | None
    keys: list[Key]


@dataclass
class Span:
    start: int
    end: int


@dataclass
class ColourBlock:
    start: int
    end: int
    colour: int          # 0xAARRGGBB
    ext: int
    colour_end: int
    ext_end: int


@dataclass
class PositionFlag:
    t: int
    preset: int          # index into the Positions palette


@dataclass
class Positions:
    ver: int
    x: int
    palette: list[tuple[str, int]]
    flags: list[PositionFlag]


@dataclass
class StrobeBlock:
    start: int
    end: int
    rate: float
    rate_end: float


@dataclass
class ShapeBlock:
    start: int
    end: int
    a: int
    b: int
    params: tuple[float, float, float, float]
    flag: int
    one: int
    kind: int
    kver: int


@dataclass
class Section:
    """Sections B, C, E and F: a version and a list of blocks."""
    ver: int
    items: list


@dataclass
class Shapes:
    ver: int
    x: int
    items: list[ShapeBlock]


@dataclass
class Track:
    node: int
    lanes: list[Lane]
    blocks: Section | None            # B (Span)
    link: int
    colours: Section | None           # C (ColourBlock)
    positions: Positions | None       # D
    strobes: Section | None           # E (StrobeBlock)
    position_blocks: Section | None   # F (Span)
    shapes: Shapes | None             # G


@dataclass
class Venue:
    key: int
    guid: str
    key2: int
    tracks: list[Track]
    trailer: tuple[int, int]


@dataclass
class TrackScript:
    container_ver: int
    fmt: int
    venues: list[Venue]
    global_ver: int
    tempo: list[tuple[int, float]]
    post_tempo: bytes
    main: Track
    pre_cue: list[int]
    cue_palette: list[tuple[str, int]]
    cue_flags: list[tuple[int, int]]
    post_cue: bytes
    node_lists_ver: int | None
    node_lists: list[int]
    # Fixed bytes around the object table. They exist only when the script has a shape
    # block, so they are not part of equality.
    tail_pre: bytes | None = field(compare=False)
    tail_post: bytes | None = field(compare=False)


def tracks(script: TrackScript) -> list[Track]:
    """Every venue's tracks, in file order (the Main track is `script.main`)."""
    return [t for v in script.venues for t in v.tracks]


def track(script: TrackScript, node: int) -> Track | None:
    """The track with this node id; node ids are not stable positions, always look up."""
    return next((t for t in tracks(script) if t.node == node), None)


def intensity(trk: Track) -> Lane | None:
    """The intensity curve: the attr-4 lane."""
    return next((ln for ln in trk.lanes if ln.attr == 4), None)


# ------------------------------------------------------------------ parsing ----


class _Reader:
    def __init__(self, data: bytes, pos: int = 0):
        self.b = data
        self.o = pos

    def fail(self, msg: str, at: int | None = None):
        raise ParseError(f"{msg} at {self.o if at is None else at:#x}")

    def _need(self, n: int):
        if self.o + n > len(self.b):
            self.fail(f"unexpected end of file (need {n} bytes)")

    def u32(self) -> int:
        self._need(4)
        (v,) = struct.unpack_from("<I", self.b, self.o)
        self.o += 4
        return v

    def raw(self, n: int) -> bytes:
        self._need(n)
        v = self.b[self.o:self.o + n]
        self.o += n
        return v

    def guid(self) -> str:
        return str(uuid.UUID(bytes_le=self.raw(16)))

    def expect(self, what: str, value: int):
        at = self.o
        got = self.u32()
        if got != value:
            self.fail(f"{what}: expected {value:#x}, got {got:#x}", at)

    def rows(self, st: struct.Struct, n: int) -> list[tuple]:
        """n fixed-size records, with the offset of each available for error messages."""
        if n * st.size > len(self.b) - self.o:
            self.fail(f"table of {n} x {st.size} bytes overruns the file")
        end = self.o + n * st.size
        out = list(st.iter_unpack(self.b[self.o:end]))
        self.o = end
        return out

    def check_rows(self, what: str, rows: list[tuple], start: int, size: int, ok):
        """Run `ok(row)` on every row; a False names the row's offset."""
        for i, row in enumerate(rows):
            if not ok(row):
                self.fail(f"{what}: unexpected constants {row}", start + i * size)


def _lanes(r: _Reader) -> list[Lane]:
    lanes = []
    while True:
        attr = r.u32()
        if attr == END:
            return lanes
        at = r.o
        ver = r.u32()
        if ver != 1:
            r.fail(f"lane version {ver}", at)
        has_default = r.u32()
        if has_default not in (0, 1):
            r.fail(f"lane has_default {has_default}", r.o - 4)
        default = r.u32() if has_default else None
        n = r.u32()
        start = r.o
        rows = r.rows(_KEY, n)
        r.check_rows("keyframe", rows, start, _KEY.size,
                     lambda k: k[0] == 2 and k[1] == k[2] and k[4] == 0)
        lanes.append(Lane(attr, ver, default, [Key(k[1], k[3]) for k in rows]))


def _section(r: _Reader, name: str, body):
    mark = r.u32()
    if mark == 0:
        return None
    if mark != MARK:
        r.fail(f"section {name}: marker {mark:#x}", r.o - 4)
    return body()


def _span_section(r: _Reader, what: str) -> Section:
    ver = r.u32()
    n = r.u32()
    start = r.o
    rows = r.rows(_SPAN, n)
    r.check_rows(what, rows, start, _SPAN.size, lambda s: s[0] == 1 and s[1] == 1)
    return Section(ver, [Span(s[2], s[3]) for s in rows])


def _node(r: _Reader, objs: list[int]) -> Track:
    node = r.u32()
    lanes = _lanes(r)

    flag = r.u32()
    if flag not in (0, 1):
        r.fail(f"section B: flag {flag}", r.o - 4)
    blocks = _span_section(r, "intensity block") if flag else None
    link = r.u32()

    def colours():
        ver = r.u32()
        n = r.u32()
        start = r.o
        rows = r.rows(_COLOUR, n)
        r.check_rows("colour block", rows, start, _COLOUR.size,
                     lambda c: c[0] == 1 and c[1] == 2 and c[2] == 1)
        return Section(ver, [ColourBlock(c[3], c[4], c[5], c[6], c[7], c[8]) for c in rows])

    def positions():
        ver = r.u32()
        x = r.u32()
        palette = [(r.guid(), r.u32()) for _ in range(r.u32())]
        n = r.u32()
        start = r.o
        rows = r.rows(_FLAG, n)
        r.check_rows("position flag", rows, start, _FLAG.size,
                     lambda f: f[0] == 1 and f[1] == 1 and f[3] == 1)
        return Positions(ver, x, palette, [PositionFlag(f[2], f[4]) for f in rows])

    def strobes():
        ver = r.u32()
        n = r.u32()
        start = r.o
        rows = r.rows(_STROBE, n)
        r.check_rows("strobe block", rows, start, _STROBE.size,
                     lambda s: s[0] == 1 and s[1] == 1 and s[2] == 1)
        return Section(ver, [StrobeBlock(s[3], s[4], s[5], s[6]) for s in rows])

    def shapes():
        ver = r.u32()
        x = r.u32()
        items = []
        for _ in range(r.u32()):
            items.append(_shape(r, objs))
        return Shapes(ver, x, items)

    c = _section(r, "C", colours)
    d = _section(r, "D", positions)
    e = _section(r, "E", strobes)
    f = _section(r, "F", lambda: _span_section(r, "position block"))
    g = _section(r, "G", shapes)
    return Track(node, lanes, blocks, link, c, d, e, f, g)


def _shape(r: _Reader, objs: list[int]) -> ShapeBlock:
    at = r.o
    r._need(_SHAPE_HEAD.size + _SHAPE_OBJ.size)
    a, b, p0, p1, p2, p3, flag, one, start, end = _SHAPE_HEAD.unpack_from(r.b, r.o)
    r.o += _SHAPE_HEAD.size
    if (a, b, one) != (0, 2, 1):
        r.fail(f"shape block: unexpected constants {(a, b, one)}", at)
    tag_at = r.o
    tag, kind, kver, ptr = struct.unpack_from("<IIII", r.b, r.o)
    r.o += _SHAPE_OBJ.size
    if tag != OBJ_TAG | (len(objs) + 1):
        r.fail(f"shape object tag {tag:#x}, expected id {len(objs) + 1}", tag_at)
    if kver != 1:
        r.fail(f"shape object version {kver}", tag_at + 8)
    if ptr != tag_at + 4:
        r.fail(f"shape self-pointer {ptr:#x}, expected {tag_at + 4:#x}", tag_at + 12)
    objs.append(tag_at)
    return ShapeBlock(start, end, a, b, (p0, p1, p2, p3), flag, one, kind, kver)


def parse_script(data: bytes) -> TrackScript:
    """Parse a `.ssfile`; raises `ParseError` (message ends in the hex offset) otherwise."""
    if data[:4] != MAGIC:
        raise ParseError("bad magic at 0x0")
    r = _Reader(data, 4)
    container_ver = r.u32()
    off_a = r.u32()
    off_b = r.u32()
    fmt = r.u32()
    objs: list[int] = []
    venues = []
    for _ in range(r.u32()):
        key_at = r.o
        key = r.u32()
        if key != 4:
            r.fail(f"venue key {key}", key_at)
        guid = r.guid()
        key2_at = r.o
        key2 = r.u32()
        if key2 != 3:
            r.fail(f"venue key2 {key2}", key2_at)
        nodes = [_node(r, objs) for _ in range(r.u32())]
        trailer_at = r.o
        trailer = (r.u32(), r.u32())
        if trailer != (1, 0):
            r.fail(f"venue trailer {trailer}", trailer_at)
        venues.append(Venue(key, guid, key2, nodes, trailer))

    global_ver = r.u32()
    n = r.u32()
    start = r.o
    rows = r.rows(_TEMPO, n)
    r.check_rows("tempo anchor", rows, start, _TEMPO.size, lambda t: t[0] == 1)
    tempo = [(t[1], t[2]) for t in rows]
    post_tempo = r.raw(POST_TEMPO_SIZE)
    main = _node(r, objs)
    pre_cue = [r.u32() for _ in range(8)]
    cue_palette = [(r.guid(), r.u32()) for _ in range(r.u32())]
    n = r.u32()
    start = r.o
    rows = r.rows(_CUE, n)
    r.check_rows("cue flag", rows, start, _CUE.size, lambda c: c[0] == 1 and c[1] == 1)
    cue_flags = [(c[2], c[3]) for c in rows]
    post_cue = r.raw(POST_CUE_SIZE)

    node_lists_ver = None
    node_lists: list[int] = []
    if fmt >= FMT_NODE_LISTS:
        node_lists_ver = r.u32()
        for _ in range(sum(len(v.tracks) for v in venues)):
            at = r.o
            mark, ver, count = r.u32(), r.u32(), r.u32()
            if mark != MARK or count:
                r.fail(f"per-node list marker {mark:#x}, count {count}", at)
            node_lists.append(ver)

    tail_pre = tail_post = None
    if off_a == 0 and off_b == 0:
        if r.o != len(data):
            r.fail("script without tail but with trailing bytes")
        if objs:
            r.fail("script without tail but with shape objects")
    else:
        if r.o != off_a:
            r.fail(f"body ends here but the header says offA={off_a:#x}")
        tail_pre = r.raw(TAIL_PRE_SIZE)
        if r.o != off_b:
            r.fail(f"header says offB={off_b:#x}, expected {r.o:#x}", 12)
        one, count, neg, one2 = struct.unpack_from("<IIiI", r.raw(16))
        if (one, one2) != (1, 1) or neg != -count or count != len(objs):
            r.fail(f"tail header {(one, count, neg, one2)} for {len(objs)} objects", r.o - 16)
        start = r.o
        rows = r.rows(_SHAPE_OBJ, count)
        r.check_rows("tail entry", rows, start, _SHAPE_OBJ.size,
                     lambda e: e[1:] == (12, 0, 1))
        for i, (row, obj) in enumerate(zip(rows, objs)):
            if row[0] != obj:
                r.fail(f"tail entry points at {row[0]:#x}, object is at {obj:#x}",
                       start + i * 16)
        tail_post = r.raw(len(data) - r.o)

    return TrackScript(container_ver, fmt, venues, global_ver, tempo, post_tempo, main,
                       pre_cue, cue_palette, cue_flags, post_cue, node_lists_ver,
                       node_lists, tail_pre, tail_post)


# --------------------------------------------------------------- serializing ----


class _Writer:
    def __init__(self):
        self.parts: list[bytes] = []
        self.size = 0
        self.objs: list[int] = []

    def put(self, data: bytes):
        self.parts.append(data)
        self.size += len(data)

    def u32(self, *values: int):
        self.put(struct.pack(f"<{len(values)}I", *values))

    def guid(self, text: str):
        self.put(uuid.UUID(text).bytes_le)

    def rows(self, st: struct.Struct, rows: list[tuple]):
        self.u32(len(rows))
        self.put(b"".join(st.pack(*row) for row in rows))


def _write_node(w: _Writer, t: Track):
    w.u32(t.node)
    for ln in t.lanes:
        w.u32(ln.attr, ln.ver, 0 if ln.default is None else 1)
        if ln.default is not None:
            w.u32(ln.default)
        w.rows(_KEY, [(2, k.t, k.t, k.level, 0) for k in ln.keys])
    w.u32(END)
    if t.blocks is None:
        w.u32(0)
    else:
        w.u32(1, t.blocks.ver)
        w.rows(_SPAN, [(1, 1, s.start, s.end) for s in t.blocks.items])
    w.u32(t.link)

    if t.colours is None:
        w.u32(0)
    else:
        w.u32(MARK, t.colours.ver)
        w.rows(_COLOUR, [(1, 2, 1, c.start, c.end, c.colour, c.ext, c.colour_end, c.ext_end)
                         for c in t.colours.items])
    p = t.positions
    if p is None:
        w.u32(0)
    else:
        w.u32(MARK, p.ver, p.x, len(p.palette))
        for guid, index in p.palette:
            w.guid(guid)
            w.u32(index)
        w.rows(_FLAG, [(1, 1, f.t, 1, f.preset) for f in p.flags])
    if t.strobes is None:
        w.u32(0)
    else:
        w.u32(MARK, t.strobes.ver)
        w.rows(_STROBE, [(1, 1, 1, s.start, s.end, s.rate, s.rate_end) for s in t.strobes.items])
    if t.position_blocks is None:
        w.u32(0)
    else:
        w.u32(MARK, t.position_blocks.ver)
        w.rows(_SPAN, [(1, 1, s.start, s.end) for s in t.position_blocks.items])
    g = t.shapes
    if g is None:
        w.u32(0)
    else:
        w.u32(MARK, g.ver, g.x, len(g.items))
        for s in g.items:
            w.put(struct.pack("<II4dBIII", s.a, s.b, *s.params, s.flag, s.one, s.start, s.end))
            tag_at = w.size
            w.objs.append(tag_at)
            # ids are renumbered 1..N in file order, as in every real file
            w.u32(OBJ_TAG | len(w.objs), s.kind, s.kver, tag_at + 4)


def serialize_script(script: TrackScript) -> bytes:
    """Write the script; offsets, object ids, self-pointers and the tail are recomputed."""
    w = _Writer()
    w.put(MAGIC)
    w.u32(script.container_ver, 0, 0, script.fmt, len(script.venues))
    for v in script.venues:
        w.u32(v.key)
        w.guid(v.guid)
        w.u32(v.key2, len(v.tracks))
        for t in v.tracks:
            _write_node(w, t)
        w.u32(*v.trailer)
    w.u32(script.global_ver)
    w.rows(_TEMPO, [(1, t, bpm) for t, bpm in script.tempo])
    w.put(script.post_tempo)
    _write_node(w, script.main)
    w.u32(*script.pre_cue)
    w.u32(len(script.cue_palette))
    for guid, index in script.cue_palette:
        w.guid(guid)
        w.u32(index)
    w.rows(_CUE, [(1, 1, t, index) for t, index in script.cue_flags])
    w.put(script.post_cue)
    if script.fmt >= FMT_NODE_LISTS:
        # one entry per venue track, however many tracks the model now has
        w.u32(1 if script.node_lists_ver is None else script.node_lists_ver)
        for i in range(sum(len(v.tracks) for v in script.venues)):
            w.u32(MARK, script.node_lists[i] if i < len(script.node_lists) else 1, 0)
    if not w.objs:                      # no shape objects: no tail, offA = offB = 0
        return b"".join(w.parts)

    off_a = w.size
    w.put(script.tail_pre if script.tail_pre is not None else bytes.fromhex(DEFAULT_TAIL_PRE))
    off_b = w.size
    n = len(w.objs)
    w.put(struct.pack("<IIiI", 1, n, -n, 1))
    for obj in w.objs:
        w.u32(obj, 12, 0, 1)
    w.put(script.tail_post if script.tail_post is not None else bytes.fromhex(DEFAULT_TAIL_POST))
    out = bytearray(b"".join(w.parts))
    struct.pack_into("<II", out, 8, off_a, off_b)
    return bytes(out)


# ---------------------------------------------------------------- tempo grid ----


class Grid:
    """Bars and beats from the tempo anchors.

    Bar 1 beat 1 is the first anchor. A bar is 4 beats; beats are counted straight
    through later anchors, each segment at its own BPM, so a bar can straddle an anchor.
    """

    def __init__(self, tempo: list[tuple[int, float]]):
        if not tempo:
            raise ValueError("a grid needs at least one tempo anchor")
        self.anchors = list(tempo)
        self.beats = [0.0]                # beats elapsed at each anchor
        for (t0, bpm), (t1, _) in zip(self.anchors, self.anchors[1:]):
            self.beats.append(self.beats[-1] + (t1 - t0) * bpm / 60000)

    def _segment_at(self, t: float) -> int:
        i = 0
        for j, (at, _) in enumerate(self.anchors):
            if at <= t:
                i = j
        return i

    def beat_ms(self, t: int) -> float:
        """Length of one beat at time `t`."""
        return 60000 / self.anchors[self._segment_at(t)][1]

    def _beats_at(self, t: float) -> float:
        i = self._segment_at(t)
        at, bpm = self.anchors[i]
        return self.beats[i] + (t - at) * bpm / 60000

    def ms(self, bar: int, beat: float = 1.0) -> int:
        """Time of `beat` (1-based, fractions allowed) in `bar` (1-based)."""
        b = (bar - 1) * 4 + (beat - 1)
        i = 0
        for j, start in enumerate(self.beats):
            if start <= b + 1e-9:
                i = j
        at, bpm = self.anchors[i]
        return round(at + (b - self.beats[i]) * 60000 / bpm)

    def bar_at(self, t: int) -> int:
        """The bar `t` falls in; bar 1 starts at the first anchor."""
        return math.floor(self._beats_at(t) / 4 + 1e-9) + 1


def grid(script: TrackScript) -> Grid:
    return Grid(script.tempo)


# --------------------------------------------------------------- edit helpers ----


def level_at(lane: Lane | None, t: int) -> int:
    """Linear envelope: 0 before the first key, the last level after the last."""
    if lane is None or not lane.keys or t < lane.keys[0].t:
        return 0
    prev = lane.keys[0]
    for k in lane.keys[1:]:
        if t < k.t:
            return round(prev.level + (k.level - prev.level) * (t - prev.t) / (k.t - prev.t))
        prev = k
    return prev.level


def covered(trk: Track, t: int) -> bool:
    """True when `t` is inside one of the track's B spans (ends inclusive)."""
    return trk.blocks is not None and any(s.start <= t <= s.end for s in trk.blocks.items)


def _add_span(section: Section, start: int, end: int) -> None:
    """Add [start, end] to a span section, merging overlapping or adjacent spans."""
    keep = []
    for s in section.items:
        if s.end + 1 >= start and s.start - 1 <= end:
            start, end = min(start, s.start), max(end, s.end)
        else:
            keep.append(s)
    keep.append(Span(start, end))
    section.items = sorted(keep, key=lambda s: s.start)


def _intensity_lane(trk: Track) -> Lane:
    lane = intensity(trk)
    if lane is None:
        lane = Lane(4, 1, None, [])
        trk.lanes.insert(0, lane)
    return lane


def _replace_keys(lane: Lane, start: int, end: int, keys: list[Key]) -> None:
    """Swap the keys in [start, end] for `keys`; levels outside the span stay as they were."""
    if any(not start <= k.t <= end for k in keys):
        raise ValueError(f"keys must lie inside [{start}, {end}]")
    left, right = level_at(lane, start - 1), level_at(lane, end + 1)
    kept = [k for k in lane.keys if not start <= k.t <= end]
    new = [Key(k.t, k.level) for k in keys]
    if start >= 1 and not any(k.t == start - 1 for k in kept):
        new.append(Key(start - 1, left))
    if not any(k.t == end + 1 for k in kept):
        new.append(Key(end + 1, right))
    lane.keys = sorted(kept + new, key=lambda k: k.t)


def set_intensity(trk: Track, start: int, end: int, keys: list[Key]) -> None:
    """Replace the track's intensity keys in [start, end] and make its B spans cover it."""
    _replace_keys(_intensity_lane(trk), start, end, keys)
    if trk.blocks is None:
        trk.blocks = Section(1, [])
    _add_span(trk.blocks, start, end)


def _cut(items: list, start: int, end: int) -> list:
    """The blocks with the part inside (start, end) removed; touching ends are kept."""
    out = []
    for b in items:
        if b.end <= start or b.start >= end:
            out.append(b)
            continue
        if b.start < start:
            out.append(replace(b, end=start))
        if b.end > end:
            out.append(replace(b, start=end))
    return out


def set_colour(trk: Track, start: int, end: int, colour: int,
               colour_end: int | None = None) -> None:
    """Put one colour block over [start, end], trimming the blocks it overlaps."""
    if trk.colours is None:
        trk.colours = Section(1, [])
    block = ColourBlock(start, end, colour, 0, colour if colour_end is None else colour_end, 0)
    trk.colours.items = sorted(_cut(trk.colours.items, start, end) + [block],
                               key=lambda c: c.start)


def _preset(pos: Positions, entry: tuple[str, int]) -> int:
    """Index of a palette entry in `pos`, appended when missing."""
    if entry not in pos.palette:
        pos.palette.append(entry)
    return pos.palette.index(entry)


def _positions_of(trk: Track, palette: list[tuple[str, int]], ver: int = 2,
                  x: int = 1) -> Positions:
    if trk.positions is None:
        trk.positions = Positions(ver, x, [], [])
    if not trk.positions.palette:
        trk.positions.palette = list(palette)
    return trk.positions


def set_positions(trk: Track, start: int, end: int, flags: list[PositionFlag],
                  palette: list[tuple[str, int]]) -> None:
    """Position-block span [start, end] with its flags; shape blocks it overlaps go.

    `flags` index into `palette`. A track that already has a palette keeps it, and the
    flags are re-pointed (the entry is appended when the track lacks it).
    """
    pos = _positions_of(trk, palette)
    new = [PositionFlag(f.t, _preset(pos, palette[f.preset])) for f in flags]
    pos.flags = sorted([f for f in pos.flags if not start <= f.t <= end] + new,
                       key=lambda f: f.t)
    if trk.position_blocks is None:
        trk.position_blocks = Section(1, [])
    _add_span(trk.position_blocks, start, end)
    if trk.shapes is not None:
        trk.shapes.items = _cut_whole(trk.shapes.items, start, end)


def _cut_whole(items: list, start: int, end: int) -> list:
    return [b for b in items if b.end <= start or b.start >= end]


def set_main(script: TrackScript, start: int, end: int, keys: list[Key],
             colour: int | None = None) -> None:
    """Edit the Main track: intensity keys in [start, end] and, if given, its colour."""
    _replace_keys(_intensity_lane(script.main), start, end, keys)
    if colour is not None:
        set_colour(script.main, start, end, colour)


def _gaps(occupied: list[tuple[int, int]], start: int, end: int, step: int) -> list[tuple[int, int]]:
    """Sub-spans of [start, end] outside `occupied`.

    step 1: occupied ends are inclusive, so a gap stops one ms short of them.
    step 0: blocks that only touch the gap leave it whole (colour blocks).
    """
    out = []
    cursor = start
    for s, e in sorted(occupied):
        hi = min(s - step, end)
        if hi > cursor or (step and hi == cursor):
            out.append((cursor, hi))
        cursor = max(cursor, e + step)
    if end > cursor or (step and end == cursor):
        out.append((cursor, end))
    return out


def _materialise_intensity(script: TrackScript, trk: Track, start: int, end: int) -> None:
    main = intensity(script.main)
    own = [(s.start, s.end) for s in trk.blocks.items] if trk.blocks else []
    for a, b in _gaps(own, start, end, 1):
        keys = [Key(a, level_at(main, a))]
        keys += [Key(k.t, k.level) for k in main.keys if a < k.t < b] if main else []
        if b > a:
            keys.append(Key(b, level_at(main, b)))
        set_intensity(trk, a, b, keys)


def _materialise_colour(script: TrackScript, trk: Track, start: int, end: int) -> None:
    if script.main.colours is None:
        return
    own = [(c.start, c.end) for c in trk.colours.items] if trk.colours else []
    for a, b in _gaps(own, start, end, 0):
        for c in script.main.colours.items:
            lo, hi = max(c.start, a), min(c.end, b)
            if lo < hi:
                if trk.colours is None:
                    trk.colours = Section(1, [])
                trk.colours.items.append(replace(c, start=lo, end=hi))
    if trk.colours is not None:
        trk.colours.items.sort(key=lambda c: c.start)


def _materialise_position(script: TrackScript, trk: Track, start: int, end: int) -> None:
    m = script.main
    own = [(s.start, s.end) for s in trk.position_blocks.items] if trk.position_blocks else []
    own += [(s.start, s.end) for s in trk.shapes.items] if trk.shapes else []
    for a, b in _gaps(own, start, end, 1):
        for f in m.position_blocks.items if m.position_blocks else []:
            lo, hi = max(f.start, a), min(f.end, b)
            if lo > hi:
                continue
            main_pos = m.positions
            pos = (_positions_of(trk, main_pos.palette, main_pos.ver, main_pos.x)
                   if main_pos else _positions_of(trk, []))
            flags = [PositionFlag(x.t, _preset(pos, main_pos.palette[x.preset]))
                     for x in (main_pos.flags if main_pos else []) if lo <= x.t <= hi]
            pos.flags = sorted(pos.flags + flags, key=lambda x: x.t)
            if trk.position_blocks is None:
                trk.position_blocks = Section(m.position_blocks.ver, [])
            _add_span(trk.position_blocks, lo, hi)
        for g in m.shapes.items if m.shapes else []:
            lo, hi = max(g.start, a), min(g.end, b)
            if lo < hi:
                if trk.shapes is None:
                    trk.shapes = Shapes(m.shapes.ver, m.shapes.x, [])
                trk.shapes.items.append(replace(g, start=lo, end=hi))
    if trk.shapes is not None:
        trk.shapes.items.sort(key=lambda g: g.start)


_MATERIALISE = {"intensity": _materialise_intensity, "colour": _materialise_colour,
                "position": _materialise_position}


def materialise_main(script: TrackScript, trk: Track, start: int, end: int,
                     lanes: frozenset[str] = frozenset({"intensity", "colour", "position"})) -> None:
    """Copy Main's content into `trk` over [start, end] where the track has none of its own.

    Per lane, so that a later edit of one lane does not lose what the track was showing
    through Main in the others. The track's own content is never touched.
    """
    unknown = set(lanes) - set(_MATERIALISE)
    if unknown:
        raise ValueError(f"unknown lanes {sorted(unknown)}")
    for name in ("intensity", "colour", "position"):
        if name in lanes:
            _MATERIALISE[name](script, trk, start, end)


def _overlap(items: list) -> bool:
    return any(b.start < a.end for a, b in zip(items, items[1:]))


def check(script: TrackScript) -> list[str]:
    """Invariants of an edited script; an empty list means it is valid."""
    out = []
    for trk in [*tracks(script), script.main]:
        who = f"node {trk.node}"
        for ln in trk.lanes:
            if any(b.t < a.t for a, b in zip(ln.keys, ln.keys[1:])):
                out.append(f"{who}: lane {ln.attr} keys are not sorted by time")
        sections = {"B": trk.blocks, "C": trk.colours, "E": trk.strobes,
                    "F": trk.position_blocks, "G": trk.shapes}
        for letter, sec in sections.items():
            items = sec.items if sec else []
            if any(b.start > b.end for b in items):
                out.append(f"{who}: section {letter} has a block that ends before it starts")
            if any(b.start < a.start for a, b in zip(items, items[1:])):
                out.append(f"{who}: section {letter} is not sorted")
            elif _overlap(items):
                out.append(f"{who}: section {letter} has overlapping blocks")
        f_items = trk.position_blocks.items if trk.position_blocks else []
        g_items = trk.shapes.items if trk.shapes else []
        if any(f.start < g.end and g.start < f.end for f in f_items for g in g_items):
            out.append(f"{who}: position blocks (F) and shape blocks (G) overlap")
        for fl in trk.positions.flags if trk.positions else []:
            if not any(f.start <= fl.t <= f.end for f in f_items):
                out.append(f"{who}: position flag at {fl.t} is outside every position block")
    return out
