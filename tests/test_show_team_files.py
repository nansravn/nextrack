"""Pins the contract of the show team's role agents (.claude/agents/*.md)."""

import re
from pathlib import Path

import pytest
import show_report
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
