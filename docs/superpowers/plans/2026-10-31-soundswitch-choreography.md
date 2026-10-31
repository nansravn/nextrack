# SoundSwitch Choreography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read, analyse, simulate and safely edit the owner's SoundSwitch track scripts from intent-level choreography files, so Claude can direct the light show per track and across a set.

**Architecture:** Three modules in `scripts/`: `soundswitch_format.py` (bytes ↔ typed model for the container, track scripts, TrackMap and the parts of Venues the tools need), `lightshow.py` (rig and choreography model, vocabulary, frame generators, compiler from choreography to model edits), `nextrack_lights.py` (CLI: `tracks`, `dump`, `analyze`, `render`, `compile`, `apply`, with the write-safety model). `check_repo.py` gains three rules for the `lightshows/` data. A project skill drives the per-track workflow.

**Tech Stack:** Python ≥ 3.12 stdlib + pyyaml; pytest; uv. No numpy.

**Spec:** `docs/superpowers/specs/2026-10-31-soundswitch-choreography-design.md`

## Global Constraints

- Never write to a real SoundSwitch project from a test; tests build synthetic files under `tmp_path`. No real `.ssfile`, `.ssa`, TrackMap or Venues bytes are committed (the repo is public).
- The project folder comes from `--project` or `NEXTRACK_SOUNDSWITCH_PROJECT`; one of the two is required. Never hard-code a machine path. Tests delete the variable (autouse fixture), like `NEXTRACK_AUDIO_ROOT`.
- Real-file tests (round trip over the owner's scripts) run only when `NEXTRACK_SOUNDSWITCH_REAL` points at a project folder, and are skipped otherwise (CI never has it).
- Dry-run by default; only `apply --apply` writes into a project, and only via the safety model (spec "Safety model for writes").
- Never decrypt or modify `.ssa` files.
- Ids, schema keys, code, `docs/`: English. Choreography `story`/`intent` and pool/block prose: pt-BR.
- Commit subjects are imperative English sentences (`Add …`), no `feat:` prefix; end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Definition of done per task: `uv run pytest` and `uv run scripts/check_repo.py` both pass.

## Review Focus

- A script with a second venue ("Casa", 0 tracks) and stale node ids from older venue layouts: tools must address tracks by node id and ignore stale ones, never by position. → Task 1 and Task 7 tests.
- A track with a multi-anchor tempo map (114 of 501 real scripts): bar ↔ ms must follow every anchor, not just the first. → Task 2 test.
- An edit span that cuts through an existing intensity block or a key ramp: the result must keep keys sorted, blocks non-overlapping, and the level at the span edges continuous (insert boundary keys). → Task 2 tests.
- A file with no G objects (no tail, offA = offB = 0) and an edit that removes the last G object: serialize must emit the no-tail form. → Task 1 test.
- `apply --apply` while SoundSwitch is running, or with an output that changed size before X1 is confirmed: refuse with a clear message and write nothing. → Task 9 tests.

---

### Task 1: Track-script model, parser and serializer

**Files:**
- Create: `scripts/soundswitch_format.py`
- Create: `tests/test_soundswitch_format.py`
- Modify: `tests/conftest.py` (autouse: delete `NEXTRACK_SOUNDSWITCH_PROJECT`; fixture `make_script`)

**Interfaces:**
- Produces (all in `soundswitch_format`):
  - `MAGIC = b"\xaa\xaa\x09\x55"`, `MARK = 0x80808080`, `FULL = 0xFFFFFFA0` (the level the autoscript writes for 100 %), `class ParseError(ValueError)`.
  - Dataclasses (mutable, `eq=True`): `Key(t: int, level: int)`; `Lane(attr: int, ver: int, default: int | None, keys: list[Key])`; `Span(start: int, end: int)`; `ColourBlock(start: int, end: int, colour: int, ext: int, colour_end: int, ext_end: int)`; `PositionFlag(t: int, preset: int)`; `Positions(ver: int, x: int, palette: list[tuple[str, int]], flags: list[PositionFlag])`; `StrobeBlock(start: int, end: int, rate: float, rate_end: float)`; `ShapeBlock(start: int, end: int, a: int, b: int, params: tuple[float, float, float, float], flag: int, one: int, kind: int, kver: int)`; `Section(ver: int, items: list)`; `Shapes(ver: int, x: int, items: list[ShapeBlock])`; `Track(node: int, lanes: list[Lane], blocks: Section | None, link: int, colours: Section | None, positions: Positions | None, strobes: Section | None, position_blocks: Section | None, shapes: Shapes | None)`; `Venue(key: int, guid: str, key2: int, tracks: list[Track], trailer: tuple[int, int])`; `TrackScript(container_ver: int, fmt: int, venues: list[Venue], global_ver: int, tempo: list[tuple[int, float]], post_tempo: bytes, main: Track, pre_cue: list[int], cue_palette: list[tuple[str, int]], cue_flags: list[tuple[int, int]], post_cue: bytes, node_lists_ver: int | None, node_lists: list[int], tail_pre: bytes | None, tail_post: bytes | None)`.
  - `parse_script(data: bytes) -> TrackScript`, `serialize_script(script: TrackScript) -> bytes`, `tracks(script) -> list[Track]` (every venue's tracks, in file order), `track(script, node: int) -> Track | None`, `intensity(track) -> Lane | None` (the attr-4 lane).

The grammar is the spike's (`docs/soundswitch/file-format.md`, written in Task 11; until then the spec's "How SoundSwitch stores a show"). Port it faithfully: key record `(2, t, t, level, 0)`, span `(1, 1, start, end)`, colour `(1, 2, 1, start, end, colour, ext, colour_end, ext_end)`, flag `(1, 1, t, 1, preset)`, strobe `(1, 1, 1, start, end, rate, rate_end)`, cue flag `(1, 1, t, index)`, tempo `(1, t, bpm)`; G item `u32 a, u32 b, 4×f64, u8 flag, u32 one, u32 start, u32 end, OBJ(u32 0x80000000|id, u32 kind, u32 kver), u32 ptr = &OBJ + 4`; tail at offA = 30 bytes `tail_pre`, then `(1, N, -N, 1)` and N × `(obj_offset, 12, 0, 1)`, then `tail_post`. Parse validates every constant above and raises `ParseError` naming the offset; serialize recomputes offA, offB, object ids (1..N in file order), self-pointers and the tail table, and emits no tail (offA = offB = 0) when there is no G object. Default `tail_pre`/`tail_post` when a script gains its first G object: `010001000000ffffffffe8b47929ce7c51418bbe716a8dd523fd00000000` and `ffffffff0700000044656661756c74` (hex).

- [ ] **Step 1: Write the failing tests** (in `tests/test_soundswitch_format.py`; `make_script(**overrides) -> TrackScript` in conftest builds a small valid script: fmt 13, venue "DJ" with tracks 1167 (intensity keys `[(1000, 0), (1001, FULL), (1300, 0)]`, one B span `(1000, 2000)`, one colour block, one G shape block) and 1820 (empty), a "Casa" venue with 0 tracks, tempo `[(158, 100.0)]`, a Main track (id 2) with an attr-4 lane having `default=0` and attrs 2, 3, 5, 6, 7 empty.)

```python
def test_round_trip_is_byte_identical(make_script):
    data = serialize_script(make_script())
    assert serialize_script(parse_script(data)) == data

def test_header_offsets_and_tail_point_at_the_objects(make_script):
    data = serialize_script(make_script())
    off_a, off_b = struct.unpack_from("<II", data, 8)
    assert data[:4] == MAGIC and off_b == off_a + 30
    n = struct.unpack_from("<I", data, off_b + 4)[0]
    obj = struct.unpack_from("<I", data, off_b + 16)[0]
    assert n == 1 and struct.unpack_from("<I", data, obj)[0] == 0x80000001
    assert struct.unpack_from("<I", data, obj + 12)[0] == obj + 4      # self-pointer

def test_inserting_a_key_relocates_objects(make_script):
    s = make_script(); intensity(track(s, 1167)).keys.insert(1, Key(1500, 0x80000000))
    data = serialize_script(s)
    assert parse_script(data) == s and len(data) == len(serialize_script(make_script())) + 17

def test_no_shapes_means_no_tail(make_script):
    s = make_script(); track(s, 1167).shapes = None
    data = serialize_script(s)
    assert struct.unpack_from("<II", data, 8) == (0, 0) and parse_script(data) == s

def test_bad_constant_names_the_offset():
    with pytest.raises(ParseError, match="0x"):
        parse_script(MAGIC + b"\x03\x00\x00\x00" + b"\x00" * 8 + b"\x0d\x00\x00\x00" + b"\xff" * 8)

def test_track_lookup_by_node_ignores_position(make_script):
    s = make_script(); s.venues[0].tracks.reverse()
    assert track(s, 1167).node == 1167 and track(s, 9999) is None
```

Plus `test_real_scripts_round_trip` marked `skipif` unless `NEXTRACK_SOUNDSWITCH_REAL` is set: every `{*}.ssfile` and `SSAutoLoop*.ssfile` in that folder round-trips byte-identically.

- [ ] **Step 2:** Run `uv run pytest tests/test_soundswitch_format.py -v` → FAIL (module missing).
- [ ] **Step 3:** Implement `scripts/soundswitch_format.py` per the Interfaces block (a `_Reader` and `_Writer` like the spike's; one private parse/write function per section).
- [ ] **Step 4:** Run the tests → PASS. Run them once with `NEXTRACK_SOUNDSWITCH_REAL=<snapshot folder>` (the coordinator gives the path) → the real round trip passes for all files.
- [ ] **Step 5:** Commit `Add a SoundSwitch track-script parser and serializer`.

### Task 2: Time helpers and model edit operations

**Files:**
- Modify: `scripts/soundswitch_format.py`
- Create: `tests/test_soundswitch_edit.py`

**Interfaces:**
- Consumes: Task 1 model.
- Produces:
  - `class Grid` built by `grid(script) -> Grid` from `script.tempo`; `Grid.ms(bar: int, beat: float = 1.0) -> int` (bar 1 beat 1 = first anchor), `Grid.bar_at(t: int) -> int`, `Grid.beat_ms(t: int) -> float` (beat length at t). Bars are 4 beats; with several anchors each segment uses its own BPM and bars keep counting across anchors.
  - `level_at(lane: Lane, t: int) -> int` (linear between keys; 0 before the first key; last value after the last key).
  - `covered(track: Track, t: int) -> bool` (t inside one of the track's B spans).
  - `set_intensity(track: Track, start: int, end: int, keys: list[Key]) -> None`: replace keys in `[start, end]` with `keys` (all within the span), insert boundary keys `start-1`/`end+1` carrying the previous levels so outside levels don't change, and make the B spans cover `[start, end]` (merge with overlapping or touching spans).
  - `set_colour(track, start, end, colour: int, colour_end: int | None = None) -> None` (replace colour blocks overlapping the span, trimming partial overlaps; create the Section if absent with `ver=1`).
  - `set_positions(track, start, end, flags: list[PositionFlag], palette: list[tuple[str, int]]) -> None` (F span + D flags; removes G shape blocks overlapping the span; creates sections if absent; palette copied from the script's Main track when the track has none).
  - `set_main(script, start, end, keys: list[Key], colour: int | None = None) -> None` (Main intensity keys and, if given, colour).
  - `materialise_main(script, track: Track, start: int, end: int) -> None`: for the sub-spans of `[start, end]` not covered by the track's B spans, copy Main's intensity keys (with boundary keys at the sub-span edges), colour blocks and position flags/blocks or shape blocks into the track.
  - `check(script) -> list[str]`: invariants (keys sorted by t; B/C/E/F/G each sorted and non-overlapping; F and G disjoint per track; every D flag inside an F span). Empty list = valid.

- [ ] **Step 1: Write the failing tests**, e.g.:

```python
def test_grid_two_anchors():
    g = grid(make_script(tempo=[(158, 100.0), (158 + 4 * 2400, 120.0)]))
    assert g.ms(1) == 158 and g.ms(5) == 158 + 4 * 2400 and g.ms(6) == 158 + 4 * 2400 + 2000
    assert g.bar_at(158 + 4 * 2400 + 2001) == 6

def test_set_intensity_keeps_outside_levels(make_script):
    s = make_script(); t = track(s, 1167); before = level_at(intensity(t), 900)
    set_intensity(t, 1100, 1200, [Key(1100, 0), Key(1200, 0)])
    assert level_at(intensity(t), 900) == before and level_at(intensity(t), 1150) == 0
    assert check(s) == []

def test_set_intensity_merges_blocks(make_script):
    s = make_script(); t = track(s, 1167)
    set_intensity(t, 1900, 3000, [Key(1900, FULL), Key(3000, FULL)])
    assert t.blocks.items == [Span(1000, 3000)]

def test_set_positions_drops_shapes_in_span(make_script):
    s = make_script(); t = track(s, 1167)
    set_positions(t, 0, 10_000, [PositionFlag(500, 3)], s.main.positions.palette)
    assert (t.shapes is None or t.shapes.items == []) and check(s) == []

def test_materialise_copies_main_where_uncovered(make_script):
    s = make_script(); t = track(s, 1820)            # no blocks: follows Main
    materialise_main(s, t, 0, 5000)
    assert [ (b.start, b.end) for b in t.blocks.items ] == [(0, 5000)]
    assert level_at(intensity(t), 2500) == level_at(intensity(s.main), 2500)
```

Plus one test per Review Focus line it owns (span cutting a ramp; multi-anchor grid).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS; also round-trip the edited scripts (`parse_script(serialize_script(s)) == s`).
- [ ] **Step 5:** Commit `Add tempo grid and edit operations to the SoundSwitch model`.

### Task 3: TrackMap and Venues readers

**Files:**
- Modify: `scripts/soundswitch_format.py`
- Create: `tests/test_soundswitch_project.py`
- Modify: `tests/conftest.py` (fixtures `trackmap_bytes(entries)` and `venues_bytes(tree, presets)`)

**Interfaces:**
- Produces:
  - `TrackRef(guid: str, title: str, artist: str, path: str, bpm: int | None, duration_ms: int | None)`; `read_trackmap(data: bytes) -> list[TrackRef]`. Grammar: container header (`MAGIC`, 3, 0, 0, then u32 1, u32 1), then entries to EOF: `u32 kind` (5 for library tracks; 4 seen for SoundSwitch's own demo), `u8 1`, GUID (16 bytes, `bytes_le`), three `(u32 1, string)` fields = title, artist, path (string = u32 char count incl. NUL + UTF-16LE), then `u32 bpm`, `u32 duration_ms` and a 14-byte trailer for kind 5. Any entry the grammar doesn't fit: skip to the next offset where `u32 ∈ {4, 5}`, then `u8 1`, 16 bytes, `u32 1` and a valid string start; record it in a `warnings` list returned via `read_trackmap_with_warnings(data) -> tuple[list[TrackRef], list[str]]`.
  - `VenueNode(id: int, name: str, parent: int | None, look: int | None, colour: int)`; `Preset(name: str, guid: str)`; `VenueInfo(name: str, guid: str, nodes: list[VenueNode])`; `read_venues(data: bytes) -> tuple[list[VenueInfo], list[Preset]]`. Locate and parse like the spike (`find_venues`: `04000000 GUID 01000000 <u32 n>` + UTF-16LE name followed by `00 00 0f 00 00 00`; device tree nodes `03000000 02000000 <id> 01000000 <name>` then either a model string + children (group) or `look, colour` (leaf); position presets after the last venue, located by `02000000 00000000 02000000`, each `(2, n_venue_entries, … , 1, name, colour, GUID, i32 next)`).
  - `Project(folder: Path)` with `.trackmap() -> list[TrackRef]`, `.venues()`, `.script_path(guid) -> Path`, `.resolve(text: str) -> TrackRef` (GUID, GUID prefix ≥ 6 chars, or "Artist — Title" folded like `check_repo.norm`; raises `LookupError` listing candidates when ambiguous or absent).
- [ ] **Step 1: Failing tests:** synthetic TrackMap with two kind-5 entries and one kind-4 entry round into `TrackRef`s; a corrupted entry is skipped with a warning; synthetic venues give nodes `Mover 1` (1167) and `VORLANE VL-1000 RGBW v2` (1818) with child `RGB 01 - VORLANE VL-1000 RGBW v2` (1820, parent 1818) and presets `["Stage Left", "Cake"]`; `Project.resolve` by prefix, by "Artist — Title", ambiguous → `LookupError`. Real-file test (skip unless `NEXTRACK_SOUNDSWITCH_REAL`): ≥ 480 TrackRefs, every GUID 36 chars; venue "DJ Renan" has nodes 1167 and 1936; 10 presets including "Cake".
- [ ] **Steps 2–4:** FAIL → implement → PASS (real-file test run once with the snapshot path).
- [ ] **Step 5:** Commit `Read the SoundSwitch track map and venues`.

### Task 4: `nextrack_lights.py` read commands — `tracks`, `dump`, `analyze`

**Files:**
- Create: `scripts/nextrack_lights.py`
- Create: `tests/test_nextrack_lights.py`
- Modify: `tests/conftest.py` (fixture `make_project(tmp_path)` writing a synthetic project folder: TrackMap with 2 tracks, venues, two scripts)

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: `main(argv: list[str] | None = None) -> int`; global option `--project PATH` (else `NEXTRACK_SOUNDSWITCH_PROJECT`, else exit 2 with "set --project or NEXTRACK_SOUNDSWITCH_PROJECT"). Subcommands:
  - `tracks [--match TEXT]` → one line per track: `GUID8  BPM  M:SS  Artist — Title`.
  - `dump TRACK [--yaml]` → per 8-bar phrase (bars from `Grid`), per fixture name (from venues; `Main` for node 2): `lit` (share of the phrase with level > 1 %), `pulses` (count of rises from < 10 % to > 90 %), colours (hex list), positions (preset names), shapes (kinds). `--yaml` prints the same as YAML; default is a compact text table.
  - `analyze TRACK…` → per track: the `dump` data reduced to the spec's metrics — fixtures overriding Main vs following it, white-with-colour overlap % (W cells lit while any RGB cell of the same Vorlane is lit), position changes per bar, colours used, Main-track intensity range per phrase. Markdown to stdout.
- [ ] **Step 1: Failing tests:** `tracks` lists both synthetic tracks; missing project → exit 2 with the message; `dump` of a script whose Mover 1 pulses 8 times in bars 1–8 reports `pulses: 8` for phrase 1; `analyze` reports 50 % white overlap for a synthetic Vorlane where W is lit half the time the RGB cells are.
- [ ] **Steps 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit `Add nextrack_lights tracks, dump and analyze`.

### Task 5: Rig and choreography model, vocabulary, validator rules

**Files:**
- Create: `scripts/lightshow.py`
- Create: `lightshows/rig.yml`
- Modify: `scripts/check_repo.py` (load `lightshows/rig.yml`, `lightshows/tracks/*.yml`, `lightshows/sets/*.md`; three rules)
- Modify: `scripts/README.md` (rule rows), `lightshows/README.md` (schemas; full rewrite in Task 11)
- Create: `tests/test_lightshow_model.py`; Modify: `tests/test_check_repo.py`

**Interfaces:**
- Produces (in `lightshow`):
  - `LAYERS = ("movers", "matrix", "white", "uv", "strobe", "hue", "haze")`; `MOVER_MOVES = ("hold", "pingpong", "sweep", "blink", "uv")`; `MATRIX_DRAWS = ("solid", "rows-down", "rows-up", "columns", "zigzag", "centre-out", "arrow-up", "fill-up")`; `HUE_STATES = ("dark", "pulse", "bright")`; `RATES` accepted: `"1/16"`, `"1/8"`, `"1/4"`, `"1/2"`, `"<n>bar"`.
  - `Rig(fixtures: dict[str, RigFixture], matrix_rows: list[str], zone_order: str, white_max: float)`; `RigFixture(key: str, kind: str, node: str | None, index: int | None, corner: str | None, extra: dict)`; `load_rig(path: Path) -> Rig`.
  - `Section(bars: tuple[int, int], name: str, intent: str | None, layers: dict[str, object])`; `Choreography(track: str, soundswitch: str, grid: dict, story: str, budget: str | None, base: str, sections: list[Section])`; `load_choreography(path) -> Choreography`.
  - `problems_rig(data: object) -> list[str]`, `problems_choreography(data: object, rig: Rig | None) -> list[str]`, `problems_plan(front: dict, root: Path) -> list[str]` — pure, used by `check_repo`.
- `check_repo` rules (each yields nothing for a file that failed to parse, which is a `parse-error`): `lightshow-rig` (keys `room`, `fixtures`, `matrix`; kinds `mover`, `matrix`, `haze`, `hue-chandelier`; corners `NE`, `SE`, `NW`, `SW`, `centre`; `white_max` in (0, 1]); `lightshow-track` (keys of the spec's schema; `track` resolves to a pool entry with the block tracklist matcher; `soundswitch` is a GUID; sections sorted, non-overlapping, `bars` `[a, b]` with 1 ≤ a ≤ b; layer names in `LAYERS`; each layer `auto`, `off` or a mapping whose `move`/`draw` is in the vocabulary; colours `#RRGGBB`; rates valid); `lightshow-plan` (front matter `set` path exists; `budget` keys in `LAYERS` or `white-accent`).
- [ ] **Step 1: Failing tests** for each rule's passing and failing case (unknown layer, overlapping sections, bad colour, track not in a pool, missing `set` path), and `load_choreography` on `lightshows/tracks/marshmello-x-bastille-happier.yml` gives 15 sections, the first `bars == (1, 8)`.
- [ ] **Steps 2–4:** FAIL → implement → PASS; `uv run scripts/check_repo.py` passes on the repo (add `lightshows/rig.yml` from the spec, adjusted to the real names).
- [ ] **Step 5:** Commit `Add the lightshow rig and choreography schemas and their rules`.

### Task 6: Frame generators (matrix draws, mover moves, white, hue)

**Files:**
- Modify: `scripts/lightshow.py`
- Create: `tests/test_lightshow_frames.py`

**Interfaces:**
- Produces:
  - `rate_ms(rate: str, beat_ms: float) -> float`.
  - `matrix_frames(draw: str, start: int, end: int, step_ms: float, unit: int, mirror: bool) -> list[tuple[int, set[tuple[int, int]]]]`: time of each step and the set of lit `(row, col)` cells (rows 0–6, row 3 = white strip, never lit by a draw unless `with_white`), cols 0–7. Semantics: `columns` col = k mod 8; `rows-down`/`rows-up` over colour rows `[0, 1, 2, 4, 5, 6]`; `fill-up` lit rows accumulate from the bottom, one colour row per step, holding at 6; `centre-out` cols `3-q` and `4+q`, q = k mod 4; `zigzag` one cell per step, snake order over colour rows; `arrow-up` chevron rising one row per step; `solid` all colour cells each step; `mirror` and `unit == 1` flips columns (`7 - col`).
  - `cell_node(rig_unit_nodes: dict, row: int, col: int) -> int` (row-major: rows 0–2 → RGB 01–24, row 3 → W 1–8, rows 4–6 → RGB 25–48).
  - `pulse_keys(times: list[int], decay_ms: float, level: int = FULL) -> list[Key]` (each time: `Key(t, level)`, `Key(t + decay - 1, 0)`, the autoscript's pulse shape).
  - `mover_keys(move: dict, start: int, end: int, beat_ms: float, mover_index: int) -> list[Key]` for `hold` (steady `level`), `pingpong` (lit on even steps for mover 0, odd for mover 1; `faster_from`/`faster_every` switch the step), `blink` (pulse every step), `sweep` (steady 0.85).
  - `hue_keys(state: str, start, end, beat_ms) -> list[Key]` (`dark` 0, `bright` 0.85, `pulse` beat decay).
- [ ] **Step 1: Failing tests** pinning one example per draw (e.g. `fill-up` with 4 steps lights rows {6}, {6,5}, {6,5,4}, {6,5,4,2}; `columns` mirrored on unit 1 starts at col 7; `centre-out` step 0 = cols {3,4}); `pingpong` mover 0 lit on steps 0, 2; mover 1 on 1, 3; `pulse_keys([1000], 300)` == `[Key(1000, FULL), Key(1299, 0)]`; level `0.85` → `int(0.85 * 2**32)`.
- [ ] **Steps 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit `Add matrix and mover frame generators`.

### Task 7: Compiler — choreography → edited script + manual cues

**Files:**
- Modify: `scripts/lightshow.py`
- Create: `tests/test_lightshow_compile.py`

**Interfaces:**
- Consumes: Tasks 2, 3, 5, 6.
- Produces: `ManualCue(bar: int, time_ms: int, fixture: str, what: str)`; `compile_choreography(choreo: Choreography, script: TrackScript, rig: Rig, venues: list[VenueInfo], presets: list[Preset]) -> tuple[TrackScript, list[ManualCue]]` (returns an edited deep copy). Order per section: resolve span via `Grid`; if `hue` is set, `materialise_main` into every rig fixture node whose layer is `auto`/unset for that span, then `set_main`; then each fixture layer: `off` → zero keys; mover moves → `set_intensity` + `set_colour` + `set_positions` (preset names → palette indices; unknown name → `ManualCue`); matrix draws → per-cell keys from `matrix_frames` (+ `pulse_keys` with decay = step) and `set_colour` per cell (colour default per draw as in the spec's example: columns `#FFB347`, fill-up `#FF2D95`, rows-* `#00C8FF`, centre-out `#8A5CFF`, solid `#00C8FF`, zigzag `#FFB347`, arrow-up `#FF2D95`); `white` → W-cell keys scaled by `rig.white_max`; `strobe` → 1/16 pulses; `haze` → fog/fan intensity (also a `ManualCue` "experimental: confirm the machine reacts"); `uv` → `ManualCue`. Nodes are resolved by name from `venues` (the venue that holds them), never by position; a name missing from the venue → `ManualCue` and skip. Finally `assert not check(result)`.
- [ ] **Step 1: Failing tests** on a synthetic script + rig: `movers: off` zeroes 1167/1168 across the span and nothing outside; `hue: dark` on a span where VL cells follow Main gives the cells B blocks with Main's old level and Main level 0; `matrix: {draw: fill-up, rate: 1bar}` over 4 bars lights row 6 cells (RGB 41–48) from bar 1 and row 2 (RGB 17–24) only from bar 4; `white: {accent: ["2.1"]}` gives W keys at bar 2 beat 1 with level `≤ white_max`; `uv: on` returns one `ManualCue`; unknown preset name → `ManualCue`; the Happier YAML compiles against a synthetic script containing its node ids without exceptions and with `check == []`.
- [ ] **Steps 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit `Compile choreographies into SoundSwitch script edits`.

### Task 8: `render` — the room simulator

**Files:**
- Create: `scripts/lightshow_sim.html` (template, inline JS/CSS, a single `/*__DATA__*/null` placeholder)
- Modify: `scripts/nextrack_lights.py`
- Modify: `tests/test_nextrack_lights.py`

**Interfaces:**
- Produces: `render TRACK [--choreo FILE] -o OUT.html`; `sim_data(script, venues, presets, rig, choreo=None) -> dict` with keys `before` (per fixture: intensity keys as `[t, level_fraction]`, B spans, colour blocks, position flags as names, shape blocks; `main` likewise), `after` (same shape, from the compiled script, or `null`), `sections` (name, bars, intent, ms span), `grid` (anchors), `rig` (fixture key → corner, kind, node ids). The template draws the room from `rig` (movers NE/SE as discs with a beam to an approximate preset target, Vorlanes NW/SW as 8×7 grids, Hue chandelier of 7 lamps fed by `main`, haze tint), a timeline with sections, play/seek, an mp3 file picker that drives the clock, and two rooms (before/after) when `after` is present. Port the look and behaviour of the prototype the coordinator supplies (`sim2`), but feed it from `sim_data` (both sides from real model data: after = compiled script).
- [ ] **Step 1: Failing tests:** `render` writes a file containing `<html`, no `http://`/`https://` URLs, and a JSON blob whose `before` has keys for node names `Mover 1` and `Main`; with `--choreo` the blob has non-null `after` and 15 sections for the Happier YAML on a synthetic script.
- [ ] **Steps 2–4:** FAIL → implement → PASS. Open the output once on a real track (coordinator) to eyeball it.
- [ ] **Step 5:** Commit `Render a room simulator for a track`.

### Task 9: `compile` and `apply` with the write-safety model

**Files:**
- Modify: `scripts/nextrack_lights.py`
- Modify: `tests/test_nextrack_lights.py`

**Interfaces:**
- Produces: `compile CHOREO -o OUT.ssfile` (writes only `OUT`; prints manual cues); `apply CHOREO [--apply] [--accept-resize]`: dry-run prints a summary diff (fixtures touched, keys/blocks added/removed per fixture, size before/after) and the manual cues; with `--apply`: (1) refuse if `soundswitch_running() -> bool` is true (`tasklist.exe` output contains `SoundSwitch.exe`; false when `tasklist.exe` is absent), (2) parse → serialize must equal the input bytes, else refuse, (3) compile, serialize, re-parse; untouched tracks must equal the originals, (4) refuse a size change without `--accept-resize`, (5) back up to `<project parent>/nextrack-backups/<YYYYmmdd-HHMMSS>/<GUID>.ssfile`, write `<GUID>.ssfile.tmp` in the project and `os.replace` it, (6) print the restore command (`cp <backup> <target>`). Exit codes: 0 ok, 1 refused, 2 usage.
- [ ] **Step 1: Failing tests** (with `soundswitch_running` monkeypatched): dry-run writes nothing (project bytes unchanged); `--apply` with SoundSwitch running → exit 1, unchanged; a script that does not round-trip (monkeypatch `serialize_script` to append a byte) → exit 1; size change without `--accept-resize` → exit 1; success → backup equals the old bytes, target parses and has the edits, no `.tmp` left.
- [ ] **Steps 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit `Add compile and a guarded apply for choreographies`.

### Task 10: The Happier example end to end + the show plan file

**Files:**
- Modify: `lightshows/tracks/marshmello-x-bastille-happier.yml` (only if Task 5's schema needs it)
- Create: `lightshows/sets/2026-10-31-halloween-em-casa.md` (show plan: colour story and effect budget per block of tonight's set, pt-BR prose)
- Test: `tests/test_lightshow_compile.py` (the real-file part)

- [ ] **Step 1:** A real-file test (skip unless `NEXTRACK_SOUNDSWITCH_REAL`): compile the Happier YAML against the real Happier script → `check == []`, round-trip of the result, Mover 1 level 0 in bars 1–8, Main level 0 in bar 68, at most the manual cues for `uv` and `haze`.
- [ ] **Step 2:** Run it with the snapshot path → PASS; the coordinator writes the compiled copy to the scratchpad and renders before/after for the morning report.
- [ ] **Step 3:** Write the show plan; `uv run scripts/check_repo.py` passes (`lightshow-plan`).
- [ ] **Step 4:** Commit `Add the Happier choreography example and a show plan for the Halloween set`.

### Task 11: Documentation

**Files:**
- Create: `docs/soundswitch/file-format.md`, `docs/soundswitch/experiments.md`, `docs/soundswitch/autoscript-analysis.md`
- Modify: `lightshows/README.md` (full rewrite), `docs/rig.md` (section "Lights and room"), `scripts/README.md` (`nextrack_lights.py` section), `README.md` (one line pointing at lightshows if the README lists folders)

- [ ] **Step 1:** Write the docs from the coordinator's findings (supplied in the task prompt), in English; `lightshows/README.md` documents `rig.yml`, the choreography schema, the vocabulary with an 8×7 text diagram per draw, the show plan, and the workflow (skill → render → compile → apply).
- [ ] **Step 2:** `uv run scripts/check_repo.py` (links resolve) and `uv run pytest` pass.
- [ ] **Step 3:** Commit `Document the SoundSwitch format, experiments and lightshow workflow`.

### Task 12: The `lightshow` project skill

**Files:**
- Create: `.claude/skills/lightshow/SKILL.md`

- [ ] **Step 1:** Write the skill per the spec's "Skill" section: frontmatter `name: lightshow`, a description that triggers on "coreografia", "roteiro de luz", "lightshow", "SoundSwitch" for a track or block; steps with the exact commands (`uv run scripts/nextrack_lights.py tracks|dump|analyze|render|compile|apply`), the budget discipline (read `lightshows/sets/*.md` and sibling choreographies; tally effects already spent), lyrics only for themes (never stored), pt-BR proposal phrase by phrase, approval before writing the YAML, `apply --apply` only on explicit go with SoundSwitch closed.
- [ ] **Step 2:** Pressure-test it once with a subagent on a synthetic project (superpowers:writing-skills): the subagent must stop before `--apply` and must not exceed the budget.
- [ ] **Step 3:** Commit `Add the lightshow skill`.

### Task 13: Whole-branch verification

- [ ] `uv run pytest` and `uv run scripts/check_repo.py` pass; real-file tests pass with `NEXTRACK_SOUNDSWITCH_REAL` set to the snapshot.
- [ ] Final whole-branch review (superpowers:requesting-code-review), fixes, and the morning report.
