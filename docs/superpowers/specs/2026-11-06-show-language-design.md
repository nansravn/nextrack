# Show language — design

Date: 2026-11-06. Branch `feat/show-language`. Builds on
[the choreography design](2026-10-31-soundswitch-choreography-design.md) and
[the musical map design](2026-11-05-musical-map-design.md).

## Why

Writing the 15 choreographies of the Hï Ibiza set
([plan](../../../lightshows/sets/hi-ibiza-pulso.md)) took a throwaway generator of about 600
lines plus a rule checker. The generator held named looks, bridges made automatically (the
incoming track's B → arrival section copies the outgoing track's G → end look), a beam-aim
grammar and a spiral macro. The checker counted the night's budgets and refused a repeated
arrival draw. The repo's `lightshows/tracks/*.yml` are that generator's low-level output. Nothing
in the repo knows that the 15 files are one show.

The owner wants the next layer up to be a **show language**. Its users are not people: they
are **a team of AI agents** with autonomy over the whole loop. The team comes up with the
set's theme, designs the arc of the night, creates custom effects for the set, judges the
limits of the flashy ones, critiques its own result and iterates. The human tests the lights
in the room at the end and manages a backlog: feedback, good or bad, becomes a request the
team picks up. The owner put it this way: "O humano é um gestor do backlog, todo o resto é
resolvido pela IA."

That is three projects, in this order: (1) **the language** (this design), (2) the agent team
and its create → critique → iterate loop, (3) the backlog and the feedback memory. The language
is first because the other two stand on it. The owner approved the split and the order and
delegated every remaining design decision for this one. The decisions below are the
designer's calls, listed with their reasons in [Decisions](#decisions).

### What the agents need from the language

The two research notes behind this design (a benchmark of about 30 lighting and timing products,
and a survey of intermediate languages for agents: SWE-agent's ACI, CodeAct, Code as Policies,
Voyager, Grammar Prompting, SceneCraft) agree on a pattern. Agents write a small
**declarative text**, a **deterministic compiler** turns it into the artifact, and a
**verifier in the loop** fails with an error the agent can act on alone. On top of that come a
**library of reusable skills** written as code, and **progressive disclosure**: an index first,
details on demand. For this repo, that means:

| the agents must | so the language gives them |
|---|---|
| write a whole night, not 15 unrelated files | one **show** per set: palette, looks, rules and one cue list per track, in set order |
| not count bars | **anchors** on the musical map (`drop.2`, `G`, `break.1.end`) that the compiler resolves |
| reuse what works | **named looks** and **gestures** (time-structured macros such as the spiral) |
| invent effects that do not exist yet | a **gesture library in Python**: a new effect is a new function with a test |
| judge the flashy effects | **show rules** checked by the tool: budgets, where an effect may appear, what never repeats |
| read the result without lights | a **report** of the night: every section, what produced it, the music under it, the budget tally |
| fix their own mistakes | findings that say file, line, value and what would fix it |
| trust one source | the generated choreographies are committed but **never edited by hand**: a validator rule fails when they drift from the show |

## Goals

1. A **show** is a folder `lightshows/shows/<show-id>/`: one `show.yml` (the night) and one
   file per track (its cue list). It is YAML and nothing else. The show-id is the light plan's
   file stem when the show has a plan (`hi-ibiza-pulso`).
2. A **compiler** (`scripts/show_language.py`, a pure library) turns a show, the musical maps
   and the set's track order into one **choreography** per track, in today's format
   (`lightshows/tracks/<slug>.yml`, the low-level layer). `lightshow.py`, `nextrack_lights.py`,
   `compile` and `apply` are untouched: the language sits on top of them.
3. Time is **anchored on the musical map**: hot cues, the n-th section of a kind, the last bar,
   plus or minus bars. A cue lasts until the next one, like a cue stack.
4. **Bridges and handovers** are part of the language. A track's `handover` look plays from its
   G to its end; the next track opens with a **bridge** from its B, a copy of that look.
5. **Looks** are named sets of layers. They can extend each other and be overridden per cue.
   Colours are **palette names**.
6. **Gestures** are Python functions in a registry (`scripts/show_gestures.py`). A cue
   invokes one by name with parameters. v1 ships `sequence` and `spiral`.
7. **Show rules** are Python functions in a registry (`scripts/show_rules.py`), chosen and
   parameterised in `show.yml`. v1 ships `budget`, `total-dark`, `arrivals`, `movers-aim`,
   `matrix-not-cloned` and `exclusive`.
8. A CLI, `scripts/nextrack_show.py`, offers `build` (compile and write; `--check`, `--out`,
   `--adopt`), `report` (the night for a critic) and `vocab` (anchors, gestures, rules and the
   show's palette and looks, for an agent that has not read the docs).
9. `check_repo.py` gets three rules: `show-source` (the show compiles), `show-rules` (the
   show passes its own rules) and `show-compiled` (the committed choreographies are exactly
   what the show compiles to).
10. The Hï Ibiza set is **ported**: `lightshows/shows/hi-ibiza-pulso/` compiles to the same 15
    choreographies as today (same content once parsed), passes the plan's rules, and the 15
    files become generated.
11. Docs for agents: the schema in `lightshows/shows/README.md`, the CLI in
    `scripts/README.md`, change checklists in `CLAUDE.md` (add a gesture, add a show rule),
    and a pointer in the `lightshow` skill.

## Non-goals

- New low-level vocabulary: a spiral that walks the room, a heartbeat with decay, beams that
  follow the voice, the Vorlanes as an equalizer, stereo mapped onto the room. That is project
  B: it changes `lightshow.py`. Gestures can only emit today's vocabulary until then.
- The agent team (roles, the loop, prompts, skills for each role) and the backlog: projects 2
  and 3.
- Changing `nextrack_lights.py`, the choreography schema, `compile`, `apply` or their safety
  model. The owner's go is still needed to write SoundSwitch (the `lightshow` skill's rule
  stands).
- A whole-night simulator, a set clock in the report, JSON output, music-aware rules such as
  "the centre is dark in breaks": candidates for later.
- Porting the Halloween set. Its one choreography (Happier) stays hand-written; a show is
  optional per set.

## Anti-goals

- **A custom parser.** The source is YAML. The only grammar of our own is the anchor, small
  enough for one regular expression.
- **Hand edits mixed with generation.** A generated choreography is owned by its show; a hand
  edit is a validator finding, not a fork.
- **Silent magic.** Everything the compiler infers (bridges, default ends, resolved anchors)
  shows up in the report.
- **A rule that passes when it cannot check.** A rule whose input is missing reports it.
- **Writing outside the repo.** No command writes SoundSwitch, rekordbox or audio.

## The show

### Folder

```
lightshows/shows/hi-ibiza-pulso/
  show.yml                                   # the night
  me-black-coffee-the-rapture-pt-iii.yml     # one cue list per track, named like its map
  caiiro-the-akan.yml
  ...
```

A track file is named `<slug>.yml`, where `slug` is `musical_map.slug` of the track's
`Artist — Title`: the same stem as its map and its choreography. With one file per track,
several agents can work on different tracks at once, and an agent working on one track reads
only `show.yml`, its own file and its neighbours' handovers.

### `show.yml`

```yaml
show_version: 1
set: sets/hi-ibiza-pulso.md                # repo-relative; the track order comes from it
plan: lightshows/sets/hi-ibiza-pulso.md    # optional: the prose light plan
story: >-                                  # pt-BR: the idea of the night, a few lines
  A noite é um corpo: o azul é o espaço, o vermelho é o coração...
palette:                                   # name → #RRGGBB
  azul-profundo: "#0A2CFF"
  azul-gelo: "#3A6BFF"
  carmim: "#B0001E"
looks:                                     # name → layers (see Layers)
  respiracao-azul:
    movers: {move: sweep, every: 2bar, positions: [Dance Floor Centre, Crossed Over], colour: azul-gelo, level: 0.7}
    matrix: {draw: rows-up, rate: 1bar, colour: azul-profundo, mirror: true}
    hue: {state: pulse, colour: carmim}
  breu: {movers: off, matrix: off, hue: dark}
  breu-inicial: {extends: breu}
gesture_defaults:                          # gesture → parameters merged under every call
  spiral:
    rates: ["1/2", "1/4", "1/8", "1/16"]
    colours: [azul-profundo, violeta, violeta, vermelho]
    aims: [[Crossed Over, Up, Dance Floor Centre], [Crossed Over, Up, Dance Floor Centre], Dance Floor Centre, Dance Floor Centre]
bridge:                                    # optional: without it, no bridges are made
  name: ponte
  intent: "Ponte: a mesma luz da música anterior, copiada camada por camada, até a chegada."
handover:                                  # required when a track has a handover
  name: entrega
  intent: "Entrega: do G até o fim, o look que a próxima música copia na ponte."
rules:                                     # rule id → parameters (or true)
  budget:
    breu: {max: 5}
    spiral: {max: 3}
    strobe: {max: 5, moments: [virada, pick-up, cant-decide, dirty-cash, final], from: "PAWSA — Too Cool To Be Careless"}
  total-dark: {only: [breu, breu-inicial]}
  arrivals: {draw_differs: true}
  movers-aim: true
  matrix-not-cloned: {except_moments: [virada, final]}
  exclusive: {keys: [spiral, breu], except_tracks: ["PAWSA — Too Cool To Be Careless"]}
```

Keys: `show_version` (1), `set`, `story` and `palette` are required; `plan`, `looks`,
`gesture_defaults`, `bridge`, `handover` and `rules` are optional. Names of palette entries,
looks, moments and cues are kebab-case ids (lowercase letters and digits joined by single
`-`, as everywhere in the repo); the owner's shows use pt-BR words for them, like today's
section names. Prose (`story`, `intent`, `budget`) is pt-BR.

**Track order.** The tracks of the show are the tracks of the set: each block that the set's
program links (`check_repo.set_block_ids`), in order, and in each block the lines of its
`## Tracklist` (`check_repo.tracklist_entries`). Each set track needs a track file whose
`track` names the same track (`check_repo.same_track`); a track file whose track is not in the
set is a finding. A track that appears twice in the set is a finding (v1: a track has one
choreography).

### A track file

```yaml
track: PAWSA — Too Cool To Be Careless     # the pool's Artist — Title, as in its map
story: >-                                  # pt-BR → the choreography's story
  TOO COOL é a virada da noite...
budget: >-                                 # optional pt-BR prose → the choreography's budget
  A virada gasta o que o plano guardou para ela...
cues:
  - at: 16
    name: filtro
    intent: "O grave some no filtro: filas violetas subindo devagar, um feixe para cima."
    look:
      movers: {move: hold, position: Up, colour: violeta, level: 0.4}
      matrix: {draw: rows-up, rate: 1bar, colour: violeta, mirror: true}
      hue: dark
  - at: drop.1
    name: too-cool
    role: arrival
    look: respiracao-azul
    with: {hue: {state: pulse, colour: vermelho}}
  - at: 41
    name: espiral
    intent: "Espiral da virada: os lados revezam cada vez mais rápido."
    gesture: spiral
    with: {bars: [2, 2, 2, 1]}
  - at: drop.2 - 1
    name: breu
    look: breu
  - at: drop.2
    name: virada
    moment: virada
    accents: [white, strobe]
    look:
      movers: {move: blink, every: "1/4", colour: vermelho, position: Crossed Over}
      matrix: {draw: solid, rate: "1/8", colour: vermelho}
      hue: {state: pulse, colour: vermelho}
handover:
  look: pulso-vermelho
  until: 116
```

Keys: `track`, `story` and `cues` (a list, possibly empty) are required; `budget`, `handover`
and `bridge` (only `false`: no bridge into this track) are optional.

**A cue** is a mapping:

| key | value |
|---|---|
| `at` | required: an [anchor](#anchors), the cue's first bar |
| `until` | optional: an anchor, the first bar **after** the cue (exclusive), leaving a gap that stays on the autoscript |
| `name` | required: kebab-case, becomes the section name (gestures derive their sections' names from it); names may repeat in a track (`drop`, `corte`) |
| `intent` | optional pt-BR prose |
| `look` | a look name or a mapping of layers; exactly one of `look` and `gesture` |
| `gesture` | a gesture name |
| `with` | optional: with `look`, layer overrides (see [Looks](#looks)); with `gesture`, its parameters |
| `role` | optional: `arrival` (the drop that shows the new track) |
| `moment` | optional: a kebab-case moment name, as the light plan names its moments; the budget rule reads it |
| `accents` | optional list of `white` (one beat of the white strip on the cue's first beat), `strobe` (a strobe hit there), `strobe-roll` (a strobe roll over the cue's first section) |

A cue runs from `at` to the bar before the next cue's `at`, or to `until - 1` when it has
`until`. After the last cue, it runs to the bar before the handover's `at`, or, with no
handover, to the map's last bar. `at` must increase strictly from cue to cue. `until` must be
after `at` and no later than the next start. Every cue covers at least one bar.

**The handover** is a mapping with `look` (and `with`), plus optional `at` (an anchor,
default `G`), `until` (default: after the map's last bar), `name` and `intent` (default: the
show's `handover`), `moment` and `accents`. Accents stay on this track; the bridge copies
only the look.

**The bridge.** When the show has `bridge`, the track is not the first, the track before it
has a handover, the map has a hot cue `B` and the track file does not say `bridge: false`,
the compiler adds a section from `B` to the bar before the first cue (or before the handover,
or to the map's end) with the show's bridge `name` and `intent` and exactly the layers of the
previous track's handover look, after merging and palette resolution, without its accents.
A first cue at or before `B` is a finding then: there is no room for the bridge. When the
previous track hands over but this map has no `B`, that is a finding too; the message says
to add the cue in rekordbox and run `nextrack_map.py cues`, or to write `bridge: false`.

A track whose map has a `G`, followed by a track that would take a bridge, needs a handover.
Without one it is a finding.

### Anchors

```
anchor := term [ ("+" | "-") n ]
term   := n                  an absolute bar (from 1)
        | A … H              the bar of that hot cue in the map (`hot_cues`)
        | <kind>.<i>         the first bar of the i-th section of that kind (from 1)
        | <kind>.<i>.end     its last bar
        | end                the map's last bar
kind   := intro | groove | break | build | drop | outro
```

An anchor is a YAML integer (`16`) or a string (`drop.2 - 1`, spaces optional around the
sign). `drop.i` is the i-th section of kind `drop`. That is the same bar as the i-th entry of
the map's `drops`, whose `db` the report shows. A hot cue that is not on a bar's first beat
(`9.3`, `1.1-2000ms`) cannot be an anchor: finding. Every resolution failure names what the
map has, such as `drop.4: the map has 3 drops (25, 49, 97)` or `G: the map has no hot cue G
(it has A, B)`. A resolved bar outside `1 … bars` is a finding, except for an `until`, which
may also be `bars + 1` (`end + 1`: the cue runs to the last bar).

`faster_from` in a movers layer also takes an anchor. Every other bar in a layer stays as the
choreography writes it (the raw `white.accent`, `strobe.hit`, `strobe.roll`, in absolute bars):
an escape hatch. The rules still see them, because they read the compiled sections.

### Layers

A layer value is exactly today's choreography vocabulary
([lightshows/README.md](../../../lightshows/README.md#layers)): `movers`, `matrix`, `white`,
`uv`, `strobe`, `hue`, as `auto`, `off` or a mapping. There are three differences:

- a `colour` (movers, matrix, hue) may be a palette name; `#RRGGBB` is still accepted;
- `faster_from` may be an anchor;
- a key set to `null` in a `with` override removes it (`with: {movers: {positions: null,
  position: Up}}`).

The compiler validates its output with `lightshow.problems_choreography`. A problem there
(an unknown draw, a bad rate) is a `show-source` finding at the cue that produced it, so an
agent never needs to read the generated file to find the error.

### Looks

A look is a mapping of layers, with an optional `extends: <look>`. Merging is per layer. When
both the base value and the override are mappings, their keys merge (the override wins, a
`null` removes a key). Otherwise the override replaces the base value. A cue's `look: name`
plus `with:` is the same merge, applied on top. An unknown look, a cycle of `extends` or a
layer name outside the vocabulary is a finding. A look name that is not used anywhere is fine.

### Gestures

A gesture is a Python function registered in `scripts/show_gestures.py`:

```python
@gesture("spiral", params=SpiralParams, example={"bars": [2, 2, 2, 1]})
def spiral(ctx: GestureContext, params: dict) -> list[GestureSection]:
    """v1 spiral: the two sides take turns, faster step by step, with the centre dark.

    One section per step: movers `pingpong` every <rate> in <colour> aimed at <aim>,
    matrix `columns` at <rate> in <colour> with `pingpong`, hue `dark`. Names are
    `<cue name>-<rate>` with the slash as a dash (`espiral-1-16`)."""
```

- The function is **pure**: it gets the span it must fill (`ctx.start`, `ctx.end`), the cue
  (name, intent), the map, the palette and the looks, and returns sections (`bars`, `name`,
  `intent`, `layers`, and optionally `look`: the look name a section came from, for the
  provenance) that cover exactly its span, in order, without gaps. Colours may be palette
  names; the compiler resolves them afterwards.
- It **validates its parameters** and returns readable problems (one string each), which the
  compiler reports as `show-source` findings at the cue. A gesture never raises on bad input.
- `gesture_defaults` in `show.yml` are merged under the cue's `with` (the cue wins), so a
  show sets its own spiral colours once.
- Its docstring and `example` are what `vocab` prints. A test runs every registered
  gesture's `example` against a synthetic map and asserts it covers its span and compiles
  to a valid choreography. A new gesture without a docstring or an example fails that test.

v1 gestures:

- **`sequence`**: `steps`, a list of `{bars, look, with?, name?}`. One section per step,
  consecutive. Bars must add up to the span. A step's name defaults to `<cue name>-<i>`,
  counted from 1. It is the general way to compose an effect in time from looks, with no new
  code.
- **`spiral`**: the v1 spiral of the Hï Ibiza plan (the relay that speeds up). Parameters:
  `bars`, `rates`, `colours` and `aims`, four lists of the same length, one entry per step.
  An aim is a preset name (`position`) or a list of them (`positions`). Bars must add up to
  the span. Sections as in the docstring above.

### Show rules

A rule is a Python function registered in `scripts/show_rules.py`. It takes the compiled show
(every track's sections, each with its provenance) and its parameters from `show.yml`, and
returns findings that point at the cue's line in a track file, or at `show.yml`. A rule
validates its own parameters the same way. A rule id in `rules:` that is not registered is a
`show-source` finding. The `rules:` mapping chooses which rules run; a show with no `rules`
runs none.

Every compiled section carries its own **provenance record**, kept per section, not per cue:

- `kind`: `cue`, `bridge` or `handover`;
- `track`: the track whose choreography holds the section;
- `look`: the look name that produced this section. For a cue or a handover, that is the name in
  `look: <name>`. For a gesture, it is the name the gesture reports for that section (a
  `sequence` step with `look: <name>` reports it). It is empty for inline layers;
- `gesture`: the gesture name, for sections a gesture made;
- `role` and `moment`: those of the cue, given to every section it produced. `role: arrival`
  marks only the cue's first section;
- `path` and `line`: where a finding about this section points.

A **bridge** section takes the record of the handover it copies: that handover's `look`,
`moment`, `path` and `line`, in the outgoing track's file, with `kind: bridge` and `track` the
incoming track. A finding about a bridge therefore reaches the agent who owns the handover,
which is where the fix goes. A moment exception (such as `matrix-not-cloned`'s
`except_moments`) applies to the copy as it does to the original.

**Occurrences** are what the budget and `exclusive` count. They come from sections and cues,
never from bridges:

| key | an occurrence is |
|---|---|
| a look name | a cue, a handover or a gesture step whose `look` is that name (only the name used, not the looks it extends); a cue counts once even when its look spans several sections |
| a gesture name | a cue that invokes it |
| `white-accent` | one beat of a `white.accent` list in a compiled section |
| `white-flash` | a compiled section with `white: {flash: ...}` |
| `strobe` | one beat of `strobe.hit`, or one `strobe.roll` |
| `uv` | a compiled section with `uv: on` or `movers.move: uv` |

Bridges never count: they copy a look that was already counted where it was written.

v1 rules:

| rule | parameters | finding when |
|---|---|---|
| `budget` | key → `{max?, moments?, from?}` | a key has more than `max` occurrences (the message lists them all, track and bar); an occurrence whose cue has no `moment` in `moments`; an occurrence in a track before `from` in set order. An unknown key is a parameter problem. |
| `total-dark` | `{only: [names]}` | a compiled section with movers `off`, matrix `off`, hue `dark` and no lit white, strobe or uv has neither its `look` nor its `gesture` in `only` |
| `arrivals` | `{draw_differs?: bool}` | a track has no cue with `role: arrival`, or more than one; with `draw_differs`, two consecutive tracks' arrival sections have the same matrix draw |
| `movers-aim` | `true` | a compiled section's movers is a mapping without `position` or `positions` (the autoscript would pick a random preset every two bars) |
| `matrix-not-cloned` | `{except_moments?: [names]}` | a compiled section's matrix is a mapping with neither `mirror` nor `pingpong`, and its cue's moment is not excepted |
| `exclusive` | `{keys: [names], except_tracks?: [tracks]}` | a track has occurrences of more than one of `keys` |

## Compiling

`show_language.compile_show(show, track_files, maps, set_tracks)` is pure (no file I/O). It
returns the compiled show plus findings. For each track, in set order:

1. Resolve every anchor against the track's map.
2. Work out the spans of the cues, the bridge and the handover.
3. Expand looks (merge, `with`) and gestures (validated parameters, sections inside the span).
4. Add the accents to the first section of their cue.
5. Resolve palette names and the `faster_from` anchors.
6. Build the choreography: `track`, `soundswitch` and `grid` (`bpm`, `downbeat`) from the map,
   `story` and `budget` from the track file, `base: autoscript`, the sections. A track with no
   cues, bridge or handover gets `sections: []`.
7. Validate it with `lightshow.problems_choreography`.

Then the rules run over the compiled show. Source findings stop a track from compiling, and
the rules skip a show that has any.

**The emitted file** is deterministic text, one per track:

```yaml
# Generated by scripts/nextrack_show.py build from lightshows/shows/hi-ibiza-pulso/.
# Do not edit by hand: change the show and run the build again.
track: "PAWSA — Too Cool To Be Careless"
soundswitch: A70F52BF-5680-4CE3-B9FA-984EEEF608AE
grid: {bpm: 128, downbeat: "0:00.297"}
story: >-
  ...
base: autoscript
sections:
  - bars: [1, 15]
    name: ponte
    intent: "..."
    movers: {move: pingpong, every: "1/2", colour: "#6A1CFF", positions: [Dance Floor Centre, Crossed Over, Up]}
    ...
```

Layers come in the order `movers, matrix, white, uv, strobe, hue`, written in flow style.
Their keys come in a fixed canonical order (the vocabulary's key order), so the same show
always gives the same bytes. A string that YAML would read as something else (`off`, `on`,
`1/2`, `#…`, anything with `: `) is quoted. A test asserts that the emitted text parses back to
the compiled data. The first line is the **ownership header**. `build` refuses to overwrite a
choreography without it, or one owned by another show, unless `--adopt` is given (used once,
when a set is ported).

## The CLI: `scripts/nextrack_show.py`

```bash
uv run scripts/nextrack_show.py build lightshows/shows/hi-ibiza-pulso            # compile, run the rules, write lightshows/tracks/*.yml
uv run scripts/nextrack_show.py build hi-ibiza-pulso --check                     # write nothing; exit 1 if a file would change
uv run scripts/nextrack_show.py build <scratch>/variant --out <scratch>/out      # a variant show: write its choreographies elsewhere
uv run scripts/nextrack_show.py build hi-ibiza-pulso --adopt                     # first build of a ported set: take over hand-written files
uv run scripts/nextrack_show.py report hi-ibiza-pulso                            # the night, for a critic
uv run scripts/nextrack_show.py vocab [hi-ibiza-pulso]                           # anchors, gestures, rules (and the show's palette and looks)
```

A show is a folder path or the id of a folder under `lightshows/shows/`. `--repo PATH`
(default: this repo) is where the maps, sets, blocks and `lightshows/tracks/` are read and
written. Output lines are `path:line: rule-id: message`, like `check_repo.py`. Exit status is
`0` (no findings), `1` (findings) or `2` (usage).

- `build` with a `show-source` finding writes nothing. With only rule findings it writes the
  files, so an agent can render and critique a draft, and prints the findings with exit
  status 1. It prints one line per file written or unchanged.
- `--out DIR` writes the choreographies into `DIR` instead of `lightshows/tracks/`, with no
  ownership check. It is for variants: an agent can copy a show outside the repo, change it,
  build it into scratch and `render` the result, without touching the committed show.
- `nextrack_lights.py render <track> --choreo <file>` (unchanged) is how a generated
  choreography is seen in the simulator. It needs the SoundSwitch project; the language does
  not.

### `report`

Plain text, written to be read by an agent that critiques the show. For each track, in
order: the header (`n. Artist — Title · bars · B · G`) and one line per compiled section with:

- `bars` and `name`;
- the source: `look <name>`, `look (inline)`, `gesture <name>`, `bridge` or `handover`;
- movers, matrix, hue in a short form, with colours by palette name;
- accents, `role` and `moment`;
- **the music under it**: the map's section kinds the span overlaps, with their bars, and
  the drop's `db` when the section starts on a drop.

After the tracks:

- the budget tally (key, max, used, every occurrence as track and bar);
- the arrivals (track, bar, draw, colour);
- the findings.

The report also lists what the compiler decided on its own: each bridge's span and the
look it copies, and each default end (a cue that runs to the handover or to the map's end).
The exact layout is the builder's call. It must stay compact: about one line per section.

### `vocab`

The anchor grammar with the section kinds and a worked example. The layer vocabulary, read
from `lightshow`'s constants (moves, draws, rates, hue states). Every gesture: name, docstring,
parameters, example. Every rule: name, docstring, parameters. With a show, its palette and
its looks, each in one line. An agent that has just arrived can call `vocab` instead of
reading the docs.

## Validator rules

The loader of `check_repo.py` also reads `lightshows/shows/*/show.yml` and the track files
next to it, with the same YAML loader (line numbers, duplicate keys as `parse-error`).

| rule | finding when |
|---|---|
| `show-source` | the show does not compile: the schema of `show.yml` or a track file, the set path, the track files against the set's tracks, a missing map, an anchor, a span, a look, a palette name, a gesture or its parameters, an unknown rule id or bad rule parameters, a problem in the generated choreography |
| `show-rules` | the show's own rules fail (only for shows with no `show-source` finding) |
| `show-compiled` | a track's `lightshows/tracks/<slug>.yml` is missing or differs from what the show compiles to (the message says to run `nextrack_show.py build <id>`); a choreography whose ownership header names a show that does not exist, or one that does not compile that track; two shows that own the same track |

The existing `lightshow-track` rule keeps checking the generated files like any choreography.
None of these rules read node ids or edges, so none depends on `graph_ok`. The rule table in
`scripts/README.md` gets the three rows.

## The port of Hï Ibiza

`lightshows/shows/hi-ibiza-pulso/` is written from today's 15 choreographies and the plan:

- the palette and the five handover looks of the plan, plus `breu`, `breu-inicial` and
  `contraluz`, become looks; the spirals of Move, TOO COOL and Pick Up become `spiral` calls;
- every arrival of the plan's table gets `role: arrival`; the cues of the plan's moments get
  their `moment`; bridges and handovers come from the language;
- the rules are those of the plan's "Regras da noite" that v1 can check: `budget` (breu 5,
  spiral 3, contraluz 3, white-accent 5 in its five moments, white-flash 1 in `final`,
  strobe 5 in its moments from TOO COOL on, uv 0), `total-dark`, `arrivals` with
  `draw_differs`, `movers-aim`, `matrix-not-cloned` (except `virada` and `final`) and
  `exclusive` (spiral or breu, except TOO COOL).

Acceptance: `build --adopt` writes 15 files that, parsed, equal today's files key by key
(`track`, `soundswitch`, `grid`, `story`, `budget`, `base`, `sections` with every layer). The
comparison normalises the layer words the way `lightshow` does (an unquoted `off` parses as
`False`). The only difference is the header comment and the formatting. `show-rules` and `show-compiled` are
clean. A pre-check of today's files against these rules found no violation: every mover
section aims, the only matrix layers with neither `mirror` nor `pingpong` are `virada` and
`final-flash`, and the only total-dark sections are the five `breu` and `breu-inicial`. If the
port still finds one, the repo's rule applies ("a finding in the real repo means fixing the
data, not loosening the rule"). The show is fixed with the smallest change that satisfies the
plan, each change is listed in the PR description, and the parsed comparison lists exactly
those sections as differences.

## Docs

- `lightshows/shows/README.md`: the schema above, written for agents. The folder, `show.yml`,
  track files, cues, anchors, looks, gestures, rules, provenance, the build and the loop
  (edit the show → `build` → read the findings and the `report` → `render` a track → repeat).
- `lightshows/README.md`: a row for `shows/` in the table, and a note that a choreography with
  the generated header comes from a show and is never edited by hand.
- `scripts/README.md`: a `nextrack_show.py` section and the three rule rows.
- `CLAUDE.md`: the show tool in Commands; an invariant (generated choreographies are never
  edited by hand); two change checklists: **add a gesture** (one function in the registry
  with a docstring, parameter checks and an `example`, plus a test) and **add a show rule**
  (one function, tests for passing and failing, its row in `lightshows/shows/README.md`).
- `.claude/skills/lightshow/SKILL.md`: when the track belongs to a show, the agent edits the
  show's track file and runs `build`, never the generated choreography. The owner-approval
  and apply rules are unchanged.

## How the agent team will use it (project 2, for orientation)

A director writes `show.yml`: the story, palette, looks, rules. Track agents write one track
file each, in parallel, starting from the map (`nextrack_map.py show`) and from `vocab`. A
build gives findings in the agents' own terms; they fix and build again. A critic reads the
`report`, and the simulator when the project is at hand, and proposes changes. An effects
agent adds a gesture to the library with its test. Variants are built with `--out` and
compared. None of this is in this branch. The branch only makes sure each step has a tool
and an error message.

## Decisions

Every decision here is the designer's call under the owner's delegation. Each one says why,
and what it costs if it turns out wrong.

1. **YAML source, not a Python API.** Agents write YAML and JSON-like data reliably, and the
   repo already validates YAML with line-accurate findings. Studies of niche DSLs against
   Python are mixed, and the show is mostly data. Logic lives where code is needed, in
   gestures and rules (decision 2), as CodeAct and Code as Policies suggest. *If wrong:* the
   compiler core is a library, so a Python front end can build the same model later.
2. **Gestures and rules are Python registries.** "Custom effects" need loops, arithmetic and
   reading the map; a YAML template language would be a worse programming language. A
   registry with a docstring, parameter checks and an example that a test runs is a skill
   library (Voyager) with a guardrail. *If wrong:* `sequence` already gives a no-code path
   for compositions.
3. **A cue stack, not `[a, b]` ranges.** A cue starts at an anchor and lasts until the next
   one, so overlaps are impossible and gaps are explicit (`until`). That removes the
   off-by-one errors of inclusive ranges. *If wrong:* `until` already allows any range.
4. **Anchors are a small fixed grammar, parsed by one regular expression.** No
   expression language, no relative-to-cue arithmetic. *If wrong:* new terms can be added
   (vocal phrases, voice entries) without breaking files.
5. **Bridges and handovers are language features**, because the set's continuity is the
   heart of the show and the one thing no product models. Their pt-BR names and intents are
   data in `show.yml`, not strings in code.
6. **The generated choreographies are committed and owned.** The ownership header and the
   `show-compiled` rule make the show the only source; `render`, `compile` and `apply` keep
   reading the same files as today. *Cost:* every show change touches two files (the source
   and its output). That is acceptable, and it makes PR diffs show the effect.
7. **Track order comes from the set**, so it is never written twice.
8. **The rules are a fixed v1 list with parameters.** They are the plan's rules that
   today's data can check. Predicates written in YAML are out (anti-goal: a custom language).
   A new kind of rule is a new function (CLAUDE.md checklist).
9. **Accents sit on the cue** (`accents: [white, strobe]`, the cue's first beat), which is
   where all ten of the set's accents are. The raw layer forms stay available.
10. **Build writes despite rule findings**, so a draft can be rendered and critiqued. The
    validator still fails, so it is never merged that way.
11. **One committed show per track.** Variants live outside the repo and build with `--out`.
    *If wrong:* the ownership header can grow a variant name.
12. **The canonical emitter reformats the 15 files once.** Same content, new layout. The diff
    of the port commit is reviewed with a parsed comparison, not by eye.
13. **The `lightshow` skill keeps the owner-approval and apply rules.** Agent autonomy is
    project 2's design, and writing SoundSwitch stays the owner's call.
14. **Provenance is per section, and a bridge points at the handover it copies.** Raised by
    the builder check: with provenance per cue, a `sequence` step with `look: breu` would get
    past the budget and fail `total-dark`. Without the handover's moment, a bridge copy of a
    peak would fail `matrix-not-cloned`, and its finding would land in the wrong agent's file.
    *If wrong:* the record is one dataclass, and the rules read only its fields.
