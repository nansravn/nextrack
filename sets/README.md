# sets/ — full performances

A **set** is a full performance for a specific gig: a venue, a crowd, a date, a
length. You assemble it from [radios](../radios/) and [blocks](../blocks/) along
an arc off the [genre graph](../genres/), tuned to *this* room.

A set is a plan, not a script — keep swap options so you can read the room and
fluctuate on the night.

## File naming

`sets/<date>-<venue>.md`, e.g. `sets/2026-09-12-beach-club.md`.

## Template — copy this

```markdown
---
name: Beach Club — Sunset to Peak
date: 2026-09-12
venue: Beach Club
crowd: mixed, tourists + locals, sunset into night
duration: 3h
arc: single-peak           # single-peak | waves | slow-burn
default_style: hybrid      # continuous | open-format | hybrid (blocks may override)
energy: [2, 9]
---

## Brief
The gig in two lines: the slot, the vibe expected, any hard constraints
(sound curfew, when the sun sets, a headliner to hand off to).

## Program
1. [Rádio Pôr do Sol](../radios/radio-por-do-sol.md)     · 90m · e2→6
2. [Afro → Brazilian Bridge](../blocks/afro-br-bridge.md) · 20m · e6→7
3. [Rádio Baile](../radios/radio-baile.md)                · 40m · e7→9  ← peak
4. [Cooldown Roda](../blocks/cooldown-roda.md)            · 30m · e9→4

## Journey (off the genre graph)
organic-house → afro-house → afro-brasileiro → brazilian-funk → samba-pagode

## Contingencies
- If the crowd is younger/harder: swap block 2 for global-bass → tech-house.
- If it's dead early: start block 1 at e3 and cut the MPB open.
- Handoff: leave the next DJ at e7 tech-house, key ~8A.

## After-action (fill in post-gig)
What landed, what didn't, which graph edges to re-rate.
```

## Close the loop

The **after-action** is where the system compounds: note which transitions
worked, then update edge `strength` in [`../genres/graph.yml`](../genres/graph.yml)
and tweak the blocks. Every gig makes the next plan smarter.
