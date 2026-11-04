# Continuous haze and a compliance status — design

Date: 2026-11-04. Branch `feat/continuous-haze`. Builds on
[the choreography design](2026-10-31-soundswitch-choreography-design.md).

## Why

The owner's haze machine (Lig Light LL-HZ600K, two channels: fan and fog output) makes
**haze**: a thin mist meant to sit in the room continuously, so the beams read. It is not
a smoke machine, and it should not follow the music. Today it does the opposite:

- In SoundSwitch's autoscript the two haze channels have no content of their own, so they
  follow the Main track: the mist output pulses with Main's intensity all through a song
  (Happier: 30-65 % on average per section, both channels).
- The choreography's `haze` layer treats haze as an effect (`burst`, `on`, `off` per
  section), and every section that does not set it keeps the autoscript's pulsing. The
  room simulator shows it plainly: the whole-room veil rises and falls with Main.

The owner wants the opposite rule: **fan and fog fixed at 50 % for the whole song, every
song**, with no pulsing and no bursts. A real smoke machine may come later; syncing smoke
with moments of the music belongs to that machine, not to the haze.

The owner will run the lightshow skill on every track over time, one track at a time.
They want to see which tracks are done: choreographed, applied, and with the haze at the
rig's level.

## Goals

1. The haze level is a property of the room, set once in `lightshows/rig.yml` (`0.5`
   today) and the same for both channels.
2. Every compiled track holds both haze channels at that level for the entire track:
   before the first section, inside every section, after the last one. Nothing in a
   compiled track makes the haze follow Main.
3. The choreography vocabulary has no haze effect any more: haze is not something a
   section decides.
4. `apply` still refuses any change outside the sections, except exactly this one: the
   two haze channels holding the rig's level.
5. A read-only `nextrack_lights.py status` command tells, per track, whether it is
   **compliant**: it has a choreography, the last apply's output is still what that
   choreography compiles to today, and the project file's haze channels hold the rig's
   level. Hand edits made in SoundSwitch after the apply do not break compliance; `status`
   flags them.
6. Two commands settle a hand-edited track: `restore` puts back the official version
   (without the hand edits), `accept` makes the hand-edited file the new official version.
7. The lightshow skill, the READMEs and the simulator speak of haze as a constant mist.

## Non-goals

- Writing tracks that have no choreography, or writing many tracks in one command. The
  haze reaches a track when the owner runs the skill on it and applies it (owner's
  decision: track by track).
- Separate levels for fan and fog (owner's decision: one number for both, to keep it
  simple).
- A smoke machine, smoke bursts or any haze effect tied to music moments.
- Confirming that the machine reacts to the fog channel (experiment X10) or which DMX value
  a level becomes (E5). Those stay experiments.
- Lifting `--accept-resize` (the open half of experiment X1).

## Anti-goals (a failure even if it works)

- A compiled track in which the haze still follows Main anywhere, including the bars
  outside the sections.
- A compliance list that someone has to maintain by hand, or that says "done" for a track
  whose choreography, rig level or compiler changed since the apply, or whose haze no
  longer holds the level.
- Hand edits that are silently lost: by a `restore` without a backup, or by an apply that
  replaces accepted hand edits without saying so.
- `apply` accepting any other change outside the sections because of this exception.
- `status` writing anything, or needing SoundSwitch to be closed.

## The owner's decisions

| # | Decision | In their words / when |
|---|---|---|
| O1 | Haze is a constant mist, not an effect | "O haze não é fumaça, é uma neblina bem fina que deve ser aplicada continuamente no ambiente." |
| O2 | Fan and fog both at 50 %, fixed, for the whole song | "Pode deixar ambos em 50 % para simplificar … fixo sempre" |
| O3 | Also for songs that would otherwise stay on the autoscript | "Fixa em 50 % também, mesmo sem coreografia." |
| O4 | Applied track by track as the skill runs, not in bulk | "Faixa a faixa, conforme eu for rodando a skill." |
| O5 | A way to see which tracks are compliant: choreography done and haze at 50/50 | approved the `status` table mockup ("Tá bom assim") |
| O6 | Smoke synced to the music only with a future smoke machine | out of scope here |
| O7 | Hand edits after an apply (the manual cues) keep the track compliant; `status` says the track was edited in SoundSwitch after the apply | "de acordo com continuar em dia, e com a notificação de editada no soundswitch depois do apply" |
| O8 | An easy choice for a hand-edited track: restore the version without the hand edits, or make the hand-edited version the official one | "restaurar a versão sem as edições manuais, ou tornar a versão com as edições manuais a nova fonte da verdade" |

O3 and O4 together mean: a track the owner wants left on the autoscript still goes through
the skill, with a choreography that has **no sections** (§3). It then compiles to the
autoscript plus the constant haze and can become compliant. This matters beyond taste:
69 of the project's 486 scripts have more than 8 tempo anchors, which the compiler
refuses for any section (bar numbers would not follow the music). Without this they could
never get the constant haze.

## Design

### 1. Rig: the haze level

`lightshows/rig.yml`, haze fixture, gains a required `level`, a number in (0, 1]:

```yaml
haze: {node: " Lig Light LL-HZ600K", kind: haze, fan: "Main -  Lig Light LL-HZ600K",
       fog: "Main -  Lig Light LL-HZ600K - 2", level: 0.5}
```

- `problems_rig` reports a `kind: haze` fixture without `level`, or a `level` that is not a
  number in (0, 1]. `level` on any other kind is reported too.
- The level is SoundSwitch's intensity fraction, written with `lightshow.level_of`, the
  same scale as every other level the compiler writes (my call). What DMX value the
  venue's channel ranges make of it is not settled (E5), and the design does not depend
  on it.
- The pt-BR comment in `rig.yml` calls the machine "máquina de haze (neblina)", not
  "máquina de fumaça".

### 2. Compiler: constant haze over the whole track

After all sections are compiled, one final pass writes the haze fixture:

- On the fan node and on the fog node, one own block (B span) covering the whole track and
  two intensity keys at `level_of(rig level)`, one at each end of that block, so the level
  is flat. "Whole track" runs from 0 ms to the later of the script's last event
  (`nextrack_lights.script_end`) and the track map's duration for the GUID, when known.
  The builder may put the logic in `lightshow.py` and pass the end in. Whatever the base
  had on those two nodes is replaced, including the autoscript's keys and any older haze
  blocks.
- The pass runs last, so the haze nodes end up flat even where a section's `hue`
  materialised Main into every leaf node (which today includes the haze channels). The
  builder may instead exclude the haze nodes from materialising; the result must be the
  same.
- The group node (` Lig Light LL-HZ600K`) is left as it is: groups carry no content.
- When the venue lacks the haze fixture or one of its channels, compile behaves as today
  for a missing fixture: a manual cue, nothing written for it.
- Until X10 is answered, every compile prints **one** manual cue for the whole track (not
  one per section): `haze at <level>, whole track: experimental: confirm the machine
  reacts`. Today's per-section haze cue goes away with the layer.

### 3. Vocabulary: no haze layer

- `haze` leaves `LAYERS`, so it is neither a section key nor a show-plan `budget` key
  (`BUDGET_KEYS` is built from `LAYERS`). `check_repo.py` then reports a section with
  `haze:` and a plan budget with `haze:` through the existing `lightshow-track` and
  `lightshow-plan` rules. No new validator rule is needed.
- `_compile_haze`, the `burst`/`on`/`off` values and their checks are removed.
- `sections` may be an empty list (today it must be non-empty). A choreography without
  sections means "the autoscript everywhere, plus the constant haze". Its compile skips
  `_check_grid` (both the 8-anchor limit and the grid match), because no bar number is
  used. `grid` stays a required key (the skill writes the script's first anchor), but it is
  only checked against the script when there are sections (my call).

### 4. `apply` (and `compile`): the one allowed change outside the sections

`_compile_checked` keeps every check it has. The outside-the-sections check
(`_outside_problem`) skips the haze fixture's fan and fog nodes. In their place, a new
check requires those two nodes to hold the rig's level everywhere: exactly one B span
covering the whole track, and intensity keys that are all `level_of(level)`. Anything else
on them is a refusal with a message naming the node. Every other node, Main included, is
checked outside the sections exactly as today.

### 5. `status`: which tracks are compliant

`uv run scripts/nextrack_lights.py status [--block <block-id> | --set <set-file>]`. Read
only: it never writes, and works with SoundSwitch open.

Per track it reports three facts and a verdict:

| Column | True when |
|---|---|
| choreography | a `lightshows/tracks/*.yml` has this track's GUID in `soundswitch:` |
| applied | `state.json` records an apply of this track, and compiling that choreography **now** from the track's base copy (`nextrack-backups/base/<GUID>.ssfile`), with today's rig and compiler, gives exactly the bytes that apply wrote (`applied` hash) |
| haze | the project file's fan and fog nodes hold the rig's level over the whole track, as §4 defines it |
| compliant | all three |

Plus one note column, not part of the verdict (O7):

| Note | When |
|---|---|
| `edited in SoundSwitch after the apply` | the project file differs from the official version (§5b) |
| `hand edits accepted` | the official version is an accepted one, not the apply's own output |

- "applied" is computed, not just read from `state.json`, so it turns false on its own
  when the YAML changed after the apply, the rig's level changed, or a compiler change
  would write something different. That is what "compliant with the current revision of
  the skill" means. Hand edits in SoundSwitch do not touch it; they show in the note, and
  in "haze" when they break the mist. A choreography whose compile is refused (more than
  8 tempo anchors with sections, a grid that does not match) shows that reason instead
  of yes/no. With no apply record, "applied" is false.
- "haze" is read from the project file alone, so it is meaningful for every track.
- **Which tracks it lists** (my call): with no filter, every track that has a
  choreography, followed by one summary line counting the project's tracks without one.
  `--block` lists the block's tracklist in order; `--set` lists the set's blocks in
  order, each tracklist under its block id.
- **Matching a tracklist line to a script** (my call), in this order:
  1. a choreography whose `track:` is that pool entry, found with the same matcher
     `check_repo.py` uses for choreographies; its `soundswitch:` GUID is the script;
  2. otherwise the track map, by `Artist — Title`, the way `project.resolve` folds it.

  When neither finds anything, the line says "no SoundSwitch script found under this name".
  It does not say "not in SoundSwitch": the pool's tags often differ from the track map's,
  and the Halloween set has 40 such lines out of 133. When the track map finds several
  scripts and no choreography picks one, the line lists their GUID8s. The skill's
  step 1 already asks the owner which file they play.
- The last line counts compliant tracks, as in the mockup the owner approved:
  `1 of 41 tracks compliant`.
- Output in English like the rest of the tool, with English column names
  (my call; the mockup the owner saw had Portuguese headers). The skill translates for the
  owner.
- Exit status 0 whatever the verdicts; the command reports, it does not gate.

### 5b. The official version: `restore` and `accept` (O8)

Each applied track has one **official version**: the bytes the last apply wrote, or the
hand-edited file the owner last accepted. `state.json` gains, per track, an `accepted`
hash (absent until an accept). `apply` keeps a copy of what it writes in
`nextrack-backups/applied/<GUID>.ssfile`, and `accept` keeps one in
`nextrack-backups/accepted/<GUID>.ssfile`, so either version can be put back. No apply has
run on the owner's machine yet, so no migration is needed.

- `nextrack_lights.py restore <track>`: copies the official version over the project
  file, dropping the hand edits made since. It is a dry run without `--apply`. With
  `--apply` it needs SoundSwitch closed, writes a timestamped backup of the current file
  first, and prints the `backup:` and `restore:` lines, like `apply`. It refuses when the
  project file already is the official version, or when no apply record exists.
- `nextrack_lights.py accept <track>`: the current project file becomes the official
  version. It writes `nextrack-backups/accepted/<GUID>.ssfile` and `state.json`, never the
  project file. It needs SoundSwitch closed, so the file on disk is what the editor last
  saved, and it is a dry run without `--apply`. The base copy does not change, so later
  compiles still start from the autoscript.
- `apply` on a track whose project file differs from the official version: refused as
  today, with a message that names both ways out (`restore`, or `accept` then apply). It
  replaces today's hint, `--adopt-current`, which stays available but is no longer the
  first suggestion.
- `apply` on a track whose official version is an accepted one: the new output replaces
  the accepted hand edits (the compiler cannot carry them; the skill lists the manual
  cues again). The dry run says so in one line, and `--apply` needs `--drop-hand-edits`,
  a flag the skill uses only on the owner's explicit yes, like the other two (my call).
  After the write the official version is the new output and `accepted` is cleared. The
  accepted copy stays in `nextrack-backups/accepted/` until the next accept.

### 6. Simulator

`scripts/lightshow_sim.html` needs no new logic: it already draws the room veil from the
fog channel's own block, so a compiled track shows a constant veil. Its pt-BR note says
"neblina (haze)" where it says "fumaça", and states that the mist is constant in a
compiled track.

### 7. Skill

`.claude/skills/lightshow/SKILL.md`:

- Remove haze from the effects the owner budgets and from the proposal's layers. The
  directing principle on haze becomes: the mist is constant at the rig's level in every
  compiled track, so beams always read a little; it is not a choice per section.
- A track the owner wants left on the autoscript gets a choreography with no sections
  (O3). So does a track with more than 8 tempo anchors. The skill's "stays on the
  autoscript: stop" rule becomes: tell the owner the lights stay on the autoscript, then
  write the no-section choreography so the haze still applies.
- After an apply, run `status` for that track (or its block) and report the verdict in
  pt-BR.
- When `status` flags a track as edited in SoundSwitch, ask the owner: `restore` (drop the
  hand edits) or `accept` (make them official). Run either only on their word, dry run
  first. `--drop-hand-edits` joins the red-flag table with the other two flags.
- The manual-cue translation includes the one haze cue.

## Data to change in the same branch

- `lightshows/rig.yml`: `level: 0.5`; comment wording.
- `lightshows/tracks/marshmello-x-bastille-happier.yml`: drop `haze: {burst: 6s}` from
  `ponte`. Its pt-BR `story` and `budget` stop talking about a haze moment ("um haze") and
  say the mist is constant. This is prose the owner wrote with Claude; the builder edits it
  minimally and lists the change for the owner.
- `lightshows/sets/2026-10-31-halloween-em-casa.md`: drop the `haze:` budget line; rule 3
  and the moments that mention haze bursts are rewritten to say the mist is constant all
  night. The same minimal-edit rule applies.

## Documentation in the same change

- `lightshows/README.md`: rig keys (`level`), the vocabulary table and its notes without
  `haze`, the manual-cue list, "haze" described as a constant mist.
- `scripts/README.md`: the `status`, `restore` and `accept` commands; in the safety model,
  the official version, `--drop-hand-edits`, the new backup folders, and the one exception
  to the outside-the-sections rule.
- `docs/rig.md`: the haze machine makes a constant mist at the rig's level.
- `docs/soundswitch/experiments.md`: X10 now asks whether the machine reacts to a constant
  50 % on both channels.
- The choreography design's decision ledger gets no edit; this document supersedes its
  decision 13 (haze as a per-section effect).

## Testing

Write the tests first. Each behavior below gets a passing and a failing case where it has
one:

- Rig: `level` required for `haze`, range (0, 1], refused on other kinds.
- Compile on a synthetic script whose haze channels follow Main and carry their own
  autoscript keys: after compiling, both nodes are one block over the whole track, flat at
  the level. This holds with no section touching anything, with a `hue` section (which
  materialises Main), and for bars before the first and after the last section.
- One haze manual cue per compile.
- A choreography with no sections compiles on a script with more than 8 tempo anchors and
  on one whose first anchor differs from `grid`. Only the haze nodes change. A choreography
  with sections is still refused on both.
- A section or a plan budget with `haze` is a `check_repo` finding.
- `apply`: a compiled script passes; a script whose haze nodes differ from the level
  anywhere is refused; any other node that changes outside the sections is still refused.
- `status`: no choreography; a choreography never applied; applied and current
  (compliant); project file edited after the apply (still compliant, with the note); an
  edit that breaks the haze (not compliant); YAML changed after the apply; rig level
  changed; a compile refusal shown as the reason; `--block` with a line found only
  through its choreography, one found in no way, one with several scripts; the summary
  line.
- `restore`: puts the official version back and backs up the edited file; dry run writes
  nothing; refuses with SoundSwitch running, with no apply record, and when there is
  nothing to restore; after an accept it restores the accepted version.
- `accept`: records the edited file as official without touching the project file; dry
  run writes nothing; refuses with SoundSwitch running; afterwards `status` shows
  `hand edits accepted` and `apply` refuses without `--drop-hand-edits`.
- `apply`: an edited track is refused with the restore/accept message; `--drop-hand-edits`
  writes, clears `accepted` and keeps the accepted copy.
- `check_repo.py` and `pytest` pass; the real repo's data is fixed, not the rules.

## Constraints

- Everything in [the choreography design's constraints](2026-10-31-soundswitch-choreography-design.md#constraints)
  still holds: dry run first, SoundSwitch closed for `--apply`, the base copy, backups,
  nothing hard-coded about the machine.
- The local branch `chore/record-x1-result` (not yet committed) rewords the
  `--accept-resize` lines of `SKILL.md` and `scripts/README.md`. Whichever branch reaches
  `main` second rebases over the other.

## Left to the builder

- Where the whole-track pass lives (`lightshow.py` or the CLI) and how the track end
  reaches it.
- Whether the haze nodes are excluded from materialising or simply overwritten last.
- Column widths and the exact wording of `status` lines and messages.
- How `--set` takes its argument (a path under `sets/` or a stem).

## My calls (for the owner to check)

1. The level is SoundSwitch's intensity scale (what the editor shows), not a DMX value.
2. A track left on the autoscript, or with more than 8 tempo anchors, becomes compliant
   through a choreography with no sections.
3. `status` without a filter lists only choreographed tracks plus one count of the rest.
   Tracklist lines are matched through a choreography first, then the track map.
4. "applied" also turns false when the choreography, the rig level or the compiler would
   now write something other than what the last apply wrote. That is how "compliant with
   the current revision of the skill" is checked.
5. `status` speaks English like the rest of the tool.
6. Happier's and the Halloween plan's haze prose are edited minimally and listed for the
   owner.
7. `restore` goes back to the official version, which is the accepted one after an
   `accept`. Going back to the apply's own output after an accept means applying again.
8. A new apply over accepted hand edits needs `--drop-hand-edits`, because the compiler
   cannot carry hand edits across. The accepted copy stays in `nextrack-backups/accepted/`.
9. A variable-tempo track (69 of 486) is handled by a choreography with no sections: the
   lights stay on the autoscript and only the haze changes.
