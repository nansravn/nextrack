# scripts/

Tooling for keeping the on-disk audio library tidy and in sync with the repo, and
for checking that the repo agrees with itself.

- [`nextrack_tags.py`](#nextrack_tagspy) — retag and rename the audio library, pull BPM/key into `tracks/`.
- [`nextrack_lights.py`](#nextrack_lightspy) — read SoundSwitch's light scripts, simulate the room, compile choreographies onto a track's script.
- [`nextrack_map.py`](#nextrack_mappy) — make the musical map of a track (Demucs, SoundSwitch tempo map, rekordbox cues) and print a playlist's set timeline.
- [`nextrack_show.py`](#nextrack_showpy) — build a show (the show language) into its choreographies, report the night, list the vocabulary.
- [`check_repo.py`](#check_repopy) — validate the graph, docs, pools and blocks against each other.

## `nextrack_tags.py`

Fixes the two things that drift in a downloaded DJ library — **embedded tags**
(Title/Artist often blank or garbage in MP3s) and **junk filenames** — and
harvests the **BPM/key** Serato/Tidal already wrote into the files back into
`tracks/*.yml`.

It edits tags with [`mutagen`](https://mutagen.readthedocs.io/), which rewrites
only the tag block (no re-encode), so Serato's **beatgrids and cue points survive**.
Do **not** retag these files with ffmpeg — it re-muxes and can drop that data.

### Install (one-time)

```bash
uv sync                                         # from the repo root: .venv with mutagen + pyyaml
uv run scripts/nextrack_tags.py --help          # verify

# point the tool at your audio library (machine-specific, so it's not in the repo)
echo 'export NEXTRACK_AUDIO_ROOT="/path/to/your/library"' >> ~/.bashrc
```

No uv? The system packages work too (and then plain `python3` runs the scripts):

```bash
sudo apt-get install -y python3-mutagen python3-yaml
python3 -c "import mutagen; print(mutagen.version)"   # verify
```

### Golden rule: dry-run, then `--apply`

Every command prints what it *would* do and changes nothing until you add
`--apply`. Pilot on one folder first with `--only <name>`. The examples call plain
`python3`; with uv, write `uv run nextrack_tags.py …` instead.

```bash
cd scripts

# 1. See the state of the whole library (no writes)
python3 nextrack_tags.py audit
python3 nextrack_tags.py audit --csv /tmp/library.csv          # full dump
python3 nextrack_tags.py audit --only axe                      # one folder

# 2. Fill MISSING/junk Title/Artist (keeps good tags) — pilot then whole library
python3 nextrack_tags.py fix-tags --only axe                   # dry-run
python3 nextrack_tags.py fix-tags --only axe --apply           # write axe/ only
python3 nextrack_tags.py fix-tags --apply                      # whole library

# 3. Clean junk filenames  ([NotSlider.nl], vk.com, " - Tech House", (infantil))
python3 nextrack_tags.py clean-names                           # dry-run
python3 nextrack_tags.py clean-names --apply

# 4. Pull embedded BPM/key into the repo YAML (fills only null fields)
python3 nextrack_tags.py pull-bpm                              # dry-run
python3 nextrack_tags.py pull-bpm --apply
git diff ../tracks                                             # review
```

### Subcommands

| command       | writes to        | what it does |
|---------------|------------------|--------------|
| `audit`       | nothing          | Per file: parsed vs embedded Artist/Title, BPM/key, and flags (`missing-title`, `garbage-title`, `missing-artist`, `junk-name`, `no-separator`, `title!=file`, `wav-skip`). Ends with a flag histogram. |
| `clean-names` | filenames        | Strips download-site junk and trailing genre/`Música N` suffixes → `Artist - Title.ext`. Keeps semantic `(Remix)` / `[Salsa Version]`. Collision-safe; logs renames to `_nextrack_rename_log.tsv`. |
| `fix-tags`    | file tags        | Fills **only** `Title`/`Artist` (MP3 `TIT2`/`TPE1`, FLAC `title`/`artist`) when they're **missing or junk** (blank, `Next Song`/`Mix Tutorial` placeholders, `[NotSlider.nl]`-style site tags). A present, good tag is **kept** — so featured artists (`A; B`) survive — just stripped of site-junk brackets. The fill source is the clean filename, or a matching `tracks/*.yml` entry. `--overwrite` forces filename/YAML to win even over a good tag (use with care). Serato frames / BPM / key are never touched. |
| `pull-bpm`    | `tracks/*.yml`   | Reads embedded BPM + key (key → Camelot) and fills `bpm`/`key` **only where currently `null`**. Matches a pool entry to a file by artist+title: exact first, then fuzzy — the file's artist may add collaborators and version words (`Remix`/`Extended`/`Mix`) are ignored, so `Skank - Algo Parecido (Remix)` still lines up with `Skank, Dubdogz, Bruno Be - Algo Parecido (Extended)`, while a genuinely different version stays unmatched. Comments/order preserved. Unmatched entries reported, never guessed. (A file with BPM but no embedded key fills only `bpm` — key waits on Serato analysis.) |

### Flags (type them after the subcommand)

- `--root PATH` — audio library root (default `$NEXTRACK_AUDIO_ROOT`; one of the two is required).
- `--only SUBSTR` — limit to files whose path contains `SUBSTR` (pilot on a folder).
- `--apply` — actually write (default is dry-run).
- `-v/--verbose` — `audit`: show every file, not just flagged ones; `pull-bpm`: list unmatched entries.
- `--overwrite` (`fix-tags` only) — let the filename/YAML overwrite a present, non-junk tag. Off by default so good embedded data (e.g. featured artists) is preserved.

### Safety notes

- Audio is git-ignored (by extension), so file edits never touch the repo; only
  `pull-bpm` writes tracked files (`tracks/*.yml`).
- The library lives on OneDrive, which keeps version history — a safety net if a
  bulk `--apply` needs undoing.
- WAV files are reported and skipped (tag support is limited; there's one).
- MP3s are saved as ID3v2.4 (their existing version) — no downgrade that could
  confuse Serato.

## `nextrack_lights.py`

Reads the light scripts SoundSwitch wrote for the owner's tracks and, from a
choreography in [`lightshows/tracks/`](../lightshows/README.md), edits one of them.
`soundswitch_format.py` (the file format, see
[docs/soundswitch/file-format.md](../docs/soundswitch/file-format.md)) and `lightshow.py`
(the rig and choreography models, the vocabulary and the compiler) are its libraries.
`tracks`, `dump`, `analyze`, `render`, `compile` and `status` only read the project; `apply`, `restore` and
`accept` are the ones that can write.

### Setup

```bash
uv sync
# the SoundSwitch project folder (machine-specific, so it is not in the repo)
echo 'export NEXTRACK_SOUNDSWITCH_PROJECT="/path/to/SoundSwitch/project"' >> ~/.bashrc
uv run scripts/nextrack_lights.py --help
```

Or pass `--project PATH` to any command. A *track* argument is the script GUID, a GUID
prefix, or `Artist — Title` (text of the track map).

### Commands

```bash
# list the project's tracks (GUID8, BPM, length, artist — title)
uv run scripts/nextrack_lights.py tracks
uv run scripts/nextrack_lights.py tracks --match happier

# per 8-bar phrase and fixture: lit share, pulses, colours, positions, shapes
uv run scripts/nextrack_lights.py dump "Marshmello x Bastille — Happier"
uv run scripts/nextrack_lights.py dump F41EB9E9 --yaml

# the dump reduced to metrics (Markdown): who overrides Main, white over colour, ...
uv run scripts/nextrack_lights.py analyze F41EB9E9 <another-track>

# the room simulated in one HTML file, before and (with --choreo) after
uv run scripts/nextrack_lights.py render F41EB9E9 --choreo lightshows/tracks/marshmello-x-bastille-happier.yml -o /tmp/sim.html

# compile a choreography to a file; the project is not touched
uv run scripts/nextrack_lights.py compile lightshows/tracks/marshmello-x-bastille-happier.yml -o /tmp/happier.ssfile

# dry-run of the real thing, then write it into the project
uv run scripts/nextrack_lights.py apply lightshows/tracks/marshmello-x-bastille-happier.yml
uv run scripts/nextrack_lights.py apply lightshows/tracks/marshmello-x-bastille-happier.yml --apply

# after hand edits in SoundSwitch: undo them, or make them official (dry-run, then --apply)
uv run scripts/nextrack_lights.py restore F41EB9E9
uv run scripts/nextrack_lights.py restore F41EB9E9 --apply
uv run scripts/nextrack_lights.py accept F41EB9E9
uv run scripts/nextrack_lights.py accept F41EB9E9 --apply

# which tracks are compliant: every choreographed one, one block, or a set (reads only)
uv run scripts/nextrack_lights.py status
uv run scripts/nextrack_lights.py status --block edm-assombrado
uv run scripts/nextrack_lights.py status --set sets/2026-10-31-halloween-em-casa.md
```

`render`, `compile` and `apply` take `--rig PATH` (default `lightshows/rig.yml`). They
refuse an invalid rig or choreography with the same messages `check_repo.py` gives, and
print the **manual cues** (things SoundSwitch must be told by hand) after the result.
`compile -o` and `render -o` refuse any path inside the project folder or inside
`<project parent>/nextrack-backups/`, compared lower-cased (the Windows drive under
`/mnt/c` ignores case).

`render` also draws the track's musical map (sections, five voice lanes, drops, hot cues)
under the timeline when `lightshows/maps/` of `--repo` (default: this repo) holds a valid
map whose `soundswitch` is the track's GUID. A stale map is skipped with a warning: its tempo
anchors differ from the script's (`stale (grid changed)`), or no map has the GUID but one
names the same track, so the script was redone (`stale (script GUID changed)`); either way
`nextrack_map.py analyze` redoes it. Without a map the page is unchanged.

### Reading `dump`

An *effective* value is what the fixture really shows: its own when one of its blocks
covers the moment, else the Main track's. Each row is one fixture per 8-bar phrase, but
the cells of a Vorlane are folded into two rows, `<Vorlane> RGB` (cells named `RGB nn`)
and `<Vorlane> W` (cells named `W n`). For such a row:

- `lit` is the share of the phrase in which **any** cell is lit (the union of the cells'
  lit time; "lit" is an effective level above 1 %);
- `pulses` counts rises (from under 10 % to over 90 %) on the pointwise maximum of the cells'
  effective curves: cells pulsing in unison count once, alternating cells count every step;
- colours, positions and shapes are the union across the cells.

### Golden rule: dry-run, then `--apply`

`apply` prints what it would change (fixtures touched, keys and blocks added and removed,
the manual cues) and writes nothing until you add `--apply`. Read the dry run first.

### Safety model of `apply --apply`

- **SoundSwitch must be closed.** The tool runs `tasklist.exe` and refuses while any
  process whose name contains `soundswitch` (any case) is listed. Under WSL, if
  `tasklist.exe` cannot be run, it refuses too, because a check that passes when it
  fails is no check. On a machine that is not WSL and has no `tasklist.exe` (CI), there
  is nothing to check.
- **Base copy.** The first `apply` of a track saves the project's current script as
  `<project parent>/nextrack-backups/base/<GUID>.ssfile`. Every later `apply`,
  `compile` and `render` starts from that base, so a choreography is always applied to
  the autoscript and never to its own earlier output. `render` shows the base as
  "before".
- **`state.json`** next to it (`<project parent>/nextrack-backups/state.json`) holds, per
  track, the hash of the base and of the file last written. `apply` refuses if the base
  copy changed or is missing, or if the project file differs from what the last
  `apply` wrote (you edited it in SoundSwitch). With a base copy but no `state.json`
  record of the track (the file was lost), the project file must equal the base, since
  hand edits could not be told apart otherwise.
- **The official version** is what the project file is expected to be: the accepted hand
  edits when there are any, else what the last `apply` wrote. `apply` keeps a copy of its
  output in `nextrack-backups/applied/{GUID}.ssfile`. After editing a track in SoundSwitch,
  `restore <track> --apply` backs the edited file up and puts the official version back;
  `accept <track> --apply` leaves the project file alone, copies it to
  `nextrack-backups/accepted/{GUID}.ssfile` and records its hash as `accepted` in
  `state.json`, so the hand edits become the official version. Both are dry-run without
  `--apply`, with `--apply` refuse while SoundSwitch runs, and refuse a track `apply` has not written or
  whose project file already is the official version; `restore` also refuses when its copy
  is missing or no longer matches `state.json`.
- **`--drop-hand-edits`** is what an `apply` needs on a track with accepted hand edits,
  since it replaces them. The dry run says so; `state.json` then loses `accepted`, and the
  accepted copy stays in `nextrack-backups/accepted/`.
- **`--adopt-current`** answers that refusal: the project file as it is now becomes the
  new base, keeping your edits. Use it after editing a track by hand in SoundSwitch.
- **A timestamped backup** of the project file is written to
  `nextrack-backups/<YYYYmmdd-HHMMSS>/` before the replace, and the command prints the
  restore line: `restore: cp "<backup>" "<project file>"`. If the write fails before the
  project file is replaced, the base copy is put back as it was.
- **`--accept-resize`** is required when the compiled file differs in size from the
  project file (it nearly always does). SoundSwitch loads a script of a different size
  into its editor (experiment X1a in
  [docs/soundswitch/experiments.md](../docs/soundswitch/experiments.md)), but playback on
  the lights is not yet confirmed (X1b); until it is, test on one track you can lose and
  keep the backup.
- **The haze is the one exception outside the sections.** Only the haze fixture's fan and
  fog may change there, and only to the rig's `level` over the whole track: one block from
  0 to the end of the track, every intensity key at the level. The tool refuses unless
  `lightshow.haze_problem` finds exactly that. Every other check is unchanged, and the
  haze tracks' colours, strobes and positions are compared with the base like any venue
  track.
- Before writing, the tool re-parses its own output and refuses unless it round-trips,
  everything outside the venue's tracks and Main equals the base, and outside the
  sections every venue track and Main shows what the base shows: the same keys (a key
  next to a section must carry the base's level there), the same blocks, the colour each
  colour block shows at the ends of what is left of it (within one step per byte, as a
  cut gradient is rounded), and the same position preset in force. The base itself must
  parse and serialize back to the same bytes. Writes are temp-file-then-rename.

To undo hand edits made after an `apply`, use `restore` (above). To undo the last
`apply` itself, copy the backup over the project file (the `restore:` line).
To return the track to the autoscript, close SoundSwitch and copy
`nextrack-backups/base/{GUID}.ssfile` over the file of the same name in the project
folder. Either way the next `apply` refuses (the file no longer matches `state.json`);
say `--adopt-current` to start again from the file as it now is (after copying the base
back, that is the base itself).

### Compliance: `status`

A track is **compliant** when three things hold:

- **choreography**: a `lightshows/tracks/*.yml` names its GUID in `soundswitch:`;
- **applied**: `state.json` records an apply, and compiling that choreography now, from the
  base copy and with today's rig and compiler, gives exactly the bytes that apply wrote. So
  it turns false by itself when the YAML, the rig's `level` or the compiler changed since.
  A refused compile shows its reason instead of yes or no, and so do an invalid choreography,
  a GUID the project does not have and an unreadable `state.json` (`state.json unreadable: …`);
- **haze**: the project file's fan and fog hold the rig's level over the whole track, as
  the guard of `apply` defines it. It shows `—` only when the rig has no haze fixture or the venue lacks
  its fan or fog nodes, and a `—` does not block compliance: there is no haze to hold. When the venue has a
  channel node but the script has no track for it, it shows `haze node <id> has no track in
  this script` and the track is not compliant. A project file that does not parse, or a haze
  check that fails, shows its reason instead.

A reason is one track's problem, so `status` goes on with the other tracks. A track map or
venues file that cannot be read stops it with exit 1, because no track can be judged without
them.

The **note** column is not part of the verdict. It says `edited in SoundSwitch after the
apply` when the project file differs from the official version (settle it with `restore`
or `accept`), and `hand edits accepted` when the official version is an accepted one. Hand
edits keep a track compliant unless they break the haze.

Without a filter, `status` lists every track that has a choreography, then counts the
project's tracks without one. `--block <id>` lists the block's tracklist in order, and
`--set <file>` the tracklists of the blocks the set links, each under its block id. A
tracklist line is matched to a script through a choreography whose `track:` is that track
(the matcher `check_repo.py` uses), else through the track map by `Artist — Title`; when
neither finds one, the line says `no SoundSwitch script found under this name`, and when the
track map finds several, `several scripts: <GUID8>, …`. The last line counts the compliant
tracks (`1 of 41 tracks compliant`). `--repo` (default: this repo) and `--rig` (default: the
repo's `lightshows/rig.yml`) say where the choreographies and the rig are.

`status` is read-only: it writes nothing, does not check whether SoundSwitch runs, and works
with it open. Its exit status is 0 whatever the verdicts.

### Tests against the real project

Tests use synthetic scripts and run anywhere. A few more read the owner's real project;
they are skipped unless `NEXTRACK_SOUNDSWITCH_REAL` points at a **read-only copy** of the
project folder (never the live one):

```bash
NEXTRACK_SOUNDSWITCH_REAL=/path/to/copy-of-project uv run pytest
```

## `nextrack_map.py`

Makes the **musical map** of a track (`lightshows/maps/<artist-title-slug>.yml`, schema in
[lightshows/README.md](../lightshows/README.md#musical-maps)) and prints the **set timeline**
of a rekordbox playlist. `musical_map.py` (the file format, the features, the sections and the
validator checks), `rekordbox_cues.py` (the rekordbox reader) and `set_timeline.py` (the
timeline model) are its libraries. It reads audio, rekordbox and the SoundSwitch project and
writes only map files in the repo.

### Setup

The default environment has what `show`, the validator and `render` need. `analyze`, `cues`
and `timeline` also need the optional dependency group `analysis` (Demucs, PyTorch, pyrekordbox
and its SQLCipher wheels: several GB with CUDA). It is not in CI, and the commands print the
install line when it is missing:

```bash
uv sync --group analysis
# machine-specific folders, so none of them is in the repo
echo 'export NEXTRACK_SOUNDSWITCH_PROJECT="/path/to/SoundSwitch/project"' >> ~/.bashrc
echo 'export NEXTRACK_AUDIO_ROOT="/path/to/your/library"' >> ~/.bashrc
echo 'export NEXTRACK_REKORDBOX_DIR="/path/to/folder/with/master.db"' >> ~/.bashrc
```

| input | option | environment variable | used by |
|---|---|---|---|
| SoundSwitch project folder (the track's GUID, audio path and tempo map) | `--project` | `NEXTRACK_SOUNDSWITCH_PROJECT` | `analyze`, `cues` |
| audio library root | `--root` | `NEXTRACK_AUDIO_ROOT` | `analyze` |
| folder that holds rekordbox's `master.db` | `--rekordbox` | `NEXTRACK_REKORDBOX_DIR` | `cues`, `timeline`, and `analyze` (optional: without it the map has no hot cues) |
| the NEXTRACK repo whose pools and maps are used | `--repo` (default: this repo) | | every command |

The audio file is found under the root by the base name of the path SoundSwitch stores
(Unicode-normalised, case-insensitive); several hits are narrowed to the one whose folder name
matches, and still ambiguous is refused with the list. The map's `track` is the pool's
`Artist — Title`; a track missing from its pool is refused (add it to the pool first).
A *track* argument is a script GUID, a GUID prefix or `Artist — Title`.

### Commands

```bash
# make the map of one track, or of every track of a rekordbox playlist
uv run scripts/nextrack_map.py analyze "Artist — Title"
uv run scripts/nextrack_map.py analyze --playlist 1-hi-ibiza-lightshow
uv run scripts/nextrack_map.py analyze F41EB9E9 --force --device cpu --keep-stems /tmp/stems

# reread the hot cues from rekordbox into existing maps (no audio)
uv run scripts/nextrack_map.py cues --playlist 1-hi-ibiza-lightshow

# print a map as text (reads only the map file)
uv run scripts/nextrack_map.py show "Artist — Title"

# the set timeline of a playlist: Markdown table, or --yaml
uv run scripts/nextrack_map.py timeline --playlist 1-hi-ibiza-lightshow --block blocks/<block-id>.md
```

- **`analyze <track>` or `analyze --playlist NAME`**: separates the audio with Demucs `htdemucs`
  (the GPU when there is one, else the CPU, or `--device cuda|cpu`) and writes the map. An
  existing map is kept unless it is stale (the audio file's hash, the script's GUID or its tempo
  anchors changed) or `--force` is given, so a playlist run only does what is missing or out of
  date. One line per track says what happened: `written`, `redone (stale)`, `redone (invalid)`
  (the existing map broke the schema), `kept`, or `refused <track>: <why>` (a playlist track
  SoundSwitch does not know or cannot tell apart from another says which). A map that does not
  parse is refused with `unreadable map … run analyze --force to rebuild it`. A `grid warning`
  line follows when the kick onsets sit more than a quarter of a step from the beat (either
  the grid is off, or the kick's attack is soft and `onsets.kick` reads late: see
  [Known limits](#known-limits)). `--keep-stems DIR` also writes the four stems (FLAC) under
  `DIR/<slug>/`; without it they live in memory only. A refused track makes the exit status 1,
  and the playlist run goes on.
- **`cues <track>` or `cues --playlist NAME`**: rewrites only the `hot_cues` lines of existing
  maps from rekordbox, leaving the rest of the file untouched. A map that does not parse or
  breaks the schema is refused (`unreadable map …`: rebuild it with `analyze --force`), and so
  is a hot cue past the map's last bar (the audio changed: run `analyze`); the map is then left
  as it was.
- **`show <track>`**: the map for directing, per 64 bars: a ruler, a `cues` line (the hot
  cues at their bars, `*` where two share a bar), one line of per-bar levels per voice and a
  `sections` line (`i` intro, `g` groove, `b` break, `u` build, `d` drop, `o` outro), then the
  drops with their size and the vocal phrases. `<track>` is a map file, its slug or the
  track's words.
- **`timeline --playlist NAME [--block FILE] [--yaml]`**: the order comes from the rekordbox
  playlist and the cues live from rekordbox; the maps give the bars. Needs no SoundSwitch
  project and no audio. A leg plays bars `[B, G)` (the first from bar 1, the last to its last
  non-silent bar) at its played tempo, and the set clock at `G` is the start of bar `G`, which
  is where the next track's `B` begins. Per transition it prints:
  - the outgoing track's `G` and the incoming track's `B`, and the **offset** in bars between
    the two (`B - G`);
  - the **overlap**: the bars the outgoing track still sounds after `G`, until its last
    non-silent bar, and the incoming track's sections that fall in it;
  - the **arrival**: the incoming track's first drop at or after the end of the overlap, with
    its set clock; `none` (with the drops inside the overlap) when there is no such drop;
  - the **peak**: the biggest drop strictly between the incoming `B` and its own `G` (the same
    bar as the arrival when they agree). Which of the two carries the "new song" gesture is
    the light plan's call.

  The played tempo is the script's BPM, or with `--block` the BPM field of the block's
  tracklist line (`122`, or a ramp `122-125`, linear in bars). After a track with no map the
  clock cannot be known, so the following clocks are relative and print as `+m:ss`. Warnings
  name a track missing `B` or `G` where the order needs it (the first needs no `B`, the last no
  `G`), a cue not on a beat, a `B` or `G` not on beat 1 (`G at 137.3: the timeline assumes cues
  on beat 1`; the timeline still counts from the start of its bar), a missing or unreadable map
  (one that does not parse or breaks the schema counts as missing), and a map whose stored hot
  cues differ from rekordbox's (a cue moved since: refresh with `cues`).

With `--playlist`, a playlist with no tracks is an error for `analyze`, `cues` and `timeline`:
`playlist NAME has no tracks`, exit status 1.

### Safety model

- **Read-only** on the audio library, the SoundSwitch project and rekordbox. The only files
  written are `lightshows/maps/*.yml` of `--repo`, and `--keep-stems DIR` when asked.
- **rekordbox's live database is never opened.** `master.db` (and its `-wal` and `-shm`) are
  copied to a temporary folder, read there with pyrekordbox, and the copy is deleted when the
  command ends, so rekordbox may be running. No key goes into the repo.
- Audio and stems never enter the repo; tests make synthetic audio under `tmp_path` and inject
  the separator and the rekordbox reader, so no test loads a model or a real database.
- A map that would break its own schema is refused instead of written.

### Known limits

- `onsets.kick` can sit a step late on a soft-attack kick. A kick is timed at the steepest rise
  of the drums stem's energy in the 100 ms before its low-band onset; a kick with no sharp
  transient has its steepest rise in its body, tens of ms after the hit, and an onset more than
  half a step late is quantised to the next step. The same lateness raises a `grid_warning`
  while the grid is right (seen on 2 of 15 real tracks, one at +64 ms with the grid within 6 ms
  of the audio), so the warning names both causes: check the grid against the audio.
- `onsets.perc` includes the kick's click, and quiet kicks within a second before a louder
  section can be missing from `onsets.kick`.
- The kick/percussion split is by frequency, so a low tom can read as kick.
- rekordbox's database format is reverse-engineered by pyrekordbox; an update of rekordbox can
  break the reader.

## `nextrack_show.py`

Builds, reports on and describes a **show**: a night written in the show language
(`lightshows/shows/<show-id>/`, schema and manual in
[lightshows/shows/README.md](../lightshows/shows/README.md)). `show_language.py` (the compiler
and the emitter), `show_gestures.py` (the gesture registry) and `show_rules.py` (the show
rules) are its libraries; `check_repo.py` runs the same compile as the rules `show-source`,
`show-rules` and `show-compiled`. It reads the show, the musical maps, the set and its blocks,
and writes only choreographies.

### Setup

Nothing beyond `uv sync`: no audio, rekordbox, SoundSwitch or `--group analysis`. `--repo PATH`
(default: this repo) is where the maps, the set, the blocks and `lightshows/tracks/` are read
and written. A *show* argument is a folder path or the id of a folder under
`lightshows/shows/`. A relative one is looked up under `--repo` first (`<repo>/<show>`, then
`<repo>/lightshows/shows/<show>`), then from the current folder, so
`build lightshows/shows/<id> --repo <copy>` builds the copy's show. The usage error names the
folders it tried, or the folder it found outside `lightshows/shows/`.

### Commands

```bash
uv run scripts/nextrack_show.py build <show>                  # compile, run the rules, write lightshows/tracks/*.yml
uv run scripts/nextrack_show.py build <show> --check          # write nothing; exit 1 if a file would change
uv run scripts/nextrack_show.py build <dir> --out <scratch>   # a variant: write the choreographies elsewhere
uv run scripts/nextrack_show.py build <show> --adopt          # first build of a ported set: take over hand-written files
uv run scripts/nextrack_show.py report <show>                 # the night as text, for a critic
uv run scripts/nextrack_show.py vocab [<show>]                # anchors, layer words, gestures, rules (and the show's palette and looks)
```

- `build` prints `wrote <path>` or `unchanged <path>` per track, then the rule findings. With
  a `show-source` finding it writes nothing. With only rule findings it writes the files, so a
  draft can be rendered and critiqued, and it exits 1.
- `build` and `build --check` also print
  `stale <path>: owned by this show, which no longer compiles it; delete it` for each
  choreography with this show's header whose track the show no longer compiles (a track that
  left the set). They never delete it, and exit 1 while it is there.
- `report` prints, per track, one line per compiled section (bars, name, source, layers,
  accents, role, moment, the music under it), then the budget tally, the arrivals, what the
  compiler decided on its own (bridges, default ends) and the findings.
- `vocab` prints what an agent needs to write a show without reading the docs (the anchors,
  each layer's words and mapping keys, the gestures, the rules); with a show it adds its
  palette and looks.

**Output and exit status.** Findings are `path:line: rule-id: message` (`show-source`,
`show-rules`), like `check_repo.py`, followed by `N finding(s)`. `0` no findings, `1` findings
(for `report`, any finding printed; for `build --check`, a file that would change; for both
`build` and `build --check`, a stale file), `2` usage (unknown show, a show outside
`lightshows/shows/` without `--out`).

### Safety model

- It writes only `lightshows/tracks/*.yml` of `--repo`, or the folder of `--out`. Each file is
  written whole, through a temporary file; nothing is written when any file is refused.
- Ownership: a generated choreography starts with
  `# Generated by scripts/nextrack_show.py build from <folder>/`. `build` overwrites files with
  its own header. A hand-written file (no header) is refused unless `--adopt`, which takes over
  only hand-written files. A file owned by another show is always refused. `--out` skips the
  check, because it never touches the repo's choreographies.
- A show folder outside `<repo>/lightshows/shows/` builds only with `--out DIR`.
- The generated files are committed, and `show-compiled` fails when one differs from what its
  show compiles to. Never edit one by hand.
- Nothing touches SoundSwitch, rekordbox or audio. Seeing and applying a generated
  choreography is [`nextrack_lights.py`](#nextrack_lightspy), unchanged, with the owner's go.

### Known limits

- A track has one choreography: a track played twice in the set is a finding, and a show per
  track (not per variant) is committed. Variants live outside the repo and build with `--out`.
- Gestures emit today's layer vocabulary only; a new kind of light needs `lightshow.py` first.
- The rules are the fixed list in the manual's table; a new one is a function with tests
  (CLAUDE.md, "Add a show rule").

## `check_repo.py`

Checks that the repo agrees with itself. `genres/graph.yml`, the taxonomy
([`docs/taxonomy.md`](../docs/taxonomy.md)), the Mermaid map
([`docs/genre-graph.md`](../docs/genre-graph.md)), the track pools (`tracks/*.yml`)
and the blocks (`blocks/*.md`) all refer to each other; this script loads them and
reports every place where they disagree. It only reads files, never writes.

```bash
uv run scripts/check_repo.py                 # check this repo
uv run scripts/check_repo.py --repo PATH     # check another checkout, e.g. a worktree
uv run pytest                                # tests for check_repo.py and nextrack_tags.py
```

CI runs the first command and the tests on every push and pull request
(`.github/workflows/checks.yml`).

**Output.** One line per finding, `path:line: rule-id: message`, sorted by path,
line and rule. `path` is relative to the repo; `line` is 1-based, or `0` for a
finding about a whole file. The last line is `N problem(s)` or
`ok: <nodes> nodes, <edges> edges, <tracks> tracks, <blocks> blocks`.

```
tracks/axe.yml:7: track-schema: energy 11 is not an integer from 1 to 10
1 problem(s)
```

**Exit status.** `0` when there are no findings, `1` when there are. A file that
cannot be read or parsed is a `parse-error` finding, never a traceback, and the
rules that depend on that file skip it.

A finding in the real repo means fixing the data, not loosening the rule. The
schemas the rules enforce are documented in [`genres/README.md`](../genres/README.md),
[`tracks/README.md`](../tracks/README.md) and [`blocks/README.md`](../blocks/README.md);
if a rule contradicts one of them, the README wins.

### Rules

| rule id | what it checks |
|---------|----------------|
| `parse-error` | A file could not be loaded: it is missing or not UTF-8, its YAML is invalid (a key repeated in one mapping counts: YAML 1.2 forbids it and PyYAML would silently keep the last), `graph.yml` has no `nodes` list of mappings, a pool is not a list of mappings, or a block's front matter is unclosed or not a mapping. A pool that starts with a UTF-8 byte-order mark is also reported, because `nextrack_tags.py` would miss an entry on its first line; in any other file a BOM is ignored. |
| `graph-node-schema` | Each node has exactly the keys `id`, `name`, `family`, `bpm`, `energy`, `neighbors` (plus optional `feel`, `subgenres`) with valid values: a kebab-case `id`, `family` is `brazilian` or `global`, `bpm` and `energy` are `[min, max]` integer ranges with min <= max (`energy` within 1-10), `neighbors` is a list. |
| `graph-unique-ids` | No two nodes share an `id`. |
| `graph-edge-schema` | Each edge has exactly `to`, `strength` (`strong`, `medium` or `weak`) and `via` (a non-empty string). |
| `graph-edges-resolve` | Each edge's `to` is an existing node other than its own, and a node has at most one edge to any target. |
| `graph-node-connected` | Every node has an edge out to, and an edge in from, another existing node. |
| `taxonomy-matches-graph` | The ``### `id` `` headings of `docs/taxonomy.md` are exactly the node ids. |
| `mermaid-matches-graph` | The first `mermaid` block of `docs/genre-graph.md` declares every node and draws exactly the graph: a `---` line for a pair whose strongest edge is `strong`, `-.->` for `medium`, nothing for `weak`, each pair once. Any other line with a link operator (`-->`, `==>`, `A---B`, `-.-`, `A --- B & C`) is a finding, because the rule would not read it. |
| `links-resolve` | Every relative link in every Markdown file points at a path that exists. Links in code, `#anchors` and URLs are ignored, as are files under a dot directory of the repo. |
| `pool-file-is-node` | Each `tracks/<name>.yml` is named after a node id. |
| `track-schema` | Each entry has the keys `title`, `artist`, `genre`, `bpm`, `key`, `energy`, `status` (plus optional `remixer`, `duration`, `year`, `source`, `tags`, `notes`) with valid values: `bpm` is `null` or an integer from 1 to 300, `key` is `null` or a Camelot key such as `8A`, `energy` is an integer from 1 to 10, `status` is `to-download`, `downloaded` or `organized`, `tags` is a list. |
| `track-genre-matches-pool` | An entry's `genre` is the name of the pool file it is in. |
| `track-title-first` | Every entry starts on a `- title:` line at column 0 and every such line starts an entry, because `nextrack_tags.py` finds entries by that line. |
| `track-unique` | No two entries, in one pool or two, share artist and title once case, accents and punctuation are folded. |
| `block-frontmatter` | A block starts with front matter that has exactly the keys of the template in `blocks/README.md`, with valid values: `function`, `style` and `duration` in the documented forms, `genres` existing node ids, `bpm` and `energy` ranges, `lightshow` null or an existing path. |
| `block-tracklist-resolves` | A block has a heading that starts with `## Tracklist`, and each `N. Artist — Title · …` line under it has that format and matches a track in some pool. |
| `block-bridges-are-edges` | Each backticked node id in `## Bridge in` / `## Bridge out` follows a graph edge: into one of the block's genres for Bridge in, out of one for Bridge out. |
| `lightshow-rig` | `lightshows/rig.yml` (optional) has exactly `room`, `fixtures` and `matrix`; each fixture has a `kind` (`mover`, `matrix`, `haze`, `hue-chandelier`) and, when given, a `corner` (`NE`, `SE`, `NW`, `SW`, `centre`); `matrix.white_max` is a number in (0, 1]; a `haze` fixture has a `level` in (0, 1] and no other kind has one. Schema in `lightshows/README.md`; the checks live in `scripts/lightshow.py`. |
| `lightshow-track` | Each `lightshows/tracks/*.yml` has the choreography keys with valid values: `track` is `Artist — Title` and matches a pool track (same matcher as block tracklists), `soundswitch` is a GUID, `sections` are sorted and do not overlap, layer names, moves, draws, rates and `#RRGGBB` colours are from the vocabulary, and unknown option keys are findings. |
| `musical-map` | A musical map's schema, its pool track and its file name: each `lightshows/maps/*.yml` has exactly the map keys with valid values (per-bar strings of `bars` characters, step lists adding up to `bars × 16`, sections that cover every bar, bar numbers inside `1..bars`), its `track` matches a pool track, and the file is named `slug(track).yml`. The checks live in `scripts/musical_map.py`. |
| `lightshow-plan` | Each `lightshows/sets/*.md` (but `README.md`) has front matter whose `set` is an existing path relative to the repo root and whose `budget` keys are layers or `white-accent`. |
| `show-source` | A show in `lightshows/shows/<id>/` does not compile: schema of `show.yml` or a track file, the set path (repo-relative), track files against the set's tracks, a missing or invalid map, an anchor, a span, a look, a palette name, a gesture and its parameters (a problem from `gesture_defaults` once, at `show.yml`), an unknown rule id or bad rule parameters, a problem in the generated choreography. |
| `show-rules` | The show's own rules (`rules:` in `show.yml`) fail; only for shows with no `show-source` finding. |
| `show-compiled` | A track's `lightshows/tracks/<slug>.yml` is missing or differs from what its show compiles to (run `nextrack_show.py build <id>`, or `build <id> --adopt` for a hand-written file); a choreography whose ownership header names a show that does not exist or does not compile that track; two shows that own the same track. |

A new rule is one function registered with `@rule("<rule-id>")` in
`check_repo.py`. Add its row to this table in the same change:
`tests/test_tooling.py` fails when a rule id is missing here.
