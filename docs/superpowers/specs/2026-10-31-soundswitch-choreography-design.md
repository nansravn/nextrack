# SoundSwitch choreography — design

- **Date:** 2026-10-31
- **Status:** approved in advance. On 2026-10-31 (~01:00) the owner approved an overnight plan
  (decode → analyse → demo → this spec → plan → subagent-driven build) and delegated every
  remaining design call to the tech lead. Each call is in the [decision ledger](#decision-ledger)
  with its reason and what it costs if wrong.
- **Goal:** let the owner direct the light show the way they direct the music: describe, per track
  and across the whole night, what the lights should do, and have Claude turn that into edits of
  the SoundSwitch scripts, on top of SoundSwitch's autoscript.

## Problem

The owner DJs on rekordbox with SoundSwitch driving the lights. SoundSwitch's autoscript gives
every track a competent but generic show: on the Happier test track it moves both moving heads to
a random position preset every 2 bars, colours them cyan in the loud parts, runs the same top-down
row chase on both multi-cell bars in every drop, and lights the white strip with the colours 80% of
the time it is on. Nothing tells a story, nothing builds incrementally into a drop, and nothing is
paced across the night. Editing by hand in SoundSwitch is slow, and there is no public format or
API for the per-track scripts (`.ssfile`).

On 2026-10-31 a controlled test showed the format is editable: zeroing one mover's intensity in
SoundSwitch changed exactly 8 bytes (two keyframe values), with no checksum, and a file patched by
us the same way loaded and played correctly in SoundSwitch.

## What the owner asked for

From the brainstorm (owner's words, condensed):

- **Tell a story through each track**: give each fixture a role per phrase, alternate what each
  light is doing per stage of the music.
- **Subtract**: sometimes delete what the autoscript did; darkness is an effect.
- **Build incrementally** into the drop instead of switching everything on at once.
- **Moving heads**: light one while it moves, black out, light the other while it moves, keep
  alternating (with haze the beams read in the air).
- **Multi-cell bars as an 8×7 drawing surface**: 3 colour rows, the white strip, 3 colour rows;
  progress by column, by row, zigzag, shapes. Use the **white strip with care**: it is much
  brighter than the colour rows.
- **Use the UV** better (the movers have UV).
- **Hue chandelier** (7 Philips Hue pendants in the room centre) follows the track's pattern in
  SoundSwitch: sometimes the pattern should be at zero so the centre stays dark while the rest of
  the show runs; elsewhere it should pulse with the music or brighten the party.
- **Per-track workflow in Claude Code** (a skill): read the current autoscript, the lyrics, the
  energy and style of the track, then write a script for it (colours, what gets choreographed)
  **without spending every idea in one track: the whole show must be good, not one song.**

## Success criteria

1. `nextrack_lights.py dump` turns any of the owner's ~500 SoundSwitch track scripts into a
   readable timeline (per fixture: intensity, colour, position, movement), and `analyze` reports
   what the autoscript does per phrase.
2. Parse → serialize is byte-identical for every track script in the owner's project; the tool
   refuses to write any file for which this does not hold.
3. A choreography written in `lightshows/tracks/<slug>.yml` compiles into a new `.ssfile` that
   SoundSwitch loads and plays as described, for every move the compiler claims to support; moves
   it cannot compile are listed as manual cues, never silently dropped.
4. `render` produces a self-contained HTML simulator of the room (before/after) that the owner can
   open in a browser, with no server and no install.
5. The `lightshow` skill takes a track from "autoscript only" to an approved choreography, a
   simulator preview and a written copy, in one session, using the set's lighting plan so ideas are
   paced across the show.
6. `uv run scripts/check_repo.py` and `uv run pytest` pass; the new data files are covered by
   validator rules (CLAUDE.md checklist).

## Non-goals

- Decrypting `.ssa` files (encrypted with a fixed key; untouched by script edits). Never attempted.
- Generating a show for a track SoundSwitch never scripted. v1 edits existing scripts only.
- Live control (OS2L, MIDI, Art-Net output), controlling Hue directly, or replacing SoundSwitch.
- A 3D visualizer. The simulator is a 2-D top view of this one room.
- Writing to the project while SoundSwitch is running, or without the owner present.
- Adding SoundSwitch ids to the track pools (`tracks/*.yml`). The id lives in the choreography file.
- Venue editing (presets, looks). Read only.

## Anti-goals (would be a failure even if it "works")

- A corrupted or silently changed SoundSwitch file, or a lost autoscript layer the owner wanted.
- A night where every track uses every trick: white strip, strobe and ping-pong in every drop.
- The white strip blinding the room, or white sitting under the colours by default.
- A choreography the owner cannot read and amend in plain Portuguese before it is applied.

## Constraints

- The live project is `C:\Users\<you>\Music\SoundSwitch\<project>.ssproj\` (WSL:
  `/mnt/c/Users/<you>/Music/SoundSwitch/<project>.ssproj/`). Never hard-code it: `--project` or
  `NEXTRACK_SOUNDSWITCH_PROJECT`, one of the two required.
- Dry-run by default; only `--apply` writes into the project, and only when SoundSwitch is not
  running (checked via `tasklist.exe` on WSL), after a byte-for-byte backup.
- The repo is public: no real `.ssfile`/`.ssa`/venue bytes are committed. Tests build synthetic
  files under `tmp_path`, as the audio tests do.
- Python ≥ 3.12, stdlib + existing deps (mutagen, pyyaml). No numpy.
- Language: ids, schema keys, code, `docs/` in English; choreography prose (`story`, `intent`) in
  pt-BR, like block prose.

## The rig and the room

Rectangular room seen from above, one fixture group per corner:

| Corner | Fixture | SoundSwitch nodes | Notes |
|---|---|---|---|
| NE | Moving head SHEHDS 7×18 RGBWA+UV, 15 ch | `Mover 1` (1167) | in `Group 4` (1166) |
| SE | Moving head, same model | `Mover 2` (1168) | |
| NW | Multi-cell Vorlane VL-1000 RGBW, 154 ch | 1818 → `MASTER`, `RGB 01–48`, `W 1–8` | aimed at the room centre |
| SW | Multi-cell, same model | 1876 → same children | aimed at the room centre |
| centre | 7 Philips Hue pendants (chandelier) | the script's **Main track** (pseudo-node 2) | Hue follows only Main |
| — | Haze Lig Light LL-HZ600K, 2 ch (fan, fog) | 1934 → `Main`, `Main - 2` | |

Each Vorlane, as the owner sees it: rows 1–3 colour (8 zones each), row 4 the white strip (8
zones, much brighter), rows 5–7 colour. Zone numbering is assumed row-major from the top-left
(RGB 01–08 = row 1); the autoscript's chase lights exactly 8 zones per step, which supports it.
Which unit/mover sits in which corner is the owner's to confirm; it is one line in `rig.yml`.

## How SoundSwitch stores a show

Decoded overnight on 2026-10-31 from a read-only copy of the owner's project. All 501 track scripts
and 128 AutoLoops parse with 100% of their bytes accounted for, and parse → serialize is
byte-identical for all 629. The byte-level reference becomes `docs/soundswitch/file-format.md`.

- **Project folder** `DJ Renan.ssproj/`: `.ssproj` (JSON settings), `SoundSwitchVenues.bin`
  (venues, fixtures, device tree, position presets, looks, attribute cues),
  `SoundSwitchTrackMap.bin` (script GUID → title, artist, audio path) and per track a
  `{GUID}.ssfile` (the editable script) plus `{GUID}.ssa` (encrypted; untouched by script edits;
  out of scope). All share one container: magic `aa aa 09 55`, version 3, little-endian ints,
  UTF-16LE strings, a tail object table.
- **A track script** = per venue, one **fixture track per device-tree node**, then a global part:
  the **tempo map** (`(t_ms, bpm)` anchors), the **Main track** (pseudo-node 2) and the attribute
  cues placed on it.
- **A fixture track** holds: an **intensity curve** (keyframes, level = `u32 / 2^32`, linear
  between keys); **intensity blocks** (B: the windows where the fixture overrides Main — outside
  them it follows Main); a link to its owning fixture; **colour blocks** (C: start/end ARGB +
  an extra word); **position flags** (D: preset index into a palette of the venue's position
  presets) inside **position blocks** (F); **strobe blocks** (E: start/end rate); **movement
  shape blocks** (G: shape id and four parameters; never overlapping F).
- **The Main track drives every fixture that has no block of its own at that moment, and the Hue
  chandelier follows only the Main track.** So "dark centre while the show runs" means Main
  intensity at zero while the fixtures that should keep running have their own blocks.
- **Writing:** same-size value edits are proven in SoundSwitch (2026-10-31 test). Size-changing
  edits must update counts, the G objects' self-pointers, the tail table, offA and offB; the
  spike serializer recomputes all of these and reproduces every real file, but SoundSwitch has
  not yet been shown a resized file (owner experiment X1).
- **Node ids are not stable across files**: 436 of 501 scripts carry the 122 current ids; others
  also carry tracks for stale ids of earlier venue layouts. Address tracks by node id, resolved
  from the current venue, never by position.
- **Not in the `.ssfile`:** phrase/section analysis and the audio beat analysis.

The rig as SoundSwitch sees it (from the venue): movers on DMX 37–51 and 52–66 (15 ch, no dimmer
channel, strobe ch 6, UV ch 12); Vorlanes on 101–254 and 301–454 (owner-edited "154CH Soft"
profile with the master dimmer capped at 0–127, strobe, RGB 01–48, W 1–8); haze on 504–505 (fan
fixed 100, fog fixed 175, both typed Intensity). No attribute cue targets a current fixture, and
static looks 1–32 are the factory blank.

## Design

### Layers

```
lightshows/sets/<set>.md      show plan: arc, colour story, budget of effects per block/peak
lightshows/<block>.md         block scene (existing template): palette, mood, intensity arc
lightshows/tracks/<slug>.yml  per-track choreography: sections × layers, intent in pt-BR
        │  nextrack_lights.py compile/apply
        ▼
SoundSwitch {GUID}.ssfile     lanes: per-node intensity, colour, position, movement (autoscript base)
```

The SoundSwitch script is per track (one `.ssfile` per audio file), so the choreography is per
track too. Block scenes and the show plan guide authoring; they compile to nothing.

### 1. Format library — `scripts/soundswitch_format.py`

Pure reading and writing of the SoundSwitch container and its three file kinds, no CLI:

- container: header, sections, tail table; `parse(bytes) → model`, `serialize(model) → bytes`
  with the round-trip guarantee of success criterion 2;
- `TrackMap`: GUID → title, artist, path;
- `Venues`: device tree (node id, name, parent, look number, display colour), position presets
  (name, GUID), fixtures (profile, mode, DMX address) — read only;
- `TrackScript`: header, venues → fixture tracks (intensity curve, B, link, C, D, E, F, G), global
  part (tempo map, Main track, attribute-cue palette and flags), tail object table — the grammar in
  `docs/soundswitch/file-format.md`. Serialization recomputes every derived field (counts, object
  ids, self-pointers, tail table, offA/offB); it never copies them.
- Edit operations on the model, each keeping keys sorted, blocks sorted and non-overlapping, and F
  and G disjoint: replace a fixture's intensity keys and B blocks in a span; set colour blocks;
  set position flags/blocks (dropping G blocks in the span); set Main-track intensity/colour;
  materialise Main into a fixture for a span.
- Time helpers from the tempo map: bar/beat ↔ ms, including multi-anchor (variable tempo) maps.

### 2. CLI — `scripts/nextrack_lights.py`

Same conventions as `nextrack_tags.py` (dry-run default, `--apply`, env var for the root):

| Command | Does | Writes |
|---|---|---|
| `tracks [--match TEXT]` | list scripted tracks: GUID, title, artist, path; match against pool entries | nothing |
| `dump TRACK [--yaml]` | readable timeline of the current script, per fixture and phrase | stdout |
| `analyze TRACK…` | per-phrase stats of what the autoscript does (who is lit, colours, position rate, chases, white-with-colour overlap) | stdout / markdown |
| `render TRACK [--choreo FILE] -o FILE.html` | self-contained room simulator, before/after | the HTML file |
| `compile CHOREO -o OUT.ssfile` | apply a choreography to a copy of the track's script | the copy only |
| `apply CHOREO [--apply]` | dry-run: show the diff and manual cues; `--apply`: back up, refuse if SoundSwitch runs or round-trip fails, replace the project file | project file + backup |

`TRACK` is a GUID, a GUID prefix, or "Artist — Title" resolved through the TrackMap.

### 3. Rig — `lightshows/rig.yml`

The room and roles, by SoundSwitch node **name** (ids are resolved from the venue at run time, so
re-adding a fixture in SoundSwitch doesn't break the file):

```yaml
room: {shape: rectangle, front: N}
fixtures:
  mover-ne:  {node: Mover 1, corner: NE, kind: mover}
  mover-se:  {node: Mover 2, corner: SE, kind: mover}
  matrix-nw: {node: VORLANE VL-1000 RGBW v2, index: 1, corner: NW, kind: matrix, aim: centre}
  matrix-sw: {node: VORLANE VL-1000 RGBW v2, index: 2, corner: SW, kind: matrix, aim: centre}
  haze:      {node: " Lig Light LL-HZ600K", kind: haze, fan: Main, fog: Main - 2}
  hue:       {kind: hue-chandelier, corner: centre, lamps: 7, follows: main-track}
matrix:
  rows: [colour, colour, colour, white, colour, colour, colour]   # 8 zones per row
  zone_order: row-major-top-left
  white_max: 0.6        # cap for the white strip relative to full
```

### 4. Choreography — `lightshows/tracks/<artist-title-slug>.yml`

```yaml
track: Marshmello x Bastille — Happier      # must match a pool entry (same rule as blocks)
soundswitch: F41EB9E9-B82B-4F58-A40C-B039222EBB0E
grid: {bpm: 100, downbeat: "0:00.158"}      # bars count from 1 at the downbeat
story: >-                                    # pt-BR: the arc of the track in light
  …
base: autoscript                             # what an unspecified layer keeps
sections:
  - bars: [17, 20]
    name: drop-1
    intent: …                                # pt-BR, one line
    movers: {move: pingpong, every: 1/2, colour: "#00C8FF"}
    matrix: {draw: rows-down, rate: 1/8, mirror: true}
    white: {accent: ["17.1"]}
    hue: dark
    haze: {burst: 4s}
```

Layers: `movers`, `matrix`, `white`, `uv`, `strobe`, `hue`, `haze`. Each takes `auto` (keep the
autoscript), `off`, or a move. Bars are inclusive; a section may set any subset of layers.

**Vocabulary v1** (ids in English, documented with pictures in `lightshows/README.md`):

- **movers:** `hold` (position, colour, level) · `pingpong` (one lit, the other dark, swap every
  N beats/bars; both keep moving) · `sweep` (step through a position list every N bars, lit) ·
  `blink` (pulse on the beat) · `uv` (UV wash).
- **matrix** (each Vorlane as 8 columns × 7 rows): `solid` · `rows-down` · `rows-up` · `columns`
  · `zigzag` · `centre-out` · `arrow-up` · `fill-up` (the build: rows accumulate until the drop);
  options `rate`, `colour`, `mirror` (NW and SW draw symmetrically), `pingpong` (NW ↔ SW),
  `with_white` (default false).
- **white:** `accent` (hits as `bar.beat`) · `flash` (rate); always capped by `white_max`.
- **strobe:** `hit` · `roll` (bars).
- **hue:** `dark` · `pulse` · `bright`.
- **haze:** `burst` (seconds) · `on`.

The rig and choreography models, the vocabulary, the frame generators and the compiler live in
`scripts/lightshow.py`; `check_repo.py` imports its schema checks.

**How each layer compiles** (a section's span = its bars converted to ms through the tempo map):

| Layer / move | Writes | v1 status |
|---|---|---|
| any non-`auto` fixture layer | replaces that fixture's B blocks and keys inside the span with a B block covering the span | compiles |
| `off` | intensity 0 across the span | compiles |
| movers `hold`, `sweep` | intensity level; C block with the colour; F block + D flags for the position(s); G blocks removed from the span | compiles |
| movers `pingpong`, `blink` | intensity keys (steps or eighth-note style decay, as the autoscript writes pulses: full → 0 over the step); colour as above; positions left to the autoscript unless given | compiles |
| matrix draws | per-cell intensity keys from the 8×7 frame sequence, per-cell C blocks for the colour | compiles |
| `white` | intensity keys on the 8 W cells, scaled by `white_max` | compiles |
| `strobe` | v1: fast intensity pulses (1/16) on the named fixtures; true E blocks once their rate unit is known (X8) | compiles (approximation) |
| `hue` | Main-track intensity (`dark` 0, `pulse` beat decay, `bright` 0.85) and colour | compiles; see the rule below |
| `haze` | intensity keys + B block on the fog/fan nodes (they are typed Intensity) | experimental until the owner confirms the machine reacts (X10) |
| `uv` | — | manual cue until the colour "ext" word is understood (X3) |

**The Main-track rule.** When a section changes `hue` (the Main track), every fixture whose layer is
`auto` and which had no block of its own there would change with it. The compiler therefore first
**materialises** Main's previous content for that span into those fixtures (a B block with the old
Main intensity keys, plus C and F/D or G copies), and only then edits Main. The look of the room
stays as the autoscript made it; only the chandelier changes.

Anything the compiler cannot express is printed as a manual cue (bar, time, fixture, what to do),
so the owner can add it in SoundSwitch; it is never silently dropped.

### 5. Show plan — `lightshows/sets/<set-file-stem>.md`

Front matter `set:` (path to the set) and a `budget:` map from effect to where it may appear
(`white-accent: [peak-1, peak-2, final]`, `strobe: [final]`, `uv: [halloween-chegada,
os-fantasmas]`…); pt-BR prose for the colour story and the arc. The skill reads it, plus the
choreographies already written for tracks in the same blocks, and keeps a tally so an effect is
not reused beyond its budget.

### 6. Simulator

`render` writes one HTML file with inline data and script: the room from `rig.yml` (movers as
coloured discs with the current preset name, each Vorlane as an 8×7 grid, the Hue chandelier and
the haze state), a timeline with the phrase grid, play/seek, and a before/after toggle. If the
track's audio path (from the TrackMap) is reachable, an `<audio>` element plays it in sync.

### 7. Skill — `.claude/skills/lightshow/SKILL.md`

Runs per track (or per block, track by track):

1. Resolve the track: pool entry, block(s) and set it is in, SoundSwitch GUID.
2. `dump` + `analyze` the current autoscript; `render` it.
3. Gather context: pool entry (genre, bpm, key, energy), block scene, show plan and the effects
   already spent in that block/set, the lyrics' themes (looked up, never stored in the repo).
4. Propose a script in pt-BR, phrase by phrase: story, then per section the layers that change.
   Use few effects; justify each spend against the budget.
5. On approval, write `lightshows/tracks/<slug>.yml`, `render` before/after, `compile` to a copy.
6. Only on the owner's explicit go, with SoundSwitch closed: `apply --apply`.

### 8. Validator rules

Per the CLAUDE.md checklist, each with passing/failing tests, README and rule-table rows:

- `lightshow-rig`: `rig.yml` schema, known kinds and corners, `white_max` in (0, 1].
- `lightshow-track`: schema; `track` resolves to a pool entry; `soundswitch` is a GUID; sections
  ordered and non-overlapping; layer values and moves from the vocabulary; fixtures exist in
  `rig.yml`.
- `lightshow-plan`: `set` path exists; budget keys are vocabulary effects.

## Safety model for writes

1. Parse the target file; serialize; require byte identity, else refuse.
2. Apply edits to the model; serialize; re-parse the result and check every untouched lane is
   identical to the original.
3. `apply --apply` only: refuse if `SoundSwitch.exe` is in `tasklist.exe`; copy the original to
   `<project parent>/nextrack-backups/<timestamp>/<GUID>.ssfile`; write to a temp file in the same
   folder and rename over the original.
4. Until the owner confirms experiment X1 (SoundSwitch loads a resized file), `apply --apply`
   refuses an output whose size differs from the input unless `--accept-resize` is given.
5. Print the restore command.

## Testing

- A synthetic builder in the tests writes container files (header, sections, tail table) and track
  scripts with chosen lanes; no real SoundSwitch bytes in the repo.
- Round trip, every edit operation, the compiler per move, the CLI commands on synthetic projects
  (including the "SoundSwitch running" and "round-trip fails" refusals, with `tasklist` mocked).
- Real-file checks (round-trip over the owner's ~500 scripts) run only when
  `NEXTRACK_SOUNDSWITCH_PROJECT` is set, and are skipped in CI.

## Documentation in the same change

- `docs/soundswitch/file-format.md`: the grammar, field table with confidence, writer rules (from the
  decoding findings).
- `docs/soundswitch/autoscript-analysis.md`: what the autoscript does on the party set's EDM tracks.
- `docs/soundswitch/experiments.md`: the owner experiments (X1–X10) that settle what is still
  unknown, each with steps, what to diff and what the answer changes.
- `lightshows/README.md`: replace the "future" template with rig, choreography and show-plan schemas
  and the vocabulary, with a small 8×7 diagram per matrix draw.
- `docs/rig.md`: a "Lights and room" section (fixtures, corners, DMX, what each lane drives).
- `scripts/README.md`: a `nextrack_lights.py` section and the new validator rule rows.

## Left to the builder

Module layout inside the two scripts, the YAML dump format, HTML/CSS of the simulator, exact
`analyze` metrics beyond the ones named, the slug function for choreography file names.

## Open questions for the owner

*(Filled after the builder check.)*

## Decision ledger

| # | Decision | Why | Cost if wrong |
|---|---|---|---|
| 1 | Three modules: `soundswitch_format.py` (bytes ↔ model), `lightshow.py` (rig/choreography model, vocabulary, compiler; also imported by `check_repo.py` for its rules), `nextrack_lights.py` (CLI) | one CLI per file as in `scripts/`; format and compiler testable alone; the validator can share the vocabulary without importing a CLI | a later move into a package; cheap |
| 2 | Choreography per track, in `lightshows/tracks/` | SoundSwitch stores one script per track; a block-level file could not compile | a track in two blocks gets one show; acceptable |
| 3 | Unspecified layers keep the autoscript (`base: autoscript`) | the owner said the autoscript is fine and they want to direct on top | some tracks may want `base: dark`; it is one key |
| 4 | Intent-level YAML compiled by the tool; compiled output never hand-edited | the owner reads and amends the YAML in Portuguese; the bytes stay machine-made | a move the vocabulary lacks needs a code change |
| 5 | Moves the compiler cannot express become printed manual cues | honest about partial decoding; no silent drops | more manual work until decoded |
| 6 | Write only with round-trip identity + backup + SoundSwitch closed | the anti-goal is a corrupted file before a party | none beyond a few seconds |
| 7 | Rig by node **name**, resolved at run time | ids change if a fixture is re-added; names are what the owner sees | duplicate names need `index` (used for the two Vorlanes) |
| 8 | Show plan as `lightshows/sets/<set>.md` with an effect budget | the owner insisted the whole show matters, not one song | budgets may feel rigid; prose overrides are allowed |
| 9 | Lyrics consulted for themes, never stored | copyright, and the repo's "notes stay musical" rule | none |
| 10 | Simulator is static HTML, no server | opens anywhere, no install; Node exists only under nvm | less interactive than a live tool |
| 11 | Editing Main (the Hue layer) first materialises Main into `auto` fixtures without blocks | otherwise darkening the chandelier darkens every fixture that follows Main | larger files; a fixture loses its link to later Main edits in that span |
| 12 | Resized writes need `--accept-resize` until X1 passes | the format is proven, SoundSwitch's acceptance is not | one extra flag, briefly |
| 13 | `haze` compiles to intensity on the fog/fan nodes, marked experimental | they are typed Intensity in the venue; 4 scripts already ramp them | a haze machine that ignores it; the cue list still tells the owner |
| 14 | `strobe` approximated by fast intensity pulses in v1 | E-block rate units unknown; pulses are proven | not a hardware strobe (no shutter channel) |
| 15 | Bars come from the script's tempo map, not from rekordbox | the tempo map is in the `.ssfile` and matches SoundSwitch's grid | none for fixed-tempo tracks; multi-anchor maps handled explicitly |
