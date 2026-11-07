# Brief: critique of {{show_id}} through the lens `{{lens}}`

Write your full report to `{{report_file}}`.

## Your lens

Read `.claude/skills/show-team/lenses/{{lens}}.md`: its questions, the views that answer
them, what counts as grave. Judge only through that lens. Find where the night is weakest
and most predictable; never approve by default.

## Scope

{{scope}}

(`whole night`, or the units named above with their neighbours.) Rate only the ground you
tested.

## What to read

The show at `{{show}}`, the light plan `lightshows/sets/{{show_id}}.md` with its cards, and
the views your lens lists: `uv run scripts/nextrack_show.py report {{show}} [--track T]
[--section a,b]`, `zoom`, `brief {{set}}`, `compare`, `vocab`. Build only with `--out` into
`{{run}}/critic-out/{{lens}}`.

## What not to read

Do not open `ledger.md`, the run folder's designer reports, any other critic's report, or
anything that explains why the author chose what it chose. Never run `book` and never open a
book file: the book prints the ledger's decisions. If a path you meet points at one of
these, do not read it and say so in your reply.

## Findings

In pt-BR, with the parts your agent file lists (lente, severidade, unidade, evidência with
bars and clock, problema, direção). A finding without evidence is dropped.

Reply with at most 15 lines: status, the report path, the count of findings by severity and
any concern.
