# The senses and the book (project 2a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the show critic measures that see energy (music and light per bar), six new
views, nine new advice rules, the night's declared identity, the echo, and three commands:
`brief`, `compare` and `book`, the HTML book of the night.

**Architecture:** Music facts are precomputed in the maps (map v2 `mix` block, added by an
upgrade that never re-runs the separation). Everything else is computed on demand from the
compiled show:

- `show_zoom.sample_light` samples the compiler's own output;
- `show_energy` turns music and light into per-bar digits;
- `show_analysis` builds the six analyses, cached on the `CompiledShow`;
- `show_report`, `show_brief`, `show_compare` and `show_book` render them;
- the rules in `show_rules` read the same analysis.

**Tech Stack:** Python 3.12, numpy, PyYAML, soundfile (main dependencies only), pytest, uv.

**Spec:** `docs/superpowers/specs/2026-11-07-show-team-design.md` (Part A). The research
behind it, with every formula's source, is `docs/superpowers/research/2026-11-07-show-team/`
(front C §6 for the measures).

## Global Constraints

- Setup and commands: `uv sync`, `uv run pytest`, `uv run scripts/check_repo.py`. Never pip
  or poetry.
- No new dependency in the main group, and none in `analysis`: numpy, PyYAML, soundfile and
  mutagen only. Spectra use `numpy.fft.rfft`.
- Audio is never committed. Tests synthesise audio under `tmp_path`.
- Never commit a machine path, a user name or local config. Run
  `git diff --cached | grep -iE "/home/|/mnt/|C:\\\\Users"` before every commit; it must print
  nothing.
- Every formula and constant lives in a docstring, and the manual repeats it.
- The views never say "boring" or "too long": they print facts.
- Output and docs are in English. The book's labels are pt-BR. Show prose stays pt-BR.
- Ids are kebab-case.
- Findings print as `path:line: rule-id: message`.
- Same inputs give the same bytes for `report`, `brief`, `compare` and `book`.
- Every new show rule has a docstring, a `check`, a test of the passing case and one of the
  failing case, and its row in the rules table of `lightshows/shows/README.md`
  (`tests/test_show_docs.py` enforces the row).
- A rule whose input is missing reports it ("cannot check: ...") and never passes silently.
- The Hï Ibiza choreographies do not change: `uv run scripts/nextrack_show.py build
  hi-ibiza-pulso --check` exits 0 after every task.
- Commit subjects are imperative English sentences with no `feat:` prefix. Every commit message
  ends with:

  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01TJp8YhHnGhN5eQ9PfRzAsC
  ```
- Definition of done for each task: `uv run pytest` and `uv run scripts/check_repo.py` pass.

## Review Focus

1. **A show with a v1 map (no `mix`)** must still report: that track's music energy uses the
   interim formula and is marked `(interim)`. Test in Task 7.
2. **A track whose light is all autoscript**, or a night with no drops: the analyses return
   None or empty, and the rules print "cannot check", never a pass and never a crash. Tests in
   Tasks 8 and 11.
3. **Echo edges:**
   - the outgoing map is shorter than the copy;
   - the incoming track has a gap (no section) in the copied stretch;
   - the incoming track says `bridge: false`;
   - the show has no `bridge.bars`.

   Tests in Task 5.
4. **Text that needs escaping in the book** (`&ME`, `<`, accents, apostrophes in titles and
   prose) is escaped and the file stays valid. Test in Task 15.
5. **`compare` across shows whose sets differ** (a track only in one) prints the added and
   removed tracks and does not crash. An unknown `--keep` name is a usage error (exit 2). Test
   in Task 14.

---

### Task 1: Map v2: the `mix` block

**Files:**
- Modify: `scripts/musical_map.py`
- Test: `tests/test_musical_map_file.py`, `tests/test_musical_map_features.py`,
  `tests/mapdata.py`
- Docs: `lightshows/README.md` (Musical maps: map v2 and `mix`)

**Interfaces:**
- Produces:
  - `musical_map.MAP_VERSION = 2` (what `analyze` writes), `MAP_VERSIONS = (1, 2)`;
  - `KEYS` gains `"mix"` as its last key;
  - `mix_block(x: np.ndarray, sr: int, bar_edges_ms: list[float]) -> dict[str, str]`, which
    returns `{"loudness": <digits>, "brightness": <digits>}`, one digit per bar;
  - `build_map(..., audio: np.ndarray, audio_sr: int)`: two new required keywords; it writes
    `map_version: 2` and `mix`;
  - `mapdata.good_map(bars, version=1)`: with `version=2` it adds a `mix` block (`"5" * bars`
    for both).

- [ ] **Step 1: Write the failing schema tests** in `tests/test_musical_map_file.py`:

```python
def test_a_v2_map_needs_a_mix_block():
    data = good_map(4, version=2)
    assert problems_map(data) == []
    del data["mix"]
    assert any("mix" in p for p in problems_map(data))

def test_a_v1_map_has_no_mix_block():
    data = good_map(4)
    data["mix"] = {"loudness": "5555", "brightness": "5555"}
    assert any("mix needs map_version 2" in p for p in problems_map(data))

def test_mix_digits_cover_every_bar():
    data = good_map(4, version=2)
    data["mix"]["loudness"] = "555"
    assert any("mix.loudness" in p for p in problems_map(data))

def test_a_v2_map_dumps_and_loads_back(tmp_path):
    data = good_map(4, version=2)
    path = tmp_path / "m.yml"
    path.write_text(dump_map(data), encoding="utf-8")
    assert load_map(path) == data
```

- [ ] **Step 2: Run them; expect FAIL** (`good_map` has no `version`).
  `uv run pytest tests/test_musical_map_file.py -k "mix or v2" -v`
- [ ] **Step 3: Implement the schema.**
  - `problems_map` accepts `map_version` 1 or 2. A v2 map requires `mix`: a mapping with
    exactly `loudness` and `brightness`, each a string of `bars` digits. A v1 map with `mix`
    is a problem: `mix needs map_version 2`.
  - `dump_map` writes `mix` the way it writes a voice's entry.
  - Extend `good_map`.
- [ ] **Step 4: Write the failing feature tests** in `tests/test_musical_map_features.py`. The
  audio is synthetic: 8 bars at 120 BPM, `sr = 22050`, bar edges every 2000 ms.

```python
def test_mix_loudness_reads_loud_bars_as_9_and_bars_20_db_down_as_0():
    x = np.concatenate([0.05 * sine(200, 8.0), 0.5 * sine(200, 8.0)])  # bars 1-4 quiet, 5-8 loud
    mix = mix_block(x, SR, EDGES)
    assert mix["loudness"] == "00009999"

def test_mix_brightness_reads_a_high_tone_above_a_low_one():
    x = np.concatenate([0.3 * sine(200, 8.0), 0.3 * sine(6000, 8.0)])
    assert mix_block(x, SR, EDGES)["brightness"] == "00009999"

def test_a_silent_bar_reads_0_in_both():
    x = np.concatenate([np.zeros(int(2.0 * SR)), 0.3 * sine(200, 14.0)])
    mix = mix_block(x, SR, EDGES)
    assert mix["loudness"][0] == "0" and mix["brightness"][0] == "0"

def test_build_map_writes_a_v2_map_with_mix(...):   # extend the existing build_map test
    data = build_map(..., audio=x, audio_sr=SR)
    assert data["map_version"] == 2 and len(data["mix"]["loudness"]) == data["bars"]
```

  `sine(f, seconds)` is a test helper (mono, `SR`). `EDGES` is `[0, 2000, ..., 16000]`.
- [ ] **Step 5: Run them; expect FAIL** (`mix_block` is undefined).
- [ ] **Step 6: Implement `mix_block`.** The docstring states the formula:
  - **The bar's audio:** the mono mix over `[edge_b, edge_{b+1})`.
  - **Loudness `L(b)`:** `10·log10` of the mean K-weighted power. The K-weighting is the
    ITU-R BS.1770 two-stage filter's magnitude response (the 48 kHz pre-filter and RLB
    coefficients), evaluated at each `rfft` bin's frequency and applied to that bin's power.
  - **Silence:** a bar is silent when it has no samples or `L < max L − 40`. A silent bar reads
    0 in both digits.
  - **The loudness reference:** `ref` is the 95th percentile of `L` over the non-silent bars.
  - **The loudness digit:** `clamp(9 − floor((ref − L) / 1.5), 0, 9)`, so 1.5 dB per digit.
  - **Brightness `s(b)`:** the share of the bar's unweighted power above 4000 Hz. Its digit is
    `round(9 · clip01((s − p5)/(p95 − p5)))`, with `p5` and `p95` over the non-silent bars, and
    0 when `p95 − p5 < 1e-9`.
  - Implement `build_map(audio, audio_sr)`: `mix_block(audio, audio_sr, bar_edges)` with the
    bar edges it already computes, and `map_version` set to `MAP_VERSION`.
  - Update every existing `build_map` caller in the tests.
- [ ] **Step 7: Run both test files; expect PASS.** Then `uv run pytest` (all) and
  `uv run scripts/check_repo.py`. The repo's v1 maps stay valid.
- [ ] **Step 8: Docs.** In `lightshows/README.md` "Musical maps", add `map_version: 2` and the
  `mix` block, the two formulas in words, and that a v1 map stays valid.
- [ ] **Step 9: Commit:** `Add the mix block of map version 2`.

### Task 2: `nextrack_map.py upgrade`, and `analyze` writes v2

**Files:**
- Modify: `scripts/nextrack_map.py`
- Test: `tests/test_nextrack_map_cli.py`
- Docs: `scripts/README.md` (`nextrack_map.py` section)

**Interfaces:**
- Consumes: `musical_map.mix_block`, `MAP_VERSION` (Task 1).
- Produces:
  - `upgrade_one(sess: Session, ref: ssf.TrackRef, known, out: list[str]) -> None`;
  - CLI `nextrack_map.py upgrade [track] [--playlist P | --all] --project P --root R`.
    `--all` upgrades every map under `lightshows/maps/`, resolving each one by its
    `soundswitch` GUID through `project.resolve`.

- [ ] **Step 1: Write the failing tests**, reusing the fixtures the `analyze` tests use (a
  synthetic project and audio under `tmp_path`):

```python
def test_upgrade_adds_the_mix_block_and_keeps_every_other_line(...):
    before = map_file.read_text(encoding="utf-8")            # a v1 map made by analyze on synthetic audio
    assert main(["upgrade", GUID, "--project", str(project), "--root", str(root), "--repo", str(repo)]) == 0
    after = map_file.read_text(encoding="utf-8")
    strip = lambda t: [l for l in t.splitlines() if not l.startswith(("map_version:", "mix:", "  loudness:", "  brightness:"))]
    assert strip(after) == strip(before)
    assert yaml.safe_load(after)["map_version"] == 2

def test_upgrade_refuses_when_the_audio_changed(...):
    # rewrite the audio file with other samples: sha differs
    assert main([...]) == 1
    assert "re-analyse" in capsys.readouterr().out

def test_upgrade_keeps_a_v2_map(...):           # second run prints "kept <path>" and changes nothing
def test_upgrade_all_upgrades_every_map(...):   # two maps, --all, both v2
def test_analyze_writes_a_v2_map(...):          # extend the existing analyze test: map_version 2 and mix
```

  The "strip" helper must match the way `dump_map` lays out `mix`.
- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Implement.**
  - `upgrade_one` reads the existing map (`read_map`). A missing map is refused:
    `no map: run analyze`.
  - A v2 map gives `kept <path>`.
  - It hashes the audio. When the hash differs from `audio.sha256`, it refuses with
    `the audio changed since the map was made: re-analyse with analyze --force`.
  - Otherwise it decodes with `read_audio` and builds the bar edges from the map's
    `grid.anchors` (`step_edges_ms(Grid(anchors), audio.ms)[::16][: bars + 1]`).
  - It sets `mix`, sets `map_version = 2`, writes with `dump_map`, and prints
    `upgraded <path>`.
  - It never calls the separator.
  - Register `upgrade` in `main`: it requires `--root`, and accepts a track, `--playlist` or
    `--all`, exactly one of them.
  - `analyze_one` passes `audio=x, audio_sr=sr` to `build_map`.
- [ ] **Step 4: Run the tests; expect PASS.** Then the whole suite.
- [ ] **Step 5: Docs.** In `scripts/README.md`, add `upgrade` with what it reads, writes and
  refuses.
- [ ] **Step 6: Commit:** `Add nextrack_map.py upgrade to bring maps to version 2`.

### Task 3: Upgrade the repo's maps

This task is run by the controller, which holds the owner's folders. It writes data, not code.

- [ ] **Step 1:** Run
  `uv run scripts/nextrack_map.py upgrade --all --project "$NEXTRACK_SOUNDSWITCH_PROJECT" --root "$NEXTRACK_AUDIO_ROOT"`,
  with both variables exported in the command (the controller has the values, which never
  appear in a committed file).
  - Expected: 15 lines `upgraded lightshows/maps/<slug>.yml`, and exit 0.
  - A refusal is reported to the owner, never forced.
- [ ] **Step 2:** Run `git diff --stat lightshows/maps`. Expected: 15 files, each with only
  `map_version` and the `mix` lines changed (`git diff lightshows/maps | grep '^[-+]' | grep -v
  -E '^(\+\+\+|---|[-+]map_version|\+mix|\+  (loudness|brightness))'` prints nothing).
- [ ] **Step 3:** Run `uv run scripts/check_repo.py`,
  `uv run scripts/nextrack_show.py build hi-ibiza-pulso --check` and `uv run pytest`. All exit 0.
- [ ] **Step 4: Commit:** `Upgrade the musical maps to version 2`.

### Task 4: What a compiled show knows, and its identity

**Files:**
- Modify: `scripts/show_language.py`, `scripts/check_repo.py`, `scripts/set_timeline.py`,
  `scripts/show_views.py`, `scripts/nextrack_show.py` (use `check_repo.valid_rig`, and `vocab`
  lists the identity dimensions)
- Test: `tests/test_show_language_model.py`, `tests/test_show_language_compile.py`,
  `tests/test_set_timeline.py`, `tests/test_check_repo_shows.py`, `tests/test_show_views.py`
- Docs: `lightshows/shows/README.md` (a new `### identity` section under `show.yml`)

**Interfaces:**
- Produces in `set_timeline.py`:
  - `block_energies(block_text: str) -> list[tuple[str, str, int | None]]`: the `eN`
    (1-10) at the start of a tracklist line's fourth `·` field.
- Produces in `check_repo.py`:
  - `show_energies(repo, source) -> dict[str, int]`: per show track, the energy of its block
    line, else its pool entry's `energy`;
  - `valid_rig(repo) -> lightshow.Rig | None`, moved from `nextrack_show._valid_rig`;
  - `show_inputs` fills `tempos`, `energies` and `rig`.
- Produces in `show_language.py`:
  - `ShowInputs` gains `tempos: dict[str, tuple[float, float]]`, `energies: dict[str, int]`
    (default empty) and `rig: object | None = None`;
  - `CompiledShow` gains `tempos`, `energies`, `rig`, `room` (filled from the inputs),
    `rule_lines: dict[tuple[str, str], int]`, and `cache: dict = field(default_factory=dict,
    compare=False, repr=False)`. `rule_lines` maps `("rules", id)`, `("advice", id)` and
    `("identity", signature name)` to their line in `show.yml`;
  - `IDENTITY_DIMENSIONS = ("look", "gesture", "movers.move", "movers.rate", "movers.colour",
    "aim", "matrix.draw", "matrix.rate", "matrix.colour", "hue.state", "hue.colour")` and
    `ARC_SHAPES = ("single-peak", "waves", "slow-burn")`;
  - `problems_identity(identity: object, palette: dict, looks: dict, room) -> list[tuple[int,
    str]]`. `compile_show` calls it (it needs `inputs.room`), and `problems_show` accepts the
    key `identity`.
- Produces in `show_views.py`:
  - `set_clock(maps: list[dict], tempos: list[tuple[float, float] | None], last_bars:
    list[int] | None = None) -> ShowClock`: the clock without a show;
  - `build_clock(show, tempos=None)` delegates to it, using `show.tempos` when `tempos` is
    None.

- [ ] **Step 1: Write the failing tests.**

```python
# test_set_timeline.py
def test_block_energies_reads_the_e_field():
    text = "## Tracklist (primary)\n1. A — B · 8A · 120 · e6  abre\n2. C — D · 9A · 121 · sem\n"
    assert block_energies(text) == [("A", "B", 6), ("C", "D", None)]

# test_show_language_model.py
def test_identity_accepts_signatures_on_dimensions():
    show = {..., "identity": {"arc": "waves", "signatures": [
        {"name": "azul-espaco", "intent": "O azul é o espaço.", "is": {"movers.colour": ["azul"]}, "share": {"min": 0.6}}]}}
    assert problems_identity(show["identity"], PALETTE, {}, None) == []

@pytest.mark.parametrize("sig, words", [
    ({"name": "x", "intent": "y", "is": {"movers.color": "azul"}}, "'movers.color' is not a dimension"),
    ({"name": "x", "intent": "y", "is": {"movers.colour": "azull"}}, "did you mean 'azul'"),
    ({"name": "x", "intent": "y", "is": {"look": "nada"}}, "look 'nada' is not defined"),
    ({"name": "x", "intent": "y", "is": {"aim": "cruzado"}}, "no valid lightshows/room.yml"),
    ({"name": "x", "intent": "y", "is": {"hue.colour": "azul"}, "share": {"min": 0.7, "max": 0.5}}, "min 0.7 is above max 0.5"),
    ({"name": "x", "intent": "y", "is": {}}, "is: name at least one dimension"),
    ({"name": "X", "intent": "y", "is": {"look": "a"}}, "kebab-case"),
])
def test_identity_problems(sig, words): ...
def test_identity_arc_is_a_known_shape(): ...   # "zigzag" -> "arc 'zigzag' is not one of single-peak, waves, slow-burn"

# test_show_language_compile.py
def test_a_compiled_show_carries_tempos_energies_and_rule_lines():
    src, inp = two_track_show()
    src.show["advice"] = {"bridges": {"max": 16}}   # with __line__ as the loader gives it
    compiled, _ = compile_show(src, dataclasses.replace(inp, tempos={TRACK_1: (120.0, 121.0)}, energies={TRACK_1: 6}))
    assert compiled.tempos[TRACK_1] == (120.0, 121.0) and compiled.energies[TRACK_1] == 6
    assert ("advice", "bridges") in compiled.rule_lines

# test_check_repo_shows.py
def test_show_inputs_read_the_energy_of_each_block_line(mini_repo): ...

# test_show_views.py
def test_set_clock_matches_build_clock_on_the_two_track_show(): ...
```

- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Implement** to the interfaces above.
  - **Messages:** `identity.signatures[<i>].is: '<dim>' is not a dimension; dimensions: <list>`,
    and the palette, look and aim messages that the cue checks already use (close matches
    included).
  - **Value checks:**
    - colours are palette names;
    - `look` takes defined looks;
    - `gesture` takes registered gestures;
    - `aim` takes aim ids of `room.yml`;
    - `movers.rate` and `matrix.rate` take a rate word;
    - `movers.move`, `matrix.draw` and `hue.state` take the layer's words (`lightshow`'s
      constants);
    - `share` is a fraction from 0 to 1, with `min <= max`.
  - `nextrack_show.vocab` prints the identity dimensions after the rules.
- [ ] **Step 4: Run the tests; expect PASS.** Then the whole suite and `check_repo.py`.
- [ ] **Step 5: Docs.** In the manual, add `identity` to the `show.yml` key table and an
  `### identity` section: the schema and example of spec A5, and how declared dimensions are
  exempt from the dominance checks.
- [ ] **Step 6: Commit:** `Give a compiled show its tempos, energies and rig, and add identity`.

### Task 5: The echo

**Files:**
- Modify: `scripts/show_language.py`, `scripts/show_rules.py`, `scripts/show_views.py`
- Test: `tests/test_show_language_compile.py`, `tests/test_show_rules.py`,
  `tests/test_show_views.py`
- Docs: `lightshows/shows/README.md` (the handover and the bridge: the echo),
  `docs/soundswitch/experiments.md` (P1's row)

**Interfaces:**
- Produces:
  - `Provenance.kind` may be `"echo"`;
  - `_echoes(show: _Show, tracks: list[CompiledTrack]) -> tuple[list[str], list[ShowFinding]]`
    runs in `compile_show` after `_compile_tracks` when the tracks are linked. It appends echo
    sections to the outgoing tracks, rebuilds their `choreography["sections"]`, revalidates
    them with `problems_choreography`, and returns the decision lines and any findings.

- [ ] **Step 1: Write the failing tests.** They start from `two_track_show()` with
  `show["bridge"]["bars"] = 4`. Outgoing Dançarina: G 25, handover 25-28. Incoming Voa Voa:
  B 5, bridge 5-8, first cue at `drop.1` = 9. The offset is G − B = 20.

```python
def test_the_echo_copies_the_incoming_light_onto_the_outgoing_tail():
    compiled = compiled_with_window(4)
    out, inc = compiled.tracks
    echo = [s for s in out.sections if s.origin.kind == "echo"]
    assert [(s.bars, s.name) for s in echo] == [((29, 32), "chegada")]
    src = next(s for s in inc.sections if s.bars[0] == 9)
    assert echo[0].origin.path == src.origin.path and echo[0].origin.line == src.origin.line
    assert echo[0].origin.role is None
    assert "Dançarina: echo 29-32 copies Voa Voa (Ao Vivo) 9-12" in compiled.decisions

def test_the_echo_shifts_faster_from_and_leaves_out_the_events(): ...
    # an outgoing map of 48 bars (G still 25), so the copy reaches the incoming 'subida'
    # (break.1 = 17, faster_from drop.2 - 2 = 19) and 'final' (drop.2 = 21, strobe-roll):
    # the echo's movers.faster_from == 39, and no echo layer holds white.accent, strobe.hit
    # or strobe.roll
def test_no_echo_without_bridge_bars(): ...
def test_no_echo_when_the_incoming_track_writes_bridge_false(): ...
def test_the_echo_stops_at_the_outgoing_maps_end(): ...       # outgoing map of 30 bars: echo 29-30
def test_a_gap_in_the_incoming_track_stays_a_gap(): ...       # incoming cue with until: no echo section over those bars
def test_the_emitted_choreography_with_an_echo_is_valid(): ...  # emit_choreography + problems_choreography == []

# test_show_rules.py
def test_echo_sections_are_not_occurrences(): ...             # budget counts equal with and without the echo
def test_rules_that_read_sections_skip_the_echo(): ...        # total-dark, movers-aim, matrix-not-cloned: no finding naming an echo

# test_show_views.py
def test_echo_sections_add_no_events_and_no_hit_rows(): ...
```

- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Implement.**
  - **When an echo exists:** for consecutive compiled tracks A then B, when `show.bridge` has
    `bars`, A's handover section ends before A's map's last bar, B holds a `bridge` section,
    and both hot cues resolve (A's `G`, B's `B`).
  - **What it copies:** offset = `G_A − B_B`. A's bars `h_end + 1 .. A.bars` copy B's
    sections intersecting `[h_end + 1 − offset, A.bars − offset]`, clipped and shifted by
    `+offset`.
  - **The layers:** deep-copied. `movers.faster_from` is shifted, and `white.accent`,
    `strobe.hit` and `strobe.roll` are removed (a layer left empty is dropped, so it reads
    `auto`).
  - **Name, intent and provenance:** the name and intent are B's. The provenance is
    `dataclasses.replace(B's origin, kind="echo", track=A.track, role=None)`.
  - **Decision line:** `"<A title>: echo <a>-<b> copies <B title> <a-offset>-<b-offset>"`.
  - **Rules:** `show_rules.occurrences` skips `echo` like `bridge`. `total_dark`,
    `movers_aim` and `matrix_not_cloned` skip `echo` sections: the original is checked where
    it is written.
  - **Views:** `show_views._events` and `hit_checks` skip `echo`. `peaks` gives `moment: None`
    for an echo, as for a bridge.
- [ ] **Step 4: Run the tests; expect PASS.** Then the whole suite. `build hi-ibiza-pulso
  --check` exits 0, because Hï Ibiza has no `bridge.bars`.
- [ ] **Step 5: Docs.**
  - The manual's bridge section gets the echo: when it exists, what it copies and what it
    leaves out, its provenance, `bridge: false`, and its line under "decided by the compiler".
  - P1's row in `experiments.md` says the echo keeps short bridges safe whatever P1 finds.
- [ ] **Step 6: Commit:** `Add the echo: the incoming light on the rest of a long mix`.

### Task 6: A public light sampler

**Files:**
- Modify: `scripts/show_zoom.py`
- Test: `tests/test_show_zoom.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class StepLight:
    t: int                               # ms on the track's grid: step start + SAMPLE_OFFSET_MS
    movers: tuple[float | None, ...]      # each mover's level 0-1 (a strobe window wins); None: auto
    units: tuple[float | None, ...]       # each Vorlane's highest colour-cell level; None: auto
    coverage: tuple[float | None, ...]    # each Vorlane's lit share of its colour cells, 0-1; None: auto
    white: float | None                   # the white strip's level; None: auto
    strobe: bool | None                   # a strobe window lit at t; None: auto
    hue: float | None                     # the lustre's level; None: auto

def sample_light(track: CompiledTrack, first: int, last: int, rig, room) -> list[StepLight]
```

  It returns one sample per 1/16 step of bars `first..last` (16 per bar), at `sample_times`.
  A step that no section holds has every field None (the autoscript). `rig` None takes the
  same defaults `render_zoom` takes.

- [ ] **Step 1: Write the failing tests:**
  - `test_sample_light_has_16_samples_per_bar`;
  - `test_sample_light_agrees_with_the_zoom_lanes` (for every step of the two-track show's
    'virada', `movers[i]` equals `_light(section, ctx).mover(i, t)[0]`, and `coverage[u]` is
    the lit share of `COLOUR_CELLS`);
  - `test_a_bar_with_no_section_samples_as_autoscript`;
  - `test_a_strobe_window_marks_strobe_true` (on the 'virada' hit).
- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Implement `sample_light`.** Build the `_Context` the way `render_zoom` does,
  and share that construction in a helper both call.
- [ ] **Step 4: Run them; expect PASS.** Then the whole suite.
- [ ] **Step 5: Commit:** `Add sample_light, the zoom's sampler as a public function`.

### Task 7: Energy per bar (`show_energy.py`)

**Files:**
- Create: `scripts/show_energy.py`
- Test: `tests/test_show_energy.py`, `tests/test_show_energy_repo.py`

**Interfaces:**
- Consumes: `sample_light`, `StepLight` (Task 6); the `CompiledShow` fields (Task 4);
  `show_views.ShowClock`, `section_aims`.
- Produces:

```python
MUSIC_WEIGHTS = {"loudness": 0.4, "brightness": 0.2, "density": 0.2, "texture": 0.2}
INTERIM_WEIGHTS = {"density": 0.5, "texture": 0.5}
LIGHT_WEIGHTS = {"movers": 0.35, "vorlanes": 0.35, "lustre": 0.15, "white": 0.10, "strobe": 0.05}
CHANGE_DIMENSIONS = IDENTITY_DIMENSIONS[2:]           # the nine layer dimensions (no look, no gesture)

@dataclass(frozen=True)
class BarMusic:
    loudness: int | None      # mix.loudness digit; None on a v1 map
    brightness: int | None
    density: float            # steps with a kick or perc onset >= 3, / 16
    texture: int              # voices whose bar digit is >= 6 (0-5)

@dataclass(frozen=True)
class BarLight:
    brightness: float | None  # weighted mean of level x coverage; None: unknown (auto)
    activity: float | None    # weighted dark->lit rises / 16

@dataclass
class TrackEnergy:
    index: int
    track: str
    first: int                # the bar of list index 0 (the sounding window's first bar)
    music: list[int]          # E_music, track scope
    music_night: list[int]    # E_music, night scope
    light: list[int | None]   # E_light, night scope
    brightness: list[int | None]   # night-normalised digits
    activity: list[int | None]
    changes: list[int]        # X(b)
    interim: bool
    def at(self, series: str, bar: int) -> int | None: ...   # None outside the window

def normalise(values: list[float], scope: list[float]) -> list[float]
def music_bars(map_data: dict) -> list[BarMusic]
def music_energy(bars: list[BarMusic], scope: list[BarMusic]) -> list[int]
def light_bars(samples: list[StepLight]) -> list[BarLight]
def light_energy(bars: list[BarLight], scope: list[BarLight]) -> list[int | None]
def dimension_values(section: CompiledSection | None, room, names: dict[str, str]) -> dict[str, tuple[str, ...]]
def signature(section: CompiledSection | None, room, names: dict[str, str]) -> tuple
def night_energy(show: CompiledShow, clock: ShowClock) -> list[TrackEnergy]   # cached in show.cache["energy"]
```

- **The formulas**, in the module docstring and the manual:
  - `normalise`: `clip01((x − p5)/(p95 − p5))` with `numpy.percentile` over `scope`, and 0.5
    when `p95 − p5 < 1e-9`.
  - `E_music = round(9 · Σ w·featurê)`, with `MUSIC_WEIGHTS`. When the map has no `mix`, it uses
    `INTERIM_WEIGHTS` and `interim=True`.
  - Light per bar, from its 16 samples:
    - the bar is unknown when any sample has a None in `movers`, `units` or `hue`;
    - each group's brightness is its mean level over the steps (Vorlanes: level × coverage per
      unit, averaged over units; white: its level, None as 0; strobe: the share of steps lit);
    - each group's rises are steps where its level is ≥ 0.05 after a step below 0.05. The
      first step compares with the previous bar's last sample, which `night_energy` passes;
    - `B` and `A` are `Σ LIGHT_WEIGHTS·group`, with rises divided by 16;
    - `E_light = round(9 · (0.5·B̂ + 0.5·Â))`, normalised over the night's known leg bars.
  - `X(b)`: the dimensions of `CHANGE_DIMENSIONS` whose value at bar b differs from bar b − 1
    of the same track (0 at the window's first bar).
- **Dimension values:**
  - `look` is the origin's look, else its gesture, else `"inline"`;
  - colours are palette names (`names` maps `#RRGGBB` to a name), and `aim` is
    `section_aims(...)`;
  - a layer that is `auto` gives `("auto",)`, `off` gives `("off",)`, and no section gives
    `("auto",)` for every dimension.
- **Scopes:** the track scope is the track's leg bars, and the night scope is every track's
  leg bars. `music` and `music_night` cover the whole sounding window (normalised over those
  scopes).

- [ ] **Step 1: Write the failing unit tests** (synthetic maps from `showdata.show_map`, made
  v2 with a `mix` you set):
  - `test_normalise_clips_to_the_scope_percentiles`;
  - `test_a_constant_scope_normalises_to_a_half`;
  - `test_music_energy_rises_with_loudness_and_texture` (bars 1-8 loudness `2`, texture 1;
    bars 9-16 loudness `9`, texture 4: every E_music of 9-16 is above every one of 1-8);
  - `test_a_v1_map_uses_the_interim_formula_and_says_so`;
  - `test_light_activity_sees_rate` (a section `matrix columns rate 1/16` against the same at
    `1bar`: higher activity);
  - `test_strobe_and_white_enter_the_light`;
  - `test_an_auto_layer_makes_the_bar_unknown`;
  - `test_changes_count_the_dimensions_that_change` (bar 9 of the two-track show, from
    'intro' autoscript to 'chegada');
  - `test_signature_of_no_section_is_all_auto`;
  - `test_night_energy_is_cached_on_the_show`.
- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Implement `show_energy.py`** to the interfaces and formulas.
- [ ] **Step 4: Run them; expect PASS.**
- [ ] **Step 5: Write the repo calibration test** `tests/test_show_energy_repo.py` (it reads the
  committed Hï Ibiza show and its v2 maps through `check_repo.load_repo`, `show_inputs` and
  `compile_show`, with no audio):

```python
def test_hi_ibiza_music_energy_does_not_saturate():
    shares = Counter(d for t in energies for d in leg_values(t, "music_night"))
    assert max(shares.values()) / sum(shares.values()) <= 0.40

def test_hi_ibiza_drops_after_a_break_rise_in_music_energy():
    rising = [mean(music[d:d+4]) > mean(music[d-4:d]) for each map drop d after a break or build section]
    assert sum(rising) / len(rising) >= 0.80
```

- [ ] **Step 6: Run it.** If it fails, tune `MUSIC_WEIGHTS` and the feature definitions (not
  the thresholds). Report the final weights and both measured values in the task report. If
  no tuning meets them, stop and report: the spec makes this the builder's call to raise.
- [ ] **Step 7: Commit:** `Add show_energy: music and light energy per bar`.

### Task 8: Analyses I: follows, drops, builds (`show_analysis.py`)

**Files:**
- Create: `scripts/show_analysis.py`
- Test: `tests/test_show_analysis.py`

**Interfaces:**
- Consumes: `night_energy`, `TrackEnergy`, `signature`, `dimension_values` (Task 7);
  `show_views.build_clock`, `_section_at`-style lookups.
- Produces:

```python
def spearman(a: list[float], b: list[float]) -> float | None   # None below 3 pairs or for a constant side

@dataclass
class Boundary: bar: int; music: float; light: float
@dataclass
class Follow:
    index: int; track: str
    rho: float | None; agreement: float | None; lag: int | None
    missed: list[Boundary]; unmotivated: list[Boundary]; unknown_share: float
def follows(show: CompiledShow, clock: ShowClock) -> list[Follow]

@dataclass
class Drop:
    clock_s: float; index: int; track: str; bar: int
    loud_rise: float; bass_return: float; density_rise: float; main: bool
    salience: float; rank: int                       # 1 = the night's biggest
    contrast: float | None; change: int; freshness: float | None; response: float | None
    template: tuple; holder: CompiledSection | None
def drops(show: CompiledShow, clock: ShowClock) -> list[Drop]          # sorted by rank
def top(rows: list[Drop], n: int | float) -> list[Drop]                  # int: count; float: fraction, at least 1
def drop_agreement(rows: list[Drop]) -> float | None                     # spearman(salience, response) over drops above the median salience

@dataclass
class Build:
    index: int; track: str; bars: tuple[int, int]
    music_slope: float; activity_slope: float | None; brightness_slope: float | None
    into: str                                        # "dip" | "ramp" | "flat" | "unknown"
def builds(show: CompiledShow, clock: ShowClock) -> list[Build]
```

- **Formulas** (docstrings and manual):
  - **follows:** over the leg's bars with known light. `rho` = `spearman(music, light)`.
  - **Boundaries:** map section starts `s` with `leg[0] + 4 <= s <= leg[1] − 3`. `Δm` = mean
    track-scope E_music over `s..s+3` minus over `s−4..s−1`; `Δl` is the same for E_light.
  - **agreement:** the share of boundaries with `|Δm| >= 2` where `sign(Δl) == sign(Δm)` and
    `|Δl| >= 1`; None when no boundary qualifies.
  - **missed** and **unmotivated:** missed boundaries have `|Δm| >= 2` and `|Δl| < 1`;
    unmotivated ones have `|Δl| >= 3` and `|Δm| < 1`.
  - **lag:** the shift in `[−8, 8]` that maximises Pearson(music[t], light[t + shift]);
    positive means the light is late. None below 16 known bars.
  - **Drops:** every map drop `d` in a track's sounding window. `loud_rise` = mean
    `mix.loudness` digit over `d..d+3` minus over `d−8..d−1` (a v1 map uses track-scope
    E_music). `bass_return` = `max(0, bass digit at d − min bass digit over d−8..d−1) / 9`.
    `density_rise` uses the density the same way.
  - **main:** the track's drop with the largest `loud_rise`, or its last map drop.
  - **salience:** `S = 0.4·L̂ + 0.3·bass_return + 0.2·D̂ + 0.1·main`, where `x̂ = max(0, x) /
    max over the night's drops` (0 when that max is ≤ 0).
  - **Response:**
    - `contrast` = mean E_light over `d..d+3` minus over `d−2..d−1`, with known bars only.
      None when either side has none. At a leg's first bar, `d−2..d−1` are read in the
      previous track, as `_section_before` does;
    - `change` = `X(d)`;
    - `freshness` = the share of the drop section's `CHANGE_DIMENSIONS` values that no other
      section sounding in the 600 s before it on the set clock has;
    - `response = 0.5·clip01(contrast/4) + 0.25·change/9 + 0.25·freshness`.
  - **template:** `(signature at d − 1, signature at d)`.
  - **Builds:** each map `build` section of at least 4 bars, and the last `min(16, len)` bars
    of each `break` of at least 4 bars that a `drop` section follows directly, inside the
    sounding window.
  - **music_slope:** the least-squares slope per bar of `T(b) = mean(L̂, Ĉ, D̂)` (track scope;
    interim: `D̂`). `activity_slope` and `brightness_slope` come from the night digits.
  - **into**, with `d` = the window's end + 1:
    - `"dip"` when `E_light(d−1) <= mean(E_light(d−9..d−2)) − 1`;
    - else `"ramp"` when the window's last 4 E_light do not decrease and
      `E_light(d−1) > E_light(window start)`;
    - else `"flat"`;
    - `"unknown"` when the bars it needs are unknown.

- [ ] **Step 1: Write the failing tests** on synthetic shows built from `two_track_show()`,
  with v2 maps whose `mix` you shape:
  - `test_spearman_known_values` (`[1,2,3]` with `[1,2,3]` is 1.0; with `[3,2,1]` it is −1.0;
    a constant side gives None);
  - `test_a_light_that_rises_with_the_music_follows_it` (`rho > 0.5`, no missed boundary);
  - `test_a_flat_light_misses_the_boundaries` (missed lists bar 9 and 21);
  - `test_lag_reads_a_late_light` (the light's rise placed 2 bars after the music's gives
    lag 2);
  - `test_drops_rank_by_salience` (a drop with a bigger loudness rise and bass return ranks
    first);
  - `test_the_last_drop_of_a_track_is_main`;
  - `test_a_drop_with_a_dark_bar_before_has_positive_contrast`;
  - `test_freshness_is_low_for_a_repeated_look`;
  - `test_a_build_into_a_dark_bar_reads_dip`;
  - `test_a_track_all_autoscript_gives_none_not_a_crash`;
  - `test_a_night_with_no_drops_gives_no_rows`.
- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; expect PASS.**
- [ ] **Step 5: Commit:** `Add show_analysis: follows, drops and builds`.

### Task 9: Analyses II: variety, arc, identity, and `analyse`

**Files:**
- Modify: `scripts/show_analysis.py`
- Test: `tests/test_show_analysis.py`

**Interfaces:**
- Produces:

```python
@dataclass
class Run: index: int; track: str; bars: tuple[int, int]; seconds: float; music: str   # music: the map's section kinds under it
@dataclass
class Dominant: value: str; share: float; declared: bool
@dataclass
class Usage: index: int; track: str; looks: list[str]; colours: dict[str, list[str]]; aims: list[str]; gestures: list[str]; templates: int
@dataclass
class Variety:
    static_runs: list[Run]                 # top 5 by seconds; a run continues across a leg boundary when the signature is the same
    window: list[int | None]               # one digit per minute of the night
    dominance: dict[str, Dominant]         # per IDENTITY_DIMENSIONS entry
    similarity: list[tuple[int, float]]    # (i, cosine of track i and i + 1)
    templates: tuple[int, int]             # (distinct, drops)
    phrase_share: float | None
    usage: list[Usage]
def variety(show, clock) -> Variety

@dataclass
class ArcTrack: index: int; track: str; energy: int | None; mean: float | None; p90: float | None; activity: float | None; warm: float | None; rare: dict[str, int]
@dataclass
class Arc:
    tracks: list[ArcTrack]
    rho: float | None; rho90: float | None; headroom: float | None
    staircase: list[int]                   # indices that break the staircase
    steps: list[tuple[int, str]]           # (index of the second track, "jump" | "flat")
    breathers: list[tuple[int, int]]       # (index, bar) of top drops with no breather after them
    labels: list[str]                      # label-check questions
    target: list[tuple[float, int]]        # (clock_s at each leg's start, owner energy)
def arc(show, clock) -> Arc

@dataclass
class SignatureCheck: name: str; intent: str; share: float; min: float | None; max: float | None; ok: bool; occurrences: list[tuple[int, str, tuple[int, int], float]]
@dataclass
class Identity: arc: str | None; signatures: list[SignatureCheck]; undeclared: dict[str, tuple[str, float]]
def identity(show, clock) -> Identity

@dataclass
class Analysis: clock: ShowClock; energy: list[TrackEnergy]; follows: list[Follow]; drops: list[Drop]; builds: list[Build]; variety: Variety; arc: Arc; identity: Identity
def analyse(show: CompiledShow) -> Analysis       # cached in show.cache["analysis"]; clock = build_clock(show)
```

- **Formulas** (docstrings and manual). All shares are of time summed over legs.
  - **Static runs:** consecutive bars with the same `signature`, merged across a leg
    boundary.
  - **window:** for minute `m`, the signatures' time shares in `[60m − 120, 60m + 120)`. `H =
    −Σ p·log2 p / log2(k)` with `k` distinct signatures (0 when `k <= 1`), printed as
    `round(9H)`.
  - **dominance:** per dimension, the value (not `auto`) with the largest share, marked
    `declared` when a signature's `is` names that dimension and value.
  - **similarity:** the cosine of the tracks' vectors of time shares over every
    `(dimension, value)` pair.
  - **templates:** distinct drop templates against the number of drops.
  - **phrase_share:** the share of bars with `X(b) > 0` whose bar is a map section start or
    `(b − start of its map section) % 4 == 0`.
  - **usage:** per track, the values it uses.
  - **Arc:**
    - `energy` comes from `show.energies`; `mean` and `p90` are the night E_light over the
      leg's known bars;
    - `warm`: the share of the leg where the movers' or the lustre's colour has an HSV hue
      within 30° of red;
    - `rare` counts the `occurrences` of `strobe`, `white-accent`, `white-flash` and `uv`, the
      total-dark sections, and the gesture calls;
    - `rho` and `rho90` are the `spearman` of energy against mean and against p90;
    - `headroom` = the max p90 over the tracks before the first one at the night's max energy,
      divided by the night's max p90 (None without such tracks, or a max of 0);
    - the **staircase** breaks where a track's p90 exceeds every earlier p90 while its energy
      is below an earlier energy;
    - a **step** is a `"jump"` when `|Δmean| >= 2` and `Δe == 0`, and a `"flat"` when
      `|Δmean| < 1` and `Δe >= 1`;
    - **breathers:** each drop in `top(drops, 0.25)` needs a bar with E_light ≤ the night's
      median within 180 s after it;
    - **labels:** tracks whose rank by mean night E_music differs from their rank by owner
      energy by 3 or more. The question reads `"<title>: owner energy e<n> ranks <r>,
      measured music ranks <m>: check the label"`.
  - **Identity:** a section carries a signature when every listed dimension's values meet the
    section's values. `share` is its time share; `ok` means it is within `min`/`max`. The
    occurrences are maximal runs of carrying sections. `undeclared` holds, per dimension, the
    top value that no signature declares.

- [ ] **Step 1: Write the failing tests:**
  - `test_the_longest_static_run_crosses_a_bridge` (the two-track show's handover and bridge
    share a signature: one run spans both legs);
  - `test_window_variety_is_0_for_one_signature`;
  - `test_dominance_marks_declared_values`;
  - `test_identical_tracks_have_similarity_1`;
  - `test_phrase_share_counts_changes_on_4_bar_lines`;
  - `test_arc_rho_follows_the_owner_energy` (energies 6 and 9 with lights 2 and 7 give
    `rho = 1.0` for two tracks; use three tracks for spearman's 3 pairs);
  - `test_headroom_reads_the_peak_before_the_peak_track`;
  - `test_a_flat_step_is_flagged_when_energy_rises_and_light_does_not`;
  - `test_a_top_drop_without_a_breather_is_listed`;
  - `test_the_label_check_names_a_track_three_ranks_off`;
  - `test_identity_measures_a_declared_signature` (`movers.colour: [azul]` on the two-track
    show: its share equals the azul movers' leg time / night);
  - `test_analyse_is_cached`.
- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; expect PASS.** Then the whole suite.
- [ ] **Step 5: Commit:** `Add show_analysis: variety, arc and identity`.

### Task 10: The report on the new measures, its new sections and its filters

**Files:**
- Create: `scripts/show_report.py` (the new sections' text)
- Modify: `scripts/show_views.py`, `scripts/nextrack_show.py`
- Test: `tests/test_show_views.py`, `tests/test_nextrack_show.py`, `tests/test_show_report.py`
- Docs: `lightshows/shows/README.md` ("Levels" rewritten; "What report prints" with the new
  sections and filters), `scripts/README.md` (report flags)

**Interfaces:**
- Consumes: `analyse` and everything it returns (Tasks 7-9).
- Produces:
  - `show_views`: delete `WEIGHTS`, `light_values`, `light_level`, `music_level` and helpers
    only they use;
  - `peaks(show, clock, energy)` and `hit_checks(show, clock, energy)`: `music` is the
    track-scope E_music at the bar, `before` is E_light at bar − 1 (in the previous track at
    a leg's first bar), and `at` is E_light at the bar;
  - `strips(track, clock, energy) -> dict[str, str]` with keys `music`, `light`, `bright` and
    `activity` (`~` for unknown);
  - `show_report.REPORT_SECTIONS = ("summary", "tracks", "peaks", "hits", "follows", "drops",
    "builds", "variety", "arc", "identity", "budget", "arrivals", "advice", "decided",
    "findings")`;
  - `show_report.follows_lines(a: Analysis, show) -> list[str]`, and the same for
    `drops_lines`, `builds_lines`, `variety_lines`, `arc_lines` and `identity_lines`;
  - `render_report(show, findings, advice, clock, room, *, track: str | None = None, sections:
    tuple[str, ...] = REPORT_SECTIONS) -> str`;
  - CLI `report <show> [--track TEXT] [--section a,b]`. `--track` matches like `zoom`'s
    track target. An unknown section or track is a usage error (exit 2) that lists the valid
    ones.

- [ ] **Step 1: Write the failing tests:**
  - `test_strips_have_four_rows`;
  - `test_peaks_use_the_light_energy`;
  - in `test_show_report.py`, one test per section that checks its header and one known
    line on the two-track show (`follows`: a `rho` line per track; `drops`: `rank 1` first;
    `identity`: the declared signature's share);
  - in `test_nextrack_show.py`:
    - `test_report_section_filter_prints_only_that_section`;
    - `test_report_track_filter_prints_that_track_and_its_neighbours_handover`;
    - `test_report_unknown_section_is_a_usage_error` (exit 2, lists the names);
    - `test_report_is_deterministic` (two runs, same text).
- [ ] **Step 2: Run them; expect FAIL.** Update the existing tests that asserted the retired
  indices to the new measures, and keep each test's intent.
- [ ] **Step 3: Implement.**
  - Each new section starts with a header line (`follows`, `drops`...) and one line per
    item, about one line per item in all.
  - The legend states the formulas' names and points at the manual.
  - With `--track`, it prints:
    - that track's header and strips, and its section lines;
    - the previous track's handover line and the next track's bridge line;
    - that track's follows and builds lines;
    - the drops, variety and arc lines that name it.
- [ ] **Step 4: Run them; expect PASS.** Then the whole suite. Run `report hi-ibiza-pulso` and
  check that a `--track` slice is under 12 000 characters (about 3k tokens). Note the full
  report's size in the task report.
- [ ] **Step 5: Docs.**
  - Rewrite the manual's "Levels" section with the Task 7 formulas.
  - Document each new report section with its formula, and `--track` and `--section`.
  - Remove the retired index from the docs.
  - Update the sample excerpts by rerunning them.
- [ ] **Step 6: Commit:** `Report the night with energy measures, six new views and filters`.

### Task 11: Rules I: signatures, static-run, neighbours-differ, distinct-drops, phrase-aligned

**Files:**
- Modify: `scripts/show_rules.py`
- Test: `tests/test_show_rules.py`
- Docs: the manual's rules table (one row each)

**Interfaces:**
- Consumes: `show_analysis.analyse`, imported **inside** each rule function (show_analysis
  imports show_views, which imports show_rules).
- Produces registered rules, with `params` lines and `check` functions:

| rule | params | check | finding at |
|---|---|---|---|
| `signatures` | `true` | `_check_true` | the signature's `identity` line (`rule_lines[("identity", name)]`) |
| `static-run` | `{max_seconds: 30-600}` | int in range | the first section of the run |
| `neighbours-differ` | `{max_similarity: 0-1}` | number in range | the second track's arrival section, else its first section |
| `distinct-drops` | `{top: int >= 1 or 0 < float <= 1}` | as said | the later drop's holder section |
| `phrase-aligned` | `{min_share: 0-1}` | number in range | the rule's line (`rule_lines`, `rules` then `advice`) |

- **Messages** (in each rule's tests):
  - `signatures: coracao holds 38% of the night, min 50%`, or `... max 30%`;
  - `static-run: The Akan 57-96 holds one light for 2:08, max 2:00 (music: groove, drop)`;
  - `neighbours-differ: Trippy Yeah looks like We Dance Again (similarity 0.91, max 0.85)`;
  - `distinct-drops: Can't Decide 69 (top drop 4) repeats the light of PICK UP 137 (top drop 3)`.
    Consecutive in rank order among the top drops, by clock;
  - `phrase-aligned: 84% of the light's changes are on phrase lines, min 90%; off the lines: The Akan 38, ...`
    (at most 5 listed).
- **Missing input:** "cannot check: <why>" findings for a night with no known light, no drops
  (distinct-drops), or no changes (phrase-aligned).

- [ ] **Step 1: Write the failing tests:** for each rule a passing and a failing case on
  synthetic shows, a `check` test for a bad parameter, and the "cannot check" case where it
  applies.
- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; expect PASS.** Then `uv run pytest tests/test_show_docs.py` after
  adding the five rows.
- [ ] **Step 5: Commit:** `Add the signatures, static-run, neighbours-differ, distinct-drops and phrase-aligned rules`.

### Task 12: Rules II: drop-contrast, main-drop, follows-track, follows-set

**Files:**
- Modify: `scripts/show_rules.py`
- Test: `tests/test_show_rules.py`
- Docs: the manual's rules table

**Interfaces:**
- Consumes: the same as Task 11.
- Produces:

| rule | params | finding when | at |
|---|---|---|---|
| `drop-contrast` | `{top, min_change: 1-9}` | a top drop has `contrast <= 0` (or None) or `change < min_change` | the drop's holder section |
| `main-drop` | `true` | a track's main drop has a lower `response` than an earlier drop of the same track | the main drop's holder |
| `follows-track` | `{min_rho?: -1..1, max_lag?: 0-8}`, at least one | `rho < min_rho` or `abs(lag) > max_lag` | the section at the first missed boundary, else the track's first section |
| `follows-set` | `{min_rho?: -1..1, max_headroom?: 0-1}`, at least one | `arc.rho < min_rho` or `arc.headroom > max_headroom` | the rule's line |

- **Messages:**
  - `drop-contrast: Too Cool To Be Careless 49 (top drop 2) has contrast 0.0 and 1 change, min 2`;
  - `main-drop: The Rapture Pt.III's main drop 145 answers 0.31, below its drop 97 (0.52)`;
  - `follows-track: The Akan: rho 0.12, min 0.30; lag 3 bars, max 1; missed boundaries 57, 89`;
  - `follows-set: rho 0.21 between the owner's energy and the light per track, min 0.50; headroom 0.95, max 0.80`.
- **Cannot check:** a track with no known light (`follows-track`), fewer than 3 tracks with
  energy and light (`follows-set` rho), no drops.

- [ ] **Steps 1-5:** as in Task 11. Commit message: `Add the drop-contrast, main-drop, follows-track and follows-set rules`.

### Task 13: `brief`

**Files:**
- Create: `scripts/show_brief.py`
- Modify: `scripts/nextrack_show.py`
- Test: `tests/test_show_brief.py`, `tests/test_nextrack_show.py`
- Docs: the manual (a `## brief` section), `scripts/README.md`

**Interfaces:**
- Consumes: `show_views.set_clock` (Task 4); `show_energy.music_bars`, `music_energy`
  (Task 7); `set_timeline.block_tempos`, `block_energies`; and the check_repo set, tracklist
  and map lookups that `show_inputs` uses.
- Produces:
  - `render_brief(repo: check_repo.Repo, set_rel: str) -> str`;
  - CLI `brief <set>` (a repo-relative path, or the stem of `sets/<stem>.md`).

- **Content**, in order, with the headers `night`, `tracks`, `drops`, `target`, `labels` and
  `missing`:
  - the night's length, the set's `arc`, the blocks' `function`s and the tempo ramp;
  - per track:
    - its clock, enters at and leg minutes;
    - `B`, `G` and the mix window (bars from `G` to the end);
    - the owner energy;
    - night-normalised E_music mean and p90;
    - the section strip (the letters of `nextrack_map.py show`);
    - vocal presence (the share of leg bars with a vocals digit ≥ 6);
  - the night's drops ranked by the salience formula of Task 8, applied to the maps alone;
  - the target energy per minute as a digit strip;
  - the label questions;
  - the tracks with no map, a v1 map, or no hot cue `B`/`G` where a bridge would need it.
- It needs no show, and a missing map is a line under `missing`, not a crash.

- [ ] **Step 1: Write the failing tests** on the mini repo's set:
  - `test_brief_lists_every_set_track_in_order`;
  - `test_brief_ranks_the_drops`;
  - `test_brief_reports_a_missing_map_under_missing`;
  - `test_brief_is_deterministic`;
  - CLI: `test_brief_accepts_a_set_stem` and `test_brief_unknown_set_is_a_usage_error`.
- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Implement.** Share the salience computation with `show_analysis.drops` (move
  its map-only part into a function both call).
- [ ] **Step 4: Run them; expect PASS.** Run `brief sets/hi-ibiza-pulso.md`. The text is at
  most 16 000 characters (about 4k tokens); report its size.
- [ ] **Step 5: Docs. Commit:** `Add nextrack_show.py brief: a set's music for the director`.

### Task 14: `compare`

**Files:**
- Create: `scripts/show_compare.py`
- Modify: `scripts/nextrack_show.py`
- Test: `tests/test_show_compare.py`, `tests/test_nextrack_show.py`
- Docs: the manual (a `## compare` section), `scripts/README.md`

**Interfaces:**
- Produces:
  - `FACTS = ("arrivals", "moments", "drops", "signatures", "looks", "colours", "windows",
    "findings")`;
  - `facts(show: CompiledShow, rules: list[ShowFinding], advice: list[ShowFinding]) ->
    dict[str, dict[str, str]]`: per fact, a key (a track, or a track and bar) mapped to a
    printable value;
  - `diff_facts(a: dict, b: dict) -> dict[str, list[str]]`: per fact, the lines that differ,
    such as `+ <key>: <value>`, `- <key>: <value>` and `~ <key>: <a> -> <b>`;
  - CLI `compare <show-a> <show-b> [--keep a,b]`. Each show is an id or a folder; a folder
    outside `lightshows/shows/` is fine. It prints `<fact>: same` or the lines. With `--keep`
    it exits 1 when a kept fact differs; an unknown name exits 2 and lists `FACTS`.
- **Facts:**
  - arrivals (bar, look, matrix draw, colours by name);
  - moments (name and bar);
  - drops (rank, response rounded to 2);
  - signatures (share rounded to 2);
  - looks and colours (minutes rounded to 0:05, per zone);
  - windows (handover and bridge lengths);
  - findings (counts per rule id, for rules and advice).

- [ ] **Step 1: Write the failing tests:**
  - `test_a_show_compared_with_itself_is_the_same_everywhere`;
  - `test_moving_an_arrival_is_a_difference_in_arrivals`;
  - `test_keep_exits_1_when_a_kept_fact_differs`;
  - `test_keep_unknown_name_is_a_usage_error`;
  - `test_a_track_in_only_one_show_is_listed_as_added_or_removed`.
- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; expect PASS.**
- [ ] **Step 5: Docs. Commit:** `Add nextrack_show.py compare: the facts of two shows`.

### Task 15: `book`

**Files:**
- Create: `scripts/show_book.py`
- Modify: `scripts/nextrack_show.py`
- Test: `tests/test_show_book.py`, `tests/test_nextrack_show.py`
- Docs: the manual (`## book` and the ledger format of spec A10), `scripts/README.md`

**Interfaces:**
- Consumes: `analyse` (Tasks 7-9), `show_views.night_summary`, `show_rules.occurrences`.
- Produces:
  - `BOOK_SECTIONS = ("capa", "conceito", "paleta", "assinaturas", "vocabulario", "arco",
    "momentos", "ritmo", "musicas", "limites", "avisos")`: the `id` of each `<section>`;
  - `@dataclass LedgerRun: title: str; decisions: list[str]; later: list[str]`;
  - `latest_run(ledger: str) -> LedgerRun | None`: the last `## ` heading's run, its
    `### Decisões` and `### Para depois` list items;
  - `render_book(show: CompiledShow, advice: list[ShowFinding], ledger: str | None) -> str`;
  - CLI `book <show> -o FILE`. It reads `<show folder>/ledger.md` when present, writes FILE
    and prints `wrote FILE`. Without `-o` it is a usage error.

- **The page:**
  - a single HTML document with inline CSS and inline SVG only. There is no `<script>`, and no
    `http://`, `https://` or `src=` anywhere;
  - `<title>` is the show's id turned into words, at most four words, such as `Hi Ibiza
    Pulso`;
  - colour tokens on `:root`, redefined under `@media (prefers-color-scheme: dark)` guarded
    by `:root:not([data-theme="light"])` and again under `:root[data-theme="dark"]`;
  - an explicit `body` background, and a single-column layout readable at 360 px;
  - palette swatches draw the show's real hex colours in both themes;
  - all text is escaped with `html.escape`;
  - the labels are pt-BR (the headings in spec A9);
  - the night's prose comes from `story`, `identity` intents and the tracks' `story`.
- **The section contents** are spec A9's:
  - the colour score is one SVG ribbon per zone (movers, Vorlanes, lustre), with one `rect`
    per section in its palette colour, x on the set clock;
  - the arc chart is one SVG with three polylines: target (owner energy), E_music and
    E_light per minute.

- [ ] **Step 1: Write the failing tests:**
  - `test_book_has_every_section`;
  - `test_book_is_deterministic`;
  - `test_book_has_no_external_reference_and_no_script`;
  - `test_book_has_theme_tokens_and_a_title`;
  - `test_book_escapes_text` (a track titled `&ME — <Teste> 'x'`: `&amp;ME` and `&lt;Teste&gt;`
    appear, the raw `<Teste>` does not);
  - `test_latest_run_reads_decisions_and_later`;
  - `test_book_prints_the_ledger_decisions`;
  - `test_book_without_a_ledger_leaves_the_decisions_out`;
  - CLI: `test_book_writes_the_file` and `test_book_needs_an_output`.
- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; expect PASS.**
- [ ] **Step 5: Docs. Commit:** `Add nextrack_show.py book: the book of the night`.

### Task 16: Hï Ibiza's identity and advice, the remaining docs, final verification

**Files:**
- Modify: `lightshows/shows/hi-ibiza-pulso/show.yml`, `CLAUDE.md`, `scripts/README.md`,
  `lightshows/shows/README.md` (the loop and "Writing a show" mention `brief`, `compare` and
  `book`)

- [ ] **Step 1: Measure first.** Run `uv run scripts/nextrack_show.py report hi-ibiza-pulso
  --section identity,variety,arc` and note the measured shares.
- [ ] **Step 2: Declare the identity in `show.yml`**, in pt-BR intents from the plan's words:

```yaml
identity:
  arc: single-peak
  signatures:
    - name: azul-espaco
      intent: 'O azul é o espaço da noite: os feixes das movings moram nele.'
      is: {movers.colour: [azul-gelo, azul-profundo]}
      share: {min: 0.7}
    - name: coracao
      intent: 'O vermelho é o coração, no lustre, no centro da sala.'
      is: {hue.colour: [carmim, vermelho]}
      share: {min: 0.6}
```

  Keep the minimums at what the plan intends, even if the measure is below them. The
  `signatures` advice then shows the gap.
- [ ] **Step 3: Add the advice** next to `bridges: {max: 16}`:

```yaml
  signatures: true
  static-run: {max_seconds: 120}
  neighbours-differ: {max_similarity: 0.85}
  distinct-drops: {top: 0.25}
  drop-contrast: {top: 0.25, min_change: 2}
  main-drop: true
  follows-track: {min_rho: 0.3, max_lag: 1}
  follows-set: {min_rho: 0.5, max_headroom: 0.8}
  phrase-aligned: {min_share: 0.9}
```

- [ ] **Step 4: Verify.**
  - `uv run scripts/nextrack_show.py build hi-ibiza-pulso --check` exits 0; the advice
    count is reported in the task report.
  - `uv run scripts/nextrack_show.py book hi-ibiza-pulso -o <scratch>/book.html` writes the
    book. Open it, check it renders, and attach the path to the task report.
  - `uv run scripts/nextrack_show.py brief sets/hi-ibiza-pulso.md` is at most 16 000
    characters.
- [ ] **Step 5: Docs.**
  - In `CLAUDE.md`'s Commands and tool bullets, add `brief`, `compare`, `book` and `report
    --track/--section` to the show tool, and `upgrade` to the map tool.
  - In the manual, the loop step 4 names `report --track` and `zoom`, and "Writing a show"
    names `brief` first and `book` last.
- [ ] **Step 6: Final checks.** `uv run scripts/check_repo.py` and `uv run pytest` both pass;
  report the real output.
- [ ] **Step 7: Commit:** `Declare Hi Ibiza's identity and the new advice`.
