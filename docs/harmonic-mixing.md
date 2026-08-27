# Harmonic mixing — keys & BPM

Two tracks sound "right" together when their **keys** are compatible and their
**tempos** are close (or in a clean half/double-time relationship). NEXTRACK
records both for every track so you can plan smooth moves in advance.

## The Camelot wheel

The Camelot system relabels musical keys as a clock so compatibility is obvious:
a number (1–12) + a letter (**A** = minor, **B** = major).

| Camelot | Key | Camelot | Key |
|--------|------|--------|------|
| 1A | A♭ minor | 1B | B major |
| 2A | E♭ minor | 2B | F♯ major |
| 3A | B♭ minor | 3B | D♭ major |
| 4A | F minor | 4B | A♭ major |
| 5A | C minor | 5B | E♭ major |
| 6A | G minor | 6B | B♭ major |
| 7A | D minor | 7B | F major |
| 8A | A minor | 8B | C major |
| 9A | E minor | 9B | G major |
| 10A | B minor | 10B | D major |
| 11A | F♯ minor | 11B | A major |
| 12A | D♭ minor | 12B | E major |

## The compatible moves

From any track's Camelot code, these blends are harmonically safe:

- **Same code** (e.g. 8A → 8A) — perfect, same key.
- **±1 on the wheel** (8A → 7A or 9A) — adjacent, very smooth.
- **Switch letter, same number** (8A → 8B) — relative major/minor, a nice lift.
- **+7 "energy boost"** (8A → 3A) — a bold, uplifting jump (dominant); use with intent.

Everything else risks a clash — fine for a hard cut or an effect-covered
transition, but not a blend.

## BPM matching

- **Within ~±3 BPM** — beatmatch/blend directly.
- **~±6 BPM** — doable with a tempo nudge; watch for pitch on vocals.
- **Half / double time** — e.g. funk 150 ↔ house 122-ish worlds. Feel the groove
  at half or double and the two lock together. This is how many `graph.yml` edges
  work (`via: "double/half-time..."`).
- **Bigger gaps** — when tempos are too far apart to blend, *execute* the move with
  an echo out, a half-time lock, or an accepted hard cut. See
  [transitions.md](transitions.md#jumping-big-bpm-gaps).

## In practice

- Record every track's key in **Camelot** (`key: 8A`) and its **BPM** in
  [the catalog](../tracks/).
- When building a [block](../blocks/), write the **key journey** and **BPM path**
  right next to the tracklist, so cold transitions are pre-solved.
- Analysis tools (rekordbox, Serato, Mixed In Key, Beatport's own key tags) will
  give you the Camelot code — just copy it in.

> Rule of thumb: plan the *harmony and tempo* here, keep the *feel* in your ears.
> The wheel tells you what's safe; the room tells you what's right.
