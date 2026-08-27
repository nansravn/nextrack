# 🎚️ NEXTRACK

**Your DJ crate as a git repo — set planning as code.**

NEXTRACK is a documentation-first system for organizing music to DJ with. It's
the source of truth for *what you own, how genres connect, how tracks flow into
blocks, and — eventually — how each block should look under lights.* You document
here first; you download the audio later (Beatport, Tidal) into folders that
mirror this structure.

It's built for a wide palette — not just EDM, but **Brazilian styles** (funk,
brazilian bass, afro-brasileiro, samba/pagode, forró/piseiro, sertanejo, MPB)
and **thematic "radios"** (time-boxed blocks with a specific mood and energy).

> ⚠️ **This repo never stores audio.** Committing downloaded Beatport/Tidal files
> to a public repo is a copyright problem. `.gitignore` excludes all audio — the
> files live on your drive in a folder layout that mirrors this repo.

---

## The model

A clean hierarchy makes DJing decisions, transitions, and light shows all fall
into place:

| Unit | What it is | Ordered? |
|------|-----------|----------|
| **Genre** | a *node in a graph*; edges describe how to move between genres | — |
| **Track** | one song + metadata (BPM, key, energy, source, tags) | no — a pool |
| **Block** ⭐ | a short, **time-boxed**, themed sequence with an energy arc | yes (flexible) |
| **Radio** | a longer themed *program* made of blocks | yes |
| **Set** | a full gig, assembled from blocks/radios for a venue/crowd | yes |

**Three ideas do the heavy lifting:**

1. **Genres are a graph, not a list.** `genres/graph.yml` models each genre as a
   node with edges to compatible genres (BPM path, rhythmic bridge, strength).
   That's your *navigation map* — how to travel from funk 150 to afro house to
   amapiano. See [`docs/genre-graph.md`](docs/genre-graph.md).

2. **The track catalog is a pool, not a play-order.** You fluctuate within a
   genre/energy band based on the room. Ordering intelligence lives at the
   genre-transition level and inside **blocks** — never baked into the track list.

3. **Two mixing styles are first-class.** Continuous blend (the EDM journey) and
   open-format (recognition — cuts, echo-outs, FX between genre blocks). Each
   [block](blocks/) declares its `style`. See [`docs/mixing-styles.md`](docs/mixing-styles.md).

---

## Repo layout

```
nextrack/
├── docs/            # the thinking — concept, taxonomy, mixing theory, workflow
│   ├── concept.md         the vision
│   ├── taxonomy.md        genre glossary (EDM + Brazilian)
│   ├── genre-graph.md     the graph model + how to fluctuate within a genre
│   ├── mixing-styles.md   continuous blend vs open-format — the two modes
│   ├── transitions.md     technique catalog (blend, cut, echo out, FX…)
│   ├── harmonic-mixing.md Camelot wheel + BPM cheat sheet
│   ├── energy-arcs.md     warmup → peak → cooldown model
│   ├── rig.md             gear → technique map (FLX6 + Serato)
│   └── workflow.md        discover → document → download → organize
├── genres/          # the genre graph (nodes + edges)
│   └── graph.yml
├── tracks/          # the crate — an unordered pool of documented tracks
├── blocks/          # ⭐ time-boxed themed sequences (the DJ + lightshow unit)
├── radios/          # thematic programs (arcs of blocks)
├── sets/            # full performances per gig
└── lightshows/      # per-block lighting scenes (future)
```

Each folder has a `README.md` explaining its schema and a template to copy.

---

## Quickstart

1. Read [`docs/concept.md`](docs/concept.md) and [`docs/genre-graph.md`](docs/genre-graph.md).
2. Document a track: copy the template in [`tracks/README.md`](tracks/README.md).
3. Build a block: copy the template in [`blocks/README.md`](blocks/README.md),
   pick a genre lane from the graph, target a time frame and energy arc.
4. When you're ready to play it, download the tracks into your mirrored audio
   folder (git-ignored) and rehearse the transitions noted in the block.

---

## License

[MIT](LICENSE) — reuse, remix, and build on it. A credit back is always
appreciated but not required.
