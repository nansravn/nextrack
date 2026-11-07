# Lens: drops

Judge the moments that must land. At each of the night's top drops the light needs contrast
(a dip or near-darkness before, then a hit on the downbeat), change, and freshness; the main
drop of each track gets the bigger answer; builds grow into the drop.

## Judges

- Contrast, change and freshness at the night's top drops.
- The main drop of each track against its other drops.
- Builds going into drops: growing in rate and density, starting subtracted.
- Rare resources kept for the climaxes.

## Run

`<show>` stands for the show folder named in your brief; `<track>` is `Artist — Title` as the
file names it.

```
uv run scripts/nextrack_show.py report <show> --section drops,builds,peaks,hits
uv run scripts/nextrack_show.py zoom <show> "<track>" <bar>
```

Run `zoom` once for each of the top drops (the first ranks in `drops`), with `<bar>` the
drop's bar from its line. Add `--before 3 --after 2` to see the build and the aftermath.

## Questions

1. For each top drop: is `contrast` clearly positive (about +3 or more)? A drop with
   `contrast +0.0` did not land.
2. Is there a dip or near-darkness before the hit (`light 0>8`, or a `dip` in `builds`), or at
   least a ramp? A `flat` build into a top drop is a miss.
3. `changes`: does the drop change several dimensions (5 or more of 9), or is it the same look
   made louder?
4. `fresh`: has the drop's look been used in the previous 10 minutes (`fresh 0.00`)? Do two
   consecutive top drops share draw, matrix colour and mover move?
5. In `zoom`: does the light hit on the downbeat of the drop bar, or late? Does the kick row
   align with the first light step?
6. Main drop: does the track's `main` drop get a larger response than its other drops?
7. Is `agreement` (salience against response) low, so that big drops get small answers?
8. Builds: do the light's `activity` and `brightness` slopes rise with the music's slope, or
   stay level or fall?
9. Are the rare resources (strobe, white, solid) spent before the top drops, so nothing is
   left for the climax? Check the accents at each peak.
10. In `hits`: is a strong kick (`kick 9`) met by a light that rises (`0>8`), not by a light
    that was already high?

## Severity

- `grave`: a top drop of the night with contrast near 0 and few changes, or with a late or
  missing hit in `zoom`; or the main drop of a track answered less than a minor drop; or no
  build into the top drop at all.
- `moderado`: a drop below the top that fails one criterion (stale look, flat build, accents
  spent); low agreement across the mid-ranked drops.
- `menor`: polish, such as a one-step offset in a hit that otherwise lands.

## Finding format

Write each finding in pt-BR with `lente`, `severidade`, `unidade`, `evidência`, `problema` and
`direção`, as the critic agent file defines. Example:

```
- lente: drops
- severidade: grave
- unidade: The Akan, drop do compasso 105
- evidência: "rank 2 · 7:12 · The Akan 105 · salience 0.84 ... response 0.22 (contrast +0.0, changes 7, fresh 0.11)"; zoom: a luz já estava no máximo no compasso 104
- problema: o segundo maior drop da noite não tem contraste: a luz chega ao drop já alta e
  nada sobra para o golpe.
- direção: olhar a construção antes do drop e abrir espaço (um respiro ou escuro curto) para
  que o golpe tenha de onde subir.
```
