# C — The craft, and the analyses that feed it

Research notes for project 2 (an autonomous AI light team for NEXTRACK). Front C: how human
lighting designers plan electronic-music shows for energy and immersion, research on
music-driven lighting and close analogs, the MIR analyses that serve the owner's four success
criteria, and the precompute vs on-demand question.

Date: 2026-11-07. Repo: `the repo root` at `78e61eb` (read-only).

**Marks.** **[read]**: I opened the source (web page, PDF text or repo file) and the claim is
from it. **[repo]**: I measured it in the repo myself (commands given). **[snippet]**: seen only
in a search-engine summary, page not opened: treat as unverified. **[recalled]**: from memory,
unverified.

The owner's four criteria, used as labels below: **M** not monotonous, **D** immersive at the
drops, **T** follows the energy of each track, **S** follows the energy of the set.

---

## 0. Top findings

1. **The critic's music level is saturated.** Over the 15 Hï Ibiza maps, 82 % of all bars have
   music level 9 and 88 % have 8 or 9 [repo]. The level is the highest of kick, bass and other,
   and each voice is normalised to *its own* 95th-percentile loudness (`LOUD_PERCENTILE = 95`,
   3 dB per digit) [repo: `scripts/musical_map.py`]. So the strip cannot show energy *inside* a
   drop or a groove (T), and says nothing comparable *across* tracks (S).
2. **The light level index cannot see what makes peak light intense.** It ignores rate (a draw at
   1/16 scores the same as at 1 bar), strobe, white, colour and aim changes, and gives
   pingpong/blink a flat 0.5 [read: `lightshows/shows/README.md`, Levels]. Result on Hï Ibiza:
   51 % of the night's bars score 3 and 30 % score 4; no bar scores above 5 [repo]. In the peaks
   table, 30 of the 35 drops score 3 at the drop. 17 of the 35 have the same level before and at
   the drop, or a lower one. Most of the rest rise only from a dark bar (0) to 3 [repo]. The mean light level per track *falls* as the owner's energy
   rises. The e6 tracks average 3.4, the e7 tracks 3.1, the e8 tracks 2.8 and Dirty Cash (e9)
   2.7 [repo]. Either the show does not follow the set, or the index cannot tell. The critic
   cannot decide which, and that is the main gap for D and S.
3. **The views never read the energy plan.** The pool's `energy` (1–10), the block's
   `energy: [6, 9]` and `function: build` are not inputs to `report` [read: brief, confirmed in
   `show_views.py` docstrings]. S has no target to compare against.
4. **Practitioners' craft is consistent and mostly codifiable.** Most sources agree on these:
   contrast and near-darkness before payoffs; a distinct look per major drop; save the big
   effects for the climaxes; intensity in waves, with breathers after intense stretches; a small
   palette with roles per fixture group; "start with a single lamp and add" in a club; judge a
   show over hours, not over one 8-minute track [read: Ticket Fairy, Grunwald/Panorama Bar,
   Greil/Chauvet]. Section 7 turns these into rules, advice and rubric items.
5. **The research on music→light warns against literal mapping.** Rule-based mappings scored 2.7
   against 4.3 for a learned model and 4.5 for the real engineers (7-point scale) [read:
   Skip-BART]. Raters called event-driven AI lighting "repetitive", "predictable" and "too
   explicit" [read: Glow with the Flow]. Dance-generation research found that beat-alignment and
   FID metrics correlate poorly with quality, and relies on user studies [read: EDGE and later
   papers' critiques]. Metrics should therefore gate gross failures and inform a judging agent,
   not define "good".
6. **EDM structure is well characterised; drops are the peak of the experience.** The "break
   routine" (breakdown → build-up → drop) makes the amplitude profile U-shaped, and drops give
   significantly larger skin-conductance responses [read: Solberg & Dibben 2019]. Dancers'
   movement falls and rises with it, and they synchronise better after the drop [read: Solberg &
   Jensenius]. Later drops in a track are usually the bigger ones [read: Solberg & Dibben;
   Raveform]. The repo's own drop rule, the bass coming back after a break, matches the MIR
   definition of a drop: the full bassline re-introduced after a build [read: Yadati et al. 2014].
7. **For set-level energy, loudness is the wrong signal.** DJs keep loudness homogeneous across a
   set. Timbre changes smoothly, and the order of tracks matters [read: Kell & Tzanetakis 2013].
   The set arc therefore has to come from the owner's labels plus BPM, onset density, brightness
   and texture, not from LUFS.
8. **Recommendation: precompute the music, compute the light-versus-music views on demand, and
   never have agents run audio analysis ad hoc.** Details in section 8.

---

## 1. What the repo computes and states today (grounding)

### 1.1 Musical maps (`lightshows/maps/<slug>.yml`) [read]

- Per bar and per 1/16 step, five voices (`vocals`, `kick`, `perc`, `bass`, `other`) from
  Demucs `htdemucs`, with drums split by frequency into kick and perc. Each voice is a digit
  0–9, where 9 is that voice's own loud level and each digit below is 3 dB quieter. Bleed voices
  read 0. `entries`/`exits`, stereo `balance` for perc and other, `onsets.kick`/`onsets.perc` per
  step (strength 1–9), vocal `register` per step and vocal `phrases`.
- `sections` with kinds `intro/groove/break/build/drop/outro`, cut from the low end (kick+bass
  power sum). A bar is *full* when the low end is within 6 dB of its loud level and kick and bass
  are each within 15 dB of their own; a break starts with at least 2 bars at least 9 dB under
  full. `drops[].db` measures kick+bass against the two bars before, so a drop after silence
  "reads huge" (README's own caveat). `silences`, `hot_cues` A–H.
- **Not in the map:** mix loudness (absolute or LUFS), spectral brightness or centroid, spectral
  flux or novelty, any tension or arousal curve, riser or uplifter detection, cross-track
  comparable levels, and a per-track summary.
- `pawsa-too-cool-to-be-careless.yml`: 118 bars, sections groove 1–15, break 16–24, drop 25–45,
  break 46–48, drop 49–93, break 94–96, drop 97–115, outro; drops at 25 (+12.0 dB), 49 (+22.0),
  97 (+16.1) [read].

### 1.2 Critic views (`scripts/show_views.py`, `scripts/show_zoom.py`) [read]

- `music_level(bar)` is the maximum of the kick, bass and other digits. Vocals are shown apart.
- `light_level(section) = round(9 × (0.4·movers + 0.4·matrix + 0.2·hue))`. Movers: hold/sweep at
  `level`, pingpong/blink 0.5 flat, uv 0.3. Matrix: lit share per draw (solid 1, fill-up 0.6,
  rows 1/6, columns 1/8, centre-out 0.25, arrow-up 0.15, zigzag 1/48), ×0.5 with pingpong, ×0.6
  for the decay. Hue: pulse 0.5, bright 0.85. White, strobe and UV are accents, not level.
  `auto` reads `~`.
- `report` prints, in order: the night summary (minutes per look, colour per zone, aim, zone
  lit, centre dark, total dark, events), per-track strips (music digit over light digit per bar),
  section lines with voices, peaks (each map drop: dB, music, light before>at, accents, moment),
  hit checks (each arrival and moment: kick onset on the first step, light before>at, accents,
  voices of a dark bar before), budget, arrivals (draw and colour), advice, and "decided by the
  compiler".
- `zoom`: a moment at 1/16 step, with music lanes from the map and light lanes sampled from the
  compiler's own envelopes 2 ms into each step. This is a *measured* light signal: it could
  replace the table index (gap G2).

### 1.3 Measured on Hï Ibiza (Pulso) [repo]

Commands: `uv run scripts/nextrack_show.py report hi-ibiza-pulso`, and a read-only Python pass
over `lightshows/maps/*.yml` and the report's strips.

| fact | value |
|---|---|
| bars with music level 9 (all 15 maps) | 82 % (8 or 9: 88 %) |
| tracks with ≥ 95 % of bars at music 9 | Move 96 %, We Dance Again 97 %, Ma Tnsani 97 %, The Akan 95 % |
| night's light-level distribution | 0: 1 %, 1: 8 %, 2: 8 %, 3: 51 %, 4: 30 %, 5: 2 % |
| mean light level by owner energy | e6 ≈ 3.4, e7 ≈ 3.1, e8 ≈ 2.8, e9 = 2.7 (falling) |
| peak tracks' light level max | Pick Up 3, Can't Decide 3 (both e8) |
| peaks table (35 drops) | light at the drop: 3 in 30, 4 in 4, 5 in 1; same or lower than before in 17 |
| night summary | inline looks 29:02 of 44:09; movers azul-gelo 37:55 (86 %); aims centro-da-pista + cruzado 34:49 (79 %) |
| report size | ≈ 51 kB (≈ 13–15 k tokens); a zoom ≈ 2 kB; all 15 maps ≈ 338 kB (≈ 100 k tokens) |

The owner's light plan (`lightshows/sets/hi-ibiza-pulso.md`) states an arc in words: dark
first; blue = space, red = heart; the heart's pulse speeds up and turns red as BPM rises from
120 to 132; strobe only from TOO COOL on; five blackouts, three spirals, three backlights; the
arrival draw differs between consecutive tracks. The arc lives in prose and in budgets
(`from`, `max`, `moments`). No number in the views tracks "faster and redder as the night goes
on", even though rate and colour are exactly the dimensions the plan uses to express it.

### 1.4 The repo's own autoscript study [read: `docs/soundswitch/autoscript-analysis.md`]

24 tracks were sampled against per-second audio energy. Five looks cover 99 % of bars; first
drops land 4–7 bars late in 8 of 24 tracks; "builds do not build" (0 of 85 chase onsets are
preceded by acceleration or more lit fixtures); the centre is almost never dark; one strobe ramp
in the whole set; adjacent tracks' colours collide. The study already used *audio energy per
second* and *band energy normalised to the track's 90th percentile*: precedent for adding a mix
energy curve to the maps.

---

## 2. Craft: how human LDs and operators plan for energy and immersion

### 2.1 Contrast, darkness, build-up, drop

- **Near-darkness before the drop, then the drop.** "Use moments of near-darkness to build
  suspense"; "a single well-timed movement or blackout into a perfectly-synced drop" can do
  more than constant motion; keep a quiet intro static or dimmed, then a synchronised mover sweep
  "right as the bass drops" [read: Ticket Fairy, *Kinetic Festival Lighting Without Chaos*,
  2025/2026].
- **A distinct look per major drop.** Pre-program different looks, for example strobe and
  blinder on the first drop and a different movement on the second [read: Ticket Fairy].
- **Trigger on musical moments, not on every hit.** Avoid "randomly flashing lights on every
  drum beat" [read: Ticket Fairy].
- **Contrast is the core tool.** Robert Grunwald (Panorama Bar): "To play with brightness and
  darkness is the key for me… It can be total darkness in the right moment or just bright lights
  at the climax" [read: Electronic Groove interview].
- **Restraint.** Roland Greil: knowing "when to apply the brake instead of the throttle"; "no
  light without darkness": build in black space so lit elements stand out [read: Chauvet
  Professional, *5 Lessons in Light*]. Steve Lieberman: anything can be overused, "there must be
  balance" [snippet].
- **Build-ups.** Tension through a stutter (half-intensity pulses on alternate snares), then full
  power on the drop's first beat; a build scene that tightens movement and raises brightness over
  16 bars [snippet: vendor blogs, low authority]. Breakdowns: "slow-moving lights", moodier hues;
  builds: ramp intensity or tease; drops: a sharp accent [read: Ticket Fairy, *Timecode vs
  Busking*].
- **Strobe.** Short deliberate bursts; the rarer the effect, the more weight it carries; slower
  rates for tension, fast ones for impact [snippet: vendor blogs]. Save intense blinders for the
  most impactful beats and keep them short [read: Ticket Fairy].
- **Photosensitivity** [recalled]: broadcast guidance (UK Ofcom/Harding) treats flashing at about
  3 Hz and above as a seizure risk. A 1/16 strobe at 128 BPM is about 8.5 Hz. The repo's strobe
  budget (5 events, about 5 s for the night) is the right instinct; a rubric item should keep
  rolls short.

### 2.2 Pacing over a night: waves, saving the big looks

- "Build your show's intensity in waves" rather than running at maximum from the start; "ebb and
  flow"; "it's a marathon, not a sprint"; "save some tricks for the climaxes"; don't run every
  fixture at full continuously; follow intense sequences with calmer "reset cues" or
  "breathers" [read: Ticket Fairy].
- Club practice: "you just start with a single lamp in the corner and add more and more lights
  when it comes to a highlight situation." Long sets give "more chance to arrange the evening in
  different moods and take people on a journey". Judge the light over a longer span "than just in
  a 8 min track" [read: Grunwald].
- The repo's `docs/energy-arcs.md` already names the arc shapes (single peak, waves, slow burn,
  radio arc) and block functions (warmup 3→5, build 5→8, peak 8→10, plateau 7↔8, breakdown −2/−3,
  cooldown) [read]. The Hï Ibiza block is a *build*, 6→9 [read].
- DJs move energy one step at a time: Mixed In Key's guidance is to move by one energy level
  when possible [snippet: mixedinkey.com workflows].

### 2.3 Variety and coherence

- Keep the palette small: two colours are often enough, sometimes three, if related [snippet].
  Each fixture group has a role [snippet]. Hï Ibiza's plan already does this (blue = space, red =
  heart; roles per fixture) [read].
- Avoid "a mish-mash of clashing looks"; after many intense acts, a more subtle show stands out
  by contrast [read: Ticket Fairy].
- Club restraint at the other extreme: Horst's designers describe light as "the secondary layer,
  but it's essential in context with the music" [snippet]. A techno club (BAIA) avoided flashy
  fixtures so that darkness carries equal weight [snippet].

### 2.4 Busking versus timecode

- Timecode "shines for repeatable headliner shows" and for locking lasers, pyro and video; it
  leaves "little room for spontaneity". Busking suits B2B and improvised sets and is "only as good
  as the operator". The common hybrid is "timecode for core sequences and manual overrides for
  spontaneity" [read: Ticket Fairy, *Timecode vs Busking*].
- Grunwald plans the setup, then reacts: "you never know what the DJ is going to play… You need
  both skills" [read].
- **Relevance:** NEXTRACK is timecode (per-track scripts), but the mix points are live. The
  bridge design ("the room sees no cut at any bar SoundSwitch switches scripts") is the repo's
  answer to that [read: Pulso plan]. A rubric item: *the show must not depend on the exact mix
  bar*.

### 2.5 Small room versus festival

- Festival guidance warns against total blackouts (venues often prohibit them; exits must stay
  visible) [read: Ticket Fairy]. In a private small room this is a lesser concern, but total dark
  keeps a budget (`total-dark` rule).
- In a small room the beams in haze *are* the show (Pulso's "beam grammar") [read]. With two
  movers, the figure they draw matters more than brightness. A drop can be immersive through a
  change of figure (aim) and rate, not only through more light. This is one more reason the
  light index must count rate and aim changes.

### 2.6 What auto-lighting products map (phrase or energy → light)

- **SoundSwitch.** Autoscript detects phrases: Intro, Main 1 (higher energy, chorus-like),
  Main 2 (verse), Middle, Bridge (bridges and breakdowns), Outro. It builds a show per phrase and
  detects build-ups, breakdowns and drops [snippet: inMusic support, via search]. 2.8 adds phrase
  editing and re-autoscripting with the same preset [read: *What's new in SoundSwitch 2.8*]. The
  repo's study shows what it actually does on this rig (section 1.4).
- **rekordbox lighting.** Phrase analysis is required to sync. Mood HIGH/MID/LOW is "based on
  audio information including tempo, rhythm, kick drum and sound density". Scenes are mapped to
  phrases by Macro; Banks (Cool, Natural, Hot, Subtle, Warm, Vivid, Club 1, Club 2) are scene
  variations [read: rekordbox FAQ lighting-6]. Phrase types Intro/Up/Down/Chorus/Bridge/Verse/
  Outro, with Up = build and Chorus = drop [snippet].
- **MaestroDMX** (real-time, no pre-analysis). "The Activity Level is a measure of how 'exciting'
  the music is." Snapshots are constrained to an activity range and laid out from Quiet to Peak.
  Activation categories are Silence, Kick Drum and No Kick Drum (breakdowns). Several snapshots in
  one category cycle "when MaestroDMX senses a substantial change in the music" [read: FX
  Palettes]. Pattern parameters: Excitement (faster and more abrupt versus smoother) and Mover
  Speed are both "modulated by the energy of the music"; Background (a floor that keeps lights
  from going fully dark; lower means more contrast); "Allow Music-Based Blackouts"; "Blackout On
  Silence" [read: Pattern Parameters].
  - **Takeaway.** The commercial "energy" model has three parts: a continuous *activity level*
    (excitement), a binary *kick present / absent* state (groove versus breakdown) and *change
    detection* (when to switch look). Energy modulates *speed and abruptness*, not only
    brightness. NEXTRACK's maps already have the kick/no-kick state and the change points. What
    is missing is a continuous activity curve, and a light index that counts speed.

---

## 3. Research on music-driven lighting, and close analogs

### 3.1 Lighting generation

- **Skip-BART** (Zhao et al., arXiv 2506.01482, ICLR 2026 poster) [read]. Input: OpenL3 audio
  embeddings over 1 s windows with a 0.1 s hop. Output per frame: a hue token (180) and a value
  (brightness) token (256); saturation fixed. Data: RPMC-L2, 699 clips from 35 live
  rock/punk/metal shows, with labels extracted from video (hue = mode of the hue histogram, value
  = weighted mean). Metrics: RMSE/MAE (circular for hue) and corr(|Δ|), the correlation of
  frame-to-frame change magnitudes. Human study: 38 raters, six 7-point dimensions; ground truth
  4.5, Skip-BART 4.3 (n.s. versus ground truth), rule-based 2.7. Self-reported limits: "excess
  local fluctuation and weaker long-term rhythmic stability". Prior rule-based work maps coarse
  categories (style, theme, emotion, chords) to fixed patterns, judged "coarse-grained".
  - **Takeaway.** corr(|Δ|) is a cheap, useful idea: compare *when and how much* the light changes
    with *when and how much* the music changes, not absolute levels. It becomes G3 below.
- **Cadence** (NeurIPS 2026, concert video with music-responsive lighting) [read: abstract
  page]. Its "music-relative aligner" contrasts the response to music with the response to
  silence. It decomposes the problem into *what* changes, *when* and *where*, and reports
  "lighting activity" as an evaluation axis (+44.2 % toward real recordings).
  - **Takeaway.** Activity, meaning how much the light moves, is something researchers measure
    explicitly, separately from brightness.
- **Glow with the Flow** (arXiv 2602.08838, ambient lightscapes for music videos) [read].
  Features: median RMS over short windows, normalised per song and clustered into a 1–5
  "temperature" per functional segment (from a joint beat/structure model); kicks and snares
  from the drum stem as "primary rhythmic anchors"; colour palettes from video. Mapping: cold
  segments (1–2) are ambient, slow and soft; 3–4 add spatial modulation; 5 uses all layers.
  Evaluation: blind paired 10 s clips (AI versus a lighting artist), 32 raters, three axes
  (emotional, rhythmic, chromatic congruence); no significant difference after correction.
  Qualitative comments called the AI designs "repetitive", "predictable", "too explicit".
  Practitioner principles: one global palette per song, "audio events for *when*, sustained
  layers for ambience", "scale intensity across sections".
  - **Takeaway.** This is close to NEXTRACK's design (structure plus energy plus stems). Its
    failure mode is literalness and repetition: criterion M.

### 3.2 Dance and choreography generation (analog of a "show from music")

- **EDGE** (Tseng et al., arXiv 2211.10658) uses Jukebox embeddings and a diffusion model, and is
  evaluated with a user study plus a new physical-plausibility metric [read: abstract]. EDGE
  argues that FID on AIST++ is unreliable and that the Beat Alignment Score rests on a flawed
  premise, since dance follows the beat loosely and half- or double-time is valid [snippet:
  search summary of the paper and of later papers]. BAS measures the mean distance from each
  music beat to the nearest motion beat. Diversity is the distance between generations for
  different music [snippet].
- **Lodge** (arXiv 2403.10518), for long dances: a global stage produces "characteristic dance
  primitives" and a local stage fills detail, "striking a balance between global choreographic
  patterns and local motion quality" [read: abstract].
  - **Takeaway for the team design.** Global then local is the director-then-track-agents split.
    Long-sequence work needs an explicit global plan, otherwise generation is locally fine and
    globally monotonous.
- **Metric lesson.** Every subfield relies on human judgment because automatic metrics miss
  artistic quality [read/snippet as above]. For NEXTRACK, the deterministic measures should
  catch gross failures (no contrast at a top drop, a ten-minute static stretch, light falling
  while energy rises), and the judgment stays with a critic agent using a rubric and, at the end,
  the owner in the room.

### 3.3 Music visualisation [recalled]

Classic visualisers map loudness to size or brightness, spectral centroid to colour or
brightness, onsets to flashes and tempo to motion speed. Surveys (for example Lima et al.,
*A Survey of Music Visualization Techniques*, ACM CSUR 2021) note the same literal-mapping
problem. Not opened.

---

## 4. MIR analyses for "follows the energy" and "immersive drops"

### 4.1 What the perception and EDM research says matters

- **The break routine.** Break routines reduce "dynamics, texture, and structure" to a few
  elements (breakdown), rebuild layer by layer (build-up) and reach the peak with "the
  reintroduction of the groove in its layered entirety" (drop). "EDM tracks normally contain two
  or more break routines… of which the latter is intended to be experienced as the most intense."
  The four drop tracks shared four features: a U-shaped amplitude profile; large changes in
  frequency register, especially at the build→drop transition; sudden removal and gradual
  reintroduction of bass and bass drum; risers ascending to the drop, then descending to mark it.
  Features analysed: amplitude, RMS, spectral flux, spectrum, brightness, roughness (MIR toolbox).
  Rhythm features showed no relationship with skin conductance (seated listeners) [read: Solberg
  & Dibben 2019, *Music Perception* 36(4), full text].
- **Drops drive peak responses.** Drop sections gave significantly higher skin-conductance
  responses than other parts of the break routine (24 participants) [read: same]. Dancers show "a
  sudden decrease and increase in the general quantity of motion" through the break routine and
  "an improved level of interpersonal synchronization after the drop" (29 participants, motion
  capture) [read: Jensenius's blog summary of Solberg & Jensenius].
- **Production techniques of tension.** Uplifters, the "drum roll effect", large frequency
  changes, removal and reintroduction of bass and bass drum, a contrasting breakdown [snippet:
  Solberg 2014, *Dancecult*].
- **The EDM structure vocabulary.** Labels: intro, buildup, breakdown, drop, cooldown, bridge,
  outro, ambient-intro/outro. The most common segment is "30 seconds or 16 measures"; changes
  "tend to occur at multiples of four or eight measures"; drops can last 80–90 measures; flow
  intro–buildup–drop–breakdown–drop–cooldown–outro; "the drop possesses the highest energy";
  "later drops often exceed earlier ones" [read: Raveform, TISMIR 2026, text via
  transactions.ismir.net].
- **The drop in MIR.** "A drop occurs after a build, a building up of tension, and is followed by
  the re-introduction of the full bassline"; the ground truth is "the point where the buildup ends
  and the bassline is re-introduced". The method was two-stage: segment boundaries from chroma
  self-similarity, then an SVM on MFCC, spectrogram statistics and rhythm features. Data: 100
  tracks, 190 drops. Average F1 0.71 at a 15 s tolerance, above 0.6 at 3 s [read: Yadati et al.,
  ISMIR 2014, full text]. A later open-source detector reports F1 0.95 with 29 features (RMS
  rise, future energy, grid alignment on 4/8/16/32 bars, pulse clarity, transient dominance, bass
  ratio, bass continuity); this is self-reported and the split is unclear [read: GitHub
  felixmeyer6/drop-detector].
  - **Takeaway.** NEXTRACK's rule-based drop (full low end after ≥ 2 bars well below) matches the
    definition and is bar-exact on the script's grid, which beats the published learned detectors
    at their tolerance. What is missing is *salience*: which drops are the big ones. The current
    `db` is relative to the two bars before, so it is inflated after silence (README caveat).
- **Tension (Farbood 2012).** Tension is integrated over time from the *slopes* of features in a
  moving attentional window, weighted, and amplified when the trend continues the preceding
  memory window's direction. Formula: `s'(t) = Σ_f w_f · β · s_f(t)`, with `s_f(t)` the slope of
  the best linear fit of feature f over [t, t+d], β = 1 if the sign of s(t−d) ≠ sign of s(t),
  else β = 5 (fitted), `Σ w_f = 1`, evaluated every 0.25 s and integrated. Weights: dynamics and
  melodic pitch height 3, tempo and onset frequency 2, harmony and bass/inner pitch height 1
  [read: Farbood 2012, *Music Perception* 29(4), full text]. A 2016 audiovisual follow-up
  weighted loudness first, then spectral centroid, roughness, onset frequency [snippet].
  - **Takeaway.** This is a formula-level tension model built from cheap features. It fits EDM
    builds (rising loudness, rising centroid from risers, rising onset density from snare rolls)
    but is not validated on EDM, so treat it as advice-level only.
- **Arousal and valence.** On DEAM (MediaEval Emotion in Music), "very good performance on
  arousal and completely unsatisfactory performance on valence". Best dynamic arousal ρ ≈ 0.66
  (BLSTM-RNN) against a baseline of 0.37; best valence ρ ≈ 0.15. "Arousal can be successfully
  modeled just with simple timbral features (spectral valley and spectral flatness)" [read: PMC
  5345802, Aljanaki et al. 2017]. Schubert 2004: R² 0.78 for arousal against 0.22 for valence
  from loudness, tempo, contour, texture and centroid [snippet].
  - **Takeaway.** "Energy" in the owner's sense is close to arousal, and arousal is mostly
    loudness plus timbre (brightness, flatness) plus onset rate. A learned arousal model adds
    little over those features and brings genre shift (DEAM is Western pop excerpts). Valence is
    not reliably computable; leave colour mood to the director's story.

### 4.2 Set-level energy flow

- DJs choose tracks similar in timbre and order them to minimise timbral jumps; the original order
  beats a shuffle in all factors but key. "Loudness can easily be (and is almost always)
  controlled by the DJ… DJ sets will be relatively homogeneous"; "DJs appear to vary volume
  slightly over the course of a set" [read: Kell & Tzanetakis, ISMIR 2013, full text].
- Large-scale DJ-mix statistics (1,557 mixes, 20,765 transitions): cue points, transition lengths,
  musical changes [read: abstract only, arXiv 2008.10267]. Raveform: DJ-mix-specific structure
  data (4,902 mixes, 1,423 annotated tracks) and models [read].
- Commercial energy scores: Mixed In Key 1–10 (method unpublished; reported to listen for hi-hats
  and white-noise risers; "not necessarily linked to tempo") [snippet]. Spotify `energy` is a
  "perceptual measure of intensity" from dynamic range, perceived loudness, timbre, onset rate and
  general entropy [snippet: secondary pages quoting the Web API docs]. Mixgraph claims a 0–100
  energy from loudness, "spectral drive" and percussive weight [snippet].
- **Takeaway.** No mature, published set-energy measure exists. The owner's `energy` labels are
  the ground truth for S. Measured features (BPM played, onset density, brightness, texture
  density, integrated LUFS) can check the labels for consistency, but should not replace them.

### 4.3 Maturity, cost and fragility

| analysis | serves | maturity | cost here | fragility / notes |
|---|---|---|---|---|
| beat/downbeat grid | all | mature | free (SoundSwitch script anchors) | already solved in the repo |
| source separation (Demucs htdemucs) | T, D | mature | minutes per track on CPU [recalled]; already done | bleed handled (`is_bleed`) |
| per-voice levels per bar/step | T, D | done | free (in map) | **saturated**: per-voice self-normalisation |
| mix short-term loudness, LUFS (BS.1770 / EBU R128, 400 ms momentary, 3 s short-term, integrated, LRA) | T, S, D | mature, standardised [read: Essentia LoudnessEBUR128] | cheap (numpy or pyloudnorm/essentia) | homogeneous across a set (Kell & Tzanetakis): use it *within* tracks and for drop contrast, not alone for set arc |
| spectral centroid / high-band ratio (brightness) | T, D (risers), S | mature | cheap | perceptual mapping approximate; mastering differs per track |
| spectral flux / flatness | D, T (arousal proxy) | mature | cheap | flatness tracks noise risers and white-noise sweeps |
| onset density per bar | T, D, S | mature | **free from map** (`onsets.perc`, `onsets.kick`) | perc onsets include the kick click |
| texture density (active voices per bar) | T, S | simple | **free from map** | thresholds are a choice (for example ≥ 6) |
| novelty / boundaries (Foote checkerboard on SSM) | M (light should mark boundaries) | mature (2000) [read: FMP, intro only] | cheap | kernel size sets the scale; EDM boundaries also come from the kick/bass rule |
| functional labels (allin1: intro/verse/chorus/break/bridge/inst/solo/outro, Demucs-based, MIT, Harmonix-trained) | T | good on pop [read: GitHub] | moderate (GPU helps; reports 10 songs/33 min in 73 s on an RTX 4090) | pop label set; EDM labels (Raveform 2026) are newer; use only as a cross-check |
| drop detection | D | rule in repo matches the definition; learned F1 0.71 at 15 s (2014) | done | need **salience ranking**, not detection |
| build/riser detection | D | moderate | cheap features (centroid + flatness slope, perc density slope) | fragile: filtered builds and tech-house bass filtering |
| tension curve (Farbood slopes) | D, T | validated on tonal music, not EDM | cheap, derived | advice only |
| arousal (learned) | T, S | moderate (ρ ≈ 0.66) | moderate | genre shift; little gain over loudness + timbre |
| valence (learned) | colour mood | poor (ρ ≈ 0.15) | moderate | do not use |
| set energy (commercial) | S | proprietary | n/a | owner labels instead |

---

## 5. Precompute versus on-demand: the arguments

From Anthropic's engineering guidance:

- Find "the smallest possible set of high-signal tokens that maximize the likelihood of some
  desired outcome"; context is "a finite resource with diminishing marginal returns" [read:
  *Effective context engineering for AI agents*].
- Just-in-time retrieval keeps lightweight references (paths, stored queries) and loads them at
  runtime, but "runtime exploration is slower than retrieving pre-computed data". "The most
  effective agents might employ a hybrid strategy, retrieving some data up front for speed".
  Claude Code itself is hybrid (CLAUDE.md up front, glob/grep just in time). Hybrid suits "less
  dynamic content" [read: same].
- Subagents return "a condensed, distilled summary of its work (often 1,000-2,000 tokens)"
  [read: same].
- Tools should return "only high signal information"; offer a `response_format`
  (concise/detailed; concise used about a third of the tokens in their example); use pagination,
  range selection, filtering and truncation; make errors actionable; consolidate multi-step
  workflows into one tool; design tools by evaluation [read: *Writing effective tools for
  agents*].
- Multi-agent systems use "about 15× more tokens than chats". Domains with many dependencies
  between agents are a poor fit. Subagents should "store their work in external systems, then
  pass lightweight references back". "End-state evaluation rather than turn-by-turn analysis".
  The LLM judge gives 0.0–1.0 scores plus pass/fail against a rubric [read: *How we built our
  multi-agent research system*].
- Evaluator-optimizer is "particularly effective when we have clear evaluation criteria, and when
  iterative refinement provides measurable value" [read: *Building effective agents*].

Applied to NEXTRACK:

| criterion | audio analyses (music facts) | light-versus-music views |
|---|---|---|
| inputs | audio on the owner's drive (never in the repo or CI), stems, `uv sync --group analysis` (heavy) | the show (changes every iteration) plus maps |
| cost | minutes per track (Demucs); once per audio hash | milliseconds; pure Python over YAML |
| determinism | must be identical for every agent and every run, or agents argue over different numbers | deterministic given show + maps |
| reuse | every agent, every iteration, every future show of the same track | per iteration |
| auditability | committed YAML, stale by hash/GUID (maps already do this) | formulas in docstrings (the critic already does this) |
| context size | the raw map is about 19 kB per track (all 15 ≈ 100 k tokens): too big to read whole | filtered views of 2–15 k tokens |
| verdict | **precompute** | **on demand (tool)** |

---

## 6. Gaps, each with a proposed measure

The conventions follow the repo: digits 0–9, bars on the script grid, *legs* for states,
*sounding windows* for events, and every formula stated in a docstring. "p5/p95" are
percentiles; `clip01(x) = min(1, max(0, x))`; `n̂ = clip01((x − p5)/(p95 − p5))`, normalised
over the scope named (track or night).

### G1. Music energy per bar does not saturate and is comparable across tracks (T, S, D)

Today `music_level = max(kick, bass, other)` is 9 in 82 % of bars.

Proposal (map v2, precomputed): add a `mix` block per bar.

- `L(b)`: mean short-term loudness (BS.1770 K-weighted, 3 s window, 100 ms hop) over bar b, in
  LUFS; stored as `loudness` digits on an **absolute** scale: `digit = clip(9 − floor((−6 − L)/3),
  0, 9)`, so 9 means L ≥ −6 LUFS and each digit is 3 LU. This keeps the repo's 3 dB/digit
  convention but with a shared reference across tracks. The track summary also stores integrated
  LUFS and LRA.
- `C(b)`: brightness, the ratio of mix energy above 4 kHz to total (or the spectral centroid), as
  digits on an absolute scale.
- `D(b)`: onset density, the number of steps in the bar with `onsets.perc` or `onsets.kick` ≥ 3,
  divided by 16 (**derivable from the current map, no audio needed**).
- `V(b)`: texture, the number of voices with a bar digit ≥ 6 (0–5) (**from the current map**).
- Track energy, for within-track shape (T):
  `E_music(b) = round(9 × (0.4·L̂ + 0.2·Ĉ + 0.2·D̂ + 0.2·V̂))`, normalised over the track's bars.
  The weights follow the arousal and tension literature: loudness first, then timbre and onset
  rate.
- Night energy, for the set (S): the same formula normalised over all the night's bars, so an e6
  groove and an e9 drop differ.
- An interim version with no new audio: `E0_music(b) = round(9 × (0.5·D̂ + 0.5·V̂))`.

### G2. A light measure that sees rate, strobe and white, computed from the compiler (D, T, S)

Today the table index scores a 1/16 draw like a 1-bar draw and puts pingpong/blink at a flat
0.5. Proposal: use the zoom's sampled envelopes (the compiler's own generators, one sample per
1/16 step) for each fixture group f (mover NE, mover SE, Vorlane NW, Vorlane SW, lustre, white
strip, strobe):

- **Brightness** `B_f(b) = mean over steps of level_f(s) × coverage_f(s)`, where coverage is the
  lit share of a Vorlane's colour cells, and 1 for single-lamp fixtures.
- **Activity** `A_f(b) = (number of dark→lit rises in bar b) / 16`: flashes per step, with a
  strobe pulse counting as a rise.
- **Change events** `X(b)`: the number of dimensions whose value changes at bar b (mover move,
  mover rate, mover colour, aim, matrix draw, matrix rate, matrix colour, hue state, hue colour).
- `E_light(b) = round(9 × (0.5·B̂ + 0.5·Â))`, with `B = Σ_f w_f B_f` and `A = Σ_f w_f A_f`;
  starting weights movers 0.35 (both), Vorlanes 0.35 (both), lustre 0.15, white 0.10, strobe 0.05
  (a design call, stated in the docstring like the current 0.4/0.4/0.2). Normalise over the
  night.
- Print both brightness and activity strips, not only the blend: a drop that is dimmer but much
  faster is a legitimate design, and the critic should see it.

### G3. "Follows the track": agreement, direction and lag (T)

For each track, over the leg's bars where the light is known:

- **Shape** `ρ_T = Spearman(E_music(b), E_light(b))`.
- **Change correlation (Skip-BART's corr(|Δ|))** `κ_T = Pearson(|ΔE_music(b)|, |ΔE_light(b)|)`
  with Δ over 1 bar: does light move when the music moves?
- **Direction at boundaries.** For each map section boundary k, take
  `Δm_k = mean E_music[k..k+3] − mean E_music[k−4..k−1]` and the same `Δl_k` for light.
  Agreement is the share of boundaries with `|Δm_k| ≥ 2` where `sign(Δl_k) = sign(Δm_k)` and
  `|Δl_k| ≥ 1`. List the **missed boundaries** (`|Δm| ≥ 2`, `|Δl| < 1`). List the **unmotivated
  changes** (`|Δl| ≥ 3`, `|Δm| < 1`) for information only; they can be deliberate.
- **Lag** `λ_T = argmax over lag ∈ [−8, 8] bars of xcorr(E_music, E_light)`; flag `|λ| > 1`. The
  autoscript lands drops 4–7 bars late, which is the failure this catches.
- **Residual view.** The 5 sections with the largest `|E_light − E_music|` (rescaled): "where the
  light disagrees most with the music", for the critic to judge.

### G4. Drop salience versus light response (D)

Music side, precomputed per map drop d:

- `ΔL = mean L[d..d+3] − mean L[d−8..d−1]` in LU (robust to silence, because it uses 8 bars and
  absolute loudness, not two bars of the low end).
- `bass_return = (bass digit at d − min bass over d−8..d−1)/9`; `ΔD` the same for onset density.
- `main = 1` if d is the track's largest-ΔL drop **or** its last drop (later drops are meant to be
  bigger), else 0.
- `S_d = 0.4·ΔL̂ + 0.3·bass_return + 0.2·ΔD̂ + 0.1·main`, normalised over the night; rank all
  sounding drops by S. These are the night's *peaks*, ranked.

Light side, on demand:

- **Contrast** `C_d = mean E_light[d..d+3] − mean E_light[d−2..d−1]` (hit against the dip).
- **Change** `X_d` = the number of dimensions that change at d (0–9, see G2).
- **Freshness** `F_d` = the share of the drop section's dimension values not seen in the previous
  10 minutes of the night (rewards saving looks).
- `R_d = 0.5·Ĉ_d + 0.25·X_d/9 + 0.25·F_d`.

Checks:

- Night: `Spearman(S, R) ≥ 0.5` over drops with S above the night median (advice).
- Each top-quartile drop has `C_d > 0` and `X_d ≥ 2`. Today 30 of 35 drops read 3 at the drop,
  and 17 do not rise.
- **Within a track**, the response to the `main` drop is at least that of earlier drops.
- **Sync**: the share of light rises in bars d..d+3 that fall within ±1 step of a kick or perc
  onset *or* on the 1/8 grid. Half- and double-time are accepted, which answers EDGE's critique
  of beat-alignment scores.

### G5. Builds build (D, T)

- **Tension** per bar from G1 features, Farbood style: slopes `s_f` over a 2-bar window for
  f ∈ {L, C, D}, weights 3/2/2 normalised, β = 5 when the slope keeps the previous window's sign,
  integrated over the break and build.
- **Light** over each build of ≥ 4 bars (map `build` or the last 4–16 bars of a `break` before a
  drop): the slope of activity `A` and of coverage. Check `sign(slope_light) = sign(slope_T)`.
  Also "subtract before adding": `E_light` at the build's start ≤ the median of the preceding
  groove or drop (the repo's own "builds do not build" finding).
- **Dip before the drop**: `E_light(d−1) ≤ E_light` mean over `d−9..d−2`, *or* a monotone ramp
  ending at d. Either is valid; "flat into the drop" is the failure.

### G6. Monotony and its opposite, chaos (M)

Signature per bar: `sig(b)` = (mover move, mover rate, mover colour, aims, matrix draw, matrix
rate, matrix colour, hue state, hue colour).

- **Longest static run**: the longest run of identical `sig` in seconds; list the top 5 with their
  music. Advice threshold set by the director per block (for example ≤ 120 s in a build or peak,
  ≤ 180 s in a warmup).
- **Windowed variety**: in a sliding 4-minute window, normalised Shannon entropy of time shares
  of `sig`: `H_w = −Σ p_i log2 p_i / log2(k)`, with k the number of distinct signatures in the
  window. Print it as a strip per minute.
- **Night dominance**: the largest share of one value per dimension (today movers azul-gelo 86 %,
  the top two aims 79 %). This is advice only against dimensions the show does *not* declare as a
  signature: coherence is legitimate, and the plan says blue is the space.
- **Track similarity**: cosine similarity of consecutive tracks' time-share vectors over all
  dimension values; flag > 0.85, excluding bridges.
- **Drop-template predictability**: for each drop, the tuple (light pattern of the 4 bars before,
  of the drop's first section). Report `distinct templates / drops`; advice ≥ 0.5 (the "too
  explicit / predictable" failure from Glow with the Flow).
- **Chaos guard**: the share of light changes on phrase lines, meaning map boundaries or bars
  ≡ 1 mod 4 from the section start (EDM changes sit on 4/8/16-bar lines). Advice ≥ 0.9. Also
  flag more than one change per 4 bars outside builds.
- **Repetition across shows** (later): the same measures against the owner's previous shows, so
  each night does not repeat the last.

### G7. Set arc: target versus light curve (S)

- **Target** (precomputed per set): the owner's `energy` per track from the pool, the block's
  `energy: [a, b]` and `function`, the played BPM ramp, and the arc shape from
  `docs/energy-arcs.md`. Interpolate a target per minute on the set clock (the clock exists).
- **Light per track** (on demand): `mean E_light`, `p90 E_light`, mean activity, warm-colour share
  (palette hue within ±30° of red), rare resources used (strobe, white, total dark, spiral).
- **Measures**:
  - `ρ_S = Spearman(e_track, mean E_light)` and `ρ_S90 = Spearman(e_track, p90 E_light)` over
    tracks. Today, with the table index, the trend is negative (section 1.3).
  - **Headroom** `H = max p90 E_light before the first track with e ≥ peak threshold / night max
    p90 E_light`; advice H ≤ 0.8 ("save the big looks").
  - **Staircase**: a new running maximum of `p90 E_light` or of activity appears only in a track
    whose `energy` ≥ the running maximum energy.
  - **Step proportionality**: between consecutive tracks, flag a light jump (`|Δ mean E_light| ≥
    2`) where `Δe = 0`, and flat light (`< 1`) where `Δe ≥ 1`. This catches a turning point such
    as Move → TOO COOL (e7 → e8, "a virada").
  - **Waves**: after each top-quartile drop, at least one section within N minutes with
    `E_light ≤` night median ("breathers").
- **Label check** (music only): rank tracks by measured night-normalised `E_music` (mean of the
  leg) and by BPM, and list tracks whose rank differs from the owner's `energy` rank by ≥ 3
  positions. This is a question for the owner, not a fix.

### G8. Smaller gaps

- **Vocals**: the map has vocal phrases and register. A "beam that breathes with the voice"
  (Pulso's wish list) needs no new analysis, only a view that shows vocal phrases against mover
  level.
- **Kick-absent state**: MaestroDMX's Kick / No-Kick category is the cheapest "groove versus
  breakdown" signal; the map has it (`kick` digits). A view could print a kick-presence lane
  next to the hue (heart) lane, since Pulso ties the heart to the kick.
- **Drop `db` caveat**: replace or complement it with `ΔL` from G4 in the peaks table.

---

## 7. Rules of thumb → rule, advice or rubric item

| # | rule of thumb (source) | where it goes | measure |
|---|---|---|---|
| 1 | Near-darkness or a dip before a big payoff; then hit on the downbeat (Ticket Fairy; Grunwald) | **advice** `drop-contrast` on top-quartile drops | G4 `C_d > 0`, G5 dip-or-ramp |
| 2 | A distinct look per major drop (Ticket Fairy) | **rule** extension of `arrivals.draw_differs` to top-N drops: no two consecutive major drops share (draw, matrix colour, mover move) | G4 X_d, signature |
| 3 | Save the tricks for the climaxes (Ticket Fairy; Greil "brake pedal") | **advice** `headroom`, plus **rule** budget `from` (exists) | G7 H ≤ 0.8; first use of strobe/white/solid in a top-quartile drop |
| 4 | Intensity in waves; breathers after intense stretches (Ticket Fairy) | **advice** `breathers` | G7 waves |
| 5 | Builds grow in rate and density, starting subtracted (repo study; Solberg; Ticket Fairy) | **advice** `build-grows` | G5 |
| 6 | Changes on phrase lines (Raveform: 4/8/16 bars) | **advice** `phrase-aligned` | G6 chaos guard |
| 7 | Don't flash every hit; "too explicit" reads as cheap (Ticket Fairy; Glow with the Flow) | **rubric** plus advice on accent density | accents per minute; G6 template predictability |
| 8 | The later or main drop of a track gets the bigger answer (Solberg & Dibben; Raveform) | **advice** `main-drop` | G4 within-track check |
| 9 | Start minimal and add as the night grows (Grunwald) | **advice** `coverage-grows` | lit coverage per block increases with block energy |
| 10 | Move one energy step at a time between tracks (MIK) | **advice** `step-proportional` | G7 |
| 11 | Small palette, roles per fixture group (vendor guides; Pulso plan) | **rubric** plus night dominance (informational) | G6 dominance against declared signature dimensions |
| 12 | Breakdowns: slower movement, moodier colour (Ticket Fairy) | **rubric** | activity in breaks < neighbouring drops |
| 13 | Strobe in short bursts, not every drop; photosensitivity (vendor; Ofcom [recalled]) | **rule** budget (exists) plus **advice** max roll length (for example ≤ 2 bars) | strobe seconds; roll bars |
| 14 | Judge over the night, not one track (Grunwald) | **rubric** framing for the critic | windowed views |
| 15 | Timecode needs to survive live mixing (Ticket Fairy hybrid; Pulso bridge) | **rule** `bridges` (exists) | — |
| 16 | Light follows the track's energy without lag (MaestroDMX activity; repo study: late drops) | **advice** `follows-track` | G3 ρ_T, λ_T |
| 17 | Light follows the set arc (energy-arcs.md) | **advice** `follows-set` | G7 ρ_S |

**Critic rubric** (for an LLM judge, end-state, 0–1 score plus pass/fail per item, following
Anthropic's research-system pattern):

1. **Arc.** Does the light's per-track curve rise and fall with the declared set energy? Are the
   biggest looks saved for the peak? (G7)
2. **Track.** Within each track, does the light move when the music moves, in the same
   direction and on time? (G3)
3. **Drops.** Do the night's top drops each land with contrast, change and freshness, and the
   main drop of each track with the biggest answer? (G4, G5)
4. **Variety.** No long static stretches, no repeated drop template, consecutive tracks
   distinguishable; but no chaos (changes on phrase lines). (G6)
5. **Coherence.** Palette and fixture roles hold the story the director declared; departures are
   deliberate and named as moments.
6. **Restraint.** Rare resources are rare and where the budget says; darkness is used as a
   canvas. (budget rules, total dark)
7. **Facts and judgment kept apart.** Every claim in a critique cites a view line. Numbers are
   evidence, not a verdict; the critic's final call is judgment.

---

## 8. Precompute versus on-demand: recommendation

**Precompute every music fact; compute every light-versus-music view on demand from those facts
and the current show; never let an agent run audio analysis ad hoc.**

1. **Tier 0: per-track music facts, precomputed and committed** (`nextrack_map.py analyze` on
   the owner's machine, map v2, stale by audio hash, script GUID and tempo anchors, as today).
   Add a `mix` block per bar (absolute loudness, brightness and flux digits; derived onset density,
   texture and tension), drop salience fields (`ΔL`, `bass_return`, `main`), and a short track
   summary (integrated LUFS, LRA, mean brightness, mean density, BPM).
   - **Why precompute:** the audio is not in the repo or CI; the dependencies are heavy and
     optional; every agent must see the same numbers; the owner can audit committed YAML; the
     cost is paid once per audio file instead of once per agent per iteration (multi-agent ≈ 15×
     chat tokens).
   - **Add analyses like gestures:** code, tests, a map version bump, then re-analyse all tracks.
     An exploratory analysis can be prototyped by an "analyst" agent on the owner's machine, but
     it lands as a precomputed field before any show depends on it.
2. **Tier 1: a per-set music brief, generated deterministically** (a new command, small, about
   2–4 k tokens). It holds the clock, each track's owner energy plus measured summary, the
   night's drops ranked by salience, the target energy per minute, the block function and arc,
   and the bridges and arrivals. The director reads it whole, up front: the "hybrid strategy" of
   loading compact, slowly changing context like CLAUDE.md. It is generated, never hand-edited
   (like maps and choreographies).
3. **Tier 2: on-demand critic tools** (deterministic, cheap, depend on the current show): today's
   `report` and `zoom` plus G2–G7 (`agree`, `drops`, `builds`, `variety`, `arc`). Each takes
   filters (`--track`, `--window`, `--section peaks`) and a `--format concise|detailed`, per
   Anthropic's tool guidance. A track agent should get its own track's 2–3 k-token slice, not the
   51 kB report. Formulas stay in docstrings, as the critic spec already requires, so a surprising
   number is "a question about the formula" first.
4. **Agents exchange files, not transcripts.** Subagents write show edits and critique notes to
   files and return 1–2 k-token summaries with references (Anthropic's artifact pattern). Raw maps
   stay out of agent context: about 19 kB per track, and step strings are unreadable at scale.
   The views are the interface.
5. **Gate versus judgment.** Turn only the robust checks into rules (budgets, bridges, the
   distinct-drop rule). Keep agreement, freshness, variety and arc as advice plus rubric. The
   research shows automatic metrics correlate poorly with perceived quality, so the critic agent
   judges and the owner's room test is the final eval.

---

## Sources

Lighting practice and products:

- Ticket Fairy, *Kinetic Festival Lighting Without Chaos: Movement Cues for Drops* (2025, upd.
  2026), <https://www.ticketfairy.com/blog/kinetic-festival-lighting-without-chaos-movement-cues-for-drops> [read]
- Ticket Fairy, *Lighting for BPM festivals: timecode vs busking*, <https://www.ticketfairy.com/blog/lighting-for-bpm-festivals-timecode-vs-busking> [read]
- Robert Grunwald (Panorama Bar) interview, Electronic Groove, <https://electronicgroove.com/?p=5496> [read]
- Roland Greil, *5 Lessons in Light*, Chauvet Professional, <https://www.chauvetprofessional.com/news/roland-greil-5-lessons-in-light> [read]
- Steve Lieberman interviews: <https://magneticmag.com/2019/11/in-conversation-steve-lieberman-ceo-sj-lighting/>, <https://www.vice.com/en/article/steve-lieberman-ultra-music-festival-lighting-interview> [snippet]
- Horst, *No Light Matter*, <https://www.horstartsandmusic.com/editorial/no-light-matter-inside-horsts-creative-laboratory> [snippet; 404 when fetched]
- Hï Ibiza production (Robe / LSi), <https://www.lsionline.com/high-scream-hits-hi-in-ibiza-with-robe> [snippet]
- SoundSwitch 2.8, <https://support.inmusicstore.com/en/support/solutions/articles/69000843903-what-s-new-in-soundswitch-2-8> [read]; phrase types <https://inmusicsupport.freshdesk.com/en/support/solutions/articles/69000844233> [snippet]
- rekordbox lighting FAQ, <https://rekordbox.com/en/support/faq/lighting-6/> [read]
- MaestroDMX FX Palettes, <https://maestrodmx.freshdesk.com/support/solutions/articles/153000225567-custom-control-with-fx-palettes> [read]; Pattern Parameters, <https://maestrodmx.freshdesk.com/support/solutions/articles/153000070521-maestro-pattern-parameters> [read]
- Mixed In Key energy level, <https://mixedinkey.com/workflows/use-energy-level-detection/> [snippet]
- Vendor blogs on strobe, palette and busking (Betopper, Uking): search results only [snippet, low authority]

Lighting generation and analogs:

- Zhao et al., *Automatic Stage Lighting Control: Is it a Rule-Driven Process or Generative Task?* (Skip-BART), <https://arxiv.org/html/2506.01482v2> [read]
- *Cadence: Music-Responsive Stage Lighting in Concert Video Generation*, NeurIPS 2026, <https://neurips.cc/virtual/2026/160647> [read: abstract]
- *Glow with the Flow: AI-Assisted Creation of Ambient Lightscapes for Music Videos*, <https://arxiv.org/html/2602.08838v1> [read]
- Tseng et al., *EDGE*, <https://arxiv.org/abs/2211.10658> [read: abstract]; metric critiques via <https://arxiv.org/pdf/2602.13778>, <https://arxiv.org/pdf/2505.14222> [snippet]
- Li et al., *Lodge*, <https://arxiv.org/abs/2403.10518> [read: abstract]

MIR and music perception:

- Yadati, Larson, Liem, Hanjalic, *Detecting Drops in EDM*, ISMIR 2014, <https://archives.ismir.net/ismir2014/paper/000297.pdf> [read: full text]
- felixmeyer6/drop-detector, <https://github.com/felixmeyer6/drop-detector> [read]
- Solberg & Dibben, *Peak Experiences with EDM*, Music Perception 36(4) 2019, <https://eprints.whiterose.ac.uk/145911/> [read: full text]
- Solberg & Jensenius, group behaviour to EDM, <https://arj.no/2017/07/15/group-behaviour-edm> [read: summary]
- Solberg, *Waiting for the Bass to Drop*, Dancecult 2014 [snippet]
- Kim, Kim, Kim, Nam, *Raveform*, TISMIR 9(1) 2026, <https://reference-global.com/article/10.5334/tismir.288>, text <https://transactions.ismir.net/articles/288/files/69e5ef9565689.xml> [read], <https://mir-aidj.github.io/raveform/> [read]
- Kim & Nam, *All-In-One structure analysis* (allin1), <https://github.com/mir-aidj/all-in-one> [read], <https://arxiv.org/pdf/2307.16425> [snippet]
- Kim et al., *A Computational Analysis of Real-World DJ Mixes*, ISMIR 2020, <https://arxiv.org/abs/2008.10267> [read: abstract]
- Kell & Tzanetakis, *Empirical Analysis of Track Selection and Ordering in EDM*, ISMIR 2013, <https://archives.ismir.net/ismir2013/paper/000210.pdf> [read: full text]
- Farbood, *A Parametric, Temporal Model of Musical Tension*, Music Perception 29(4) 2012, <https://bpb-us-e1.wpmucdn.com/wp.nyu.edu/dist/f/11865/files/2020/08/Farbood_2012_Musical_Tension.pdf> [read: full text]; ICMPC 2016 audiovisual tension [snippet]
- Aljanaki, Yang, Soleymani, *Developing a benchmark for emotional analysis of music* (DEAM), PLoS ONE 2017, <https://pmc.ncbi.nlm.nih.gov/articles/PMC5345802/> [read]
- Essentia LoudnessEBUR128, <https://essentia.upf.edu/reference/std_LoudnessEBUR128.html> [read]
- Müller, FMP, novelty-based segmentation, <https://www.audiolabs-erlangen.de/resources/MIR/FMP/C4/C4S4_NoveltySegmentation.html> [read: introduction only]; Foote 2000 [recalled]
- Spotify `energy` definition via secondary docs, <https://help.spotontrack.com/article/what-do-the-audio-features-mean> [snippet]

Agent engineering:

- Anthropic, *Effective context engineering for AI agents*, <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents> [read]
- Anthropic, *Writing effective tools for agents*, <https://www.anthropic.com/engineering/writing-tools-for-agents> [read]
- Anthropic, *How we built our multi-agent research system*, <https://www.anthropic.com/engineering/multi-agent-research-system> [read]
- Anthropic, *Building effective agents*, <https://www.anthropic.com/engineering/building-effective-agents> [read]

Repo files read: `lightshows/README.md`, `lightshows/shows/README.md`,
`lightshows/maps/pawsa-too-cool-to-be-careless.yml`, `scripts/show_views.py` and
`scripts/show_zoom.py` (docstrings), `scripts/musical_map.py` (level constants and functions),
`docs/energy-arcs.md`, `blocks/hi-ibiza-pulso.md`, `lightshows/sets/hi-ibiza-pulso.md`,
`docs/soundswitch/autoscript-analysis.md`, `docs/superpowers/specs/2026-11-06-show-critic-design.md`
(intro and decisions), `tracks/tech-house.yml` (energy field).
