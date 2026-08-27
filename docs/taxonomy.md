# Taxonomy — genre glossary

The vocabulary NEXTRACK uses. Each genre here corresponds to a node `id` in
[`../genres/graph.yml`](../genres/graph.yml). BPM ranges are typical, not rules —
half/double-time bridging is normal and encoded as graph edges.

> Terms: **BPM** = beats per minute. **Key** = musical key, tracked in the
> [Camelot](harmonic-mixing.md) system for harmonic mixing. **Energy** = a 1–10
> feel rating (see [energy-arcs.md](energy-arcs.md)).

---

## 🇧🇷 Brazilian families

### `brazilian-funk` — Funk (carioca / mandelão)
The sound of the baile. High rhythmic energy, chant hooks, heavy low end.
- **Subgenres:** funk 130 (carioca), funk 150 *mandelão*, brega funk (Recife,
  ~105–130), funk melody, rasteirinha, funk automotivo.
- **BPM:** ~125–160 · **Energy:** 6–10 · **Feel:** peak, rhythmic, vocal.

### `brazilian-bass`
Brazil's biggest electronic export — the Alok / Vintage Culture / Cat Dealers
lane. Deep, melodic, festival-ready house with a signature bassline.
- **BPM:** ~120–128 · **Energy:** 5–8 · **Feel:** melodic, driving, radio-friendly.

### `afro-brasileiro`
Afro house and organic house infused with Brazilian percussion, berimbau,
batuque, and vocal chops. The bridge between global afro house and BR roots.
- **BPM:** ~118–125 · **Energy:** 5–8 · **Feel:** percussive, hypnotic, warm.

### `samba-pagode`
Samba, pagode, samba-rock and their electronic edits ("samba-house", roda
eletrônica). Great for identity moments and singalongs.
- **BPM:** ~95–105 (edits vary) · **Energy:** 4–7 · **Feel:** joyful, swung, vocal.

### `forro-piseiro`
Forró (pé de serra, eletrônico), piseiro, and arrocha. Northeastern dance music;
piseiro edits sit comfortably in a club tempo.
- **BPM:** ~120–140 · **Energy:** 5–8 · **Feel:** danceable, romantic, regional.

### `sertanejo`
Sertanejo universitário, sofrência, agronejo. Mostly a "radio"/crowd-moment tool
rather than a beatmatched lane — but club edits and remixes exist.
- **BPM:** song-dependent (~120–160 for edits) · **Energy:** 3–7 · **Feel:** singalong.

### `axe`
Axé and its retro / pagodão baiano cousins — festive, singalong Bahian party music.
An **open-format** lane: joined to its neighbors by cuts and echo-outs, not blends.
- **BPM:** ~100–115 · **Energy:** 6–8 · **Feel:** festive, singalong, party.

### `mpb-bossa`
MPB, bossa nova, tropicália, and their downtempo/electronic reinterpretations.
Warmup and cooldown gold; also `tecnobrega`/`brega` textures.
- **BPM:** ~90–115 · **Energy:** 2–5 · **Feel:** warm, nostalgic, melodic.

---

## 🌍 Global / EDM families

### `organic-house`
Downtempo-adjacent, percussive, melodic house (Anjunadeep / All Day I Dream /
Bedouin vibe). The universal warmup and sunset lane.
- **BPM:** ~108–122 · **Energy:** 3–6 · **Feel:** warm, textured, hypnotic.

### `deep-house`
Groove-forward, soulful, sub-heavy house. The dependable mid-warmup connective
tissue.
- **BPM:** ~118–124 · **Energy:** 4–7 · **Feel:** smooth, groovy.

### `tech-house`
Punchy, minimal-leaning, bass-driven club house. Peak-time workhorse.
- **BPM:** ~122–128 · **Energy:** 6–9 · **Feel:** driving, percussive.

### `afro-house`
Global afro house — melodic, percussive, spiritual (Keinemusik / &ME / Black
Coffee lane). Bridges beautifully into `afro-brasileiro` and `amapiano`.
- **BPM:** ~118–125 · **Energy:** 5–8 · **Feel:** percussive, deep, emotive.

### `amapiano`
South African house with log-drum bass and jazzy, spacious grooves. Slower,
patient, powerful — a natural bridge between afro and downtempo lanes.
- **BPM:** ~108–118 · **Energy:** 4–7 · **Feel:** spacious, swung, hypnotic.

### `melodic-house-techno`
Emotional, cinematic, driving (Afterlife / Anjunadeep-darker lane). The
build-to-peak connector.
- **BPM:** ~120–126 · **Energy:** 6–9 · **Feel:** cinematic, euphoric, dark.

### `techno-peak`
Peak-time and driving techno. The hardest, highest-energy node.
- **BPM:** ~128–140+ · **Energy:** 8–10 · **Feel:** relentless, hypnotic, hard.

### `nu-disco-funk`
Nu-disco, indie dance, French touch, and US funk/boogie edits. Playful,
crossover, vocal.
- **BPM:** ~110–124 · **Energy:** 4–7 · **Feel:** groovy, joyful, retro.

### `global-bass`
The percussive global-club umbrella: baile-influenced global bass, moombahton,
reggaeton, dembow, guaracha. Shares rhythmic DNA with `brazilian-funk`.
- **BPM:** ~90–130 · **Energy:** 6–9 · **Feel:** rhythmic, tropical, vocal.

### `pop-dance`
Commercial pop and dance — radio pop, dance-pop, eurodance, and the 2000s-throwback
palette that powers themed parties. An **open-format** lane: play the hook, join
blocks with cuts, echo-outs, and FX rather than long blends.
- **BPM:** ~100–132 (often flat) · **Energy:** 5–9 · **Feel:** commercial, singalong, throwback.

---

## Extending the taxonomy

Add a genre by adding a node to [`../genres/graph.yml`](../genres/graph.yml) and
a short entry here. Keep `id`s in `kebab-case` and stable — tracks reference them.
Prefer a handful of well-connected nodes over dozens of thin ones; use
`subgenres` inside a node for finer detail. An edge's `via` can describe an
**open-format bridge** (a hard cut, echo out, or FX pass), not only a beatmatched
blend — see [mixing-styles.md](mixing-styles.md).
