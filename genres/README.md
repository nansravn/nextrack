# genres/ — the genre graph

Genres are modeled as **nodes in a graph**. Edges describe *how to travel between
them* — the BPM path, the rhythmic/harmonic bridge, and how reliable the move is.
This is the navigation map for your sets; it is deliberately separate from the
[track pool](../tracks/), which is unordered.

- **[`graph.yml`](graph.yml)** — the machine-readable graph (nodes + edges).
- **[`../docs/genre-graph.md`](../docs/genre-graph.md)** — the human explanation,
  a Mermaid visualization, and how to "fluctuate" within a node.
- **[`../docs/taxonomy.md`](../docs/taxonomy.md)** — the plain-language glossary
  for every node.

## Node schema

```yaml
- id: afro-house            # kebab-case, stable — tracks reference this
  name: Afro House
  family: global            # brazilian | global
  bpm: [118, 125]           # typical range
  energy: [5, 8]            # 1-10 scale (see docs/energy-arcs.md)
  feel: [percussive, deep, emotive]
  subgenres: [afro-house, afro-tech, 3-step]
  neighbors:                # edges OUT of this node
    - to: afro-brasileiro
      strength: strong      # strong | medium | weak (reliability)
      via: "swap global percussion for BR percussion"
```

## Conventions

- Keep `id`s **stable** — the whole catalog references them.
- Prefer a handful of **well-connected** nodes over many thin ones; use
  `subgenres` for finer detail inside a node.
- Edges are written directionally for clarity but most work both ways — add the
  reverse edge when the return trip needs different advice.
- `strength` is your confidence the move lands cold. Downgrade one after it flops
  in a real room; that feedback is the whole point of writing it down.

> Growth path: for now the entire graph lives in one `graph.yml` for easy
> visualization. If it gets large, split into one file per node (e.g.
> `genres/afro-house.yml`) — the schema is identical.
