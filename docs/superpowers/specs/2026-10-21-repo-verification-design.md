# Repo verification & superpowers readiness — design

- **Date:** 2026-10-21
- **Status:** approved — the owner chose the dependency, enforcement, strictness
  and approach decisions below and delegated the rest to the tech lead.
- **Goal:** make NEXTRACK a repo whose rules are executable, so future features
  can be built through the superpowers flow (brainstorm → spec → plan →
  subagent-driven development) with real tests and review gates.

## Problem

NEXTRACK's rules live only in prose: README schemas, the "genres are a graph" /
"pool, not a setlist" model, and the unwritten links between `graph.yml`, the
taxonomy, the Mermaid map, pools and blocks. On 2026-10-21 a manual audit found
six block bridges with no graph edge and eight edges missing from the Mermaid
map. The one script, `scripts/nextrack_tags.py`, edits the owner's audio files
and has no tests. Superpowers assumes a test command, an instruction file and
auto-detectable setup; the repo has none of them.

## Success criteria

1. `uv sync`, `uv run scripts/check_repo.py` and `uv run pytest` behave the same
   on the owner's machine, in a fresh worktree, for a subagent and in CI.
2. Every rule in "Validator rules" is enforced by `scripts/check_repo.py`, and
   the validator reports zero problems on the repo once this work lands.
3. `nextrack_tags.py`'s current behavior, including all three write paths
   (`clean-names`, `fix-tags`, `pull-bpm --apply`), is pinned by tests that
   need no committed audio.
4. `CLAUDE.md` gives any agent, including a subagent with no session history,
   the invariants, commands, change checklists and workflow conventions.
5. GitHub Actions runs the validator and the tests on every push and pull request.

## Non-goals

- No Python package (`nextrack/`). Revisit when a second feature needs the
  repo model; until then the loader lives inside `check_repo.py`.
- No machine-readable block bridges. That changes every block's schema and
  gets its own spec.
- No validation of `radios/` or `sets/` beyond link checking (neither has files yet).
- No behavior change to `nextrack_tags.py`. Only its "mutagen not installed"
  message changes, to mention `uv sync`.
- No pre-commit hook.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Dependencies | uv + `pyproject.toml` + committed `uv.lock` | One command set everywhere; no sudo, so agents and CI set themselves up. System Python is externally managed and has no pip. |
| Python | `.python-version` = 3.14, `requires-python >= 3.12` | CI runs the owner's interpreter version. |
| Enforcement | GitHub Actions on push + PR | Also catches direct commits to `main`; puts evidence on each PR. |
| Strictness | Every finding is an error; prose formats are documented | Drift is what we are preventing; all 5 existing blocks already follow the formats. |
| Approach | One validator script built from rule functions | Matches the `scripts/` one-CLI-per-file pattern; a rule plus its two tests is one plan task. |
| Unknown keys | Error, in graph nodes, edges, tracks and block front matter | Catches typos such as `artsit:`. A new field means updating the rule and the README in the same change. |
| Worktrees | `.worktrees/` (git-ignored), consent given in `CLAUDE.md` | Plan execution stays isolated from the owner's checkout; the audio library is outside the repo, so worktrees stay small. |

## 1. Tooling and layout

New files:

```
pyproject.toml          # dependencies + tool config only; not a package
uv.lock                 # committed
.python-version         # 3.14
CLAUDE.md
scripts/check_repo.py
tests/conftest.py
tests/test_check_repo.py
tests/test_nextrack_tags.py
.github/workflows/checks.yml
```

`pyproject.toml`:

- `[project]`: `name = "nextrack"`, `version = "0.1.0"`, `requires-python = ">=3.12"`,
  `dependencies = ["mutagen>=1.47", "pyyaml>=6.0"]`.
- `[dependency-groups] dev = ["pytest>=8"]`.
- `[tool.uv] package = false`.
- `[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["scripts"]`.
  Tests import `check_repo` and `nextrack_tags` directly; `scripts/` stays a plain folder.

`.gitignore` gains `.venv/` and `.worktrees/`.

Commands:

| Purpose | Command |
|---|---|
| Set up (once per checkout or worktree) | `uv sync` |
| Validate repo data | `uv run scripts/check_repo.py` |
| Run tests | `uv run pytest` |
| Library tool | `uv run scripts/nextrack_tags.py <cmd>` (plain `python3` still works with the apt packages) |

## 2. Validator — `scripts/check_repo.py`

### Interface

- CLI: `check_repo.py [--repo PATH]`. `--repo` defaults to the parent of `scripts/`.
- Output: one line per finding, `path:line: rule-id: message`. `path` is relative
  to the repo; `line` is 1-based, or `0` for a finding about a whole file.
  Findings are sorted by path, then line, then rule. The last line is
  `N problem(s)` or `ok: <nodes> nodes, <edges> edges, <tracks> tracks, <blocks> blocks`.
- Exit status: `0` when there are no findings, `1` when there are. Unreadable YAML or
  front matter is reported as a `parse-error` finding, never a traceback, and
  rules that depend on that file skip it.
- Python API: `check(root: Path) -> list[Finding]`, where `Finding` is a frozen
  dataclass `(path: str, line: int, rule: str, message: str)`. `RULES` is
  the ordered list of rule functions, each `(repo) -> Iterable[Finding]`.

### Structure

The file has two sections:

1. **Loader.** `load_repo(root) -> Repo` reads `genres/graph.yml`, `tracks/*.yml`,
   `blocks/*.md` (excluding `README.md`) and the Markdown files the rules need.
   YAML is parsed with a `yaml.SafeLoader` subclass that stores each mapping's
   1-based start line under the key `__line__`, so findings can name a line, including
   inside a single-line `{to: …}` edge. Rules ignore `__line__` when checking keys.
2. **Rules.** One function per rule, listed in `RULES`.

### Shared definitions

- **Node id:** matches `^[a-z0-9]+(-[a-z0-9]+)*$`.
- **Range `[a, b]`:** a two-item list of integers.
- **Camelot key:** matches `^(?:[1-9]|1[0-2])[AB]$`.
- **norm(s):** Unicode NFKD, drop combining marks, lowercase, replace each run of
  non-`[a-z0-9]` characters with one space, then strip.
- **core(title):** `norm` of the title after removing every `(...)` and `[...]` part.
- **artist tokens(a):** the words of `norm(a)`, minus the joiners
  `feat ft x e and com pres vs`.

### Validator rules

**Graph (`genres/graph.yml`)**

| Rule id | Requirement |
|---|---|
| `graph-node-schema` | Each node has `id`, `name`, `family`, `bpm`, `energy`, `neighbors`. It may also have `feel` and `subgenres` (lists of strings), and no other keys. `id` is a node id, `name` is a non-empty string, `family` is `brazilian` or `global`. `bpm` is a range of positive integers with min ≤ max. `energy` is a range within 1–10 with min ≤ max. `neighbors` is a list. |
| `graph-unique-ids` | No two nodes share an `id`. |
| `graph-edge-schema` | Each edge has exactly `to`, `strength` and `via`. `strength` is `strong`, `medium` or `weak`; `via` is a non-empty string. |
| `graph-edges-resolve` | `to` is an existing node id and is not the node's own id. A node has at most one edge to any given target. |
| `graph-node-connected` | Every node has at least one outgoing and one incoming edge, so no node is a dead end on the map. |

**Docs**

| Rule id | Requirement |
|---|---|
| `taxonomy-matches-graph` | Take every heading in `docs/taxonomy.md` that starts with `` ### `id` `` (text may follow, as in `` ### `brazilian-funk` — Funk ``). The set of those ids equals the set of node ids. Missing and leftover headings are both findings. |
| `mermaid-matches-graph` | Applies to the first ` ```mermaid ` block in `docs/genre-graph.md`. Each node declaration `ALIAS["id"]` names an existing node, and every node is declared exactly once. Edge lines use `A --- B` or `A -.-> B`, and every alias they use must be declared. Take each pair of nodes and the stronger of its two directions. If that is `strong` or `medium`, the pair is drawn exactly once. If it is `weak`, or the pair has no edge, it is not drawn. Strong pairs use solid `---` and medium pairs use dashed `-.->`. |
| `links-resolve` | In every `*.md` file, each relative Markdown link points to an existing path. Skip files whose path *relative to the repo root* has a component starting with `.` (the repo itself may live inside `.worktrees/`). Ignore fenced code blocks and inline code spans, and drop `#anchors`. Skip `http(s):` and `mailto:` links. |

**Pools (`tracks/*.yml`)**

| Rule id | Requirement |
|---|---|
| `pool-file-is-node` | The file's name (without `.yml`) is a node id that exists in the graph. |
| `track-schema` | Each entry has `title` and `artist` (non-empty strings), `genre`, `bpm` (null or an integer from 1 to 300), `key` (null or a Camelot key), `energy` (an integer from 1 to 10) and `status` (`to-download`, `downloaded` or `organized`). It may also have `remixer`, `duration`, `year`, `source`, `tags` (a list) and `notes`, and no other keys. `bpm` and `key` must be present even when null, because `nextrack_tags.py pull-bpm` fills them by editing their existing lines. |
| `track-genre-matches-pool` | `genre` equals the pool's file name. |
| `track-title-first` | Every entry starts with a line `- title:` at column 0. The number of such lines equals the number of entries. `nextrack_tags.py` finds entries by these lines. |
| `track-unique` | No two entries share `(norm(artist), norm(title))`, whether in the same pool or different pools. |

**Blocks (`blocks/*.md`, excluding `README.md`)**

| Rule id | Requirement |
|---|---|
| `block-frontmatter` | The file starts with a `---` front-matter block. It has exactly the keys `name`, `function`, `style`, `duration`, `genres`, `bpm`, `energy`, `key_journey` and `lightshow`. `function` is one of `warmup build peak plateau breakdown cooldown`. `style` is one of `continuous open-format hybrid`. `duration` matches `^\d+[mh]$`. `genres` is a non-empty list of existing node ids. `bpm` is a range of positive integers with min ≤ max. `energy` is a range within 1–10 read as start → end, so either order is allowed. `key_journey` is a string. `lightshow` is null, or a path relative to the block that exists. |
| `block-tracklist-resolves` | The block has a heading that starts with `## Tracklist`. In that section, every line that starts with `<digits>.` matches `^\d+\.\s+(?P<artist>.+?)\s+—\s+(?P<title>.+?)\s+·` (an em dash between artist and title, then a middle dot). Each line also matches at least one track in any pool. A track matches when its artist tokens and the line's artist tokens are subsets one way or the other, and its core title equals the line's core title or one starts with the other followed by a space. A line in the wrong format is a finding with the message prefix `format:`. A line with no match is a finding with the message prefix `unresolved:`. |
| `block-bridges-are-edges` | Look at each `` `token` `` in the sections whose headings start with `## Bridge in` and `## Bridge out`. A section runs until the next `## ` heading. Skip it if it isn't a node id or is one of the block's own `genres`. For **Bridge in**, there must be an edge from that token to one of the block's genres. For **Bridge out**, there must be an edge from one of the block's genres to the token. |

### Data fixes included in this work

- Remove the six duplicate Mermaid lines that `mermaid-matches-graph` will
  report: brazilian-funk–global-bass, brazilian-bass–tech-house,
  brazilian-bass–melodic-house-techno, afro-brasileiro–afro-house,
  afro-brasileiro–organic-house, mpb-bossa–samba-pagode.
- If the validator finds anything else in the real repo, fix the data, not the
  rule. The exception is a rule that contradicts a convention documented in a
  README; then the README wins, the rule is corrected, and the decision is
  recorded in the plan's ledger.

## 3. Tests

### Validator tests (`tests/test_check_repo.py`)

- `tests/conftest.py` provides a `mini_repo` fixture. It writes the smallest
  valid repo into `tmp_path`:
  - three nodes, connected so that every node has incoming and outgoing edges and the graph contains `strong`, `medium` and `weak` edges;
  - a matching `docs/taxonomy.md` and Mermaid block;
  - one pool;
  - one block with a tracklist, a Bridge in and a Bridge out.

  The fixture returns the repo path. Tests change one file and call `check()`.
- `test_mini_repo_is_clean`: the fixture produces zero findings.
- **For each rule:** at least one test that breaks exactly one thing and asserts
  that the rule's findings are exactly the expected `(path, line)` list. Other
  rules may also fire when a break cascades (for example, removing a node's
  only edge also disconnects it), so each test pins only its own rule. The
  clean-repo tests catch false positives from every rule. Rules with
  several clauses (for example `track-schema`) get one parameterized case per clause.
- `test_real_repo_is_clean`: `check(<repo root>)` returns no findings. This turns
  the whole repo into a test fixture.
- **CLI tests:** clean repo → exit 0 and an `ok:` summary; broken repo → exit 1,
  `path:line: rule-id: message` lines and `N problem(s)`; an unparseable YAML
  file → a `parse-error` finding with no traceback.
- **TDD:** each rule is written test-first. The failing test comes first and is run to watch it fail for the
  expected reason, then the rule is written.

### Library-tool tests (`tests/test_nextrack_tags.py`)

These are characterization tests: they pin current behavior and must pass
without changing `nextrack_tags.py`, apart from the mutagen hint. A test that
asserts nothing the code computes counts as a review finding.

- **Pure functions** (table-driven):
  - `clean_stem`: each junk pattern alone and combined, and that semantic `(Remix)` / `[Salsa Version]` parts are kept.
  - `parse_artist_title`, `normalize`.
  - `to_camelot`: all 24 keys, enharmonic spellings, `♯`/`♭`, Camelot passed through, invalid input → `None`.
  - `to_bpm`, `is_junk_title`, `is_junk_artist`, `strip_sitejunk`.
  - `_desired_tags` in both conservative and `--overwrite` mode.
  - `parse_pool`: line indices, quoted and unquoted values, comments.
- **Synthetic audio,** built inside `tmp_path`:
  - **MP3:** an empty file plus an ID3v2.4 tag (TIT2, TPE1, TBPM, TKEY), including a `GEOB:Serato Markers2` frame.
  - **FLAC:** a 42-byte file: `fLaC` plus one final 34-byte STREAMINFO block (44.1 kHz), with no audio frames.

  Both were checked against mutagen 1.47 on 2026-10-21.
- **Command tests,** calling `main([...])` with `--root` and `--tracks-dir` pointing into `tmp_path`:
  - The dry-run of each command changes no file, compared by bytes and modification time.
  - `clean-names --apply`: renames files, appends `_nextrack_rename_log.tsv`, and skips a file whose target name already exists.
  - `fix-tags --apply`:
    - fills missing or junk Title/Artist and keeps a good existing tag;
    - with `--overwrite`, the filename or YAML value wins;
    - the GEOB frame and ID3v2.4 survive;
    - FLAC `title`/`artist` are written;
    - WAV files are skipped.
  - `pull-bpm --apply`:
    - fills only `null` bpm/key, converting the key to Camelot;
    - keeps comments and entry order;
    - matches a pool entry when the file's artist adds collaborators and a version word;
    - leaves an ambiguous candidate unmatched.
  - **No root:** with `NEXTRACK_AUDIO_ROOT` unset and no `--root`, `SystemExit` is raised and its message names the variable.

## 4. CLAUDE.md and documentation

`CLAUDE.md` (repo root, concise) covers:

- **What NEXTRACK is,** and the Genre → Track → Block → Radio → Set hierarchy.
- **Invariants:**
  - genres are graph nodes, and edges say how to travel between them;
  - the catalog is an unordered pool, and order lives only in blocks, radios and sets;
  - audio is never committed;
  - ids are stable kebab-case;
  - one pool file per node, named after its id.
- **Commands:** the table in section 1. For the library tool: dry-run by default; `--apply` writes; edit tags with mutagen and never ffmpeg; `NEXTRACK_AUDIO_ROOT`.
- **Change checklists:**
  - Add or rename a node: update `graph.yml`, the taxonomy heading, the Mermaid declaration and its edges, and the pool file name.
  - Add or change an edge: update `graph.yml` and the Mermaid line.
  - Add tracks: `- title:` comes first; `bpm`/`key` stay null until analysed.
  - Add a block: use the documented tracklist and bridge formats; every bridge needs an edge.
  - Change `nextrack_tags.py`: tests first.
  - Add a validator rule: one function in `RULES`, tests for passing and failing cases, and the README that documents the schema.
- **Definition of done:** `uv run scripts/check_repo.py` and `uv run pytest` both pass, and CI is green.
- **Language:** block prose and pool comments are Portuguese (pt-BR). Ids, schema keys, graph `via`, `docs/`, code and commit messages are English.
- **Superpowers conventions:**
  - Specs go in `docs/superpowers/specs/`, plans in `docs/superpowers/plans/`.
  - Content work (new tracks, blocks or edges) needs no spec; the validator is its gate.
  - Script features and schema changes go brainstorm → spec → plan → subagent-driven development.
  - Worktrees live under `.worktrees/`, are allowed without asking, and get set up with `uv sync`.
  - Branches are named `feat/`, `fix/` or `chore/`. Work reaches `main` as a pull request merged with rebase.

Documentation updates:

- `blocks/README.md`: the two checked formats (tracklist line, backticked node ids in Bridge sections) and a pointer to the validator.
- `tracks/README.md`: `- title:` first; the allowed fields; `bpm`/`key` present even when null.
- `genres/README.md`, `docs/genre-graph.md` ("Growing the graph"): add steps for the taxonomy heading, the Mermaid line and the validator.
- `scripts/README.md`: install with `uv sync` (apt remains an alternative); a `check_repo.py` section listing the rule ids.
- `README.md`: list `CLAUDE.md`, `pyproject.toml` and `tests/` in the layout; mention validation in the quickstart.

## 5. CI — `.github/workflows/checks.yml`

- Triggers: `push` (all branches) and `pull_request`.
- One job on `ubuntu-latest`:
  1. `actions/checkout`
  2. `astral-sh/setup-uv`, pinned to the major tag of its latest release (look it up with `gh release view -R astral-sh/setup-uv`)
  3. `uv sync --locked`
  4. `uv run scripts/check_repo.py`
  5. `uv run pytest`
- `--locked` fails the job if dependencies change without an updated `uv.lock`.

## Risks

- **A prose rule rejects a new block format the owner prefers.** Change `blocks/README.md` and the rule in the same pull request; never loosen it silently.
- **The tracklist match is fuzzy (subset and prefix).** It can accept a wrong but similar track. That's acceptable, because the rule exists to catch missing tracks, not to pick the exact one.
- **`uv` is missing on a new machine.** `CLAUDE.md` gives the install command.
