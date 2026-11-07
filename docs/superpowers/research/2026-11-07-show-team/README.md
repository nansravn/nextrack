# Project 2 benchmark — synthesis

Date: 2026-11-07. Question: how should a team of AI agents create, critique and iterate the
light shows of NEXTRACK, inside Claude Code, so that a show is **not monotonous**, **immersive at
the drops**, **follows the energy of each track** and **follows the energy of the set** (the
owner's four criteria)? Three parallel research fronts, raw notes next to this file:

- `A-orchestration.md`: how multi-agent loops are built and run (superpowers, Anthropic
  guidance, Claude Code primitives, skill-creator, BMAD, spec-kit, general frameworks).
- `B-creative.md`: multi-agent creative generation (Re3/DOC, Agents' Room, Dramatron, CritiCS,
  FilmAgent, ComposerX/CoComposer, SceneCraft/Idea2Img, self-critique and judging evidence,
  homogenization).
- `C-craft-analyses.md`: how lighting designers work energy and drops, music-driven lighting
  research, MIR analyses, precompute vs on demand, and what the repo measures today.

Each raw note marks every claim as read, abstract only, recalled or measured, with URLs.

## 1. What the evidence says

1. **Plan the arc first, then re-inject a slice of it into every writer.** Long works that
   hold together (Re3, DOC, Dramatron) plan a short middle layer before the details and give
   each writer the relevant plan items, the neighbours and a summary of what came before. DOC's
   three-level outline beat Re3 by +22.5 coherence points. (B §1.1, §1.3)
2. **Parallel writers repeat each other.** Agents' Room section writers, sharing a scratchpad,
   reached 47.5 intra-story trigram repetition against 15.5 for human stories; FilmAgent's
   failures included consecutive identical shots. One agent per track is the main monotony
   risk. (B §1.2, §1.5)
3. **A critic needs an outside signal.** Self-critique without tools adds little or hurts
   (CRITIC; GPT-4 GSM8K 95.5 → 89.0 with intrinsic self-correction). The big gains come from
   critics that sense the output and score constraints written as code (SceneCraft 26.1 →
   88.9). Agents "reliably skew positive when grading their own work" (Anthropic). (A §3.3,
   B §3)
4. **LLM judges of creative work are weak and drift to the typical.** No LLM judge correlated
   with experts on TTCW; GPT-4 prefers its own text 0.71–0.91; judges favour low-perplexity
   text. Metrics catch gross failures; the owner in the room is the final judge. (B §3)
5. **Homogenization is severe; model-swapping barely helps.** About 200 unique ideas out of
   4,000 seeds (Si et al.); models are 0.71–0.82 similar to each other (Artificial Hivemind).
   What works: asking for N options with their probabilities (verbalized sampling, 1.6–2.1×
   diversity), a quality-diversity archive on axes you define, dedupe by a computed signature.
   (B §4)
6. **Multi-agent wins on structure and repeated choices, not on local aesthetics**, and a
   small team in a fixed order beats free-form chat. (B §5, A §3.2)
7. **Stop early, keep every version.** Two or three rounds capture most of the gain; more
   rounds trade coherence for novelty, so pick the best across rounds. Top failures in MAST:
   step repetition and not knowing when to stop; one role owning the stop helps. Minor
   findings never enter the fix loop. (A §3.4, B §5)
8. **Handoffs are files; replies are short.** Workers get a brief file, the binding
   constraints verbatim and an output contract; they write a report file and return ~15
   lines. A skill-driven controller loses its place after compaction: keep a ledger file in
   git, never conversation memory. (A §1.1, §3.1)
9. **Cost.** Multi-agent ≈ 15× the tokens of a chat; keep 3–5 agents in parallel, name a model
   per dispatch, batch same-shape edits. (A §3.5)
10. **Measure the skill, not the vibe.** Run with and without it on the same cases (≥ 3 runs),
    cases drawn from real failures, graders = code checks + model judge + human, human last.
    (A §1.5, §3.6)
11. **Lighting craft rules of thumb exist and are checkable**: dip or dark before a payoff, a
    distinct look per major drop, save the big looks, intensity in waves, builds grow in rate
    and density, changes on phrase lines, the main drop gets the biggest answer, start minimal
    and add as the night grows. Literal event-to-light mapping reads "repetitive, predictable,
    too explicit". (C §2, §7)
12. **No prior art for agents in lighting or DJ sets.** Stage-lighting research learns frames,
    has no notion of drops or a set arc. NEXTRACK's metrics are its own. (B §2, C §3)

## 2. What the repo measures today (verified)

Measured on `hi-ibiza-pulso` (C §1.3; the first two rechecked independently):

- **The music level is saturated:** 82% of the 2,179 bars of the 15 maps read 9
  (`max(kick, bass, other)`, each voice scaled to its own peak). The strips cannot show shape
  inside a drop, nor compare tracks.
- **The light level cannot see speed:** rate, strobe, white, colour and aim changes do not
  enter it; pingpong/blink are a flat 0.5. In the peaks table, 30 of 35 drops read 3 at the
  drop and 17 do not rise; no bar of the night reads above 5.
- **Light falls as the owner's energy rises:** mean light per track ≈ 3.4 (e6), 3.1 (e7), 2.8
  (e8), 2.7 (e9). The critic cannot tell whether the show fails the set or the index is blind.
- **The views never read the energy plan** (pool `energy`, block `energy: [6, 9]`).
- Night summary facts: inline looks 29:02 of 44:09; movers azul-gelo 37:55 (86%); the top two
  aims 79%.

Consequence: a critic or a dashboard built on today's indices would report noise as findings.
Three of the four criteria have a measure in name only.

## 3. Implications for NEXTRACK

### 3.1 Analyses: precompute the music, compute comparisons on demand (A §4, C §5, §8)

- **Tier 0, per track, precomputed and committed** (map v2, stale by audio hash as today):
  absolute loudness per bar on a scale shared by all tracks, brightness, onset density and
  texture (the last two derivable from today's maps), a tension curve, drop salience (ΔL, bass
  return, main drop), a short track summary.
- **Tier 1, per set, generated** (~2–4k tokens): the clock, owner energy and measured summary
  per track, the night's drops ranked, a target energy per minute, the block function and arc,
  bridges and arrivals. The director reads it whole.
- **Tier 2, on demand:** `report`, `zoom` and new views (agreement, drops, builds, variety,
  arc), filterable per track or window, concise or detailed. A track agent gets its own slice,
  not the 51 kB report.
- Agents never run audio analysis. A new analysis lands like a gesture: code, tests, re-analyse.

### 3.2 New measures (C §6, formulas there)

G1 music energy per bar (shared scale) · G2 light brightness and activity from the compiler's
own samples, plus change events per bar · G3 follows the track (shape, direction at section
boundaries, lag) · G4 drop salience vs light response (contrast, change, freshness) · G5 builds
build · G6 monotony and chaos (static runs, windowed variety, dominance against declared
signatures, consecutive-track similarity, drop-template predictability, phrase alignment) ·
G7 set arc (target vs light per track, headroom, staircase, step proportionality, breathers).
Robust ones become rules; the rest are advice and critic rubric items.

### 3.3 The team (A §5, B §6)

- **Director** = the main session following a project skill, with a run folder holding a
  ledger of decisions and versions (survives compaction).
- **Arc cards first:** one card per track (energy target, role in the arc, arrival idea, peak
  moment, look family, declared signatures). A fresh agent reads the night design before any
  track is written and lists what it would have to guess.
- **Track designers** get the story, their card, the neighbours' cards and handovers, a
  **ledger of what the night already uses**, and their slice of the views. Each proposes N
  options before choosing.
- **Critics:** fresh, read-only, never see the author's reasoning, one lens per criterion,
  every finding cites a bar or report line, routed as fix / decision / later.
- **Effects engineer:** new gestures through the existing SDD loop (code + tests).
- **Mix owner:** each mix (outgoing handover + incoming bridge) has one owner; the 23 bridge
  findings are 13 mixes, batched, with a before/after diff of computed facts to prove the story
  survived.
- **Loop:** one change per round, variants built with `--out`, at most 3 rounds per track and 2
  for the night, every version kept, the director picks and owns the stop.
- **Guard:** a `PreToolUse` hook blocks `apply`; writing SoundSwitch stays the owner's call by
  enforcement.
- **Conflict to resolve:** the `lightshow` skill asks the owner to approve each track before
  writing, which contradicts end-to-end autonomy.

### 3.4 The owner's dashboard ("the night's identity book")

The owner proposed an HTML report per set, styled like a visual identity presentation:
concept, palette with minutes, what the night does and for how long, the signature that
repeats on purpose. The benchmark supports it: facts computed by tools, intent written by the
team before creating ("promised vs delivered"), the owner as the final judge. It is the human
face of G2–G7 and the brief, and has no precedent to copy.

## 4. Questions put to the owner

Answered in the design, [2026-11-07-show-team-design.md](../../specs/2026-11-07-show-team-design.md).


- Order: sharpen the senses (measures + set brief + dashboard) before the team, or the team
  first on interim measures (G1's no-audio version, G2)?
- Is re-running `nextrack_map.py analyze` on all tracks acceptable (map v2)?
- Does the `lightshow` skill's per-track approval go away for shows written by the team?
