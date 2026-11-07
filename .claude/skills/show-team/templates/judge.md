# Brief: blind comparison of two versions of {{scope}} in {{show_id}}

Write your full report to `{{report_file}}`.

## The two versions

- A: `{{variant_a}}`
- B: `{{variant_b}}`

Do not open `ledger.md`, the run folder's designer reports or other critics' reports; you judge what the versions
do, not why they were made. Never run `book`. Build only with `--out` into a scratch folder made with `mktemp -d`.

## Against what

The story and identity in each show's `show.yml`, and the cards in
`lightshows/sets/{{show_id}}.md` (`## Cartões`). Set file: `{{set}}`.

## How

1. Compare in this order, A then B:
   `uv run scripts/nextrack_show.py compare {{variant_a}} {{variant_b}}`
   and read each with `report <variant> --track "<Artist — Title>"` for the units in scope.
2. Compare again in the reverse order, B then A:
   `uv run scripts/nextrack_show.py compare {{variant_b}} {{variant_a}}`
   and judge fresh, as if you had not seen the first pass.
3. Report both verdicts. If they disagree, say the comparison is undecided.
4. Otherwise pick one, with reasons tied to the story and the cards, citing report lines with
   bars and clock. Reasons are in pt-BR.

Reply with at most 15 lines: status, the report path, the pick (A, B or undecided) and any
concern.
