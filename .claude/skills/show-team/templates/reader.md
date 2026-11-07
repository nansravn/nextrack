# Brief: cold read of {{show_id}}

Run folder: `{{run}}`. Write your full report to `{{report_file}}`.

You have not seen the story's reasoning or any draft. Read cold.

## What you read, in this order

1. The show: `{{show}}/show.yml` (identity, rules, bridges, budgets).
2. The light plan `lightshows/sets/{{show_id}}.md` and its cards under `## Cartões` (a plan
   written before the team may have none: then say which units have no card, and rank that
   first).
3. `uv run scripts/nextrack_show.py brief {{set}}` (the music facts the designers get).
4. `lightshows/shows/README.md` only when you need the meaning of a term.

## Scope

{{scope}}

## What to produce

A ranked list of every place a designer would have to guess, as your agent file describes:
where, the likely guess, why it matters, the sentence that would close it. Do not rewrite the
plan and do not propose a design. Do not edit any file except your report.

Reply with at most 15 lines: status, the report path, a one-line summary and any concern.
