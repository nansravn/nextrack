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
    mini_repo.write(GRAPH, "nodes: []\n")
    assert mini_repo.findings() == []
