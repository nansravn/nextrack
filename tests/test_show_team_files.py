"""Pins the contract of the show team's role agents (.claude/agents/*.md)."""

from pathlib import Path

import pytest
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
