"""Tests of the PreToolUse hook that asks before any command that writes SoundSwitch."""

import importlib.util
import io
import json
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
    assert not asks(base + "--accept-resize")
    assert not asks(base + "--adopt-current")


def test_unbalanced_quote_still_asks():
    assert asks("uv run scripts/nextrack_lights.py apply x.yml --apply 'unbalanced")
    assert not asks("echo 'unbalanced")


def test_settings_json_runs_the_guard():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
    entry = settings["hooks"]["PreToolUse"][0]
    assert entry["matcher"] == "Bash"
    assert ".claude/hooks/guard_soundswitch.py" in entry["hooks"][0]["command"]
    assert HOOK.is_file()
