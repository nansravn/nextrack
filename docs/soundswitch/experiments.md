# SoundSwitch experiments

Questions the [file format](file-format.md) analysis could not settle from bytes alone.
Each takes five minutes or less in SoundSwitch and leaves a diff that answers it.

**How to run one.** Work on a scratch copy of the project when you can. Otherwise
close SoundSwitch before and after, and copy the project folder first.

- Before: `nextrack_lights.py dump "<track>" > before.txt` (or `--yaml`).
- Do the steps, save (Save Lightshow), close SoundSwitch.
- After: `dump` again into `after.txt`, then `diff before.txt after.txt`. For a question
  about exact bytes, diff the `.ssfile` (`cmp -l`) or the whole project folder instead.

Use a track you do not care about. A `dump` shows lit share, pulses, colours, positions
and shapes per phrase and fixture, so most changes show up there; byte diffs settle
what `dump` does not show.

## Script format (X)

| # | Question | Steps in SoundSwitch | Diff | What the answer changes |
|---|---|---|---|---|
| X1 | Does SoundSwitch load a script whose size changed? | Compile a choreography to a file (`compile -o`), close SoundSwitch, copy it over a scratch track's `.ssfile` (keep a backup), open the track, play across the edited bars. | none: it loads and plays, or it errors/ignores the file | Yes lifts the `--accept-resize` requirement of `apply`. No means the writer must keep the size (rewrite values in place), a big redesign. |
| X2 | Which value does the editor write for 100 %? | On a scratch fixture, draw one intensity key at exactly 100 % and one at 50 % near 1:00. Save. | `dump` and a byte diff of the two keys | Replaces the autoscript's `0xffffffa0` with the editor's value as the compiler's FULL, if different. |
| X3 | What is byte 1 of the colour "ext" word: White, UV or other? | On the Main track, make one colour block pure White and another UV (if the picker offers it) near 0:10. Save. | byte diff of the C blocks | Decides whether `matrix` colours can carry white, and whether the `uv` layer can be compiled (today it is a manual cue). |
| X4 | Order of the four shape parameters. | On a mover, open one shape effect and change only its start size, then only its end size (or speed). Save after each. | byte diff after each change | Lets the tools write shape blocks (sizes, speeds) instead of copying existing ones. |
| X5 | Shape kind numbers, flag byte. | Change the same block's shape (circle to figure 8), then toggle any reverse/mirror option. Save after each. | byte diff of the shape item | Names the kinds 0-9; may add a `shape` option to `movers`. |
| X6 | Does a fixture follow Main outside its B blocks, and are keys outside a block ignored? | On Main, set intensity to 0 from 0:00 to 0:30 where a mover has no block. Watch the movers and Hue in preview. Save. | `dump` effective levels | Confirms the "effective value" rule used by `dump`, `render` and the compiler. |
| X7 | What is the new per-node trailing list of format 13? | Place an attribute cue (such as Custom Cue 1) on the haze fog track rather than Main. Save. | byte diff | Documentation today; if per-fixture cues exist, they could fire the haze from a cue instead of an intensity key. |
| X8 | E blocks are strobe: what unit are the rates? | On a Vorlane cell, add a strobe block 1:00-1:05, start rate 10, end rate 90. Save. | byte diff of the E block | Real strobe blocks for the `strobe` layer instead of 1/16-note pulses. |
| X9 | Colour per zone: which tracks hold it? | Set Vorlane 1 cells 1-8 to red from 1:00 to 1:10. | `dump` colours; expect eight new C blocks on the cell nodes, or one on the group node | Confirms that the compiler's per-cell colour (`matrix.colour`) is where SoundSwitch looks. |
| X10 | Does the haze machine react to intensity keys on its fog node (Main - 2)? | On a scratch track, put 0 %, 50 % and 100 % intensity blocks on the fog node (the second haze channel). Play it with the machine on and watch the fog; the DMX output monitor shows channel 505 (fan 504). | `dump`; the machine itself | The `haze` layer is marked experimental (every use prints a manual cue). A yes removes that warning; a no means haze stays a manual cue or an attribute cue. |

## Venue file (E)

| # | Question | Steps | Diff | What the answer changes |
|---|---|---|---|---|
| E1 | Physical order of the Vorlane cells. | In Edit Mode, on a scratch track or a static look, light only RGB 01 red, RGB 08 green, RGB 09 blue, RGB 25 magenta and W 1 white on one Vorlane. Photograph the bar. | photo | Settles `matrix.zone_order` in `rig.yml` (today `row-major-top-left`) and the block above/below the white row. |
| E2 | The fixture-record flag byte (movers differ). | In the DMX map or fixture settings, compare Mover 1 and Mover 2 (invert pan/tilt?). Toggle it on Mover 1. Save. | byte diff of the venue file | Whether movers mirror each other; mover corners in `rig.yml`. |
| E3 | Is the group field an index or a bitmask? | Move the haze to control group 4. Save. | byte diff | Documentation only. |
| E4 | Haze fixture type. | Note what the DMX map shows, set the type to Smoke/Atmospheric, save. | byte diff (type 1 to 16) | Documentation only; may let SoundSwitch's own smoke controls drive it. |
| E5 | Haze output at 0, 50, 100 %. | Same as X10, reading channels 504 and 505 in the output monitor. | output monitor | Same as X10: how the compiler should write `haze` levels. |
| E6 | Lane attribute ids for colour, position, strobe. | Copy a scripted track. On the copy change only a mover's colour in one block; then only its position. Save. | byte diff of the copy | Checks that the tools address the right lane per attribute. |
| E7 | Where the active venue is stored. | Switch to the other venue, quit, diff the venue file. | byte diff | If nothing changes the choice is in the registry; the tools always pick the venue by GUID from the script. |
| E8 | Static look layout. | Create one static look in slot 33: Mover 1 red, "Disco Ball", strobe 50 %. Save. | byte diff | Documentation only. |

## Corners (rig)

Not a file question: which physical corner each mover and Vorlane stands in
(`lightshows/rig.yml` assumes NE/SE movers, NW/SW Vorlanes). Run `render` on a choreography
and compare the simulator with the room; fix the `corner` keys when they differ.
