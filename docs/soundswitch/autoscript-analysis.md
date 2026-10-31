# What SoundSwitch's autoscript does on the party's EDM tracks

Read-only analysis of 24 primary tracks (3,357 bars, about 105 minutes: 13 of the EDM
summer block, 11 of the haunted EDM block) against per-second audio energy. The
autoscript is what the choreographies in [lightshows/](../../lightshows/README.md) start
from, so this is what an author is correcting. Format background:
[file-format.md](file-format.md). Numbers are rounded.

## Summary

1. **The vocabulary is tiny and the same in every track.** Five looks cover 99 % of the
   bars: chase 43 %, groove 22 %, breathe 10 %, calm (intro, break, outro: everything
   follows Main) 17 %, pre-drop build 3.5 %. Only colours and where the looks sit change.
2. **Everything is quantised to the bar from the first beat-grid anchor.** All fixture
   intensity blocks start on a 4-bar line; positions change every 2 bars, the intensity
   look every 4, the colour sweep every 8.
3. **When it chases, it is right, but not often enough.** 94 % of chase bars have full
   energy; only 69 % of full-energy bars get a chase.
4. **First drops land late** in 8 of 24 tracks: the bass enters 4-7 bars before the chase,
   which waits for the next 8-bar line (for instance bass at bar 18, chase at 24).
5. **Vorlane chase runs over rows of 8 in DMX order**, eighth-note steps, 7 steps: a
   3.5-beat cycle that drifts against the bar. The second chase pattern ignores rows:
   four DMX-linear groups of 14 cells flash in 1/16 notes. Every chase alternates the two
   every 4 bars, in all 24 tracks.
6. **Vorlane 2 is a clone of Vorlane 1**: identical intensity scripts in all 1,368 pairs.
7. **The white strip washes the colour out.** W is lit 64 % of the show; in the follow-Main
   looks it is lit 100 % of the time colour is, in chase 26 %.
8. **The centre (Main = Hue) is almost never dark** (at most 6 % of a track): in chase it
   pulses 1.0 to 0 every beat, in groove once a bar at 0.9, in breakdowns holds 0.4-0.5.
9. **UV is never used**, and the colour "ext" byte that behaves like White shows up only
   on Main, on the icy-blue break colour and at the end of build-ups ("fade to black" is
   really "to white").
10. **Movers alternate only as 8th-note ping-pong** (Mover 1 on the beat, 2 off it), in
    breathe and some chase sections. Positions change every 8 beats in random order from
    10 presets, unrelated to the music; the only shape is kind 2, fixed parameters.
11. **Builds do not build.** None of 85 chase onsets is preceded by a rhythmic
    acceleration or more lit fixtures; growth is a Main colour fade to white or a level
    ramp. The whole set has one strobe ramp; the haze has no keys.
12. **Colour is a random analogous pair per track** (about 60 degrees apart); neighbours in
    the running order share a hue half the time; nothing tells the warm summer block from
    the haunted one.
13. **Copies of one song can differ.** A longer extended mix of the same song has no real
    chase; some lossless copies have beat grids seconds away from their mp3s.

## The five looks

VL2 = VL1 in every look. "W with colour" is the share of colour-lit time during which the
white strip is also lit.

| look (share of bars) | Main = Hue | movers | Vorlanes | W with colour |
|---|---|---|---|---|
| chase A (22 %) | 1/4 sawtooth 1.0 to 0; 8-bar colour sweep | follow Main, or 8th ping-pong | row chase, 8th steps, DMX order | 26 % |
| chase B (22 %) | same | full + shape 2 | 4 x 14 split, 1/16 flashes | 26 % |
| groove (22 %) | one 0.9 pulse per bar | full on a new preset every 2 bars | follow Main + per-cell colour twinkle | 100 % |
| breathe (10 %) | steady 0.4 or a ramp | 8th ping-pong | cells and master swell 0 to 50 % to 0 every 2 beats | 100 % |
| calm (17 %) | steady or ramp 0.1-0.5; icy blue + white in breaks | follow | follow | 100 % |
| build (3.5 %) | ramp, fade to white over 1-2 bars | follow or hold | follow | 100 % |

## The owner's questions

- **(a) White over colour.** Confirmed: 67 % of colour time has W on top, 100 % in four of
  the six looks. The choreography default (`white` off under a drawing) fixes it.
- **(b) Dark centre.** Confirmed: Hue is dark under 6 % of a track and never in a build.
- **(c) UV.** Never, on any fixture.
- **(d) Mover alternation.** Only as fast ping-pong; 18 % of mover-lit time has exactly one
  mover on. One mover is never dark for a bar while the other runs.
- **(e) Builds.** None grow in rhythm or density.

## Show-level gaps

| problem | evidence | fix in a choreography |
|---|---|---|
| same drop all night | row chase and 4 x 14 split alternate for about 47 minutes | one drawing per peak (`draw`), different per track |
| two bars are clones | 1,368 of 1,368 identical | `mirror`, `pingpong` NW and SW |
| white strip on top of colour | 67 % overlap | `white` only as `accent`/`flash` |
| no darkness, no contrast | Hue dark under 6 %, no blackout, strobe or haze | `hue: dark` in builds and breaks, one blackout bar, budgeted strobe and haze |
| random positions every 2 bars | 98 % of intervals are 8 beats | one `position` per section |
| builds do not build | 0 of 85 | `fill-up`, `faster_from`/`faster_every` |
| colour neighbours collide | half the adjacent pairs within 30 degrees | a palette per block (the show plan) |
| late or missed drops | 8 tracks 3-7 bars late | sections cut from the audio's bass-in and bass-out |
| Hue full-swing pulses | 43 % of bars | `hue: bright`, or fewer pulses |

## Effect budget (recommendations)

What the analysis suggests for a whole night; the numbers become a show plan's `budget`:

- **White strip:** an accent on peaks only, one beat each; a flash for the single last
  chorus.
- **Strobe:** a hit or a roll on a few peaks; it is the rarest thing the autoscript does.
- **UV:** the dark moments of a themed block only, under `hue: dark`, since colour hides it.
- **Haze:** a burst at a few moments, never in consecutive songs.
- **Blackout (everything off, a bar):** where the music really stops, a few times a night.
- **Subtract before adding:** each build starts with the centre dark and grows.

## Method (short)

Each `.ssfile` was parsed by the decoded grammar and sampled every 10 ms. A fixture shows
its own intensity inside its own blocks and Main's elsewhere ("effective value", the rule
`dump` uses; X6 in [experiments.md](experiments.md) confirms it). "Lit" is above 5 % with
a non-black colour. Bars are four beats counted from the first anchor. Looks were detected
per segment from the pulse intervals, the grouping of cells with equal onsets and the
mover modes. Audio classes (intro, build, drop, groove, break, outro) come from per-bar
band energy normalised to each track's 90th percentile, so a pop verse can read as a
drop. Assumptions that move the numbers: X3 (ext byte is White), X6 (follow Main), and
row-major cell order (E1).
