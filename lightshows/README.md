# lightshows/ — per-block lighting scenes (future)

> 🚧 **Future work.** This folder is scaffolded and ready, but light shows come
> after the crate and blocks exist. It's here so the structure is future-proof.

Because a [block](../blocks/) already carries a mood, an energy arc, and a genre
identity, a **lighting scene** maps onto it one-to-one. One scene per block; the
block's `lightshow:` field points here.

## File naming

`lightshows/<block-slug>.md` — same slug as the block it lights.

## Template — copy this

```markdown
---
block: sunset-warmup-organic     # the block this lights
mood: warm, golden, unhurried
palette: ["#F4A259", "#E76F51", "#7B4B94", "#2A1B3D"]  # hex, warm->deep
intensity: [20, 50]              # % start -> end, tracks the block's energy arc
movement: slow                   # static | slow | medium | fast | strobe
haze: light
---

## Scene
How the room should feel visually across the block: dominant colors, how they
shift as energy rises, what the light "does".

## Cues (sync to the block's energy arc)
- 0:00  wash amber, low intensity, slow movement
- 8:00  introduce magenta as energy lifts to e4
- 20:00 add slow beam movement on the build to e5
- 30:00 hand off warm/bright into the next block

## Fixtures / notes
Rig-specific mapping (which fixtures, DMX groups, any manual triggers). Keep
generic here; venue-specific overrides go in the set.
```

## Design notes

- **Palette follows genre + mood.** Warm oranges/purples for sunset organic; deep
  blues/whites for peak techno; saturated tropical colors for baile/global bass.
- **Intensity follows the [energy arc](../docs/energy-arcs.md).** Map light
  intensity to the block's start→end energy so the room *sees* the build.
- **Cue on the block's structure.** Breaks and drops in the tracklist are your
  lighting cue points.

## Schemas checked by the validator

Checked by `check_repo.py` (rules `lightshow-rig`, `lightshow-track`,
`lightshow-plan`); the checks live in `scripts/lightshow.py`.

**`rig.yml`** — keys `room` (`shape`, `front` in `N E S W`), `fixtures`, `matrix`.
A fixture is `{kind, node, index, corner, aim, fan, fog, lamps, follows}`: `kind` is
`mover`, `matrix`, `haze` or `hue-chandelier`; `node` is the SoundSwitch node name
(required unless `hue-chandelier`); `corner` is `NE`, `SE`, `NW`, `SW` or `centre`.
`matrix` is `{rows, zone_order, white_max}`: `rows` lists `colour` / `white`, and
`white_max` is a number in (0, 1].

**`tracks/<artist-title-slug>.yml`** — keys `track` (`Artist — Title`, must match a pool
track), `soundswitch` (GUID), `grid` (`{bpm, downbeat}`), `story`, `budget` (optional),
`base` (`autoscript`), `sections`. A section is `{bars: [a, b], name, intent?}` plus any
of the layers; bars are inclusive, from 1, sorted and not overlapping. YAML reads an
unquoted `off` / `on` as a boolean; both spellings are accepted. A layer is `auto`,
`off` or a mapping:

| layer | values |
|---|---|
| `movers` | `{move: hold\|pingpong\|sweep\|blink\|uv, every, colour, level (0-1], position, positions, faster_from (bar), faster_every}` |
| `matrix` | `{draw: solid\|rows-down\|rows-up\|columns\|zigzag\|centre-out\|arrow-up\|fill-up, rate, colour, mirror, pingpong, with_white}` |
| `white` | `{accent: ["<bar>.<beat>", …]}` or `{flash: <rate>}` |
| `uv` | `on`, `off`, `auto` |
| `strobe` | `{hit: ["<bar>.<beat>", …]}` or `{roll: [a, b]}` |
| `hue` | `dark`, `pulse`, `bright`, or `{state: dark\|pulse\|bright, colour}` |
| `haze` | `{burst: "<n>s"}`, `on`, `off`, `auto` |

Rates are `1/16`, `1/8`, `1/4`, `1/2` or `<n>bar`; colours are `#RRGGBB`. Under a
`matrix` other than `auto`, `white` defaults to `off` (applied by the compiler), except
under a draw with `with_white: true`, which lights the white row itself.

**`sets/<set-file-stem>.md`** — front matter `set:` (path to the set, relative to the
repo root) and `budget:` mapping an effect (a layer, or `white-accent`) to a list of
names where it may appear.
