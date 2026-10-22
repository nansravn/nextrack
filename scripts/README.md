# scripts/

Tooling for keeping the on-disk audio library tidy and in sync with the repo, and
for checking that the repo agrees with itself.

- [`nextrack_tags.py`](#nextrack_tagspy) — retag and rename the audio library, pull BPM/key into `tracks/`.
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

A new rule is one function registered with `@rule("<rule-id>")` in
`check_repo.py`. Add its row to this table in the same change:
`tests/test_tooling.py` fails when a rule id is missing here.
