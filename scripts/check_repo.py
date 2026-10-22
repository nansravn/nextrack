#!/usr/bin/env python3
"""check_repo.py — verify that the NEXTRACK repo agrees with itself.

`genres/graph.yml`, the taxonomy, the Mermaid map, the track pools and the blocks
all refer to each other. This script loads them and reports every place where
they disagree, so the consistency is checked by a program rather than by memory.

Usage:  uv run scripts/check_repo.py [--repo PATH]

Output is one line per finding, `path:line: rule-id: message`, sorted by path,
line and rule. `path` is relative to the repo; `line` is 1-based, or 0 for a
finding about a whole file. The last line is `N problem(s)` or
`ok: <nodes> nodes, <edges> edges, <tracks> tracks, <blocks> blocks`. The exit
status is 0 when the repo is clean and 1 when there are findings. A file that
cannot be read or parsed is a `parse-error` finding, never a traceback, and the
rules skip what depends on it.

The file has two sections: the loader, which turns the repo into plain data and
knows no rules, and the rules, each one a function registered with `@rule`.
Python API: `check(root) -> list[Finding]`.
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit(
        "pyyaml not installed.\n"
        "  Run:  uv sync   (then: uv run scripts/check_repo.py)\n"
        "  Or:   sudo apt-get install -y python3-yaml"
    )

GRAPH_PATH = "genres/graph.yml"

# --------------------------------------------------------------------- loader --


@dataclass(frozen=True, order=True)
class Finding:
    """One problem. Ordering is by path, then line, then rule."""

    path: str
    line: int
    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.message}"


@dataclass
class Pool:
    """A `tracks/<stem>.yml` file: its text and its entries (all mappings)."""

    path: str
    stem: str
    text: str
    entries: list[dict]


@dataclass
class Block:
    """A `blocks/*.md` file split into front matter and body.

    `body` holds `(1-based line, text)` for the lines after the front matter, or
    for every line when there is none. `front` is None when the front matter is
    missing or failed to parse (`has_front` tells the two apart); an unclosed
    front matter has an empty `body`.
    """

    path: str
    text: str
    has_front: bool
    front: dict | None
    body: list[tuple[int, str]]


@dataclass
class Repo:
    """Everything the rules need, loaded once.

    `graph_ok` is False when `genres/graph.yml` is missing or failed to parse, or
    when its top level is not a mapping with a `nodes` list of mappings; `nodes`
    is then empty. Every rule, or rule clause, that reads node ids or edges must
    yield nothing when `graph_ok` is False, so that a broken graph is reported
    once, as a `parse-error`, and not again as a flood of dangling references.

    A pool that fails to parse is reported in `errors` and left out of `pools`. A
    block that fails to parse is kept, with `front` set to None.

    `errors` holds the loader's `parse-error` findings; `check` adds them to
    those of the rules.
    """

    root: Path
    nodes: list[dict]
    pools: list[Pool]
    blocks: list[Block]
    errors: list[Finding]
    graph_ok: bool = True

    def node_ids(self) -> set[str]:
        return {n["id"] for n in self.nodes if isinstance(n.get("id"), str)}

    def edges(self) -> list[tuple[str, dict]]:
        """`(from_id, edge)` for every well-formed edge.

        Skips a node without a string `id`, a node whose `neighbors` is not a
        list, and any edge that is not a mapping.
        """
        found = []
        for node in self.nodes:
            from_id, neighbors = node.get("id"), node.get("neighbors")
            if not isinstance(from_id, str) or not isinstance(neighbors, list):
                continue
            found.extend((from_id, e) for e in neighbors if isinstance(e, dict))
        return found


def read_text(path: Path) -> str:
    """Read a repo text file as UTF-8, with `\\r\\n` turned into `\\n`."""
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


class _LineLoader(yaml.SafeLoader):
    """A SafeLoader that stores where each mapping starts under `__line__`.

    It also reports a value PyYAML cannot build (`!!int ""`, `2024-13-45`) as a
    `yaml.YAMLError` at that value's position, whatever exception PyYAML raised.
    """

    first_line = 1

    def construct_object(self, node, deep=False):
        try:
            return super().construct_object(node, deep=deep)
        except yaml.YAMLError:
            raise
        except Exception as exc:
            problem = f"cannot construct {node.tag} ({type(exc).__name__}: {exc})"
            raise yaml.constructor.ConstructorError(None, None, problem, node.start_mark) from exc

    def construct_mapping(self, node, deep=False):
        mapping = super().construct_mapping(node, deep=True)
        mapping["__line__"] = node.start_mark.line + self.first_line
        return mapping


def load_yaml(text: str, first_line: int = 1) -> object:
    """Parse YAML; every mapping gets `__line__`, the file line it starts on.

    `first_line` is the file line that `text` starts at: 1 for a whole file, 2
    for the front matter of a block. Raises `yaml.YAMLError`.
    """
    loader = _LineLoader(text)
    loader.first_line = first_line
    try:
        return loader.get_single_data()
    except RecursionError as exc:  # absurdly deep nesting fails in the parser
        raise yaml.YAMLError("nested too deeply") from exc
    finally:
        loader.dispose()


class _LoadError(Exception):
    """A file could not be loaded; carries the `parse-error` finding for it."""

    def __init__(self, path: str, line: int, message: str):
        super().__init__(message)
        self.finding = Finding(path, line, "parse-error", message)


def _lines(text: str) -> list[str]:
    """Split on `\\n` only, as editors count lines, with no phantom last line."""
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    return lines


def _read(root: Path, rel: str) -> str:
    path = root / rel
    if not path.is_file():
        raise _LoadError(rel, 0, f"missing file {rel}")
    try:
        return read_text(path)
    except UnicodeDecodeError:
        raise _LoadError(rel, 0, "not valid UTF-8") from None
    except OSError as exc:
        raise _LoadError(rel, 0, f"cannot read file: {exc.strerror}") from None


def _parse(rel: str, text: str, first_line: int = 1) -> object:
    try:
        return load_yaml(text, first_line)
    except yaml.YAMLError as exc:
        # Point at where the parser noticed the problem, but never past the end.
        mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
        last = first_line + max(len(_lines(text)) - 1, 0)
        line = min(mark.line + first_line, last) if mark else 0
        parts = (getattr(exc, "context", None), getattr(exc, "problem", None))
        detail = "; ".join(p for p in parts if p) or str(exc)
        raise _LoadError(rel, line, "invalid YAML: " + " ".join(detail.split())) from None


def _load_graph(root: Path, errors: list[Finding]) -> tuple[list[dict], bool]:
    try:
        data = _parse(GRAPH_PATH, _read(root, GRAPH_PATH))
        nodes = data.get("nodes") if isinstance(data, dict) else None
        if not isinstance(nodes, list) or not all(isinstance(n, dict) for n in nodes):
            raise _LoadError(GRAPH_PATH, 0, "expected a mapping with a `nodes` list of mappings")
    except _LoadError as exc:
        errors.append(exc.finding)
        return [], False
    return nodes, True


def _load_pools(root: Path, errors: list[Finding]) -> list[Pool]:
    pools = []
    for path in sorted((root / "tracks").glob("*.yml")):
        rel = path.relative_to(root).as_posix()
        try:
            text = _read(root, rel)
            entries = _parse(rel, text)
            if entries is None:  # only comments: a node with no tracks yet
                entries = []
            if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
                raise _LoadError(rel, 0, "expected a list of mappings")
        except _LoadError as exc:
            errors.append(exc.finding)
            continue
        pools.append(Pool(rel, path.stem, text, entries))
    return pools


def _split_block(rel: str, text: str, errors: list[Finding]) -> Block:
    lines = _lines(text)
    if not text.startswith("---\n"):
        return Block(rel, text, False, None, list(enumerate(lines, 1)))
    close = next((i for i in range(1, len(lines)) if lines[i] == "---"), None)
    if close is None:
        errors.append(Finding(rel, 0, "parse-error", "unclosed front matter: no closing `---`"))
        return Block(rel, text, True, None, [])
    body = list(enumerate(lines[close + 1 :], close + 2))
    try:
        front = _parse(rel, "\n".join(lines[1:close]) + "\n", first_line=2)
        if not isinstance(front, dict):
            raise _LoadError(rel, 0, "front matter must be a mapping")
    except _LoadError as exc:
        errors.append(exc.finding)
        front = None
    return Block(rel, text, True, front, body)


def _load_blocks(root: Path, errors: list[Finding]) -> list[Block]:
    blocks = []
    for path in sorted((root / "blocks").glob("*.md")):
        if path.name == "README.md":
            continue
        rel = path.relative_to(root).as_posix()
        try:
            text = _read(root, rel)
        except _LoadError as exc:
            errors.append(exc.finding)
            continue
        blocks.append(_split_block(rel, text, errors))
    return blocks


def load_repo(root: Path) -> Repo:
    """Load the graph, the pools and the blocks. Never raises on bad content."""
    errors: list[Finding] = []
    nodes, graph_ok = _load_graph(root, errors)
    pools = _load_pools(root, errors)
    blocks = _load_blocks(root, errors)
    return Repo(root, nodes, pools, blocks, errors, graph_ok)


# ---------------------------------------------------------------------- rules --

RULES: list[Callable[[Repo], Iterable[Finding]]] = []


def rule(rule_id: str):
    """Register a rule function `(repo) -> Iterable[Finding]` under `rule_id`."""

    def register(fn):
        fn.rule_id = rule_id
        RULES.append(fn)
        return fn

    return register


def norm(s: str | None) -> str:
    """Fold case, accents and punctuation: `Dançarina (Ao Vivo)` -> `dancarina ao vivo`.

    Anything that is not a string (None, or a wrong YAML type) gives `""`.
    """
    if not isinstance(s, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", s)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", plain.lower()).strip()


def is_int(v) -> bool:
    """An int that is not a bool (`isinstance(True, int)` is true in Python)."""
    return isinstance(v, int) and not isinstance(v, bool)


def is_range(v, lo: int | None = None, hi: int | None = None, ordered: bool = True) -> bool:
    """A two-item list of ints within `[lo, hi]`, with min <= max when `ordered`."""
    if not isinstance(v, list) or len(v) != 2 or not all(is_int(x) for x in v):
        return False
    if lo is not None and min(v) < lo:
        return False
    if hi is not None and max(v) > hi:
        return False
    return not ordered or v[0] <= v[1]


# ------------------------------------------------------------------------ run --


def _run(repo: Repo) -> list[Finding]:
    findings = list(repo.errors)
    for check_rule in RULES:
        findings.extend(check_rule(repo))
    return sorted(findings)


def check(root: Path) -> list[Finding]:
    """Every finding for the repo at `root`, sorted by path, line and rule."""
    return _run(load_repo(root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that graph.yml, the docs, the pools and the blocks agree."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repo root (default: the parent of scripts/)",
    )
    args = parser.parse_args(argv)

    repo = load_repo(args.repo)
    findings = _run(repo)
    for finding in findings:
        print(finding)
    if findings:
        print(f"{len(findings)} problem(s)")
        return 1
    tracks = sum(len(pool.entries) for pool in repo.pools)
    print(
        f"ok: {len(repo.nodes)} nodes, {len(repo.edges())} edges, "
        f"{tracks} tracks, {len(repo.blocks)} blocks"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
