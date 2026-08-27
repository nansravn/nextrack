# Concept

## Why this exists

DJing well is less about owning tracks and more about *knowing what you own and
how it connects*. A folder full of downloads doesn't tell you that this funk 150
bridges cleanly into an afro house roller, or that this MPB edit is the perfect
sunset opener. NEXTRACK captures that knowledge as plain text you can version,
search, and grow over time.

The audio is the easy part — you download it later. The hard part, the part
worth keeping, is the **thinking**: the map of genres, the curated blocks, the
transition notes, the energy arcs, and the light-show intentions.

## Principles

- **Documentation first, audio later.** You decide *what* and *how* here, then
  download from Beatport/Tidal into a mirrored (git-ignored) folder on disk.
- **The catalog is a pool, not a setlist.** Tracks are tagged, not ordered. In
  the moment you fluctuate within a genre/energy band based on the crowd. The
  repo never pretends to know the exact order you'll play.
- **Ordering lives in two places:** the *genre graph* (how families bridge into
  each other) and *blocks* (short, deliberate, time-boxed sequences).
- **Brazilian styles are first-class.** Funk, brazilian bass, afro-brasileiro,
  samba/pagode, forró/piseiro, sertanejo, and MPB sit next to house, techno,
  amapiano, and global bass — same schema, same graph.
- **Blocks are the atom.** A block is simultaneously the unit you *play*, the
  unit you *transition* within, and the unit a *light show* attaches to.
- **Everything is reversible and legible.** Plain YAML/Markdown, small files,
  clean git diffs. Future-you (and anyone who forks this) can read it.

## The four layers

1. **Genre graph** — the map. Nodes are genres; edges are how you travel between
   them (BPM path, rhythmic bridge, harmonic feel, strength). This is what makes
   an "unexpected but it works" transition repeatable.
2. **Track pool** — the crate. Each track is documented with BPM, key (Camelot),
   energy, source, download status, mood, and tags. Unordered by design.
3. **Blocks / radios / sets** — the arrangements. Time-boxed, themed, ordered
   (but with room to swap). Blocks compose into radios; radios/blocks compose
   into a set for a specific gig.
4. **Light shows** — the look. Because a block already carries a mood, palette,
   and energy arc, a lighting scene attaches to it naturally (future work).

## A worked example (in words)

> *"Sunset warmup, 30 minutes, beach club."* You pull from the `organic-house`
> and `mpb-bossa` nodes, keep energy 3→5, BPM ~108–115, key journey along the
> Camelot wheel. As the sun drops you follow the graph edge from `organic-house`
> into `afro-house`, then later a strong edge into `afro-brasileiro` to bring the
> room home. Each of those is a block; together they're a radio; the whole night
> is a set — and each block gets its own light scene later.

See [`genre-graph.md`](genre-graph.md) for how the map is encoded, and
[`energy-arcs.md`](energy-arcs.md) for the energy model.
