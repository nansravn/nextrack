# Show Language Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A declarative show language (a folder of YAML per set) that a deterministic compiler
turns into today's per-track choreographies, with gestures and show rules as Python registries,
validator rules that keep the generated files in sync, and a CLI (`build`, `report`, `vocab`)
written for AI agents; the Hï Ibiza set ported to it.

**Architecture:** Three pure libraries in `scripts/`: `show_gestures.py` (gesture registry),
`show_language.py` (model, anchors, looks, compiler, emitter; imports `show_gestures` and
`lightshow`), and `show_rules.py` (rule registry and `evaluate_show`, the one entry point; imports
`show_language`). `check_repo.py` loads show folders and wraps the results into three rules.
`nextrack_show.py` is the CLI on top of `check_repo.load_repo`. Nothing in `lightshow.py` or
`nextrack_lights.py` changes.

**Tech Stack:** Python ≥ 3.12, PyYAML, pytest; run everything with `uv run`.

**Spec:** [docs/superpowers/specs/2026-11-06-show-language-design.md](../specs/2026-11-06-show-language-design.md).
Read it before any task: it holds the schema, the semantics and the decision ledger. This plan
holds the module boundaries, names, signatures and tests.

## Global Constraints

- No new dependency. `uv sync` once per worktree; tests with `uv run pytest`, validator with
  `uv run scripts/check_repo.py`.
- `show_gestures.py`, `show_language.py` and `show_rules.py` never import `check_repo` at
  module level (`check_repo` imports them). The set-matching function comes in through
  `ShowInputs.same_track`.
- No command of this plan writes outside `lightshows/tracks/` of `--repo` or the `--out` folder.
  Nothing touches SoundSwitch, rekordbox or audio.
- Ids (palette names, look names, cue names, moment names) match `[a-z0-9]+(-[a-z0-9]+)*`.
- Code, docstrings, docs and commit messages are English; `story`, `intent` and `budget` prose
  in show files is pt-BR.
- Every finding is `path:line: rule-id: message`. `path` is repo-relative, or the folder as
  given for a show outside the repo. `rule-id` is `show-source`, `show-rules` or
  `show-compiled`. Messages name the value and what would fix it.
- Bad content never raises. Every problem becomes a finding, and a library bug in a gesture
  (sections that do not cover the span) becomes a finding too.
- The loader's `__line__` keys never reach compiled layers or emitted files.
- Layer words: YAML 1.1 reads unquoted `off`/`on` as `False`/`True`. A top-level layer value
  `False` means `"off"` and `True` means `"on"`, as in `lightshow._layer_value`. Booleans
  inside a layer mapping (`mirror: true`) stay booleans.
- Commit subjects are imperative English sentences (`Add …`), no `feat:` prefix, ending with
  the two attribution lines:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01TJp8YhHnGhN5eQ9PfRzAsC`.
- Before every commit, `git diff --cached | grep -nE "/mnt/|Users/|/tmp/|scratchpad|AppData|OneDrive"`,
  extended with the owner's user names (the controller gives them), must print nothing: no
  machine paths, user names or scratch paths in the repo.
- Definition of done for every task: `uv run pytest` and `uv run scripts/check_repo.py` both
  pass (report their last lines).

## Review Focus

- **Unquoted `off` in show files** (`movers: off` in a look, a `with`, a sequence step). Expected:
  the same as `"off"` everywhere: merge, rules (`total-dark`), emission. Test in Task 1
  (`test_expand_look_reads_unquoted_off`) and Task 5 (`test_total_dark_sees_unquoted_off`).
- **Anchors written loosely**: `"drop.2-1"`, `" drop.2 - 1 "`, `"Drop.2"`, `"b"`, `16.0`, `true`.
  Expected: spaces optional; kinds lowercase and cues uppercase, with a message that shows the
  accepted forms; a float or bool is a finding, not a crash. Test in Task 1
  (`test_anchor_loose_forms`).
- **Prose with YAML specials** in `story`, `intent`, `budget`: colons, `#`, quotes `"` and `“ ”`,
  a leading dash, double spaces, accents. Expected: the emitted file parses back to the same
  strings. Test in Task 4 (`test_emit_round_trips_tricky_prose`).
- **A broken input upstream** (the set file missing, a block link that does not resolve, a
  track's map missing or invalid, a track file that does not parse). Expected: one
  `show-source` finding per cause, no traceback, and no `show-rules` or `show-compiled` finding
  for that show. Test in Task 6 (`test_broken_inputs_report_once`).
- **Editing a generated file by hand** (or deleting it). Expected: `show-compiled` names the
  file and the command to run. `build` restores it, and `build --check` exits 1 before that.
  Tests in Task 6 (`test_show_compiled_flags_a_hand_edit`) and Task 7
  (`test_build_check_reports_drift`).

---

### Task 1: Anchors, schema checks and looks (`show_language.py`, part 1)

**Files:**
- Create: `scripts/show_language.py`
- Create: `tests/showdata.py` (shared synthetic data for every show test)
- Test: `tests/test_show_language_model.py`

**Interfaces:**
- Consumes: `lightshow.LAYERS`, `lightshow.COLOUR_RE`; `tests/mapdata.good_map`.
- Produces (in `show_language`):
  - constants `SHOW_VERSION = 1`, `SECTION_KINDS = ("intro", "groove", "break", "build", "drop", "outro")`,
    `ACCENTS = ("white", "strobe", "strobe-roll")`, `ROLES = ("arrival",)`, `ID_RE`.
  - `clean(value: object) -> object`: a deep copy without `__line__` keys.
  - `layer_word(value: object) -> object`: `False → "off"`, `True → "on"`, anything else unchanged.
  - `resolve_anchor(value: object, map_data: dict, *, until: bool = False) -> tuple[int | None, str | None]`:
    `(bar, None)` or `(None, problem)`. With `until=True` the bar may also be `bars + 1`.
  - `problems_show(data: object) -> list[tuple[int, str]]`: schema of `show.yml` alone (keys,
    types, ids, `#RRGGBB` palette values, look layer names, `bridge`/`handover` shapes). Each
    item is `(line, message)`, with line 0 when unknown.
  - `problems_track_file(data: object) -> list[tuple[int, str]]`: schema of one track file
    (keys, cue keys, exactly one of `look`/`gesture`, `role` in `ROLES`, `accents` in
    `ACCENTS`, ids, `bridge` only `false`).
  - `merge_layers(base: dict, override: dict) -> dict`.
  - `flatten_looks(looks: dict) -> tuple[dict[str, dict], list[tuple[str, str]]]`: every look
    with its `extends` chain merged in, plus `(look name, problem)` for an unknown base or a
    cycle.
  - `expand_look(ref: object, with_: object, looks: dict[str, dict]) -> tuple[dict | None, list[str]]`:
    `ref` is a look name or a mapping of layers. The result has `layer_word` applied to every
    top-level layer.
  - `resolve_colours(layers: dict, palette: dict[str, str]) -> tuple[dict, list[str]]`.
- Produces (in `tests/showdata.py`):
  - `show_map(bars: int = 32, sections: list[tuple[int, int, str]] | None = None, hot_cues: dict | None = None, track: str = "Pedro Sampaio — Dançarina", **overrides) -> dict`:
    a valid map (built on `mapdata.good_map`). The default sections are
    `[(1, 8, "intro"), (9, 16, "drop"), (17, 20, "break"), (21, 32, "drop")]` and the
    default hot cues `{"A": "1.1", "B": "5.1", "G": "25.1"}`. `drops` is derived from the drop
    sections.
  - `PALETTE = {"azul": "#0A2CFF", "vermelho": "#FF0A2A"}`.

- [ ] **Step 1: Write the failing tests** in `tests/test_show_language_model.py`:

```python
def test_anchor_terms():
    m = show_map()
    assert resolve_anchor(16, m) == (16, None)
    assert resolve_anchor("B", m) == (5, None)
    assert resolve_anchor("drop.2", m) == (21, None)
    assert resolve_anchor("drop.1.end", m) == (16, None)
    assert resolve_anchor("break.1 - 1", m) == (16, None)
    assert resolve_anchor("end", m) == (32, None)
    assert resolve_anchor("end + 1", m, until=True) == (33, None)

def test_anchor_problems_name_what_the_map_has():
    m = show_map()
    assert resolve_anchor("drop.3", m)[1] == "drop.3: the map has 2 drop sections (9, 21)"
    assert resolve_anchor("H", m)[1] == "H: the map has no hot cue H (it has A, B, G)"
    assert "outside 1-32" in resolve_anchor("end + 1", m)[1]
    off_beat = show_map(hot_cues={"A": "1.1", "B": "5.3"})
    assert "not on a bar's first beat" in resolve_anchor("B", off_beat)[1]

def test_anchor_loose_forms():
    m = show_map()
    assert resolve_anchor("drop.2-1", m) == (20, None)
    assert resolve_anchor(" drop.2 - 1 ", m) == (20, None)
    for bad in ("Drop.2", "b", 16.0, True, None, "drop", "drop.0"):
        bar, problem = resolve_anchor(bad, m)
        assert bar is None and "anchor" in problem   # the message lists the accepted forms

def test_merge_layers_merges_mappings_and_null_removes():
    base = {"movers": {"move": "pingpong", "positions": ["Up", "Down"]}, "hue": "dark"}
    over = {"movers": {"positions": None, "position": "Up"}, "hue": {"state": "pulse"}}
    assert merge_layers(base, over) == {"movers": {"move": "pingpong", "position": "Up"},
                                        "hue": {"state": "pulse"}}

def test_flatten_looks_extends_and_cycles():
    flat, problems = flatten_looks({"breu": {"movers": "off", "hue": "dark"},
                                    "breu-inicial": {"extends": "breu"},
                                    "a": {"extends": "b"}, "b": {"extends": "a"}})
    assert flat["breu-inicial"] == {"movers": "off", "hue": "dark"}
    assert ("a", "extends cycle: a -> b -> a") in problems

def test_expand_look_reads_unquoted_off():
    layers, problems = expand_look({"movers": False, "matrix": {"draw": "solid", "mirror": True}}, None, {})
    assert problems == [] and layers == {"movers": "off", "matrix": {"draw": "solid", "mirror": True}}

def test_expand_look_unknown_name_suggests():
    _, problems = expand_look("pulso-vermelhoo", None, {"pulso-vermelho": {}})
    assert problems == ["look 'pulso-vermelhoo' is not defined; did you mean 'pulso-vermelho'?"]

def test_resolve_colours_palette_and_hex():
    layers, problems = resolve_colours({"matrix": {"colour": "azul"}, "hue": {"state": "pulse", "colour": "#B0001E"}}, PALETTE)
    assert layers["matrix"]["colour"] == "#0A2CFF" and layers["hue"]["colour"] == "#B0001E"
    assert resolve_colours({"movers": {"colour": "roxo"}}, PALETTE)[1] == [
        "colour 'roxo' is not in the palette (azul, vermelho) nor #RRGGBB"]

def test_problems_show_and_track_file():
    # a minimal valid show.yml and track file give no problems; then one bad value each:
    # palette value "#12345" -> problem; look with layer "laser" -> problem;
    # cue with both look and gesture -> problem; accents: [flash] -> problem; cue name "Drop 1" -> problem
    ...
```

The last test's body is the implementer's. It must assert one problem per bad value, and
`[]` for the valid files given in the comment. Every message names the key and the bad value.

- [ ] **Step 2: Run** `uv run pytest tests/test_show_language_model.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** the Interfaces above in `scripts/show_language.py`. The anchor is
  one regular expression (spec, "Anchors"); `drop.i` counts sections of kind `drop`. Messages:
  exactly the strings asserted above. The "did you mean" comes from `difflib.get_close_matches`
  (cutoff 0.6). Without a close match, the message lists the defined names.
- [ ] **Step 4: Run** the tests. Expected: PASS. Then `uv run pytest` and `uv run scripts/check_repo.py`.
- [ ] **Step 5: Commit** `Add anchors, schema checks and looks of the show language`.

---

### Task 2: Gesture registry with `sequence` and `spiral` (`show_gestures.py`)

**Files:**
- Create: `scripts/show_gestures.py`
- Test: `tests/test_show_gestures.py`

**Interfaces:**
- Consumes: `lightshow.RATE_RE`.
- Produces:

```python
@dataclass
class GestureContext:
    start: int          # first bar the gesture fills
    end: int            # last bar (inclusive)
    cue_name: str
    intent: str | None
    map: dict
    expand_look: Callable[[object, object], tuple[dict | None, list[str]]]  # (look ref, with) -> layers, problems

@dataclass
class GestureSection:
    bars: tuple[int, int]
    name: str
    intent: str | None
    layers: dict[str, object]       # colours may still be palette names
    look: str | None = None         # the look name this section came from, for the provenance

@dataclass
class Gesture:
    name: str
    doc: str                        # the function's docstring
    params: dict[str, str]          # parameter -> one-line description (vocab prints it)
    example: dict                   # a valid `with` for the generic test, colours as #RRGGBB
    example_bars: int               # the span the example fills
    fn: Callable[[GestureContext, dict], tuple[list[GestureSection], list[str]]]

GESTURES: dict[str, Gesture]
def gesture(name: str, *, params: dict[str, str], example: dict, example_bars: int): ...  # decorator
def run_gesture(name: str, ctx: GestureContext, params: object) -> tuple[list[GestureSection], list[str]]
```

`run_gesture` reports an unknown gesture (`unknown gesture 'x'; gestures: sequence, spiral`)
and non-mapping params. It also checks the result: sections in order, contiguous, covering
exactly `[start, end]`. Otherwise the problem is `gesture 'x' returned sections that do not cover
bars a-b` (a library bug, surfaced as a finding). With problems, the sections list is `[]`.
Every problem a gesture returns starts with `<gesture>: `. An unknown parameter is
`<gesture>: unknown parameter 'p'; parameters: …`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_spiral_makes_one_section_per_step():
    ctx = GestureContext(41, 47, "espiral", "gira", show_map(64), lambda r, w: ({}, []))
    params = {"bars": [2, 2, 2, 1], "rates": ["1/2", "1/4", "1/8", "1/16"],
              "colours": ["azul", "violeta", "violeta", "vermelho"],
              "aims": [["Crossed Over", "Up"], ["Crossed Over", "Up"], "Dance Floor Centre", "Dance Floor Centre"]}
    sections, problems = run_gesture("spiral", ctx, params)
    assert problems == []
    assert [(s.bars, s.name) for s in sections] == [((41, 42), "espiral-1-2"), ((43, 44), "espiral-1-4"),
                                                    ((45, 46), "espiral-1-8"), ((47, 47), "espiral-1-16")]
    first = sections[0].layers
    assert first["movers"] == {"move": "pingpong", "every": "1/2", "colour": "azul", "positions": ["Crossed Over", "Up"]}
    assert first["matrix"] == {"draw": "columns", "rate": "1/2", "colour": "azul", "pingpong": True}
    assert first["hue"] == "dark"
    assert sections[2].layers["movers"]["position"] == "Dance Floor Centre"
    assert all(s.intent == "gira" for s in sections)

def test_spiral_bars_must_fill_the_span():
    ctx = GestureContext(41, 47, "espiral", None, show_map(64), lambda r, w: ({}, []))
    _, problems = run_gesture("spiral", ctx, {"bars": [2, 2, 2], "rates": ["1/2"] * 3, "colours": ["azul"] * 3, "aims": ["Up"] * 3})
    assert problems == ["spiral: bars add up to 6, the cue spans 7 bars (41-47)"]

def test_spiral_lists_must_have_the_same_length(): ...    # one problem naming the four lengths
def test_spiral_rejects_a_bad_rate(): ...                 # "spiral: rates[1] '1/3' is not a rate (1/16, 1/8, 1/4, 1/2, <n>bar)"

def test_sequence_expands_looks_and_reports_them():
    looks = {"breu": {"movers": "off", "matrix": "off", "hue": "dark"}}
    ctx = GestureContext(1, 4, "corte", None, show_map(), lambda r, w: expand_look(r, w, looks))
    sections, problems = run_gesture("sequence", ctx, {"steps": [{"bars": 1, "look": "breu"},
                                                                 {"bars": 3, "look": {"hue": "pulse"}, "name": "volta"}]})
    assert problems == []
    assert [(s.bars, s.name, s.look) for s in sections] == [((1, 1), "corte-1", "breu"), ((2, 4), "volta", None)]

def test_sequence_step_problems_are_prefixed(): ...       # "sequence: step 2: look 'x' is not defined; ..."
def test_unknown_gesture_lists_the_registry(): ...
def test_a_gesture_that_misses_its_span_is_reported(): ...  # register a throwaway broken gesture in the test, then remove it

def test_every_gesture_documents_itself():
    for g in GESTURES.values():
        assert g.doc.strip() and g.params and g.example_bars >= 1
        ctx = GestureContext(1, g.example_bars, "exemplo", None, show_map(max(g.example_bars, 32)),
                             lambda r, w: expand_look(r, w, {}))
        sections, problems = run_gesture(g.name, ctx, g.example)
        assert problems == [] and sections
```

(Task 3 adds the check that every example also compiles to a valid choreography.)

- [ ] **Step 2: Run** `uv run pytest tests/test_show_gestures.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `show_gestures.py`. A rate's slug for names is the rate with `/`
  replaced by `-` (`1/16` → `1-16`, `2bar` → `2bar`). `spiral`'s params description and docstring
  follow the spec ("Gestures"). `sequence` steps are `{bars, look, with?, name?}`. A step's
  look name is reported in `GestureSection.look` when `look` is a string.
- [ ] **Step 4: Run** the tests, `uv run pytest`, `uv run scripts/check_repo.py`. Expected: all pass.
- [ ] **Step 5: Commit** `Add the gesture registry with sequence and spiral`.

---

### Task 3: The compiler (`show_language.compile_show`)

**Files:**
- Modify: `scripts/show_language.py`
- Modify: `tests/showdata.py` (source and inputs builders)
- Test: `tests/test_show_language_compile.py`

**Interfaces:**
- Consumes: Task 1 functions; `show_gestures.run_gesture`, `GestureContext`;
  `lightshow.problems_choreography(data, None)`; `musical_map.slug`.
- Produces (in `show_language`):

```python
@dataclass
class Provenance:
    kind: str                 # "cue" | "bridge" | "handover"
    track: str                # Artist — Title of the choreography that holds the section
    look: str | None
    gesture: str | None
    role: str | None          # "arrival" only on the first section of its cue
    moment: str | None
    path: str                 # file a finding points at (for a bridge: the outgoing track's file)
    line: int                 # the cue's or handover's line there

@dataclass
class CompiledSection:
    bars: tuple[int, int]
    name: str
    intent: str | None
    layers: dict[str, object]  # final IR values: colours #RRGGBB, anchors resolved, words normalised
    origin: Provenance

@dataclass
class CompiledTrack:
    track: str
    slug: str
    path: str                  # the track file
    map: dict
    choreography: dict         # track, soundswitch, grid {bpm, downbeat}, story, [budget], base, sections
    sections: list[CompiledSection]

@dataclass
class CompiledShow:
    show_id: str
    folder: str                # e.g. "lightshows/shows/hi-ibiza-pulso"
    data: dict                 # clean(show.yml)
    tracks: list[CompiledTrack]  # set order
    decisions: list[str]       # what the compiler inferred, one line each (bridges, default ends)

@dataclass
class ShowFinding:
    path: str
    line: int
    rule: str                  # "show-source" | "show-rules" | "show-compiled"
    message: str

@dataclass
class ShowSource:
    show_id: str
    folder: str
    show: object               # parsed show.yml (with __line__)
    track_files: dict[str, object]   # file name ("<slug>.yml") -> parsed YAML
    parse_failed: bool = False

@dataclass
class ShowInputs:
    maps: dict[str, dict]              # slug -> valid map
    set_tracks: list[tuple[str, str]] | None   # (artist, title) in set order
    set_problem: str | None            # why set_tracks is None
    same_track: Callable[[str, str, str, str], bool]

def compile_show(source: ShowSource, inputs: ShowInputs) -> tuple[CompiledShow | None, list[ShowFinding]]
```

`compile_show` returns `(None, findings)` when there is any finding (all `show-source`), else
`(show, [])`. It follows the spec's "Compiling" steps 1–7. The steps leave three choices, fixed
here:
- The track-file ↔ set matching. A track file's `track` is split on ` — `. Its file name must
  be `slug(track) + ".yml"`, and it must match exactly one set track through `same_track`. Each
  set track needs exactly one file.
- Accents: `white` → `white: {accent: ["<at>.1"]}`, `strobe` → `strobe: {hit: ["<at>.1"]}`, both
  on the cue's first section. `strobe-roll` → `strobe: {roll: [a, b]}` over that section. An
  accent on a section whose layers already set that layer is a finding.
- `decisions` lines (pt-BR not needed; English): `"<Title>: bridge a-b copies the handover of <Title> (look <name>|inline)"` and
  `"<Title>: cue '<name>' runs to bar n (the handover|the map's end)"` for a last cue without `until`.

- Produces (in `tests/showdata.py`): `source(show: dict, tracks: dict[str, dict], folder: str = "lightshows/shows/teste") -> ShowSource`
  (`tracks` maps file name → data), `inputs(maps: dict[str, dict], set_tracks: list[tuple[str, str]]) -> ShowInputs`
  (with `check_repo.same_track`), and `two_track_show() -> tuple[ShowSource, ShowInputs]`: a
  two-track show, a valid and complete example (palette, two looks, a bridge, a handover, a
  `spiral` call, an arrival per track, accents) on two `show_map`s, for the tracks
  `Pedro Sampaio — Dançarina` and `Chiclete com Banana — Voa Voa (Ao Vivo)` (the second map
  with its own `soundswitch` GUID), in the order of the mini repo's block `alpha-festa`.
  Tasks 3, 5, 6 and 7 build on it.

- [ ] **Step 1: Write the failing tests:**

```python
def test_cue_stack_spans():                 # cues at 9 and drop.2 with a handover at G: sections [9,20], [21,24], handover [25,32]
def test_until_leaves_a_gap():              # cue at 9 until 13, next at 17: sections [9,12] and [17,...]; nothing for 13-16
def test_cues_must_increase(): ...          # "cue 'b' at 9 does not come after cue 'a' at 9" at the second cue's line
def test_bridge_copies_the_previous_handover_without_accents():
    show, findings = compile_show(*two_track_show())
    assert findings == []
    second = show.tracks[1]
    bridge, handover = second.sections[0], show.tracks[0].sections[-1]
    assert bridge.name == "ponte" and bridge.bars[0] == 5            # the second map's B
    assert bridge.layers == {k: v for k, v in handover.layers.items() if k not in ("white", "strobe")}
    assert bridge.origin.kind == "bridge" and bridge.origin.path == show.tracks[0].path
    assert bridge.origin.line == handover.origin.line and bridge.origin.moment == handover.origin.moment
def test_first_cue_at_b_leaves_no_room_for_the_bridge(): ...
def test_no_b_with_a_handover_before_is_a_finding(): ...    # message mentions "nextrack_map.py cues" and "bridge: false"
def test_bridge_false_skips_the_bridge(): ...
def test_g_without_handover_before_a_bridged_track(): ...
def test_gesture_sections_get_the_cue_provenance():         # spiral sections: gesture "spiral", moment of the cue, role only on the first
def test_accents_land_on_the_first_section(): ...           # "21.1" in white.accent and strobe.hit
def test_palette_and_faster_from_are_resolved(): ...        # faster_from: "drop.2 - 2" -> 19
def test_choreography_comes_from_the_map():
    show, _ = compile_show(*two_track_show())
    c = show.tracks[0].choreography
    assert c["soundswitch"] == show.tracks[0].map["soundswitch"] and c["base"] == "autoscript"
    assert c["grid"] == {"bpm": 120, "downbeat": show.tracks[0].map["grid"]["downbeat"]}
    assert lightshow.problems_choreography(c, None) == []
def test_lightshow_problems_point_at_the_cue(): ...         # a look with draw "spiral" -> show-source finding at that cue's line
def test_track_files_against_the_set(): ...                 # missing file, extra file, wrong file name, track twice in the set
def test_missing_or_unreadable_inputs(): ...                # map missing for a track; set_tracks None -> one finding with set_problem
def test_decisions_name_bridges_and_default_ends(): ...
def test_every_gesture_example_compiles():                  # each GESTURES example as the only cue of a one-track show -> no findings
```

- [ ] **Step 2: Run** `uv run pytest tests/test_show_language_compile.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `compile_show` and the dataclasses. A finding's line is the cue's
  (or handover's) `__line__`. A problem in `show.yml` points at its line in
  `<folder>/show.yml`. Gesture defaults (`gesture_defaults[name]`) are merged under the cue's
  `with` (the cue wins) before `run_gesture`. `grid.bpm` is the map's bpm as an int when it is
  whole (`128.0` → `128`).
- [ ] **Step 4: Run** the tests, `uv run pytest`, `uv run scripts/check_repo.py`. Expected: all pass.
- [ ] **Step 5: Commit** `Compile a show into per-track choreographies`.

---

### Task 4: The emitter and the ownership header

**Files:**
- Modify: `scripts/show_language.py`
- Test: `tests/test_show_language_emit.py`

**Interfaces:**
- Consumes: `CompiledTrack.choreography` (Task 3).
- Produces:
  - `HEADER_RE = re.compile(r"# Generated by scripts/nextrack_show\.py build from (?P<folder>.+)/\.$")`
  - `emit_choreography(choreo: dict, folder: str) -> str`: the file text, exactly as the spec's
    "The emitted file" shows. The first two lines are
    `# Generated by scripts/nextrack_show.py build from <folder>/.` and
    `# Do not edit by hand: change the show and run the build again.`
  - `owner_of(text: str) -> str | None`: the folder named by the first line, or None.

- [ ] **Step 1: Write the failing tests:**

```python
def test_emit_matches_the_layout():
    # a choreography with two sections -> exact expected text (write it out in the test):
    # track double-quoted; grid {bpm: 128, downbeat: "0:00.297"}; story as `>-` folded at 96 columns,
    # 2-space indent; base: autoscript; sections as "  - bars: [a, b]" / "    name: x" /
    # '    intent: "…"' / layers in LAYERS order, flow style, keys in MOVER_KEYS / MATRIX_KEYS order,
    # rates, colours and "off" quoted; a blank line between sections; `sections: []` when empty
def test_emit_round_trips_tricky_prose():
    for text in ['Ponte: a mesma luz', 'o "coração" e o # da sala', '“aspas”', '- começa com traço',
                 'dois  espaços', 'acentuação ç ã é', 'x' * 300]:
        choreo = _choreo(story=text, intent=text)
        parsed = yaml.safe_load(emit_choreography(choreo, "lightshows/shows/teste"))
        assert parsed["story"] == text and parsed["sections"][0]["intent"] == text
def test_emit_round_trips_the_compiled_show():
    show, _ = compile_show(*two_track_show())
    for t in show.tracks:
        assert yaml.safe_load(emit_choreography(t.choreography, show.folder)) == t.choreography
def test_emit_is_deterministic_and_valid():           # same input twice -> same text; lightshow.problems_choreography of the parse == []
def test_owner_of():
    assert owner_of(emit_choreography(_choreo(), "lightshows/shows/teste")) == "lightshows/shows/teste"
    assert owner_of("# Coreografia de luz — rascunho v1\ntrack: x\n") is None
```

- [ ] **Step 2: Run** `uv run pytest tests/test_show_language_emit.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** A plain scalar is allowed only for strings matching
  `[A-Za-z][A-Za-z0-9 ._-]*` that are not YAML 1.1 special words (`y n yes no on off true false
  null ~`, any case). Everything else is double-quoted with `\\` and `\"` escaped. `story` and
  `budget` are `>-` blocks when the folded text parses back equal; otherwise they are
  double-quoted. Numbers: ints as ints, floats with `repr`.
- [ ] **Step 4: Run** the tests, `uv run pytest`, `uv run scripts/check_repo.py`. Expected: all pass.
- [ ] **Step 5: Commit** `Emit generated choreographies with an ownership header`.

---

### Task 5: Show rules and `evaluate_show` (`show_rules.py`)

**Files:**
- Create: `scripts/show_rules.py`
- Test: `tests/test_show_rules.py`

**Interfaces:**
- Consumes: Task 3 types and `compile_show`; `show_gestures.GESTURES`.
- Produces:

```python
@dataclass
class Occurrence:
    key: str
    track: str
    bar: int
    origin: Provenance

@dataclass
class ShowRule:
    name: str
    doc: str
    params: str                                    # one line: the parameter shape, for vocab
    check: Callable[[object, dict], list[str]]     # (params, clean show.yml) -> problems
    fn: Callable[[CompiledShow, object], list[ShowFinding]]

RULES: dict[str, ShowRule]
EFFECT_KEYS = ("white-accent", "white-flash", "strobe", "uv")
def show_rule(name: str, *, params: str, check: Callable[[object, dict], list[str]]): ...  # decorator
def occurrences(show: CompiledShow, key: str) -> list[Occurrence]
def rule_param_findings(source: ShowSource) -> list[ShowFinding]      # show-source: unknown rule id, bad params
def run_rules(show: CompiledShow) -> list[ShowFinding]               # show-rules, in rule then track order
def evaluate_show(source: ShowSource, inputs: ShowInputs) -> tuple[CompiledShow | None, list[ShowFinding], list[ShowFinding]]
```

`evaluate_show` returns `(compiled, source_findings, rule_findings)`. It compiles, adds
`rule_param_findings` to the source findings, and runs the rules only when there are no source
findings (otherwise `compiled` is None and rule findings are `[]`). Occurrences follow the
spec's table exactly; bridges never count. Each `show-rules` message starts with the rule id
(`budget: …`) and points at the occurrence's `origin.path`/`origin.line`. A `budget` key must
be a look in `show.yml`, a registered gesture or one of `EFFECT_KEYS`.

- [ ] **Step 1: Write the failing tests**: one passing and one failing case per rule, plus:

```python
def test_budget_max_lists_every_occurrence(): ...     # breu used 3x with max 2 -> exactly one finding, at the third occurrence,
                                                      # "budget: breu is used 3 times, max 2: Dançarina 9, Dançarina 17, Voa Voa 5"
def test_budget_moments_and_from(): ...               # strobe outside its moments; strobe in a track before `from`
def test_budget_unknown_key_is_a_source_finding(): ...
def test_sequence_step_look_counts_and_passes_total_dark(): ...   # sequence with a breu step: counted for breu, allowed by only: [breu]
def test_bridges_never_count(): ...                   # a handover with look X followed by its bridge -> X counted once
def test_total_dark_sees_unquoted_off(): ...          # look {movers: False, matrix: False, hue: dark} not in only -> finding
def test_arrivals_one_per_track_and_draws_differ(): ...
def test_movers_aim(): ...
def test_matrix_not_cloned_honours_moments_through_bridges(): ...  # a peak handover in moment `final` copied by the bridge -> no finding
def test_exclusive(): ...
def test_unknown_rule_id_and_bad_params(): ...        # rules: {budjet: true} -> "unknown rule 'budjet'; rules: arrivals, budget, ..."
def test_every_rule_documents_itself(): ...           # doc and params non-empty for every RULES entry
def test_evaluate_show_skips_rules_on_source_findings(): ...
```

- [ ] **Step 2: Run** `uv run pytest tests/test_show_rules.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the six rules of the spec's table (`budget`, `total-dark`,
  `arrivals`, `movers-aim`, `matrix-not-cloned`, `exclusive`) with their `check`s. A track is
  named by its title (the part after ` — `) in messages.
- [ ] **Step 4: Run** the tests, `uv run pytest`, `uv run scripts/check_repo.py`. Expected: all pass.
- [ ] **Step 5: Commit** `Add show rules and the show evaluation entry point`.

---

### Task 6: Validator rules (`check_repo.py`)

**Files:**
- Modify: `scripts/check_repo.py`
- Modify: `scripts/README.md` (three rows in the rule table, after `lightshow-plan`)
- Test: `tests/test_check_repo_shows.py`

**Interfaces:**
- Consumes: `show_language.ShowSource`, `ShowInputs`, `emit_choreography`, `owner_of`;
  `show_rules.evaluate_show`; `musical_map.problems_map`, `musical_map.slug`.
- Produces (in `check_repo`):
  - `Repo.shows: list[show_language.ShowSource]` (default empty), loaded from
    `lightshows/shows/*/show.yml` and every other `*.yml` in that folder, sorted. A file that
    does not parse is a `parse-error`, and its show gets `parse_failed=True`.
  - `load_show_folder(root: Path, folder: Path, errors: list[Finding]) -> show_language.ShowSource | None`.
    `folder` may be outside `root`; then the label is the folder as given. `None` when there
    is no `show.yml`.
  - `show_inputs(repo: Repo, source: ShowSource) -> ShowInputs`: the set → blocks → tracklist
    order (`set_block_ids`, `tracklist_entries`), the valid maps by slug (`problems_map(data) == []`),
    and `same_track`.
  - `show_results(repo: Repo) -> list[tuple[ShowSource, CompiledShow | None, list[ShowFinding], list[ShowFinding]]]`,
    computed once per `Repo` and cached on it. Shows with `parse_failed` are left out: their
    `parse-error` is enough.
  - rules `show-source`, `show-rules`, `show-compiled` (spec, "Validator rules").
    `show-compiled` reads the text of `lightshows/tracks/*.yml` from disk. A drift finding is
    `lightshows/tracks/<slug>.yml:0: show-compiled: differs from what lightshows/shows/<id> compiles to; run uv run scripts/nextrack_show.py build <id>`.

- [ ] **Step 1: Write the failing tests** with `mini_repo`. A helper `_put_show(repo)` writes
  `sets/teste.md` (linking `../blocks/alpha-festa.md`), the two maps of `two_track_show`
  (with `musical_map.dump_map`), the show folder `lightshows/shows/teste/` (with `yaml.safe_dump`)
  and the generated choreographies (with `emit_choreography`):

```python
def test_a_valid_show_has_no_findings(mini_repo):           # all three rules empty; the whole check clean
def test_show_source_reports_a_bad_anchor_at_its_line(mini_repo): ...
def test_show_rules_report_a_broken_budget(mini_repo): ...
def test_show_compiled_flags_a_hand_edit(mini_repo): ...     # edit one generated file -> drift finding with the build command
def test_show_compiled_flags_a_missing_file(mini_repo): ...
def test_show_compiled_flags_an_orphan_generated_file(mini_repo): ...   # header names lightshows/shows/gone
def test_two_shows_owning_one_track(mini_repo): ...
def test_broken_inputs_report_once(mini_repo):
    # for each of: set file missing; block link broken; one map deleted; a track file with invalid YAML:
    # exactly one finding about that cause (show-source, or parse-error for the YAML),
    # and no show-rules / show-compiled finding for the show
def test_rules_table_lists_the_show_rules(): ...             # covered by test_tooling once the rows exist; assert here too
```

- [ ] **Step 2: Run** `uv run pytest tests/test_check_repo_shows.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement**, then add the three rows to `scripts/README.md`'s rule table, one
  line each, as the spec's table says.
- [ ] **Step 4: Run** the tests, `uv run pytest` (including `tests/test_tooling.py`) and
  `uv run scripts/check_repo.py` (the real repo has no show yet: still `ok`). Expected: all pass.
- [ ] **Step 5: Commit** `Validate shows and the choreographies they generate`.

---

### Task 7: The CLI (`nextrack_show.py`: `build`, `report`, `vocab`)

**Files:**
- Create: `scripts/nextrack_show.py`
- Test: `tests/test_nextrack_show.py`

**Interfaces:**
- Consumes: `check_repo.load_repo`, `load_show_folder`, `show_inputs`; `show_rules.evaluate_show`,
  `occurrences`, `RULES`; `show_gestures.GESTURES`; `show_language.emit_choreography`, `owner_of`,
  `SECTION_KINDS`; `lightshow` vocabulary constants.
- Produces:
  - `main(argv: list[str] | None = None) -> int` with subcommands `build SHOW [--check] [--out DIR] [--adopt]`,
    `report SHOW`, `vocab [SHOW]`, each with `--repo PATH` (default: the repo containing the script).
    `SHOW` is a folder path, or the id of a folder under `<repo>/lightshows/shows/`. Anything else
    exits 2 with a usage message.
  - `render_report(show: CompiledShow, findings: list[ShowFinding]) -> str`
  - `render_vocab(source: ShowSource | None) -> str`

Behaviour (spec, "The CLI"):
- Findings print as `path:line: rule: message`, sorted, then `N finding(s)` or nothing.
- `build`: a `show-source` finding → nothing written, exit 1. Otherwise, per track, `wrote <path>`
  or `unchanged <path>`; rule findings printed; exit 1 when there are any, else 0.
  Without `--out`: an existing target with no header is refused (`refused <path>: not generated by a show; use --adopt to take it over`)
  unless `--adopt`. A target owned by another show is always refused. Any refusal means
  nothing is written. With `--out DIR`: no ownership check; `DIR` is created.
- `build --check`: writes nothing. It prints `would change <path>` for each difference and exits
  1 when there is one (or any finding).
- `report` and `vocab`: exit 0, print the text. `report` on a show with source findings prints
  the findings and exits 1.

- [ ] **Step 1: Write the failing tests** (the mini repo with `_put_show` from Task 6, moved
  into `tests/showdata.py` as `put_show(repo)`):

```python
def test_build_writes_and_is_idempotent(mini_repo, capsys): ...   # 1st run "wrote" x2, 2nd run "unchanged" x2, exit 0
def test_build_check_reports_drift(mini_repo, capsys): ...        # hand-edit a generated file -> exit 1, "would change", file untouched
def test_build_refuses_hand_written_files_without_adopt(mini_repo, capsys): ...  # and --adopt takes them over
def test_build_refuses_another_shows_file(mini_repo, capsys): ...
def test_build_writes_nothing_on_a_source_finding(mini_repo, capsys): ...
def test_build_writes_despite_rule_findings(mini_repo, capsys): ...  # exit 1, files written
def test_build_out_writes_a_variant_elsewhere(mini_repo, tmp_path, capsys): ...  # a copied show folder outside the repo, --out tmp_path/out
def test_unknown_show_is_a_usage_error(mini_repo, capsys): ...    # exit 2
def test_report_has_a_line_per_section_and_the_tally(mini_repo, capsys):
    # every compiled section's "a-b name" appears; the source column ("bridge", "handover", "gesture spiral", "look <name>");
    # colours by palette name; the music under a section ("drop 21-32"); the budget table; the arrivals; the decisions
def test_vocab_lists_anchors_gestures_rules_and_the_shows_looks(mini_repo, capsys): ...
```

- [ ] **Step 2: Run** `uv run pytest tests/test_nextrack_show.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** The report's layout is the implementer's call (about one line per
  section; spec, "`report`"). Reverse palette lookup shows a colour's name, or its hex when it is
  not in the palette. The music column lists the map sections the span overlaps, clipped
  (`break 113-132`), plus `drop +22.0 dB` when the section starts on a drop.
- [ ] **Step 4: Run** the tests, `uv run pytest`, `uv run scripts/check_repo.py`. Expected: all pass.
- [ ] **Step 5: Commit** `Add the show CLI: build, report and vocab`.

---

### Task 8: Docs for agents

**Files:**
- Create: `lightshows/shows/README.md`
- Modify: `lightshows/README.md` (table row for `shows/`; a note under "Choreography" that a file
  starting with the generated header comes from a show and is never edited by hand)
- Modify: `scripts/README.md` (a `## nextrack_show.py` section after `nextrack_map.py`: setup,
  commands, output, exit status, the build's ownership rules, `--out` for variants)
- Modify: `CLAUDE.md` (Commands table row `uv run scripts/nextrack_show.py <cmd>`; an
  invariant bullet; a "Show tool" bullet list like the map tool's; two change checklists: **Add
  a gesture** and **Add a show rule**, per the spec's "Docs")
- Modify: `.claude/skills/lightshow/SKILL.md` (in "1. Resolve the track": if the track file
  exists under `lightshows/shows/*/`, the choreography is generated; amend the show's track file
  and run `build`; never edit the generated file. Approval and apply rules unchanged.)
- Test: `tests/test_show_docs.py`

**Interfaces:**
- Consumes: `show_gestures.GESTURES`, `show_rules.RULES`.

- [ ] **Step 1: Write the failing test:**

```python
def test_the_show_readme_names_every_gesture_and_rule():
    text = (ROOT / "lightshows/shows/README.md").read_text(encoding="utf-8")
    missing = [n for n in [*GESTURES, *RULES] if f"`{n}`" not in text]
    assert not missing
```

- [ ] **Step 2: Run** `uv run pytest tests/test_show_docs.py -v`. Expected: FAIL.
- [ ] **Step 3: Write the docs.** `lightshows/shows/README.md` is the agent's manual. It covers
  the folder, `show.yml`, the track file, cues, anchors (with the grammar), layers, looks,
  bridges and handovers, gestures (a table: name, parameters, what it does), rules (a table:
  name, parameters, finding when), provenance and occurrences, and the loop: edit → `build` →
  findings → `report` → `render` → repeat, plus variants with `--out`. Its examples must be
  valid against the real implementation. Copy them from passing tests or from `vocab`
  output; do not write them from memory. Prose English (the repo's docs language).
- [ ] **Step 4: Run** `uv run pytest` and `uv run scripts/check_repo.py` (`links-resolve` covers
  the new links). Expected: all pass.
- [ ] **Step 5: Commit** `Document the show language for agents`.

---

### Task 9: Port the Hï Ibiza set

**Files:**
- Create: `lightshows/shows/hi-ibiza-pulso/show.yml` and 15 track files (one per track of
  `blocks/hi-ibiza-pulso.md`, named like its map)
- Modify (regenerated): the 15 `lightshows/tracks/<slug>.yml` of the set (not Happier)

Work from the docs (`lightshows/shows/README.md`, `vocab`) as an agent would. If the docs are
not enough, fix the docs in this task and say what was missing.

- [ ] **Step 1: Snapshot** today's 15 files into a scratch folder outside the repo (the
  controller names it). Write a comparison script there (never in the repo). For each slug, it compares
  `yaml.safe_load` of the old and the new file on `track`, `soundswitch`, `grid`, `story`,
  `budget`, `base` and `sections`, with top-level layer values normalised by `layer_word`.
  It prints every difference.
- [ ] **Step 2: Write `show.yml`**: `set: sets/hi-ibiza-pulso.md`, `plan: lightshows/sets/hi-ibiza-pulso.md`, a short pt-BR
  `story` from the plan's "A história da noite", the plan's palette (six colours), looks for the
  five handover looks (`respiracao-azul`, `aceleracao`, `pulso-vermelho`, `pico-pick-up`,
  `pico-cant-decide`) plus `breu`, `breu-inicial` and `contraluz`, `gesture_defaults.spiral`
  (the plan's rates, colours and aims), `bridge` and `handover` with today's names and intents
  (`ponte`, `entrega`), and the rules of the spec's "The port of Hï Ibiza".
- [ ] **Step 3: Write the 15 track files** from today's choreographies. Each `story` and
  `budget` is copied verbatim. Cues are anchored on the map where the music names the bar
  (`drop.n`, `break.n`, `G`); absolute bars stay where the plan picked a bar inside a section.
  Each arrival from the plan's table gets `role: arrival`, each plan moment's cue gets its
  `moment` (`abertura`, `yamore`, `virada`, `pick-up`, `cant-decide`, `dirty-cash`, `final`),
  and the three spirals become `gesture: spiral` with their `bars` (Move overrides `colours`).
- [ ] **Step 4: Build** with `uv run scripts/nextrack_show.py build hi-ibiza-pulso --adopt`.
  Iterate on the show files until there are no findings and the comparison script prints no
  difference. If a plan rule fails on today's data, apply the spec's rule (smallest data fix
  that satisfies the plan) and list each such change in the commit message body.
- [ ] **Step 5: Verify:** `uv run scripts/nextrack_show.py build hi-ibiza-pulso --check` exits 0,
  `uv run scripts/check_repo.py` is `ok`, `uv run pytest` passes, and
  `uv run scripts/nextrack_show.py report hi-ibiza-pulso` shows the budget tally: breu 5,
  spiral 3, contraluz 3, white-accent 5, white-flash 1, strobe 5, uv 0.
- [ ] **Step 6: Commit** `Port the Hi Ibiza set to the show language`. The body says the 15
  choreographies are now generated, gives the comparison result, and lists any data fix.

---

## After the tasks

A whole-branch review (superpowers:requesting-code-review). Then a final `uv run pytest` and
`uv run scripts/check_repo.py`, and the PR description drafted for the owner (not pushed).
