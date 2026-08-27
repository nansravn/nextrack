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
