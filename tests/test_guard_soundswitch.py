"""Tests of the PreToolUse hook that asks before any command that writes SoundSwitch."""

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".claude" / "hooks" / "guard_soundswitch.py"

_spec = importlib.util.spec_from_file_location("guard_soundswitch", HOOK)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def asks(command):
    out = guard.decision(bash(command))
    if out is None:
        return False
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "ask"
    assert out["permissionDecisionReason"] == guard.REASON
    return True


def test_apply_with_apply_asks():
    assert asks("uv run scripts/nextrack_lights.py apply lightshows/tracks/x.yml --apply")


def test_restore_and_accept_with_apply_ask():
    assert asks("uv run scripts/nextrack_lights.py restore --apply")
    assert asks("uv run scripts/nextrack_lights.py accept lightshows/tracks/x.yml --apply")


def test_dry_run_does_not_ask():
    assert not asks("uv run scripts/nextrack_lights.py apply lightshows/tracks/x.yml")


def test_render_and_status_do_not_ask():
    assert not asks("uv run scripts/nextrack_lights.py render lightshows/tracks/x.yml")
    assert not asks("uv run scripts/nextrack_lights.py status")


def test_tags_apply_does_not_ask():
    assert not asks("uv run scripts/nextrack_tags.py fix-tags --apply")


def test_other_tools_do_not_ask():
    payload = {"tool_name": "Edit", "tool_input": {"command": "nextrack_lights.py --apply"}}
    assert guard.decision(payload) is None


def test_non_bash_shapes_do_not_ask():
    assert guard.decision(None) is None
    assert guard.decision([]) is None
    assert guard.decision({"tool_name": "Bash"}) is None
    assert guard.decision({"tool_name": "Bash", "tool_input": {}}) is None
    assert guard.decision({"tool_name": "Bash", "tool_input": {"command": 5}}) is None


def test_malformed_input_exits_0_silently():
    proc = subprocess.run(
        [sys.executable, str(HOOK)], input="not json", capture_output=True, text=True
    )
    assert proc.returncode == 0
    assert proc.stdout == ""


def test_main_prints_the_decision():
    out = io.StringIO()
    stdin = io.StringIO(json.dumps(bash("python scripts/nextrack_lights.py apply a.yml --apply")))
    assert guard.main(stdin, out) == 0
    answer = json.loads(out.getvalue())
    assert answer["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_wrapped_and_glued_forms_ask():
    assert asks('bash -c "uv run scripts/nextrack_lights.py apply x --apply"')
    assert asks("uv run scripts/nextrack_lights.py apply x --apply;")
    assert asks("uv run scripts/nextrack_lights.py apply x --apply&& echo ok")
    assert not asks("uv run scripts/nextrack_lights.py apply x --applyfoo")


def test_abbreviated_apply_asks():
    base = "uv run scripts/nextrack_lights.py apply x.yml "
    for flag in ("--ap", "--app", "--appl"):
        assert asks(base + flag)
    # `restore` and `accept` have no other `--a...` option, so argparse reads `--a` as `--apply`
    assert asks('uv run scripts/nextrack_lights.py restore "X" --a')
    assert asks('uv run scripts/nextrack_lights.py accept "X" --a')
    assert not asks(base + "--accept-resize")
    assert not asks(base + "--adopt-current")


def test_unbalanced_quote_still_asks():
    assert asks("uv run scripts/nextrack_lights.py apply x.yml --apply 'unbalanced")
    assert not asks("echo 'unbalanced")


def pre_tool_use_commands():
    """(matcher, command) of every command hook of every `PreToolUse` entry."""
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
    return [
        (entry.get("matcher"), hook.get("command"))
        for entry in settings["hooks"]["PreToolUse"]
        for hook in entry["hooks"]
        if hook.get("type") == "command"
    ]


def guard_command():
    """The settings command that runs the guard, exactly as Claude Code runs it."""
    guards = [c for _, c in pre_tool_use_commands() if ".claude/hooks/guard_soundswitch.py" in c]
    assert len(guards) == 1, "the guard must be registered exactly once"
    return guards[0]


def test_settings_json_runs_the_guard():
    command = guard_command()
    assert [m for m, c in pre_tool_use_commands() if c == command] == ["Bash"]
    assert HOOK.is_file()


def test_every_pre_tool_use_command_fails_open():
    # a PreToolUse command that exits 2 blocks the tool: a missing script would block every call
    for matcher, command in pre_tool_use_commands():
        assert command.rstrip().endswith("|| true"), f"{matcher}: {command!r} does not fail open"


def run_guard_command(project_dir, payload):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)}
    return subprocess.run(
        ["sh", "-c", guard_command()], input=json.dumps(payload), capture_output=True,
        text=True, env=env,
    )


def test_the_settings_command_fails_open_without_the_script(tmp_path):
    proc = run_guard_command(tmp_path, bash("uv run scripts/nextrack_lights.py apply x --apply"))
    assert proc.returncode == 0
    assert proc.stdout == ""


def test_the_settings_command_asks_before_an_apply():
    proc = run_guard_command(ROOT, bash("uv run scripts/nextrack_lights.py apply x --apply"))
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": guard.REASON,
        }
    }
