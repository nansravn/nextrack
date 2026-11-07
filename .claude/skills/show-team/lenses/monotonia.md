# Lens: monotonia

Judge the night's repetition and predictability: long static stretches, neighbouring tracks
that look alike, a drop template that never changes. Also guard the other side: change that
lands off the phrase lines is chaos, not variety. Judge over the night, not one track.

## Judges

- Repetition: the same signature (look, gesture, colours, aims) held for too long.
- Static stretches: the longest runs of one signature, across track boundaries too.
- Neighbours alike: consecutive tracks that a viewer cannot tell apart.
- Predictable drops: the same (before, at) template under many drops.
- The chaos guard: the light's changes should start a map section or fall on a 4-bar line.

## Run

`<show>` stands for the show folder named in your brief.

```
uv run scripts/nextrack_show.py report <show> --section variety,identity
uv run scripts/nextrack_show.py report <show> --section tracks
```

Read the `tracks` section only for the music under the static runs the `variety` section
names (their bars, the strips and the section lines), to learn whether the music itself is
static there.

## Questions

1. What are the five longest static runs (`variety`, "static runs"), and how long is each in
   minutes? Is the music under each one really static (flat `music` strip, one map section),
   or does it move while the light does not?
2. Does the per-minute entropy row dip to 0-3 for several minutes in a row? Where?
3. Which neighbouring tracks have a `similarity` above the show's `neighbours-differ` max (else 0.85)? Are they meant to be
   alike by the story (the identity's signatures)?
4. Are there few distinct drop templates for many drops ("drop templates: N distinct of M")?
   A template shared by most drops means the drops are predictable.
5. Does one value dominate a dimension for most of the night (`dominant ... 86%`) without an
   identity signature declaring it? A declared dominance is deliberate; an undeclared one is
   an accident.
6. Chaos guard: is the `phrase lines` share high (about 70% or more)? Low means changes land
   off the phrase, which reads as noise.
7. Does the night show waves, with quieter stretches between busy ones, or one flat level?
8. Is any accent (white, strobe) used on so many hits that it stops meaning anything?

Numbers are evidence, not taste: cite the line that made you answer.

## Severity

Let T be the static-run threshold: the show's `static-run` `max_seconds` when its `advice:` or
`rules:` declares one, otherwise 60 s (a replacement, not an alternative). On a show that
declares 120, a 1:20 run is not a finding at all.

- `grave`: a static run of T or more that either has music changing section kind under it (for
  example `drop+break`) or covers one of the night's top drops. A light that sits still through
  a top drop without reaching T is the `drops` lens's business.
- `moderado`: a static run of T or more under one section kind; or two neighbours whose
  `similarity` is above the show's `neighbours-differ` `max_similarity` (else 0.85).
- `menor`: polish, such as a single repeated colour pair or an entropy dip of one minute.

## Finding format

Write each finding in pt-BR with `lente`, `severidade`, `unidade`, `evidência`, `problema` and
`direção`, as the critic agent file defines. Example (illustrative: the track and numbers are invented, for a show with T = 60 s):

```
- lente: monotonia
- severidade: grave
- unidade: <Faixa X>
- evidência: "<clock> · <Faixa X> 27-68 · 1:30 · drop+break" (variety, static runs)
- problema: a mesma luz fica 1:30 parada enquanto a música passa de drop para break: a luz
  não acompanha a mudança de seção.
- direção: olhar onde o break começa e que dimensão da luz poderia trocar ali, sem sair da
  identidade.
```
