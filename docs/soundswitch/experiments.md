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
| X1a | Does SoundSwitch load a script whose size changed? | Compile a choreography to a file (`compile -o`), close SoundSwitch, copy it over a scratch track's `.ssfile` (keep a backup), open the track in the editor and read the edited lanes (no lights needed). | none: the editor shows the compiled lanes, or it errors, re-analyses or shows the autoscript | **Done 2026-11-04: yes** (see Results). No would have meant the writer must keep the size (rewrite values in place), a big redesign. |
| X1b | Does SoundSwitch play a resized script on the lights? | **Pending: needs the owner in the room with the lights.** Same file as X1a; play the track across the edited bars and watch the fixtures (or the DMX output monitor: dimmers at 0 through a silence bar, the white strip's one-beat accent). | none: the lights follow the compiled lanes, or the autoscript | Yes lifts the `--accept-resize` requirement of `apply`. No means SoundSwitch reads the editor data but plays something else: investigate before any real apply. |
| X2 | Which value does the editor write for 100 %? | On a scratch fixture, draw one intensity key at exactly 100 % and one at 50 % near 1:00. Save. | `dump` and a byte diff of the two keys | Replaces the autoscript's `0xffffffa0` with the editor's value as the compiler's FULL, if different. |
| X3 | What is byte 1 of the colour "ext" word: White, UV or other? | On the Main track, make one colour block pure White and another UV (if the picker offers it) near 0:10. Save. | byte diff of the C blocks | Decides whether `matrix` colours can carry white, and whether the `uv` layer can be compiled (today it is a manual cue). |
| X4 | Order of the four shape parameters. | On a mover, open one shape effect and change only its start size, then only its end size (or speed). Save after each. | byte diff after each change | Lets the tools write shape blocks (sizes, speeds) instead of copying existing ones. |
| X5 | Shape kind numbers, flag byte. | Change the same block's shape (circle to figure 8), then toggle any reverse/mirror option. Save after each. | byte diff of the shape item | Names the kinds 0-9; may add a `shape` option to `movers`. |
| X6 | Does a fixture follow Main outside its B blocks, and are keys outside a block ignored? | On Main, set intensity to 0 from 0:00 to 0:30 where a mover has no block. Watch the movers and Hue in preview. Save. | `dump` effective levels | Confirms the "effective value" rule used by `dump`, `render` and the compiler. |
| X7 | What is the new per-node trailing list of format 13? | Place an attribute cue (such as Custom Cue 1) on the haze fog track rather than Main. Save. | byte diff | Documentation today; if per-fixture cues exist, they could fire the haze from a cue instead of an intensity key. |
| X8 | E blocks are strobe: what unit are the rates? | On a Vorlane cell, add a strobe block 1:00-1:05, start rate 10, end rate 90. Save. | byte diff of the E block | Real strobe blocks for the `strobe` layer instead of 1/16-note pulses. |
| X9 | Colour per zone: which tracks hold it? | Set Vorlane 1 cells 1-8 to red from 1:00 to 1:10. | `dump` colours; expect eight new C blocks on the cell nodes, or one on the group node | Confirms that the compiler's per-cell colour (`matrix.colour`) is where SoundSwitch looks. |
| X10 | Does the haze machine react to a constant level on its fan and fog nodes (both at the rig's level, 0.5 today)? | Compile any track, apply it on a scratch copy, play it with the machine on and watch the mist and channels 504-505 in the DMX output monitor. | `dump`; the machine itself | A yes removes the experimental cue; a no means the level must be set on the machine. |
| X11 | Where does a mover's colour store UV and Amber? | On a scratch track, on Mover 1's colour lane, paint one block of pure UV (HEX in the Color Picker) near 0:10 and one of pure Amber near 0:20. Save. | byte diff of the two colour blocks (ARGB and ext words) | Lets the `uv` layer, `move: uv` and the UV vocabulary compile instead of printing manual cues. |

### Results

**X1a, 2026-11-04: done, it loads.** Happier's compiled choreography (537,096 bytes,
against 997,548 for its autoscript) was copied over its `.ssfile` and opened in the editor,
over remote desktop and without the lights: no error, no new analysis. The editor showed
the compiled data, not the autoscript: one override on Mover 1 from 0:00 to the end, Mover 1
flat at 0 until bar 9 and about 50 % from there, Main flat at 0 through bar 68 and about
85 % at bar 69, and the Vorlane W cells at 0 except one key of about 60 % at bar 81 that
falls to 0 within a beat. Opening and closing SoundSwitch, without saving, rewrote the
`.ssfile`, the `.ssa`, `.ssproj` and the track map with the same bytes (new mtimes, same
hashes), so an mtime is no sign of an edit; `apply` compares hashes.

**X1b: pending.** The visual test needs the owner in the room. Until it passes, `apply`
keeps demanding `--accept-resize`, and every other piece of work goes on in parallel.

Seen on the way: the autoscript gives the W cells colour blocks too (Happier's turn green at
1:45.758, at intensity 0). The compiler keeps them wherever it sets only intensity.

## Venue file (E)

| # | Question | Steps | Diff | What the answer changes |
|---|---|---|---|---|
| E1 | Physical order of the Vorlane cells. | In Edit Mode, on a scratch track or a static look, light only RGB 01 red, RGB 08 green, RGB 09 blue, RGB 25 magenta and W 1 white on one Vorlane. Photograph the bar. | photo | Settles `matrix.zone_order` in `rig.yml` (today `row-major-top-left`) and the block above/below the white row. |
| E2 | The fixture-record flag byte (movers differ). | In the DMX map or fixture settings, compare Mover 1 and Mover 2 (invert pan/tilt?). Toggle it on Mover 1. Save. | byte diff of the venue file | Whether movers mirror each other; mover corners in `rig.yml`. |
| E3 | Is the group field an index or a bitmask? | Move the haze to control group 4. Save. | byte diff | Documentation only. |
| E4 | Haze fixture type. | Note what the DMX map shows, set the type to Smoke/Atmospheric, save. | byte diff (type 1 to 16) | Documentation only; may let SoundSwitch's own smoke controls drive it. |
| E5 | Haze output at 0, 50, 100 %. | Same as X10, reading channels 504 and 505 in the output monitor. | output monitor | Same as X10: which level the compiler should write to the haze nodes. |
| E6 | Lane attribute ids for colour, position, strobe. | Copy a scripted track. On the copy change only a mover's colour in one block; then only its position. Save. | byte diff of the copy | Checks that the tools address the right lane per attribute. |
| E7 | Where the active venue is stored. | Switch to the other venue, quit, diff the venue file. | byte diff | If nothing changes the choice is in the registry; the tools always pick the venue by GUID from the script. |
| E8 | Static look layout. | Create one static look in slot 33: Mover 1 red, "Disco Ball", strobe 50 %. Save. | byte diff | Documentation only. |

## Playback in the room (P)

Not file questions either: they need rekordbox, SoundSwitch and the lights running, with the
owner in the room (do them with X1b).

| # | Question | Steps | What to watch | What the answer changes |
|---|---|---|---|---|
| P1 | During a blend, when do the lights switch from the outgoing track's script to the incoming one's? | Load two choreographed tracks whose looks differ at a glance (e.g. a blue sweep and a red blink). Play A, start B, then move B's channel fader up and A's down, separately and with the crossfader; also try the tempo-master button. | The bar at which the room changes look, and which control triggered it. | Today every transition is a *bridge*: the incoming track copies the outgoing one's last look over the whole overlap, so the switch is invisible wherever it happens. If the switch follows the louder channel fader, the bridge can be shortened to the bars around the fader move. |
| P2 | Where does each position preset aim in the real room? | One static look per preset (Dance Floor Centre, Crossed Over, Up, Down, DJ Booth, Stage Left, Stage Right, Stage Center) on both movers, in the haze. | Where each beam lands; whether "Crossed Over" really crosses. | The beam grammar of a set's light plan (which preset to use for drops, builds, breaks) and the simulator's guessed targets. |
| P3 | Does the Hue chandelier keep up with one pulse per beat? | Play a section with `hue: pulse` at 120 and at 130 BPM. | Whether the lamps follow each beat or lag and smooth out. | Whether a heartbeat can live in the chandelier or only in the Vorlanes (with the Hue on slower states). |

## Corners (rig)

Not a file question: which physical corner each mover and Vorlane stands in
(`lightshows/rig.yml` assumes NE/SE movers, NW/SW Vorlanes). Run `render` on a choreography
and compare the simulator with the room; fix the `corner` keys when they differ.
