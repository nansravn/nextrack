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

- **Entries start with `- title:`**, at column 0. The library tool
  ([`../scripts/nextrack_tags.py`](../scripts/nextrack_tags.py)) finds the entries of
  a pool by that line, so `title` is always the first key of an entry.
- **The fields are exactly the ones above.** `title`, `artist`, `genre`, `bpm`,
  `key`, `energy` and `status` are required; `remixer`, `duration`, `year`,
  `source`, `tags` and `notes` are optional; no other key is allowed. `title` and
  `artist` are non-empty strings, and `tags` is a list.
- **`bpm` and `key` are always present, even when `null`.** `pull-bpm` fills them by
  editing their existing lines, so leave them as `null` until the track is analysed.
  `bpm` is `null` or a whole number from 1 to 300.
- **`genre`** must be a node `id` in [`../genres/graph.yml`](../genres/graph.yml), and it
  is the name of the file the entry is in.
- **`key`** in Camelot so harmonic moves are pre-solved: `null` or `1A`-`12A` /
  `1B`-`12B`.
- **`energy`** is the main knob you turn when picking the next track in the pool, a
  whole number from 1 to 10.
- **`status`** tracks the download pipeline (see [../docs/workflow.md](../docs/workflow.md)).
- **`tags`** are free-form — moods, functions, "vocal", "peak", "br", venue fit.
- **A track appears once.** No two entries, in one pool or in two, may have the same
  artist and title once case, accents and punctuation are ignored.

All of this is checked by `uv run scripts/check_repo.py`, together with the file
name (it must be a node `id`).

> Remember: the actual audio never lives here — only this description does. See
> [../docs/workflow.md](../docs/workflow.md) for the download/mirror step.
