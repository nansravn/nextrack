# NEXTRACK — agent instructions

## What this is

NEXTRACK is a documentation-first DJ "set planning as code" repo: Markdown and
YAML, plus one Python CLI (`scripts/nextrack_tags.py`) and a validator
(`scripts/check_repo.py`). It documents what the owner plays; the audio lives on
the owner's drive, outside the repo.

Hierarchy: **Genre** (graph node) → **Track** (pool entry) → **Block**
(time-boxed themed sequence) → **Radio** (program of blocks) → **Set** (full gig).
Start with [README.md](README.md); the `README.md` of each content folder
(`genres/`, `tracks/`, `blocks/`, `radios/`, `sets/`, `lightshows/`, `scripts/`)
holds its schema.

## Invariants

- Genres are graph nodes in `genres/graph.yml`; edges say how to travel between
  them. See [genres/README.md](genres/README.md).
- The catalog (`tracks/`) is an unordered pool. Order lives only in blocks,
  radios and sets.
- Audio is never committed. Tests create synthetic audio under `tmp_path` only.
- Ids are stable kebab-case: lowercase letters and digits joined by single `-`.
- One pool file per node, `tracks/<node-id>.yml`, and every entry's `genre` is
  that id.
- `graph.yml`, the taxonomy, the Mermaid map, pools and blocks reference each
  other. Their consistency is checked by `scripts/check_repo.py`, not by memory.

## Commands

Install uv once if it is missing: `curl -LsSf https://astral.sh/uv/install.sh | sh`

| Purpose | Command |
|---|---|
| Set up (once per checkout or worktree) | `uv sync` |
| Validate repo data | `uv run scripts/check_repo.py` |
| Run tests | `uv run pytest` |
| Library tool | `uv run scripts/nextrack_tags.py <cmd>` |

`pyproject.toml` exists, so setup is `uv sync`. Do not use poetry or pip; the
system Python is externally managed.

Library tool (`audit`, `clean-names`, `fix-tags`, `pull-bpm`; see
[scripts/README.md](scripts/README.md)):

- Dry-run by default. Only `--apply` writes.
- Edit tags with mutagen, never ffmpeg: ffmpeg re-muxes and drops Serato
  beatgrids and cues.
- The audio library root comes from `--root` or `NEXTRACK_AUDIO_ROOT`; one of the
  two is required. Never hard-code a machine path.
- `pull-bpm --apply` edits the `bpm`/`key` lines of `tracks/*.yml` in place.
  Review it with `git diff tracks`.

## Change checklists

- **Add or rename a node:** `genres/graph.yml` (node and edges in both
  directions where the return trip differs), the `` ### `id` `` heading in
  [docs/taxonomy.md](docs/taxonomy.md), the declaration and edges in the Mermaid
  map in [docs/genre-graph.md](docs/genre-graph.md), and the pool file name.
- **Add or change an edge:** `graph.yml` and the Mermaid line together.
  `strong` is drawn solid (`---`), `medium` dashed (`-.->`), `weak` not at all.
- **Add tracks:** each entry starts with `- title:` at column 0 (the library tool
  finds entries by that line). Keep `bpm` and `key` as `null` until analysed;
  `pull-bpm` fills them. Schema: [tracks/README.md](tracks/README.md).
- **Add a block:** copy the template in [blocks/README.md](blocks/README.md).
  Tracklist lines read `N. Artist — Title  · key · bpm · eN` and each must match
  a track in a pool. Every backticked node id in `## Bridge in` / `## Bridge out`
  needs a graph edge.
- **Change `nextrack_tags.py`:** write or update the test first. Its tests pin
  current behavior, including the three write paths.
- **Add a validator rule:** one function in `RULES`, tests for the passing and
  the failing case, and the README that documents the schema, in the same change.
  Add its row to the rule table in [scripts/README.md](scripts/README.md);
  `tests/test_tooling.py` fails without it. A rule, or a clause of one, that reads
  node ids or edges must return nothing when `repo.graph_ok` is False, so a broken
  graph is reported once, as a `parse-error`. If a rule contradicts a documented
  convention, the README wins: fix the rule.

## Definition of done

`uv run scripts/check_repo.py` and `uv run pytest` both pass, and CI is green.
Run both before saying work is complete, and report the real output.
A finding in the real repo means fixing the data, not loosening the rule.

## Language

- pt-BR: block prose and pool comments.
- English: ids, schema keys, graph `via`, `docs/`, code and commit messages.

## Superpowers workflow

- Specs go in `docs/superpowers/specs/`, plans in `docs/superpowers/plans/`.
- Content work (new tracks, blocks or edges) needs no spec; the validator is the
  gate.
- Script features and schema changes go brainstorm → spec → plan →
  subagent-driven development.
- Execute plans in a worktree. Creating one is allowed without asking.
  Prefer the native `EnterWorktree` tool: it places worktrees under
  `.claude/worktrees/` and branches from `origin/main`. Enter it before writing
  the spec, so spec, plan and code share one branch. Manual fallback:
  `git worktree add .worktrees/<name> -b <branch>` (`.worktrees/` is git-ignored).
  Run `uv sync` in every fresh worktree.
- Branches are named `feat/`, `fix/` or `chore/`. Commit subjects are imperative
  English sentences (`Add …`, `Fix …`) with no `feat:` prefix.
- Work reaches `main` as a pull request merged with rebase.
