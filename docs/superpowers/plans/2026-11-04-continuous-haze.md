# Continuous Haze and Compliance Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Haze becomes a room setting (fan and fog fixed at the rig's `level` over every compiled track), and three new commands (`status`, `restore`, `accept`) show and settle which tracks are compliant.

**Architecture:** `lightshow.py` loses the `haze` layer and gains one whole-track haze pass that runs after the sections, plus two helpers (`haze_tracks`, `haze_problem`). Then `nextrack_lights.py` changes in four places: its guard allows exactly that haze change outside the sections, `apply` keeps a copy of every output and honours an accepted hand-edited version, `restore`/`accept` move between those versions, and `status` recomputes compliance from the repo and the project. `check_repo.py` exposes its tracklist and track-matching helpers for `status`.

**Tech Stack:** Python 3 via `uv run`, PyYAML, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-04-continuous-haze-design.md`. Read it before any task.

## Global Constraints

- Nothing committed may contain sensitive configuration or machine paths (owner's rule). That means no `/mnt/...`, `C:\Users\...`, user names, real project or venue paths, scratchpad or `/tmp` paths. Before each commit, run `git diff --cached | grep -nE "/mnt/|Users[\\/]|/tmp/|scratchpad|AppData|OneDrive"` and expect no output. Grep for the owner's user name too, but type it at the prompt: it never goes into a repo file, this plan included. Test fixtures already carry the public venue and node names; add no new ones.
- Tests use synthetic scripts and projects under `tmp_path` only; never the real SoundSwitch project. Audio is never committed.
- Run everything with `uv run` from the worktree root; never pip or poetry.
- Commit subjects are imperative English sentences (`Add …`, `Make …`) with no `feat:` prefix. Every commit message ends with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Language: pt-BR for choreography `story`/`budget`/`intent`, show-plan prose and the simulator note; English for keys, code, CLI output, `docs/` and READMEs.
- Write commands stay dry-run unless `--apply`; `--apply` refuses while SoundSwitch runs (`soundswitch_running()`).
- Haze cue text, exactly: `haze at {level:g}, whole track: experimental: confirm the machine reacts` (uses the existing `HAZE_WARNING`).
- The rig level today is `0.5` and is the same for fan and fog.
- Definition of done for every task: `uv run pytest` and `uv run scripts/check_repo.py` pass.

## Review Focus

1. A rig `level` written as a YAML boolean (`level: true`) must be refused, not read as 1. Test in Task 1.
2. A section that ends after the script's last event: the haze must still cover everything, so the whole-track end is computed after the sections. Test in Task 2.
3. Haze nodes that carry colour or strobe blocks in the base: the haze pass keeps them, `check(out)` stays clean, the guard accepts that, and it still refuses a changed haze colour outside the sections. Tests in Task 3.
4. An apply record whose `applied/` copy is missing (deleted by hand): `restore` refuses with a message naming the missing copy and does not crash. Test in Task 4.
5. `status` meeting an invalid choreography, or one whose GUID is not in the project: the row gives the reason and the command goes on. Test in Task 5.

---

### Task 1: The rig's haze level

**Files:**
- Modify: `scripts/lightshow.py` (`FIXTURE_KEYS`, `_fixture_problems`, new `haze_level`)
- Modify: `lightshows/rig.yml:9-10`
- Modify: `lightshows/README.md` (rig keys paragraph near line 52), `docs/rig.md:58` and `:81-82`
- Test: `tests/test_lightshow_model.py`

**Interfaces:**
- Produces: `lightshow.haze_level(rig: Rig) -> float | None`. It returns the `level` of the rig's first `kind: haze` fixture as a float, or None when the rig has none.

- [ ] **Step 1: Write the failing tests** in `tests/test_lightshow_model.py` (the existing fixture `rig_data()` loads the real rig as a dict):

```python
def test_rig_haze_needs_a_level():
    data = rig_data(); del data["fixtures"]["haze"]["level"]
    assert "fixture 'haze': missing key 'level'" in ls.problems_rig(data)

@pytest.mark.parametrize("level", [0, -0.1, 1.5, "half", True])
def test_rig_haze_level_must_be_in_range(level):
    data = rig_data(); data["fixtures"]["haze"]["level"] = level
    assert any("level" in p for p in ls.problems_rig(data))

def test_rig_level_only_on_haze():
    data = rig_data(); data["fixtures"]["mover-ne"]["level"] = 0.5
    assert any("level" in p for p in ls.problems_rig(data))
```

Then extend `test_load_rig_reads_the_real_rig` with `assert ls.haze_level(rig) == 0.5` and add `assert ls.haze_level(ls.Rig({}, ["colour"], "x", 0.6)) is None`.

- [ ] **Step 2: Run** `uv run pytest tests/test_lightshow_model.py -q`. Expected: the new tests FAIL (unknown key `level`; `haze_level` not defined).

- [ ] **Step 3: Implement.** Add `"level"` to `FIXTURE_KEYS`. In `_fixture_problems`, a `kind: haze` fixture without `level` yields `f"{where}: missing key 'level'"`. A `level` that is not `_is_num` with `0 < level <= 1` yields `f"{where}: level {_show(v)} is not a number in (0, 1]"`, and `_is_num` already rejects bools. A `level` on another kind yields `f"{where}: level is only for kind haze"`. Add `haze_level`.

- [ ] **Step 4: Data and docs.**
  - In `rig.yml`, add `level: 0.5` to the haze entry. The comment on line 9 reads `O nome do nó da máquina de haze (neblina) começa com um espaço; os canais têm espaço duplo.`, and a comment `# level: ventilador e neblina fixos nesse nível a música toda` goes beside `level`.
  - `lightshows/README.md`: add `level` to the fixture key list. One sentence: the haze fixture's `level` (0-1] holds fan and fog over the whole of every compiled track.
  - `docs/rig.md`: the haze machine makes a constant thin mist at the rig's `level`. Replace the "fog burst" note with: both channels are intensity channels, so the level is an intensity key; whether the machine reacts is X10.

- [ ] **Step 5: Run** `uv run pytest -q && uv run scripts/check_repo.py`. Expected: all pass, `ok: …`.

- [ ] **Step 6: Commit** with the subject `Give the rig a haze level`.

---

### Task 2: Haze leaves the sections and holds the level over the whole track

**Files:**
- Modify: `scripts/soundswitch_format.py` (add `script_end`, moved from `nextrack_lights.py:231-241`)
- Modify: `scripts/nextrack_lights.py` (replace the local `script_end` with `script_end = ssf.script_end`)
- Modify: `scripts/lightshow.py` (`LAYERS`, `SCALARS`, `_haze`, `_MAPPING_CHECKS`, `problems_choreography`, `compile_choreography`, `_compile_section`, remove `_compile_haze` and `SECONDS_RE`, add `haze_tracks`, `haze_problem`, `_compile_haze_whole`)
- Modify: `lightshows/tracks/marshmello-x-bastille-happier.yml`, `lightshows/sets/2026-10-31-halloween-em-casa.md`
- Modify: `lightshows/README.md` (vocabulary table line 96, the `haze` note at 113, manual cues at 180), `scripts/lightshow_sim.html:52`
- Test: `tests/test_lightshow_model.py`, `tests/test_lightshow_compile.py`, `tests/test_nextrack_lights.py:182`

**Interfaces:**
- Consumes: `haze_level(rig)` (Task 1).
- Produces:
  - `soundswitch_format.script_end(script: TrackScript, floor: int = 0) -> int`, the same body as today's `nextrack_lights.script_end`.
  - `lightshow.compile_choreography(choreo, script, rig, venues, presets, *, duration_ms: int = 0) -> tuple[TrackScript, list[ManualCue]]`.
  - `lightshow.haze_tracks(script: TrackScript, rig: Rig, venues: list[VenueInfo]) -> list[Track]`: the fan track, then the fog track, of the rig's haze fixture in the script's venue. It returns only the ones present, and `[]` without a haze fixture.
  - `lightshow.haze_problem(script, rig, venues, duration_ms: int = 0) -> str | None`. It returns None when `haze_tracks` is empty or every haze track has blocks exactly `[Span(0, E)]` and a non-empty intensity lane whose keys all equal `level_of(haze_level(rig))`, with `E = ssf.script_end(script, duration_ms)`. Otherwise it returns a message that starts with `haze node <id>`.

- [ ] **Step 1: Failing vocabulary tests** (`tests/test_lightshow_model.py`):
  - Remove every `haze` entry from `test_bad_layer_values_are_problems` and `test_good_layer_values_are_clean`, and `("_haze", {})` from `test_module_level_schema_checks_are_not_shadowed`.
  - Add `test_a_section_with_haze_is_a_problem`: `with_section(haze="on")` has a problem containing `"haze"`.
  - Add `test_a_choreography_without_sections_is_clean`: `ls.problems_choreography(choreo(sections=[])) == []`.
  - Add `test_sections_must_be_a_list`: `sections="x"` has a problem.
  - Add to `test_plan_front_matter`: a budget with `haze: [x]` has a problem containing `"budget key 'haze'"`.

- [ ] **Step 2: Failing compile tests** (`tests/test_lightshow_compile.py`). Delete `test_haze_burst_is_experimental` and drop `haze="on"` from the section at line 209. Then add:

```python
L = ls.level_of(0.5)

def flat_haze(out, end):
    for node in (1935, 1936):
        trk = ssf.track(out, node)
        assert trk.blocks.items == [ssf.Span(0, end)]
        assert {k.level for k in intensity(trk).keys} == {L}

def test_haze_holds_the_level_over_the_whole_track(room):
    script = room()                                     # haze nodes follow Main; give 1936 own keys
    fog = ssf.track(script, 1936); fog.lanes[0].keys = [Key(5000, FULL), Key(9000, 0)]
    fog.blocks = ssf.Section(1, [ssf.Span(5000, 9000)])
    out, cues = compile_(script, section(3, 4, movers="off"))
    flat_haze(out, ssf.script_end(script))
    assert [(c.bar, c.time_ms, c.fixture, c.what) for c in cues] == [
        (1, 0, "haze", "haze at 0.5, whole track: experimental: confirm the machine reacts")]
    assert ls.haze_problem(out, RIG, VENUES) is None

def test_haze_stays_flat_under_a_hue_section(room):          # materialise must not leak in
    out, _ = compile_(room(), section(1, 8, hue="pulse"))
    flat_haze(out, ssf.script_end(out))

def test_haze_covers_a_section_past_the_script_end(room):    # Review Focus 2
    out, _ = compile_(room(), section(200, 201, movers="off"))   # room() ends at 400_000 ms
    flat_haze(out, ssf.script_end(out)); assert ssf.script_end(out) >= ms(202) - 1

def test_haze_end_honours_the_track_length(room):
    out, _ = ls.compile_choreography(choreo(section(1, 2)), room(), RIG, VENUES, PRESETS,
                                     duration_ms=500_000)
    flat_haze(out, 500_000)

def test_no_sections_skips_the_grid_checks(room):
    many = tuple((158 + i * 1000, 100.0 + i) for i in range(9))      # 9 anchors
    script = room(tempo=many)
    out, _ = ls.compile_choreography(choreo(grid={"bpm": 90, "downbeat": "0:01.000"}),
                                     script, RIG, VENUES, PRESETS)
    changed = [t.node for t, b in zip(ssf.tracks(out), ssf.tracks(script)) if t != b]
    assert changed == [1935, 1936] and out.main == script.main
    with pytest.raises(ls.CompileError):
        compile_(script, section(1, 2))

def test_a_rig_without_haze_writes_none(room):
    rig = ls.Rig({k: f for k, f in RIG.fixtures.items() if f.kind != "haze"}, RIG.matrix_rows,
                 RIG.zone_order, RIG.white_max)
    script = room()
    out, _ = ls.compile_choreography(choreo(section(1, 2)), script, rig, VENUES, PRESETS)
    assert ssf.track(out, 1936) == ssf.track(script, 1936)
```

`choreo()` must accept zero sections; it already does (`*sections`). Update `test_happier_compiles_on_a_synthetic_script` to expect `[(c.bar, c.fixture) for c in cues] == [(1, "haze")]`. In `tests/test_nextrack_lights.py:182` the assertion stays: the test project has no haze nodes, so the cue is the "skipped" one, and its fixture is still `"haze"`.

- [ ] **Step 3: Run** `uv run pytest tests/test_lightshow_model.py tests/test_lightshow_compile.py -q`. Expected: the new tests FAIL.

- [ ] **Step 4: Implement in `scripts/soundswitch_format.py` and `scripts/lightshow.py`.**
  - Move `script_end` into `soundswitch_format.py`.
  - Set `LAYERS = ("movers", "matrix", "white", "uv", "strobe", "hue")`. Remove `SCALARS["haze"]`, `_haze`, `_MAPPING_CHECKS["haze"]`, `_compile_haze`, its call in `_compile_section` and `SECONDS_RE`.
  - In `problems_choreography`, `sections` must be a list (message `sections must be a list`), and empty is fine.
  - In `compile_choreography`, call `_check_grid` only when `choreo.sections` is non-empty. After the section loop, compute `end = ssf.script_end(job.script, duration_ms)`, then run `_compile_haze_whole(job, haze_level(job.rig), end)`, then `check(out)`.
  - `_compile_haze_whole` sets each haze track's intensity lane keys to exactly `[Key(0, L), Key(end, L)]`, and its blocks to `Section(ver, [Span(0, end)])`, keeping the existing section's `ver` (1 when absent). It leaves the track's other parts alone and appends the one cue `ManualCue(1, 0, "haze", f"haze at {level:g}, whole track: {HAZE_WARNING}")`.
  - Without a haze fixture the cue is `("haze", "haze, whole track: the rig has no haze; not compiled")`. When the venue lacks a channel, it is `("haze", f"haze, whole track: skipped {'; '.join(fixture.missing)}")`.
  - Update the `compile_choreography` docstring.

- [ ] **Step 5: Data.** Happier YAML:
  - Remove line 95 (`haze: {burst: 6s}`).
  - In the line 11 sentence, `A ponte é contemplativa: haze, movings lentas e o centro aceso.` becomes `A ponte é contemplativa: movings lentas e o centro aceso, dentro da neblina fina que fica a música toda.`
  - Line 14: `nenhum UV, um haze.` becomes `nenhum UV; a neblina fica fixa no nível do rig.`
  - Line 91: `Contemplativo; haze, movings lentas` becomes `Contemplativo; movings lentas`.

  Halloween plan:
  - Delete line 8 (the `haze:` budget line).
  - `Sem strobe e sem haze.` (lines 29 and 35) becomes `Sem strobe.`
  - Line 40: `Haze, movings revezando no haze,` becomes `Movings revezando na neblina,`.
  - Line 47: `haze no uivo. No Thriller,` becomes `No Thriller,`.
  - Line 51: `no drop, haze e as movings revezando` becomes `no drop, as movings revezando`.
  - Line 52: `o haze do apagão vira neblina do mar;` becomes `no apagão, a neblina de sempre vira o mar;`.
  - Line 55: `Escuro e haze na introdução;` becomes `Escuro na introdução;`.
  - Rule 3 (lines 102-104) becomes:

```
3. **Strobe fica nos picos e momentos.** Strobe: `hit` nos picos 2 e 4, `roll` só no
   `final`. A neblina (haze) não é efeito: fica fixa no nível do rig a noite toda, em toda
   música; experimental até a máquina responder.
```

- [ ] **Step 6: Docs.**
  - `lightshows/README.md`: drop the `haze` row and note from the vocabulary. Add a short "Haze" paragraph: constant at the rig's `level` over the whole of every compiled track, not a section layer, one experimental cue per compile. A choreography may have `sections: []` (the autoscript plus the haze, also for tracks with more than 8 tempo anchors). Update the manual-cue list.
  - `scripts/lightshow_sim.html:52`: in the pt-BR note, `a fumaça vem só do canal de fumaça da máquina` becomes `a neblina (haze) vem só do canal de fog da máquina e, num script compilado, fica constante no nível do rig`.

- [ ] **Step 7: Run** `uv run pytest -q && uv run scripts/check_repo.py`. Expected: all pass.

- [ ] **Step 8: Commit** with the subject `Hold the haze at the rig level over the whole track`.

---

### Task 3: The guard allows exactly the constant haze outside the sections

**Files:**
- Modify: `scripts/nextrack_lights.py` (`_compile_checked`, `cmd_compile`, `cmd_apply`, `cmd_render`, `sim_data`)
- Modify: `tests/conftest.py` (`make_project` gains `haze: bool = False`)
- Modify: `scripts/README.md` (safety model)
- Test: `tests/test_nextrack_lights.py`

**Interfaces:**
- Consumes: `haze_tracks`, `haze_problem`, the `compile_choreography(..., duration_ms=)` keyword (Task 2).
- Produces:
  - `_compile_checked(choreo, base, venues, presets, rig, duration_ms: int = 0) -> tuple[bytes, list]`. Every caller passes `ref.duration_ms or 0`, and `sim_data(..., duration_ms=...)` passes it on to `compile_choreography`.
  - `make_project(haze=True)` adds to the venue the group ` Lig Light LL-HZ600K` (id 1934), with children `Main -  Lig Light LL-HZ600K` (1935) and `Main -  Lig Light LL-HZ600K - 2` (1936). Note the double space, as in `rig.yml`.
  - In `tests/test_nextrack_lights.py`, `_happier_project(make_project, make_script, haze=False)` replaces the first script with `make_script()`, as today. With `haze=True` it calls `make_project(haze=True)` and appends tracks 1935 and 1936 to that script: keys `[Key(0, FULL), Key(8000, 0)]` and no own block, so they follow Main as in the autoscript. `node_lists` grows to one entry per track. Every new test below uses `_happier_project(..., haze=True)`.

- [ ] **Step 1: Failing tests** (`tests/test_nextrack_lights.py`). All of them use `_happier_project(..., haze=True)`, Happier's choreography from `_choreo_for_project`, and `idle`. `_compiled()` passes `duration_ms=16000`, as apply does.
  - `test_apply_writes_the_constant_haze`: after `--apply --accept-resize`, `ls.haze_problem(project script, rig, venues, 16000) is None`, and the exit code is 0.
  - `test_the_guard_refuses_haze_that_is_not_flat`: monkeypatch `nl.ls.compile_choreography` (as `_meddle` does) to set node 1936's last key to `level_of(0.4)`. Apply exits 1, stderr contains `haze node 1936`.
  - `test_the_guard_still_checks_other_nodes_outside_sections`: the existing `test_a_change_outside_every_section_is_refused` must still pass with `haze=True`. Parametrize it over `haze` in `(False, True)`.
  - `test_haze_colour_blocks_survive_and_are_checked` (Review Focus 3): give node 1936 a colour block `ColourBlock(0, 16000, 0xFF00FF00, 0, 0xFF00FF00, 0)` and a strobe block inside it in the project script. Apply succeeds, and the block is unchanged in the output. With `_meddle` changing that colour outside the sections, apply exits 1 and stderr contains `node 1936`.

- [ ] **Step 2: Run** `uv run pytest tests/test_nextrack_lights.py -q`. Expected: the new tests FAIL. Without the change, the guard refuses the haze edit outside the sections.

- [ ] **Step 3: Implement.**
  - In `_compile_checked`, compute `haze_ids = {t.node for t in ls.haze_tracks(again, rig, venues)}`.
  - In the `pairs` loop, for a node in `haze_ids`, compare `_with_base_intensity(c, b)` against `b` instead of `c`. `_with_base_intensity(out: ssf.Track, base: ssf.Track) -> ssf.Track` is a deep copy of `out` with `base`'s intensity lane and `blocks`.
  - Then refuse with `f"the compiled script's haze is not constant: {problem}"` when `ls.haze_problem(again, rig, venues, duration_ms)` is not None.
  - Thread `duration_ms` through `cmd_compile`, `cmd_apply`, `cmd_render` and `sim_data`.

- [ ] **Step 4: Docs.** In the `scripts/README.md` safety model, add one bullet: outside the sections only the haze fixture's fan and fog may change, and only to the rig's `level` over the whole track (one block from 0 to the end, every key at the level). Every other check is unchanged.

- [ ] **Step 5: Run** `uv run pytest -q && uv run scripts/check_repo.py`. Expected: all pass.

- [ ] **Step 6: Commit** with the subject `Let apply write the constant haze outside the sections`.

---

### Task 4: The official version, `restore` and `accept`

**Files:**
- Modify: `scripts/nextrack_lights.py` (`_plan_base`, `cmd_apply`, `_commit`, new `cmd_restore`, `cmd_accept`, `_copy_path`, `_backup`, `_official`, parser)
- Modify: `scripts/README.md` (commands, safety model, undo paragraph)
- Test: `tests/test_nextrack_lights.py`

**Interfaces:**
- Consumes: the apply path of Task 3.
- Produces:
  - `_copy_path(project, guid: str, kind: str) -> Path`, which is `<project parent>/nextrack-backups/<kind>/{GUID}.ssfile` for `kind` in `("applied", "accepted")`.
  - `_official(entry: dict) -> str | None`, which is `entry.get("accepted") or entry.get("applied")`.
  - `_backup(root: Path, target: Path, current: bytes) -> Path`: the timestamped-folder backup, extracted unchanged from `_commit`.
  - `state.json` entries gain the optional `"accepted": <sha256>`.
  - CLI: `restore <track> [--apply]`, `accept <track> [--apply]`, and `apply … --drop-hand-edits`.

- [ ] **Step 1: Failing tests** (`tests/test_nextrack_lights.py`). Each one starts with one successful `--apply --accept-resize` on `_happier_project(..., haze=True)`. "Edit" below means a hand edit: parse `_target(project)`, change the level of one Mover 1 intensity key, and serialise it back.
  - `test_apply_keeps_a_copy_of_its_output`: `_copy_path(..., "applied")` bytes equal the project file.
  - `test_an_edited_track_is_refused_with_restore_and_accept`: after the edit, apply exits 1 and stderr contains `restore` and `accept`.
  - `test_restore_dry_run_writes_nothing` and `test_restore_puts_the_official_version_back`: with `--apply`, the project file equals the applied copy, a backup holds the edited bytes, and stdout has `backup:` and `restore:` lines.
  - `test_restore_refuses_when_nothing_changed`, `test_restore_refuses_without_an_apply_record`, `test_restore_refuses_while_soundswitch_runs`.
  - `test_restore_names_a_missing_copy` (Review Focus 4): delete the applied copy. `restore --apply` exits 1 and stderr names `applied`.
  - `test_accept_makes_the_edit_official`: after `accept --apply`, the project file is untouched, the accepted copy equals it, `state.json` has `accepted`, and a following `apply --apply --accept-resize` exits 1 with `--drop-hand-edits` in stderr.
  - `test_accept_dry_run_writes_nothing`, `test_accept_refuses_without_changes`, `test_accept_refuses_while_soundswitch_runs`.
  - `test_restore_after_accept_restores_the_accepted_version`: edit again, then restore. The project file equals the accepted copy.
  - `test_drop_hand_edits_applies_and_clears_accepted`: `apply --apply --accept-resize --drop-hand-edits` exits 0, `accepted` is gone from `state.json`, and the accepted copy still exists. The dry run's stdout has one line containing `hand edits`.

- [ ] **Step 2: Run** `uv run pytest tests/test_nextrack_lights.py -q`. Expected: the new tests FAIL.

- [ ] **Step 3: Implement.**
  - **`_plan_base`:** compare the current file with `_official(entry)` rather than `entry["applied"]`. The refusal reads `the project file was edited in SoundSwitch since the last apply: restore puts the official version back, accept makes the edited file official; --adopt-current keeps the edits as the new base`.
  - **`cmd_apply` with `entry["accepted"]` and no `--adopt-current`:** the dry run prints `this apply replaces the hand edits accepted for this track; their copy stays in <path>`. `--apply` without `--drop-hand-edits` is refused with a message naming the flag.
  - **`_commit`:** also writes `_copy_path(..., "applied")` atomically, and writes the state entry as `{"base", "applied"}` (which clears `accepted`). Extract `_backup` from it.
  - **`cmd_restore`:**
    - Refusals: no apply record; the official copy is missing (the message names the path); the copy's hash differs from `_official(entry)`; the project file already is official.
    - The dry run prints what would be restored.
    - `--apply` checks `soundswitch_running()`, calls `_backup`, then replaces the file through a `.tmp` and `os.replace`, and prints `wrote`, `backup:` and `restore:` as `_commit` does. `state.json` is not changed.
  - **`cmd_accept`:**
    - Refusals: no apply record; the file already is official; SoundSwitch running with `--apply`.
    - `--apply` writes the accepted copy and `state[guid]["accepted"]`; the project file is never written.
  - **Parser:** add the `restore` and `accept` subparsers (with `track` and `--apply`) and `--drop-hand-edits` on `apply`, then register both in the dispatch dict.

- [ ] **Step 4: Docs.**
  - `scripts/README.md` commands block: `restore` and `accept` examples.
  - Safety model: the official version, the `applied/` and `accepted/` folders, `--drop-hand-edits`.
  - Undo paragraph: `restore` is the way back from hand edits.

- [ ] **Step 5: Run** `uv run pytest -q && uv run scripts/check_repo.py`. Expected: all pass.

- [ ] **Step 6: Commit** with the subject `Add restore and accept for hand-edited tracks`.

---

### Task 5: `status`

**Files:**
- Modify: `scripts/check_repo.py` (public `tracklist_entries`, `same_track`, `set_block_ids`; `_resolves` uses `same_track`)
- Modify: `scripts/nextrack_lights.py` (`cmd_status`, `track_status`, parser)
- Modify: `scripts/README.md` (commands)
- Test: `tests/test_nextrack_status.py` (new), `tests/test_check_repo.py`

**Interfaces:**
- Consumes: `_compile_checked` (Task 3), `_official` and `_copy_path` (Task 4), `ls.haze_tracks` and `ls.haze_problem` (Task 2).
- Produces:
  - `check_repo.tracklist_entries(block: Block) -> list[tuple[int, str, str]]`: `(line, artist, title)` per `TRACK_LINE_RE` match under `## Tracklist`, in order.
  - `check_repo.same_track(artist_a: str, title_a: str, artist_b: str, title_b: str) -> bool`: today's `_resolves` predicate for one pair.
  - `check_repo.set_block_ids(text: str) -> list[str]`: the block ids of every `../blocks/<id>.md` link, in order, duplicates kept.
  - `nextrack_lights.track_status(project, guid: str, choreo_path: Path | None, rig, repo_root: Path) -> dict`. It returns the keys `track` (str), `choreography` (bool), `applied` (bool or a reason str), `haze` (bool or None when the venue has no haze), `note` (str or None) and `compliant` (bool).
  - CLI: `status [--repo PATH] [--rig PATH] [--block ID | --set PATH]`, with `--repo` defaulting to this repo's root.

- [ ] **Step 1: Failing helper tests** (`tests/test_check_repo.py`): `same_track` true for `("Skank, Dubdogz", "Algo Parecido (Extended)")` against `("Skank", "Algo Parecido")`, and false for a different title. `tracklist_entries` returns line numbers and pairs for a two-line tracklist. `set_block_ids` reads `[A](../blocks/a.md) … [B](../blocks/b-c.md)` as `["a", "b-c"]`.

- [ ] **Step 2: Failing status tests** (`tests/test_nextrack_status.py`). They use the Task 3 `_happier_project(..., haze=True)` setup (move the helper to `conftest.py` so both test files share it) and a repo built under `tmp_path`: `build_mini_repo` plus pool entries for `Pedro Sampaio — Dançarina` and `Chiclete com Banana — Voa Voa`, `lightshows/rig.yml` copied from the real repo, and `lightshows/tracks/` holding the choreography from `_choreo_for_project`. Each test asserts on the row returned by `track_status` and, once, on the printed table.
  - `test_no_choreography`: choreography False, compliant False.
  - `test_never_applied`: applied False, haze False.
  - `test_applied_and_current_is_compliant`: after apply, everything True, note None, and the last line is `1 of 1 tracks compliant`. When unfiltered, it is followed by `1 more track in the project has no choreography`.
  - `test_hand_edit_keeps_compliance_with_a_note`: edit Mover 1, then compliant True, note `edited in SoundSwitch after the apply`.
  - `test_hand_edit_that_breaks_the_haze`: set a fog key to 0, then haze False, compliant False.
  - `test_accepted_edits_note`: after `accept --apply`, note `hand edits accepted`.
  - `test_yaml_change_after_apply`: drop the last section from the choreography file, then applied False.
  - `test_rig_level_change`: a rig copy with `level: 0.4` passed through `--rig`. Then applied False and haze False.
  - `test_compile_refusal_is_the_reason`: the choreography's grid changed to 90 BPM, so applied is a str containing `grid`.
  - `test_invalid_choreography_and_unknown_guid` (Review Focus 5): the rows carry `invalid choreography: …` and `its GUID is not in the project`, and the command exits 0.
  - `test_block_filter`: a block whose tracklist has a line found only through its choreography (the pool artist differs from the track map's), a line found nowhere (`no SoundSwitch script found under this name`), and the two test tracks. The rows come out in tracklist order.
  - `test_set_filter`: a set linking that block twice gets two groups headed by the block id.
  - `test_status_writes_nothing`: the project folder's and backups' files have the same hashes and mtimes before and after.

- [ ] **Step 3: Run** `uv run pytest tests/test_nextrack_status.py tests/test_check_repo.py -q`. Expected: the new tests FAIL.

- [ ] **Step 4: Implement.**
  - The `check_repo` helpers come first; the existing rules keep their findings, and `uv run pytest tests/test_check_repo.py` stays green.
  - **`track_status`:**
    - **applied:** with no state entry or no base copy, it is False. Otherwise it compiles with `_compile_checked(choreo, base, venues, presets, rig, duration)`: a `Refused` gives its message, and otherwise it is `sha(data) == entry["applied"]`.
    - **haze:** None when `ls.haze_tracks` is empty, else `ls.haze_problem(project script, rig, venues, duration) is None`.
    - **note:** from `_official(entry)` against the project file's hash, and `"accepted" in entry`.
  - **Choreographies:** they come from `<repo>/lightshows/tracks/*.yml`, each validated with `ls.problems_choreography` (the first problem becomes the reason).
  - **Matching lines:** a tracklist line is matched first to a choreography whose `track:` splits on ` — ` into a pair that `same_track` accepts, then to the track map through `project.resolve` (a `LookupError` mentioning several matches gives `several scripts: <guid8>, …`).
  - **Output:** columns `track`, `choreography`, `applied`, `haze`, `compliant`, `note`, with values `yes`, `no`, `—`, or the reason. The exit status is 0.

- [ ] **Step 5: Docs.** In `scripts/README.md`, add a `status` example and a short "Compliance" paragraph: the three conditions, the note, and that `status` is read-only and works with SoundSwitch open.

- [ ] **Step 6: Run** `uv run pytest -q && uv run scripts/check_repo.py`. Expected: all pass.

- [ ] **Step 7: Commit** with the subject `Add a status command for compliant tracks`.

---

### Task 6: The skill, the experiments and a final sweep

**Files:**
- Modify: `.claude/skills/lightshow/SKILL.md`
- Modify: `docs/soundswitch/experiments.md` (X10 row)

**Interfaces:**
- Consumes: the commands and behaviours of Tasks 1-5.

- [ ] **Step 1: Skill.**
  - Remove haze from the budget tally (line 69: `(no strobe or UV)`; line 71: drop `haze:` from the grep), from the proposal's layer list (line 102) and from the directing principles. The line-84 sentence becomes: `The haze is a constant thin mist at the rig's level in every compiled track, so the beams always read a little; no section decides it.`
  - In step 1, the "no script: stop" bullet stays. The "more than 8 tempo anchors" paragraph of step 5 becomes: tell the owner the lights stay on the autoscript, then write a choreography with `sections: []` so the haze still applies.
  - Add to step 2 or 4: a track the owner wants left on the autoscript also gets `sections: []`.
  - Step 6 gains a step 5: run `status` for the track (or its block) and report the verdict in pt-BR. When `status` notes `edited in SoundSwitch after the apply`, ask the owner: `restore` or `accept`, dry run first, either only on their word.
  - The flags paragraph and the red-flag table gain `--drop-hand-edits`: it replaces accepted hand edits, so the owner's explicit yes comes first.
  - The checklist's item 6 adds `status`.

- [ ] **Step 2: Experiments.** Row X10: the question becomes `Does the haze machine react to a constant level on its fan and fog nodes (both at the rig's level, 0.5 today)?`. The steps: compile any track, apply it on a scratch copy, play with the machine on and watch the mist and channels 504-505. "What the answer changes": a yes removes the experimental cue, a no means the level must be set on the machine.

- [ ] **Step 3: Sweep.**
  - `grep -rn -iE "haze|fumaça" --include=*.md --include=*.yml --include=*.py --include=*.html . | grep -v -E "^./(\.venv|docs/superpowers)"`. Every hit either describes the constant mist or is code or tests for it, and no hit mentions `burst`, `haze:` as a layer, or haze in a budget.
  - Run the sensitive-path grep from Global Constraints on the whole branch: `git diff origin/main --stat` then `git diff origin/main -- . ':!docs/superpowers/plans' | grep -nE "/mnt/|Users[\\/]|/tmp/|scratchpad|AppData|OneDrive"`. Expected: no output. The plan is excluded because it quotes the pattern itself.

- [ ] **Step 4: Run** `uv run pytest -q && uv run scripts/check_repo.py`. Expected: all pass, with the real numbers reported.

- [ ] **Step 5: Commit** with the subject `Teach the lightshow skill the constant haze and status`.
