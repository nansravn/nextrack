---
name: lightshow
description: Use when the user asks for a light show, a choreography ("coreografia", "roteiro de luz", "lightshow") or a SoundSwitch script for a NEXTRACK track or block, or wants to amend, preview, compile or apply one (lightshows/tracks/*.yml, nextrack_lights.py).
---

# Lightshow: direct a track's lights

The owner directs the lights the way they direct the music. Per track you read what
SoundSwitch's autoscript does, propose a story in pt-BR phrase by phrase, write the
choreography only after approval, preview it and compile a copy. **Writing into SoundSwitch
is the owner's call, never yours.** The whole night must be good, not one song: spend
little, and justify every spend against the show plan.

Read these before the first proposal:
[lightshows/README.md](../../../lightshows/README.md) (schemas, vocabulary, the 8×7 draws,
what the compiler does), the [`nextrack_lights.py` section](../../../scripts/README.md#nextrack_lightspy)
(commands, reading `dump`, safety model), [rig.yml](../../../lightshows/rig.yml), the example
[Happier](../../../lightshows/tracks/marshmello-x-bastille-happier.yml),
[autoscript-analysis.md](../../../docs/soundswitch/autoscript-analysis.md) (what you correct)
and [experiments.md](../../../docs/soundswitch/experiments.md) (what is still unknown).

Run commands from the repo root. The SoundSwitch project folder is `--project PATH` (on any
command) or `NEXTRACK_SOUNDSWITCH_PROJECT`; if neither is set, ask the owner; never hard-code
it. `<scratch>` is a folder outside the repo and the project (the session scratchpad, else
`/tmp/lightshow`). For a block, go track by track in tracklist order, carrying the tally.

Copy this checklist into your reply and keep it current:

```
- [ ] 1. Resolved: pool entry, block(s), set, show plan, full GUID, grid
- [ ] 2. Autoscript read: dump, analyze, render "before"
- [ ] 3. Context: block, show plan, budget tally, lyrics' themes
- [ ] 4. Proposal in pt-BR sent; owner approved it
- [ ] 5. YAML written; check_repo clean; render; compile to a copy; cues listed in pt-BR
- [ ] 6. Apply: only on the owner's explicit go (dry run, then --apply, SoundSwitch closed)
```

## 1. Resolve the track

- Pool entry: `grep -rn -A8 "<Title>" tracks/` (artist, genre, bpm, key, energy).
  The choreography's `track:` is `Artist — Title` as the pool writes it.
- Block(s): `grep -ln "<Title>" blocks/*.md`; set(s): `grep -ln "<block-id>" sets/*.md`;
  show plan: `lightshows/sets/<set-file-stem>.md`.
- Script: `uv run scripts/nextrack_lights.py tracks --match "<words>"` prints
  `guid8  BPM  length  Artist — Title`; the BPM is `grid.bpm`. In
  `uv run scripts/nextrack_lights.py dump <guid8> --yaml | head -9`, `guid:` is the full GUID
  for `soundswitch:` and phrase 1's `start_ms` is `grid.downbeat` (158 → `"0:00.158"`).
- **No row, or `no script file`: the track has no SoundSwitch script. Say so (the owner must
  analyse it in SoundSwitch first) and stop.** Several rows: ask which file the owner plays.
- `lightshows/tracks/<slug>.yml` exists already: read it; you are amending it.

## 2. Read the autoscript

- `uv run scripts/nextrack_lights.py dump <guid8>`: per 8-bar phrase and fixture, `src`
  (`own` block or following `main`), `lit` share, `pulses`, colours, positions, shapes.
  Vorlane cells fold into `<Vorlane> RGB` and `<Vorlane> W` rows. Many pulses on movers and
  RGB = a chase (a loud part); every row on `main` = calm. Note the positions it uses.
- `uv run scripts/nextrack_lights.py analyze <guid8>`: who overrides Main, white over colour
  (%), position changes per bar, and Main's (the Hue centre's) min-max per phrase: `0 %-100 %`
  pulses, a low max is calm, a max of `0 %` is a dark centre.
- `uv run scripts/nextrack_lights.py render <guid8> -o <scratch>/<slug>-before.html`.

## 3. Gather context and tally the budget

- The block file: its feel, the track's place and energy, the tracks before and after.
- The show plan: `budget` front matter (effect → blocks/peaks where it may appear), peaks
  and moments, this block's palette and fixture roles, the night's rules. The plan wins.
  No plan for the set: say so, offer to write one, and spend at most one white accent
  (no strobe, haze or UV) meanwhile.
- Choreographies already written: `grep -H "^track:" lightshows/tracks/*.yml`; for those of
  this set, read the `budget:` prose, `grep -nE "white:|strobe:|uv:|haze:"` and the main draw.
- Tally: effect · allowed in · already spent (track, bar) · this track. An effect the
  budget does not give this block or peak stays out; never repeat the main draw of the
  track before or after.
- Lyrics: look them up for themes only; never store them in the repo.

## Directing principles

- **Story:** every fixture has a role per section; keep `auto` where the autoscript is fine.
- **Subtract:** `off` and `hue: dark` are effects; the section after a drop starts with less.
- **Build into drops:** `hue: dark`, `matrix: {draw: fill-up, rate: 1bar}`, movers
  `pingpong` with `faster_from`/`faster_every` (an absolute bar).
- **Movers:** one lit, the other dark (`pingpong`); a verse `hold`s one position per
  section. Haze (only where budgeted) makes the beams read.
- **Vorlanes:** two 8×7 drawings, one draw per section, `mirror` or `pingpong` so NW and
  SW never clone.
- **White strip:** an accent, one beat on a budgeted drop (`white: {accent: ["81.1"]}`).
  Under a draw an unset `white` is off; with `matrix: auto`, write `white: off`.
- **UV:** only under `hue: dark` and `matrix: off` (colour hides it); a manual cue in v1.
- **Hue centre:** choose `dark`, `pulse` or `bright` on purpose; the autoscript rarely darkens it.
- **Colours** from the block's palette; **positions** from the track's `dump` (a preset
  the script lacks becomes a manual cue). Few effects per track.

## 4. Propose in pt-BR, then wait

The proposal, in Portuguese, has four parts:

1. **História**: 2-4 lines, the arc of the track in light.
2. **Orçamento**: the tally lines; what this track spends, the plan line that allows it,
   what stays saved for later.
3. **Seções**: one line per musical phrase, `c. a-b (m:ss-m:ss) · nome · intenção`, then
   only the layers that change (movings, Vorlanes, fita branca, lustre, haze/UV/strobe);
   unset is the autoscript. Bar n starts at downbeat + (n − 1) × 240 / bpm seconds.
4. **Dúvidas**: drop bar, positions, anything you guessed.

Cut sections where the music changes (bass in, drop, break), not on the autoscript's
8-bar lines: in a third of the tracks its first drop is 3-7 bars late. Write no YAML until
the owner approves; on amendments, send the revised proposal.

## 5. Write, check, preview, compile

1. Write `lightshows/tracks/<artist-title-slug>.yml` (ASCII kebab-case, as the example):
   `story`, `budget` and every `intent` in pt-BR; keys and values in English.
2. `uv run scripts/check_repo.py`; fix every finding in the YAML.
3. `uv run scripts/nextrack_lights.py render <guid8> --choreo lightshows/tracks/<slug>.yml -o <scratch>/<slug>.html`.
   Give the owner the path (on WSL also `wslpath -w <file>`); the page toggles before/after.
4. `uv run scripts/nextrack_lights.py compile lightshows/tracks/<slug>.yml -o <scratch>/<slug>.ssfile`
   (never inside the project folder).
5. Translate every `manual cue, bar N: …` line into Portuguese: bar, time, fixture, what to
   do by hand in SoundSwitch.

If compile refuses more than 8 tempo anchors, the track stays on the autoscript: tell the
owner and stop. If `grid` does not match `the script's first tempo anchor (X BPM at Y ms)`,
copy those values into `grid`, unless the owner plays another version of the track.

## 6. Apply: only on the owner's explicit go

Approving the choreography is not a go. Apply only when the owner says, in this session,
to write it into SoundSwitch. A go covers one track's choreography as it stands: ask again
for the next track, and again after any change to the YAML.

1. Ask the owner to close SoundSwitch.
2. Dry run: `uv run scripts/nextrack_lights.py apply lightshows/tracks/<slug>.yml`; show
   the fixtures touched, the cues and any flag it says the write needs.
3. `uv run scripts/nextrack_lights.py apply lightshows/tracks/<slug>.yml --apply`, plus only
   the flags below that the owner agreed to.
4. Report the `wrote`, `backup:` and `restore:` lines verbatim; the owner then plays the
   bars and adds the manual cues.

Two flags need the owner's explicit yes after you explain them:

- `--accept-resize`: the output's size differs from the project file (nearly always).
  SoundSwitch is not yet known to load a resized script (X1); the backup and `restore:` line
  are the way back. Suggest a track the owner can lose for the first time.
- `--adopt-current`: the project file changed since the last apply (edited in SoundSwitch
  or restored). The file as it is now becomes the base, keeping those edits; `auto` then
  means that file, not the autoscript.

The first apply stores the current project file as the track's base; if the owner edited
that track in SoundSwitch, ask whether that is the base they want. Any other refusal
(SoundSwitch running, base changed, round trip, a change outside the sections): report it
and wait for the owner. Never add a flag on your own to get past a refusal: report the
refusal and wait.

## Red flags

| Thought | Reality |
|---|---|
| "They approved the choreography, so I apply it" | Approval is for the YAML. Writing SoundSwitch needs its own go. |
| "They said go for the last track, and I only tweaked one section" | A go covers one track's YAML as it was. Ask again. |
| "`--adopt-current` / `--accept-resize` gets past this refusal" | Report the refusal and wait. A flag goes in only on the owner's explicit yes. |
| "It is only `--accept-resize`" | It writes a file SoundSwitch may not load. Explain, ask, wait. |
| "This drop deserves white or strobe too" | Not in the budget for this block or peak: out. Ask the owner. |
| "I'll write the YAML and they can amend it" | They amend the Portuguese proposal. YAML comes after approval. |
