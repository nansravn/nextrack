# Lens: arco-do-set

Judge the night as a whole against the owner's energy and arc: the light must follow the
owner's per-track energy labels, keep headroom for the peak, climb in steps that match the
energy, and breathe after intense stretches. Judge over the night, not one track.

## Judges

- Headroom: the biggest looks saved for the peak.
- Staircase: a track outshining earlier ones while its energy is lower.
- Steps: neighbours whose light jumps at the same energy, or stays flat while the energy rises.
- Breathers: a quieter stretch after the top drops.
- The light following the owner's labels (`rho`), and the labels worth a question.

## Run

`<show>` stands for the show folder; `<set>` is the set the show belongs to (its file stem).

```
uv run scripts/nextrack_show.py report <show> --section arc,summary
uv run scripts/nextrack_show.py brief <set>
```

`brief` gives the target arc, the clock, the owner's energy and the night's drops ranked by
salience: read it first, then the `arc` section against it.

## Questions

1. What are the two `rho` values (mean and p90) of the owner's energy against the light? A low
   or negative value means the light does not follow the arc.
2. `headroom`: is it above 0.8 (the light peaks well before the night's top energy)? Then the
   tricks were spent early.
3. `staircase`: which tracks beat every earlier p90 with a lower energy?
4. `step`: which neighbours `jump` (light mean up 2 or more at the same energy) or are `flat`
   while the energy rises? One energy step should be one step of light.
5. `no breather`: which top drops have no bar at or below the night's median E_light within
   3:00 after them? Intensity should come in waves.
6. Does the light's per-track curve (mean, p90) match the target arc in `brief` (single peak,
   waves, plateau)? Where does it part from it?
7. Does the rare-resource count (strobe, white, UV, total dark in the `rare` column) grow
   with the energy, or is it spent at the start? What does the `summary` say about the night's
   strobe and white time?
8. Does coverage grow with the energy: do the zones lit and the activity digit rise toward
   the peak, starting minimal?
9. Is any `label` question likely a wrong label rather than a wrong light? Report it as a
   question for the owner, never a fix.

## Severity

- `grave`: the light's curve is against the arc across the night (negative `rho`), or the
  peak track is not the night's top light, or the strobe and white budget is spent before the
  peak so the climax has nothing left.
- `moderado`: a staircase, a jump of 2 or more at the same energy, a missing breather after a
  top drop, a headroom above 0.8.
- `menor`: a small step that is off by one digit, a label question with no other evidence.

## Finding format

Write each finding in pt-BR with `lente`, `severidade`, `unidade`, `evidência`, `problema` and
`direção`, as the critic agent file defines. The unit is the night, a pair of tracks or a
track. Example:

```
- lente: arco-do-set
- severidade: moderado
- unidade: Say What -> Baianá (Pablo Fierro Edit)
- evidência: "step jump: Say What -> Baianá (Pablo Fierro Edit): energy e7 -> e7, light mean 2.9 -> 5.2"
- problema: a energia do dono não muda entre as duas faixas, mas a luz quase dobra: o salto
  gasta o que a noite precisa guardar para o pico.
- direção: olhar a abertura da segunda faixa e reduzir o que ela acende de uma vez.
```
