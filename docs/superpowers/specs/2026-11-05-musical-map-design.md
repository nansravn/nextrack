# Musical map — design

Date: 2026-11-05. Branch `feat/musical-map`. Builds on
[the choreography design](2026-10-31-soundswitch-choreography-design.md) and
[the continuous haze design](2026-11-04-continuous-haze-design.md).

## Why

The owner is preparing a new party: one 44-minute set of 15 tracks, afro house into tech
house, 120 to 132 BPM, inspired by Hï Ibiza, with a light show directed by Claude. The
night must read as one show, not 15. The owner built it in rekordbox as the playlist
`1-hi-ibiza-lightshow` and marked every transition with two hot cues per track: **B** is
where a track enters, laid on the previous track's **G**, where the owner starts to
beatmatch the next one. "O show deste set vai ser à partir destas transições."

In the brainstorm the owner asked for a light designer's way of working: several
**lenses**, each reading one aspect of the music and proposing light, and a **director**
that merges them under a budget. Every lens needs facts about the music that nothing in
the repo has today. The only per-track data is SoundSwitch's script (`dump`, `analyze`:
what the *lights* do) and its 8-bar phrases, which miss a third of the first drops by
3-7 bars ([autoscript analysis](../../soundswitch/autoscript-analysis.md)). In this
session the facts came from throwaway scripts: per-bar bass and loudness from the audio,
cues read from a copy of rekordbox's database, a stem separation spike.

The **musical map** makes those facts a tool and a file: for each track, what the music
does bar by bar and step by step, in the very bar numbers a choreography uses; and for a
playlist, how the tracks hand over to each other. It is project A of three the owner
ordered: A. the musical map (this), C. this set's light plan and 15 choreographies,
drafted with today's vocabulary, B. new compiler vocabulary, only for what the plan needs.

### The lenses and what each needs from the map

| lens (from the brainstorm) | what the room does | what it needs from the map |
|---|---|---|
| 1. Voice → movers | a beam "sings" with the voice; side changes per phrase; high notes up | vocal level per step, vocal phrases, vocal register |
| 2. Instruments → Vorlanes | the pixel map shows the arrangement building: a band of rows per instrument | level per instrument per step; when each enters and leaves |
| 3. Heartbeat → Hue and Vorlanes | flash on the hit, decay to nothing, again on the next | kick and percussion onsets and their strength |
| 4. Autoscript as a base | recolour or echo what it does well | nothing new: `dump` already reads it |
| 5. Darkness agent (≤ 5 a night) | one bar of total dark, or dark with a slow red heart, before a drop | breaks, builds, drops and how big each drop is |
| 6. Spiral (≤ 3 a night) | light walks round the room, faster and redder, closing on the drop | builds and the drop they end in |
| 7. Stereo becomes the room | what is panned left lights the left of the room | left/right balance per instrument |
| 8. Backlight in the mist | beams only, in vocal breaks | vocal phrases inside breaks |
| 9. The director | budgets, a ceiling that rises with the set clock, every arrival reads as a new song | the set timeline: transitions, overlaps, arrivals, set clock |

Lenses 4-9 are decided in project C; the map only has to carry the facts.

## Goals

1. One command makes the **musical map** of a track: a YAML file in the repo,
   `lightshows/maps/<artist-title-slug>.yml`, the same slug as the track's choreography.
2. The map counts bars exactly like a choreography: from the SoundSwitch script's tempo
   map (its first anchor is bar 1 beat 1). Its finest unit is the **step**, a 1/16 note,
   the finest rate the choreography vocabulary has.
3. The map separates the track into **five voices** (vocals, kick, percussion, bass,
   other) and, for each, records level per bar and per step, entries and exits, plus
   onsets for kick and percussion, register for the vocals and left/right balance for
   percussion and other.
4. The map labels every bar with a **section kind** (intro, groove, break, build, drop,
   outro) cut from the audio, lists **drops** with their size, and lists the vocal
   **phrases**.
5. The map carries the track's **rekordbox hot cues** (A-H) as `bar.beat` on the same
   grid, and a cheap command refreshes them without redoing the analysis.
6. One command prints the **set timeline** of a rekordbox playlist: every transition (G
   of the outgoing, B of the incoming), the overlap, the incoming track's **arrival** (its
   first drop after the outgoing track has gone), and the set clock at the tempos the
   owner plays.
7. `render` draws the map under the simulator's timeline, so the owner sees the music
   and the lights together.
8. `check_repo.py` validates map files, and the 15 tracks of `1-hi-ibiza-lightshow` are
   in the pools and have their maps committed in this branch.

## Non-goals

- New choreography vocabulary: envelope following, onset-driven pulses, colour bands,
  the spiral, recolouring or echoing the autoscript. That is project B.
- The light plan of the set, its budgets and the 15 choreographies. That is project C,
  which also decides which drops get darkness, spirals, white or strobe.
- Lyrics, words, hook recognition, chords, keys or genre detection.
- Writing anything to rekordbox, SoundSwitch or the audio library.
- Sharing stems, or listening to them in the simulator.
- Lifting `--accept-resize` or anything else about X1b (the owner tests it on Saturday,
  2026-11-07, at home).

## Anti-goals (a failure even if it works)

- A map whose bars do not line up with the choreography's bars, by any offset.
- A map that looks confident where it is not: a voice that is only bleed from another
  stem reading as present, or a grid that disagrees with the audio's beats hidden
  behind clean bar numbers.
- Default `uv sync`, CI or `pytest` downloading PyTorch, Demucs or rekordbox tooling.
- Audio, stems or machine paths in the repo.
- Opening rekordbox's live database for anything but a copy.

## The owner's decisions

| # | Decision | In their words / when |
|---|---|---|
| O1 | One set, one show: the night reads as one thing | "a noite tem que parecer uma coisa só, não 15 shows soltos"; "Não quero dividir em dois sets" |
| O2 | The show is built from the transitions they marked (B on the previous track's G) | "o mais importante é entender que o show deste set vai ser à partir destas transições" |
| O3 | Transitions are disguised; the drop of the new track must show it is a new song | "Você está certo com o que eu quero na transição. Quero que o drop realmente mostre que é uma música nova" |
| O4 | The lenses: voice, instruments, heartbeat, autoscript, darkness (3-5 per 30 min), spiral (2-3 per 30 min), and Claude's own | the brainstorm message listing (1)-(6) and asking for (7, 8, 9) |
| O5 | Order A (this map) → C (draft) → B (vocabulary) | "pode seguir nessa ordem, começa pelo mapa musical" |
| O6 | Spec flow for this development | "Lembre-se de especificar, se seguir o superpowers nestes desenvolvimentos" |
| O7 | Test in the simulator now; the real lights on Saturday; these 15 tracks are expendable | "quando eu voltar para casa no sábado finalmente quero testar o X1b e esse show de luzes lá … se as músicas corromperem, eu posso deletar o arquivo e recriar um novo autoscript" |

## Design

### 1. Inputs

- **SoundSwitch project** (`--project` or `NEXTRACK_SOUNDSWITCH_PROJECT`, as
  `nextrack_lights.py`): the track map gives the GUID, artist, title and the audio file's
  Windows path; the track's script gives the tempo map. The track is named the way
  `nextrack_lights.py` names it (GUID prefix or words).
- **Audio** (`--root` or `NEXTRACK_AUDIO_ROOT`, as `nextrack_tags.py`): the file is found
  under the root by the base name of the track map's path (Unicode-normalised and
  case-insensitive, as Windows treats names). Several hits: prefer the one whose folder
  name matches the path's folder; still ambiguous: refuse and list them. No path
  conversion, so no machine path in the code.
- **rekordbox** (`--rekordbox DIR` or `NEXTRACK_REKORDBOX_DIR`: the folder that holds
  `master.db`): read with `pyrekordbox` from a **copy** of `master.db`, `master.db-wal` and
  `master.db-shm` in a temporary folder, deleted afterwards. rekordbox may be running. A
  track is found by the file name of its path, compared like the audio. rekordbox not
  configured, or the track not in its collection: the map has no hot cues and says so.
  In the session, `djmdCue.Kind` 1, 2 and 8 held the owner's A, B and G; the full map is
  0 memory cue, 1 A, 2 B, 3 C, 5 D, 6 E, 7 F, 8 G, 9 H. Memory cues are ignored.
- **Pools**: the map's `track` is the pool's `Artist — Title`, found with the same
  matcher as choreographies (`same_track`). No pool match: refuse and say to add the track
  to its pool first.

### 2. Grid

Bars and beats come from the script's tempo anchors, through the same grid code the
compiler uses (`soundswitch_format`'s bar grid), so a map bar is a choreography bar.
Steps are 1/16 notes: 16 per bar. The map stores the grid it used: the choreography's
form (`{bpm, downbeat}` of the first anchor) plus **every tempo anchor** (`[ms, bpm]`),
so `cues`, `timeline` and `render` can turn milliseconds into bars from the map alone,
without the SoundSwitch project.

**Stale maps.** A map is stale when the audio file's hash, the script's GUID or its tempo
anchors differ from the ones stored (the owner may delete a script and let SoundSwitch
redo it). `analyze` redoes a stale map without `--force` and says so; `render` prints a
warning and does not draw a map whose GUID or anchors differ from the script it renders.

**Grid check.** The median offset between kick onsets and the nearest beat, in ms, is
stored. Above a quarter of a step it is a warning printed by `analyze` and `show` and
stored in the map (`grid_warning`), never silently absorbed.

### 3. Stems and voices

- Separation with Demucs `htdemucs` (four stems: vocals, drums, bass, other), on the GPU
  when there is one, else on the CPU. Session spike: a 3:01 track took 16 s on the
  owner's RTX 5080, model load included; the CPU is minutes per track.
- Stems go to a temporary folder and are deleted, unless `--keep-stems DIR`.
- The drums stem is split by frequency into **kick** (the low band) and **percussion**
  (the rest). So the map has five voices: `vocals`, `kick`, `perc`, `bass`, `other`.
- The separator sits behind a small interface (audio in, four stem arrays out) so tests
  feed synthetic stems and never load a model.

### 4. Features

All per voice unless said otherwise.

- **Level** per step and per bar: a digit `0`-`9`, from the voice's RMS in dB. `9` is the
  voice's own loud level (around its 95th percentile) and each digit below is about 3 dB
  quieter; `0` is silence. A voice that is only bleed (its loud level is far below the
  mix's) reads `0` all the way: an instrumental's vocal stem must not light the movers.
- **Entries and exits**: a voice enters at the first bar it reaches a clear level after at
  least two quiet bars, and exits at the last such bar before two quiet bars.
- **Onsets** for `kick` and `perc`: per step, `.` or a strength digit `1`-`9`, from the
  onset envelope of that band, quantised to the nearest step.
- **Register** for `vocals`: per step, `.` when no voice, else a digit `0`-`9` for the
  pitch within the track's own vocal range (`0` its lowest, `9` its highest).
- **Phrases** for `vocals`: from `bar.beat` to `bar.beat`, with level and register
  (`low`, `mid`, `high` by the phrase's median); gaps shorter than a beat do not split a
  phrase.
- **Balance** per bar for `perc` and `other`: `L`, `l`, `c`, `r` or `R`, from the
  left-right level difference (hard and soft sides, centre).
- **Sections** per bar, from the whole map. "Full" means bass and kick near the track's
  own loud level; tech house often filters the bass in a break instead of removing it, so
  a break is **well below full**, not necessarily silent.
  - `intro`: from bar 1 to the first full bar, when the track does not start full.
  - `groove`: full from bar 1, until the first break (a track that starts with its groove).
  - `break`: at least two bars well below full, after full bars.
  - `build`: the end of a break where energy rises bar over bar (more percussion, more
    high end, denser onsets), ending in a drop.
  - `drop`: from the bar the track turns full after the intro or after a break, until the
    next break. So the first entry of the bass after an intro is a drop.
  - `outro`: after the last full bar.
- **Drops**: bar and size (the dB jump of bass plus kick against the two bars before), so
  the director can tell the bass returning from a filter (TOO COOL bar 21) from the real
  drop (TOO COOL bar 49).
- **Silences**: bars where the whole mix is near silent.

### 5. The map file

`lightshows/maps/<artist-title-slug>.yml`. Keys in English, no prose needed; a comment
line on top says the file is generated by `nextrack_map.py`. Shape (values shortened):

```yaml
# Generated by scripts/nextrack_map.py analyze. Do not edit by hand.
map_version: 1
track: Rampa, Adam Port, &ME, chuala, Keinemusik — Say What   # the pool's Artist — Title
soundswitch: 0123ABCD-...-...                                 # script GUID
audio: {sha256: 3f9c1a2b4d5e, ms: 181245}                     # first 12 hex of the file's hash, length
grid: {bpm: 120, downbeat: "0:00.061", anchors: [[61, 120.0]], offset_ms: -5}
separator: htdemucs
bars: 97
hot_cues: {A: "1.1", B: "26.1", G: "79.1"}                    # or `hot_cues: null` with `hot_cues_note`
voices:
  vocals: {bars: "9999…", entries: [1, 45], exits: [33, 96]}
  kick:   {bars: "…", entries: […], exits: […]}
  perc:   {bars: "…", balance: "ccccl…"}
  bass:   {bars: "…"}
  other:  {bars: "…", balance: "…"}
steps:            # one string per 8 bars (128 characters), the last one shorter
  vocals: ["9988…", …]
  kick:   [...]
  perc:   [...]
  bass:   [...]
  other:  [...]
onsets:
  kick: ["9...9...9...9...", …]
  perc: [...]
register: ["..567765..", …]
phrases: [{from: "1.1", to: "8.4", register: mid, level: 8}, …]
sections: [{bars: [1, 38], kind: groove}, {bars: [39, 40], kind: break}, {bars: [41, 64], kind: drop}, …]
drops: [{bar: 41, db: 18.5}, {bar: 73, db: 15.2}]
silences: [[95, 97]]
```

`audio.sha256` lets a later run tell that the file was replaced by another download.

### 6. Commands: `scripts/nextrack_map.py`

- `analyze <track>` or `analyze --playlist NAME`: makes the map(s). An existing map is
  kept unless it is stale (section 2) or `--force` is given, so a playlist run only does
  what is missing or out of date. `--keep-stems DIR`, `--device cuda|cpu` (default: the
  GPU when there is one). Prints one line per track (written, redone because stale, kept
  or refused, and why) and any grid warning.
- `cues <track>` or `cues --playlist NAME`: rereads the hot cues from rekordbox and
  rewrites only `hot_cues` in existing maps (cheap: no audio).
- `show <track>`: the map as text for directing: per 64 bars a cue line (hot cues), one
  line per voice with the bar digits, the section letters, then drops and phrases. Reads
  only the map file.
- `timeline --playlist NAME [--block FILE] [--yaml]`: the set timeline.
  - The order comes from the rekordbox playlist, the cues live from rekordbox; the
    maps give the bars.
  - Per transition: the outgoing track's G (bar), the incoming track's B (bar), the
    **offset** between the two grids, the **overlap** (bars the outgoing still sounds
    after G, until its last non-silent bar), the incoming track's sections that fall in
    the overlap, the **arrival**: the incoming track's first drop at or after the
    outgoing track's last bar, as mapped onto the incoming grid, and its **peak**: the
    biggest drop of the incoming track before its own G (the same bar when they agree).
    No such drop: say so. Which of the two carries the "new song" gesture is project C's
    call.
  - Inputs: rekordbox and the maps only (the maps carry the grids); no SoundSwitch
    project and no audio.
  - The **set clock** at each G and arrival. Each track plays from B (bar 1 for the
    first) to G (its last non-silent bar for the last), at its played tempo. With
    `--block`, the played tempo is read from the block tracklist's BPM field (`122`, or a
    ramp `122-125`, taken as linear in bars); without it, the script's BPM. The owner
    gave the played tempos of this set in the brainstorm (120; 120-121; 122 for tracks
    3-9; 122-125; 126-128; 128; 129; 130; 132); they go into the set's block, which is
    project C's first content task, not this branch.
  - Warnings: a track missing B or G where the order needs it (the first needs no B, the
    last no G); a cue not on a beat; a map missing; a map whose stored hot cues differ
    from rekordbox's (cue moved since the map: refresh with `cues`).
  - Output: a Markdown table (default) or YAML.

`nextrack_lights.py render` loads `lightshows/maps/<slug>.yml` when it exists and passes
it to the page (see 7). Nothing else in `nextrack_lights.py` changes.

### 7. Simulator

`scripts/lightshow_sim.html` draws, under the existing timeline and on the same time
axis: five thin lanes (vocals, kick, percussion, bass, other) shaded by step level, the
section kinds as coloured bands with their names, drop markers, and the hot cues as
labelled ticks (`B`, `G`). Labels in pt-BR. With no map the page looks as today.

### 8. Validator rule `musical-map`

Every `lightshows/maps/*.yml` (but a README): parses; has exactly the keys above
(`hot_cues_note` only when `hot_cues` is null; `grid_warning` optional); `track` matches
a pool track; `soundswitch` is a GUID; `grid` as in a choreography plus `anchors` and
`offset_ms`; `bars` a positive integer; every per-bar string has `bars` characters and
every step list adds up to `bars × 16`, from the right alphabet; bar numbers and
`bar.beat` values inside `1..bars`; sections sorted, not overlapping, covering every bar,
kinds from the list; the file name is the slug of `track`. The rule follows the
checklist in `CLAUDE.md` (one function in `RULES`, tests for passing and failing cases,
README and rule-table row).

### 9. Dependencies

- Default dependencies gain only what the feature code and its tests need (NumPy and an
  audio reader such as `soundfile`); CI keeps running `uv sync --locked`, check_repo and
  pytest, and never downloads PyTorch.
- A dependency group `analysis` holds Demucs, PyTorch, and `pyrekordbox` with its
  SQLCipher wheels, in the repo's own environment (Python 3.14, `.python-version`). It is
  not a default group. `analyze`, `cues` and `timeline` check for it and, when it is
  missing, print the one command that installs it (`uv sync --group analysis`).
- Session spikes, both on the owner's RTX 5080 (Blackwell): Python 3.12 with
  `torch 2.7.1+cu128` and the Demucs command line (16 s for a 3:01 track, model load
  included); then Python 3.14 with `torch 2.15.0+cu132`, Demucs **through its Python API
  with our own audio I/O** (`soundfile` in, arrays out; 4 s for the separation), and
  `pyrekordbox 0.5.0` plus `sqlcipher3-wheels` importing. The code calls Demucs's API
  (`get_model`, `apply_model`), not its command line, so torchaudio's file I/O is never
  needed. The builder confirms that `uv lock` resolves the group for the platforms the
  lock covers and that CI's `uv sync --locked` stays green.
- `pyrekordbox` opened the owner's `master.db` copy with `unlock=True` and no key step
  (version 0.5.0). No key goes into the repo; if a later rekordbox needs one, the error
  says to run pyrekordbox's own key download.

## Data to change in the same branch

- Pool entries for the 12 tracks of the playlist not yet in a pool in the version played:
  11 new tracks and `Barbatuques — Baianá (Pablo Fierro Edit)`, in `tracks/afro-house.yml`
  (8) and `tracks/tech-house.yml` (4; `Too Cool To Be Careless` is there already), with
  `bpm` and `key` from rekordbox's analysis (key in Camelot), `energy` estimated and the
  pools' usual note that it was estimated, `status: downloaded`. The Jack Back Club Mix of
  Baianá stays as it is. The folders follow the move already done on the owner's drive
  (see the rename log).
- The 15 maps, made on the owner's machine with `analyze --playlist 1-hi-ibiza-lightshow`
  and committed.

## Documentation in the same change

- `lightshows/README.md`: a "Musical maps" section (what a map is, the file, the voices,
  the sections, how a choreography reads it), and the validator schema list.
- `scripts/README.md`: a `nextrack_map.py` section (commands, inputs, the `analysis`
  group, safety: read-only everywhere, the rekordbox copy) and the `musical-map` row in
  the rule table.
- `CLAUDE.md`: the commands table gains the map tool and the `analysis` group setup.
- `.claude/skills/lightshow/SKILL.md`: step 2 adds "read the map (`nextrack_map.py
  show`)"; sections are cut at the map's drops and breaks rather than guessed from
  `dump`; with a set, read `timeline` for the transitions.

## Testing

Write the tests first. No test loads a model, opens a real rekordbox database or reads
real audio: the separator and the rekordbox reader are injected.

- Grid: on a synthetic script with a known tempo map (one anchor, and two anchors), a
  synthetic kick on every beat lands on step 0, 4, 8, 12 of each bar; a kick track
  shifted by half a step raises `grid_warning`; bar numbers equal the compiler's.
- Levels: a stem silent in bars 1-8 and loud from 9 reads `0`s then high digits; the
  same stem 40 dB under the mix reads all `0`.
- Entries/exits, onsets (strength order kept), register (a rising tone reads rising
  digits), phrases (a sub-beat gap does not split; a one-bar gap does), balance (a stem
  panned hard left reads `L`).
- Sections and drops on a synthetic arrangement: intro (kick only), the bass enters (a
  drop), a 4-bar break with a rising noise build, a second drop; both drop bars and their
  sizes are found; a break of one bar is not a break; a break where the bass is filtered
  (12 dB down) rather than removed is a break; a track full from bar 1 starts with
  `groove`.
- Staleness: a map whose stored hash, GUID or anchors differ is redone by `analyze`
  without `--force`; an up-to-date one is kept.
- Audio lookup: one match, two matches resolved by folder, an ambiguous pair refused,
  Unicode NFC/NFD and case.
- Hot cues: a fake rekordbox row set maps Kind 1/2/8 to A/B/G and ms to `bar.beat`;
  memory cues are ignored; no rekordbox gives `hot_cues: null` with a note.
- `cues` rewrites only `hot_cues` (the rest of the file byte for byte).
- Timeline on three fake tracks: offsets, overlaps, arrivals and peaks, set clock with
  constant and ramped tempos from a block, the warnings (missing B or G, moved cue,
  missing map).
- `show` prints a known map as expected.
- `render` passes the map to the page when the file exists, and nothing when it does not.
- Validator: a good map passes; each schema violation in section 8 fails.

## Constraints

- Read-only on audio, rekordbox and the SoundSwitch project; the rekordbox database only
  through a copy.
- No machine paths in code, docs, maps or commits; folders come from options or
  environment variables.
- Audio and stems never enter the repo; tests make synthetic audio under `tmp_path` only.
- Code, keys, docs and commit messages in English; simulator labels in pt-BR.

## Left to the builder

- Thresholds and windows for levels, entries, onsets, register, balance and sections,
  as long as the tests above hold.
- The kick/percussion split frequency, the onset method and the pitch tracker.
- Calling Demucs through its Python API or its command line.
- The module layout (one script, or a small library beside it, as `lightshow.py` is to
  `nextrack_lights.py`).
- The exact `show` and timeline table layouts.

## My calls (for the owner to check)

1. **Maps are committed to the repo**, not kept in a cache. They are knowledge about the
   music (the repo's whole point), small (tens of kilobytes), and project B's compiler
   can then compile without the audio. Cost if wrong: noisy diffs on regeneration.
2. **Steps are 1/16 notes**, the finest rate the vocabulary has. Cost: nothing finer for
   project B without re-analysing.
3. **Demucs `htdemucs`** for the stems, GPU when there is one. Cost: a heavy optional
   install (several GB with CUDA).
4. **rekordbox read through `pyrekordbox` on a copy of `master.db`**, not through an
   XML export, so the owner does nothing after moving a cue. Cost: depends on a
   reverse-engineered database format that a rekordbox update could break; the XML
   export would be the fallback.
5. **Five voices** (drums split into kick and percussion), because the heartbeat lens
   needs the kick apart from the shakers. Cost: the split is by frequency, so a low tom
   can read as kick.
6. **Hot cues live in the map** (refreshable with `cues`), so the simulator shows B and G
   and the timeline can say when a cue moved since the map.
7. **The timeline takes its order from the rekordbox playlist** (what the owner actually
   plays), and played tempos from a block when given.
8. **Played tempo ramps are linear in bars** (`Move` 122 → 125, `TOO COOL` 126 → 128).
9. **A drop is the track turning full after its intro or a break**, filtered breaks
   included, each with its size; the timeline shows both the **arrival** (first drop once
   the old track is gone) and the **peak** (biggest drop before G). For TOO COOL that is
   bar 21 and bar 49. Cost if wrong: project C reads the wrong bar as "the new song".
10. **Maps carry every tempo anchor and are redone when stale** (new audio, new GUID or
    new grid), so a recreated autoscript cannot leave a map with shifted bars.
11. **The analysis stack lives in the repo's Python 3.14 environment** as the optional
    group `analysis`, with Demucs called through its Python API.
12. **The set's block (with the played tempos) is project C's first task**, so this
    branch's real timeline runs at the scripts' tempos; the block path is tested on
    synthetic data.
