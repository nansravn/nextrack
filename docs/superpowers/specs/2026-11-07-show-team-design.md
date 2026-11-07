# The show team (project 2) — design

Date: 2026-11-07. Branch `feat/show-team`. Builds on
[the show language](2026-11-06-show-language-design.md) (PR #14) and
[the critic's senses](2026-11-06-show-critic-design.md) (PR #15), whose terms (show, cue,
bridge, handover, provenance, occurrence, finding, advice, leg, sounding window, aim) this
document uses without redefining them. The research behind it is in
[`docs/superpowers/research/2026-11-07-show-team/`](../research/2026-11-07-show-team/README.md).

## Why

The owner wants a team of AI agents that creates and evolves the light shows on its own. The
team comes up with the night's theme, designs its arc, writes the show with the vocabulary of
project 1, creates new gestures when a word is missing, critiques its result, thinks about
what could be better or different, and iterates. The owner manages the backlog: they bring a
set and a simple idea, or feedback from the room. At the end they receive the show, built and
compiled, and a **book of the night**: an HTML presentation, like a visual-identity designer's,
that explains the night's identity. It covers the palette, how many minutes each thing plays,
and the signature the night repeats on purpose. The owner reads the book before playing, then
sees the lights in the room. Their feedback becomes the next request. The backlog itself and
the feedback memory are project 3.

The owner's success criteria, in their words: the show is **not monotonous**, it is
**immersive at the drops**, and it **follows the energy of each track** and **the energy of
the set**. For the team's process, the owner asked to follow the best practices of the
benchmark rather than only their own picture. Their picture: a critic who sees the whole,
takes the best of each agent's view, and heals the work when it goes the wrong way.

### What the benchmark found

Three research fronts (orchestration practice, multi-agent creative systems, lighting craft
and music analyses) are summarised in the research folder's `README.md`. Six findings shape
this design:

1. **A critic needs a signal from outside the model.** Self-critique without tools adds little
   or makes things worse. The big gains come from critics that read computed facts and check
   constraints written as code. Agents "reliably skew positive when grading their own work".
2. **LLM judges of creative work are weak and drift toward the typical.** So computed checks
   catch the gross failures, independent critics judge, and the owner in the room gives the
   verdict.
3. **Parallel writers repeat each other, and models converge on the same ideas.** The fixes
   are a shared record of what the work already uses, asking for several options before
   choosing, and repetition checks that are computed.
4. **Plan the arc first, then give each writer a slice of it.** Long works that hold together
   plan a short middle layer (one card per part) and re-inject it into every writer's brief.
5. **Small teams in a fixed order, files as handoffs, and few rounds.** Two or three rounds
   capture most of the gain. Keep every version and pick the best. One role owns the stop. A
   ledger on disk survives what conversation memory does not.
6. **Today's senses are blind to three of the four criteria** (measured on Hï Ibiza, and
   checked twice). 82% of the night's bars read music level 9. The light level ignores rate,
   strobe and white. 30 of 35 drops read 3 at the drop, and 17 do not rise. By that index the
   light *falls* as the owner's energy rises (mean 3.4 at e6, 2.7 at e9). The views never read
   the owner's energy plan.

Finding 6 sets the order of the work. A team whose critics read today's numbers would chase
noise. The senses come first.

## Two deliveries

| | what | nature | PR |
|---|---|---|---|
| **2a** | the senses and the book: energy measures, new views and checks, the night's identity, the echo, `brief`, `compare`, `book` | deterministic tooling, like project 1.1 | first |
| **2b** | the team: a project skill, role agents, the run and its ledger, the guard on SoundSwitch writes, a rehearsal | agent workflow | second, after 2a is merged |

Each delivery gets its own plan and PR. The owner approves the design once, for both. The
team's first real run (Hï Ibiza's bridges) comes after 2b is merged. Claude Code picks up
new files in `.claude/agents/` and `.claude/skills/` during a session, except when the folder
did not exist when the session started; this repo had no `.claude/agents/`, so the session
that writes the team needs a restart to dispatch it. The team's worktree also branches from
`origin/main`, which has the skill only after the merge. The run is its own branch and PR,
like any content work.

## Goals

**2a, the senses and the book**

1. **Map v2.** The musical maps gain a `mix` block (loudness and brightness per bar), read
   from the audio without re-running the stem separation. Every repo map is upgraded, and no
   v1 field changes.
2. **Music energy per bar** that does not saturate, from loudness, brightness, onset density
   and texture.
3. **Light measures from the compiler's own output:** brightness and activity per fixture
   group, and change events per bar. They replace the 1.1 light-level index.
4. **New views** in `report`: follows-the-track, the night's drops ranked, builds, variety,
   arc, and identity. `report` gains filters so an agent reads only its slice.
5. **Identity:** an optional `identity:` block in `show.yml` where the show declares its
   signatures (what repeats on purpose) and their intended share of the night.
6. **New show rules** for the checkable rules of thumb, used as advice by default.
7. **`brief`:** a generated, compact description of a set's music (the clock, the owner's
   energy per track, the drops ranked, the target arc) that needs no show.
8. **`compare`:** the facts of two shows side by side, with an exit status for facts that must
   not change.
9. **`book`:** the book of the night, a self-contained HTML file generated from the show, the
   maps and the views.
10. **The echo:** when `bridge.bars` cuts a handover before the end of the outgoing track, the
    compiler copies the incoming track's light onto the rest of the outgoing track. Whichever
    script SoundSwitch plays during a long mix, the room sees one light.
11. **Hï Ibiza:** maps upgraded, `identity` declared from its plan, the new advice declared,
    and its book generated. Its choreographies do not change.

**2b, the team**

12. **A project skill `show-team`:** the rite the main session follows as the **director**.
13. **Role agents** in `.claude/agents/`: a cold reader, a designer, a critic (one agent,
    several lenses) and a gesture engineer.
14. **The run:** intake → brief → concept or diagnosis → cold read → design batches → gates →
    critique → consolidation → selection → delivery. It has a ledger committed in the show
    folder and bulky artifacts in a scratch run folder. A run can resume from its ledger.
15. **The guard:** a `PreToolUse` hook that makes Claude Code ask the owner before any command
    that writes SoundSwitch.
16. **The `lightshow` skill:** its per-track approval step does not apply to shows the team
    writes.
17. **A rehearsal** of the whole run on a small case before the PR. The **first real task**,
    Hï Ibiza's 23 bridge advice findings (13 mixes), is the team's first run after 2b is
    merged, in a fresh session the owner starts (B8).

## Non-goals

- The backlog, the feedback memory and an eval harness built on the owner's verdicts: those
  are project 3. 2b documents the eval protocol that project 3 will fill.
- New low-level vocabulary (a real spiral, heartbeat decay, voice beams, an equalizer, stereo
  mapped onto the room): project B. The team can add gestures, which only emit today's
  vocabulary.
- Compiling UV (waits for X11), measuring the room, creating the pending presets: owner tasks.
- Choosing tracks, deciding the mix or setting hot cues. The set and its hot cues `B`/`G` are
  the owner's; the team lights them.
- Pushing, opening PRs, merging or writing SoundSwitch. The team stops at a branch.
- A vision model watching the simulator. A render is not haze and beams; it may be tried later
  as a weak proxy.

## Anti-goals

- **A critic that grades its own work.** The director never gives the verdict on what it
  decided; the critics never see the author's reasoning.
- **Numbers that pass for taste.** Every measure has a stated formula in a docstring, and the
  views never say "boring". A computed check catches a gross failure; judgment stays with the
  critics and the owner.
- **Churn.** Changing the show without making it better: minors never loop, rounds are capped,
  and every version is kept.
- **A metric that becomes the goal.** Variety checks have a chaos guard, and declared
  signatures are exempt from the monotony checks.
- **Silent team decisions.** Every overruled critic finding and every choice between variants
  is a ruling in the ledger, and the book prints it.
- **Agents computing music facts ad hoc.** Music analysis is a committed, tested tool, run
  before any show depends on it.

---

## Part A — the senses and the book (2a)

### A1. Map v2: the `mix` block

`map_version: 2` adds one required block:

```yaml
mix:
  loudness: '5566778899998888...'    # one digit per bar
  brightness: '2233445566667777...'  # one digit per bar
```

- **`loudness`**: the mix's loudness per bar, as digits relative to the track's own loud
  reference (the same idea as the voices' `bars`, with a resolution fine enough that a break
  reads below the drop around it). The mix is the decoded audio, not a sum of stems.
- **`brightness`**: the share of the mix's energy at high frequencies per bar (or its spectral
  centroid), as digits normalised over the track's own range (its 5th to 95th percentile), so
  a filter opening through a build reads as a rise.
- Both are relative to the track. That is deliberate: rekordbox's auto-gain and the DJ level
  tracks in the room, so absolute loudness across tracks describes the mastering, not the
  night. The set's arc comes from the owner's labels (A2).
- **Exact formulas, the reference, the digit step and the high-frequency cutoff are the
  builder's**, stated in docstrings. They are calibrated on the 15 maps against the acceptance
  checks of A2.

**The upgrade.** A `nextrack_map.py` command (its name is the builder's) adds the `mix` block
to an existing v1 map from the audio file. It finds the file the way `analyze` does, never
runs the separator and needs no GPU. It refuses when the audio's hash differs from the map's
`audio.sha256` (the audio changed: re-analyse). Every v1 field stays byte-identical, and a test
asserts it. `analyze` writes v2 from now on. A v1 map stays valid (the `musical-map` rule
accepts both versions). The views fall back to the interim formula (A2) for a track without
`mix` and say so. All 15 repo maps are upgraded in 2a, and `build --check` on Hï Ibiza stays
clean.

### A2. Music energy per bar

`E_music(b)`, a digit 0-9 per bar, combines four features of bar `b`:

| feature | from | needs audio |
|---|---|---|
| `L` loudness | `mix.loudness` | yes (map v2) |
| `C` brightness | `mix.brightness` | yes (map v2) |
| `D` onset density | steps of the bar with a `kick` or `perc` onset of strength ≥ 3, divided by 16 | no |
| `V` texture | voices whose bar digit is ≥ 6 (0-5) | no |

The starting formula is `round(9 × (0.4·L̂ + 0.2·Ĉ + 0.2·D̂ + 0.2·V̂))`. The hat is a feature
normalised over a scope: **the track's bars** for the track views, **the night's played bars**
for the set views. The interim formula, for a v1 map, is `round(9 × (0.5·D̂ + 0.5·V̂))`, and
every view that uses it marks the track `(interim)`.

**Acceptance on Hï Ibiza** (the builder tunes the weights to meet it and reports the final
values):

- no digit holds more than 40% of the night's bars (music level 9 holds 82% today);
- at 80% or more of the map drops that follow a `break` or `build`, the mean `E_music` of the
  drop's first 4 bars is higher than that of the 4 bars before it.

**The set's target energy** comes from the owner's labels, not from loudness. It uses each
track's `eN` from its block tracklist line (else the pool's `energy`), the block's
`energy: [a, b]` and `function`, the set's `arc`, and the tempo ramp. It is interpolated per
minute on the set clock. The **label check** ranks the tracks by measured night-normalised
`E_music` and by BPM. It lists the tracks whose rank differs from the owner's energy rank by
three places or more, as a question for the owner and never as a fix.

`music_level` (the maximum of three voices) is retired. The strips print `E_music`, and the
section lines keep the voices (`k9 b7 v0 p8 o7`).

### A3. Light measures from the compiler

The light is sampled the way `zoom` samples it: the compiler's own generators, one sample per
1/16 step, 2 ms in, for each fixture group of the rig (mover NE, mover SE, Vorlane NW,
Vorlane SW, lustre, white strip, strobe).

- **Brightness** `B_f(b)`: the mean over the bar's steps of the group's level × coverage
  (coverage is the lit share of a Vorlane's colour cells, and 1 for a single lamp).
- **Activity** `A_f(b)`: dark→lit rises in the bar divided by 16 (a strobe pulse is a rise).
- **Change events** `X(b)`: how many of the light's dimensions change value at bar `b`. The
  dimensions are mover move, mover rate, mover colour, aim, matrix draw, matrix rate, matrix
  colour, hue state and hue colour.
- **`E_light(b)`** is `round(9 × (0.5·B̂ + 0.5·Â))`, with `B = Σ w_f·B_f` and `A = Σ w_f·A_f`.
  The starting weights are movers 0.35 (both), Vorlanes 0.35 (both), lustre 0.15, white 0.10
  and strobe 0.05, normalised over the night. The weights are a stated design call.
- The views print **brightness and activity apart** as well as `E_light`. A drop that is
  dimmer but much faster is a legitimate design, and the critic must see it.
- A bar whose movers, matrix or hue is `auto` is unknown (`~`). It is left out of every
  correlation and counted as the night's unknown share.

`light_level` and its table are retired. The strips, the peaks, the hit checks and the zoom's
level digits use these measures. The manual's "Levels" section is rewritten with the formulas.

### A4. The views

`report` keeps its order and its facts, with the new measures in place of the old indices. It
gains six sections (formulas in the research notes, front C §6, which the builder may refine
and must state in docstrings):

- **follows** (per track): `ρ` (Spearman) of `E_music` vs `E_light` over the leg; direction
  agreement at section boundaries (the share of boundaries where the music moves by ≥ 2 and
  the light moves the same way by ≥ 1); the **missed boundaries**; the **unmotivated changes**
  (for information); the lag (cross-correlation over ±8 bars, flagged beyond 1).
- **drops** (night): every sounding map drop ranked by **salience** `S_d`. It weighs the
  loudness rise over 8 bars, the bass return, the onset-density rise, and whether it is the
  track's main drop (its biggest or its last). Each drop gets its light **response**: contrast
  (light at the drop against the 2 bars before), change (dimensions changed at `d`) and
  freshness (the share of the drop section's dimension values not seen in the 10 minutes
  before). It also prints the rank agreement between salience and response.
- **builds**: for each build of 4 bars or more (a map `build`, or the last 4-16 bars of a
  `break` before a drop), the music's tension slope against the light's activity and coverage
  slope, and whether the light dips or ramps into the drop ("flat into the drop" is the
  failure).
- **variety**: the longest static runs (identical light signature, in seconds, top 5, with the
  music under them). A per-minute strip of windowed variety (normalised entropy over 4
  minutes). Night dominance per dimension, with declared signatures marked. Consecutive-track
  similarity. Drop-template predictability (distinct templates / drops). Phrase alignment (the
  share of changes on 4-bar lines from a section start, or on map boundaries). Also **what the
  night uses, per track**: looks, colours per zone, aims, gestures and drop templates. This is
  the record the designers read.
- **arc** (night): the target energy against the light per track (mean and 90th percentile of
  `E_light`, activity, warm-colour share, rare resources), with these checks:
  - `ρ` between the owner's energy and the light per track;
  - **headroom**: the brightest light before the peak against the night's brightest;
  - **staircase**: a new light maximum only where the energy reaches a new maximum;
  - **step proportionality**: a light jump with no energy step, or flat light across an
    energy step;
  - **breathers**: a calmer stretch after each top drop.
- **identity**: each declared signature's intended share against its measured share, its
  occurrences on the clock, and the most present undeclared value per dimension.

**Filters.** `report <show> --track "<Artist — Title>"` prints that track's header, strips,
section lines, follows, builds and its drops. It also prints the neighbours' handover and
bridge lines and the night-level lines that name the track. `--section <name>[,<name>]`
prints only those sections (summary, tracks, peaks, hits, follows, drops, builds, variety,
arc, identity, budget, arrivals, advice, decided, findings). A track slice of Hï Ibiza stays
under about 3k tokens.

### A5. Identity: the promise

```yaml
identity:
  arc: single-peak                 # optional; default: the set's arc (single-peak | waves | slow-burn)
  signatures:
    - name: azul-espaco
      intent: 'O azul é o espaço da noite: os feixes moram nele.'
      is: {movers.colour: [azul-gelo, azul-profundo]}
      share: {min: 0.6}
    - name: coracao
      intent: 'O vermelho é o coração, no centro da sala.'
      is: {hue.colour: [carmim, vermelho]}
      share: {min: 0.5}
```

- `identity` is optional. `signatures` is a list of `{name, intent, is, share?}`. `name` is
  kebab-case and `intent` is pt-BR prose.
- `is` maps dimensions to a value or a list of values. The dimensions are `look`, `gesture`,
  `movers.move`, `movers.rate`, `movers.colour`, `aim`, `matrix.draw`, `matrix.rate`,
  `matrix.colour`, `hue.state` and `hue.colour`. Colours are palette names and aims are aim ids.
  A section carries the signature when every listed dimension matches (a list means any of its
  values).
- `share` is `{min?, max?}`, a fraction of the night summed over legs.
- Unknown dimensions, values outside the palette or the aim catalogue, and bad shares are
  `show-source` findings.
- Declared signature dimensions are exempt from the variety checks' dominance. That is how a
  conscious repetition differs from monotony.

### A6. New show rules

Each is a registered rule with a docstring, a `check`, tests for the passing and failing case,
and a row in the manual's rules table. A show can use it under `advice:` or `rules:`. Hï Ibiza
uses all of them under `advice:`.

| rule | criterion | finding when |
|---|---|---|
| `signatures` | identity | a declared signature's measured share is outside its `share` |
| `static-run` `{max_seconds}` | monotony | a run of identical light signature lasts longer |
| `neighbours-differ` `{max_similarity}` | monotony | two consecutive tracks' time-share vectors are more similar (bridges excluded) |
| `distinct-drops` `{top}` | monotony, drops | two consecutive top drops share the same light template |
| `drop-contrast` `{top, min_change}` | drops | a top drop has no positive contrast, or fewer than `min_change` dimensions change |
| `main-drop` | drops | a track's main drop gets a weaker response than an earlier drop of the same track |
| `follows-track` `{min_rho?, max_lag?}` | track energy | a track's `ρ` is below `min_rho`, or its lag is beyond `max_lag` |
| `follows-set` `{min_rho?, max_headroom?}` | set energy | the night's `ρ` is below `min_rho`, or the headroom is above `max_headroom` |
| `phrase-aligned` `{min_share}` | chaos guard | the share of changes on phrase lines is below `min_share` |

- `top` is a count or a fraction of the night's drops ranked by salience.
- Defaults and the Hï Ibiza thresholds are the builder's, documented in the manual.
- A finding points at the cue or handover to change when there is one, otherwise at the rule's
  line in `show.yml`.
- Rules may read the maps, the clock and the light samples, so the rule API gives them the
  views' data. A rule whose input is missing (an unknown light, a v1 map) reports it and never
  passes silently.
- Builds, breathers and step proportionality stay **views only**: the critics judge them.

### A7. `brief`

```bash
uv run scripts/nextrack_show.py brief sets/hi-ibiza-pulso.md     # a set path, or its stem
```

It is a generated text that needs no show (about 2-4k tokens for 15 tracks):

- the night (length, arc, block functions, tempo ramp);
- per track, in order:
  - the clock (enters, leg minutes);
  - `B`, `G` and the mix windows (the bars from `G` to the end);
  - the owner's energy;
  - the measured energy summary (night-normalised `E_music` mean and 90th percentile);
  - a section strip (letters, as `nextrack_map.py show`);
  - vocal presence;
- the night's drops ranked by salience, with their clock;
- the target energy per minute, as a strip;
- the label check's questions;
- tracks without a map, without `mix`, or missing a hot cue that bridges need.

The director reads it whole. A map missing or invalid is a line in the brief, not a crash.

### A8. `compare`

```bash
uv run scripts/nextrack_show.py compare hi-ibiza-pulso <scratch>/variant
uv run scripts/nextrack_show.py compare hi-ibiza-pulso <scratch>/variant --keep arrivals,moments,signatures
```

It compiles both shows (an id or a folder; folders outside `lightshows/shows/` are fine) and
prints, per fact, what differs:

- arrivals (bar, look, draw, colours);
- moments (bar);
- each drop's response;
- signature shares, look minutes, colour minutes per zone;
- bridge and handover lengths;
- the counts of findings and advice per rule.

With `--keep`, it exits 1 when one of the named facts differs. That is how the team proves a
rework kept the story. Without `--keep` it exits 0.

### A9. `book`

```bash
uv run scripts/nextrack_show.py book hi-ibiza-pulso -o <scratch>/book.html
```

It is a single, self-contained HTML file (inline CSS and SVG, no scripts from anywhere, no
network), deterministic for the same inputs. The labels are pt-BR (the owner reads it). The
prose comes from the show. Its sections follow a visual-identity presentation:

1. **Capa:** the show, the set, the night's length, the story.
2. **Conceito:** the story, the arc's shape, the declared signatures with their intents, and
   the director's decisions from the ledger (A10).
3. **Paleta:** swatches (palette name, hex), minutes per zone, proportion bars, and a **colour
   score**: the night as a ribbon per zone (movers, Vorlanes, lustre), coloured section by
   section on the clock.
4. **Assinaturas:** promised against delivered share, occurrences on the timeline, and the
   most repeated undeclared element.
5. **Vocabulário:** each look as a card (layers in words, minutes, count, where), the gestures,
   the aims with their figures (pending ones marked with their stand-in).
6. **Arco:** the target energy, `E_music` and `E_light` over the clock, with the BPM, in one
   chart.
7. **Momentos:** the drops ranked by salience with their light response, the arrivals, the
   moments.
8. **Ritmo e variedade:** static runs, the variety strip, changes per minute, and what each rare
   resource spent (strobe, white, total dark, spirals) against its budget.
9. **Música por música:** one card per track: story, arrival, peak, strips, bridge in and out.
10. **O que a ferramenta não sabe:** the autoscript's share, pending aims and their stand-ins,
    `room.yml` assumed, UV not compiled, the measures being indices with formulas.
11. **Avisos:** the advice still open.

The HTML follows the Artifact page contract, so the team can publish it as a private Artifact:

- a `<title>` of two to four words;
- colour tokens on `:root` with a dark-mode override;
- an explicit `body` background;
- a layout that works at phone width.

The show's palette swatches show the real colours in both themes. A test asserts the file is
deterministic, has no external reference and holds every section. **The owner reviews the
first generated book (Hï Ibiza); their notes become backlog items, not a blocker.**

### A10. The ledger, as the book reads it

`lightshows/shows/<id>/ledger.md` is the team's record, committed. The loaders read only
`*.yml` in a show folder, so it is ignored by the compiler. 2a defines its format so the book
can read it; 2b writes it.

```markdown
# Diário do time — hi-ibiza-pulso

## 2026-11-08 — Pontes de até 16 compassos sem perder a história
Pedido: ...
Rodadas: 2 · versões: v1, v2 (escolhida: v2)

### Decisões
- A ponte da Rapture para a Akan termina no compasso 72: ... (custo se errado: ...)

### Para depois
- ...
```

The book prints the latest run's "Decisões" and "Para depois". Without a ledger, those parts
are left out.

### A11. The echo: the rest of a long mix

With `bridge.bars`, the outgoing handover runs `bars` bars from `G`, and today the outgoing
track's bars after it go back to the autoscript. Many of the owner's mixes are longer than the
window: 40 bars from The Rapture into The Akan. During that time the room hears both tracks,
and which script SoundSwitch plays is still unknown (experiment P1). The plan's rule 9 ("a
ponte é cópia exata": the room sees no cut when SoundSwitch switches scripts) then breaks
unless the outgoing tail shows the same light as the incoming track.

**The echo** keeps the rule. When the show has `bridge.bars`, the track has a handover cut by
it, and the next track takes a bridge, the compiler fills the outgoing track's bars after the
handover. It copies the incoming track's compiled sections over the same stretch of the mix.
The two tracks are beat-matched, and the clock already puts the incoming `B` on the outgoing
`G`, so outgoing bar `k` is incoming bar `k − G + B`.

- The echo runs from the bar after the handover to the outgoing map's end, or to the last
  incoming bar the copy can reach, whichever comes first.
- It copies the states, not the events. The layers are copied exactly, with `faster_from`
  shifted by the offset. `white.accent`, `strobe.hit` and `strobe.roll` are left out, whether
  written raw or by `accents:` (a layer left empty becomes `auto`): the bridge does not copy
  accents either, and an event belongs to the track that plays it.
- Its sections take the incoming sections' names and intents. Their provenance has a new
  `kind: echo` and the record of the incoming cue they copy, so a finding lands in the file
  that owns the chapter.
- Echo sections never count as occurrences (like bridges). The views count them in neither
  the night's states nor its events: the incoming track's leg already holds that time.
- `report` lists each echo under "decided by the compiler". `bridge: false` in the incoming
  track disables both the bridge and the echo.
- A copied section that is `auto` stays `auto`.

Writing it is never needed and never allowed: like the bridge, the echo is made by the
compiler. If P1 later shows that the switch follows the fader inside the window, the echo is
harmless: the outgoing script is just not seen. The manual's bridge section and P1's row in
`docs/soundswitch/experiments.md` say so.

Hï Ibiza does not set `bridge.bars` in 2a, so it gets no echo, and its choreographies do not
change. The team's first run sets it.

### A12. Hï Ibiza in 2a

- Its 15 maps are upgraded to v2 (A1).
- `show.yml` gets `identity`, from its plan's words: blue is the space (movers), red is the
  heart (the lustre). The shares are measured first and declared at what the plan intends.
  When the plan and the measure disagree, the plan wins, and the `signatures` advice shows the
  gap.
- `show.yml` gets the A6 rules under `advice:`.
- `build --check` stays clean: the choreographies do not change.
- Its book is generated, as the acceptance example.

### A13. Validator, CLI and docs

- `check_repo.py`: `musical-map` accepts v1 and v2 (v2 requires `mix`); `show-source` checks
  `identity`. No other new rule.
- `show-compiled` covers the echo like any compiled section.
- `nextrack_show.py`: `report` gains its sections and filters; new subcommands `brief`,
  `compare` and `book`; `vocab` lists the new rules and the identity dimensions.
- Docs:
  - `lightshows/shows/README.md`: identity, the echo, the new measures with formulas, the new
    views, rules, `brief`, `compare`, `book` and the ledger format;
  - `docs/soundswitch/experiments.md`: P1's row says the echo keeps short bridges safe
    whatever P1 finds;
  - `lightshows/README.md`: map v2 and the upgrade;
  - `scripts/README.md`: the commands;
  - `CLAUDE.md`: the commands.

---

## Part B — the team (2b)

### B1. Shape

- **The director** is the main Claude Code session following the `show-team` skill. It owns
  the night: the brief it reads, the concept or the diagnosis, the cards, every dispatch, the
  consolidation of the critics' findings, the stop, the ledger and the delivery. It is the
  owner's "critic who sees the whole", with one correction from the evidence: it **decides
  but does not judge**. Its own work is judged by critics who never see its reasoning. It may
  overrule a finding only with a ruling in the ledger, which the book prints.
- **Role agents** are files in `.claude/agents/`, each with its prompt, tools and model:

| agent | does | tools | context it receives |
|---|---|---|---|
| `show-reader` | reads the night's design cold and lists what it would have to guess | read-only | `show.yml`, the light plan with the cards, the brief |
| `show-designer` | writes one unit (a track file, or a mix: the outgoing handover and the incoming opening) in a scratch copy of the show, builds it with `--out`, and returns the files | read, write, run | a brief file: the story and identity, its card and the neighbours' cards and handovers, the night's usage record, its `report --track` slice, the binding constraints verbatim |
| `show-critic` | judges the night, or a part of it, through one lens; also blind pairwise comparison of variants | read-only (runs the views) | the story, identity, plan and cards, the views for its lens, the lens rubric. Never the director's or the designers' reasoning |
| `gesture-engineer` | adds a gesture through the CLAUDE.md checklist, test first | read, write, run | the requested effect in words, the vocabulary (`vocab`), the gestures code |

- The critic's model is the strongest available. The other models are the builder's call,
  named in each agent file.
- A designer asks for a missing word in its report ("missing gesture: ..."). Only the director
  dispatches the engineer. A new gesture also gets a code review (the superpowers
  requesting-code-review pattern) before designers use it.

### B2. Files

```
.claude/skills/show-team/
  SKILL.md                  # the director's rite (checklist, phases, rules, stop)
  lenses/                   # one rubric per critic lens (B4)
  templates/                # dispatch briefs: reader, designer, critic, compare, engineer
.claude/agents/
  show-reader.md  show-designer.md  show-critic.md  gesture-engineer.md
.claude/settings.json       # the guard hook (B6)
.claude/hooks/              # the hook's script
lightshows/shows/<id>/ledger.md      # the run record (A10), committed
lightshows/sets/<id>.md              # the light plan: the night's design in prose, with the cards
<scratch>/show-team/<id>/<run>/      # briefs, critic reports, variants, books: not committed
```

`<scratch>` is the session's scratch folder, else a temporary folder outside the repo.

- The **cards** live in the light plan as a section, one per track. Each card holds the energy
  target, the role in the arc, the arrival idea, the peak moment and the look family, in pt-BR.
  The design then persists beyond the run, and a later rework starts from it.
- **Versions are commits** on the run's branch: one commit per round, so any earlier version
  of a unit can be brought back.

### B3. The run

The skill gives the director a checklist to copy and keep current. The phases:

0. **Intake.**
   - If the show's ledger has a run that did not reach delivery, offer to **resume** it from
     its last completed phase. The ledger records a state line after every phase.
   - Classify the request: a new show for a set, a rework of the night, or a rework of some
     units.
   - Write in the ledger an estimate of the run's dispatches (units × options, critics,
     comparisons). If the owner set a cap in the request, plan within it.
   - Start a worktree and branch (`feat/show-<id>-<topic>`; creating one needs no permission),
     then `uv sync`.
   - Create the run folder and open the run's ledger entry with the request in the owner's
     words.
1. **Inputs.**
   - Every set track needs a valid v2 map. The director may run `nextrack_map.py analyze` or
     the upgrade when the audio folders are configured. These are deterministic tools, not ad
     hoc analysis.
   - A missing hot cue that the bridges need is an owner task. The run stops and reports it.
   - Read `brief`.
2. **Concept** (new show or rework of the night).
   - Write three distinct concepts, each with an estimate of how typical it is, and choose
     one, with the reason in the ledger. Asking for options with their likelihood counters the
     models' pull to the typical idea.
   - Write `show.yml` (story, palette, looks, identity, rules, advice) and the light plan with
     the cards.

   **Diagnosis** (rework).
   - Read `report` and the advice.
   - Write in the ledger the problem, the units it touches, and the **preservation contract**:
     the facts that must not change, in `compare --keep` terms plus prose.
3. **Cold read** (whenever the concept or the cards change). `show-reader` lists the
   questions it would have to guess. The director answers them in the plan or the cards
   before any unit is designed.
4. **Design.**
   - Batches of at most 5 designers in parallel, and no two units in a batch touch the same
     file (alternate mixes when units are mixes).
   - Each designer writes three options for its unit, chooses one against its card and the
     usage record, writes it, builds its copy and returns a report of about 15 lines (what it
     chose, why, what it rejected, the options' one-line summaries) plus the changed files.
   - The director merges the files into the show and builds.
5. **Gates.** `build` with no `show-source` or `show-rules` finding. A designer's unit that
   breaks a gate goes back to that designer with the findings verbatim.
6. **Critique.**
   - Five critics in parallel, one per lens. For a new show or a rework of the night, the
     first pass covers the whole night. For a rework of some units, it covers those units,
     their neighbours, and the night-level facts the change can move (compared with
     `compare` against the starting show).
   - Later passes cover only the open findings and the changed units with their neighbours.
   - Each critic writes a report file and returns its findings (B4).
   - **Scope discipline.** A finding outside the request's scope that the run did not cause
     is not fixed in this run. It goes to "Para depois" as a proposal for the owner's backlog,
     with its evidence. The owner manages the backlog; the team does not grow its own
     request.
7. **Consolidation.**
   - The director routes every finding as **fix** (back to a designer, the finding verbatim,
     one change per finding), **decision** (a ruling in the ledger) or **later** (the ledger's
     "Para depois").
   - It commits the round.
8. **Selection.**
   - When a unit or the night has two or more acceptable versions, a `show-critic` compares
     them blind, in pairs, in both orders, against the story and the cards.
   - The director picks and records why.
9. **Delivery.**
   - `build --check`, `uv run scripts/check_repo.py` and `uv run pytest` green.
   - On a rework, `compare --keep` holds against the starting show.
   - The book is generated and published as a private Artifact when the tool is available,
     otherwise the HTML file's path.
   - The ledger is complete and the work committed on the branch.
   - A short report to the owner: what changed, the book, the open "later" items, and the
     owner tasks (presets to create, cues to add).
   - No push, PR or apply.

### B4. Critics: lenses, findings, routing

| lens | judges | reads |
|---|---|---|
| `monotonia` | repetition, static stretches, neighbours alike, predictable drops, and the chaos guard | variety, identity, the static runs' music |
| `drops` | immersion at the moments that must land: contrast, change, freshness, the main drop, builds into drops | drops, builds, peaks, hit checks, `zoom` of the top drops |
| `energia-da-musica` | the light following each track: shape, direction, lag, missed boundaries | follows, strips, section lines |
| `arco-do-set` | the night following the owner's energy and arc: headroom, staircase, steps, breathers | arc, brief, night summary |
| `briefing` | fidelity to the story, identity and cards, restraint, coherence of the palette and fixture roles | identity, the plan and cards, budgets, the book's sections in text |

- Each lens has a rubric file. It lists the questions to answer, the views that answer them,
  and what counts as grave in that lens.
- The critic is told to find where the night is weakest and most predictable, and never to
  approve by default.
- A **finding** has a lens, a severity (`grave`: a criterion fails at a top moment or across a
  track; `moderado`; `menor`), the unit, the evidence (a report or zoom line, with bars and
  clock), the problem, and a suggested direction (not a patch).
- Findings without evidence are dropped by the director, and the ledger says so.

### B5. Stopping and self-healing

- A unit gets **at most 3 design rounds**, and the night **at most 2 full critique passes**,
  re-reviews of open findings aside.
- **`menor` findings never enter the loop**: they go to "Para depois".
- **Self-healing:**
  - a grave finding goes back to the designer with the evidence;
  - **a grave finding that comes back in a unit's third round means the cause is upstream**,
    so the director revises the card or the concept once and redesigns that unit;
  - if it is still grave after that, the run stops on it. It goes in the ledger and in the
    report to the owner as an open problem, and never gets patched round after round.
- The run ends when no `grave` finding in scope is open (or each one is ruled) and the gates
  are green, or when the budget is spent. The director owns the stop.
- **The budget** is the round caps above, plus the owner's cap when the request sets one.
  When a run stops on a usage limit, the ledger's last state line is where the next session
  resumes (B3.0).
- Every version stays in git. The delivered version is the best one by selection (B3.8), not
  necessarily the last.

### B6. The guard

- `.claude/settings.json` registers a `PreToolUse` hook on Bash. Its script answers
  `permissionDecision: "ask"`, with a reason in pt-BR, for any `nextrack_lights.py` command
  carrying `--apply`, the commands that write SoundSwitch.
- Everything else passes untouched, and so do dry runs.
- Writing SoundSwitch then waits for the owner's click even in auto mode, by enforcement, not
  by instruction.
- The script has a test with sample hook inputs.

### B7. The `lightshow` skill

- A track that belongs to a show is changed through the show (as today).
- A show with a `ledger.md` is the team's. For it there is no per-track approval: the
  `show-team` run replaces steps 4-5.
- The apply rules (step 6) are unchanged.
- The skill points to `show-team` for whole-night work.

### B8. The rehearsal, the first task, and the acceptance of 2b

**The rehearsal (in the 2b PR).** Before the PR, the builder runs the whole rite once on a
small case in scratch: two or three Hï Ibiza tracks copied to a variant folder, with a short
request. The new project agents cannot be dispatched in the session that writes them, so
general-purpose subagents are given each agent file's prompt and tools. The rehearsal proves
the templates, the run folder, the ledger with its state lines, the routing, a resume from
the ledger, and the book. Nothing from it is committed except fixes to the skill. 2b is done
when the rehearsal passes and the PR is merged.

**The first task (after the merge).** The owner starts a fresh session and asks for it in
one sentence; the skill takes it from there. The request: *"Hï Ibiza: pontes de até 16
compassos, sem perder a história."* Those are 23 `bridges` advice findings in 13 mixes. In
several of them the music mixes for much longer than 16 bars (40 from The Rapture into The
Akan). The rework sets `bridge.bars: 16`. The echo (A11) carries the rest of each long mix,
and the incoming track needs a new chapter there, not a cut. It is a rework of units (the 13
mixes), so the scope discipline of B3.6 applies.

Acceptance of that run:

- the `bridges` advice reads 0;
- `compare <main's show> hi-ibiza-pulso --keep arrivals,moments` exits 0. The first argument
  is the main branch's show folder, copied into the run folder (`git archive origin/main
  lightshows/shows/hi-ibiza-pulso`);
- the `signatures` advice does not get worse;
- gates, `check_repo.py` and `pytest` are green;
- no `grave` finding in scope is open without a ruling, and the findings outside it are in
  "Para depois";
- the run respects the round limits;
- the ledger is written and the book delivered.

The owner's verdict in the room comes after, as project 3's first feedback.

### B9. Measuring the team

The skill's `README` (or a section of `SKILL.md`) documents the protocol project 3 will run:

- cases drawn from real requests and the owner's room feedback;
- each case run with and without the skill (at least 3 runs each when cost allows);
- graders in order: the computed checks, a model judge, the owner, who has the last word;
- pass rate, tokens and minutes recorded per run.

2b ships the protocol and the first case (B8), not the harness.

---

## Decisions

These are the designer's calls under the owner's direction ("siga principalmente as melhores
práticas dos benchmarks"). Each says why, and what it costs if wrong.

1. **Two deliveries, the senses first.** The critics need a signal from outside the model, and
   today's measures misreport three criteria (verified). *If wrong:* 2b waits one PR longer;
   nothing in 2a is wasted, because the book needs it.
2. **Facts from tools, judgment from agents, verdict from the owner.** LLM judges of creative
   work do not track experts. *If wrong:* a check can still be promoted from advice to rule.
3. **Precompute the music, compute comparisons on demand.** The audio is outside the repo and
   CI, every agent must see the same numbers, and multi-agent runs cost about 15× a chat.
   *Cost:* a map upgrade per new analysis, done as code with tests.
4. **The upgrade never re-runs the separation**, so no v1 field (and no anchor of Hï Ibiza)
   can move. *If wrong:* a full re-analysis is still available.
5. **The set's target comes from the owner's labels**, not loudness, because auto-gain and the
   DJ level the room. *If wrong:* the label check already surfaces disagreements.
6. **New measures replace the 1.1 indices.** One measure per thing, and the old ones are
   proven blind. *Cost:* report outputs and some tests change.
7. **New checks are rules used as advice.** A goal that does not hold yet never turns CI red.
   *If wrong:* a show can move any of them to `rules:`.
8. **Identity is declared in `show.yml`.** A repetition is a signature when declared and
   monotony otherwise; the book shows promised against delivered.
9. **The book is generated, not written.** Prose comes from the show and the ledger, numbers
   from the views, so it cannot dress up the result. Labels are pt-BR because it is the
   owner's reading. *Cost:* layout changes are code changes.
10. **The director decides, the critics judge.** Self-preference is measured in the
    literature. The owner's "critic who sees the whole" is the director. Its overrules are
    visible in the ledger and the book.
11. **A small team in a fixed order, at most 5 in parallel, units with disjoint files per
    batch.** Parallel writers conflict and repeat each other, and free-form group chat
    underperforms.
12. **Three options before choosing**, for concepts and units, to counter homogenization.
    *Cost:* more tokens per unit; the reports stay short.
13. **Few rounds, every version kept, blind selection.** Two or three rounds capture most of
    the gain; the best version is often not the last.
14. **A grave finding on a unit's third round goes upstream once, then stops.** That avoids
    churn (BMAD's rule, MAST's failure modes).
15. **The ledger is committed; bulky artifacts are not.** The ledger survives compaction and
    reaches the book; critic reports and variants stay in scratch. *If wrong:* the run folder
    can be archived later.
16. **The cards live in the light plan.** The design persists between runs in the prose
    document the owner already reads.
17. **The guard is a hook that asks.** Autonomy covers the show, not SoundSwitch; enforcement
    beats instruction.
18. **The team stops at a branch.** Push, PR and merge stay the owner's go, as for every
    session in this repo.
19. **The research notes are committed** with the design. Project 1's notes were lost.
20. **The echo copies the incoming light onto the outgoing tail** (from the builder check).
    Short bridges with long mixes would otherwise leave the outgoing script on the autoscript
    while P1 is open, breaking the plan's no-cut rule. Copying keeps the rule whatever P1
    finds. *Cost:* a compiler feature in 2a. *If wrong* (P1 shows the switch follows the
    fader inside the window): the echo is harmless and could be made optional.
21. **Scope discipline in reworks** (from the builder check). A finding outside the request
    goes to the owner's backlog as a proposal, never into the run. Otherwise the first rework
    would grow into a redesign of the night and break "sem perder a história".
22. **The first real run comes after the merge, in a fresh session** (from the builder
    check). A session sees a new `.claude/agents/` folder only after a restart (Claude Code
    watches existing folders, not ones created mid-session), and a new worktree branches from
    `origin/main`, which has the skill only after the merge. The 2b PR carries a rehearsal
    with general-purpose stand-ins instead.
23. **The budget is the round caps, plus an optional cap from the owner, and runs resume from
    the ledger** (from the builder check). A run that hits a usage limit loses nothing.

## Left to the builder

- The exact formulas, weights, digit steps and thresholds of A1-A6, within the stated
  acceptance and with every formula in a docstring.
- The layout of the new report sections, and the names of the map-upgrade command and its
  flags.
- The book's visual design within A9's sections and contract.
- The wording of the skill, the lens rubrics, the templates and the agent files, and the
  models of the non-critic agents.
- How the rule API receives the views' data.
