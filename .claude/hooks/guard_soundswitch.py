#!/usr/bin/env python3
"""PreToolUse hook: ask the owner before any command that writes SoundSwitch.

Claude Code sends the hook call as JSON on stdin. For a Bash call whose command runs
`nextrack_lights.py` with a `--apply` token, the hook answers `permissionDecision: "ask"`
with a reason in pt-BR, so the session waits for the owner's click. Everything else (other
tools, dry runs, `render`, `status`, `nextrack_tags.py --apply`, malformed input) exits 0
with no output and leaves the normal permission flow alone. The hook never exits 2, so it
never blocks.

The match is on the raw command text, so wrapped or glued forms (`bash -c "..."`,
`--apply;`, `--apply&& ...`) are caught too. A command that merely mentions both
`nextrack_lights.py` and `--apply` also asks: that false positive is accepted.

`--ap`, `--app` and `--appl` count as `--apply` because argparse accepts unique prefixes
of an option. Shell-level obfuscation (quotes inside the word, `$'...'`) is a known limit
of a text match.

In auto mode the "ask" goes to the permission prompt. What it does under
bypass-permissions is not documented by Claude Code. Either way the rule stays: writing
SoundSwitch needs the owner's explicit go.
"""

import json
import re
import sys
from typing import TextIO

REASON = "Gravar no SoundSwitch é decisão do dono: confirme este comando."


_APPLY = re.compile(r"(?<![\w-])--ap(?:p(?:l(?:y)?)?)?(?![\w-])")


def decision(payload: object) -> dict | None:
    """The `hookSpecificOutput` dict for a Bash call that writes SoundSwitch, else None."""
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return None
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return None
    if "nextrack_lights.py" in command and _APPLY.search(command):
        return {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": REASON,
        }
    return None


def main(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    try:
        out = decision(json.load(stdin))
    except Exception:
        return 0
    if out is not None:
        stdout.write(json.dumps({"hookSpecificOutput": out}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
