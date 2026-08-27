# Energy & arcs

A great set is a *shape*, not a flat line. NEXTRACK uses a simple 1–10 energy
scale so blocks, radios, and sets can be planned as deliberate curves.

## The 1–10 energy scale

| Level | Feel | Typical use |
|------|------|-------------|
| 1–2 | ambient, background | doors open, chillout, afters |
| 3–4 | warm, heads-nodding | warmup, sunset, dinner |
| 5–6 | grooving, bodies moving | early floor, plateau |
| 7–8 | driving, hands-up | main floor, build |
| 9–10 | peak, euphoric/relentless | the moment, drop, climax |

Record it per track (`energy: 6`) and per block (target range + arc).

## Block functions

Give every [block](../blocks/) a *function* — what it does to the room:

- **Warmup** — set mood, low energy, patient (3→5).
- **Build** — climb steadily, tension up (5→8).
- **Peak** — the payoff, hold the top (8→10).
- **Plateau** — cruise at high energy without climaxing (7↔8).
- **Breakdown** — deliberate release, reset (drop 2–3 levels).
- **Cooldown / Afters** — bring it home (down to 2–4).

## Arc shapes

- **Single peak** — classic night: warmup → build → peak → cooldown.
- **Waves** — build → peak → breakdown → build higher → bigger peak. Keeps a long
  set from fatiguing.
- **Slow burn** — a sunset/organic set that never fully peaks; the *restraint* is
  the point.
- **Radio arc** — a themed [radio](../radios/) has its own mini shape even if the
  whole night is bigger.

## Tying it together

- A **track** has an energy value.
- A **block** has an energy *arc* (start → end + shape) and a function.
- A **radio** sequences blocks into a larger arc.
- A **set** is the night's full curve, assembled for the specific crowd.

When you pick the next track *within* a genre node, energy is usually the deciding
variable: same node, nudge the energy up or down to match where the room is going.
Between nodes, follow a [graph edge](genre-graph.md) — the energy note in the block
tells you whether to pick a higher- or lower-energy landing track on the far side.
