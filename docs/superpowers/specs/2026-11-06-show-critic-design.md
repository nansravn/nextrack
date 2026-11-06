# Show language 1.1: the critic's senses — design

Date: 2026-11-06. Branch `feat/show-critic`. Builds on
[the show language design](2026-11-06-show-language-design.md) (PR #14), whose terms (show,
cue, bridge, handover, provenance, occurrence, finding) this document uses without
redefining them.

## Why

The show language gave a team of AI agents a common way to write a night. The next project
(project 2) is the team itself: a director, track agents, a critic and an effects agent,
looping create → critique → iterate. Reading `nextrack_show.py report hi-ibiza-pulso` as a
club lighting designer showed what a critic still cannot see. These are **facts** the
tooling must compute; the **judgment** stays with the agents:

- **Time.** The report counts bars, but the room lives in minutes. The eight first
  transitions of Hï Ibiza all use the same look (`respiracao-azul`): nearly 8 of the first 28
  minutes. That may be the plan, but no agent can tell without minutes per look.
- **Contrast.** A drop lands because the light before it is lower. The report lists states,
  not a light level next to the music's level, and does not rank the musical peaks against
  the light's answer.
- **Who plays.** The music column gives the section kind (`break`) but not the voices (kick,
  bass, voice). In TOO COOL bar 48 (the one-bar `breu`) drums and bass are silent while the
  voice sings at level 9, and nothing in the report says so.
- **The beat.** The craft of a club show is in the bars before a drop and on its first
  beat. The report has one line per section.
- **The room.** With two moving heads, the figure the two beams draw in the haze is the
  show. Aims are SoundSwitch preset names, and nothing says where they point.

The owner also decided three things in this conversation:
- **Bridges are agile.** A mix lasts at most 32 bars, and 16 is the base. The agent team will
  rework Hï Ibiza to fit later; this branch only lets the designer state the limit.
- **Aims are free.** Only the fixtures' places and types limit a show. Mover positions do
  not: the owner will create any preset the design asks for, and until then a fallback stands
  in.
- **More UV.** The movers' UV is a highlight for some moments, the off-beat among them. UV is
  **designed** here but not implemented: compiling it needs a manual test in SoundSwitch
  (experiment X11) that the owner will run later.

This is project 1.1. It is an extension of the language, not project 2: every view here is
deterministic and computed from the show, the maps, the set and the rig. Project 2 consumes
them.

## Goals

1. **Advice.** `show.yml` gets an `advice:` mapping beside `rules:`. It takes the same rule
   ids and parameters, but its findings are design goals: `build` and `report` print them,
   and they never fail `check_repo.py`.
2. **Agile bridges.** `bridge.bars` (1-32) sets the mix window, and a new show rule
   `bridges {max}` measures every bridge and handover. Hï Ibiza declares
   `advice: {bridges: {max: 16}}` and a pt-BR line in its plan. Its choreographies do not
   change.
3. **Clock and screen time.** The report gets the set clock (per track and per section) and a
   night summary: minutes per look, per colour (per fixture group), per aim and per zone,
   plus the share of time with the centre dark.
4. **Contrast.** The report gets per-track strips, one character per bar, of the music level
   and the light level. It also gets a peak table: every drop of the played music, its size,
   and the light's level before and at it, with accents and moment.
5. **Voices.** Each section line shows the voices' levels under it.
6. **Hit checks.** The report gets one line per arrival and moment: the kick at the hit, the
   light before and at it, and what plays in a dark bar before it.
7. **Zoom.** A new command, `nextrack_show.py zoom`, prints a moment at 1/16-beat resolution:
   music lanes from the map, light lanes sampled with the compiler's own generators, and
   optional 8×7 Vorlane frames.
8. **The room.** A new file, `lightshows/room.yml`, holds the room's size, each fixture's
   place (assumed until measured) and the **aim catalogue**. Each aim is a beam figure with
   target points, the SoundSwitch preset that realises it, a status (`configured` or
   `pending`) and a fallback. A movers layer can name an aim; the compiler writes the
   preset, or the fallback's while the preset is pending. `vocab` lists what to create in
   SoundSwitch.
9. **UV, designed.** A section of this document gives UV's role, best practices,
   vocabulary, rules and compilation path, and `docs/soundswitch/experiments.md` gets
   experiment X11. The zoom and the report show UV wherever a choreography already writes it
   (`uv: on`, `move: uv`).
10. **Docs.** The manual (`lightshows/shows/README.md`), `scripts/README.md`, the lightshow
    README and `CLAUDE.md` are updated, plus a new rule row for `lightshow-room`.

## Non-goals

- Compiling UV, the UV layer forms, UV gestures and UV rules: they wait for X11 (see [UV](#uv-designed-implemented-after-x11)).
- Reworking Hï Ibiza: 16-bar bridges, new aims, UV moments. That is the agent team's first backlog.
- Changing `lightshow.py`, `nextrack_lights.py`, the choreography schema, `compile` or `apply`.
- Writing presets into SoundSwitch, or computing pan and tilt. The owner programs presets
  by hand from the targets.
- A drawn top view of the room, an HTML view, a whole-night simulator, or JSON output.
- The agent team, its prompts and the backlog (projects 2 and 3).

## Anti-goals

- **Opinions dressed as facts.** Every number has a stated formula. Indices are labelled as
  approximations, and the report never says "too long" or "boring".
- **A hidden fallback.** A pending aim is always visible in `report` and `vocab`.
- **Advice that blocks.** An advice finding never fails CI.
- **Drift.** The views read the compiled show, the same data `build` writes. They are never
  a second interpretation of the source.

## 1. Advice

```yaml
rules:                                # gates: fail show-rules (check_repo, CI)
  budget: {breu: {max: 5}}
advice:                               # goals: printed, never failing
  bridges: {max: 16}
  budget: {breu: {max: 4}}            # a rule may appear in both, with other parameters
```

- `advice` is optional. Its keys are registered rule ids, and its parameters are checked by
  the same `check` as in `rules`. An unknown id or a bad parameter is a `show-source`
  finding, because a broken goal is a broken file.
- Its findings use the rule id `show-advice` and the same `path:line` format, with their
  message prefixed by the rule id, as in `show-rules`.
- `check_repo.py` does not report them. `build` prints them after the rule findings, under
  `N advice`, and they do not change the exit status. `report` lists them in an `advice`
  section.
- `evaluate_show` returns them as a fourth value, or the API gets a new function. That
  choice is the builder's, provided `check_repo` and the CLI share one entry point.

## 2. Agile bridges

**`bridge.bars`** (optional, an integer from 1 to 32 in `show.yml`'s `bridge`) is the
length of the mix window. When it is set:
- The incoming track's bridge runs from `B` for at most `bars` bars. If the first cue starts
  before `B + bars`, the bridge stops there, as today. If the first cue starts after
  `B + bars`, that is a `show-source` finding at the first cue: "the bridge ends at bar
  <B + bars - 1> (bridge.bars <n>); start a cue at or before bar <B + bars>".
- The outgoing track's handover runs by default from `G` to `G + bars - 1`, not to the map's
  end. An explicit `until` later than `G + bars` is the same kind of finding, at the handover.
- Without `bars`, the behaviour is unchanged. Hï Ibiza is unchanged.

**Rule `bridges`** `{max: n}` (1-32). A compiled bridge section, or a handover section,
longer than `max` bars is a finding at the handover's line in the outgoing track's file,
since the fix is in both tracks and the handover owns the window. The message names both
lengths and the two tracks.

**Hï Ibiza.**
- `show.yml` gets `advice: {bridges: {max: 16}}`. Today that is 11 bridge findings and
  most of the handovers, and it is the team's first backlog item.
- Its light plan (`lightshows/sets/hi-ibiza-pulso.md`) gets one rule in "Regras da noite",
  in pt-BR: the bridge is agile, 16 bars, never more than 32.
- The 15 choreographies do not change. `build --check` stays at 0.

## 3. Clock and screen time

**The clock model** is `set_timeline`'s:
- A track plays bars `[B, G)`. The first track plays from bar 1, and the last runs to its
  last non-silent bar (`set_timeline.last_bar`).
- Each bar takes 240 / tempo seconds. The tempo ramps linearly over the played bars, from the
  range in the block's tracklist line (`set_timeline.block_tempos`); without one, it is the
  map's `bpm`.
- The next track starts when the previous one reaches `G`, so a bridge's clock is the
  outgoing track's `G` clock.

Reuse `set_timeline`'s functions. Where a function needs rekordbox cues in milliseconds,
derive them from the maps' stored hot cues on the map grid; do not read rekordbox.

**Two windows per track.**
- The **leg** is `[B, G)` (the first track from bar 1, the last to its last non-silent bar).
  It is the track's share of the night's time.
- The **sounding window** is `[B, the track's last compiled bar]`. The outgoing track
  still sounds during the mix, after its `G`. A bar at or after `G` gets its clock as
  `clock(G)` plus the seconds from `G` to that bar, at the track's tempo.

**States and events.**
- **States** (looks, colours, aims, zones, dark) are summed over legs, so no moment is
  counted twice. During a mix, the time belongs to the incoming track, whose bridge copies
  the outgoing handover's look. Which script SoundSwitch really plays then is still
  experiment P1, and the manual says so.
- **Events** (white accents, strobe, UV sections, moments, map drops) are listed over
  sounding windows, at their own clock. So the peak of PICK UP at its G (137, ~39:30), the
  peak of Can't Decide at its G (69) and TOO COOL's drop 97, inside the mix, all appear. The
  summary's event counts then equal the budget's.

**In the report:**
- Each track header gets `enters m:ss` (its B on the set clock) and `arrival <bar> at m:ss`.
  The arrival is the section with `role: arrival`, not `set_timeline`'s computed arrival.
- Each section line starts with its clock (`32:20`), handover sections included.

**The night summary** (top of `report`) sums the states over legs and lists the events over
sounding windows, as above:
- **minutes per look**: by `origin.look`, inline sections as `inline`, gesture sections by
  gesture name (`spiral`);
- **minutes per colour per fixture group** (movers, matrix, hue), by palette name;
- **minutes per aim** (see [The room](#8-the-room)), and every pending aim used, with the
  fallback that stood in for it. A section that cycles several aims (`positions`) splits its
  time evenly among them;
- **minutes per zone lit**: movers (east), Vorlanes (west), lustre (centre). A zone is lit
  when its layer is neither `off`, `dark` nor `auto`;
- **centre dark**: the share of time with hue `dark` or `off`;
- **total dark**: minutes, and the count of total-dark sections;
- **strobe, white accents, UV**: counts and minutes.

All values are shown as `m:ss`, with percentages where they help.

## 4. Contrast: music and light strips, peak table

**The music level of a bar** is the highest of its `kick`, `bass` and `other` levels in the
map (0-9). Vocals are shown separately (see [Voices](#5-voices)).

**The light level of a section** is an approximation, 0-9, computed from its compiled layers:

| layer | value in 0-1 |
|---|---|
| movers | `off` 0; `hold`, `sweep`: `level` (default 0.85); `pingpong`, `blink`: `level` × 0.5; `uv`: 0.3 |
| matrix | `off` 0; per draw, the lit share of the colour cells: `solid` 1, `fill-up` 0.6, `rows-*` 1/6, `columns` 1/8, `centre-out` 0.25, `arrow-up` 0.15, `zigzag` 1/48; × 0.5 with `pingpong`; then × 0.6 (draws pulse and decay) |
| hue | `dark`, `off` 0; `pulse` 0.5; `bright` 0.85 |

The level is `round(9 × (0.4 × movers + 0.4 × matrix + 0.2 × hue))`. A section whose
movers, matrix or hue is `auto` (or unset) is `~` (unknown: the autoscript decides). The
`white`, `strobe` and `uv` layers do not enter the level; they show as accents. The formula
lives in one function with this table in its docstring, and the manual repeats it, so
agents know it is an index, not a measurement.

**The strips.** Under each track header come two lines, one character per played bar,
wrapped at 64 bars like `nextrack_map.py show`:

```
  music |99999999666666666666996699999999...
  light |55555555333334444444442233333333...
```

**The peak table** comes after the tracks. It has one row per map drop inside a track's
sounding window, so the drops of the outgoing music during a mix are included:
- the clock and the track title;
- the bar and `db`. The map's `db` is the drop against the two bars before it, so a drop
  after a musical silence reads huge;
- the music level;
- the light level of the section before the bar and of the section at it;
- the accents and `moment` at that bar.

The table is sorted by clock. The report's text says what the columns mean.

## 5. Voices

Each section line gets, after `music:`, the highest level of each voice over the section's
bars, abbreviated: `k9 b0 v9 p8 o3` (kick, bass, vocals, perc, other).

## 6. Hit checks

After the peak table comes one line per arrival (`role: arrival`) and per `moment`, in set
order. Each line gives:
- the clock, the track and the bar;
- the kick onset strength on the hit's first step (`onsets.kick`, `.` = none);
- the light level of the section before and of the section at the hit;
- the accents on that beat;
- when the section just before is total dark, the voices' levels in it (`dark 48: k0 b0 v9`).

Facts only.

## 7. Zoom

```bash
uv run scripts/nextrack_show.py zoom hi-ibiza-pulso virada                       # a moment name
uv run scripts/nextrack_show.py zoom hi-ibiza-pulso "PAWSA — Too Cool To Be Careless" drop.2 --before 3 --after 2
uv run scripts/nextrack_show.py zoom hi-ibiza-pulso virada --frames 48.4,49.1    # also the Vorlanes' 8×7 frames
```

**The target** is either a moment name (the first cue or handover with that `moment`), or a
track (`Artist — Title`, as in its track file) plus an anchor. The window is `--before`
bars (default 3) before the target bar and `--after` bars (default 1) after it. An unknown
target is a usage error, and the message lists the moments.

**The output** has one column per 1/16 step and a `|` at each bar line. The layout of the
spec's example is binding in spirit, not to the character:

```
TOO COOL · virada (c. 49) · c. 46-50 · 32:12-32:21
           |46              |47              |48              |49              |50
section    |espiral-1-8     |espiral-1-16    |breu            |virada          |virada
music
  kick     |7..77.8...8.7...|7..77.7...7.7...|................|98.79.8.9.7.9.5.|98579.7.9.8.9.5.
  perc     |4.616.6.5.5.7.5.|4.627.6.5.5.8.5.|................|9.629.6.9.6.9.5.|9.5.9.5.8.6.8.6.
  bass     |7748777730012332|1102100100000000|0000000000000000|8989599940987797|7979499711021499
  vocals   |9299999798999985|9988999845999899|9998999899999999|8999899989430000|0000000000000000
light
  mover NE |vv..vv..vv..vv..|r.r.r.r.r.r.r.r.|................|R...R...R...R...|R...R...R...R...
  mover SE |..vv..vv..vv..vv|.r.r.r.r.r.r.r.r|................|R...R...R...R...|R...R...R...R...
  aim      |centro-da-pista |centro-da-pista |-               |cruzado         |cruzado
  uv       |                |                |                |                |
  vorl. NW |...
  vorl. SW |...
  lustre   |................|................|................|9631963196319631|9631963196319631
  white    |                |                |                |####            |
  strobe   |                |                |                |xxxx            |
legend: v violeta, r/R vermelho (lower case: decaying), lustre 0-9, ~ autoscript
```

- **Music lanes** come straight from the map's step data: `onsets.kick`, `onsets.perc` (for
  the off-beat), and `steps` for bass, vocals and other.
- **Light lanes** sample the **compiler's generators**, `lightshow.mover_keys`,
  `lightshow.matrix_frames` and `lightshow.hue_keys`, at each step's time on the map's grid
  (downbeat plus tempo anchors). The zoom draws what `compile` would write. Rules for each
  lane:
  - A mover, a Vorlane unit or the lustre lane gets one glyph per step: the colour's legend
    letter, upper case at or above half level, lower case below it, `.` when dark.
  - A Vorlane lane's glyph shows whether any cell of that unit is lit; `--frames` gives the
    detail.
  - White, strobe and UV lanes mark the steps their layer fills.
  - A layer at `auto` is `~` all along its section.
  - The colour legend gives each palette colour one unique letter.
  - The aim lane shows, per step, the aim in force, by the compiler's cycling rule:
    `positions` change one per movers step. When the aim changes within a bar, it uses a
    legend digit per aim instead of the name.
- **`--frames BAR.BEAT,...`** prints, for each beat, the two Vorlanes' 8×7 frames side by
  side, as in the lightshow README's frame drawings.

The zoom samples each step a few milliseconds after its start (`SAMPLE_OFFSET_MS`), so it reads
the value in force and not the compiler's rounding edge.

The zoom needs no SoundSwitch project. A later version could read the base script with
`--project` to show the autoscript's lanes too; that is a non-goal here.

## 8. The room

### `lightshows/room.yml`

```yaml
# The room in metres: x from west (0) to east, y from south (0) to north, z up from the floor.
size: {x: 5.0, y: 4.0, z: 2.6}
assumed: true                         # true until the owner measures the room and the fixtures
fixtures:                             # the rig's fixture keys (lightshows/rig.yml), each at its place
  mover-ne:  [5.0, 4.0, 2.3]
  mover-se:  [5.0, 0.0, 2.3]
  matrix-nw: [0.0, 4.0, 1.6]
  matrix-sw: [0.0, 0.0, 1.6]
  hue:       [2.5, 2.0, 2.2]
  haze:      [5.0, 0.0, 0.3]
booth: [2.5, 4.0, 1.2]               # the DJ booth (the room's front is north)
aims:
  centro-da-pista:
    figure: "os dois feixes convergem no centro do chão"
    preset: Dance Floor Centre
    status: configured
    targets: {mover-ne: [2.5, 2.0, 0.0], mover-se: [2.5, 2.0, 0.0]}
  apice:
    figure: "os dois se encontram meio metro acima do lustre: uma tenda de luz sobre o coração"
    preset: Apex
    status: pending
    fallback: coluna
    targets: {mover-ne: [2.5, 2.0, 2.6], mover-se: [2.5, 2.0, 2.6]}
```

**Keys.**
- `size` (three positive numbers), `assumed` (bool), `fixtures`, `booth` (a point) and
  `aims` are all required.
- Every `fixtures` key is a fixture key of `lightshows/rig.yml`, and every rig fixture has a
  place.
- A point is three numbers inside `size` (bounds included).

**An aim** is:
- `figure`: pt-BR prose, the image the beams draw;
- `preset`: the SoundSwitch position preset name;
- `status`: `configured` or `pending`;
- `fallback`: another aim id, required when `pending` and forbidden when `configured`;
- `targets`: one point per mover of the rig.

Aim ids are kebab-case. Fallback chains must end on a configured aim, with no cycle.

The owner measures the room once and sets `assumed: false`. Nothing in `report` or `zoom`
uses coordinates: they name aims by id and figure. The coordinates are the owner's
programming instructions. `vocab` prints them for every pending aim, marked
`(geometria presumida)` while `assumed` is true.

**Validator rule `lightshow-room`** (in `check_repo.py`, with the checks in a pure
function). It checks the schema above against `rig.yml`, and that fallbacks resolve, have no
cycle and end on a configured aim. The file is optional: without it, aims are unavailable,
and a show that names one gets a `show-source` finding.

### The aim catalogue for this set

The seven presets the set already uses are `configured`. The new ones are `pending`, with a
fallback that already exists. All targets assume the nominal room until it is measured.

| aim | preset | status | figure | fallback |
|---|---|---|---|---|
| `centro-da-pista` | Dance Floor Centre | configured | both converge on the floor's centre | — |
| `cruzado` | Crossed Over | configured | an X over the floor (NE to the SW side, SE to the NW side, at ~1.2 m) | — |
| `coluna` | Up | configured | two vertical columns in the haze | — |
| `poca` | Down | configured | each beam down at its own corner | — |
| `cabine` | DJ Booth | configured | on the DJ | — |
| `lado-oeste` | Stage Left | configured | to the west side (which preset is which side: to confirm, P2) | — |
| `lado-leste` | Stage Right | configured | to the east side (to confirm, P2) | — |
| `apice` | Apex | pending | they meet half a metre above the lustre | `coluna` |
| `leque` | Fan Out | pending | NE to the NW top corner, SE to the SW top corner: the room opens | `coluna` |
| `varal` | Parallel West | pending | both level over the heads, towards the Vorlanes | `cruzado` |
| `rasante` | Low Cross | pending | they cross at ~0.9 m, under eye level | `poca` |
| `anel-1` … `anel-8` | Ring 1 … Ring 8 | pending | eight points round the walls at ~2.2 m, clockwise from the north wall's centre; a pattern gives the two movers opposite points | `cruzado` |

The anel aims are what a real spiral (project B) will walk. Today they make agents and
the owner aware that the figure exists.

**Targets** (nominal room 5 × 4 × 2.6 m; movers at NE `[5, 4, 2.3]` and SE `[5, 0, 2.3]`;
`room.yml` holds them, and they change when the room is measured):

| aim | mover-ne target | mover-se target |
|---|---|---|
| `centro-da-pista` | [2.5, 2.0, 0.0] | [2.5, 2.0, 0.0] |
| `cruzado` | [0.5, 0.5, 1.2] | [0.5, 3.5, 1.2] |
| `coluna` | [5.0, 4.0, 2.6] | [5.0, 0.0, 2.6] |
| `poca` | [4.5, 3.5, 0.0] | [4.5, 0.5, 0.0] |
| `cabine` | the booth [2.5, 4.0, 1.2] | the booth |
| `lado-oeste` | [1.25, 2.0, 0.0] | [1.25, 2.0, 0.0] |
| `lado-leste` | [3.75, 2.0, 0.0] | [3.75, 2.0, 0.0] |
| `apice` | [2.5, 2.0, 2.6] | [2.5, 2.0, 2.6] |
| `leque` | [0.0, 4.0, 2.4] | [0.0, 0.0, 2.4] |
| `varal` | [0.0, 3.0, 2.2] | [0.0, 1.0, 2.2] |
| `rasante` | [0.0, 0.5, 0.9] | [0.0, 3.5, 0.9] |
| `anel-k` | ring point k | ring point k + 4 (mod 8) |

**The ring.**
- The eight ring points are evenly spaced along the walls' perimeter at z 2.2, starting at
  the north wall's centre and going clockwise as seen from above (north, then east, south,
  west).
- In the nominal room these are: [2.5, 4, 2.2], [4.75, 4, 2.2], [5, 2, 2.2], [4.75, 0, 2.2],
  [2.5, 0, 2.2], [0.25, 0, 2.2], [0, 2, 2.2] and [0.25, 4, 2.2].
- Opposite points are four apart, so the two beams always face each other across the room.

### Aims in the show language

An aim id may stand wherever a movers preset name stands: in `position`, in a `positions`
list, and in gesture parameters that hold presets, such as the spiral's `aims`.
- **Resolution happens once, in the compiler, after gestures expand.** A value that is an aim
  id of `room.yml` becomes the aim's preset when the aim is configured, or else the preset of
  the first configured aim along its fallback chain. Any other value is a raw preset name: the
  escape hatch. Aim ids are kebab-case and preset names are not, so the two never collide.
- **The provenance gets a new field, `aims`**: the aim ids the section's movers named, in
  order.
- **`movers-aim`** is unchanged: an aim id is a `position`.
- **The report maps raw preset names back** to their aim id when exactly one configured aim
  uses that preset.

`vocab` lists the catalogue: the configured aims, then the pending ones with their targets
and figures under the title "presets to create in SoundSwitch". `report` lists the pending
aims the show uses.

Hï Ibiza keeps its raw preset names, so its choreographies do not change. Its report shows
the aim ids through the reverse mapping.

## 9. UV (designed; implemented after X11)

**Role.** UV makes people and the room glow: white clothes, smiles, UV-reactive decorations
on the walls. It barely shows in haze, so it is not a beam effect. A night planned around it
(a white party) spends more of it; a night like Pulso spends little.

**Best practice, for the rules.**
- **Dark first.** UV reads only in a dark room: Vorlanes off (or deep blue at a low level),
  lustre `dark`, the white strip off.
- **Time to adapt.** The eye needs seconds to adapt to the dark, so a UV moment lasts at
  least 4-8 bars, and preferably comes out of a dark section.
- **Pure UV on the movers.** The colour is off while UV is on, because colour hides it.
  The aim is on the floor and on people: `centro-da-pista`, `rasante`, or a sweep between
  `lado-oeste` and `lado-leste`, because a spot has to move to paint a floor.
- **The rhythm.**
  - Steady: a glow under a break.
  - On the off-beat: a pulse on the "and" of each beat, between the kicks, while the
    lustre beats on the kick. This is house's counter-beat.
  - On the percussion onsets: the map's `onsets.perc`.
  - On the vocal phrases.
- **Safety.** The movers' UV is UV-A LED (never UV-C), and a beam never rests at eye height.
  `rasante` is under eye level.

**Vocabulary (to add after X11).**
- **The `uv` layer** grows from `on|off|auto` to a mapping: `{pulse: steady | beat | offbeat
  | perc, level}`.
- **`move: uv`** keeps its meaning (the movers in pure UV) and aims by aim id like any
  mover section.
- **A gesture `uv-glow`** gives a dark room with a UV pulse pattern over its span.

**Rules (to add after X11).**
- `uv-needs-dark {matrix: off|dim, hue: dark}`
- `uv-min-bars {min: 4}`
- the `budget` key `uv`, which exists already

**Compiling.** SoundSwitch has mixed Amber, White and UV into colours since 2.1, set with HEX
in the Color Picker. The repo already knows that the colour's "ext" word carries White in
byte 1 (X3). X11 finds UV's byte. After that, a UV section writes the movers' colour blocks
with the UV byte, and pulses write intensity keys as the other layers do. Until then,
`uv: on` and `move: uv` stay manual cues, as today.

**X11**, added to `docs/soundswitch/experiments.md`:

| # | Question | Steps in SoundSwitch | Diff | What the answer changes |
|---|---|---|---|---|
| X11 | Where does a mover's colour store UV and Amber? | On a scratch track, on Mover 1's colour lane, paint one block of pure UV (HEX in the Color Picker) near 0:10 and one of pure Amber near 0:20. Save. | byte diff of the two colour blocks (ARGB and ext words) | Lets the `uv` layer, `move: uv` and the UV vocabulary compile instead of printing manual cues. |

## Validator and CLI summary

- **`check_repo.py`** gains `lightshow-room`. Its existing show rules use `room.yml` for
  aims, and `show-advice` is never a check_repo finding. `scripts/README.md` gets the new row.
- **`nextrack_show.py`** changes:
  - `report` gains the night summary, the clock, the strips, the voices, the peak table, the
    hit checks, the advice section and the aims;
  - `zoom` is new;
  - `vocab` lists the aims and the presets to create;
  - `build` prints the advice.
- **The light-level and music-level functions** live in one place (a library module). The
  report and the zoom share them.

## Docs

- `lightshows/shows/README.md`:
  - `advice`, `bridge.bars` and the `bridges` rule;
  - aims in a movers layer;
  - the report's new sections, with their formulas;
  - `zoom`;
  - a short "reading the report as a critic" paragraph that names what is fact and what is
    left to judgment.
- `lightshows/README.md`: a row for `room.yml`, and the room section (schema, the catalogue's
  meaning, measuring the room).
- `scripts/README.md`: `zoom`, the report's new sections, and the `lightshow-room` row.
- `CLAUDE.md`: a change checklist for **adding an aim** (catalogue entry, `pending` with a
  fallback, the owner creates the preset) and the zoom in the show tool's bullets.
- `docs/soundswitch/experiments.md`: X11.
- `lightshows/sets/hi-ibiza-pulso.md`: the bridge rule, in pt-BR.

## Decisions

These are the designer's calls under the owner's direction in this conversation. Each says
why, and what it costs if wrong.

1. **1.1 extends project 1.** The views are deterministic facts about the show; the judgment
   stays in project 2's agents. *If wrong:* the views move into the team's tooling unchanged.
2. **`advice` beside `rules`, same rules.** A design goal that does not hold yet must be
   writable without turning CI red. Agents get a backlog from it, and gates stay gates. *If
   wrong:* a show can still move a rule from `advice` to `rules`.
3. **`bridge.bars` is opt-in and symmetric**, cutting the incoming bridge and the outgoing
   handover to the same window. The schema caps it at 32. *If wrong:* the default can be
   changed later without touching shows that set it.
4. **The geometry lives in `room.yml`, not `rig.yml`.** The rig maps SoundSwitch nodes, and
   the room is physical. Keeping them apart leaves `lightshow.py` untouched. *Cost:* one more
   file, cross-checked by `lightshow-room`.
5. **Aims are figures of both movers**, which is how a SoundSwitch position preset works
   (each fixture's pan and tilt). A pending aim compiles to its fallback, so creativity never
   waits for the owner, and the owner gets a list.
6. **The light level is a stated, simple index**, labelled as such. A measured level would
   need the autoscript and the fixtures' photometry. *If wrong:* one function with one table
   to tune.
7. **The zoom samples the compiler's own generators**, so it cannot disagree with `compile`.
8. **UV is designed, not built**, on the owner's call: compiling it waits for X11.
9. **Text only.** Agents read text best, and so does a terminal. A drawn room view waits.
10. **Legs for states, sounding windows for events** (from the builder check). Counting
    states over `[B, G)` never counts a moment twice. Counting events over the whole
    sounding window keeps the peaks that sit on a G or inside a mix, and keeps the summary
    consistent with the budget. *If wrong:* only the two window functions change.
11. **Aim ids live in the existing preset fields**, not in new `aim`/`aims` keys (from the
    builder check). This gives one resolution point, after gestures expand, and gestures
    such as the spiral take aim ids with no change. *If wrong:* sugar keys can be added later.
12. **Cycling sections split their aim time evenly**, a formula that is stated and simple.
    *If wrong:* switch to the compiler's step times inside one function.
