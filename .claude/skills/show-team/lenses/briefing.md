# Lens: briefing

Judge the night against what the director declared: the story, the identity and the cards of
the light plan. Is the show faithful to them, is it restrained, and do the palette and the
fixture roles hold together? A departure is fine if it is deliberate and named as a moment.

## Judges

- Fidelity to the story, the identity (signatures, arc) and each track's card.
- Restraint: budgets, rare resources kept rare, darkness used as canvas.
- Coherence: a small palette, fixed roles per fixture group.

## Run

`<show>` stands for the show folder named in your brief; `<set>` is its set's id.

```
uv run scripts/nextrack_show.py report <show> --section identity,budget,arrivals
```

Then read the show's story and identity files in the show folder, and the light plan's cards:
`lightshows/sets/<set>.md`, section `## Cartões`. Judge from these files and the report alone.

## Questions

1. Does each declared signature (`identity`) hold its `share`: `in range`, or `below min` /
   `above max`? Does each occurrence fall where its intent says?
2. Is there an undeclared dominant value (`undeclared movers.colour: azul-gelo 86%`) that the
   story does not mention? A palette that drifts from the story is a finding.
3. Card by card: does each track's light do what its card says (look, colour, mood, the
   moment it promises)? Name the card line and the report line side by side.
4. Is the palette small, and do the fixture groups keep their roles (movers, matrix, hue,
   white strip) across the night? A role that changes for no named moment is incoherent.
5. Restraint: in the `budget` tally, are the rare resources (strobe, white flash, solid, UV)
   within the show's own rules and kept for the climaxes? Is any used in a moment the rule
   does not allow?
6. Is darkness used as a canvas (the total dark and centre dark), or is the room never dark?
7. `arrivals`: does each arrival look different from the previous one (draw, matrix colour,
   mover move)? Does every arrival land on the track's entry, as the card says?
8. Breakdowns: slower movement and moodier colour, as the cards ask?
9. Do the accents stay rare, or does every hit flash? "Too explicit" reads as cheap.

## Severity

- `grave`: the night contradicts the story or the identity across a whole track or at a top
  drop (a signature absent or far outside its share, a card's central promise not kept); or
  a rare resource spent against the budget at the climax.
- `moderado`: an undeclared dominant value, a palette or role that drifts between tracks, an
  arrival that repeats the one before, a signature slightly off its share.
- `menor`: polish, such as one extra colour in a corner of a card.

## Finding format

Write each finding in pt-BR with `lente`, `severidade`, `unidade`, `evidência`, `problema` and
`direção`, as the critic agent file defines. The evidence may cite a card line next to a report
line. Example:

```
- lente: briefing
- severidade: moderado
- unidade: a noite
- evidência: "undeclared movers.colour: azul-gelo 86%"; a história pede "calor que cresce"
- problema: os movers ficam em azul-gelo quase a noite toda e a identidade não declara isso:
  a promessa de calor não aparece.
- direção: olhar quais faixas da segunda metade podem virar para tons quentes, nomeando o
  momento na identidade.
```
