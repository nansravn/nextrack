# Mixing styles — two philosophies

NEXTRACK supports two ways of DJing, because they are genuinely different crafts —
not "skilled" vs "easy", but **different skills**. Every [block](../blocks/)
declares which one it's in via a `style` field, and that choice drives everything
downstream: how you transition, how you plan, even how much of each track you play.

## The two modes

- **`continuous`** — the blend/EDM journey. The music was *made to be mixed*:
  beat-only intros in multiples of 8, instrumental outros, a locked BPM grid. Your
  job is one unbroken journey — the crowd often can't tell where one track ended.
- **`open-format`** — the recognition party (a 2000s theme going axé → pagode →
  funk → dance-pop). The music was *made for radio*: vocals almost immediately,
  fade/applause endings, sometimes no constant BPM at all. The crowd doesn't want a
  journey — it wants to *recognize* the song. The magic moment is the first second
  of a hook everyone already sings, **not** the transition.
- **`hybrid`** — the honest reality of most sets: you *blend within* a genre block
  and go *open-format between* blocks.

## The root difference

| | `continuous` | `open-format` |
|---|---|---|
| Music built for | mixing | radio |
| What the crowd wants | a journey | recognition |
| The magic moment | the transition | the first beat of the hook |
| Transition length | long (32–64 beats) | short — cut / echo / FX |
| Key mixing | central | mostly only for acapellas |
| BPM | locked grid | often flat / live-band drift |
| How much you play | most of the track | the **hook window** (~1:30–2:30) |
| Success metric | seamlessness | **moments per hour** |

The last row is the mindset shift: in open-format a long transition is a *defect* —
it spends seconds of a song people know. You want the *maximum number of
recognition moments per hour*, so you get in, hit the hook, and get out.

## What changes downstream

**Planning.** Continuous plans an *energy curve* by BPM and key (see
[energy-arcs.md](energy-arcs.md), [harmonic-mixing.md](harmonic-mixing.md)).
Open-format plans **genre blocks** — 20 min of dance-2000s → a pagode block → back
up through axé → close on funk. The delicate moment is the *block change*, and it's
where you deploy an effect, a vignette, or a bridge track.

**Transitions.** Continuous → long blends, EQ swaps, harmonic layering.
Open-format → hard cut on the downbeat, echo out, backspin, teasing, FX bridge. The
full toolkit and which move fits which situation is in
[transitions.md](transitions.md).

**Track choice.** Continuous wants mixable intros/outros. Open-format wants the
*hook* — you cue to the chorus, not the top of the song, and you may only ride
1:30–2:30 of it.

**BPM.** Continuous stays inside a tempo band and bridges with half/double-time.
Open-format jumps freely (pagode ~95 → axé ~105 → dance ~126 → funk ~150) and
resolves the gap with an echo out, a half-time lock, or an accepted cut.

## Using the `style` field

Blocks carry `style`; sets carry an optional `default_style` that blocks override:

```yaml
# a block
style: open-format        # continuous | open-format | hybrid
```

```yaml
# a set
default_style: hybrid     # continuous | open-format | hybrid (blocks may override)
```

The [genre graph](genre-graph.md) serves both modes: in `continuous` you follow a
harmonic/BPM edge; in `open-format` you follow the same edge but execute it as a
cut or FX bridge (edges whose `via` reads like "hard cut on the downbeat" or "echo
out across the BPM gap").

> Rule of thumb: your beatmatch never stops being an asset — in open-format it
> becomes your edge *inside* each genre block. What open-format adds is real-time
> crowd reading and a sense of *show*, which a continuous set exercises less because
> the music's own structure carries the energy for you.
