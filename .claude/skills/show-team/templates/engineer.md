# Brief: add one gesture to the show language

Run folder: `{{run}}`. Write your full report to `{{report_file}}`.

## The effect, in words

{{effect}}

## What to read

- The output of `uv run scripts/nextrack_show.py vocab` (the words that exist now).
- `scripts/show_gestures.py`, `tests/test_show_gestures.py` and the gestures table of
  `lightshows/shows/README.md`.

## What to do

Follow the "Add a gesture" checklist of the repo's `CLAUDE.md`, test first: one function in
`scripts/show_gestures.py` registered with `@gesture(name, params=..., example=...,
example_bars=...)`, with a docstring and checks that return readable problems; a test in
`tests/test_show_gestures.py`; its row in the gestures table. Then run `uv run pytest` and
`uv run scripts/check_repo.py` and report the real output.

Do not touch any show or `lightshows/tracks/`. Never push or open a PR. Commit only if the
director says so.

Reply with at most 15 lines: status, the files changed, a one-line test summary and any
concern.
