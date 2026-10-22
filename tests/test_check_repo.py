"""Tests for scripts/check_repo.py: the loader, the CLI and the helpers.

Each rule group adds its own tests below, built on the `mini_repo` fixture.
"""
import re

import pytest
import yaml
from conftest import MINI_REPO_FILES, REPO_ROOT

import check_repo
from check_repo import (
    Finding,
    check,
    is_int,
    is_range,
    load_repo,
    load_yaml,
    main,
    norm,
    rule,
)

# ------------------------------------------------------------ clean repos ----


def test_mini_repo_is_clean(mini_repo):
    assert mini_repo.findings() == []


def test_real_repo_is_clean():
    assert [str(f) for f in check(REPO_ROOT)] == []


def test_crlf_repo_is_clean(mini_repo):
    for rel, text in MINI_REPO_FILES.items():
        mini_repo.path(rel).write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert mini_repo.findings() == []


# ----------------------------------------------------------------- loader ----


def test_loader_records_lines(mini_repo):
    repo = load_repo(mini_repo.root)
    graph = "genres/graph.yml"
    assert repo.nodes[0]["__line__"] == mini_repo.line_of(graph, "- id: alpha")
    first_edge = repo.edges()[0][1]
    assert first_edge["__line__"] == mini_repo.line_of(graph, "{to: beta,  strength: strong")
    pool = repo.pools[0]
    assert pool.entries[1]["__line__"] == mini_repo.line_of("tracks/alpha.yml", "Voa Voa")
    assert repo.blocks[0].front["__line__"] == 2


def test_loader_reads_the_mini_repo(mini_repo):
    repo = load_repo(mini_repo.root)
    assert repo.errors == []
    assert repo.graph_ok
    assert repo.node_ids() == {"alpha", "beta", "gamma"}
    assert [(src, e["to"]) for src, e in repo.edges()] == [
        ("alpha", "beta"), ("alpha", "gamma"),
        ("beta", "alpha"), ("beta", "gamma"),
        ("gamma", "beta"),
    ]  # fmt: skip
    pool = repo.pools[0]
    assert (pool.path, pool.stem, len(pool.entries)) == ("tracks/alpha.yml", "alpha", 2)
    assert pool.text == mini_repo.read("tracks/alpha.yml")
    block = repo.blocks[0]
    assert (block.path, block.has_front) == ("blocks/alpha-festa.md", True)
    assert block.front["name"] == "Alpha Festa"
    # The body starts right after the closing `---` (file line 11).
    assert block.body[0] == (12, "")
    assert block.body[1] == (13, "## Feel")
    assert block.body[-1] == (25, "- Ver `alpha-festa.md` (não é um node).")


def test_block_body_without_front_matter_is_every_line(mini_repo):
    mini_repo.write("blocks/alpha-festa.md", "## Feel\nOi.\n")
    block = load_repo(mini_repo.root).blocks[0]
    assert (block.has_front, block.front) == (False, None)
    assert block.body == [(1, "## Feel"), (2, "Oi.")]


def test_blocks_readme_is_not_a_block(mini_repo):
    mini_repo.write("blocks/README.md", "# Blocks\n")
    assert [b.path for b in load_repo(mini_repo.root).blocks] == ["blocks/alpha-festa.md"]


def test_comment_only_pool_has_no_entries(mini_repo):
    mini_repo.write("tracks/beta.yml", "# beta — vazio por enquanto\n")
    repo = load_repo(mini_repo.root)
    assert repo.errors == []
    assert [(p.stem, len(p.entries)) for p in repo.pools] == [("alpha", 2), ("beta", 0)]


def test_edges_skip_malformed_nodes_and_edges(mini_repo):
    repo = load_repo(mini_repo.root)
    repo.nodes[0]["neighbors"] = "beta"  # not a list: all its edges are skipped
    repo.nodes[1]["neighbors"].append("gamma")  # not a dict: skipped
    repo.nodes[2]["id"] = 7  # not a string id: no edges, and not an id
    assert [(src, e["to"]) for src, e in repo.edges()] == [
        ("beta", "alpha"), ("beta", "gamma"),
    ]  # fmt: skip
    assert repo.node_ids() == {"alpha", "beta"}


# ------------------------------------------------------------ parse errors ----


def test_missing_graph_is_a_parse_error(mini_repo):
    mini_repo.path("genres/graph.yml").unlink()
    repo = load_repo(mini_repo.root)
    assert repo.nodes == [] and not repo.graph_ok
    [finding] = repo.errors
    assert (finding.path, finding.line, finding.rule) == ("genres/graph.yml", 0, "parse-error")
    assert "missing" in finding.message


@pytest.mark.parametrize(
    "text",
    ["- alpha\n", "nodes: alpha\n", "nodes: [alpha]\n", "", "nodes: [{id: a}, 3]\n"],
    ids=["list-top-level", "nodes-scalar", "node-scalar", "empty", "mixed-nodes"],
)
def test_graph_of_the_wrong_shape_is_a_parse_error(mini_repo, text):
    mini_repo.write("genres/graph.yml", text)
    repo = load_repo(mini_repo.root)
    assert repo.nodes == [] and not repo.graph_ok
    assert [(f.path, f.rule) for f in repo.errors] == [("genres/graph.yml", "parse-error")]


@pytest.mark.parametrize(
    "text",
    ["{a: 1}\n", "- title: x\n- plain\n", "- title: [\n"],
    ids=["mapping-top-level", "scalar-entry", "unclosed-flow"],
)
def test_broken_pool_is_a_parse_error_and_left_out(mini_repo, text):
    mini_repo.write("tracks/beta.yml", text)
    repo = load_repo(mini_repo.root)
    assert [p.stem for p in repo.pools] == ["alpha"]
    assert [(f.path, f.rule) for f in repo.errors] == [("tracks/beta.yml", "parse-error")]


@pytest.mark.parametrize(
    ("text", "expected_error"),
    [
        ("---\nname: x\n", "unclosed front matter"),
        ("---\n---\n", "mapping"),
        ("---\n- a\n---\n", "mapping"),
        ("---\nname: [x\n---\n", "invalid YAML"),
    ],
    ids=["unclosed", "empty", "list", "bad-yaml"],
)
def test_broken_front_matter_is_a_parse_error(mini_repo, text, expected_error):
    mini_repo.write("blocks/alpha-festa.md", text + "\n## Feel\n")
    repo = load_repo(mini_repo.root)
    [block] = repo.blocks
    assert block.has_front and block.front is None
    [finding] = repo.errors
    assert (finding.path, finding.rule) == ("blocks/alpha-festa.md", "parse-error")
    assert expected_error in finding.message


def test_parse_error_line_is_the_file_line(mini_repo):
    mini_repo.edit("blocks/alpha-festa.md", "genres: [alpha]", "genres: [alpha")
    [finding] = load_repo(mini_repo.root).errors
    # The parser notices the missing `]` on the next line, `bpm`, whose file line
    # is 2 more than its index in the front-matter text.
    assert finding.line == mini_repo.line_of("blocks/alpha-festa.md", "bpm: [100, 135]")
    assert "\n" not in finding.message


def test_parse_error_line_never_points_past_the_end(mini_repo):
    mini_repo.write("tracks/beta.yml", "# beta\n- title: [\n")
    [finding] = load_repo(mini_repo.root).errors
    assert finding.line == 2


def test_unreadable_files_are_parse_errors(mini_repo):
    mini_repo.path("tracks/beta.yml").write_bytes(b"- title: \xff\xfe\n")
    mini_repo.path("blocks/beta.md").write_bytes(b"\xff\xfe")
    repo = load_repo(mini_repo.root)
    assert sorted(f.path for f in repo.errors) == ["blocks/beta.md", "tracks/beta.yml"]


def test_impossible_date_is_a_parse_error_not_a_crash(mini_repo):
    mini_repo.edit("tracks/alpha.yml", "bpm: 135", "bpm: 2024-13-45")
    line = mini_repo.line_of("tracks/alpha.yml", "bpm: 2024-13-45")
    assert mini_repo.findings("parse-error") == [("tracks/alpha.yml", line, "parse-error")]


@pytest.mark.parametrize(
    "value",
    ['!!int ""', '!!float ""', '!!bool "x"', '!!timestamp "x"'],
    ids=["int", "float", "bool", "timestamp"],
)
def test_explicit_tag_that_cannot_be_built_is_a_parse_error(mini_repo, value):
    # PyYAML raises IndexError, KeyError or AttributeError for these, not YAMLError.
    mini_repo.write("tracks/beta.yml", f"# beta\n\n- title: {value}\n")
    assert mini_repo.findings("parse-error") == [("tracks/beta.yml", 3, "parse-error")]


@pytest.mark.parametrize("escape", [r"\UFFFFFFFF", r"\U00110000"])
def test_bad_unicode_escape_is_a_parse_error(mini_repo, escape):
    # PyYAML's scanner raises a bare ValueError (`chr() arg not in range`) for these.
    mini_repo.write("tracks/beta.yml", f'- title: "{escape}"\n')
    mini_repo.edit("blocks/alpha-festa.md", "name: Alpha Festa", f'name: "{escape}"')
    assert mini_repo.findings("parse-error") == [
        ("blocks/alpha-festa.md", 0, "parse-error"),
        ("tracks/beta.yml", 0, "parse-error"),
    ]


def test_absurdly_nested_yaml_is_a_parse_error(mini_repo):
    mini_repo.write("tracks/beta.yml", "- " + "[" * 1000 + "]" * 1000 + "\n")
    assert mini_repo.findings("parse-error") == [("tracks/beta.yml", 0, "parse-error")]


def test_cli_reports_parse_error(mini_repo, capsys):
    mini_repo.edit("genres/graph.yml", "    bpm: [100, 120]", "    bpm: [100, 120")
    assert main(["--repo", str(mini_repo.root)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert [ln for ln in lines if re.match(r"^genres/graph\.yml:\d+: parse-error: ", ln)] == lines[:-1]
    assert len(lines) == 2
    assert lines[-1] == "1 problem(s)"


def test_parse_errors_never_raise(mini_repo):
    mini_repo.write("tracks/alpha.yml", mini_repo.read("tracks/alpha.yml") + "- title: [\n")
    mini_repo.edit("blocks/alpha-festa.md", "genres: [alpha]", "genres: [alpha")
    paths = {path for path, _line, _rule in mini_repo.findings("parse-error")}
    assert paths == {"tracks/alpha.yml", "blocks/alpha-festa.md"}


# -------------------------------------------------------------------- CLI ----


def test_cli_clean(mini_repo, capsys):
    assert main(["--repo", str(mini_repo.root)]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[-1] == "ok: 3 nodes, 5 edges, 2 tracks, 1 blocks"


def test_cli_defaults_to_the_repo_root(capsys):
    assert main([]) == 0
    assert capsys.readouterr().out.startswith("ok: ")


# --------------------------------------------------- load_yaml and registry ----


def test_load_yaml_offsets_lines_by_first_line():
    text = "a: 1\nb:\n  c: {d: 2}\n"
    data = load_yaml(text)
    assert (data["__line__"], data["b"]["__line__"], data["b"]["c"]["__line__"]) == (1, 3, 3)
    shifted = load_yaml(text, first_line=2)
    assert (shifted["__line__"], shifted["b"]["c"]["__line__"]) == (2, 4)
    assert load_yaml("# only a comment\n") is None


def test_load_yaml_raises_yaml_error():
    with pytest.raises(yaml.YAMLError):
        load_yaml("a: [1\nb: 2\n")


def test_rule_decorator_registers_and_check_sorts(mini_repo, monkeypatch):
    monkeypatch.setattr(check_repo, "RULES", [])

    @rule("demo")
    def demo(repo):
        yield Finding("z.md", 1, "demo", "last")
        yield Finding("a.md", 9, "demo", "second")
        yield Finding("a.md", 2, "demo", "first")

    assert demo.rule_id == "demo"
    assert check_repo.RULES == [demo]
    assert [str(f) for f in check(mini_repo.root)] == [
        "a.md:2: demo: first",
        "a.md:9: demo: second",
        "z.md:1: demo: last",
    ]


# ---------------------------------------------------------------- helpers ----


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  Dançarina (Ao Vivo) ", "dancarina ao vivo"),
        ("Pedro Sampaio & MC Pedrinho", "pedro sampaio mc pedrinho"),
        ("ＡＢＣ１２３", "abc123"),
        ("---", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_norm(value, expected):
    assert norm(value) == expected


def test_is_int_rejects_bool():
    assert is_int(0) and is_int(-3)
    assert not any(is_int(v) for v in (True, False, 1.0, "1", None, [1]))


@pytest.mark.parametrize(
    ("value", "kwargs", "expected"),
    [
        ([100, 120], {}, True),
        ([120, 100], {}, False),
        ([120, 100], {"ordered": False}, True),
        ([1, 10], {"lo": 1, "hi": 10}, True),
        ([0, 10], {"lo": 1, "hi": 10}, False),
        ([1, 11], {"lo": 1, "hi": 10}, False),
        ([5, 5], {}, True),
        ([1], {}, False),
        ([1, 2, 3], {}, False),
        ([True, 2], {}, False),
        ([1.5, 2], {}, False),
        (["1", "2"], {}, False),
        ((1, 2), {}, False),
        ("1-2", {}, False),
        (None, {}, False),
    ],
)
def test_is_range(value, kwargs, expected):
    assert is_range(value, **kwargs) is expected


# ------------------------------------------------------------ graph rules ----

GRAPH = "genres/graph.yml"
GRAPH_RULES = {
    "graph-node-schema",
    "graph-unique-ids",
    "graph-edge-schema",
    "graph-edges-resolve",
    "graph-node-connected",
}
# Gamma's only edge, and the line that follows it in the file.
GAMMA_EDGE = '      - {to: beta,  strength: medium, via: "ease down"}\n'
GAMMA_NEIGHBORS = "    neighbors:\n" + GAMMA_EDGE
GAMMA_SELF = '      - {to: gamma, strength: weak, via: "self"}\n'
GAMMA_AGAIN = '      - {to: beta, strength: weak, via: "again"}\n'


def graph_findings(mini_repo, rule_id):
    """`(line, message)` for every finding of one rule on the graph."""
    return [(f.line, f.message) for f in check(mini_repo.root) if f.rule == rule_id]


def test_graph_rules_are_registered():
    assert {fn.rule_id for fn in check_repo.RULES} >= GRAPH_RULES


@pytest.mark.parametrize(
    ("old", "new", "anchor"),
    [
        ("    name: Beta\n", "", "- id: beta"),
        ("    name: Gamma\n    family: global", "    name: Gamma\n    family: world", "- id: gamma"),
        ("bpm: [124, 130]", "bpm: [130, 124]", "- id: gamma"),
        ("energy: [6, 9]", "energy: [0, 9]", "- id: gamma"),
        ("energy: [4, 8]", "energy: [yes, 8]", "- id: alpha"),
        ("    name: Gamma\n", "    name: Gamma\n    colour: red\n", "- id: gamma"),
        (GAMMA_NEIGHBORS, "    neighbors: beta\n", "- id: gamma"),
        # Beyond the table: the other clauses of the rule, and more wrong types.
        ("- id: gamma", "- id: Gamma_2", "- id: Gamma_2"),
        ("- id: gamma", "- id: 7", "- id: 7"),
        ("- id: gamma\n    name: Gamma", "- name: Gamma", "- name: Gamma"),
        ("    name: Gamma\n", '    name: ""\n', "- id: gamma"),
        ("    name: Gamma\n", "    name: [Gamma]\n", "- id: gamma"),
        ("family: global\n    bpm: [124", "family: [global]\n    bpm: [124", "- id: gamma"),
        ("bpm: [124, 130]", 'bpm: "124"', "- id: gamma"),
        ("bpm: [124, 130]", "bpm: [0, 130]", "- id: gamma"),
        ("bpm: [124, 130]", "bpm: [124.5, 130]", "- id: gamma"),
        ("bpm: [124, 130]", "bpm: [124]", "- id: gamma"),
        ("energy: [6, 9]", "energy: [6, 11]", "- id: gamma"),
        ("energy: [6, 9]", "energy: 9", "- id: gamma"),
        ("feel: [warm]", "feel: warm", "- id: alpha"),
        ("feel: [warm]", "feel: [1]", "- id: alpha"),
        ("subgenres: [alpha-sub]", "subgenres: {a: b}", "- id: alpha"),
        (GAMMA_NEIGHBORS, "", "- id: gamma"),
        (GAMMA_NEIGHBORS, "    neighbors: {to: beta}\n", "- id: gamma"),
    ],
    ids=[
        "missing-name", "family", "bpm-reversed", "energy-zero", "energy-bool", "unknown-key",
        "neighbors-scalar", "id-not-kebab", "id-int", "id-missing", "name-empty", "name-list",
        "family-list", "bpm-string", "bpm-zero", "bpm-float", "bpm-one-item", "energy-eleven",
        "energy-scalar", "feel-scalar", "feel-int", "subgenres-mapping", "neighbors-missing",
        "neighbors-mapping",
    ],
)  # fmt: skip
def test_graph_node_schema(mini_repo, old, new, anchor):
    mini_repo.edit(GRAPH, old, new)
    line = mini_repo.line_of(GRAPH, anchor)
    assert mini_repo.findings("graph-node-schema") == [(GRAPH, line, "graph-node-schema")]
    mini_repo.findings()  # no rule raises on the wrong type


def test_graph_node_schema_reports_each_problem_of_a_node(mini_repo):
    mini_repo.edit(GRAPH, "    name: Gamma\n", "    colour: red\n    shade: dark\n")
    line = mini_repo.line_of(GRAPH, "- id: gamma")
    # `name` is missing, and `colour` and `shade` are unknown.
    assert mini_repo.findings("graph-node-schema") == [(GRAPH, line, "graph-node-schema")] * 3


def test_graph_unique_ids(mini_repo):
    text = mini_repo.read(GRAPH)
    mini_repo.write(GRAPH, text + text[text.index("  - id: gamma") :])
    line = text.count("\n") + 1
    assert mini_repo.findings("graph-unique-ids") == [(GRAPH, line, "graph-unique-ids")]


def test_graph_unique_ids_flags_every_later_copy(mini_repo):
    text = mini_repo.read(GRAPH)
    copy = text[text.index("  - id: gamma") :]
    mini_repo.write(GRAPH, text + copy + copy)
    first = text.count("\n") + 1
    assert mini_repo.findings("graph-unique-ids") == [
        (GRAPH, first, "graph-unique-ids"),
        (GRAPH, first + copy.count("\n"), "graph-unique-ids"),
    ]


@pytest.mark.parametrize(
    ("old", "new", "anchor"),
    [
        ('strength: medium, via: "ease down"', 'strength: solid, via: "ease down"', "strength: solid"),
        ('via: "ease down"', 'via: ""', 'via: ""'),
        ('via: "ease down"}', 'via: "ease down", note: 1}', "note: 1"),
        # Beyond the table: the other clauses of the rule, and more wrong types.
        ('via: "ease down"', "via: [ease]", "via: [ease]"),
        ('via: "ease down"', "via: 3", "via: 3"),
        ('strength: medium, via: "ease', 'strength: [medium], via: "ease', "strength: [medium]"),
        ('{to: beta,  strength: medium, via: "ease down"}', '{to: beta, via: "ease down"}', "{to: beta, via"),
        ('{to: beta,  strength: medium, via: "ease down"}', "{to: beta, strength: medium}", "{to: beta, strength: medium}"),
        ('{to: beta,  strength: medium, via: "ease down"}', '{strength: medium, via: "ease down"}', "{strength: medium"),
        # A scalar edge has no line of its own, so the finding points at its node.
        ('{to: beta,  strength: medium, via: "ease down"}', "beta", "- id: gamma"),
    ],
    ids=[
        "strength-unknown", "via-empty", "extra-key", "via-list", "via-int", "strength-list",
        "missing-strength", "missing-via", "missing-to", "edge-not-a-mapping",
    ],
)  # fmt: skip
def test_graph_edge_schema(mini_repo, old, new, anchor):
    mini_repo.edit(GRAPH, old, new)
    line = mini_repo.line_of(GRAPH, anchor)
    assert mini_repo.findings("graph-edge-schema") == [(GRAPH, line, "graph-edge-schema")]
    mini_repo.findings()  # no rule raises on the wrong type


def test_graph_edge_schema_checks_the_edges_of_a_node_with_a_bad_id(mini_repo):
    mini_repo.edit(GRAPH, "- id: gamma", "- id: 7")
    mini_repo.edit(GRAPH, 'via: "ease down"', 'via: ""')
    line = mini_repo.line_of(GRAPH, 'via: ""')
    assert mini_repo.findings("graph-edge-schema") == [(GRAPH, line, "graph-edge-schema")]


@pytest.mark.parametrize(
    ("old", "new", "anchor"),
    [
        ("{to: beta,  strength: medium", "{to: delta, strength: medium", "{to: delta"),
        (GAMMA_EDGE, GAMMA_EDGE + GAMMA_SELF, '"self"'),
        (GAMMA_EDGE, GAMMA_EDGE + GAMMA_AGAIN, '"again"'),
        # Beyond the table: a target that is not a string must not raise.
        ("{to: beta,  strength: medium", "{to: [beta], strength: medium", "{to: [beta]"),
        ("{to: beta,  strength: medium", "{to: 7, strength: medium", "{to: 7,"),
        ("{to: beta,  strength: medium", "{to: Beta, strength: medium", "{to: Beta"),
    ],
    ids=["unknown", "self", "duplicate", "to-list", "to-int", "to-wrong-case"],
)  # fmt: skip
def test_graph_edges_resolve(mini_repo, old, new, anchor):
    mini_repo.edit(GRAPH, old, new)
    line = mini_repo.line_of(GRAPH, anchor)
    assert mini_repo.findings("graph-edges-resolve") == [(GRAPH, line, "graph-edges-resolve")]
    mini_repo.findings()  # no rule raises on the wrong type


def test_graph_edges_resolve_flags_two_edges_to_an_unknown_node_as_unknown(mini_repo):
    mini_repo.edit(GRAPH, GAMMA_EDGE, GAMMA_EDGE.replace("beta,", "delta,") * 2)
    lines = [n for n, text in enumerate(mini_repo.read(GRAPH).splitlines(), 1) if "to: delta" in text]
    assert len(lines) == 2
    assert graph_findings(mini_repo, "graph-edges-resolve") == [
        (line, "edge to unknown node 'delta'") for line in lines
    ]


def test_graph_edges_resolve_ignores_an_edge_without_a_target(mini_repo):
    # The missing `to` is graph-edge-schema's finding; resolving it would repeat it.
    mini_repo.edit(GRAPH, "{to: beta,  strength: medium, ", "{strength: medium, ")
    assert mini_repo.findings("graph-edges-resolve") == []
    assert len(mini_repo.findings("graph-edge-schema")) == 1


def test_graph_node_connected(mini_repo):
    mini_repo.edit(GRAPH, GAMMA_NEIGHBORS, "    neighbors: []\n")
    line = mini_repo.line_of(GRAPH, "- id: gamma")
    assert mini_repo.findings("graph-node-connected") == [(GRAPH, line, "graph-node-connected")]


def test_graph_node_connected_needs_an_incoming_edge(mini_repo):
    # Only beta pointed at alpha: alpha still leads out, but nothing leads in.
    mini_repo.edit(GRAPH, '      - {to: alpha, strength: strong, via: "drop back to the groove"}\n', "")
    line = mini_repo.line_of(GRAPH, "- id: alpha")
    assert mini_repo.findings("graph-node-connected") == [(GRAPH, line, "graph-node-connected")]


@pytest.mark.parametrize(
    "replacement",
    [GAMMA_SELF, GAMMA_SELF.replace("gamma", "delta")],
    ids=["self-edge-only", "dangling-edge-only"],
)
def test_graph_node_connected_counts_only_edges_to_another_node(mini_repo, replacement):
    mini_repo.edit(GRAPH, GAMMA_EDGE, replacement)
    line = mini_repo.line_of(GRAPH, "- id: gamma")
    assert mini_repo.findings("graph-node-connected") == [(GRAPH, line, "graph-node-connected")]


def test_graph_node_connected_reports_a_missing_direction_each(mini_repo):
    lone = (
        "nodes:\n  - id: lone\n    name: Lone\n    family: global\n"
        "    bpm: [100, 120]\n    energy: [4, 8]\n    neighbors: []\n"
    )
    mini_repo.write(GRAPH, lone)
    assert graph_findings(mini_repo, "graph-node-connected") == [
        (2, "node 'lone' has no incoming edge from another node"),
        (2, "node 'lone' has no outgoing edge to another node"),
    ]


@pytest.mark.parametrize(
    ("old", "new", "rule_id", "message"),
    [
        ("    name: Gamma\n", "    name: Gamma\n    colour: red\n", "graph-node-schema", "unknown key 'colour'"),
        ("    name: Beta\n", "", "graph-node-schema", "missing key 'name'"),
        ("family: global\n    bpm: [124", "family: world\n    bpm: [124", "graph-node-schema", "family 'world'"),
        ('strength: medium, via: "ease', 'strength: solid, via: "ease', "graph-edge-schema", "strength 'solid'"),
        ('via: "ease down"}', 'via: "ease down", note: 1}', "graph-edge-schema", "unknown key 'note'"),
        ("{to: beta,  strength: medium", "{to: delta, strength: medium", "graph-edges-resolve", "unknown node 'delta'"),
        (GAMMA_EDGE, GAMMA_EDGE + GAMMA_SELF, "graph-edges-resolve", "edge from 'gamma' to itself"),
        (GAMMA_EDGE, GAMMA_EDGE + GAMMA_AGAIN, "graph-edges-resolve", "second edge to 'beta'"),
    ],
    ids=["unknown-key", "missing-key", "family", "strength", "edge-key", "unknown-node", "self", "duplicate"],
)  # fmt: skip
def test_graph_messages_name_the_offender(mini_repo, old, new, rule_id, message):
    mini_repo.edit(GRAPH, old, new)
    [(_line, text)] = graph_findings(mini_repo, rule_id)
    assert message in text


def test_graph_unique_ids_message_names_the_id_and_the_first_line(mini_repo):
    text = mini_repo.read(GRAPH)
    mini_repo.write(GRAPH, text + text[text.index("  - id: gamma") :])
    first = mini_repo.read(GRAPH).splitlines().index("  - id: gamma") + 1
    [(_line, message)] = graph_findings(mini_repo, "graph-unique-ids")
    assert message == f"duplicate id 'gamma' (first defined on line {first})"


@pytest.mark.parametrize(
    "text",
    ["- alpha\n", "nodes: alpha\n", "nodes: [alpha]\n", "", "nodes: [{id: a}, 3]\n"],
    ids=["list-top-level", "nodes-scalar", "node-scalar", "empty", "mixed-nodes"],
)
def test_graph_that_did_not_load_gets_only_a_parse_error(mini_repo, text):
    mini_repo.write(GRAPH, text)
    assert [rule_id for _path, _line, rule_id in mini_repo.findings()] == ["parse-error"]


def test_every_graph_rule_checks_graph_ok_itself(mini_repo):
    repo = load_repo(mini_repo.root)
    repo.nodes[0]["colour"] = "red"  # graph-node-schema
    repo.nodes.append(dict(repo.nodes[1]))  # graph-unique-ids
    repo.nodes[1]["neighbors"] = [{"to": "delta", "strength": "solid", "via": "", "__line__": 9}]
    repo.nodes[2]["neighbors"] = []  # graph-node-connected
    graph_rules = [fn for fn in check_repo.RULES if fn.rule_id in GRAPH_RULES]
    assert {fn.rule_id for fn in graph_rules if list(fn(repo))} == GRAPH_RULES
    repo.graph_ok = False
    assert [fn.rule_id for fn in graph_rules if list(fn(repo))] == []


def test_graph_with_no_nodes_is_clean(mini_repo):
    # The taxonomy and the map must list no node either, or the docs rules rightly object.
    mini_repo.write(GRAPH, "nodes: []\n")
    mini_repo.write("docs/taxonomy.md", "# Taxonomy\n")
    mini_repo.write("docs/genre-graph.md", "# Genre graph\n\n```mermaid\ngraph LR\n```\n")
    graph_and_docs = GRAPH_RULES | {"taxonomy-matches-graph", "mermaid-matches-graph"}
    assert [f for f in mini_repo.findings() if f[2] in graph_and_docs] == []


# -------------------------------------------------------------- docs rules ----

TAXONOMY = "docs/taxonomy.md"
MAP = "docs/genre-graph.md"
TAXONOMY_RULE = "taxonomy-matches-graph"
MERMAID_RULE = "mermaid-matches-graph"
LINKS_RULE = "links-resolve"
DOCS_RULES = {TAXONOMY_RULE, MERMAID_RULE, LINKS_RULE}
MAP_END = "  B -.-> G\n```"  # the last edge of the map and the block's closing fence


def append(mini_repo, rel, text):
    mini_repo.write(rel, mini_repo.read(rel) + text)


def add_to_map(mini_repo, line):
    """Insert a line just before the closing fence of the Mermaid block; return its line."""
    mini_repo.edit(MAP, MAP_END, f"  B -.-> G\n{line}\n```")
    return mini_repo.line_of(MAP, "  B -.-> G\n") + 1


def messages(mini_repo, rule_id):
    return [f.message for f in check(mini_repo.root) if f.rule == rule_id]


def test_docs_rules_are_registered():
    assert {fn.rule_id for fn in check_repo.RULES} >= DOCS_RULES


# ---- taxonomy-matches-graph ----


def test_taxonomy_missing_heading(mini_repo):
    mini_repo.edit(TAXONOMY, "### `gamma`\n", "")
    assert mini_repo.findings(TAXONOMY_RULE) == [(TAXONOMY, 0, TAXONOMY_RULE)]
    assert messages(mini_repo, TAXONOMY_RULE) == ["node 'gamma' has no ### `gamma` heading"]


def test_taxonomy_stale_heading(mini_repo):
    append(mini_repo, TAXONOMY, "\n### `delta`\nGone.")
    line = mini_repo.line_of(TAXONOMY, "### `delta`")
    assert mini_repo.findings(TAXONOMY_RULE) == [(TAXONOMY, line, TAXONOMY_RULE)]
    assert messages(mini_repo, TAXONOMY_RULE) == ["heading for 'delta' has no node in graph.yml"]


@pytest.mark.parametrize(
    "text",
    ["## `delta`\n", "#### `delta`\n", "### Delta\n", "- ### `delta`\n", "```\n### `delta`\n```\n"],
    ids=["level-2", "level-4", "no-backticks", "in-a-list", "in-a-fence"],
)
def test_taxonomy_only_counts_level_3_id_headings_outside_code(mini_repo, text):
    append(mini_repo, TAXONOMY, "\n" + text)
    assert mini_repo.findings(TAXONOMY_RULE) == []


def test_taxonomy_heading_text_after_the_id_is_free(mini_repo):
    mini_repo.edit(TAXONOMY, "### `beta`\n", "### `beta` — Beta (driving)\n")
    assert mini_repo.findings(TAXONOMY_RULE) == []


# ---- mermaid-matches-graph ----


@pytest.mark.parametrize(
    ("old", "new", "anchors"),
    [
        ('  G["gamma"]\n', "", ["```mermaid", "```mermaid", "  B -.-> G"]),
        (MAP_END, '  B -.-> G\n  D["delta"]\n```', ['  D["delta"]']),
        (MAP_END, "  B -.-> G\n  B --- A\n```", ["  B --- A"]),
        ("  B -.-> G", "  B --- G", ["  B --- G"]),
        ("  A --- B\n", "", ["```mermaid"]),
        (MAP_END, "  B -.-> G\n  A -.-> G\n```", ["  A -.-> G"]),
    ],
    ids=["undeclared-node", "unknown-node", "pair-twice", "wrong-style", "pair-missing", "weak-drawn"],
)
def test_mermaid(mini_repo, old, new, anchors):
    mini_repo.edit(MAP, old, new)
    expected = sorted((MAP, mini_repo.line_of(MAP, anchor), MERMAID_RULE) for anchor in anchors)
    assert mini_repo.findings(MERMAID_RULE) == expected


def test_mermaid_messages_name_the_offender(mini_repo):
    mini_repo.edit(MAP, '  G["gamma"]\n', "")
    # Findings sort by line, then by message: the two on the fence line come first.
    assert messages(mini_repo, MERMAID_RULE) == [
        "'beta' and 'gamma' have a medium edge but are not drawn: add a `-.->` line",
        "node 'gamma' is not declared in the map",
        "edge uses alias 'G', which is not declared",
    ]


def test_mermaid_message_for_a_pair_drawn_twice_names_the_first_line(mini_repo):
    add_to_map(mini_repo, "  B --- A")
    first = mini_repo.line_of(MAP, "  A --- B")
    assert messages(mini_repo, MERMAID_RULE) == [
        f"'alpha' and 'beta' are already drawn on line {first}"
    ]


def test_mermaid_message_for_a_wrong_style_says_which_to_use(mini_repo):
    mini_repo.edit(MAP, "  B -.-> G", "  B --- G")
    assert messages(mini_repo, MERMAID_RULE) == [
        "'beta' and 'gamma' have a medium edge: draw `-.->`, not `---`"
    ]


def test_mermaid_message_for_a_weak_pair_says_it_is_weak(mini_repo):
    add_to_map(mini_repo, "  A -.-> G")
    assert messages(mini_repo, MERMAID_RULE) == [
        "'alpha' and 'gamma' have only a weak edge in graph.yml, so they are not drawn"
    ]


def test_mermaid_takes_the_stronger_direction_of_a_pair(mini_repo):
    # Alpha -> gamma is weak, but gamma -> alpha is medium: the pair must be drawn.
    mini_repo.edit(GRAPH, GAMMA_EDGE, GAMMA_EDGE + '      - {to: alpha, strength: medium, via: "x"}\n')
    fence = mini_repo.line_of(MAP, "```mermaid")
    assert mini_repo.findings(MERMAID_RULE) == [(MAP, fence, MERMAID_RULE)]
    add_to_map(mini_repo, "  G -.-> A")
    assert mini_repo.findings(MERMAID_RULE) == []


def test_mermaid_stronger_direction_changes_the_style(mini_repo):
    mini_repo.edit(GRAPH, GAMMA_EDGE, GAMMA_EDGE.replace("medium", "strong"))
    line = mini_repo.line_of(MAP, "  B -.-> G")
    assert mini_repo.findings(MERMAID_RULE) == [(MAP, line, MERMAID_RULE)]


@pytest.mark.parametrize(
    "extra_edge",
    [
        GAMMA_SELF,
        GAMMA_SELF.replace("gamma", "delta"),
        GAMMA_SELF.replace("gamma", "delta").replace("weak", "strong"),
        GAMMA_AGAIN.replace("weak", "solid"),
        GAMMA_AGAIN.replace("beta,", "[beta],"),
    ],
    ids=["self-edge", "unknown-target", "unknown-strong-target", "bad-strength", "list-target"],
)
def test_mermaid_ignores_edges_that_other_rules_report(mini_repo, extra_edge):
    mini_repo.edit(GRAPH, GAMMA_EDGE, GAMMA_EDGE + extra_edge)
    assert mini_repo.findings(MERMAID_RULE) == []
    mini_repo.findings()  # no rule raises on the wrong type


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ('  A["alpha"]', "alias 'A' is declared again (first on line {A})"),
        ('  X["alpha"]', "node 'alpha' is declared again (first on line {A})"),
        ("  A --- Z", "edge uses alias 'Z', which is not declared"),
        ("  A --- A", "'alpha' and 'alpha' have no edge in graph.yml, so they are not drawn"),
    ],
    ids=["alias-twice", "node-twice", "undeclared-alias", "self-pair"],
)
def test_mermaid_declaration_and_edge_problems(mini_repo, line, message):
    where = add_to_map(mini_repo, line)
    assert mini_repo.findings(MERMAID_RULE) == [(MAP, where, MERMAID_RULE)]
    declared_at = mini_repo.read(MAP).splitlines().index('  A["alpha"]') + 1
    assert messages(mini_repo, MERMAID_RULE) == [message.format(A=declared_at)]


def test_mermaid_edge_may_come_before_the_declarations(mini_repo):
    mini_repo.edit(MAP, '  A["alpha"]\n  B["beta"]\n  G["gamma"]\n  A --- B\n  B -.-> G\n',
                   '  A --- B\n  B -.-> G\n  A["alpha"]\n  B["beta"]\n  G["gamma"]\n')  # fmt: skip
    assert mini_repo.findings(MERMAID_RULE) == []


def test_mermaid_ignores_subgraph_and_other_lines(mini_repo):
    mini_repo.edit(MAP, '  A["alpha"]\n', '  subgraph S["Group"]\n  A["alpha"]\n  end\n  %% a comment\n')
    assert mini_repo.findings(MERMAID_RULE) == []


def test_mermaid_only_the_first_mermaid_block_counts(mini_repo):
    mini_repo.edit(MAP, "```mermaid\ngraph LR", '```text\n  Q["quux"]\n```\n\n```mermaid\ngraph LR')
    append(mini_repo, MAP, '\n```mermaid\ngraph LR\n  Z["zeta"]\n  Z --- Y\n```\n')
    assert mini_repo.findings(MERMAID_RULE) == []


def test_mermaid_block_may_be_indented_and_unclosed(mini_repo):
    mini_repo.edit(MAP, "```mermaid", "   ```mermaid")
    mini_repo.edit(MAP, MAP_END, "  B -.-> G\n")  # no closing fence: the block runs to the end
    assert mini_repo.findings(MERMAID_RULE) == []


def test_mermaid_without_a_block(mini_repo):
    mini_repo.write(MAP, "# Genre graph\n\n```text\nno map here\n```\n")
    assert mini_repo.findings(MERMAID_RULE) == [(MAP, 0, MERMAID_RULE)]
    assert messages(mini_repo, MERMAID_RULE) == ["no ```mermaid block"]


# ---- both rules that read the graph ----


def test_docs_rules_that_read_the_graph_check_graph_ok_themselves(mini_repo):
    mini_repo.edit(TAXONOMY, "### `gamma`\n", "")
    mini_repo.edit(MAP, '  G["gamma"]\n', "")
    repo = load_repo(mini_repo.root)
    graph_docs = [fn for fn in check_repo.RULES if fn.rule_id in {TAXONOMY_RULE, MERMAID_RULE}]
    assert len(graph_docs) == 2 and all(list(fn(repo)) for fn in graph_docs)
    repo.graph_ok = False
    assert [list(fn(repo)) for fn in graph_docs] == [[], []]


def test_a_graph_that_did_not_load_does_not_flood_the_docs_rules(mini_repo):
    mini_repo.edit(TAXONOMY, "### `gamma`\n", "")
    mini_repo.write(GRAPH, "nodes: alpha\n")
    assert mini_repo.findings(TAXONOMY_RULE) == mini_repo.findings(MERMAID_RULE) == []


@pytest.mark.parametrize(
    ("rel", "rule_id"),
    [(TAXONOMY, TAXONOMY_RULE), (MAP, MERMAID_RULE)],
    ids=["taxonomy", "map"],
)
def test_unreadable_docs_are_a_parse_error_and_never_raise(mini_repo, rel, rule_id):
    mini_repo.path(rel).write_bytes(b"\xff\xfe")
    assert mini_repo.findings("parse-error") == [(rel, 0, "parse-error")]
    assert mini_repo.findings(rule_id) == []


@pytest.mark.parametrize("rel", [TAXONOMY, MAP])
def test_missing_docs_are_a_parse_error(mini_repo, rel):
    mini_repo.path(rel).unlink()
    assert mini_repo.findings("parse-error") == [(rel, 0, "parse-error")]


# ---- links-resolve ----


@pytest.mark.parametrize(
    ("appended", "broken"),
    [
        ("[x](missing.md)\n", "[x](missing.md)"),
        ("`[x](missing.md)`\n", None),
        ("```\n[x](missing.md)\n```\n", None),
        ("[x](#top)\n", None),
        ("[x](https://example.com)\n", None),
        ("[t](docs/taxonomy.md#alpha)\n", None),
    ],
    ids=["missing", "inline-code", "fenced-block", "anchor-only", "url", "anchor-on-a-file"],
)
def test_links_resolve(mini_repo, appended, broken):
    append(mini_repo, "README.md", appended)
    expected = [("README.md", mini_repo.line_of("README.md", broken), LINKS_RULE)] if broken else []
    assert mini_repo.findings(LINKS_RULE) == expected


def test_links_message_names_the_target(mini_repo):
    append(mini_repo, "README.md", "[x](missing.md#top)\n")
    assert messages(mini_repo, LINKS_RULE) == ["link to 'missing.md#top' does not exist"]


def test_links_checked_when_repo_lives_under_dot_dir(tmp_path, mini_repo_at):
    repo = mini_repo_at(tmp_path / ".worktrees" / "x")
    append(repo, "README.md", "[x](missing.md)\n")
    line = repo.line_of("README.md", "[x](missing.md)")
    assert repo.findings(LINKS_RULE) == [("README.md", line, LINKS_RULE)]


def test_links_ignored_in_nested_fence(mini_repo):
    # A ```` fence is not closed by a ``` line, so the link inside it is code.
    append(mini_repo, "README.md", "````\n```\n[x](missing.md)\n```\n````\n")
    assert mini_repo.findings(LINKS_RULE) == []


@pytest.mark.parametrize(
    "appended",
    [
        "~~~\n[x](missing.md)\n~~~\n",
        "```md\n[x](missing.md)\n```\n",
        "   ```\n[x](missing.md)\n   ```\n",
        "```\n[x](missing.md)\n`````\n",
        "```\n[x](missing.md)\n",
        "~~~\n```\n[x](missing.md)\n```\n~~~\n",
        "``a ` [x](missing.md)``\n",
        "`a ``[x](missing.md)`` b`\n",
        "`a\n[x](missing.md) b`\n",
    ],
    ids=[
        "tilde-fence", "fence-with-info", "indented-fence", "longer-closing-fence", "unclosed-fence",
        "tilde-fence-around-backticks", "double-backtick-span", "span-around-a-longer-run",
        "span-over-two-lines",
    ],
)
def test_links_ignored_in_code(mini_repo, appended):
    append(mini_repo, "README.md", appended)
    assert mini_repo.findings(LINKS_RULE) == []


@pytest.mark.parametrize(
    "appended",
    [
        "```\ncode\n```\n[x](missing.md)\n",
        "~~~\n```\ncode\n~~~\n[x](missing.md)\n",
        "```\ncode\n```not a closing fence\n```\n[x](missing.md)\n",
        "a stray ` here\n\n[x](missing.md) and ` there\n",
        "``a`` and `b` then [x](missing.md)\n",
        "![image](missing.png) and [ok](README.md)\n",
    ],
    ids=[
        "after-a-fence", "after-a-tilde-fence", "closing-fence-has-text",
        "stray-backtick", "after-spans", "image",
    ],
)
def test_links_checked_outside_code(mini_repo, appended):
    # The blanked-out code keeps its lines, so the finding is on the link's own line.
    before = len(mini_repo.read("README.md").splitlines())
    append(mini_repo, "README.md", appended)
    offset = next(n for n, text in enumerate(appended.splitlines(), 1) if "missing." in text)
    assert mini_repo.findings(LINKS_RULE) == [("README.md", before + offset, LINKS_RULE)]


def test_links_each_broken_link_is_a_finding(mini_repo):
    append(mini_repo, "README.md", "[a](one.md) [b](README.md) [c](two.md)\n")
    line = mini_repo.line_of("README.md", "[a](one.md)")
    assert mini_repo.findings(LINKS_RULE) == [("README.md", line, LINKS_RULE)] * 2


@pytest.mark.parametrize(
    ("rel", "target", "ok"),
    [
        (TAXONOMY, "../README.md", True),
        (TAXONOMY, "README.md", False),
        (TAXONOMY, "genre-graph.md", True),
        (TAXONOMY, "../docs/", True),
        (TAXONOMY, "/README.md", True),
        (TAXONOMY, "/taxonomy.md", False),
        (TAXONOMY, "//example.com/page", True),
        (TAXONOMY, "mailto:a@example.com", True),
        (TAXONOMY, "missing.md#top", False),
        ("notes/deep/n.md", "../../README.md", True),
        ("notes/deep/n.md", "README.md", False),
    ],
)
def test_links_resolve_relative_to_the_file(mini_repo, rel, target, ok):
    old = mini_repo.read(rel) if mini_repo.path(rel).exists() else ""
    mini_repo.write(rel, old + f"[x]({target})\n")
    line = len(mini_repo.read(rel).splitlines())
    assert mini_repo.findings(LINKS_RULE) == ([] if ok else [(rel, line, LINKS_RULE)])


@pytest.mark.parametrize("rel", [".hidden/n.md", "docs/.draft.md", "docs/.private/n.md", ".n.md"])
def test_links_skip_files_under_a_dot_component(mini_repo, rel):
    mini_repo.write(rel, "[x](missing.md)\n")
    assert mini_repo.findings(LINKS_RULE) == []


def test_links_a_target_the_filesystem_rejects_is_a_finding_not_a_crash(mini_repo):
    append(mini_repo, "README.md", f"[x]({'a' * 5000}.md)\n")
    append(mini_repo, "README.md", "[y](bad\x00name.md)\n")
    assert [line for _p, line, _r in mini_repo.findings(LINKS_RULE)] == [4, 5]


def test_unreadable_markdown_is_one_parse_error_per_file(mini_repo):
    for rel in ("README.md", TAXONOMY, MAP, "notes/n.md"):
        mini_repo.path(rel).parent.mkdir(parents=True, exist_ok=True)
        mini_repo.path(rel).write_bytes(b"\xff\xfe")
    # The three rules that read docs/taxonomy.md and docs/genre-graph.md must not repeat it.
    assert mini_repo.findings("parse-error") == [
        ("README.md", 0, "parse-error"),
        (MAP, 0, "parse-error"),
        (TAXONOMY, 0, "parse-error"),
        ("notes/n.md", 0, "parse-error"),
    ]
    assert mini_repo.findings(LINKS_RULE) == []


# --------------------------------------------------------------- pool rules ----

ALPHA = "tracks/alpha.yml"
POOL_RULES = {
    "pool-file-is-node",
    "track-schema",
    "track-genre-matches-pool",
    "track-title-first",
    "track-unique",
}
# The pool is a comment, then two entries; each entry starts with its `- title:` line.
_, FIRST_ENTRY, SECOND_ENTRY = MINI_REPO_FILES[ALPHA].split("\n\n")
FIRST_TITLE = '- title: "Dançarina"'
SECOND_TITLE = '- title: "Voa Voa (Ao Vivo)"'
SWAPPED = '- artist: "Chiclete com Banana"\n  title: "Voa Voa (Ao Vivo)"'


def track(title='"Outra Música"', artist='"Outro Artista"', genre="beta"):
    """One valid pool entry; `title` and `artist` are raw YAML, so they can be any type."""
    return (
        f"- title: {title}\n  artist: {artist}\n  genre: {genre}\n"
        "  bpm: null\n  key: null\n  energy: 5\n  status: to-download\n"
    )


def pool_findings(mini_repo):
    """`(path, line, rule)` of every finding of the five pool rules."""
    return [f for f in mini_repo.findings() if f[2] in POOL_RULES]


def pool_messages(mini_repo, rule_id):
    return [f.message for f in check(mini_repo.root) if f.rule == rule_id]


def title_lines(text):
    """The 1-based lines of `text` that start an entry."""
    return [n for n, line in enumerate(text.split("\n"), 1) if line.startswith("- title:")]


def test_pool_rules_are_registered():
    assert {fn.rule_id for fn in check_repo.RULES} >= POOL_RULES


# ---- pool-file-is-node ----


def test_pool_file_is_node(mini_repo):
    mini_repo.write("tracks/delta.yml", track(genre="delta"))
    assert mini_repo.findings() == [("tracks/delta.yml", 0, "pool-file-is-node")]


def test_pool_file_is_node_message_names_the_pool(mini_repo):
    mini_repo.write("tracks/delta.yml", track(genre="delta"))
    assert pool_messages(mini_repo, "pool-file-is-node") == [
        "'delta' is not a node id in genres/graph.yml"
    ]


def test_pool_file_is_node_flags_each_pool_without_a_node(mini_repo):
    mini_repo.write("tracks/delta.yml", track(genre="delta"))
    mini_repo.write("tracks/Not_An_Id.yml", track(title='"Mais Uma"', genre="Not_An_Id"))
    assert mini_repo.findings("pool-file-is-node") == [
        ("tracks/Not_An_Id.yml", 0, "pool-file-is-node"),
        ("tracks/delta.yml", 0, "pool-file-is-node"),
    ]


def test_pool_file_is_node_checks_graph_ok_itself(mini_repo):
    mini_repo.write("tracks/delta.yml", track(genre="delta"))
    repo = load_repo(mini_repo.root)
    (fn,) = (fn for fn in check_repo.RULES if fn.rule_id == "pool-file-is-node")
    assert [f.path for f in fn(repo)] == ["tracks/delta.yml"]
    repo.graph_ok = False
    assert list(fn(repo)) == []


def test_a_graph_that_did_not_load_does_not_flood_pool_file_is_node(mini_repo):
    mini_repo.write("genres/graph.yml", "- alpha\n")
    assert [rule_id for _path, _line, rule_id in mini_repo.findings()] == ["parse-error"]


def test_the_other_pool_rules_do_not_need_the_graph(mini_repo):
    mini_repo.write("genres/graph.yml", "- alpha\n")
    mini_repo.edit(ALPHA, "status: downloaded", "status: lost")
    line = mini_repo.line_of(ALPHA, FIRST_TITLE)
    assert mini_repo.findings("track-schema") == [(ALPHA, line, "track-schema")]


# ---- track-schema ----


@pytest.mark.parametrize(
    ("old", "new", "anchor"),
    [
        ("  status: to-download\n", "", SECOND_TITLE),
        ("status: to-download", "status: lost", SECOND_TITLE),
        ("bpm: 135", 'bpm: "135"', FIRST_TITLE),
        ("bpm: 135", "bpm: 0", FIRST_TITLE),
        ("key: 8A", "key: 13A", FIRST_TITLE),
        ("key: 8A", "key: 8C", FIRST_TITLE),
        ("energy: 8", "energy: 11", FIRST_TITLE),
        ("energy: 8", "energy: yes", FIRST_TITLE),
        ('  notes: "opens the block"\n', '  notes: "opens the block"\n  artsit: "x"\n', SECOND_TITLE),
        ('title: "Dançarina"', 'title: ""', '- title: ""'),
        ("  bpm: null\n", "", SECOND_TITLE),
        ("tags: [funk, singalong]", "tags: funk", FIRST_TITLE),
        # Beyond the table: the other clauses of the rule, and more wrong types.
        ("bpm: 135", "bpm: 301", FIRST_TITLE),
        ("bpm: 135", "bpm: 135.5", FIRST_TITLE),
        ("bpm: 135", "bpm: true", FIRST_TITLE),
        ("bpm: 135", "bpm: [135]", FIRST_TITLE),
        ("key: 8A", "key: 0A", FIRST_TITLE),
        ("key: 8A", "key: 8a", FIRST_TITLE),
        ("key: 8A", "key: 8", FIRST_TITLE),
        ("key: 8A", "key: [8A]", FIRST_TITLE),
        ("energy: 8", "energy: 0", FIRST_TITLE),
        ("energy: 8", "energy: 7.5", FIRST_TITLE),
        ("energy: 8", 'energy: "8"', FIRST_TITLE),
        ("status: downloaded", "status: [downloaded]", FIRST_TITLE),
        ("  key: null\n", "", SECOND_TITLE),
        ("  energy: 7\n", "", SECOND_TITLE),
        ("  genre: alpha\n  bpm: null", "  bpm: null", SECOND_TITLE),
        ('  artist: "Pedro Sampaio & MC Pedrinho"\n', "", FIRST_TITLE),
        ('artist: "Pedro Sampaio & MC Pedrinho"', "artist:", FIRST_TITLE),
        ('title: "Dançarina"', "title: 5", "- title: 5"),
        ('title: "Dançarina"', "title: [a]", "- title: [a]"),
        ("tags: [funk, singalong]", "tags: {a: b}", FIRST_TITLE),
    ],
    ids=[
        "missing-status", "bad-status", "bpm-string", "bpm-zero", "key-number", "key-letter",
        "energy-eleven", "energy-bool", "unknown-key", "empty-title", "missing-bpm", "tags-scalar",
        "bpm-301", "bpm-float", "bpm-bool", "bpm-list", "key-zero", "key-lowercase", "key-int",
        "key-list", "energy-zero", "energy-float", "energy-string", "status-list", "missing-key",
        "missing-energy", "missing-genre", "missing-artist", "null-artist", "title-int",
        "title-list", "tags-mapping",
    ],
)  # fmt: skip
def test_track_schema(mini_repo, old, new, anchor):
    mini_repo.edit(ALPHA, old, new)
    line = mini_repo.line_of(ALPHA, anchor)
    assert mini_repo.findings("track-schema") == [(ALPHA, line, "track-schema")]
    # No other pool rule reports the same mistake, and none raises on the wrong type.
    assert pool_findings(mini_repo) == [(ALPHA, line, "track-schema")]


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("bpm: 135", "bpm: 1"),
        ("bpm: 135", "bpm: 300"),
        ("key: 8A", "key: 12B"),
        ("key: 8A", "key: 1A"),
        ("energy: 8", "energy: 1"),
        ("energy: 8", "energy: 10"),
        ("status: downloaded", "status: organized"),
        ("tags: [funk, singalong]", "tags: []"),
        (
            'notes: "opens the block"',
            'notes: "opens the block"\n  remixer: ""\n  duration: "3:20"\n  year: 2024\n  source: beatport',
        ),
    ],
    ids=["bpm-1", "bpm-300", "key-12B", "key-1A", "energy-1", "energy-10", "organized", "no-tags", "optional-keys"],
)  # fmt: skip
def test_track_schema_accepts_the_limits_and_the_optional_keys(mini_repo, old, new):
    mini_repo.edit(ALPHA, old, new)
    assert pool_findings(mini_repo) == []


def test_track_schema_reports_each_problem_of_an_entry(mini_repo):
    mini_repo.edit(ALPHA, "status: downloaded", "status: lost\n  artsit: x")
    mini_repo.edit(ALPHA, "energy: 8", "energy: 11")
    line = mini_repo.line_of(ALPHA, FIRST_TITLE)
    assert mini_repo.findings("track-schema") == [(ALPHA, line, "track-schema")] * 3


@pytest.mark.parametrize(
    ("old", "new", "fragments"),
    [
        ("  status: to-download\n", "", ["missing key 'status'"]),
        ("status: to-download", "status: lost", ["status 'lost'"]),
        ("bpm: 135", 'bpm: "135"', ["bpm '135'", "integer"]),
        ("bpm: 135", "bpm: 0", ["bpm 0", "1 to 300"]),
        ("key: 8A", "key: 13A", ["key '13A'", "Camelot"]),
        ("key: 8A", "key: 8C", ["key '8C'", "Camelot"]),
        ("energy: 8", "energy: 11", ["energy 11", "1 to 10"]),
        ("energy: 8", "energy: yes", ["energy True", "integer"]),
        ('  notes: "opens the block"\n', '  notes: "x"\n  artsit: "x"\n', ["unknown key 'artsit'"]),
        ('title: "Dançarina"', 'title: ""', ["title ''", "non-empty string"]),
        ("  bpm: null\n", "", ["missing key 'bpm'"]),
        ("tags: [funk, singalong]", "tags: funk", ["tags 'funk'", "list"]),
    ],
    ids=[
        "missing-status", "bad-status", "bpm-string", "bpm-zero", "key-number", "key-letter",
        "energy-eleven", "energy-bool", "unknown-key", "empty-title", "missing-bpm", "tags-scalar",
    ],
)  # fmt: skip
def test_track_schema_messages_name_the_offender(mini_repo, old, new, fragments):
    mini_repo.edit(ALPHA, old, new)
    [message] = pool_messages(mini_repo, "track-schema")
    for fragment in fragments:
        assert fragment in message


def test_pool_rules_never_raise_on_a_non_mapping_entry(mini_repo):
    # The loader keeps such a pool out of `repo.pools`, so build the case by hand.
    repo = load_repo(mini_repo.root)
    repo.pools[0].entries.append("a bare string")
    pool_rules = {fn.rule_id: fn for fn in check_repo.RULES if fn.rule_id in POOL_RULES}
    assert set(pool_rules) == POOL_RULES
    found = {rule_id: list(fn(repo)) for rule_id, fn in pool_rules.items()}
    assert [(f.path, f.line, f.message) for f in found.pop("track-schema")] == [
        (ALPHA, 0, "entry 'a bare string' is not a mapping")
    ]
    assert found == {rule_id: [] for rule_id in POOL_RULES - {"track-schema"}}


# ---- track-genre-matches-pool ----

BETA_GENRE = ("  genre: alpha\n  bpm: null", "  genre: beta\n  bpm: null")  # the second entry's


def test_track_genre_matches_pool(mini_repo):
    mini_repo.edit(ALPHA, *BETA_GENRE)
    line = mini_repo.line_of(ALPHA, SECOND_TITLE)
    assert pool_findings(mini_repo) == [(ALPHA, line, "track-genre-matches-pool")]


def test_track_genre_matches_pool_message_names_both(mini_repo):
    mini_repo.edit(ALPHA, *BETA_GENRE)
    assert pool_messages(mini_repo, "track-genre-matches-pool") == [
        "genre 'beta' is not 'alpha', the pool it is in"
    ]


@pytest.mark.parametrize("genre", ["5", "[alpha]", "null", "ALPHA", "alpha-sub"])
def test_track_genre_matches_pool_flags_any_other_value(mini_repo, genre):
    mini_repo.edit(ALPHA, BETA_GENRE[0], f"  genre: {genre}\n  bpm: null")
    line = mini_repo.line_of(ALPHA, SECOND_TITLE)
    assert pool_findings(mini_repo) == [(ALPHA, line, "track-genre-matches-pool")]


def test_track_genre_matches_pool_leaves_a_missing_genre_to_track_schema(mini_repo):
    mini_repo.edit(ALPHA, BETA_GENRE[0], "  bpm: null")
    line = mini_repo.line_of(ALPHA, SECOND_TITLE)
    assert pool_findings(mini_repo) == [(ALPHA, line, "track-schema")]


# ---- track-title-first ----


def test_track_title_first(mini_repo):
    mini_repo.edit(ALPHA, f'{SECOND_TITLE}\n  artist: "Chiclete com Banana"', SWAPPED)
    line = mini_repo.line_of(ALPHA, SWAPPED)
    assert pool_findings(mini_repo) == [(ALPHA, line, "track-title-first")]


def test_track_title_first_message(mini_repo):
    mini_repo.edit(ALPHA, f'{SECOND_TITLE}\n  artist: "Chiclete com Banana"', SWAPPED)
    assert pool_messages(mini_repo, "track-title-first") == [
        "entry does not start with a `- title:` line at column 0"
    ]


FLOW_ENTRY = (
    '- {title: "Voa Voa (Ao Vivo)", artist: "Chiclete com Banana", genre: alpha, bpm: null,'
    " key: null, energy: 7, status: to-download}"
)


@pytest.mark.parametrize(
    ("old", "new", "anchor"),
    [
        (SECOND_ENTRY, SECOND_ENTRY.replace("- t", "-  t").replace("\n  ", "\n   "), '-  title: "Voa'),
        (SECOND_TITLE, '-\n  title: "Voa Voa (Ao Vivo)"', '  title: "Voa'),
        (SECOND_ENTRY, FLOW_ENTRY + "\n", "- {title:"),
    ],
    ids=["extra-space", "dash-on-its-own-line", "flow-mapping"],
)
def test_track_title_first_wants_the_exact_line(mini_repo, old, new, anchor):
    """`nextrack_tags.py` is told where an entry starts by a `- title:` line."""
    mini_repo.edit(ALPHA, old, new)
    line = mini_repo.line_of(ALPHA, anchor)
    assert pool_findings(mini_repo) == [(ALPHA, line, "track-title-first")]


def test_track_title_first_counts_title_lines_that_are_not_entries(mini_repo):
    # PyYAML lets a quoted string continue at column 0. The library tool would take
    # that `- title:` line for an entry, so the number of lines and entries differ.
    mini_repo.edit(ALPHA, 'notes: "opens the block"', 'notes: "opens\n- title: fake"')
    line = mini_repo.line_of(ALPHA, "- title: fake")
    assert pool_findings(mini_repo) == [(ALPHA, line, "track-title-first")]
    assert "not the start of an entry" in pool_messages(mini_repo, "track-title-first")[0]


def test_track_title_first_allows_comments_and_blank_lines_between_entries(mini_repo):
    mini_repo.edit(ALPHA, f"\n{SECOND_TITLE}", f"\n# um comentário\n\n{SECOND_TITLE}")
    assert pool_findings(mini_repo) == []


# ---- track-unique ----


def test_track_unique_within_a_pool(mini_repo):
    copy = FIRST_ENTRY.replace("Dançarina", "DANÇARINA")
    mini_repo.write(ALPHA, mini_repo.read(ALPHA) + "\n" + copy + "\n")
    assert mini_repo.line_of(ALPHA, FIRST_TITLE) == 3
    line = mini_repo.line_of(ALPHA, '- title: "DANÇARINA"')
    assert pool_findings(mini_repo) == [(ALPHA, line, "track-unique")]
    [message] = pool_messages(mini_repo, "track-unique")
    assert "tracks/alpha.yml:3" in message


def test_track_unique_across_pools(mini_repo):
    mini_repo.write("tracks/beta.yml", FIRST_ENTRY.replace("genre: alpha", "genre: beta") + "\n")
    assert pool_findings(mini_repo) == [("tracks/beta.yml", 1, "track-unique")]
    [message] = pool_messages(mini_repo, "track-unique")
    assert "tracks/alpha.yml:3" in message


def test_track_unique_reports_every_later_copy_against_the_first(mini_repo):
    copy = SECOND_ENTRY.replace("genre: alpha", "genre: beta").replace("Chiclete com", "CHICLETE  com")
    mini_repo.write("tracks/beta.yml", "# beta\n" + copy + "\n" + copy)
    first = mini_repo.line_of(ALPHA, SECOND_TITLE)
    findings = [(f.path, f.line, f.message) for f in check(mini_repo.root) if f.rule == "track-unique"]
    assert [(path, line) for path, line, _message in findings] == [
        ("tracks/beta.yml", n) for n in title_lines(mini_repo.read("tracks/beta.yml"))
    ]
    assert len(findings) == 2
    assert all(f"tracks/alpha.yml:{first}" in message for _path, _line, message in findings)


@pytest.mark.parametrize(
    ("artist", "title"),
    [
        ('"Pedro Sampaio  &  MC Pedrinho"', '"Dancarina"'),
        ('"pedro sampaio mc pedrinho"', '"DANÇARINA!"'),
        ('"Pedro Sampaio & MC Pedrinho"', '"Dançarina"'),
    ],
    ids=["accent-and-spaces", "case-and-punctuation", "exact"],
)
def test_track_unique_compares_the_normalized_pair(mini_repo, artist, title):
    mini_repo.write("tracks/beta.yml", track(title=title, artist=artist))
    assert pool_findings(mini_repo) == [("tracks/beta.yml", 1, "track-unique")]


@pytest.mark.parametrize(
    ("artist", "title"),
    [
        ('"Pedro Sampaio & MC Pedrinho"', '"Outra Música"'),
        ('"Outro Artista"', '"Dançarina"'),
        ('"Pedro Sampaio"', '"Dançarina"'),
        ('"Pedro Sampaio & MC Pedrinho"', '"Dançarina (Remix)"'),
    ],
    ids=["same-artist", "same-title", "shorter-artist", "longer-title"],
)
def test_track_unique_needs_both_artist_and_title_to_match(mini_repo, artist, title):
    mini_repo.write("tracks/beta.yml", track(title=title, artist=artist))
    assert pool_findings(mini_repo) == []


def test_track_unique_skips_entries_whose_artist_or_title_is_not_a_string(mini_repo):
    mini_repo.write("tracks/beta.yml", track(title="5", artist="5") + "\n" + track(title="5", artist="5"))
    assert mini_repo.findings("track-unique") == []
    assert {rule for _path, _line, rule in pool_findings(mini_repo)} == {"track-schema"}


# ---- a pool with no tracks ----


def test_comment_only_pool_is_clean(mini_repo):
    mini_repo.write("tracks/beta.yml", "# beta — vazio por enquanto\n")
    assert mini_repo.findings() == []


# -------------------------------------------------------------- block rules ----

BLOCK = "blocks/alpha-festa.md"
FRONTMATTER = "block-frontmatter"
TRACKLIST = "block-tracklist-resolves"
BRIDGES = "block-bridges-are-edges"
BLOCK_RULES = {FRONTMATTER, TRACKLIST, BRIDGES}
# Lines of the block; the new lines in the tests go right after them.
TRACK_1 = "1. Pedro Sampaio — Dançarina        · e8  abre"
TRACK_2 = "2. Chiclete com Banana — Voa Voa    · e7"
BRIDGE_IN = "← `beta`: hard cut no refrão."
BRIDGE_OUT = "- → `beta`: echo out."
GHOST = "3. Nobody — Ghost Track · e5"
FUNCTIONS = ["warmup", "build", "peak", "plateau", "breakdown", "cooldown"]
STYLES = ["continuous", "open-format", "hybrid"]


def block_findings(mini_repo):
    """`(path, line, rule)` of every finding of the three block rules."""
    return [f for f in mini_repo.findings() if f[2] in BLOCK_RULES]


def block_messages(mini_repo, rule_id):
    return [f.message for f in check(mini_repo.root) if f.rule == rule_id]


def add_after(mini_repo, anchor, new_line, rel=BLOCK):
    """Insert `new_line` after the line `anchor` of a block; return its line number."""
    mini_repo.edit(rel, anchor + "\n", f"{anchor}\n{new_line}\n")
    return mini_repo.line_of(rel, new_line)


def without_front_matter(mini_repo):
    """The block's text from its first body line on, without both `---` lines."""
    return mini_repo.read(BLOCK).split("---\n", 2)[2]


def block_rule(rule_id):
    (fn,) = (fn for fn in check_repo.RULES if fn.rule_id == rule_id)
    return fn


def test_block_rules_are_registered():
    assert {fn.rule_id for fn in check_repo.RULES} >= BLOCK_RULES


# ---- helpers: core, artist_tokens, section ----


def test_joiners():
    assert check_repo.JOINERS == {"feat", "ft", "x", "e", "and", "com", "pres", "vs"}


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Voa Voa (Ao Vivo)", "voa voa"),
        ("Dançarina [Salsa Version]", "dancarina"),
        ("Song (A) Name [B]", "song name"),
        ("(Remix)", ""),
        ("Don't You Worry Child", "don t you worry child"),
        ("Title (feat. X (Remix))", "title"),
        ("Title (unclosed", "title unclosed"),
        ("Plain", "plain"),
    ],
)
def test_core(title, expected):
    assert check_repo.core(title) == expected


@pytest.mark.parametrize(
    ("artist", "expected"),
    [
        ("Pedro Sampaio & MC Pedrinho", {"pedro", "sampaio", "mc", "pedrinho"}),
        ("Chiclete com Banana", {"chiclete", "banana"}),
        (
            "Artist feat. Other ft. Third vs Fourth x Fifth and Sixth e Sétimo pres. Oitavo",
            {"artist", "other", "third", "fourth", "fifth", "sixth", "setimo", "oitavo"},
        ),
        ("X", set()),
        ("ÁÉÍ Ôu", {"aei", "ou"}),
        ("", set()),
    ],
)
def test_artist_tokens(artist, expected):
    assert check_repo.artist_tokens(artist) == expected


SECTIONED = [
    (1, "intro"),
    (2, "## Bridge in"),
    (3, "a"),
    (4, "### sub"),
    (5, "## Tracklist (primary)"),
    (6, "1. x"),
    (7, "## Bridge out"),
    (8, "b"),
    (9, "## Bridge out (again)"),
    (10, "c"),
]


@pytest.mark.parametrize(
    ("body", "prefix", "expected"),
    [
        (SECTIONED, "## Bridge in", [(3, "a"), (4, "### sub")]),  # `###` does not end it
        (SECTIONED, "## Tracklist", [(6, "1. x")]),
        (SECTIONED, "## Bridge out", [(8, "b")]),  # the first heading only
        (SECTIONED[:3], "## Bridge in", [(3, "a")]),  # runs to the end of the file
        (SECTIONED[:2], "## Bridge in", []),
        (SECTIONED, "## Swap", None),
        ([(1, "see ## Tracklist")], "## Tracklist", None),  # the heading starts the line
        ([], "## Tracklist", None),
    ],
    ids=["h3-inside", "prefix", "first-only", "to-the-end", "empty", "absent", "mid-line", "no-body"],
)
def test_section(body, prefix, expected):
    assert check_repo.section(body, prefix) == expected


# ---- block-frontmatter ----

FRONT_PROBLEMS = [
    # The table of the brief.
    ("function: peak", "function: party", "function"),
    ("style: open-format", "style: blend", "style"),
    ("duration: 30m", "duration: 30 minutes", "duration"),
    ("genres: [alpha]", "genres: [delta]", "genre-unknown"),
    ("genres: [alpha]", "genres: alpha", "genres-scalar"),
    ("bpm: [100, 135]", "bpm: [135, 100]", "bpm-reversed"),
    ("energy: [7, 8]", "energy: [0, 8]", "energy-zero"),
    ("key_journey: TBD\n", "", "no-key_journey"),
    ("lightshow: null", "lightshow: null\nmood: hot", "unknown-key"),
    ("lightshow: null", "lightshow: ../lightshows/alpha-festa.md", "lightshow-missing-file"),
    # The other keys, missing.
    ("name: Alpha Festa\n", "", "no-name"),
    ("function: peak\n", "", "no-function"),
    ("style: open-format\n", "", "no-style"),
    ("duration: 30m\n", "", "no-duration"),
    ("genres: [alpha]\n", "", "no-genres"),
    ("bpm: [100, 135]\n", "", "no-bpm"),
    ("energy: [7, 8]\n", "", "no-energy"),
    ("lightshow: null\n", "", "no-lightshow"),
    # Wrong values and wrong YAML types: a finding, never a TypeError.
    ("function: peak", "function: [peak]", "function-list"),
    ("function: peak", "function: yes", "function-bool"),
    ("function: peak", "function:", "function-null"),
    ("function: peak", "function: Peak", "function-case"),
    ("style: open-format", "style: [hybrid]", "style-list"),
    ("style: open-format", "style: {a: b}", "style-mapping"),
    ("duration: 30m", "duration: 30", "duration-int"),
    ("duration: 30m", "duration: m", "duration-no-digits"),
    ("duration: 30m", "duration: 30M", "duration-case"),
    ("duration: 30m", "duration: 1h30m", "duration-two-units"),
    ("duration: 30m", "duration: [30m]", "duration-list"),
    ("duration: 30m", "duration:", "duration-null"),
    ("genres: [alpha]", "genres: []", "genres-empty"),
    ("genres: [alpha]", "genres:", "genres-null"),
    ("genres: [alpha]", "genres: [5]", "genres-int"),
    ("genres: [alpha]", "genres: [[alpha]]", "genres-nested"),
    ("genres: [alpha]", "genres: [{a: b}]", "genres-mapping-item"),
    ("genres: [alpha]", "genres: [alpha, delta]", "genres-one-unknown"),
    ("genres: [alpha]", "genres: {alpha: 1}", "genres-mapping"),
    ("bpm: [100, 135]", "bpm: [0, 135]", "bpm-zero"),
    ("bpm: [100, 135]", 'bpm: "100-135"', "bpm-string"),
    ("bpm: [100, 135]", "bpm: [100]", "bpm-one"),
    ("bpm: [100, 135]", "bpm: [100, 135, 140]", "bpm-three"),
    ("bpm: [100, 135]", "bpm: [100.5, 135]", "bpm-float"),
    ("bpm: [100, 135]", "bpm: [true, 135]", "bpm-bool"),
    ("bpm: [100, 135]", "bpm: 120", "bpm-scalar"),
    ("energy: [7, 8]", "energy: [7, 11]", "energy-eleven"),
    ("energy: [7, 8]", "energy: 8", "energy-scalar"),
    ("energy: [7, 8]", "energy: [7, true]", "energy-bool"),
    ("energy: [7, 8]", 'energy: [7, "8"]', "energy-string"),
    ("key_journey: TBD", "key_journey: [8A]", "key_journey-list"),
    ("key_journey: TBD", "key_journey: 8", "key_journey-int"),
    ("key_journey: TBD", "key_journey:", "key_journey-null"),
    ("lightshow: null", "lightshow: 5", "lightshow-int"),
    ("lightshow: null", "lightshow: yes", "lightshow-bool"),
    ("lightshow: null", 'lightshow: ""', "lightshow-empty"),
    ("lightshow: null", "lightshow: [a.md]", "lightshow-list"),
    ("lightshow: null", "lightshow: /etc/passwd", "lightshow-absolute"),
    ("lightshow: null", "lightshow: ../lightshows/missing.md", "lightshow-not-there"),
]


@pytest.mark.parametrize(
    ("old", "new"),
    [case[:2] for case in FRONT_PROBLEMS],
    ids=[case[2] for case in FRONT_PROBLEMS],
)
def test_block_frontmatter(mini_repo, old, new):
    mini_repo.edit(BLOCK, old, new)
    assert mini_repo.findings(FRONTMATTER) == [(BLOCK, 2, FRONTMATTER)]
    # No other block rule reports the same mistake, and none raises on the wrong type.
    assert block_findings(mini_repo) == [(BLOCK, 2, FRONTMATTER)]


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("energy: [7, 8]", "energy: [8, 7]"),  # a falling arc
        ("energy: [7, 8]", "energy: [1, 10]"),
        ("energy: [7, 8]", "energy: [5, 5]"),
        ("bpm: [100, 135]", "bpm: [100, 100]"),
        ("bpm: [100, 135]", "bpm: [1, 1000]"),
        ("duration: 30m", "duration: 2h"),
        ("duration: 30m", "duration: 120m"),
        ("duration: 30m", "duration: 0m"),
        ("genres: [alpha]", "genres: [alpha, beta]"),
        ("genres: [alpha]", "genres: [alpha, alpha]"),
        ("key_journey: TBD", "key_journey: 8A -> 9A -> 9B"),
        ("key_journey: TBD", 'key_journey: ""'),
        ("lightshow: null", "lightshow: ../lightshows/alpha-festa.md"),
        ("lightshow: null", "lightshow: ../README.md"),
        ("lightshow: null", "lightshow: ~"),
        ("lightshow: null", "lightshow: null  # -> ../lightshows/alpha-festa.md (futuro)"),
        *[("function: peak", f"function: {name}") for name in FUNCTIONS],
        *[("style: open-format", f"style: {name}") for name in STYLES],
    ],
)
def test_block_frontmatter_accepts(mini_repo, old, new):
    mini_repo.write("lightshows/alpha-festa.md", "# Alpha Festa\n")
    mini_repo.edit(BLOCK, old, new)
    assert mini_repo.findings() == []


def test_block_lightshow_is_resolved_relative_to_the_block(mini_repo):
    mini_repo.write("lightshows/alpha-festa.md", "# Alpha Festa\n")  # relative to the repo root
    mini_repo.edit(BLOCK, "lightshow: null", "lightshow: lightshows/alpha-festa.md")
    assert mini_repo.findings(FRONTMATTER) == [(BLOCK, 2, FRONTMATTER)]
    mini_repo.write("blocks/lightshows/alpha-festa.md", "# Alpha Festa\n")  # relative to the block
    assert mini_repo.findings() == []


def test_block_frontmatter_reports_each_problem_of_a_block(mini_repo):
    mini_repo.edit(BLOCK, "function: peak", "function: party\nmood: hot")
    mini_repo.edit(BLOCK, "key_journey: TBD\n", "")
    assert sorted(block_messages(mini_repo, FRONTMATTER)) == sorted(
        [
            "function 'party' is not one of warmup, build, peak, plateau, breakdown, cooldown",
            "unknown key 'mood'",
            "missing key 'key_journey'",
        ]
    )
    assert block_findings(mini_repo) == [(BLOCK, 2, FRONTMATTER)] * 3


def test_block_frontmatter_reports_each_unknown_genre(mini_repo):
    mini_repo.edit(BLOCK, "genres: [alpha]", "genres: [alpha, delta, 5]")
    assert block_messages(mini_repo, FRONTMATTER) == [
        "genre 'delta' is not a node id in genres/graph.yml",
        "genre 5 is not a node id in genres/graph.yml",
    ]


@pytest.mark.parametrize(
    ("old", "new", "fragments"),
    [
        ("function: peak", "function: party", ["function", "'party'", "peak"]),
        ("style: open-format", "style: blend", ["style", "'blend'", "open-format"]),
        ("duration: 30m", "duration: 30 minutes", ["duration", "'30 minutes'"]),
        ("genres: [alpha]", "genres: alpha", ["genres", "'alpha'", "list"]),
        ("bpm: [100, 135]", "bpm: [135, 100]", ["bpm", "[135, 100]", "min <= max"]),
        ("energy: [7, 8]", "energy: [0, 8]", ["energy", "[0, 8]", "1-10"]),
        ("key_journey: TBD", "key_journey: 8", ["key_journey", "8", "string"]),
        ("key_journey: TBD\n", "", ["missing key 'key_journey'"]),
        ("lightshow: null", "lightshow: null\nmood: hot", ["unknown key 'mood'"]),
        ("lightshow: null", "lightshow: 5", ["lightshow", "5", "path"]),
        ("lightshow: null", "lightshow: ../l/x.md", ["lightshow", "'../l/x.md'", "does not exist"]),
        ("lightshow: null", "lightshow: /etc/passwd", ["lightshow", "'/etc/passwd'", "relative"]),
    ],
)
def test_block_frontmatter_messages_name_the_offender(mini_repo, old, new, fragments):
    mini_repo.edit(BLOCK, old, new)
    (message,) = block_messages(mini_repo, FRONTMATTER)
    for fragment in fragments:
        assert fragment in message


def test_block_without_frontmatter(mini_repo):
    mini_repo.write(BLOCK, without_front_matter(mini_repo))
    assert mini_repo.findings() == [(BLOCK, 1, FRONTMATTER)]
    assert "---" in block_messages(mini_repo, FRONTMATTER)[0]


@pytest.mark.parametrize(
    "text",
    ["", "\n---\nname: x\n---\n", "## Feel\nOi.\n", "----\nname: x\n---\n"],
    ids=["empty-file", "blank-first-line", "no-yaml", "four-dashes"],
)
def test_block_that_does_not_start_with_front_matter_never_raises(mini_repo, text):
    mini_repo.write(BLOCK, text)
    found = block_findings(mini_repo)
    assert (BLOCK, 1, FRONTMATTER) in found
    assert {rule_id for _path, _line, rule_id in found} <= {FRONTMATTER, TRACKLIST}


def test_block_unclosed_frontmatter(mini_repo):
    mini_repo.edit(BLOCK, "lightshow: null\n---\n", "lightshow: null\n")
    assert mini_repo.findings("parse-error") == [(BLOCK, 0, "parse-error")]
    assert [f for f in mini_repo.findings() if f[2].startswith("block-")] == []


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("genres: [alpha]", "genres: [alpha"),  # YAML that does not parse
        ("energy: [7, 8]", "energy: [7, 8]\n  bad: indent"),
    ],
    ids=["bad-yaml", "bad-indent"],
)
def test_block_with_unparseable_frontmatter_is_skipped_by_every_block_rule(mini_repo, old, new):
    mini_repo.edit(BLOCK, old, new)
    assert [f[2] for f in mini_repo.findings() if f[0] == BLOCK] == ["parse-error"]


def test_block_frontmatter_checks_graph_ok_for_the_genres_only(mini_repo):
    mini_repo.edit(BLOCK, "genres: [alpha]", "genres: [delta]")
    repo = load_repo(mini_repo.root)
    fn = block_rule(FRONTMATTER)
    assert [f.line for f in fn(repo)] == [2]
    repo.graph_ok = False
    assert list(fn(repo)) == []  # `delta` cannot be judged without a graph
    repo.blocks[0].front["genres"] = "alpha"
    repo.blocks[0].front["function"] = "party"
    assert len(list(fn(repo))) == 2  # the other clauses still run


def test_a_graph_that_did_not_load_does_not_flood_the_block_rules(mini_repo):
    mini_repo.write("genres/graph.yml", "- alpha\n")
    assert [rule_id for _path, _line, rule_id in mini_repo.findings()] == ["parse-error"]


# ---- block-tracklist-resolves ----


def test_block_tracklist_unresolved(mini_repo):
    line = add_after(mini_repo, TRACK_2, GHOST)
    assert mini_repo.findings(TRACKLIST) == [(BLOCK, line, TRACKLIST)]
    assert block_findings(mini_repo) == [(BLOCK, line, TRACKLIST)]
    (message,) = block_messages(mini_repo, TRACKLIST)
    assert message.startswith("unresolved:")
    assert "'Nobody'" in message and "'Ghost Track'" in message


def test_block_tracklist_format(mini_repo):
    line = add_after(mini_repo, TRACK_2, "3. Nobody - Ghost Track · e5")
    assert mini_repo.findings(TRACKLIST) == [(BLOCK, line, TRACKLIST)]
    assert block_findings(mini_repo) == [(BLOCK, line, TRACKLIST)]
    (message,) = block_messages(mini_repo, TRACKLIST)
    assert message.startswith("format:")
    assert "3. Nobody - Ghost Track · e5" in message


def test_block_tracklist_heading_missing(mini_repo):
    mini_repo.edit(BLOCK, "## Tracklist (primary)", "## Lista")
    assert mini_repo.findings(TRACKLIST) == [(BLOCK, 0, TRACKLIST)]
    assert block_findings(mini_repo) == [(BLOCK, 0, TRACKLIST)]
    assert "## Tracklist" in block_messages(mini_repo, TRACKLIST)[0]


def test_block_tracklist_folds_case_and_accents(mini_repo):
    mini_repo.edit(BLOCK, TRACK_1, "1. PEDRO SAMPAIO — DANCARINA · e8")
    assert mini_repo.findings() == []


@pytest.mark.parametrize(
    "heading",
    ["## Tracklist", "## Tracklist (primary)", "## Tracklist — set de teste", "## Tracklist(x)"],
)
def test_block_tracklist_heading_only_has_to_start_with_tracklist(mini_repo, heading):
    mini_repo.edit(BLOCK, "## Tracklist (primary)", heading)
    assert mini_repo.findings() == []


@pytest.mark.parametrize(
    "heading", ["### Tracklist", "# Tracklist", "## tracklist", "##Tracklist", " ## Tracklist"]
)
def test_block_tracklist_heading_must_be_a_level_2_tracklist_heading(mini_repo, heading):
    mini_repo.edit(BLOCK, "## Tracklist (primary)", heading)
    assert mini_repo.findings(TRACKLIST) == [(BLOCK, 0, TRACKLIST)]


@pytest.mark.parametrize(
    "line",
    [
        "3. Nobody – Ghost Track · e5",  # en dash
        "3. Nobody -- Ghost Track · e5",
        "3. Nobody — Ghost Track e5",  # no middle dot
        "3. Nobody — Ghost Track",
        "3. Nobody — Ghost Track . e5",  # a period, not a middle dot
        "3. Nobody — Ghost Track• e5",
        "3.Nobody — Ghost Track · e5",  # no space after the number
        "3. — Ghost Track · e5",  # no artist
        "3. Nobody — · e5",  # no title
        "3. Nobody — Ghost Track· e5",  # the dot needs a space before it
        "3. Nobody",
        "3.",
    ],
)
def test_block_tracklist_format_findings(mini_repo, line):
    line_no = add_after(mini_repo, TRACK_2, line)
    assert mini_repo.findings(TRACKLIST) == [(BLOCK, line_no, TRACKLIST)]
    assert block_messages(mini_repo, TRACKLIST)[0].startswith("format:")


@pytest.mark.parametrize(
    "line",
    [
        "(abre forte, sobe no 3)",
        "- 3. Nobody - Ghost Track",
        "   3. Nobody - Ghost Track",  # indented: does not start with `<digits>.`
        "3) Nobody - Ghost Track",
        "3 Nobody - Ghost Track",
        "x3. Nobody - Ghost Track",
        "1→2: blend on the break",
        "Nota: 3. Nobody - Ghost Track",
    ],
)
def test_block_tracklist_ignores_lines_that_are_not_numbered(mini_repo, line):
    add_after(mini_repo, TRACK_2, line)
    assert mini_repo.findings() == []


def test_block_tracklist_only_looks_inside_its_section(mini_repo):
    # A bad numbered line under another heading, before and after the tracklist.
    mini_repo.edit(BLOCK, "Bloco de teste.", "Bloco de teste.\n1. Nobody - Ghost Track")
    mini_repo.edit(BLOCK, "- Ver `alpha-festa.md`", "1. Nobody - Ghost Track\n- Ver `alpha-festa.md`")
    assert mini_repo.findings() == []


def test_block_tracklist_without_numbered_lines_is_fine(mini_repo):
    mini_repo.edit(BLOCK, TRACK_1 + "\n", "")
    mini_repo.edit(BLOCK, TRACK_2 + "\n", "A ordem fica pra pista.\n")
    assert mini_repo.findings() == []


def test_block_tracklist_reports_every_bad_line(mini_repo):
    first = add_after(mini_repo, TRACK_2, GHOST)
    second = add_after(mini_repo, GHOST, "4. Nobody - Ghost Track · e5")
    third = add_after(mini_repo, "4. Nobody - Ghost Track · e5", "5. Other Nobody — Ghost Two · e5")
    assert mini_repo.findings(TRACKLIST) == [(BLOCK, n, TRACKLIST) for n in (first, second, third)]
    kinds = [message.split(":")[0] for message in block_messages(mini_repo, TRACKLIST)]
    assert kinds == ["unresolved", "format", "unresolved"]


@pytest.mark.parametrize(
    ("anchor", "line"),
    [
        (TRACK_1, "1. Pedro Sampaio — Dançarina (Nicky Jam Remix) · e8"),  # () and [] are dropped
        (TRACK_1, "1. Pedro Sampaio — Dançarina [Salsa Version] · e8"),
        (TRACK_1, "1. Pedro Sampaio, Anitta, MC Pedrinho — Dançarina · e8"),  # pool artist is a subset
        (TRACK_1, "1. Pedro — Dançarina · e8"),  # line artist is a subset
        (TRACK_1, "1. Pedro Sampaio feat. MC Pedrinho — Dançarina · e8"),  # joiners are no tokens
        (TRACK_1, "1. MC Pedrinho x Pedro Sampaio — Dançarina · e8"),  # token order is free
        (TRACK_1, "1. Pedro Sampaio — Dancarina · e8"),
        (TRACK_2, "2. Chiclete Banana — Voa Voa [Ao Vivo] · e7"),
        (TRACK_2, "2. Chiclete com Banana — Voa · e7"),  # a prefix that ends at a word
        (TRACK_2, "2. Chiclete com Banana — Voa Voa Ao Vivo Parte 2 · e7"),  # pool title is the prefix
        (TRACK_2, "2. Banana — Voa Voa (Ao Vivo) · e7"),
    ],
)
def test_block_tracklist_matching_accepts(mini_repo, anchor, line):
    mini_repo.edit(BLOCK, anchor, line)
    assert mini_repo.findings() == []


@pytest.mark.parametrize(
    ("anchor", "line"),
    [
        (TRACK_1, "1. Anitta — Dançarina · e8"),  # artist shares no token with the pool
        (TRACK_1, "1. Pedro Samp — Dançarina · e8"),  # tokens are whole words
        (TRACK_1, "1. Pedro Sampaio — Galopa · e8"),  # title does not match
        (TRACK_1, "1. Pedro Sampaio — Dança · e8"),  # a prefix has to end at a word: "dancarina"
        (TRACK_1, "1. Pedro Sampaio — Dancarinas · e8"),
        (TRACK_1, "1. Pedro Sampaio — Rina · e8"),  # the title must start the pool title
        (TRACK_1, "1. Pedro Sampaio — (Remix) · e8"),  # nothing is left of the title
        (TRACK_2, "2. Chiclete com Banana — Vo · e7"),
        (TRACK_2, "2. Chiclete com Banana — Voa Vo · e7"),
        (TRACK_2, "2. Pedro Sampaio — Voa Voa · e7"),  # right title, another artist's track
        (TRACK_2, "2. Chiclete com Banana — Dançarina · e7"),
    ],
)
def test_block_tracklist_matching_rejects(mini_repo, anchor, line):
    mini_repo.edit(BLOCK, anchor, line)
    line_no = mini_repo.line_of(BLOCK, line)
    assert mini_repo.findings(TRACKLIST) == [(BLOCK, line_no, TRACKLIST)]
    assert block_messages(mini_repo, TRACKLIST)[0].startswith("unresolved:")


def test_block_tracklist_matches_a_track_in_any_pool(mini_repo):
    mini_repo.write("tracks/beta.yml", track(title='"Galopa"', artist='"Pedro Sampaio"'))
    add_after(mini_repo, TRACK_2, "3. Pedro Sampaio — Galopa · e8")
    assert mini_repo.findings() == []


def test_block_tracklist_needs_one_track_to_match_both_artist_and_title(mini_repo):
    # The artist of one track and the title of another is not a match.
    mini_repo.write("tracks/beta.yml", track(title='"Galopa"', artist='"Anitta"'))
    line = add_after(mini_repo, TRACK_2, "3. Pedro Sampaio — Galopa · e8")
    assert mini_repo.findings(TRACKLIST) == [(BLOCK, line, TRACKLIST)]


def test_block_tracklist_does_not_match_tracks_whose_artist_or_title_is_not_a_string(mini_repo):
    # `norm` gives "" for them, and an empty token set is a subset of every artist.
    mini_repo.write(
        "tracks/beta.yml",
        track(title="5", artist="5") + "\n" + track(title="null", artist="[a]"),
    )
    line = add_after(mini_repo, TRACK_2, "3. 5 — 5 · e5")
    assert mini_repo.findings(TRACKLIST) == [(BLOCK, line, TRACKLIST)]


def test_block_tracklist_never_raises_on_a_non_mapping_entry(mini_repo):
    # The loader keeps such a pool out of `repo.pools`, so build the case by hand.
    repo = load_repo(mini_repo.root)
    repo.pools[0].entries.append("a bare string")
    repo.pools[0].entries.append({"title": 5, "artist": ["x"], "__line__": 1})
    assert list(block_rule(TRACKLIST)(repo)) == []


def test_block_tracklist_does_not_need_the_graph(mini_repo):
    mini_repo.write("genres/graph.yml", "- alpha\n")
    line = add_after(mini_repo, TRACK_2, GHOST)
    assert mini_repo.findings(TRACKLIST) == [(BLOCK, line, TRACKLIST)]


def test_block_tracklist_runs_on_a_block_without_front_matter(mini_repo):
    body = without_front_matter(mini_repo)
    # Appended after the Bridge out: not in the tracklist.
    mini_repo.write(BLOCK, body + GHOST + "\n")
    assert mini_repo.findings() == [(BLOCK, 1, FRONTMATTER)]
    mini_repo.write(BLOCK, body.replace(TRACK_2, GHOST))
    assert [f[2] for f in mini_repo.findings() if f[0] == BLOCK] == [FRONTMATTER, TRACKLIST]


def test_block_tracklist_does_not_cascade_from_a_broken_pool(mini_repo):
    mini_repo.write(ALPHA, "- title: [\n")
    add_after(mini_repo, TRACK_2, GHOST)
    bad = add_after(mini_repo, GHOST, "4. Nobody - Ghost Track · e5")
    assert [(path, rule_id) for path, _line, rule_id in mini_repo.findings("parse-error")] == [
        (ALPHA, "parse-error")
    ]
    # No line is unresolved, not even the valid ones the pool used to resolve, but the
    # format of a line does not depend on any pool.
    assert mini_repo.findings(TRACKLIST) == [(BLOCK, bad, TRACKLIST)]
    assert block_messages(mini_repo, TRACKLIST)[0].startswith("format:")


def test_block_tracklist_does_not_cascade_from_any_broken_pool(mini_repo):
    mini_repo.write("tracks/beta.yml", "- title: [\n")  # not the pool with the block's tracks
    add_after(mini_repo, TRACK_2, GHOST)
    assert mini_repo.findings(TRACKLIST) == []


# ---- block-bridges-are-edges ----


def test_block_bridge_in_without_an_edge(mini_repo):
    line = add_after(mini_repo, BRIDGE_IN, "← `gamma`: corte.")
    assert mini_repo.findings(BRIDGES) == [(BLOCK, line, BRIDGES)]  # there is no gamma -> alpha
    assert block_findings(mini_repo) == [(BLOCK, line, BRIDGES)]
    assert block_messages(mini_repo, BRIDGES) == ["no edge gamma -> alpha for Bridge in `gamma`"]


def test_block_bridge_out_with_a_weak_edge_counts(mini_repo):
    add_after(mini_repo, BRIDGE_OUT, "- → `gamma`: lift.")  # alpha -> gamma is weak
    assert mini_repo.findings() == []


def test_block_bridge_to_the_blocks_own_genre_is_skipped(mini_repo):
    add_after(mini_repo, BRIDGE_OUT, "Fica em `alpha` mesmo.")
    add_after(mini_repo, BRIDGE_IN, "Vem de `alpha` também.")
    assert mini_repo.findings() == []


def test_block_bridge_out_without_an_edge(mini_repo):
    mini_repo.edit(BLOCK, "genres: [alpha]", "genres: [gamma]")  # gamma -> beta only
    line = add_after(mini_repo, BRIDGE_OUT, "- → `alpha`: volta.")
    assert mini_repo.findings(BRIDGES) == [(BLOCK, line, BRIDGES)]
    assert block_messages(mini_repo, BRIDGES) == ["no edge gamma -> alpha for Bridge out `alpha`"]


def test_block_bridge_direction_matters(mini_repo):
    # With genres [gamma]: alpha -> gamma exists, gamma -> alpha does not.
    mini_repo.edit(BLOCK, "genres: [alpha]", "genres: [gamma]")
    add_after(mini_repo, BRIDGE_IN, "← `alpha`: vem do alpha.")  # alpha -> gamma: fine
    out_line = add_after(mini_repo, BRIDGE_OUT, "- → `alpha`: vai pro alpha.")  # gamma -> alpha: no
    assert mini_repo.findings(BRIDGES) == [(BLOCK, out_line, BRIDGES)]


@pytest.mark.parametrize("genres", ["[beta, gamma]", "[gamma, beta]"])
def test_block_bridge_needs_an_edge_to_or_from_any_one_genre(mini_repo, genres):
    # Bridge in `alpha`: alpha -> beta and alpha -> gamma both exist.
    # Bridge out `alpha`: beta -> alpha exists, gamma -> alpha does not: one genre is enough.
    mini_repo.edit(BLOCK, "genres: [alpha]", f"genres: {genres}")
    add_after(mini_repo, BRIDGE_IN, "← `alpha`: vem do alpha.")
    add_after(mini_repo, BRIDGE_OUT, "- → `alpha`: volta pro alpha.")
    assert block_findings(mini_repo) == []


def test_block_bridge_message_names_all_the_genres(mini_repo):
    mini_repo.edit(BLOCK, "genres: [alpha]", "genres: [alpha, beta]")
    mini_repo.edit(GRAPH, GAMMA_NEIGHBORS, "    neighbors: []\n")  # gamma has no edge out now
    line = add_after(mini_repo, BRIDGE_IN, "← `gamma`: corte.")
    assert mini_repo.findings(BRIDGES) == [(BLOCK, line, BRIDGES)]
    assert block_messages(mini_repo, BRIDGES) == [
        "no edge gamma -> alpha or beta for Bridge in `gamma`"
    ]


@pytest.mark.parametrize(
    "token",
    ["alpha-festa.md", "Make U Sweat", "axe/", "Beta", "a_b", "-x", "x--y", " beta", "beta "],
)
def test_block_bridge_tokens_that_are_not_node_ids_are_skipped(mini_repo, token):
    add_after(mini_repo, BRIDGE_OUT, f"- `{token}` é um nome, não um node.")
    assert mini_repo.findings() == []


def test_block_bridge_node_id_that_is_not_a_node_is_a_finding(mini_repo):
    line = add_after(mini_repo, BRIDGE_OUT, "- → `delta`: nem existe.")
    assert mini_repo.findings(BRIDGES) == [(BLOCK, line, BRIDGES)]
    assert block_messages(mini_repo, BRIDGES) == [
        "Bridge out `delta` is not a node id in genres/graph.yml"
    ]


def test_block_bridges_check_every_token_on_a_line(mini_repo):
    line = add_after(mini_repo, BRIDGE_IN, "← `beta` ou `gamma` ou `beta`: corte.")
    assert mini_repo.findings(BRIDGES) == [(BLOCK, line, BRIDGES)]
    assert block_messages(mini_repo, BRIDGES) == ["no edge gamma -> alpha for Bridge in `gamma`"]


def test_block_bridges_only_look_inside_their_sections(mini_repo):
    mini_repo.edit(BLOCK, "Bloco de teste.", "Bloco de teste. Vem do `gamma`.")  # Feel
    mini_repo.edit(BLOCK, TRACK_2, TRACK_2 + "  `gamma`")  # Tracklist
    mini_repo.write(BLOCK, mini_repo.read(BLOCK) + "\n## Notas\n- `gamma` e `delta`.\n")
    assert mini_repo.findings() == []


def test_block_bridge_section_ends_at_the_next_level_2_heading_only(mini_repo):
    mini_repo.edit(
        BLOCK,
        "## Tracklist (primary)",
        "### Sub\n← `gamma`: ainda dentro.\n## Tracklist (primary)",
    )
    line = mini_repo.line_of(BLOCK, "← `gamma`: ainda dentro.")
    assert mini_repo.findings(BRIDGES) == [(BLOCK, line, BRIDGES)]


@pytest.mark.parametrize("heading", ["## Bridge out", "## Bridge out (opcional)", "## Bridge outro"])
def test_block_bridge_headings_only_have_to_start_with_the_name(mini_repo, heading):
    mini_repo.edit(BLOCK, "## Bridge out", heading)
    line = add_after(mini_repo, BRIDGE_OUT, "- → `delta`: x.")
    assert mini_repo.findings(BRIDGES) == [(BLOCK, line, BRIDGES)]


def test_block_bridges_are_optional(mini_repo):
    text = mini_repo.read(BLOCK)
    text = text.replace("## Bridge in\n" + BRIDGE_IN + "\n\n", "")
    mini_repo.write(BLOCK, text.split("## Bridge out")[0])
    assert mini_repo.findings() == []


def test_block_bridges_use_only_the_first_section_of_a_name(mini_repo):
    mini_repo.write(BLOCK, mini_repo.read(BLOCK) + "\n## Bridge out (de novo)\n- → `delta`.\n")
    assert mini_repo.findings() == []


@pytest.mark.parametrize("genres", ["[delta]", "alpha", "[]", "[5]", "[[alpha]]", "[{a: b}]", ""])
def test_block_bridges_skip_a_block_whose_genres_cannot_be_judged(mini_repo, genres):
    # block-frontmatter reports the genres; the bridges are not reported again.
    add_after(mini_repo, BRIDGE_IN, "← `gamma`: corte.")
    mini_repo.edit(BLOCK, "genres: [alpha]", f"genres: {genres}")
    assert mini_repo.findings(BRIDGES) == []


def test_block_bridges_judge_a_block_by_its_genres_that_exist(mini_repo):
    mini_repo.edit(BLOCK, "genres: [alpha]", "genres: [delta, alpha, 5]")
    line = add_after(mini_repo, BRIDGE_IN, "← `gamma`: corte.")
    assert mini_repo.findings(BRIDGES) == [(BLOCK, line, BRIDGES)]
    assert block_messages(mini_repo, BRIDGES) == ["no edge gamma -> alpha for Bridge in `gamma`"]


def test_block_bridges_check_graph_ok_themselves(mini_repo):
    add_after(mini_repo, BRIDGE_IN, "← `gamma`: corte.")
    repo = load_repo(mini_repo.root)
    fn = block_rule(BRIDGES)
    assert len(list(fn(repo))) == 1
    repo.graph_ok = False
    assert list(fn(repo)) == []


def test_block_bridges_never_raise_on_a_malformed_edge(mini_repo):
    mini_repo.edit(
        GRAPH,
        '      - {to: gamma, strength: weak,   via: "long echo out"}\n',
        '      - {to: [gamma], strength: weak, via: "long echo out"}\n'
        "      - alpha\n"
        "      - {to: 5}\n",
    )
    line = add_after(mini_repo, BRIDGE_OUT, "- → `gamma`: lift.")  # alpha -> gamma is gone
    assert mini_repo.findings(BRIDGES) == [(BLOCK, line, BRIDGES)]


def test_block_bridges_skip_a_block_without_front_matter(mini_repo):
    mini_repo.write(BLOCK, without_front_matter(mini_repo).replace(BRIDGE_IN, "← `gamma`: corte."))
    assert mini_repo.findings() == [(BLOCK, 1, FRONTMATTER)]


# ---- all three rules ----


def test_block_rules_check_every_block(mini_repo):
    other = "blocks/beta-festa.md"
    mini_repo.write(other, mini_repo.read(BLOCK).replace("genres: [alpha]", "genres: [beta]"))
    assert mini_repo.findings() == []
    mini_repo.edit(BLOCK, "function: peak", "function: party")
    ghost = add_after(mini_repo, TRACK_2, GHOST, rel=other)
    bridge = add_after(mini_repo, BRIDGE_OUT, "- → `delta`: x.", rel=other)
    assert block_findings(mini_repo) == [
        (BLOCK, 2, FRONTMATTER),
        (other, ghost, TRACKLIST),
        (other, bridge, BRIDGES),
    ]
