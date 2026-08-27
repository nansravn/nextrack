# Workflow — discover → document → download → organize

NEXTRACK is documentation-first. You capture the *knowledge* here in git; the
*audio* stays on your drive. Here's the loop.

## 1. Discover

You hear something worth playing — on Beatport, Tidal, a set, a friend, a
Shazam. Don't download yet. Capture it.

## 2. Document

Add the track to the [catalog](../tracks/) with whatever you know:

```yaml
- title: "Track Name"
  artist: "Artist"
  genre: afro-house         # a node id from genres/graph.yml
  bpm: 122
  key: 8A                   # Camelot (see docs/harmonic-mixing.md)
  energy: 6
  source: beatport          # beatport | tidal | promo | ...
  status: to-download       # to-download | downloaded | organized
  tags: [percussive, vocal, sunset]
  notes: "Big break at 2:30; lands great after a 150 funk half-timed."
```

`status` is the bridge between the repo and your disk — it's how you track what
still needs buying/downloading.

## 3. Download (audio stays OFF git)

When you're ready to actually play the track, buy/download it from Beatport or
Tidal to your drive. **Never commit the audio file.** `.gitignore` already
excludes every audio extension.

Set up a local folder that **mirrors this repo's genre ids**, e.g.:

```
~/Music/nextrack-audio/          # git-ignored (or outside the repo entirely)
├── afro-house/
├── brazilian-funk/
├── organic-house/
└── ...
```

Drop each download into the folder matching its `genre:` id. Flip the catalog
entry to `status: downloaded`.

> Why the separation? Committing purchased/streamed audio to a public repo is a
> copyright problem, and audio would bloat the repo. The repo is the *brain*; the
> drive is the *record box*.

## 4. Organize

- Analyze keys/BPM in your DJ software (rekordbox / Serato / Traktor / engine) —
  copy the Camelot key and BPM back into the catalog if you didn't have them.
- Slot the track into one or more [blocks](../blocks/).
- Set `status: organized` once it's tagged, in a block, and ready to play.

## The payoff

Because everything is documented, planning a gig becomes assembling:

1. Pick an arc off the [genre graph](genre-graph.md) for the crowd.
2. Assemble [blocks](../blocks/) along that arc with the right
   [energy shape](energy-arcs.md).
3. Group blocks into a [set](../sets/) for the venue.
4. (Later) attach a [light scene](../lightshows/) to each block.

Then you just... play — fluctuating within each genre pool as the room tells you.
