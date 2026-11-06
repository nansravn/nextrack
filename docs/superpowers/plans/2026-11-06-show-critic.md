# Show Critic (Show Language 1.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the show language the critic's senses. This means advice beside rules, agile
bridges, the room with its aim catalogue, the set clock and screen time, light against music,
voices, peaks, hit checks and a 1/16-beat zoom. All of it is deterministic, text-only, and
computed from the show, the maps, the set and the rig.

**Architecture:** Three new pure modules in `scripts/`:
- `show_room.py`: `lightshows/room.yml`, its schema and aim resolution.
- `show_views.py`: the clock, levels, voices, the night summary, peaks, hit checks and strips.
- `show_zoom.py`: the zoom text.

Existing modules gain small, local changes:
- `show_language.py`: `bridge.bars`, `advice` schema, aim resolution, `Provenance.aims`.
- `show_rules.py`: advice evaluation and the `bridges` rule.
- `check_repo.py`: `room.yml` loading, rule `lightshow-room`, tempos for the clock.
- `nextrack_show.py`: report sections, `zoom`, `vocab` aims, advice in `build`.

`lightshow.py` and `nextrack_lights.py` stay untouched; the zoom calls their generators.

**Tech Stack:** Python ≥ 3.12, PyYAML, pytest; `uv run` for everything.

**Spec:** [docs/superpowers/specs/2026-11-06-show-critic-design.md](../specs/2026-11-06-show-critic-design.md).
Read it before any task. It holds the formulas (light level, music level, windows, aims) and
the decision ledger. It builds on the [show language spec](../specs/2026-11-06-show-language-design.md).

## Global Constraints

- No new dependency. Run `uv run pytest` and `uv run scripts/check_repo.py`.
- `show_room.py`, `show_views.py`, `show_zoom.py`, `show_language.py` and `show_rules.py`
  never import `check_repo` at module level.
- `lightshow.py`, `nextrack_lights.py` and `musical_map.py` are not modified.
- The 15 generated Hï Ibiza choreographies do not change in any task. At the end of every task,
  `uv run scripts/nextrack_show.py build hi-ibiza-pulso --check` exits 0.
- Bad content never raises; every problem is a finding, at `path:line`, with the value and
  what would fix it.
- Advice findings use the rule id `show-advice`. They never come out of `check_repo.py`, and
  never change `build`'s exit status.
- Every derived number (light level, music level, minutes, shares) comes from a function whose
  docstring states the spec's formula.
- Code, docstrings, docs and commit messages are in English. Prose in `room.yml` (`figure`)
  and in the plan files is in pt-BR.
- Commit subjects are imperative English with no `feat:` prefix. Every commit message ends
  with the two attribution lines the controller gives.
- Before every commit, grep the staged diff for machine paths, user names and scratch paths
  (the controller gives the pattern). It must print nothing.
- A task is done when `uv run pytest` and `uv run scripts/check_repo.py` pass. Report their
  last lines.

## Review Focus

- **The first and the last track** (no `B`, or no `G`). Expected: the first leg runs from bar
  1, and the last runs to `set_timeline.last_bar`. Neither raises, and the clock starts at
  0:00. Test in Task 4: `test_clock_first_and_last_tracks`.
- **A tempo change inside a track** (Move ramps 122 → 125; a map with two anchors). Expected:
  the clock ramps the played tempo, and the zoom places steps on the map's anchors. Tests:
  `test_clock_ramps_the_played_tempo` (Task 4) and `test_zoom_steps_follow_the_anchors`
  (Task 6).
- **`auto` layers.** Expected: the light level is `~` and the zoom lane is `~`, never a
  guessed number. Tests: `test_light_level_unknown_when_auto` (Task 4) and
  `test_zoom_marks_auto` (Task 6).
- **Aim chains.** A pending aim may fall back on another pending aim, and a chain may loop.
  Expected: the first configured aim along the chain is used, and a cycle is one
  `lightshow-room` finding, not a hang. Tests: `test_fallback_chain_and_cycle` (Task 2) and
  `test_pending_aim_compiles_to_its_fallback` (Task 3).
- **A kebab-case typo in a preset field** (`position: apic`). Expected: a `show-source`
  finding, with a did-you-mean, and never a silent raw preset. Test in Task 3:
  `test_unknown_aim_id_is_a_finding`.

---

### Task 1: Advice, `bridge.bars` and the `bridges` rule

**Files:**
- Modify: `scripts/show_language.py` (the `show.yml` schema: `advice` and `bridge.bars`; the
  compile semantics of `bridge.bars`)
- Modify: `scripts/show_rules.py` (advice evaluation, rule `bridges`, `evaluate_show`)
- Modify: `scripts/check_repo.py` (`show_results` takes the new return shape and drops advice)
- Modify: `scripts/nextrack_show.py` (`build` prints advice; `report` gets an `advice` section)
- Test: `tests/test_show_rules.py`, `tests/test_show_language_compile.py`,
  `tests/test_nextrack_show.py`, `tests/test_check_repo_shows.py`

**Interfaces:**
- Produces:
  - `show_rules.ADVICE = "show-advice"`.
  - `show_rules.evaluate_show(source, inputs) -> tuple[CompiledShow | None, list[ShowFinding], list[ShowFinding], list[ShowFinding]]`:
    the compiled show, source findings, rule findings and advice findings. Update all 13
    call sites (`grep -rn "evaluate_show(" scripts tests`).
  - `show_rules.run_rules(show, key: str = "rules") -> list[ShowFinding]`. With
    `key="advice"`, it returns findings whose rule is `ADVICE`.
  - `rule_param_findings(source)` checks both `rules` and `advice`. Messages are prefixed
    `rules.<id>:` or `advice.<id>:`.
  - Rule `bridges`, params `{max: int 1..32}`.
  - `bridge.bars`: an int from 1 to 32 in the show.yml `bridge` mapping.
  - `nextrack_show.render_report(show, findings, advice)`: one new parameter. Task 5 adds
    more.

- [ ] **Step 1: Write the failing tests**

```python
def test_advice_runs_rules_without_failing():           # advice: {budget: {breu: {max: 0}}} -> one ADVICE finding, rule findings []
def test_advice_parameters_are_checked():               # advice: {bridgez: {}} -> show-source "advice.bridgez"... unknown rule
def test_bridges_rule_measures_bridges_and_handovers(): # two_track_show with a 12-bar bridge, rules {bridges: {max: 8}}:
                                                        # one finding at the handover's line in the outgoing file, naming both lengths and tracks
def test_bridge_bars_cuts_bridge_and_handover():        # bridge.bars 4: bridge [B, B+3], handover [G, G+3]
def test_bridge_bars_first_cue_too_late():              # first cue after B+bars -> show-source "the bridge ends at bar N (bridge.bars 4); start a cue at or before bar N+1"
def test_bridge_bars_handover_until_too_late():         # explicit handover until > G+bars -> show-source at the handover
def test_bridge_bars_bounds():                          # 0 and 33 are schema problems
def test_check_repo_ignores_advice(mini_repo):          # put_show + advice that fires -> check(root) == []
def test_build_prints_advice_and_keeps_exit_status(mini_repo, capsys):  # exit 0, "1 advice" printed
def test_report_lists_advice(mini_repo, capsys): ...
```

- [ ] **Step 2: Run them.** `uv run pytest tests/test_show_rules.py tests/test_show_language_compile.py -k "advice or bridge" -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - **Advice:** reuses `RULES` and their `check`. The finding format is that of `show-rules`,
    with rule `show-advice`.
  - **`bridge.bars`** follows spec §2:
    - the incoming bridge is at most `bars` bars from B;
    - the default handover `until` is `G + bars`;
    - a first cue after `B + bars`, or a handover `until` past `G + bars`, is a `show-source`
      finding.
  - **`bridges`** checks every compiled section with `origin.kind` `bridge` or `handover`.
    Its finding points at `origin.path`/`origin.line` (the handover's line for both kinds).
- [ ] **Step 4: Run** the full suite, `check_repo`, and `build hi-ibiza-pulso --check` (exit 0). Expected: all pass.
- [ ] **Step 5: Commit** `Add advice and agile bridges to the show language`.

---

### Task 2: The room and its aim catalogue (`show_room.py`, `lightshow-room`, `room.yml`)

**Files:**
- Create: `scripts/show_room.py`
- Create: `lightshows/room.yml`: the nominal room and the full catalogue of spec §8 (19
  aims; ring points from the spec's rule; `figure` in pt-BR; `assumed: true`).
- Modify: `scripts/check_repo.py`: load `lightshows/room.yml` into `Repo.room` (optional,
  like the rig); add rule `lightshow-room`; `show_inputs` passes the room when it is valid.
- Modify: `scripts/README.md` (the `lightshow-room` row)
- Modify: `scripts/show_language.py`: `ShowInputs` gains `room: "show_room.Room | None" = None`
  (Task 3 uses it).
- Test: `tests/test_show_room.py`, `tests/test_check_repo_room.py`

**Interfaces:**
- Produces, in `show_room`:

```python
@dataclass
class Aim:
    id: str
    figure: str
    preset: str
    status: str                       # "configured" | "pending"
    fallback: str | None
    targets: dict[str, tuple[float, float, float]]   # rig mover key -> point

@dataclass
class Room:
    size: tuple[float, float, float]
    assumed: bool
    fixtures: dict[str, tuple[float, float, float]]
    booth: tuple[float, float, float]
    aims: dict[str, Aim]

def problems_room(data: object, rig_fixtures: dict[str, str] | None) -> list[tuple[int, str]]
    # rig_fixtures: rig key -> kind (None when the rig is missing or invalid: skip cross-checks)
def load_room(data: dict) -> Room                        # run problems_room first
def resolve_aim(room: Room, aim_id: str) -> tuple[str | None, list[str], str | None]
    # (preset, chain of aim ids walked, problem): the first configured aim's preset along the fallback chain
def preset_aims(room: Room) -> dict[str, str]            # preset -> aim id, only presets used by exactly one configured aim
```

- [ ] **Step 1: Write the failing tests**

```python
def test_the_repo_room_is_valid():          # problems_room(load lightshows/room.yml, real rig) == [] and 19 aims, 7 configured
def test_room_schema_problems(): ...        # missing key, point outside size, unknown rig key, rig fixture without a place,
                                            # status other than configured|pending, fallback on a configured aim, missing fallback on a pending one
def test_fallback_chain_and_cycle():        # a pending -> b pending -> c configured resolves to c's preset with chain [a, b, c];
                                            # a -> b -> a is one problem naming the cycle
def test_ring_points_follow_the_rule():     # anel-1 ne target == [2.5, 4.0, 2.2] and se == ring point 5 [2.5, 0.0, 2.2]; anel-3 ne == [5.0, 2.0, 2.2]
def test_preset_aims_reverse_map(): ...     # "Up" -> "coluna"; a preset used by two configured aims is left out
def test_lightshow_room_rule(mini_repo): ...  # passing (no room.yml: no finding; a valid one: no finding) and failing cases
```

- [ ] **Step 2: Run them.** `uv run pytest tests/test_show_room.py tests/test_check_repo_room.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - Write the data file from spec §8 (sizes, fixture places, booth, the 19 aims with the
    targets table and the ring rule).
  - The rule follows CLAUDE.md's checklist: one function, the README row, and tests for
    passing and failing. It reads no node ids, so it does not depend on `graph_ok`.
- [ ] **Step 4: Run** the full suite, `check_repo` (must stay `ok`) and `build --check`. Expected: all pass.
- [ ] **Step 5: Commit** `Add the room and its aim catalogue`.

---

### Task 3: Aims in the compiler and in `vocab`

**Files:**
- Modify: `scripts/show_language.py`:
  - `Provenance` gains `aims: tuple[str, ...] = ()`;
  - after gestures expand, resolve aim ids in movers `position` and `positions`, using
    `inputs.room`.
- Modify: `scripts/nextrack_show.py`: `render_vocab` lists the aims. Configured aims come
  first; then pending ones under "presets to create in SoundSwitch", with figure, targets
  and `(geometria presumida)` while assumed.
- Test: `tests/test_show_language_compile.py`, `tests/test_nextrack_show.py`

**Interfaces:**
- Consumes: `show_room.resolve_aim`, `Room.aims`.
- Produces: `CompiledSection.origin.aims`, the aim ids a section's movers named, in order.
  Compiled `position`/`positions` hold preset names only.

- [ ] **Step 1: Write the failing tests**

```python
def test_aim_id_compiles_to_its_preset():          # position: coluna -> "Up"; origin.aims == ("coluna",)
def test_pending_aim_compiles_to_its_fallback():   # positions: [apice, cruzado] -> ["Up", "Crossed Over"]; decisions mention the fallback
def test_aim_ids_work_inside_gestures():           # spiral aims: [coluna, cruzado, centro-da-pista, centro-da-pista] -> presets in the sections
def test_unknown_aim_id_is_a_finding():            # position: apic -> show-source "position 'apic' is not an aim of lightshows/room.yml; did you mean 'apice'?"
def test_aim_id_without_room_is_a_finding():       # inputs.room None + position: coluna -> finding naming lightshows/room.yml
def test_raw_presets_still_compile():              # position: Dance Floor Centre unchanged, origin.aims == ()
def test_vocab_lists_presets_to_create(mini_repo, capsys): ...
```

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - A value is an aim id when it matches the id pattern (`ID_RE`).
  - Any other value is a raw preset.
  - A decision line is added for each fallback used:
    `"<Title>: aim 'apice' is pending; bar a-b uses 'coluna' (Up)"`.
- [ ] **Step 4: Run** the full suite, `check_repo` and `build --check` (Hï Ibiza uses raw presets, so it is unchanged). Expected: all pass.
- [ ] **Step 5: Commit** `Resolve aims in the show compiler`.

---

### Task 4: The views library (`show_views.py`)

**Files:**
- Create: `scripts/show_views.py`
- Modify: `scripts/set_timeline.py`: rename `_seconds` to a public `seconds` and update its
  callers (no behaviour change).
- Modify: `scripts/check_repo.py`: add `show_tempos(repo, source) -> dict[str, tuple[float, float]]`,
  the played tempo per show track from the set's block tracklists (`set_timeline.block_tempos`
  matched with `same_track`).
- Test: `tests/test_show_views.py`

**Interfaces:**
- Consumes: `CompiledShow`, `show_room.Room | None`, `set_timeline.last_bar`, `set_timeline.seconds`.
- Produces:

```python
def light_level(layers: dict) -> int | None          # spec §4 table; None when movers, matrix or hue is auto/unset
def music_level(map_data: dict, bar: int) -> int     # max of kick, bass, other bar levels
def voices(map_data: dict, first: int, last: int) -> dict[str, int]   # {"kick", "bass", "vocals", "perc", "other"} -> max level

@dataclass
class TrackClock:
    index: int
    leg: tuple[int, int]            # [first, last] played bars (B..G-1; first track from 1; last to last_bar)
    sounding: tuple[int, int]       # [first, last compiled bar]
    start_s: float                  # set clock at the leg's first bar
    tempo: tuple[float, float]

@dataclass
class ShowClock:
    tracks: list[TrackClock]
    def at(self, track_index: int, bar: int) -> float      # seconds on the set clock at the start of `bar` (also past G)

def build_clock(show: CompiledShow, tempos: dict[str, tuple[float, float]]) -> ShowClock
def night_summary(show: CompiledShow, clock: ShowClock, room: "Room | None") -> dict
    # keys: looks, colours {movers|matrix|hue: {name: s}}, aims, zones {movers|matrix|hue: s}, centre_dark_s,
    #       total_dark {s, count}, events {white-accent, strobe, uv: count, ...}, pending_aims [(aim, fallback)], total_s
def peaks(show: CompiledShow, clock: ShowClock) -> list[dict]       # spec §4 peak rows
def hit_checks(show: CompiledShow, clock: ShowClock) -> list[dict]  # spec §6 rows
def strips(track: CompiledTrack, clock: TrackClock) -> tuple[str, str]   # music and light, one char per leg bar
def clock_text(seconds: float) -> str                               # "m:ss" (h:mm:ss past an hour)
```

- [ ] **Step 1: Write the failing tests.** Use synthetic shows (`tests/showdata.py`), not the
  real repo.

```python
def test_light_level_table():                     # one case per row of spec §4 with the exact expected digit
def test_light_level_unknown_when_auto(): ...
def test_music_level_and_voices(): ...
def test_clock_first_and_last_tracks():           # first track from bar 1 at 0:00; next starts at the first's G; last runs to last_bar
def test_clock_ramps_the_played_tempo():          # tempo (120, 132) over the leg: seconds == set_timeline.seconds(...)
def test_clock_past_g_for_handover_events(): ...
def test_summary_counts_states_over_legs():       # a bridge counts in the incoming leg, the handover after G does not
def test_summary_counts_events_over_sounding_windows():   # an accent on a handover at G is counted; counts == budget occurrences
def test_summary_splits_cycling_aims_evenly(): ...
def test_peaks_include_drops_during_the_mix(): ...
def test_hit_checks_report_voices_in_a_dark_bar_before(): ...
def test_strips_wrap_nothing_and_use_tilde_for_unknown(): ...
```

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** the spec's formulas exactly, each stated in its function's
  docstring. Sounding window events take the outgoing track's tempo past `G`, which is what
  `ShowClock.at` does.
- [ ] **Step 4: Run** the full suite, `check_repo` and `build --check`. Expected: all pass.
- [ ] **Step 5: Commit** `Add the critic's views: clock, levels, voices, peaks`.

---

### Task 5: The report shows the views

**Files:**
- Modify: `scripts/nextrack_show.py`. `render_report(show, findings, advice, clock, room)`
  prints, in this order: the night summary, the tracks (header with `enters` and `arrival`,
  the two strips, section lines starting with the clock and with voices after `music:`), the
  peak table, the hit checks, budget, arrivals, advice, decided by the compiler, findings.
  Section lines name aims by id (reverse map for raw presets). `report` computes the clock
  from `check_repo.show_tempos`.
- Test: `tests/test_nextrack_show.py`

- [ ] **Step 1: Write the failing tests** on the mini repo (`put_show`):

```python
def test_report_has_the_night_summary(mini_repo, capsys):   # "night" block with looks, colours, aims, zones, centre dark, events
def test_report_track_header_has_clock_and_arrival(mini_repo, capsys): ...
def test_report_section_line_has_clock_and_voices(mini_repo, capsys):   # assert one exact line
def test_report_has_strips_peaks_and_hits(mini_repo, capsys): ...
def test_report_names_aims(mini_repo, capsys): ...
```

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - Keep about one line per section.
  - The summary says that the light level is an index, and points at the manual for its
    formula.
  - Pending aims used are listed with their fallbacks.
- [ ] **Step 4: Run** the full suite, `check_repo` and `build --check`. Then run
  `uv run scripts/nextrack_show.py report hi-ibiza-pulso | head -60` and paste it in the
  report: TOO COOL must enter at 30:47 and the virada must land near 32:20. Expected: all pass.
- [ ] **Step 5: Commit** `Show the clock, contrast and peaks in the report`.

---

### Task 6: The zoom (`show_zoom.py`, `nextrack_show.py zoom`)

**Files:**
- Create: `scripts/show_zoom.py`
- Modify: `scripts/nextrack_show.py`: the subcommand `zoom SHOW TARGET [ANCHOR] [--before N] [--after N] [--frames B.b,...]`.
- Test: `tests/test_show_zoom.py`, `tests/test_nextrack_show.py`

**Interfaces:**
- Consumes:
  - `lightshow.mover_keys`, `lightshow.matrix_frames`, `lightshow.hue_keys`;
  - `soundswitch_format.Grid` (built from the map's `grid.anchors`, as `set_timeline._grid` does);
  - `show_views.clock_text` and `ShowClock`.
- Produces: `render_zoom(show: CompiledShow, track_index: int, bar: int, before: int, after: int, frames: list[str], clock: ShowClock | None) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
def test_zoom_music_lanes_come_from_the_map():     # kick/perc/bass/vocals rows equal the map's step strings for the window
def test_zoom_movers_pingpong_alternate():          # pingpong 1/8: NE lit on steps 0-1, SE on 2-3, ...
def test_zoom_matrix_pingpong_alternates_units(): ...
def test_zoom_accents_and_strobe_steps():           # white accent at 49.1 marks 4 steps; strobe hit marks 4 steps
def test_zoom_marks_auto(): ...
def test_zoom_shows_uv_sections():                  # `uv: on` and `movers: {move: uv}` sections fill the uv lane with "u"
def test_zoom_steps_follow_the_anchors():           # a map with two tempo anchors: step times from Grid.ms
def test_zoom_frames_draw_both_vorlanes(): ...
def test_zoom_cli_moment_and_anchor(mini_repo, capsys): ...   # a moment name; a track + anchor; an unknown target -> exit 2 listing moments
```

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** the layout of spec §7.
  - Sample each envelope at each step's start, taking the value in force between keys.
  - Mirror the compiler's use of `matrix_frames`: the unit, `mirror`, and the step parity of
    `pingpong`. Read `lightshow._compile_matrix`, but do not modify it.
  - Glyphs: the colour legend letter, upper or lower case by level, `.` when dark, `~` for
    auto.
- [ ] **Step 4: Run** the full suite, `check_repo` and `build --check`. Then run
  `uv run scripts/nextrack_show.py zoom hi-ibiza-pulso virada` and paste it in the report.
  Expected: all pass.
- [ ] **Step 5: Commit** `Add the zoom to the show tool`.

---

### Task 7: Hï Ibiza's bridge goal, UV design hooks and the docs

**Files:**
- Modify: `lightshows/shows/hi-ibiza-pulso/show.yml`: `advice: {bridges: {max: 16}}`.
- Modify: `lightshows/sets/hi-ibiza-pulso.md`: one rule in "Regras da noite", in pt-BR. The
  bridge is agile, 16 bars, never more than 32. Today's bridges are longer and the team
  shortens them (state the rule; no dated note).
- Modify: `docs/soundswitch/experiments.md`: experiment X11, per spec §9.
- Modify: `lightshows/shows/README.md`:
  - `advice`, `bridge.bars` and the `bridges` rule;
  - aim ids in preset fields;
  - the report's new sections, with their formulas;
  - `zoom`;
  - "reading the report as a critic" (what is fact, what is left to judgment);
  - the UV design summary, with a link to the spec's §9.
- Modify: `lightshows/README.md`: a row for `room.yml`, and a room section (schema, catalogue,
  measuring the room).
- Modify: `scripts/README.md`: `zoom`, and the report's sections in `nextrack_show.py`.
- Modify: `CLAUDE.md`:
  - an **Add an aim** checklist: a catalogue entry, `pending` with a fallback, the owner
    creates the preset, `assumed` until measured;
  - `zoom` added to the show tool's bullets.
- Test: `tests/test_show_docs.py`. Every rule (now including `bridges`) and gesture is named
  in the manual, which the existing test already checks. Add one test: every aim id of
  `lightshows/room.yml` is named in `lightshows/README.md` or the manual.

- [ ] **Step 1: Write the failing test** (the aim ids in the docs).
- [ ] **Step 2: Run it.** Expected: FAIL.
- [ ] **Step 3: Write** the data and docs edits above. Copy the examples from real runs
  (`report`, `zoom`, `vocab`), never from memory.
- [ ] **Step 4: Verify:**
  - the full suite and `check_repo` pass;
  - `build hi-ibiza-pulso --check` exits 0;
  - `build hi-ibiza-pulso` prints the advice: 11 bridges over 16, plus handovers;
  - `report hi-ibiza-pulso` lists them under `advice`.

  Paste the advice count.
- [ ] **Step 5: Commit** `Document the critic's views and set the Hi Ibiza bridge goal`.

---

## After the tasks

A whole-branch review (most capable model) with the ledger's deferred minors, one fix wave,
a scoped re-review, then the PR proposal to the owner.
