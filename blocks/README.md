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

## Bridge in
← `deep-house`: how the previous block hands over to this one (follows a graph edge into organic-house).

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
- → `afro-house`: follow the graph edge organic-house → afro-house (add percussion) into the next block.
```

## Machine-checked formats

`uv run scripts/check_repo.py` reads every block and reports what strays from
these formats. Run it after writing or editing a block.

- **Tracklist line:** under the `## Tracklist…` heading, every line that starts
  with `N.` reads `N. Artist — Title · …`: an em dash (`—`, not `-`) between artist
  and title, then a middle dot (`·`) after the title. What follows the dot (key,
  BPM, `eN`, notes) is free.
- **The line must match a pool track:** its artist and title must find a track in
  some `tracks/*.yml`. Case, accents and punctuation don't matter, a `(…)` or `[…]`
  part of the title is ignored, and the artist may be a partial or longer credit
  (`Pedro Sampaio` finds `Pedro Sampaio & MC Pedrinho`). A track not in the pool
  yet goes into its pool first (`status: to-download` is enough).
- **Bridges follow graph edges:** write each node id in backticks in the
  `## Bridge in` and `## Bridge out` sections. For Bridge in the graph needs an
  edge from that node to one of the block's `genres`; for Bridge out, an edge from
  one of the block's `genres` to that node. A missing edge means adding it to
  `genres/graph.yml` (and the Mermaid map) or choosing another bridge. Backtick
  only node ids there: a word shaped like an id that is not a node is reported as
  a typo, and file names such as `axe-classicos.md` are never checked.
- **Only the first section of each kind is checked:** the first `## Tracklist…`,
  the first `## Bridge in…` and the first `## Bridge out…`. A second section with
  the same heading prefix is ignored, so keep one of each.
- **Swap options** stay free-form.
- **Front matter:** exactly the keys of the template above, with the values the
  comments list; `genres` are existing node ids and `lightshow` is `null` or a path
  relative to the block that exists.

## Why blocks matter

- **DJing:** in the moment you're really deciding "which block, and where in it."
- **Transitions:** the hard, pre-solvable work (key/BPM/energy between tracks and
  between blocks) is captured once, here.
- **Light shows:** a block already carries mood + palette + energy arc, so a
  [lighting scene](../lightshows/) maps onto it one-to-one.

Compose blocks into [radios](../radios/) (themed programs) and
[sets](../sets/) (full gigs).
