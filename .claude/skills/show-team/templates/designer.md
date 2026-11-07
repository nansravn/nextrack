# Brief: design unit {{unit}} of {{show_id}}

Run folder: `{{run}}`. Write your full report to `{{report_file}}`.

## Your copy

Work only in `{{run}}/work/{{unit}}/`, a copy of the show made by the director with `cp -r`
(`{{show}}` is that copy's path). Build into its `out/` subfolder. Never touch the committed
show or `lightshows/tracks/`.

## Files you may change

{{files}}

## The request and the night

The owner's request, in their words:

{{request}}

Set file: `{{set}}`. Read the story and identity in `{{show}}/show.yml`.

## Your card

{{card}}

## Neighbours (cards and handovers)

{{neighbours}}

## Constraints (verbatim, they bind you)

{{constraints}}

If two things in this brief conflict, say so in your report instead of choosing silently.

## What the night already used

Run the usage record before choosing:

`uv run scripts/nextrack_show.py report {{show}} --section variety`

Then your slice: `uv run scripts/nextrack_show.py report {{show}} --track "<Artist — Title>"`.
Use `zoom` for the key moments and `nextrack_map.py show` for the music.

## How to work

1. Write three options for the unit before choosing, each different in its idea, with a
   one-line summary and how typical it is.
2. Choose against the card and the usage record, and say why in two sentences.
3. Apply it in your copy and build:
   `uv run scripts/nextrack_show.py build {{show}} --out {{show}}/out`
4. Read the result with `report --track` and fix the findings that are yours. You have at most
   3 design rounds per unit; the director tells you when a round is a fix.

If you need a gesture that does not exist, write a `missing gesture: <effect in words>` line
in your report; do not write code.

Reply with at most 15 lines: status, the files changed, a one-line summary and any concern.
