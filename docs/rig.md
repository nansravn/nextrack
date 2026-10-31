# Rig — gear to technique mapping

The [transition catalog](transitions.md) is deliberately hardware-neutral. This doc
is the concrete mapping for one setup: a **Pioneer DDJ-FLX6** controller running
**Serato DJ**. If you're on different gear, the techniques are the same — only the
buttons move.

## The setup

- **Controller:** Pioneer DDJ-FLX6 (2-channel, 4-deck).
- **Software:** Serato DJ.
- **Signature feature:** **Merge FX** — a single knob that layers a build-up (riser
  + echo + filter) and drops you into the next track. Pioneer built it for exactly
  the cross-BPM, cross-genre jump that open-format sets live on.

## Technique → control

| Technique ([transitions.md](transitions.md)) | On this rig |
|---|---|
| **Echo out** | Beat FX → Echo/Delay, or the tail end of **Merge FX**; throw it on the last 2 beats and pull the fader |
| **Cross-BPM genre jump** | **Merge FX** — one knob, build over the outgoing track, land on the incoming downbeat regardless of tempo |
| **Hard cut on the downbeat** | cue the incoming deck to a **hot cue on the hook**, drop it on the 1 |
| **Loop-and-hold** | Auto/Manual **Loop** on the last bar; release with the loop-out |
| **Teasing** | jog/hot-cue in 4 bars of the next track, pull the fader back, commit on the next phrase |
| **Backspin / brake** | jog-wheel backspin, or Serato's brake/reverse pad FX |
| **Long blend / EQ swap** | channel EQs + faders; use **Key Sync** for harmonic layering |
| **Acapella over instrumental** | acapella on one deck, instrumental on the other; **Key Sync** to match |
| **Half-/double-time bridge** | pitch fader + beat-jump; feel the groove at half, then blend |

## Practical notes for open-format on this rig

- **Cue the hook, not the top.** Set hot cues on the chorus/drop of your most-played
  tracks, because you'll ride the hook window, not the whole song.
- **Fix live-band grids in Serato.** Pagode and axé recorded with a live band drift
  off the analyzer's grid — correct the beatgrid by hand on the tracks you lean on,
  or Merge FX / echo out to sidestep the grid entirely.
- **Merge FX is your block-seam tool.** The risky beat is the *genre-block change*
  ([mixing-styles.md](mixing-styles.md)); Merge FX covers it in one gesture.
- **Starter edits help.** A 16-beat beat-intro edit of a radio track (which opens on
  vocal) turns an un-mixable song into a mixable one — worth making for your
  most-played tracks.

> This doc maps *your* buttons; keep the technique names in
> [transitions.md](transitions.md) generic so the method survives a gear change.

## Lights and room

The party room is a rectangle. The lights are driven by SoundSwitch over DMX (a Control One
interface, universe 1) and a Philips Hue chandelier. The room as the choreographies see it
is [`lightshows/rig.yml`](../lightshows/rig.yml); how to write for it is in
[`lightshows/README.md`](../lightshows/README.md).

- **Two moving heads** in the north-east and south-east corners (assumed).
- **Two Vorlane VL-1000 bars** in the north-west and south-west corners (assumed), aimed
  at the centre of the room. Each is an 8 x 7 matrix of cells.
- **A Hue chandelier** with seven lamps in the centre. It follows only SoundSwitch's Main
  track, so it is controlled by the `hue` layer.
- **A haze machine** (fan and fog on two channels).

The corners are unconfirmed: the file says which fixture is which, not where it stands.
Check with `render` against the real room (see
[experiments](soundswitch/experiments.md#corners-rig)).

| Fixture | Script node (id in the owner's venue) | DMX (universe 1) | Notable channels |
|---|---|---|---|
| Mover 1 | `Mover 1` (1167) | 37-51 | 15 channels: pan/tilt 37-40, **strobe 42**, RGBWA 43-47, **UV 48**. No dimmer channel. |
| Mover 2 | `Mover 2` (1168) | 52-66 | the same layout, +15 |
| Vorlane 1 | `VORLANE VL-1000 RGBW v2` (1818) | 101-254 | **master 101** (capped at 0-127 in the "154CH Soft" mode, so the bars never exceed 50 %), strobe 102, RGB 01-48 on 103-246 (3 channels each), white 1-8 on 247-254 |
| Vorlane 2 | the second node of that name (1876) | 301-454 | the same, +200 |
| Haze | ` Lig Light LL-HZ600K` (1934) | 504-505 | **504 fan**, **505 fog**, both typed Intensity with a fixed range (fan 100, fog 175) |

Notes:

- Each Vorlane is a group node with a **master** cell (`MASTER`), 48 **RGB** cells and 8
  **W** cells, one script track each. The white strip is a row between two colour blocks of
  three rows each; the zones are taken row-major from the top left, RGB 01-24 above the
  strip, 25-48 below (unconfirmed, experiment E1).
- Node ids change between rigs; `rig.yml` names nodes and the tool looks the ids up.
- The haze nodes' names start with a space and have a double space inside (SoundSwitch
  wrote them so); `rig.yml` copies them exactly.
- The haze channels are intensity channels, so a fog burst is an intensity key on the fog
  node; whether the machine reacts is experiment X10.
