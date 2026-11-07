from pathlib import Path

import yaml
from showdata import FILE_1, FILE_2, put_show

SHOW = "lightshows/shows/teste"
RULES = ("show-source", "show-rules", "show-compiled")
TRACK_1 = f"lightshows/tracks/{FILE_1}"
TRACK_2 = f"lightshows/tracks/{FILE_2}"


def _edit_yaml(repo, rel, change):
    data = yaml.safe_load(repo.read(rel))
    change(data)
    repo.write(rel, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def _show_only(repo):
    return [f for f in repo.findings() if f[2] in RULES or f[2] == "parse-error"]


def test_a_valid_show_has_no_findings(mini_repo):
    put_show(mini_repo)
    assert mini_repo.findings() == []


def test_show_source_reports_a_bad_anchor_at_its_line(mini_repo):
    put_show(mini_repo)
    rel = f"{SHOW}/{FILE_1}"
    mini_repo.edit(rel, "at: drop.1", "at: drop.9")
    line = mini_repo.line_of(rel, "at: drop.9")
    assert mini_repo.findings() == [(rel, line, "show-source")]


def test_show_rules_report_a_broken_budget(mini_repo):
    put_show(mini_repo)

    def change(data):
        data["rules"] = {"budget": {"pulso": {"max": 0}}}

    _edit_yaml(mini_repo, f"{SHOW}/show.yml", change)
    found = mini_repo.findings()
    assert found and {f[2] for f in found} == {"show-rules"}


def test_check_repo_ignores_advice(mini_repo):
    from check_repo import check, load_repo, show_inputs, show_results
    from show_rules import evaluate_show

    put_show(mini_repo)
    _edit_yaml(mini_repo, f"{SHOW}/show.yml", lambda data: data.update(advice={"bridges": {"max": 2}}))
    repo = load_repo(mini_repo.root)
    source = repo.shows[0]
    *_, advice = evaluate_show(source, show_inputs(repo, source))
    assert [f.rule for f in advice] == ["show-advice", "show-advice"]     # the handover and its bridge
    assert [len(result) for result in show_results(repo)] == [4]           # source, compiled, found, rules
    assert check(mini_repo.root) == []


def test_show_compiled_flags_a_hand_edit(mini_repo):
    from check_repo import check

    put_show(mini_repo)
    mini_repo.write(TRACK_1, mini_repo.read(TRACK_1) + "# edited\n")
    found = [f for f in check(mini_repo.root) if f.rule == "show-compiled"]
    assert [(f.path, f.line) for f in found] == [(TRACK_1, 0)]
    assert found[0].message == (f"differs from what {SHOW} compiles to; "
                                "run uv run scripts/nextrack_show.py build teste")


def test_show_compiled_flags_a_missing_file(mini_repo):
    put_show(mini_repo)
    mini_repo.path(TRACK_2).unlink()
    assert mini_repo.findings() == [(TRACK_2, 0, "show-compiled")]


def test_show_compiled_flags_an_orphan_generated_file(mini_repo):
    put_show(mini_repo)
    text = mini_repo.read(TRACK_1)
    mini_repo.write(TRACK_1, text.replace("from lightshows/shows/teste/.", "from lightshows/shows/gone/.", 1))
    assert mini_repo.findings() == [(TRACK_1, 0, "show-compiled")]


def test_a_choreography_its_show_does_not_compile_is_flagged(mini_repo):
    put_show(mini_repo)
    mini_repo.write("lightshows/tracks/extra.yml", mini_repo.read(TRACK_1))
    assert ("lightshows/tracks/extra.yml", 0, "show-compiled") in mini_repo.findings()


def test_two_shows_owning_one_track(mini_repo):
    put_show(mini_repo)
    for name in ("show.yml", FILE_1, FILE_2):
        mini_repo.write(f"lightshows/shows/outro/{name}", mini_repo.read(f"{SHOW}/{name}"))
    found = [f for f in mini_repo.findings() if f[2] == "show-compiled"]
    for show in ("teste", "outro"):
        for name in (FILE_1, FILE_2):
            assert (f"lightshows/shows/{show}/{name}", 0, "show-compiled") in found


def test_broken_inputs_report_once(mini_repo_at, tmp_path):
    causes = {
        "set missing": (lambda r: r.path("sets/teste.md").unlink(), "show-source"),
        "block link broken": (lambda r: r.edit("sets/teste.md", "alpha-festa.md", "nope.md"), "show-source"),
        "map deleted": (lambda r: r.path(f"lightshows/maps/{FILE_2}").unlink(), "show-source"),
        "map invalid": (lambda r: r.edit(f"lightshows/maps/{FILE_2}", "bars: 32", "bars: -1"), "show-source"),
        "invalid yaml": (lambda r: r.write(f"{SHOW}/{FILE_2}", "a: [1, 2\n"), "parse-error"),
    }
    for n, (name, (break_it, expected)) in enumerate(causes.items()):
        repo = mini_repo_at(tmp_path / f"r{n}")
        put_show(repo)
        break_it(repo)
        found = _show_only(repo)
        assert [f[2] for f in found] == [expected], (name, found)


def test_an_invalid_map_is_named_as_invalid(mini_repo):
    from check_repo import check

    put_show(mini_repo)
    mini_repo.edit(f"lightshows/maps/{FILE_2}", "bars: 32", "bars: -1")
    found = check(mini_repo.root)
    assert any(f.rule == "musical-map" and f.path == f"lightshows/maps/{FILE_2}" for f in found)
    assert [(f.path, f.message) for f in found if f.rule == "show-source"] == [
        (f"{SHOW}/{FILE_2}", f"lightshows/maps/{FILE_2} is not a valid map: fix its musical-map finding "
                             "(or redo it with uv run scripts/nextrack_map.py analyze)")]


def test_show_compiled_says_adopt_for_a_hand_written_file(mini_repo):
    from check_repo import check

    put_show(mini_repo)
    mini_repo.write(TRACK_1, "\n".join(mini_repo.read(TRACK_1).splitlines()[2:]) + "\n")  # no header
    found = [f for f in check(mini_repo.root) if f.rule == "show-compiled"]
    assert [(f.path, f.line, f.message) for f in found] == [
        (TRACK_1, 0, f"differs from what {SHOW} compiles to and is hand-written; run uv run "
                     "scripts/nextrack_show.py build teste --adopt to take it over")]


def test_rules_table_lists_the_show_rules():
    text = (Path(__file__).resolve().parents[1] / "scripts/README.md").read_text(encoding="utf-8")
    for rule_id in RULES:
        assert f"`{rule_id}`" in text


def test_show_inputs_read_the_energy_of_each_block_line(mini_repo):
    import check_repo
    from showdata import TRACK_1 as NAME_1, TRACK_2 as NAME_2

    put_show(mini_repo)
    # the mini repo's block lines carry no energy field: the pool entry's `energy` answers
    repo = check_repo.load_repo(mini_repo.root)
    source = next(s for s in repo.shows if s.folder == SHOW)
    assert check_repo.show_energies(repo, source) == {NAME_1: 8, NAME_2: 7}
    # a block line's `eN` wins over the pool
    mini_repo.edit("blocks/alpha-festa.md", "Dançarina        · e8", "Dançarina · 8A · 120 · e5")
    repo = check_repo.load_repo(mini_repo.root)
    source = next(s for s in repo.shows if s.folder == SHOW)
    inputs = check_repo.show_inputs(repo, source)
    assert inputs.energies == {NAME_1: 5, NAME_2: 7}
    assert inputs.tempos == {NAME_1: (120.0, 120.0)} and inputs.rig is None


def test_valid_rig_is_none_without_a_rig(mini_repo):
    import check_repo

    assert check_repo.valid_rig(check_repo.load_repo(mini_repo.root)) is None
