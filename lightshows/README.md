# lightshows/ — the rig, per-track choreographies and show plans

The room's lights are driven by SoundSwitch, which writes an automatic script for every
track (the *autoscript*). This folder holds what makes that script yours:

| path | what it is |
|---|---|
| `rig.yml` | the room and its fixtures, by SoundSwitch node name |
| `tracks/<artist-title-slug>.yml` | the **choreography** of one track: sections of bars, each saying what a layer does |
| `sets/<set-file-stem>.md` | the **show plan** of a set: its story, palette per block and the effect budget |

A track without a choreography keeps the autoscript. A choreography replaces only what it
names; everything else (an unset layer is `auto`) stays as SoundSwitch wrote it. What the
autoscript does on its own is in
[docs/soundswitch/autoscript-analysis.md](../docs/soundswitch/autoscript-analysis.md); the
rig is in [docs/rig.md](../docs/rig.md#lights-and-room); the file format in
[docs/soundswitch/file-format.md](../docs/soundswitch/file-format.md).

Prose in the files (`story`, `intent`, plan text) is pt-BR; keys and values are English.

## Workflow

1. **Write the choreography** (by hand, or with the agent skill for it) from the track's
   structure and the show plan's budget.
2. **See it:** `uv run scripts/nextrack_lights.py render "<track>" --choreo lightshows/tracks/<slug>.yml -o /tmp/sim.html`
   writes the room simulator, before and after, on a timeline (add the audio file in the
   page to hear it). Nothing is written to SoundSwitch.
3. **Compile** to a file: `compile lightshows/tracks/<slug>.yml -o out.ssfile`. Use it to
   inspect; the project is untouched.
4. **Apply** with SoundSwitch closed: `apply lightshows/tracks/<slug>.yml` is a dry run
   that prints what would change, then `--apply` writes it (backup first).
   [scripts/README.md](../scripts/README.md#nextrack_lightspy) has the safety model.
5. Open SoundSwitch, play the bars, add the **manual cues** the tool printed, and run
   `uv run scripts/check_repo.py`.

## `rig.yml`

```yaml
room: {shape: rectangle, front: N}
fixtures:
  mover-ne:  {node: "Mover 1", corner: NE, kind: mover}
  matrix-nw: {node: "VORLANE VL-1000 RGBW v2", index: 1, corner: NW, kind: matrix, aim: centre}
  haze:      {node: " Lig Light LL-HZ600K", kind: haze, fan: "Main -  Lig Light LL-HZ600K", fog: "..."}
  hue:       {kind: hue-chandelier, corner: centre, lamps: 7, follows: main-track}
matrix:
  rows: [colour, colour, colour, white, colour, colour, colour]   # 8 zones per row
  zone_order: row-major-top-left
  white_max: 0.6        # ceiling of the white strip, 0-1
```

Keys: `room` (`shape`, `front` in `N E S W`), `fixtures`, `matrix`. A fixture is
`{kind, node, index, corner, aim, fan, fog, lamps, follows}`: `kind` is `mover`,
`matrix`, `haze` or `hue-chandelier`; `node` is the SoundSwitch node **name** (required
unless `hue-chandelier`; ids are looked up in the venue, they change between rigs);
`index` picks the n-th node with that name (the two Vorlanes share one); `corner` is `NE`,
`SE`, `NW`, `SW` or `centre`. `matrix` is `{rows, zone_order, white_max}`: `rows` lists
`colour` / `white`, `white_max` is a number in (0, 1].

## Choreography: `tracks/<artist-title-slug>.yml`

```yaml
track: Marshmello x Bastille — Happier      # must match a pool track
soundswitch: F41EB9E9-B82B-4F58-A40C-B039222EBB0E   # the script GUID (nextrack_lights.py tracks)
grid: {bpm: 100, downbeat: "0:00.158"}      # checked against the script's tempo map
story: >-                                    # prose: what the light says about the song
budget: >-                                   # optional: what this track spends
base: autoscript
sections:
  - bars: [21, 28]            # inclusive, from 1, sorted, no overlap
    name: subida-1
    intent: ...               # optional
    movers: {move: pingpong, every: 1bar, colour: "#00C8FF", faster_from: 27, faster_every: 1/2}
    matrix: {draw: fill-up, rate: 1bar, mirror: true}
    hue: dark
```

Keys: `track` (`Artist — Title`), `soundswitch` (GUID), `grid` (`{bpm, downbeat}`), `story`,
`budget` (optional), `base` (`autoscript`), `sections`. A section is
`{bars: [a, b], name, intent?}` plus any of the layers. Bars are counted from the
downbeat in `grid`; the compiler maps them through the script's tempo map and refuses a
track with more than 8 tempo anchors. YAML reads an unquoted `off` / `on` as a boolean;
both spellings are accepted.

### Layers

A layer is `auto`, `off` or a mapping.

| layer | values |
|---|---|
| `movers` | `{move: hold\|pingpong\|sweep\|blink\|uv, every, colour, level (0-1], position, positions, faster_from (bar), faster_every}` |
| `matrix` | `{draw: solid\|rows-down\|rows-up\|columns\|zigzag\|centre-out\|arrow-up\|fill-up, rate, colour, mirror, pingpong, with_white}` |
| `white` | `{accent: ["<bar>.<beat>", ...]}` or `{flash: <rate>}` |
| `uv` | `on`, `off`, `auto` |
| `strobe` | `{hit: ["<bar>.<beat>", ...]}` or `{roll: [a, b]}` |
| `hue` | `dark`, `pulse`, `bright`, or `{state: dark\|pulse\|bright, colour}` |
| `haze` | `{burst: "<n>s"}`, `on`, `off`, `auto` |

Rates are `1/16`, `1/8`, `1/4`, `1/2` or `<n>bar` (a bar is four beats); colours are
`#RRGGBB`.

- `movers`: `hold` and `sweep` stay lit at `level` (default 0.85; the position, not the
  light, moves); `pingpong` lights one mover per step, the other dark, `every` long (default
  `1/4`); `blink` pulses every step; `uv` is a manual cue. `position` / `positions` are
  venue preset names (`DJ Booth`, `Dance Floor Centre`, `Up`, ...); several are cycled,
  one per step. `faster_from` is an **absolute bar** from which `faster_every` replaces
  `every`.
- `hue`: the Hue chandelier follows the Main track, so this layer edits Main. `dark` is
  0, `bright` steady 0.85, `pulse` one pulse per beat. `off` means `dark`.
- `white`: the white strip never goes above the rig's `white_max`. `accent` is one beat at
  each `bar.beat`; `flash` pulses at the rate.
- `strobe`: v1 is 1/16-note pulses on the movers and the colour cells for one beat per
  `hit`, or for the bars of `roll`.
- `haze`: fog on for `burst` seconds with the fan on across the section; experimental, the
  tool prints a manual cue to confirm the machine reacted.

### The matrix draws

The two Vorlanes are 8 columns by 7 rows of cells (see [the rig](../docs/rig.md#lights-and-room)).
Rows 0-2 and 4-6 are colour, row 3 is the white strip, lit only by `with_white`. One step
of the draw is one `rate`; `k` is the step (from 0), `#` is a lit cell. One frame of each
draw, rows top to bottom:

```
solid          rows-down k=1   rows-up k=0     columns k=2     fill-up k=2
########       ........        ........        ..#.....        ........
########       ########        ........        ..#.....        ........
########       ........        ........        ..#.....        ........
........       ........        ........        ........        ........
########       ........        ........        ..#.....        ########
########       ........        ........        ..#.....        ########
########       ........        ########        ..#.....        ########

centre-out q=0 centre-out q=1  zigzag k=2      zigzag k=9      arrow-up k=3
...##...       ..#..#..        ..#.....        ........        ........
...##...       ..#..#..        ........        ......#.        ........
...##...       ..#..#..        ........        ........        ...##...
........       ........        ........        ........        ........
...##...       ..#..#..        ........        ........        ..#..#..
...##...       ..#..#..        ........        ........        .#....#.
...##...       ..#..#..        ........        ........        #......#
```

- `solid`: every colour cell, every step (a pulse per step, not steady light).
- `rows-down` / `rows-up`: one row per step, top to bottom or the reverse, wrapping.
- `fill-up`: from the bottom, one more row per step; once full, every row keeps pulsing
  each step.
- `columns`: one column of every colour row per step, left to right, wrapping.
- `centre-out`: two columns from the middle (3 and 4), then 2 and 5, and so on, wrapping every four steps.
- `zigzag`: one cell per step, snake order: row 0 left to right, row 1 right to left, ...
- `arrow-up`: a "^" whose apex rises one row per step; cells past the bottom row are cut.

Options of `matrix`: `colour` (default depends on the draw), `rate` (default `1/4`),
`mirror` (the second Vorlane draws flipped, so the two bars are symmetrical across the
room), `pingpong` (the first Vorlane gets the even steps and the second the odd ones),
`with_white` (the white row takes part in the draw, at `white_max`).

## What the compiler does that matters to an author

- **Unset is `auto`.** A layer you do not write stays as the autoscript wrote it. A
  fixture the rig names but the venue or the script lacks is skipped with a manual cue.
- **White is off under a drawing.** With `matrix` other than `auto`, an unset `white` is
  `off`, because the autoscript's white strip washes colour out. A draw with
  `with_white: true` lights the strip itself, so there `white` stays `auto`. To ask for
  white in a section with `matrix: auto`, write it.
- **The Main track is the Hue centre.** `hue` rewrites Main for the section. Fixtures
  that follow Main there would change too, so the compiler first copies the old Main onto
  every fixture track that is not edited by this section for the lanes `hue` changes;
  a `hue` layer therefore does not alter movers or Vorlanes by side effect. Only leaf
  nodes get the copy: group nodes (a Vorlane, the haze, "Group 4") carry no content.
  A `hue` colour cuts Main's colour blocks, most of them gradients; what is left of a cut
  gradient keeps showing the colours it showed.
- **Pulses.** Every draw is a per-step sawtooth: each lit cell jumps to full at the step
  and decays to dark over that one step, like the autoscript. That holds for `solid` and
  for the full rows of `fill-up` too: they pulse every step, they are not steady light.
  A Vorlane's master is held at full under a draw.
- **Positions.** A mover section replaces the autoscript's position flags inside it; when
  the autoscript's position block goes on past the section, the preset it had in force
  there comes back at the first moment after the section.
- **Manual cues.** What the compiler cannot write is printed as `manual cue, bar N: ...`
  by `render`, `compile` and `apply`: `uv`, `move: uv`, haze (to confirm), a position
  preset the venue or script does not have, a shape block cut by a position change, a
  strobe `off` over SoundSwitch's own strobe blocks. Add these in SoundSwitch by hand.
- **Nothing outside the sections changes.** `apply` refuses unless everything outside the
  rig's tracks and Main equals the base, and outside the sections every venue track and
  Main shows the base's intensity, colour and position.
- **Undo.** To return a track to the autoscript, close SoundSwitch and copy
  `nextrack-backups/base/{GUID}.ssfile` (next to the project folder) over the file of the
  same name in the project folder. To undo only the last `apply`, use the `restore:` line
  it printed. [scripts/README.md](../scripts/README.md#safety-model-of-apply---apply) has
  what the next `apply` then asks for.

## Show plan: `sets/<set-file-stem>.md`

```markdown
---
set: sets/2026-10-31-halloween-em-casa.md     # the set, relative to the REPO ROOT
budget:                                       # where each rare effect may appear
  white-accent: [peak-1, peak-2]
  strobe: [peak-2]
  uv: [halloween-chegada]
---
# Plano de luz — ...
```

`set` is the path of the set file, **relative to the repo root** (not to this file).
`budget` maps an effect (a layer, or `white-accent`) to a list of names where it may
appear: peaks, blocks or moments the prose of the plan names. The rest of the file is
pt-BR prose: the story of the night, peaks, moments, a palette per block, a role per
block and the rules of the night. Choreographies read it; the validator only checks the
front matter.

## Seeing the show

SoundSwitch has no 3D preview. `render` is the cheap way; for the real signal, SoundSwitch
can send Art-Net to a visualizer on the same Windows PC (Preferences, Hardware: enable
Art-Net and the localhost node; listen on Art-Net universe 0; start the visualizer first).
Free choices: XR_DMX_Visualiser, Capture (Student edition) and QLC+ 5. Details in
[docs/soundswitch/file-format.md](../docs/soundswitch/file-format.md#seeing-the-show).

## Schemas checked by the validator

Checked by `check_repo.py` (rules `lightshow-rig`, `lightshow-track`, `lightshow-plan`);
the checks live in `scripts/lightshow.py`.

**`rig.yml`** (optional): exactly `room`, `fixtures` and `matrix`, with the keys above;
`kind` and `corner` from their lists; `matrix.white_max` a number in (0, 1].

**`tracks/<artist-title-slug>.yml`**: `track` matches a pool track (same matcher as block
tracklists), `soundswitch` is a GUID, `grid` has `bpm` and `downbeat` (`m:ss.mmm`),
`sections` are sorted and do not overlap, layer names, moves, draws, rates and `#RRGGBB`
colours are from the vocabulary, and unknown option keys are findings.

**`sets/*.md`** (but `README.md`): front matter whose `set` is an existing path relative
to the repo root and whose `budget` keys are layers or `white-accent`.
