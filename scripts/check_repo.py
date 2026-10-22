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
import os
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
    except yaml.YAMLError:
        raise
    except Exception as exc:
        # PyYAML's scanner and parser can raise a bare ValueError (`"\UFFFFFFFF"`) or
        # RecursionError (absurd nesting) outside construct_object.
        raise yaml.YAMLError(str(exc)) from exc
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


NODE_ID_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def is_node_id(v) -> bool:
    """A kebab-case node id: lowercase letters and digits joined by single `-`."""
    return isinstance(v, str) and NODE_ID_RE.fullmatch(v) is not None


def _show(v) -> str:
    """`repr(v)` for a message, without the loader's `__line__` bookkeeping."""
    return "a mapping" if isinstance(v, dict) else repr(v)


# ---- graph (genres/graph.yml) ----
#
# Findings point at the node's `__line__`, or the edge's. A node whose `neighbors`
# is not a list, and an edge that is not a mapping, are reported once by the schema
# rules; the other graph rules skip them so that one mistake is not reported twice.

NODE_REQUIRED = ("id", "name", "family", "bpm", "energy", "neighbors")
NODE_OPTIONAL = ("feel", "subgenres")
FAMILIES = ("brazilian", "global")
EDGE_KEYS = ("to", "strength", "via")
STRENGTHS = ("strong", "medium", "weak")


def _graph_finding(rule_id: str, line: int, message: str) -> Finding:
    return Finding(GRAPH_PATH, line, rule_id, message)


def _key_problems(
    mapping: dict, allowed: tuple[str, ...], required: tuple[str, ...]
) -> Iterable[str]:
    """Messages for each required key `mapping` lacks and each key not in `allowed`."""
    for key in required:
        if key not in mapping:
            yield f"missing key {key!r}"
    for key in mapping:
        if key != "__line__" and key not in allowed:
            yield f"unknown key {key!r}"


def _node_problems(node: dict) -> Iterable[str]:
    yield from _key_problems(node, NODE_REQUIRED + NODE_OPTIONAL, NODE_REQUIRED)
    if "id" in node and not is_node_id(node["id"]):
        yield f"id {_show(node['id'])} is not a kebab-case node id"
    if "name" in node and not (isinstance(node["name"], str) and node["name"]):
        yield f"name {_show(node['name'])} is not a non-empty string"
    if "family" in node and node["family"] not in FAMILIES:
        yield f"family {_show(node['family'])} is not 'brazilian' or 'global'"
    if "bpm" in node and not is_range(node["bpm"], lo=1):
        yield f"bpm {_show(node['bpm'])} is not [min, max] of positive integers with min <= max"
    if "energy" in node and not is_range(node["energy"], lo=1, hi=10):
        yield f"energy {_show(node['energy'])} is not [min, max] within 1-10 with min <= max"
    if "neighbors" in node and not isinstance(node["neighbors"], list):
        yield f"neighbors {_show(node['neighbors'])} is not a list"
    for key in NODE_OPTIONAL:
        value = node.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            yield f"{key} {_show(value)} is not a list of strings"


def _edge_problems(edge: dict) -> Iterable[str]:
    yield from _key_problems(edge, EDGE_KEYS, EDGE_KEYS)
    if "strength" in edge and edge["strength"] not in STRENGTHS:
        yield f"strength {_show(edge['strength'])} is not 'strong', 'medium' or 'weak'"
    if "via" in edge and not (isinstance(edge["via"], str) and edge["via"]):
        yield f"via {_show(edge['via'])} is not a non-empty string"


def _edges_of(node: dict) -> list[dict]:
    """The well-formed edges of one node. Unlike `Repo.edges`, a node with a bad `id`
    keeps them, so the edge rules still check what it points at."""
    neighbors = node.get("neighbors")
    return [e for e in neighbors if isinstance(e, dict)] if isinstance(neighbors, list) else []


@rule("graph-node-schema")
def graph_node_schema(repo: Repo) -> Iterable[Finding]:
    if not repo.graph_ok:
        return
    for node in repo.nodes:
        for problem in _node_problems(node):
            yield _graph_finding("graph-node-schema", node["__line__"], problem)


@rule("graph-unique-ids")
def graph_unique_ids(repo: Repo) -> Iterable[Finding]:
    if not repo.graph_ok:
        return
    first_line: dict[str, int] = {}
    for node in repo.nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str):
            continue  # graph-node-schema reports it
        if node_id not in first_line:
            first_line[node_id] = node["__line__"]
            continue
        yield _graph_finding(
            "graph-unique-ids",
            node["__line__"],
            f"duplicate id {node_id!r} (first defined on line {first_line[node_id]})",
        )


@rule("graph-edge-schema")
def graph_edge_schema(repo: Repo) -> Iterable[Finding]:
    if not repo.graph_ok:
        return
    for node in repo.nodes:
        neighbors = node.get("neighbors")
        if not isinstance(neighbors, list):
            continue  # graph-node-schema reports it
        for edge in neighbors:
            if not isinstance(edge, dict):
                # A scalar has no line of its own, so point at its node.
                message = f"edge {_show(edge)} is not a mapping with to, strength and via"
                yield _graph_finding("graph-edge-schema", node["__line__"], message)
                continue
            for problem in _edge_problems(edge):
                yield _graph_finding("graph-edge-schema", edge["__line__"], problem)


@rule("graph-edges-resolve")
def graph_edges_resolve(repo: Repo) -> Iterable[Finding]:
    if not repo.graph_ok:
        return
    ids = repo.node_ids()
    for node in repo.nodes:
        from_id = node.get("id")
        seen: set[str] = set()
        for edge in _edges_of(node):
            if "to" not in edge:
                continue  # graph-edge-schema reports it
            target = edge["to"]
            # `target` may be any YAML value: test it as a string before any set lookup.
            if not isinstance(target, str) or target not in ids:
                message = f"edge to unknown node {_show(target)}"
            elif target == from_id:
                message = f"edge from {from_id!r} to itself"
            elif target in seen:
                message = f"second edge to {target!r}"
            else:
                seen.add(target)
                continue
            yield _graph_finding("graph-edges-resolve", edge["__line__"], message)


@rule("graph-node-connected")
def graph_node_connected(repo: Repo) -> Iterable[Finding]:
    """Every node has an edge out to, and an edge in from, another existing node.

    A self edge or an edge to an unknown node leads nowhere, so it does not count;
    that is a dead end the map would show, even if graph-edges-resolve also
    reports the edge.
    """
    if not repo.graph_ok:
        return
    ids = repo.node_ids()
    leads_to: list[tuple[dict, set[str]]] = []
    reached: set[str] = set()
    for node in repo.nodes:
        from_id = node.get("id")
        if not isinstance(from_id, str):
            continue  # graph-node-schema reports it
        targets = {
            e["to"]
            for e in _edges_of(node)
            if isinstance(e.get("to"), str) and e["to"] in ids and e["to"] != from_id
        }
        leads_to.append((node, targets))
        reached |= targets
    for node, targets in leads_to:
        if not targets:
            message = f"node {node['id']!r} has no outgoing edge to another node"
            yield _graph_finding("graph-node-connected", node["__line__"], message)
        if node["id"] not in reached:
            message = f"node {node['id']!r} has no incoming edge from another node"
            yield _graph_finding("graph-node-connected", node["__line__"], message)


# ---- docs (Markdown) ----
#
# These rules read their Markdown files themselves: the loader only protects the
# graph, the pools and the blocks. A file that is missing or not UTF-8 gives the
# loader's `parse-error`, and `_run` keeps one copy when two rules report the same
# file. `taxonomy-matches-graph` and `mermaid-matches-graph` read node ids and
# edges, so they yield nothing when `graph_ok` is False.

TAXONOMY_PATH = "docs/taxonomy.md"
MAP_PATH = "docs/genre-graph.md"


def _doc(repo: Repo, rel: str) -> str | Finding:
    """The text of a Markdown file, or the `parse-error` finding that says why not."""
    try:
        return _read(repo.root, rel)
    except _LoadError as exc:
        return exc.finding


@dataclass
class _Fence:
    """A fenced code block: `start` is the index of its opening line and `end` the
    index of its closing line, or `len(lines)` when it is never closed."""

    start: int
    end: int
    info: str


FENCE_OPEN_RE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)")
FENCE_CLOSE_RE = re.compile(r" {0,3}(`{3,}|~{3,})[ \t]*")
CODE_SPAN_RE = re.compile(r"(?<!`)(`+)(?!`)(?:(?!\n[ \t]*\n).)*?(?<!`)\1(?!`)", re.DOTALL)


def _fences(lines: list[str]) -> list[_Fence]:
    """The fenced code blocks of a Markdown file, as CommonMark reads them.

    A fence opens on a line that starts, after up to three spaces, with three or
    more backticks or tildes; the info string of a backtick fence cannot contain a
    backtick. It closes on a line of at least as many of the same character and
    nothing else, so a shorter fence inside a longer one is just text.
    """
    found = []
    i = 0
    while i < len(lines):
        opened = FENCE_OPEN_RE.fullmatch(lines[i])
        if opened is None or (opened[1][0] == "`" and "`" in opened[2]):
            i += 1
            continue
        mark = opened[1]
        end = i + 1
        while end < len(lines):
            closed = FENCE_CLOSE_RE.fullmatch(lines[end])
            if closed and closed[1][0] == mark[0] and len(closed[1]) >= len(mark):
                break
            end += 1
        found.append(_Fence(i, end, opened[2].strip()))
        i = end + 1
    return found


def _outside_fences(text: str) -> list[str]:
    """The lines of `text`, with those of fenced code blocks emptied (same line count)."""
    lines = text.split("\n")
    for fence in _fences(lines):
        span = slice(fence.start, fence.end + 1)
        lines[span] = [""] * len(lines[span])
    return lines


def _without_code(text: str) -> str:
    """`text` with fenced code blocks and inline code spans blanked out.

    An inline span is a run of N backticks up to the next run of exactly N, within
    one paragraph. Newlines stay, so a line number in the result is the file's.
    """
    text = "\n".join(_outside_fences(text))
    return CODE_SPAN_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text)


# taxonomy-matches-graph

TAXONOMY_HEADING_RE = re.compile(r"###[ \t]+`([^`]+)`")


@rule("taxonomy-matches-graph")
def taxonomy_matches_graph(repo: Repo) -> Iterable[Finding]:
    """The `### `id`` headings of the taxonomy are exactly the node ids."""
    if not repo.graph_ok:
        return
    text = _doc(repo, TAXONOMY_PATH)
    if isinstance(text, Finding):
        yield text
        return
    ids = repo.node_ids()
    headings: set[str] = set()
    for number, line in enumerate(_outside_fences(text), 1):
        heading = TAXONOMY_HEADING_RE.match(line)
        if heading is None:
            continue
        headings.add(heading[1])
        if heading[1] not in ids:
            message = f"heading for {heading[1]!r} has no node in graph.yml"
            yield Finding(TAXONOMY_PATH, number, "taxonomy-matches-graph", message)
    for node_id in sorted(ids - headings):
        message = f"node {node_id!r} has no ### `{node_id}` heading"
        yield Finding(TAXONOMY_PATH, 0, "taxonomy-matches-graph", message)


# mermaid-matches-graph

MERMAID_DECL_RE = re.compile(r'^\s*(\w+)\["([^"]+)"\]\s*$')
MERMAID_EDGE_RE = re.compile(r"^\s*(\w+)\s+(---|-\.->)\s+(\w+)\s*$")
MERMAID_STYLE = {"strong": "---", "medium": "-.->"}  # weak edges are not drawn


def _strongest_pairs(repo: Repo) -> dict[tuple[str, str], str]:
    """The strongest `strength` in either direction, for each pair of distinct nodes.

    Skips an edge to an unknown node, a self edge and an invalid `strength`: the
    graph rules report those.
    """
    ids = repo.node_ids()
    best: dict[tuple[str, str], str] = {}
    for from_id, edge in repo.edges():
        target, strength = edge.get("to"), edge.get("strength")
        if not isinstance(target, str) or target not in ids or target == from_id:
            continue
        if strength not in STRENGTHS:  # a tuple test: `strength` may be unhashable
            continue
        pair = (min(from_id, target), max(from_id, target))
        if pair not in best or STRENGTHS.index(strength) < STRENGTHS.index(best[pair]):
            best[pair] = strength
    return best


@rule("mermaid-matches-graph")
def mermaid_matches_graph(repo: Repo) -> Iterable[Finding]:
    """The first ```mermaid block of the genre map draws exactly the graph."""
    if not repo.graph_ok:
        return
    text = _doc(repo, MAP_PATH)
    if isinstance(text, Finding):
        yield text
        return

    def found(line: int, message: str) -> Finding:
        return Finding(MAP_PATH, line, "mermaid-matches-graph", message)

    lines = text.split("\n")
    block = next((f for f in _fences(lines) if f.info.split()[:1] == ["mermaid"]), None)
    if block is None:
        yield found(0, "no ```mermaid block")
        return
    fence_line = block.start + 1
    body = list(enumerate(lines[block.start + 1 : block.end], block.start + 2))
    ids = repo.node_ids()

    # Declarations first, so that an edge may come before the node it uses.
    aliases: dict[str, tuple[str, int]] = {}  # alias -> (node id, declaration line)
    declared: dict[str, int] = {}  # node id -> first declaration line
    for number, line in body:
        decl = MERMAID_DECL_RE.match(line)
        if decl is None:
            continue
        alias, node_id = decl.groups()
        if alias in aliases:
            first = aliases[alias][1]
            yield found(number, f"alias {alias!r} is declared again (first on line {first})")
            continue
        aliases[alias] = (node_id, number)
        if node_id not in ids:
            yield found(number, f"declares unknown node {node_id!r}")
        elif node_id in declared:
            first = declared[node_id]
            yield found(number, f"node {node_id!r} is declared again (first on line {first})")
        else:
            declared[node_id] = number
    for node_id in sorted(ids.difference(declared)):
        yield found(fence_line, f"node {node_id!r} is not declared in the map")

    drawn: dict[tuple[str, str], list[tuple[int, str]]] = {}  # pair -> [(line, style)]
    for number, line in body:
        edge = MERMAID_EDGE_RE.match(line)
        if edge is None:
            continue
        left, style, right = edge.groups()
        undeclared = [a for a in dict.fromkeys((left, right)) if a not in aliases]
        for alias in undeclared:
            yield found(number, f"edge uses alias {alias!r}, which is not declared")
        ends = [aliases[a][0] for a in (left, right)] if not undeclared else []
        if ends and all(node_id in ids for node_id in ends):  # else reported at its declaration
            drawn.setdefault((min(ends), max(ends)), []).append((number, style))

    best = _strongest_pairs(repo)
    for pair in sorted(best.keys() | drawn.keys()):
        names = f"{pair[0]!r} and {pair[1]!r}"
        strength = best.get(pair)
        style = MERMAID_STYLE.get(strength)
        draws = drawn.get(pair, [])
        if style is None:
            reason = "only a weak edge" if strength == "weak" else "no edge"
            for number, _ in draws:
                yield found(number, f"{names} have {reason} in graph.yml, so they are not drawn")
        elif not draws:
            message = f"{names} have a {strength} edge but are not drawn: add a `{style}` line"
            yield found(fence_line, message)
        else:
            (first, first_style), later = draws[0], draws[1:]
            if first_style != style:
                message = f"{names} have a {strength} edge: draw `{style}`, not `{first_style}`"
                yield found(first, message)
            for number, _ in later:
                yield found(number, f"{names} are already drawn on line {first}")


# links-resolve

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
URL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:")


def _markdown_files(root: Path) -> list[Path]:
    """Every `*.md` file under `root` except those with a dot component in their
    path relative to `root`. Dot-skipping starts below `root`, because the repo may
    itself live in a dot directory (`.worktrees/x`)."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            path = Path(dirpath, name)
            if name.endswith(".md") and not name.startswith(".") and path.is_file():
                found.append(path)
    return found


@rule("links-resolve")
def links_resolve(repo: Repo) -> Iterable[Finding]:
    """Every relative link in every Markdown file points at a path that exists.

    Links inside fenced code and inline code spans are ignored, `#anchor`s are
    dropped, and so are URLs (`https:`, `mailto:`, `//host/…`). A target starting
    with `/` is relative to the repo root, as on GitHub.
    """
    for path in _markdown_files(repo.root):
        rel = path.relative_to(repo.root).as_posix()
        text = _doc(repo, rel)
        if isinstance(text, Finding):
            yield text
            continue
        prose = _without_code(text)
        for link in LINK_RE.finditer(prose):
            target = link[1].split("#", 1)[0]
            if not target or URL_SCHEME_RE.match(target) or target.startswith("//"):
                continue
            base = repo.root if target.startswith("/") else path.parent
            if not os.path.exists(base / target.lstrip("/")):  # False on any OS error
                line = prose.count("\n", 0, link.start(1)) + 1
                yield Finding(rel, line, "links-resolve", f"link to {link[1]!r} does not exist")


# ---- pools (tracks/*.yml) ----
#
# Entry findings point at the entry's `__line__`, the line of its first key, which
# is its `- title:` line in a well-formed pool; findings about a whole file use line
# 0. Only `pool-file-is-node` reads node ids, so only it yields nothing when
# `graph_ok` is False. A pool that did not parse is not in `repo.pools`; the loader
# reported it. The loader keeps only pools of mappings, but the rules do not rely on
# it: a bare value in a list of entries is a `track-schema` finding, never a crash.

TRACK_REQUIRED = ("title", "artist", "genre", "bpm", "key", "energy", "status")
TRACK_OPTIONAL = ("remixer", "duration", "year", "source", "tags", "notes")
STATUSES = ("to-download", "downloaded", "organized")
CAMELOT_RE = re.compile(r"(?:[1-9]|1[0-2])[AB]")
ENTRY_START = "- title:"


def _pool_finding(pool: Pool, line: int, rule_id: str, message: str) -> Finding:
    return Finding(pool.path, line, rule_id, message)


def _mappings(pool: Pool) -> list[dict]:
    """The entries of `pool` that are mappings, the only ones with a `__line__`."""
    return [entry for entry in pool.entries if isinstance(entry, dict)]


def _is_int_within(v, lo: int, hi: int) -> bool:
    return is_int(v) and lo <= v <= hi


def _track_problems(entry: dict) -> Iterable[str]:
    yield from _key_problems(entry, TRACK_REQUIRED + TRACK_OPTIONAL, TRACK_REQUIRED)
    for key in ("title", "artist"):
        if key in entry and not (isinstance(entry[key], str) and entry[key]):
            yield f"{key} {_show(entry[key])} is not a non-empty string"
    if "bpm" in entry and not (entry["bpm"] is None or _is_int_within(entry["bpm"], 1, 300)):
        yield f"bpm {_show(entry['bpm'])} is not null or an integer from 1 to 300"
    if "key" in entry and not (
        entry["key"] is None
        or (isinstance(entry["key"], str) and CAMELOT_RE.fullmatch(entry["key"]))
    ):
        yield f"key {_show(entry['key'])} is not null or a Camelot key such as 8A or 12B"
    if "energy" in entry and not _is_int_within(entry["energy"], 1, 10):
        yield f"energy {_show(entry['energy'])} is not an integer from 1 to 10"
    if "status" in entry and entry["status"] not in STATUSES:  # a tuple test: may be unhashable
        yield f"status {_show(entry['status'])} is not 'to-download', 'downloaded' or 'organized'"
    if "tags" in entry and not isinstance(entry["tags"], list):
        yield f"tags {_show(entry['tags'])} is not a list"


@rule("pool-file-is-node")
def pool_file_is_node(repo: Repo) -> Iterable[Finding]:
    if not repo.graph_ok:
        return
    ids = repo.node_ids()
    for pool in repo.pools:
        if pool.stem not in ids:
            message = f"{pool.stem!r} is not a node id in {GRAPH_PATH}"
            yield _pool_finding(pool, 0, "pool-file-is-node", message)


@rule("track-schema")
def track_schema(repo: Repo) -> Iterable[Finding]:
    for pool in repo.pools:
        for entry in pool.entries:
            if not isinstance(entry, dict):
                # A scalar has no line of its own, and no neighbour to borrow one from.
                message = f"entry {_show(entry)} is not a mapping"
                yield _pool_finding(pool, 0, "track-schema", message)
                continue
            for problem in _track_problems(entry):
                yield _pool_finding(pool, entry["__line__"], "track-schema", problem)


@rule("track-genre-matches-pool")
def track_genre_matches_pool(repo: Repo) -> Iterable[Finding]:
    for pool in repo.pools:
        for entry in _mappings(pool):
            if "genre" not in entry:
                continue  # track-schema reports it
            if entry["genre"] != pool.stem:
                message = f"genre {_show(entry['genre'])} is not {pool.stem!r}, the pool it is in"
                yield _pool_finding(pool, entry["__line__"], "track-genre-matches-pool", message)


@rule("track-title-first")
def track_title_first(repo: Repo) -> Iterable[Finding]:
    """Every entry starts on a `- title:` line at column 0, and every such line starts
    an entry, so the number of lines equals the number of entries.

    `nextrack_tags.py` finds the entries of a pool by these lines. A line that
    looks like one inside a quoted string would split an entry in two for it.
    """
    for pool in repo.pools:
        starts = {n for n, text in enumerate(_lines(pool.text), 1) if text.startswith(ENTRY_START)}
        entry_lines = set()
        for entry in _mappings(pool):
            entry_lines.add(entry["__line__"])
            if entry["__line__"] not in starts:
                message = f"entry does not start with a `{ENTRY_START}` line at column 0"
                yield _pool_finding(pool, entry["__line__"], "track-title-first", message)
        for line in sorted(starts - entry_lines):
            message = f"`{ENTRY_START}` line at column 0 is not the start of an entry"
            yield _pool_finding(pool, line, "track-title-first", message)


@rule("track-unique")
def track_unique(repo: Repo) -> Iterable[Finding]:
    """No two entries, in one pool or two, share `(norm(artist), norm(title))`.

    Every later entry is reported, against the first one in file order (pools are
    sorted by path). An entry whose artist or title is not a string is skipped:
    track-schema reports it.
    """
    first: dict[tuple[str, str], str] = {}  # (artist, title) -> "path:line" of the first
    for pool in repo.pools:
        for entry in _mappings(pool):
            artist, title = entry.get("artist"), entry.get("title")
            if not (isinstance(artist, str) and isinstance(title, str)):
                continue
            key = (norm(artist), norm(title))
            where = f"{pool.path}:{entry['__line__']}"
            if key not in first:
                first[key] = where
                continue
            message = f"duplicate of {first[key]} (artist {artist!r}, title {title!r})"
            yield _pool_finding(pool, entry["__line__"], "track-unique", message)


# ---- blocks (blocks/*.md) ----
#
# A block whose front matter did not parse (`has_front` with `front` None) was
# reported by the loader, and all three rules skip it. A block with no front matter
# at all is a `block-frontmatter` finding at line 1; `block-tracklist-resolves` still
# reads its body, but `block-bridges-are-edges` needs its genres and skips it.
# Findings about the front matter point at its `__line__` (2); a missing tracklist
# heading is a finding about the whole file (line 0); the others name their own line.
# Only the clauses that read node ids or edges yield nothing when `graph_ok` is False.

BLOCK_KEYS = (
    "name", "function", "style", "duration", "genres", "bpm", "energy", "key_journey", "lightshow",
)  # fmt: skip
FUNCTIONS = ("warmup", "build", "peak", "plateau", "breakdown", "cooldown")
STYLES = ("continuous", "open-format", "hybrid")
DURATION_RE = re.compile(r"[0-9]+[mh]")
TRACKLIST_HEADING = "## Tracklist"
BRIDGE_HEADINGS = (("## Bridge in", "Bridge in"), ("## Bridge out", "Bridge out"))
# `N. Artist — Title · …`: an em dash between artist and title, then a middle dot.
TRACK_LINE_START_RE = re.compile(r"[0-9]+\.")
TRACK_LINE_RE = re.compile(r"[0-9]+\.\s+(?P<artist>.+?)\s+—\s+(?P<title>.+?)\s+·")
BACKTICKED_RE = re.compile(r"`([^`]+)`")
JOINERS = frozenset({"feat", "ft", "x", "e", "and", "com", "pres", "vs"})
PARENTHESIZED_RE = re.compile(r"\([^)]*\)|\[[^\]]*\]")


def _block_finding(block: Block, line: int, rule_id: str, message: str) -> Finding:
    return Finding(block.path, line, rule_id, message)


def _parse_failed(block: Block) -> bool:
    return block.has_front and block.front is None


def section(body: list[tuple[int, str]], prefix: str) -> list[tuple[int, str]] | None:
    """The lines after the first heading that starts with `prefix`, up to the next
    `## ` heading (or the end), or None when there is no such heading."""
    start = next((i for i, (_, text) in enumerate(body) if text.startswith(prefix)), None)
    if start is None:
        return None
    lines = []
    for number, text in body[start + 1 :]:
        if text.startswith("## "):
            break
        lines.append((number, text))
    return lines


def core(title: str) -> str:
    """`norm` of a title without its `(...)` and `[...]` parts: `Voa Voa (Ao Vivo)` -> `voa voa`."""
    return norm(PARENTHESIZED_RE.sub("", title))


def artist_tokens(artist: str) -> set[str]:
    """The words of `norm(artist)` without the joiners (`feat`, `x`, `com`, ...)."""
    return set(norm(artist).split()) - JOINERS


# block-frontmatter


def _front_problems(repo: Repo, block: Block, front: dict) -> Iterable[str]:
    yield from _key_problems(front, BLOCK_KEYS, BLOCK_KEYS)
    # `in` on a tuple compares with `==`, so an unhashable YAML value is fine.
    if "function" in front and front["function"] not in FUNCTIONS:
        yield f"function {_show(front['function'])} is not one of {', '.join(FUNCTIONS)}"
    if "style" in front and front["style"] not in STYLES:
        yield f"style {_show(front['style'])} is not one of {', '.join(STYLES)}"
    if "duration" in front and not (
        isinstance(front["duration"], str) and DURATION_RE.fullmatch(front["duration"])
    ):
        yield f"duration {_show(front['duration'])} is not a number followed by m or h, such as 30m"
    if "genres" in front:
        genres = front["genres"]
        if not isinstance(genres, list) or not genres:
            yield f"genres {_show(genres)} is not a non-empty list of node ids"
        else:
            ids = repo.node_ids()
            for genre in genres:
                # `genre` may be any YAML value: test it as a string before any set lookup.
                if not isinstance(genre, str) or (repo.graph_ok and genre not in ids):
                    yield f"genre {_show(genre)} is not a node id in {GRAPH_PATH}"
    if "bpm" in front and not is_range(front["bpm"], lo=1):
        yield f"bpm {_show(front['bpm'])} is not [min, max] of positive integers with min <= max"
    if "energy" in front and not is_range(front["energy"], lo=1, hi=10, ordered=False):
        yield f"energy {_show(front['energy'])} is not [start, end] within 1-10"
    if "key_journey" in front and not isinstance(front["key_journey"], str):
        yield f"key_journey {_show(front['key_journey'])} is not a string"
    if front.get("lightshow") is not None:
        path = front["lightshow"]
        if not (isinstance(path, str) and path):
            yield f"lightshow {_show(path)} is not null or a path"
        elif Path(path).is_absolute():
            yield f"lightshow {_show(path)} is not a path relative to the block"
        elif not os.path.exists(repo.root / Path(block.path).parent / path):  # False on OS error
            yield f"lightshow {_show(path)} does not exist"


@rule("block-frontmatter")
def block_frontmatter(repo: Repo) -> Iterable[Finding]:
    for block in repo.blocks:
        if block.front is not None:
            for problem in _front_problems(repo, block, block.front):
                yield _block_finding(block, block.front["__line__"], "block-frontmatter", problem)
        elif not block.has_front:
            message = "no front matter: the file must start with a `---` line"
            yield _block_finding(block, 1, "block-frontmatter", message)


# block-tracklist-resolves


def _track_index(repo: Repo) -> list[tuple[set[str], str]]:
    """`(artist tokens, core title)` of every pool track whose artist and title are
    strings. Any other track is skipped: `norm` gives `""` for it, and an empty token
    set is a subset of every artist. track-schema reports it."""
    index = []
    for pool in repo.pools:
        for entry in _mappings(pool):
            artist, title = entry.get("artist"), entry.get("title")
            if isinstance(artist, str) and isinstance(title, str):
                index.append((artist_tokens(artist), core(title)))
    return index


def _same_title(a: str, b: str) -> bool:
    """Equal, or one starts with the other followed by a space."""
    return a == b or a.startswith(b + " ") or b.startswith(a + " ")


def _resolves(index: list[tuple[set[str], str]], artist: str, title: str) -> bool:
    tokens, wanted = artist_tokens(artist), core(title)
    return any((t <= tokens or tokens <= t) and _same_title(c, wanted) for t, c in index)


@rule("block-tracklist-resolves")
def block_tracklist_resolves(repo: Repo) -> Iterable[Finding]:
    """Each `N. Artist — Title · …` line of the `## Tracklist` section is in the right
    format (`format:`) and matches a track of any pool (`unresolved:`).

    While a pool fails to parse its tracks are unknown, so no line is called
    unresolved: the loader's `parse-error` already says what is wrong.
    """
    pools_ok = not any(e.path.startswith("tracks/") for e in repo.errors)
    index = _track_index(repo)
    for block in repo.blocks:
        if _parse_failed(block):
            continue
        lines = section(block.body, TRACKLIST_HEADING)
        if lines is None:
            message = f"no heading that starts with `{TRACKLIST_HEADING}`"
            yield _block_finding(block, 0, "block-tracklist-resolves", message)
            continue
        for number, text in lines:
            if not TRACK_LINE_START_RE.match(text):
                continue
            parsed = TRACK_LINE_RE.match(text)
            if parsed is None:
                message = f"format: {text!r} is not `N. Artist — Title · …` (em dash, middle dot)"
                yield _block_finding(block, number, "block-tracklist-resolves", message)
            elif pools_ok and not _resolves(index, parsed["artist"], parsed["title"]):
                message = (
                    f"unresolved: no track in any pool matches artist {parsed['artist']!r}, "
                    f"title {parsed['title']!r}"
                )
                yield _block_finding(block, number, "block-tracklist-resolves", message)


# block-bridges-are-edges


def _bridge_problem(
    name: str, token: str, own: list[str], ids: set[str], edges: set[tuple[str, str]]
) -> str | None:
    """Why the backticked node id `token` of a Bridge section is wrong, or None."""
    if token not in ids:
        return f"{name} `{token}` is not a node id in {GRAPH_PATH}"
    inbound = name == "Bridge in"
    if any(((token, g) if inbound else (g, token)) in edges for g in own):
        return None
    ends = " or ".join(own)
    direction = f"{token} -> {ends}" if inbound else f"{ends} -> {token}"
    return f"no edge {direction} for {name} `{token}`"


@rule("block-bridges-are-edges")
def block_bridges_are_edges(repo: Repo) -> Iterable[Finding]:
    """Each backticked node id in `## Bridge in` / `## Bridge out` follows a graph edge.

    Bridge in needs an edge from the node to one of the block's genres, Bridge out
    one from a genre to the node; a token that is one of the block's own `genres` is
    skipped, even if that genre is not a node. A backticked word that is not shaped
    like a node id (a file name, a track) is prose; one that is shaped like one but
    names no node is reported. A block is judged by its genres that exist; with none,
    block-frontmatter has the finding.
    """
    if not repo.graph_ok:
        return
    ids = repo.node_ids()
    edges = {(src, e["to"]) for src, e in repo.edges() if isinstance(e.get("to"), str)}
    for block in repo.blocks:
        genres = block.front.get("genres") if block.front is not None else None
        if not isinstance(genres, list):
            continue
        named = {g for g in genres if isinstance(g, str)}  # skipped, even if not a node
        own = list(dict.fromkeys(g for g in genres if isinstance(g, str) and g in ids))
        if not own:
            continue
        for heading, name in BRIDGE_HEADINGS:
            for number, text in section(block.body, heading) or []:
                for token in BACKTICKED_RE.findall(text):
                    if not is_node_id(token) or token in named:
                        continue
                    problem = _bridge_problem(name, token, own, ids, edges)
                    if problem:
                        yield _block_finding(block, number, "block-bridges-are-edges", problem)


# ------------------------------------------------------------------------ run --


def _run(repo: Repo) -> list[Finding]:
    findings = list(repo.errors)
    for check_rule in RULES:
        findings.extend(check_rule(repo))
    # Two rules that read one unreadable Markdown file report it alike: keep one.
    return sorted(set(findings))


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
