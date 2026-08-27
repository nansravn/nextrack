# blocks/ — time-boxed themed sequences ⭐

A **block** is the atom of NEXTRACK: a short, time-boxed, themed sequence of
tracks with an energy arc. It's the unit you *play*, the unit you *transition*
within, and the unit a *light scene* attaches to (later).

Blocks are ordered — but flexibly. List a primary tracklist plus swap options, so
you can still fluctuate within the genre pool on the night.

## File naming

`blocks/<slug>.md`, e.g. `blocks/sunset-warmup-organic.md`,
`blocks/baile-peak-150.md`, `blocks/roda-eletronica.md`.

## Template — copy this

```markdown
---
name: Sunset Warmup (Organic)
function: warmup            # warmup | build | peak | plateau | breakdown | cooldown
style: continuous          # continuous | open-format | hybrid — drives the transition palette
duration: 30m              # target time frame
genres: [organic-house, mpb-bossa]   # node ids from ../genres/graph.yml
bpm: [108, 116]
energy: [3, 5]             # start -> end feel (1-10)
key_journey: 8A -> 9A -> 9B
lightshow: null            # -> ../lightshows/<slug>.md (future)
---

## Feel
One or two lines: the mood, the room, the moment this block is for.

## Tracklist (primary)
1. Artist — Title  · 8A · 110 · e4
2. Artist — Title  · 9A · 112 · e4   ← blend on the break
3. Artist — Title  · 9B · 114 · e5

## Transitions
<!-- technique follows the block's `style`; see ../docs/transitions.md -->
- 1→2: blend on the 2:30 break, EQ swap bass, +2 BPM.        # continuous
- 2→3: relative-major lift (9A→9B); ride the percussion.
<!-- open-format equivalent: hard-cut on the hook, or echo out across a BPM gap -->


## Swap options (fluctuate with the room)
- Softer: Artist — Title (e3)
- Harder: Artist — Title (e6)

## Bridge out
Follow the graph edge organic-house → afro-house (add percussion) into the next block.
```

## Why blocks matter

- **DJing:** in the moment you're really deciding "which block, and where in it."
- **Transitions:** the hard, pre-solvable work (key/BPM/energy between tracks and
  between blocks) is captured once, here.
- **Light shows:** a block already carries mood + palette + energy arc, so a
  [lighting scene](../lightshows/) maps onto it one-to-one.

Compose blocks into [radios](../radios/) (themed programs) and
[sets](../sets/) (full gigs).
