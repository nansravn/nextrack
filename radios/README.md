# radios/ — thematic programs

A **radio** is a longer, themed *program* made of [blocks](../blocks/) — your
"thematic radios" idea. Think of each one as a station with a strong identity and
its own energy arc: *Rádio Pôr do Sol*, *Rádio Baile*, *Global Bass Journey*,
*Madrugada Deep*, *Roda Eletrônica*.

A radio is reusable: assemble it once, then drop it into different
[sets](../sets/) as the night calls for it.

## File naming

`radios/<slug>.md`, e.g. `radios/radio-por-do-sol.md`, `radios/radio-baile.md`.

## Template — copy this

```markdown
---
name: Rádio Pôr do Sol
theme: Brazilian-tinged sunset — organic, warm, unhurried
duration: 90m
arc: slow-burn             # single-peak | waves | slow-burn | radio-arc
energy: [2, 6]             # overall start -> end
genres: [mpb-bossa, organic-house, afro-brasileiro, afro-house]
---

## Identity
What this station *is* — the crowd, the hour, the feeling.

## Block sequence
1. [Warm Open (MPB downtempo)](../blocks/warm-open-mpb.md)      · 20m · e2→3
2. [Sunset Warmup (Organic)](../blocks/sunset-warmup-organic.md) · 30m · e3→5
3. [Afro-Brasileiro Glow](../blocks/afro-brasileiro-glow.md)     · 25m · e5→6
4. [Golden Hour Afro House](../blocks/golden-hour-afro.md)       · 15m · e6

## Journey (off the genre graph)
mpb-bossa → organic-house → afro-brasileiro → afro-house

## Notes
Where it can flex, when to cut it short, what to follow it with.
```

## Radios vs sets

- A **radio** is a *reusable, themed* arc (a station you can play anywhere).
- A **[set](../sets/)** is a *specific gig* — it may chain several radios and
  loose blocks, tuned to one venue and crowd on one night.
