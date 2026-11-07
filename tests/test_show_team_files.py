"""Pins the contract of the show team's files: the role agents (.claude/agents/*.md), the
critic lenses, the dispatch templates and the director's rite (.claude/skills/show-team/)."""

import re
from pathlib import Path

import check_repo
import pytest
import show_compare
import show_report
import show_rules
import yaml

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / ".claude" / "agents"
NAMES = ["show-reader", "show-designer", "show-critic", "gesture-engineer"]
MODELS = {"opus", "sonnet", "haiku", "inherit"}


def load(name):
    """Return (frontmatter dict, body) of an agent file."""
    text = (AGENTS / f"{name}.md").read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{name}: frontmatter must start on line 1"
    _, front, body = text.split("---\n", 2)
    return yaml.safe_load(front), body


def tools_of(name):
    return {t.strip() for t in load(name)[0]["tools"].split(",")}


@pytest.mark.parametrize("name", NAMES)
def test_every_agent_file_has_its_frontmatter(name):
    front, body = load(name)
    assert {"name", "description", "tools", "model"} <= set(front)
    assert front["name"] == name
    assert front["model"] in MODELS
    assert front["description"].strip() and body.strip()


def test_the_agent_folder_holds_exactly_these_agents():
    assert sorted(p.stem for p in AGENTS.glob("*.md")) == sorted(NAMES)


def test_the_critic_runs_on_opus():
    assert load("show-critic")[0]["model"] == "opus"


@pytest.mark.parametrize("name", ["show-reader", "show-critic"])
def test_the_reader_and_the_critic_cannot_write(name):
    assert not tools_of(name) & {"Write", "Edit", "NotebookEdit"}


def test_the_critic_is_told_not_to_read_the_authors_reasoning():
    body = load("show-critic")[1]
    assert "ledger.md" in body
    assert "designer reports" in body


@pytest.mark.parametrize("name", NAMES)
def test_every_agent_states_the_reply_contract(name):
    body = load(name)[1]
    assert "15 lines" in body
    assert "path named in your brief" in body


def test_the_critic_never_runs_the_book():
    body = load("show-critic")[1]
    assert "never run `book`" in body
    assert "ledger's decisions" in body
    # `book` appears only inside that prohibition, never as an allowed view
    assert body.count("`book`") == 1
    assert "book`," not in body


# --- the critic lenses (.claude/skills/show-team/lenses/*.md) ---

LENSES = ROOT / ".claude" / "skills" / "show-team" / "lenses"
LENS_NAMES = ["monotonia", "drops", "energia-da-musica", "arco-do-set", "briefing"]
LENS_SECTIONS = ["## Judges", "## Run", "## Questions", "## Severity", "## Finding format"]


def lens_text(name):
    return (LENSES / f"{name}.md").read_text(encoding="utf-8")


def test_the_lens_folder_holds_exactly_these_lenses():
    assert sorted(p.stem for p in LENSES.glob("*.md")) == sorted(LENS_NAMES)


@pytest.mark.parametrize("name", LENS_NAMES)
def test_every_lens_has_its_sections(name):
    headings = [line for line in lens_text(name).splitlines() if line.startswith("## ")]
    assert headings == LENS_SECTIONS


@pytest.mark.parametrize("name", LENS_NAMES)
def test_every_lens_runs_existing_report_sections(name):
    used = re.findall(r"--section ([a-z,-]+)", lens_text(name))
    assert used, f"{name}: runs no report section"
    for group in used:
        for section in group.split(","):
            assert section in show_report.REPORT_SECTIONS, f"{name}: unknown section {section}"


@pytest.mark.parametrize("name", LENS_NAMES)
def test_every_lens_defines_the_three_severities(name):
    severity = lens_text(name).split("## Severity", 1)[1].split("## Finding format", 1)[0]
    for level in ("grave", "moderado", "menor"):
        assert f"`{level}`" in severity, f"{name}: no {level}"


@pytest.mark.parametrize("name", LENS_NAMES)
def test_no_lens_runs_the_book_or_opens_the_ledger(name):
    text = lens_text(name)
    assert "show.py book" not in text
    assert "ledger.md" not in text


# --- the dispatch templates (.claude/skills/show-team/templates/*.md) ---

TEMPLATES = ROOT / ".claude" / "skills" / "show-team" / "templates"
TEMPLATE_NAMES = ["reader", "designer", "critic", "judge", "engineer"]
PLACEHOLDERS = {
    "run", "show", "show_id", "set", "unit", "files", "card", "neighbours", "constraints",
    "request", "lens", "scope", "variant_a", "variant_b", "effect", "report_file",
}


def template_text(name):
    return (TEMPLATES / f"{name}.md").read_text(encoding="utf-8")


def test_the_template_folder_holds_exactly_these_templates():
    assert sorted(p.stem for p in TEMPLATES.glob("*.md")) == sorted(TEMPLATE_NAMES)


@pytest.mark.parametrize("name", TEMPLATE_NAMES)
def test_templates_use_only_known_placeholders(name):
    text = template_text(name)
    used = set(re.findall(r"\{\{(.*?)\}\}", text))
    assert used <= PLACEHOLDERS, f"{name}: unknown {used - PLACEHOLDERS}"
    assert "{{report_file}}" in text, f"{name}: no report path"
    assert "15 lines" in text


def test_the_critic_template_hands_no_reasoning():
    text = template_text("critic")
    assert "{{request}}" not in text
    assert "{{lens}}" in text and "{{scope}}" in text
    assert "whole night" in text
    assert "Do not open `ledger.md`" in text
    assert "designer reports" in text
    assert "Never run `book`" in text


def test_the_designer_template_asks_for_three_options_and_the_usage_record():
    text = template_text("designer")
    assert "three options" in text
    assert "report {{show}} --section variety" in text
    assert "build {{show}} --out" in text
    assert "{{constraints}}" in text and "{{files}}" in text
    assert "{{run}}/work/{{unit}}/" in text
    assert "report {{show}} --track" in text


def test_the_judge_template_compares_in_both_orders():
    text = template_text("judge")
    assert "compare {{variant_a}} {{variant_b}}" in text
    assert "compare {{variant_b}} {{variant_a}}" in text
    assert "undecided" in text
    assert "{{request}}" not in text


def test_the_reader_and_engineer_templates_name_their_inputs():
    assert "brief {{set}}" in template_text("reader")
    assert "## Cartões" in template_text("reader")
    engineer = template_text("engineer")
    assert "{{effect}}" in engineer and "Add a gesture" in engineer


def test_templates_match_their_agents():
    assert "{{request}}" in template_text("designer")
    assert "owner's request" in load("show-designer")[1]
    assert "3 design rounds" in template_text("designer")
    judge = template_text("judge")
    assert "--out" in judge and "other critics' reports" in judge
    assert "critic-out" not in template_text("critic")
    assert "mktemp -d" in template_text("critic")
    assert "yourself" in template_text("engineer")
    assert "yourself" in load("gesture-engineer")[1]


# --- the director's rite (.claude/skills/show-team/SKILL.md) ---

SKILL = ROOT / ".claude" / "skills" / "show-team" / "SKILL.md"
SKILL_SECTIONS = [
    "## When to use", "## What the owner gives and keeps", "## The run folder and the ledger",
    "## Checklist", "## The phases", "## Stopping and self-healing", "## Delivery",
    "## Placeholders", "## Measuring the team",
]
# backticked `show-*` words that are not agents: the skill itself, the advice id and the
# validator's rule ids (`show-source`, `show-rules`, `show-compiled`, ...)
NOT_AGENTS = {"show-team", show_rules.ADVICE} | {fn.rule_id for fn in check_repo.RULES}


def skill():
    """Return (frontmatter dict, body) of the skill."""
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md: frontmatter must start on line 1"
    _, front, body = text.split("---\n", 2)
    return yaml.safe_load(front), body


def skill_section(heading):
    body = skill()[1]
    assert heading + "\n" in body, f"SKILL.md: no {heading}"
    return body.split(heading + "\n", 1)[1].split("\n## ", 1)[0]


def test_skill_frontmatter_names_its_triggers():
    front, _ = skill()
    assert front["name"] == "show-team"
    description = front["description"]
    assert description.startswith("Use when the owner asks the light team for a show, a rework of "
                                  "a show, or a backlog item about a set's lights")
    for words in ("time de luz", "rodar o time", "show novo", "retrabalhar o show", "branch"):
        assert words in description, f"description lacks {words!r}"


def test_skill_sections_come_in_order():
    headings = [line for line in skill()[1].splitlines() if line.startswith("## ")]
    assert [h for h in headings if h in SKILL_SECTIONS] == SKILL_SECTIONS


def test_skill_names_every_agent_lens_and_template():
    body = skill()[1]
    for path in sorted(LENSES.glob("*.md")):
        assert f"lenses/{path.name}" in body, f"SKILL.md never names lenses/{path.name}"
    for path in sorted(TEMPLATES.glob("*.md")):
        assert f"templates/{path.name}" in body, f"SKILL.md never names templates/{path.name}"
    for path in sorted(AGENTS.glob("*.md")):
        assert f"`{path.stem}`" in body, f"SKILL.md never names the agent `{path.stem}`"
    for stem in re.findall(r"lenses/([a-z0-9-]+)\.md", body):
        assert (LENSES / f"{stem}.md").exists(), f"SKILL.md names a missing lens: {stem}"
    for stem in re.findall(r"templates/([a-z0-9-]+)\.md", body):
        assert (TEMPLATES / f"{stem}.md").exists(), f"SKILL.md names a missing template: {stem}"
    for name in set(re.findall(r"`((?:show|gesture)-[a-z-]+)`", body)) - NOT_AGENTS:
        assert (AGENTS / f"{name}.md").exists(), f"SKILL.md names a missing agent: {name}"


def test_skill_documents_every_placeholder():
    used = set()
    for name in TEMPLATE_NAMES:
        used |= set(re.findall(r"\{\{(.*?)\}\}", template_text(name)))
    rows = [line for line in skill_section("## Placeholders").splitlines() if line.startswith("|")]
    documented = {m for line in rows for m in re.findall(r"`\{\{(.*?)\}\}`", line)}
    assert documented == used, f"undocumented {used - documented}, unused {documented - used}"
    unknown = set(re.findall(r"\{\{(.*?)\}\}", skill()[1])) - PLACEHOLDERS
    assert not unknown, f"SKILL.md names unknown placeholders {unknown}"


def test_skill_lens_placeholder_lists_the_lens_files():
    rows = [line for line in skill_section("## Placeholders").splitlines()
            if line.startswith("| `{{lens}}`")]
    assert len(rows) == 1, "no {{lens}} row"
    ids = set(re.findall(r"`([a-z-]+)`", rows[0]))
    assert ids == {p.stem for p in LENSES.glob("*.md")}


def test_skill_states_the_limits():
    body = skill()[1]
    for words in ("--keep", "Estado:", "Para depois", "never push", "--apply",
                  "3 design rounds", "2 full critique passes"):
        assert words in body, f"SKILL.md lacks {words!r}"
    assert "`Estado: fase <n> (<name>) concluída — <YYYY-MM-DD HH:MM>`" in body
    assert "<scratch>/show-team/<show-id>/<YYYY-MM-DD-HHMM>/" in body
    assert "## Cartões" in body


def test_skill_makes_a_run_resumable_and_its_rounds_countable():
    flat = " ".join(skill()[1].split())  # wrapping never breaks a phrase
    for words in (
        "designer-<unit>-r<r>-gate.md",            # a gate bounce has its own brief
        "At most one bounce per unit per round",
        "a bounce is not a design round",
        "Unidades: mix-02 2/3",                    # the round count survives a resume
        "git log -1 --grep 'Record round' --format=%B",
        "`leitura a frio, rodada <r>`",
        "the round its name carries",
        "A rerun does not count as a full pass",
        "git merge-base HEAD origin/main",         # the contract's starting show is stable
        "git diff <commit> HEAD -- <its files>",   # the restore rule
        "critic-<lens>-r<r>.md",
    ):
        assert words in flat, f"SKILL.md lacks {words!r}"


def test_skill_runs_existing_report_sections_and_compare_facts():
    body = skill()[1]
    for group in re.findall(r"--section ([a-z,-]+)", body):
        for section in group.split(","):
            assert section in show_report.REPORT_SECTIONS, f"SKILL.md: unknown section {section}"
    kept = re.findall(r"--keep ([a-z,]+)", body)
    assert kept, "SKILL.md never shows a --keep list"
    for group in kept:
        for fact in group.split(","):
            assert fact in show_compare.FACTS, f"SKILL.md: unknown compare fact {fact}"


def phase(n):
    """The text of the skill's `### <n>. ...` phase, with its wrapping flattened."""
    body = skill()[1]
    start = re.search(rf"^### {n}\. .*$", body, re.M)
    assert start, f"SKILL.md: no phase {n}"
    rest = body[start.end():]
    end = re.search(r"^#{2,3} ", rest, re.M)
    return " ".join(rest[: end.start() if end else None].split())


def placeholder_row(name):
    rows = [line for line in skill_section("## Placeholders").splitlines()
            if line.startswith(f"| `{{{{{name}}}}}`")]
    assert len(rows) == 1, f"no {{{{{name}}}}} row"
    return rows[0]


def test_a_gate_bounce_starts_from_the_merged_show():
    gates = phase(5)
    assert "mv <run>/work/<unit> <run>/work/<unit>-r<r>-pre-gate" in gates
    assert "cp -r lightshows/shows/<show-id> <run>/work/<unit>" in gates
    assert "The merged show already holds the unit's round-r work and its neighbours'" in gates


def test_the_merge_check_reads_each_listed_file():
    design = phase(4)
    assert "diff -rq -x out -x ledger.md" in design
    assert "only the part named in `{{files}}` changed" in design


def test_critics_review_a_copy_without_the_ledger():
    critique = phase(6)
    assert "cp -r lightshows/shows/<show-id> <run>/critic/<show-id>" in critique
    assert "rm <run>/critic/<show-id>/ledger.md" in critique
    assert "critic: its copy without the ledger, `<run>/critic/<show-id>`" in placeholder_row("show")
    for text in (template_text("critic"), load("show-critic")[1]):
        assert "Never run `git log` or `git show`" in text
    for text in (template_text("designer"), load("show-designer")[1]):
        assert "says what the light does, not why" in " ".join(text.split())


def test_the_scope_names_each_unit_by_its_tracks_and_bars():
    row = placeholder_row("scope")
    assert "`Artist — Title`" in row and "bars" in row
    assert "never read this skill" in row


def test_every_commit_message_is_grepped_before_the_commit():
    flat = " ".join(skill()[1].split())
    assert 'grep -iE "/(home|mnt)/|C:\\\\\\\\Users" <run>/commit-msg.txt' in flat
    assert "git commit -F <run>/commit-msg.txt" in flat


def test_delivery_commits_before_it_publishes_the_book():
    delivery = skill_section("## Delivery")
    assert delivery.index("git commit -F") < delivery.index("nextrack_show.py book")
    assert "compare --keep, commit, book, report" in skill_section("## Checklist")


def test_a_new_plan_is_validated_before_the_plan_commit():
    assert "`lightshow-plan`" in phase(2)
    cold_read = phase(3)
    assert cold_read.index("uv run scripts/check_repo.py") < cold_read.index("git add lightshows")


def test_the_units_and_the_estimate_count_from_the_start():
    assert "every track of the set at `0/3`" in phase(2)
    flat = " ".join(skill()[1].split())
    assert "até ~54 despachos, mais revisões" in flat
    assert "gate bounces and the engineer with its code review come on top" in phase(0)


def test_a_resume_settles_the_uncommitted_merges():
    intake = phase(0)
    assert "git status" in intake
    assert "git checkout -- lightshows" in intake
    assert "redo the build and the gates" in intake


def test_the_agents_and_the_briefing_lens_name_paths_like_their_templates():
    reader = load("show-reader")[1]
    assert "lightshows/shows/<show>/" not in reader
    assert "`<show>/show.yml`" in reader and "lightshows/sets/<show-id>.md" in reader
    critic = load("show-critic")[1]
    assert "mktemp -d" in critic and "the folder the brief names" not in critic
    briefing = lens_text("briefing")
    assert "lightshows/sets/<show-id>.md" in briefing and "lightshows/sets/<set>.md" not in briefing
