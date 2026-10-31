# SoundSwitch 2.11 file formats

What `scripts/soundswitch_format.py` reads and writes, and how that was learned. The
format is not documented by the vendor; everything here was reverse-engineered from the
owner's own project folder (501 track scripts, 128 AutoLoops, the venue file and the
track map). Open questions are listed in [experiments.md](experiments.md): each one is a
five-minute test in SoundSwitch.

Confidence: **confirmed** = proven by a controlled edit or by an exact match with known
data; **strong** = fits every file with no exception or a handful of explained ones;
**guess** = a name or meaning that fits but is untested.

The project folder holds, per analysed track, `{GUID}.ssfile` (the light script) and
`{GUID}.ssa` (an encrypted audio analysis, unrelated to the script: editing a script in
SoundSwitch leaves it byte-identical), plus `SoundSwitchTrackMap.bin` and
`SoundSwitchVenues.bin`. The script file is the only one the tools write.

## Results at a glance

- One grammar parses all 629 files (501 tracks, 128 AutoLoops), every byte accounted
  for, and parse then serialize reproduces each file byte for byte. The serializer
  recomputes every derived field (offsets, object ids, self-pointers, tail table), so
  the relocation rules below are proven, not copied.
- A file whose size changed has not yet been shown to load in SoundSwitch (experiment
  X1). Until then `apply` demands `--accept-resize`.
- Nothing checksums a script: no hash in the file, none in the track map.
- Structure in one line: `header, per-venue list of fixture tracks (one per device-tree
  node), global part (tempo map, Main track, attribute-cue flags), object table`.

## Primitive types

| type | encoding |
|---|---|
| u32 / i32 | 4 bytes little-endian |
| u8 | 1 byte; appears unaligned (the 17-byte keyframe, the 69-byte shape item) |
| f64 | IEEE-754 double, little-endian |
| GUID | 16 bytes, Windows layout (`uuid.UUID(bytes_le=...)`) |
| time | u32 milliseconds from the start of the track (confirmed against the known first downbeat) |
| level | u32 fraction, `value / 2^32`: 0 off, `0x7fffffff` 50 %, `0xffffffff` and its neighbours about 100 % |
| colour | 8 bytes: u32 `0xAARRGGBB`, then u32 "ext" (see [Value semantics](#value-semantics)) |
| MARK | `0x80808080`, precedes every present section C..G (0 = absent) |
| END | `0xffffffff`, ends a node's lane list |
| object tag | `0x80000000 | id`, ids 1..N in file order |

## Container and header

```
0x00  aa aa 09 55   magic                                       confirmed
0x04  u32 3         container version (same in the venue file)  confirmed
0x08  u32 offA      start of the tail = end of the body         confirmed (0 without a tail)
0x0C  u32 offB      offA + 30                                   confirmed (0 without a tail)
0x10  u32 fmt       content revision: 13 current tracks,        strong
                    12 for old tracks and all AutoLoops
0x14  u32 n_venues  2 in this project; 2-4 in AutoLoops         confirmed
0x18  venue[n_venues]
```

`venue = u32 4, GUID, u32 3, u32 n_nodes, node[n_nodes], u32 1, u32 0`. Each track holds
one section per venue; an empty venue has 0 nodes. The constants 4, 3 and the trailer
`1, 0` are identical in all files (meaning unknown).

Node ids are not stable across files: the same fixture can carry different ids in files
made against older venue layouts, and some files also hold tracks for stale ids. A writer
must address a track **by node id**, never by position.

## Fixture track (node) grammar

```
node  = u32 node_id
        lane* END                      ; fixtures: exactly one lane, attr 4
        B link C D E F G
lane  = u32 attr  u32 ver(=1)  u32 has_default(0|1)  [u32 default]  u32 n  key{n}
key   = u32 type(=2) u32 t u32 t(same) u32 level u8 flag(=0)               ; 17 bytes
B     = u32 0                                           ; absent (Main track only)
      | u32 1  u32 ver(=1)  u32 n  bblock{n}
bblock= u32 1 u32 1 u32 t_start u32 t_end                                 ; 16 bytes
link  = u32      ; 1 = top level, else the owning fixture's node id
C     = u32 0 | MARK u32 ver(=1) u32 n  cblock{n}
cblock= u32 1 u32 2 u32 1 u32 t_start u32 t_end colour start colour end   ; 36 bytes
D     = u32 0 | MARK u32 ver(=2) u32 1  u32 p (GUID preset, u32 index){p}  u32 n  dflag{n}
dflag = u32 1 u32 1 u32 t u32 1 u32 preset_index                          ; 20 bytes
E     = u32 0 | MARK u32 ver(=1) u32 n  eblock{n}
eblock= u32 1 u32 1 u32 1 u32 t_start u32 t_end f64 start f64 end         ; 36 bytes
F     = u32 0 | MARK u32 ver(=1) u32 n  bblock{n}                         ; 16-byte blocks
G     = u32 0 | MARK u32 ver(=1) u32 1  u32 n  gitem{n}
gitem = u32 0 u32 2 f64 p0 p1 p2 p3 u8 flag u32 1 u32 t_start u32 t_end
        OBJ u32 ptr                                                       ; 69 bytes
OBJ   = u32 (0x80000000 | obj_id) u32 kind u32 kver(=1)                   ; in the tail table
ptr   = file offset of OBJ + 4                                            ; a self-pointer
```

The values in parentheses held in every one of the 629 files.

## Global part and tail

```
global = u32 1
         u32 n  (u32 1, u32 t, f64 bpm){n}        ; tempo map: beat-grid anchors    confirmed
         15 constant bytes                          ; unknown
         MAIN                                       ; node grammar with id 2          confirmed
         8 x u32 (1,0,0,1,1,0,1,1)                  ; constant, unknown
         u32 p (GUID attr_cue, u32 index){p}        ; attribute-cue palette
         u32 n (u32 1, u32 1, u32 t, u32 index){n}  ; attribute-cue flags
         u32 a  u32 b  u8 0  u8 1                   ; tracks (0,0); AutoLoops (16,1)
         [fmt >= 13: u32 1, (MARK u32 1 u32 0){total nodes}]   ; one empty list per fixture track
tail   = at offA: 30 constant bytes
         at offB: u32 1, u32 N, i32 -N, u32 1, (u32 obj_offset, u32 12, u32 0, u32 1){N},
                  END, u32 7, "Default" (7 ASCII bytes)
```

- **Main** (pseudo-node 2) has B absent, link 0, F absent. Its lane list is attr 4 with a
  default, then attrs 2, 3, 4, 5, 6, 7 with no keys in any file. It sits after every venue
  block, not near the start of the file.
- **The tail table is the object table**: one entry per shape item (G), ids 1..N in file
  order, each followed by its self-pointer.
- A file with no shape item has **no tail**: offA = offB = 0. Seen only in AutoLoops; the
  serializer reproduces it.
- The tempo map has several anchors in about a fifth of the tracks (variable tempo). The
  compiler refuses a track with more than 8 anchors, because bar numbers would no longer
  follow the music.

## What each section means

| section | meaning | confidence | evidence |
|---|---|---|---|
| lane attr 4 | **intensity curve**: breakpoints, linear in between | confirmed | the owner zeroed a range in SoundSwitch and exactly two keys changed |
| key type, flag, second time | always 2, 0, equal to the first | confirmed constant | 34 M keys |
| B | **intensity blocks**: where a fixture's own curve overrides Main | strong | 99.94 % of fixture keys lie in a B block; the exceptions sit in 7 files |
| link | owner of a cell: cells, MASTER and W of a Vorlane point at the Vorlane node, haze channels at the haze group, fixtures and groups at 1 | strong | |
| C | **colour blocks** (start, end, start colour, end colour) | confirmed structure; fade meaning strong | 59 % of Main's colour blocks are gradients (8,605 of 14,543), against 0.15 % of the fixtures' |
| D | **position flags**: palette maps index to a position-preset GUID | confirmed | GUIDs resolve in the venue file |
| F | **position blocks**: the D flags live inside these | strong | every flag is inside an F block |
| G | **movement shape blocks**: kind (0-9), four doubles, a flag | strong guess | never overlaps F, so a movement lane holds either positions or shapes |
| E | **strobe blocks** (start rate, end rate) | strong guess | rare; all inside B blocks |
| Main | **the Main / Master track**; every fixture follows it outside its own blocks, and Philips Hue follows only it | confirmed to exist; Hue link strong (vendor docs) | |
| cue palette and flags | **attribute cues** on Main, by GUID | confirmed | names resolve in the venue file |
| tempo map | (ms, BPM) anchors | confirmed | |

"Follow Main" is structural: a fixture follows Main wherever it has no B block. A
fixture lane value is never a "follow" marker (`0xfffffffe` is just 100 %).

Not in the script: phrase or section analysis and the audio beat analysis.

## Value semantics

- **Level.** The autoscript writes "full" as `0xffffffa0` and pulses as
  `0 -> full -> (about an eighth note) -> 0`. Hand edits give `0xfffffffe`. The editor's
  own 100 % value is unverified (X2); the tools write the autoscript's `0xffffffa0`.
- **Colour ext word.** Only the Main track uses it, always `0x0000XX00`, often on black
  or on an icy blue. Byte 1 behaves as a **White** component, not UV (X3 confirms).
- **Colour gradient.** A C block fades from its start colour at `start` to its end colour
  at `end`; the tools read every byte of the ARGB word and of the ext word as linear in
  between (`colour_at`). Most of Main's blocks are gradients, so an edit that cuts a block
  gives each remaining piece the colours shown at its new ends (rounded to whole bytes),
  and the room outside the edit shows what it showed.
- **AutoLoops.** Format 12, factory venues beside the owner's, a single anchor at 100 BPM,
  content within 16 bars.
- **Shape parameters.** Movers always carry four 0.5 values; Main uses other tuples.
  Whether they read as (size, size, centre, centre) or as start/end pairs is open (X4).

## Writer rules

What a change of size must update, and nothing else:

1. Counts: lane `n`; B, C, D, E, F, G `n`; palette `p`; tempo and cue counts. For format
   13, keep one trailing empty list per node.
2. Every shape item's `ptr` (OBJ offset + 4) after the edit point.
3. Object ids renumbered 1..N in file order (every real file is sequential).
4. The tail table: N, -N and every `obj_offset`.
5. `offA` (end of the body) and `offB` (`offA + 30`). With N = 0 the real files drop the
   tail and write both as 0.
6. No checksum, no size elsewhere; the `.ssa` is untouched.

Keep keys sorted by time (true of every lane seen) and blocks sorted and non-overlapping.
An edit that keeps the size needs no relocation. The tools always go
`parse -> edit the model -> serialize`, and `apply` re-parses the result and refuses
unless it equals the model, everything outside the venue's tracks and Main equals the
base, and outside the sections those tracks show what the base shows (the safety model in
[scripts/README.md](../../scripts/README.md#safety-model-of-apply---apply)).

## TrackMap

`SoundSwitchTrackMap.bin` says which script GUID is which song. After a 24-byte header
come entries; `read_trackmap` returns, per entry, the script GUID, title, artist, audio
path, BPM and duration:

```
entry = u32 kind (5 library track, 4 SoundSwitch demo track) u8 1  GUID
        (u32 1, string){3}      ; title, artist, audio path
        u32 bpm  u32 duration_ms  14 trailer bytes
string = u32 char count (incl. NUL), UTF-16LE
```

Kind 4 entries carry extra bytes after the trailer, skipped silently, as is the list of
external-id strings after the last entry. Any other unreadable stretch becomes a
warning (`track map: skipped N bytes at 0x...`), never a failure. Titles and artists are
what `Artist — Title` in a choreography is matched against, along with the GUID. A GUID
can be listed twice (the owner's map has one, with identical rows); the project reader
keeps the first entry.

## Venues

`SoundSwitchVenues.bin` is the rig: the same container, version 3. The tools read three
things per venue: **the venue** (name and GUID, one section per venue in every script),
the **device tree** (node id, name, parent, static-look number, colour) and the **position
presets**. The owner's rig, decoded, is in [../rig.md](../rig.md#lights-and-room).

```
Venue    04 GUID 01 Str(name) 0f 02 01 nprofiles Profile*  FixtureList  StateTable  Unnamed*  Tree
Tree     next_node_id nroots (kind Node)*nroots          ; kind 1 = leaf, 0 = group
Node     03 02 id 01 Str(name) ( look# ARGB  |  01 Str(model) n (kind Node)*n ARGB )
Preset   02 nven (GUID 02 n (node 01 pan_u32 tilt_u32)*n)*nven 01 Str(name) ARGB GUID i32 next
Str      u32 char count (incl. NUL), UTF-16LE
```

- Device tree nodes are found by their head `03 02`; a venue with no fixtures (an empty
  "second home" venue) has no tree, and its body can contain byte patterns that look like
  one, so the tree is validated, not matched by the first hit.
- A preset stores, per mover node, a 16-bit pan and tilt each repeated in both halves of
  a u32 (`value * 0x10001`); `0x7fffffff` means unset. A preset also keeps stale entries
  for nodes that no longer exist; the tools ignore them.
- Fixture profiles are embedded in full (modes, cells, channels, ranges). The tools do
  not need them: DMX addresses live in [../rig.md](../rig.md#lights-and-room).
- Attribute cues point at deleted nodes only, and the 32 static looks are factory data
  that drive nothing on this rig. Neither is touched.
- A script's lane "attr 4" is not the profile enum (where 4 is tilt): Vorlane cells have
  no tilt. It most likely addresses a virtual per-cell intensity (guess, venue
  experiment E6).
- **Philips Hue is not part of the venue.** No node, no DMX patch; the bulbs follow the
  Main track, and their bridge configuration lives under the app-data folder, which the
  tools never read.

## SoundSwitch terms and the data

| UI term | Data concept |
|---|---|
| Project (`.ssproj`) | root container: venues, fixture patch, the library of positions, attribute cues, static looks and AutoLoops |
| Scripted Track / lightshow | one `{GUID}.ssfile` per audio file; the GUID is the `SOUNDSWITCH_ID` tag in the audio file, listed in the track map |
| Venue | a rig; every script holds one section per venue |
| Fixture track, cell | a node of the device tree and its timeline row; a multi-cell fixture is a group node with one cell track each |
| Master / Main track | pseudo-node 2: drives every fixture, and Hue |
| Intensity line, node | the attr-4 lane and its keys |
| Colour block, colour transition | C block with equal / different start and end colours |
| Position cue, position flag | preset by GUID in the venue; D flag referencing it by palette index |
| Movement shape effect | G item |
| Strobe block | E block |
| Attribute cue | palette GUID plus flag on Main |
| Override | a B block: the fixture's own data replaces Main inside it |
| Autoloop | a fallback timeline of 8 to 128 bars, stored as an `SSAutoLoopN.ssfile` |
| Static look | live scene, stored in the venue file |
| Phrase (Intro, Main 1, Main 2, Middle, Bridge, Outro) | analysis in the `.ssa`, not in the script |

## Seeing the show

SoundSwitch has no 3D preview. `nextrack_lights.py render` simulates the room in an HTML
page; for the real thing, SoundSwitch can send Art-Net to a visualizer on the same PC:
tick the localhost Art-Net node in its hardware preferences and listen on Art-Net
universe 0. Free options: XR_DMX_Visualiser (zero-config, has a haze fixture), Capture
(Student edition, free), QLC+ 5 (3D view, enable input passthrough). Start the
visualizer first. See [../../lightshows/README.md](../../lightshows/README.md#seeing-the-show).
