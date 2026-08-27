# tracks/ — the crate (an unordered pool)

Your documented music. **This is a pool, not a play-order** — tracks are tagged,
not sequenced. In the moment you fluctuate within a genre/energy band based on the
room; ordering intelligence lives in the [genre graph](../genres/) and in
[blocks](../blocks/), never here.

## How to organize the files

One YAML file per genre node, named after the node `id`:

```
tracks/
├── afro-house.yml
├── brazilian-funk.yml
├── organic-house.yml
└── ...
```

Each file is a list of tracks in that genre. (One-file-per-genre keeps diffs clean
and files scannable; if a genre gets huge, nothing stops you splitting further.)

## Track schema

```yaml
# tracks/<genre-id>.yml
- title: "Track Name"
  artist: "Artist"
  remixer: ""               # optional
  genre: afro-house         # a node id from ../genres/graph.yml
  bpm: 122
  key: 8A                   # Camelot — see ../docs/harmonic-mixing.md
  energy: 6                 # 1-10 — see ../docs/energy-arcs.md
  duration: "6:42"          # optional
  year: 2025                # optional
  source: beatport          # beatport | tidal | promo | bandcamp | ...
  status: to-download       # to-download | downloaded | organized
  tags: [percussive, vocal, sunset, br]
  notes: "Break at 2:30; great after a 150 funk half-timed."
```

### Field notes

- **`genre`** must be a node `id` in [`../genres/graph.yml`](../genres/graph.yml).
- **`key`** in Camelot so harmonic moves are pre-solved.
- **`energy`** is the main knob you turn when picking the next track in the pool.
- **`status`** tracks the download pipeline (see [../docs/workflow.md](../docs/workflow.md)).
- **`tags`** are free-form — moods, functions, "vocal", "peak", "br", venue fit.

> Remember: the actual audio never lives here — only this description does. See
> [../docs/workflow.md](../docs/workflow.md) for the download/mirror step.
