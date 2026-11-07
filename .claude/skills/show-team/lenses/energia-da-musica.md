# Lens: energia-da-musica

Judge each track's light against that track's own music: does the light rise and fall when
the music does, in the same direction, and on time? Judge track by track, but weigh the whole
leg, not one bar.

## Judges

- Shape: the light's curve against the music's (`rho`).
- Direction: the light moves the way the music moves at section boundaries (`agree`).
- Lag: the light arriving late or early (`lag`).
- Missed boundaries: where the music changes and the light does not.
- Unmotivated movement: light that changes where the music is still.

## Run

`<show>` stands for the show folder named in your brief; `<track>` is `Artist — Title`, taken in full from the track's header line in the `tracks`
section, without the leading `N. ` index (the `follows` lines print the title only).

```
uv run scripts/nextrack_show.py report <show> --section follows,tracks
uv run scripts/nextrack_show.py report <show> --track "<track>" --section follows,tracks
uv run scripts/nextrack_show.py zoom <show> "<track>" <bar>
```

The second command is one track in detail; use `zoom` on a missed boundary.

## Questions

1. Which tracks have a low or negative `rho` (below about 0.3)? Read their `music` and
   `light` strips: where do the curves part?
2. Which tracks have a low `agree` (below about 50%)? List their `missed` boundaries with
   `dm` and `dl`.
3. Which tracks have a `lag` beyond 1 bar? A `+` means the light is late: the viewer sees the
   change after the music has changed.
4. Which `missed` boundaries are the music's biggest moves (large `dm`) with a light that
   barely moves (`dl` under 1)?
5. Which `unmotivated` stretches show the light moving 3 or more where the music is still?
6. Does the `bright` strip rise and fall with the `music` strip, and the `activity` strip with
   the onset density? A drop that is dimmer but faster is legitimate design: say so before
   calling it a miss.
7. Is the `unknown` share high (the autoscript plays part of the leg)? Say it, and rate only
   the known ground.
8. Breakdowns: is the activity in a break lower than in the drops around it, with slower
   movement?

## Severity

- `grave`: a track whose light moves against its music (negative `rho`, or `agree` near 0),
  or that is late by more than 2 bars across the leg, or that misses the track's biggest
  boundary.
- `moderado`: a low `rho` or `agree` with the right direction; a lag of 2 bars in part of the
  leg; several small missed boundaries.
- `menor`: a single small missed boundary, or a short unmotivated move.

## Finding format

Write each finding in pt-BR with `lente`, `severidade`, `unidade`, `evidência`, `problema` and
`direção`, as the critic agent file defines. Example:

```
- lente: energia-da-musica
- severidade: moderado
- unidade: The Akan
- evidência: "The Akan · rho 0.48 · agree 50% · lag -1 · missed 105 (music +4.5, light +0.8)"
- problema: a música sobe 4,5 no compasso 105 e a luz sobe menos de 1: a maior virada da
  faixa passa quase sem resposta.
- direção: olhar a seção que começa no 105 e dar a ela uma mudança de brilho ou de atividade
  na mesma direção da música.
```
