# scripts/

Tooling for keeping the on-disk audio library tidy and in sync with the repo.

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
sudo apt-get install -y python3-mutagen
python3 -c "import mutagen; print(mutagen.version)"   # verify

# point the tool at your audio library (machine-specific, so it's not in the repo)
echo 'export NEXTRACK_AUDIO_ROOT="/path/to/your/library"' >> ~/.bashrc
```

### Golden rule: dry-run, then `--apply`

Every command prints what it *would* do and changes nothing until you add
`--apply`. Pilot on one folder first with `--only <name>`.

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
