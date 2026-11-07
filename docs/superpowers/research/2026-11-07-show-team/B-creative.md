# B — Multi-agent creative generation: research notes for NEXTRACK project 2

Date: 2026-11-07. Front: how multi-agent and LLM-critic systems create time-based or artistic
works, critique them and iterate; what transfers to an autonomous Claude Code light team that
writes a show in the show language and can never see or hear the lights.

**Legend.** **read** = I opened the source in this session (abstract, HTML full text or ar5iv)
and the claim comes from it. **read-abs** = only the abstract was available. **recalled** =
from memory, not verified here; treat as approximate. Numbers are quoted as the source gives
them.

Before researching I skimmed `lightshows/shows/README.md` (the loop, cues, handover/bridge,
gestures, rules/advice, `report`, `zoom`) and the "Why / Goals / Anti-goals" of
`docs/superpowers/specs/2026-11-06-show-critic-design.md` (which already names the planned
roles: director, track agents, critic, effects agent; and the anti-goal "opinions dressed as
facts": the report never says "boring").

---

## 0. One-screen map

| system | domain | global plan artifact | critic's senses | anti-monotony | multi vs single |
|---|---|---|---|---|---|
| Re3 / DOC | long stories | premise → setting, characters, outline (DOC: 3-level tree) re-injected in every prompt | trained rerankers (coherence, relevance), entailment, FUDGE controller | rerank filters "heavy repetition"; DOC drops outline items too similar to non-ancestors | DOC vs Re3: +22.5 coherent, +28.2 relevant, +20.7 interesting (pts) |
| Agents' Room | stories | shared labelled scratchpad written by planning agents | LLM judge (Gemini) pairwise, order swapped | scratchpad "to avoid redundant content" — did not prevent repetition | fine-tuned AR best of systems; humans still best |
| Dramatron | scripts | logline → characters → plot beats → locations → dialogue (prompt chaining) | human co-writer only | loop detector + resample | (no ablation; 15 professionals) |
| CritiCS | stories | plan refined by persona critics, each one criterion | LLM critics + leader + evaluator | criteria-split critics; evaluator picks across rounds | vs DOC plans: creative 84.33 vs 57.33 |
| FilmAgent | 3D film | director's scene outline + character profiles → JSON script | text-only (no vision), Critique-Correct-Verify, Debate-Judge | debate replaced consecutive identical shots | Group 3.98 vs Solo 3.04 vs o1 3.30 |
| ComposerX / CoComposer | symbolic music | leader's task split; ABC text | reviewer reads ABC text (no listening) | none explicit | ComposerX preferred 0.57–0.77 over single-agent; CoComposer ≈ single-agent on aesthetics |
| SceneCraft / Idea2Img | 3D scenes / images | scene graph of relations → constraint code | render + GPT-4V; constraint scores | — | inner loop: constraint score 26.1 → 88.9 |

---

## 1. Deep entries

### 1.1 Re3 (Yang et al., EMNLP 2022) and DOC (Yang et al., ACL 2023) — hierarchical plan, re-injected

**What.** Re3 writes 2,000–2,500-word stories with GPT-3 by planning first and then rebuilding
the prompt from the plan at every step; DOC deepens the plan into a multi-level outline and
adds a controller that keeps each passage on its outline item. (read, ar5iv full text for Re3;
arXiv HTML v3 for DOC)

**Roles / modules (Re3, read).**
- **Plan:** premise → one-sentence setting, up to three characters with descriptions, a
  numbered outline (resampled until it has exactly 3 points).
- **Draft:** a fixed 256-token continuation from a prompt rebuilt each step: relevant context
  (premise, setting, characters, selected by a DPR retriever against the latest passage;
  character descriptions updated as entities appear), **previous sections' outlines**, a
  **summary of the last few passages** (13B model), the **current outline point**, and the
  preceding passage verbatim.
- **Rewrite:** ~10 candidates per call; a coherence reranker (Longformer fine-tuned to tell a
  true continuation from a random one) and a relevance reranker (trained on ~2,000
  passage/summary pairs); heuristics drop empty outputs, **heavy repetition**, narration
  artifacts.
- **Edit:** extracts per-character attribute facts (kept only when several samples agree via
  entailment), flags contradictions against an attribute dictionary, edits with GPT-3's Edit
  API. Ablation: Edit contributes little.

**DOC additions (read).**
- **Detailed outliner:** breadth-first expansion of an outline tree to depth 3; each parent
  gets 2–5 children (resampled otherwise); candidates filtered for form (declarative, 3–50
  tokens) and **removed when too repetitive relative to non-ancestor nodes (edit distance +
  entailment model)**; reranked for order (RoBERTa trained to detect out-of-order events).
  Each item carries a setting and characters.
- **Detailed controller:** a FUDGE discriminator (OPT-350m) trained contrastively to tell
  whether a passage prefix matches an outline item; control strength ramps per substep; moves
  to the next item when combined relevance+coherence scores pass a threshold and stop
  improving.
- Drops Re3's Edit step (no significant effect).

**Global plan / coherence.** The plan is the only thing all steps share, and it is
**re-injected in a structured, selected form every step** (not the whole history). The
middle layer is short enough to always fit.

**Critique senses.** No LLM critic: trained classifiers (coherence, relevance, ordering),
entailment for repetition and contradictions. All are cheap, deterministic-ish scores used to
**rerank among candidates**, not to rewrite.

**Anti-monotony.** Repetition filters at rewrite (Re3) and at outline time against all
non-ancestor items (DOC). DOC notes the control/creativity trade-off: stronger control gives
"narrowly-focused, repetitive outputs".

**Stopping.** Per item: score threshold reached and no longer improving (DOC). Fixed outline
length.

**Results (read).** Re3 vs rolling GPT-3 baseline (MTurk, % of stories): Interesting 54.3 vs
45.0, Coherent 60.0 vs 45.7, Relevant 64.0 vs 44.0, Humanlike 83.3 vs 74.0. DOC vs Re3
(passage-level pairwise): Coherent 67.6 vs 45.1, Relevant 65.3 vs 37.1, Interesting 60.1 vs
39.4. Interactive (human edits the outline 15 min): DOC preferred 80% on intent/control.

**Failure modes (read).** Premise/outline drift; leaf events missed (detailed relevance only
58.5%); uneven outline detail (some leaves vague, some over-expanded); outline errors cascade
into the draft; repetition rates similar to baselines in Re3; low inter-annotator agreement.

**For NEXTRACK.** The night is a 3-level outline (night arc → track → moment). Re3's prompt
recipe is a direct template for a track agent's brief: night story + this track's arc item +
the previous track's handover and the next track's arrival + a summary of what the night has
already used + the track's map. DOC's two checks map to (a) "this track's plan item is too
similar to another track's" (computed) and (b) "the cue list is faithful to its plan item"
(a moment per planned beat).

Sources: https://arxiv.org/abs/2210.06774 · https://ar5iv.labs.arxiv.org/html/2210.06774 ·
https://arxiv.org/html/2212.10077v3

### 1.2 Agents' Room (Huot et al., 2024; ICLR 2025) — planners and section writers over a scratchpad

**What.** Narrative-theory-shaped decomposition of story writing into specialised agents that
share a labelled scratchpad, with a new dataset (Tell Me A Story) and an LLM evaluator.
(read, arXiv HTML first 100k chars)

**Roles.** Planning agents write only to the scratchpad: `[conflict]`, `[character]`,
`[setting]`, `[plot]`. Writing agents each write one part of a five-act structure:
`[exposition]`, `[rising action]`, `[climax]`, `[falling action]`, `[resolution]`. A
`[finalizer]` exists for the plan-only variant.

**Artifacts.** A shared scratchpad: the prompt, then each agent's labelled output appended.
Agents read labelled sections "which helps them avoid redundant content". Each agent formats
its output for the others; agents' own prompts are not stored.

**Orchestrator.** Deterministic, fixed order (planners, then the five acts), chosen "for
simplicity, given the strong narrative theory prior"; stops when no agents remain or at T
steps. Learned orchestration is future work.

**Critique.** No critic inside the loop. Evaluation: human pairwise preferences on Plot,
Creativity, Development, Language Use, overall (9,900 ratings, Fleiss κ=0.46); Gemini 1.5 Pro
judge pairwise with order shuffled: system-level Spearman ρ=0.62, item-level ρ=0.41;
best agreement on Development (0.83) and Creativity (0.85); same pick 90.2% after swapping
order.

**Anti-monotony / repetition.** None beyond the scratchpad. Result: writing-agent variants
produced **much more intra-story trigram repetition** (ARZS write 47.50 vs humans 15.53) and
lower lexical variety; the most repetitive systems were the longest.

**Results.** Fine-tuned Agents' Room (write and plan+write) best among systems; fine-tuned
beat zero-shot; plan-only variants poor (blamed on the simple finalizer); human stories
still preferred overall.

**Failure modes.** Repetition across section writers; one fixed structure; evaluator only
moderately correlated at item level.

**For NEXTRACK.** Strongest warning in this survey for a "one agent per track" design:
parallel section writers that each see only the plan repeat each other. The scratchpad must
carry a running **ledger of what has already been used** (looks, arrival draws, colours,
aims, gestures per track), and repetition must be checked by computation, not by trust.
The fixed, theory-driven order is a reasonable default (night arc first, tracks in set
order) — the authors chose it deliberately.

Source: https://arxiv.org/abs/2410.02603 · https://arxiv.org/html/2410.02603

### 1.3 Dramatron (Mirowski et al., CHI 2023) — hierarchical prompt chaining with a human co-writer

**What.** Chinchilla-70B (2,048-token context) co-writes screenplays/theatre scripts from a
one-sentence logline. (read, arXiv HTML first 100k chars)

**Levels / artifacts.** Logline (human) → title → characters (names + descriptions) → **plot
outline**: a list of scenes, each with location, narrative-arc element and a "beat" →
location descriptions → dialogue per scene (from beat, location, characters, logline; the
paper's two accounts disagree on whether the previous scene is seen). The plot outline is the
middle layer that fits in context and carries long-range coherence.

**Human role.** At every level: regenerate, continue, edit, and move up/down the hierarchy
(e.g., rewrite the logline after editing the plot). Eight of 15 participants mainly removed
and curated; **the plot outline was the least edited component**.

**Critique.** None automatic; the human is the critic.

**Anti-monotony.** Nucleus sampling; several seeds per level for the human to choose among;
a **loop detector that resamples when a block repeats more than a threshold (e.g., 3
times)**.

**Results.** 15 theatre/film professionals, 2-hour sessions; survey (13 respondents): surprise
92%, helpfulness 84%, enjoyment 77%, uniqueness 69%, pride 46%; most did not feel ownership.
Five scripts staged at the 2022 Edmonton Fringe.

**Failure modes (participants).** Repetition loops; stereotypes and bias; too literal and
predictable ("on the nose"); no subtext; incomplete arcs ("stories do not finish"); weak
cross-scene logic (tied to parallel dialogue generation); no sense of what is stageable.

**For NEXTRACK.** The middle layer (per-track arc beats) is where structure lives and was the
part humans trusted most; the bottom layer (here: the bars around a drop) needs the most
work. "Stories do not finish" maps to a night whose last track does not close. "Not
stageable" maps to designs the rig cannot do — the compiler already rejects most of them.
The "on the nose" failure maps to obvious choices (red at every drop, strobe on every
peak).

Source: https://arxiv.org/abs/2209.14958 · https://arxiv.org/html/2209.14958

### 1.4 CritiCS — Collective Critics for Creative Story Generation (Bae & Kim, EMNLP 2024)

**What.** A plan-then-write story system (on top of DOC) where groups of LLM critics with
distinct creativity criteria and personas refine the plan, then the text. (read, arXiv HTML)

**Roles.**
- **CrPlan:** three critics, **each owning one criterion** ("original theme and background
  setting", "unusual story structure", "unusual ending"), each given a **persona adapted to
  the story** (e.g., sociologist, psychologist, futurist for a dystopia). A **leader** (a
  literature editor) ranks the three suggestions, picks one, reconciles conflicts; the chosen
  critique revises the plan. After the rounds an **evaluator picks the final plan among all
  rounds' candidates**, balancing creativity with coherence.
- **CrText:** two critics ("Image", "Voice"), no personas; leader picks one; applied to one
  randomly chosen sentence per round.

**Artifacts.** A critique is a question plus a "why"; plans per round; a candidate list for the
evaluator.

**Critique senses.** Text only, rubric criteria from creativity literature (Mozaffari 2013).
Without personas, critics gave "broad or off-topic suggestions" (GPT-4 pairwise ablation:
personas improve every metric; values in a figure).

**Anti-monotony.** Splitting the critique into named, distinct criteria; personas grounded in
the content; one change per round.

**Stopping.** Fixed 3 rounds; then select across rounds (not "the last one wins").

**Results (human, 300 pairs, %).** Plans vs DOC: Interesting 85.00 vs 57.56, Coherent 77.89
vs 67.33, Creative 84.33 vs 57.33, Relevant 96.00 vs 95.11. Text vs DOC: Creative 89.33 vs
70.67, Interesting 80.00 vs 69.89 (coherence/consistency not significant). κ 0.19–0.52.

**Failure modes.** **More rounds → more inventive but coherence "significantly" drops** —
hence the evaluator. Without a leader, plot inconsistencies (a character returns
unexplained). Judge order-sensitive (mitigated by randomisation).

**For NEXTRACK.** The closest published template for "think about what could be better or
different" without losing the story. Map the owner's four criteria to four critics, one
criterion each (monotony across the night, immersion at drops, following each track's
energy, following the set's energy), a leader that applies **one** change per round, and an
evaluator that chooses among all round variants with the night's story as the coherence
criterion. The creativity–coherence trade-off is exactly the "fix 23 bridges without losing
the night's story" risk.

Source: https://arxiv.org/abs/2410.02428 · https://arxiv.org/html/2410.02428v1 ·
code: https://github.com/EMNLP-2024-CritiCS/Collective-Critics-for-Creative-Story-Generation

### 1.5 FilmAgent (Xu et al., 2025) — film crew roles with critique and debate, no vision

**What.** Multi-agent end-to-end film automation in pre-built Unity 3D spaces: from an idea to
an annotated script, TTS audio and rendered video. (read, arXiv HTML)

**Roles and artifacts.** Director: character profiles + scene outline (≤3 scenes; per scene:
sub-topic, characters, location, plot, dialogue goal). Screenwriter: dialogue, positions,
actions per line, movements. Actors: line adjustments for profile fit. Two cinematographers:
one shot per line. Output: **a fully annotated JSON script** (positions, actions, shots,
movements) compiled into Unity.

**Global plan.** The director's outline, conditioning every later step; no separate global
state tracker (the paper notes the gap).

**Collaboration.**
- **Critique-Correct-Verify:** actor P writes; critic Q critiques; P revises; Q verifies the
  critiques were addressed. Stop when Q returns TRUE or **M=3** iterations.
- **Debate-Judge:** two peers answer independently, critique each other for M rounds; a judge
  (the director) summarises and decides.

**Critique senses.** Text only: the critic reads the JSON script; **no visual feedback** is a
stated limitation (no multimodal LLM in the loop).

**Anti-monotony.** Observed failure: **consecutive identical medium shots**; the debate
replaced one with a pan. Also a tracking shot on a stationary character (mismatch between
movement and content).

**Results (15 ideas, human ratings).** Avg: CoT GPT-4o 2.63, CoT o1 3.30, FilmAgent Solo
(GPT-4o) 3.04, **FilmAgent Group (GPT-4o) 3.98**. Plot 1.87 → 3.53 and Camera 2.07 → 3.53 from
Solo to Group; Action 0.80 → 0.88 and Profile 4.20 → 4.44 barely moved. Revised versions
preferred over originals (figure).

**Failure modes.** Hallucinated actions not in the vocabulary ("Standing suggest"); scene
inconsistencies; profile mismatches; small evaluation (15 ideas); qualitative evidence.

**For NEXTRACK.** The most analogous architecture: a closed vocabulary (actions, shots ↔
looks, gestures, aims), a JSON script compiled into a renderer, and a critic who reads only
text. Collaboration paid most on **structure (plot) and on camera choices (where repetition
lived)**, least on things a validator could check. NEXTRACK's compiler already catches
"hallucinated vocabulary" deterministically. A camera-like debate (two independent proposals
for a moment, a judge picks) is a fit for drops.

Source: https://arxiv.org/abs/2501.12909 · https://arxiv.org/html/2501.12909

### 1.6 ComposerX (Deng et al., 2024) and CoComposer (Xing, Plaat, van Stein, 2025) — music in ABC text

**What.** GPT-4 agents compose polyphonic music in ABC notation; the reviewer never hears it.
(read, arXiv HTML for both)

**ComposerX roles.** Group leader (decomposes the request, AutoGen group chat manager),
melody, harmony (counterpoint), instrument, **reviewer** (critiques melody, harmony,
instrumentation; checks form, transitions, "conclusion efficacy"), arrangement (final ABC).
Refinement in a fixed order (melody → harmony → instruments). Stop: up to 12 rounds of
communication, arrangement starts at "satisfactory polish" (undefined).

**ComposerX results.** Listening test: multi-agent preferred over single-agent baselines at
0.77 (vs CoT), 0.68, 0.6, 0.57. Perceived as human 32.2% (human pieces 55.4%). **Good-case
rate 18.4%** (experts); ~26k tokens per song, ~$0.8 per piece but ~$4.34 per "musically
interesting" piece. Multi-agent pieces ~3× longer than single-agent.

**ComposerX failure modes.** Feedback poorly translated into notation; notes outside
instrument ranges; voices misaligned; **unresolved cadences, pieces end abruptly**; weak
dynamics/phrasing.

**CoComposer.** Five agents: leader, melody, accompaniment, **revision** (fixes timing/format
errors under a "minimum intervention principle", leaving creative content unchanged), review
(5 criteria; no numeric rubric). Iterates "multiple rounds" (no stated stop).
AudioBox-Aesthetics (automatic): CoComposer CE 6.75 / CU 7.76 / PC 4.13 / PQ 7.86;
ComposerX 6.52 / 7.61 / 3.72 / 7.76; **single-agent 6.72 / 7.77 / 3.92 / 7.88**; MusicFX
7.37 / 7.93 / 4.96 / 7.84. 20 prompts. The multi-agent edge over a single agent is within
noise on three of four axes.

**For NEXTRACK.** A text-only critic of a time-based work can check structure and rules
(form, transitions, range) but not expressiveness; the reported weaknesses (abrupt endings,
feedback that does not reach the artifact) are exactly what to measure with computed views.
CoComposer's **minimum-intervention revision agent** is the right shape for the first task
(23 bridge findings): a surgeon that changes only what the finding names. Fewer agents did as
well as more; a single agent nearly matched both.

Sources: https://arxiv.org/abs/2404.18081 · https://arxiv.org/html/2404.18081 ·
https://arxiv.org/abs/2509.00132 · https://arxiv.org/html/2509.00132v1

### 1.7 SceneCraft (Hu et al., ICML 2024) and Idea2Img (Yang et al., 2023) — render, look, revise

**SceneCraft (read).** LLM agent that turns text into Blender code. Pipeline: decompose into
sub-scenes → retrieve assets (CLIP) → **relational scene graph** (proximity, alignment,
parallelism, symmetry…) → **one scoring function per relation, written as code, returning
[0,1]** → layout optimiser maximises the summed constraint scores → render.
- **Inner loop:** GPT-4V reviews the render against the query, names unsatisfied
  constraints, edits graph edges, functions, arguments, or adds new constraint functions
  (floating lamps → a new "grounded" constraint). Fixed N_inner rounds. No ground truth or
  reward: the VLM's feedback is the only learning signal.
- **Outer loop (library learning):** functions revised across a batch of tasks are merged by
  consensus into a **spatial skill library** (seeded with 20 hand-written examples).
- **Results (40 queries):** BlenderGPT CLIP 24.7 / constraint 5.6; SceneCraft 69.8 / 88.9;
  without the learned library 48.3 / 64.5; **without the inner loop 32.8 / 26.1**; without
  the relation graph 19.4 / 3.2. Human preference: 76.8% fidelity, 83.6% composition, 74.5%
  aesthetics vs ~12–14% for BlenderGPT (22 responses).
- **Failure modes:** rarely right on the first try (hence the loop); library depends wholly
  on GPT-4V's judgment; small evaluation.

**Idea2Img (read).** GPT-4V in three roles around a text-to-image model: write N prompts,
**select the best of N drafts** (scores 1–10 with justification, then one index), write
feedback that must "**focus on one thing to improve**". A memory stores each round's prompt,
image and feedback so the LMM learns the T2I model's quirks. T=3 rounds. User preference
(104 ideas): SDXL manual prompt 13.5%, first round 29.8%, iterated **56.7%**; gains larger for
stronger generators (SD v1.5 only +4.8). Weaker LMMs repeat the same prompt without revising.

**For NEXTRACK.** The biggest measured gains in this survey come from a loop where the critic
**has a sense of the output** (render + vision) and the constraints are **code with scores**.
NEXTRACK's agents cannot see the room, but the pattern survives in two forms: (1) the
designer's intentions become scored functions over the compiled show (as `advice:` rules
already are: the critic spec's "every number has a stated formula"); (2) the vocabulary grows
as a tested library (gestures ↔ SceneCraft's constraint functions and Voyager's skills).
Idea2Img's "one thing per round" and "pick best of N" are cheap to copy with `build --out`.

Sources: https://arxiv.org/abs/2403.01248 · https://arxiv.org/html/2403.01248 ·
https://arxiv.org/abs/2310.08541 · https://arxiv.org/html/2310.08541

---

## 2. Short entries

**VideoDirectorGPT (Lin et al., 2023).** GPT-4 expands one prompt into a "video plan": scene
descriptions, entities with layouts (boxes), backgrounds, and **consistency groupings** (which
entities must stay the same across scenes); Layout2Vid renders it. Better layout/movement
control and cross-scene entity consistency. (read-abs) — Analog: named looks/palette as the
"consistency groups" of the night. https://arxiv.org/abs/2309.15091

**MovieAgent (Wu et al., 2025).** Director, screenwriter, storyboard artist, location manager;
hierarchical chain-of-thought plans scenes, camera settings, cinematography from a script and
a character bank; claims SOTA in script faithfulness, character consistency, narrative
coherence. (read-abs) https://arxiv.org/abs/2503.07314

**DreamFactory (Xie et al., 2024).** Multi-agent long video with a "key frames iteration
design" for style consistency; proposes Cross-Scene Face Distance and Cross-Scene Style
Consistency scores. (read-abs) — Pattern: invent a computed metric for the cross-part property
you care about. https://arxiv.org/abs/2408.11788

**WavJourney (Liu et al., 2023).** LLM writes a structured **audio script**, compiled into a
program that calls TTS/music/SFX models; interpretable and editable across dialogue turns.
(read-abs) — Same architecture as the show language: the LLM writes data, a compiler makes
the work. https://arxiv.org/abs/2307.14335

**ByteComposer (Liang et al., 2024).** Melody agent: conception analysis → draft → self-
evaluation and modification → aesthetic selection, with symbolic music tools; experts placed
it at "novice melody composer" level. (read-abs) https://arxiv.org/abs/2402.17785

**MusicAgent (Yu et al., 2023).** LLM orchestrates music tools (Hugging Face, GitHub, APIs)
for understanding/generation tasks; tool routing, not creative critique. (recalled)
https://arxiv.org/abs/2310.11954

**ChatMusician (Yuan et al., 2024).** LLaMA2 trained on ABC text; claims it beats GPT-4
baselines at composing full pieces; MusicTheoryBench shows general LLMs' music reasoning is
weak (no GPT-4 number in the abstract). (read-abs) — A text critic of music is not a music
expert by default. https://arxiv.org/abs/2402.16153

**DanceChat (2025).** LLM as "virtual choreographer": receives **precomputed symbolic music
descriptors** (tempo, chords, key, beat structure) as templated text and returns one dance
instruction per 5-s clip that conditions a diffusion model; one-shot, no critique.
Diversity metrics closest to ground truth (Div_k 10.64 vs GT 10.61). (read) — Supports
"precompute analyses, let the LLM read text descriptors". https://arxiv.org/abs/2506.10574

**CustomDance (SIGGRAPH Asia 2026).** An MLLM reads music + text and outputs **temporal
anchors with creative cues**; per anchor, motion clips are retrieved and stitched; iterative
user-guided refinement. (read-abs) — Same shape as NEXTRACK cues on map anchors.
https://arxiv.org/abs/2608.06722

**Lodge (CVPR 2024).** Long dance via coarse-to-fine diffusion: a global stage produces
"characteristic dance primitives", a local stage fills detail in parallel. (read-abs) —
Global-first, local-parallel, with an explicit intermediate representation.
https://arxiv.org/abs/2403.10518

**Stage lighting generation — little exists, none agentic.**
- **Skip-BART (ICLR 2026, arXiv 2506.01482).** First end-to-end learned stage lighting:
  audio (OpenL3) → **one "principal" light's hue and intensity at 10 fps**, trained on 699
  clips from 35 live shows with labels extracted from video. Human study (38 people, 7-pt):
  ground truth 4.51, Skip-BART 4.35 (n.s.), **rule-based emotion→colour baseline 2.67**.
  Limitations: overly strong local fluctuations, weak long-term stability, single light,
  offline; suggests beats/sections/lyrics as future inputs. The paper makes no claim about
  energy, drops or repetition. (read) https://arxiv.org/html/2506.01482
- **SeqLight (arXiv 2605.03660).** Skip-BART for a global colour distribution, then imitation
  learning to split it across multiple lights; no song structure, energy or diversity
  discussed in the abstract. (read-abs) https://arxiv.org/abs/2605.03660
- **LightingGen** (IEEE TMM 2026, DMX-based generation) is cited by SeqLight; not verified.
- **LLM lighting agents:** only demos and listings found (ENTTEC S-PLAY with ChatGPT at
  DevDay 2025; a "LacyLights" MCP agent listing). No research on LLM-planned stage lighting
  with critique was found. (read, search results only)
- **Takeaway:** NEXTRACK is ahead of the literature on structure: research models map frames
  to colour and admit weak long-term structure; nobody models a night's arc, drops or
  monotony. There is no benchmark to borrow; the owner's four criteria must become our own
  metrics.

**DJ mix / set planning with LLM agents — essentially none in research.** DJtransGAN (GAN
transitions), "DJ AI" (Audio Mostly 2025: ordering + MusicGen transitions), a TIME 2025 paper
splitting DJ decisions into transition / next track / overall flow, and an AiJockey hackathon
pipeline (Director picks a narrative, Planner beam-searches, Executor with 33 transition
primitives). (read, search results only; not peer-reviewed except the first three)

**Voyager (Wang et al., 2023).** Minecraft agent with automatic curriculum, a **skill library
of executable code** retrieved and composed later, and iterative prompting with execution
errors and self-verification; 3.3× more unique items, up to 15.3× faster milestones;
the library transfers to new worlds. (read-abs) — Template for "create a gesture when the
vocabulary lacks a word": code + test + library entry + docstring that later agents read
(NEXTRACK's `vocab`). https://arxiv.org/abs/2305.16291

---

## 3. Self-critique, debate and judging — the evidence

**Self-Refine (Madaan et al., 2023).** One LLM generates, critiques and refines; ~20% absolute
average gain on 7 tasks. (read-abs) https://arxiv.org/abs/2303.17651
**Counter-evidence — Huang et al., "LLMs cannot self-correct reasoning yet" (ICLR 2024).**
Without external feedback, self-correction holds or **hurts**: GPT-4 GSM8K 95.5 → 91.5 → 89.0;
GPT-3.5 CommonSenseQA 75.8 → 38.1; models turn correct answers into wrong ones more often than
the reverse. With oracle labels it helps (GPT-3.5 GSM8K 75.9 → 84.3). Part of Self-Refine's
CommonGen gain came from a weak first prompt: a stronger first prompt scored 81.8 and fell to
75.1 after self-correction. Self-consistency (majority vote) beat multi-agent debate at equal
response counts (GSM8K 85.3 vs 83.2 at 6; 88.2 vs 83.0 at 9). (read)
https://arxiv.org/html/2310.01798

**CRITIC (Gou et al., ICLR 2024).** Verify-then-correct with **external tools** (search, code
interpreter, toxicity API). ChatGPT QA F1 +~7.7 avg, math +~7.0, toxicity probability 0.192 →
0.040. **Without tools** the critique "contributes marginally" (QA +2.3) or harms (toxicity
probability rises to 0.223). Stops after 3–4 corrections or when the output is unchanged twice;
2–3 rounds capture most of the benefit. (read) https://arxiv.org/html/2305.11738v4

**Reflexion (Shinn et al., 2023).** Verbal reflections on task feedback kept in an episodic
memory for later trials; feedback may be scalar or language, external or simulated; 91%
pass@1 HumanEval vs GPT-4's 80%. Works where an evaluator signal exists (tests). (read-abs)
https://arxiv.org/abs/2303.11366

**Multi-agent debate (Du et al., 2023).** Several instances propose and debate over rounds,
improving reasoning and factuality. (read-abs) https://arxiv.org/abs/2305.14325
**MAD (Liang et al., EMNLP 2024).** Names **Degeneration-of-Thought**: once a model is
confident, self-reflection cannot produce novel thoughts. Debate with a judge helps; needs
adaptive ending and only moderate disagreement; "LLMs might not be a fair judge if different
LLMs are used for agents". (read-abs) https://arxiv.org/abs/2305.19118
**Debate or Vote (2025).** Majority voting alone accounts for most of debate's gains; debate is
a martingale (neutral in expectation) unless biased toward correction. (read-abs)
https://arxiv.org/abs/2508.17536
**Wang et al. 2024, "Rethinking the bounds".** A single agent with strong prompts nearly
matches the best multi-agent discussion; discussion wins only without demonstrations.
(read-abs) https://arxiv.org/abs/2402.18272

**Why multi-agent systems fail — MAST (Cemri et al., 2025).** 1,642 traces, 7 frameworks,
failure rates 41–86.7%. Most frequent: step repetition 15.7%, reasoning-action mismatch 13.2%,
**unaware of termination conditions 12.4%**, disobeying the task spec 11.8%; incorrect
verification 9.1%, no/incomplete verification 8.2%, premature termination 6.2%. Verifiers do
"superficial checks" (does it compile). Fixes: giving one role the final say on termination
+9.4%; **adding a high-level objective verification step +15.6%** (largest). (read)
https://arxiv.org/html/2503.13657

**Self-preference — Panickssery, Bowman, Feng (NeurIPS 2024).** LLMs recognise their own text
(GPT-4 73.5% out of the box) and prefer it: pairwise self-preference GPT-4 0.705 (XSUM),
**0.912 (CNN)**. Fine-tuning self-recognition raises self-preference along a linear trend
(GPT-3.5 to ~0.90–0.97); confounders (length, readability) fall on the same line. Proposed
mitigation: authorship obfuscation / paraphrase (untested); a different judge model is
implied, not tested. (read) https://arxiv.org/html/2404.13076
**Wataoka et al. 2024.** GPT-4 shows significant self-preference; LLM judges rate
**lower-perplexity (more familiar) text** higher than humans do, **whether or not they wrote
it**. (read-abs) https://arxiv.org/abs/2410.21819 — Implication: a critic LLM drifts toward
the typical; self-preference and homogenization are the same force.

**Can LLMs judge creative work?**
- **Chakrabarty et al. (CHI 2024), TTCW:** 14 binary tests (Fluency, Flexibility,
  Originality, Elaboration); LLM stories pass 3–10× fewer tests than professionals'; **no LLM
  judge positively correlated with expert assessments**. (read-abs)
  https://arxiv.org/abs/2309.14556
- **Si et al. (2024):** LLM judges agreed with human reviewers 53.3% at best vs human–human
  56.1% (chance 50%); "LLMs cannot evaluate ideas reliably yet". (read)
- **Agents' Room:** Gemini judge ρ=0.62 system / 0.41 item level with humans. (read)
- **Artificial Hivemind:** judges and reward models lose calibration on similar-quality
  responses and on items where humans disagree. (read)

---

## 4. Homogenization and what counters it

**Evidence of collapse.**
- **Si et al. (2024):** 4,000 seed ideas per topic → only ~200 non-duplicates (~5%) at cosine
  0.8 (MiniLM); the unique count plateaus as generation scales. AI ideas were judged **more
  novel** than experts' (5.64 vs 4.84, p<0.01) and slightly less feasible — novelty per item
  is not the problem, the spread is. (read) https://arxiv.org/html/2409.04109
- **Artificial Hivemind (Jiang et al., NeurIPS 2025):** for 79% of open-ended queries, 50
  samples from one model average >0.8 pairwise similarity (top-p 0.9, T=1); even min-p at T=2
  leaves 61.2% of pairs >0.8. **Different models are 0.71–0.82 similar to each other**, with
  verbatim shared phrases. (read) https://arxiv.org/html/2510.22954
- **Padmakumar & He (ICLR 2024):** co-writing with InstructGPT (not base GPT-3) significantly
  reduced diversity across authors; the loss came from model-written text. (read-abs)
  https://arxiv.org/abs/2309.05196
- **Doshi & Hauser (Science Advances 2024):** GenAI ideas made individual stories better
  rated but stories **more similar to each other** (roughly +10% similarity with five AI ideas).
  (read-abs for the direction; magnitudes recalled) https://arxiv.org/abs/2312.00506
- Dramatron: "predictable", "on the nose" (read). Agents' Room: 3× human trigram repetition
  (read).

**Countermeasures with evidence.**
- **Verbalized sampling (Zhang et al., 2025):** ask for N responses with their probabilities;
  1.6–2.1× diversity in creative writing without loss of quality; cause = typicality bias in
  preference data. (read-abs) https://arxiv.org/abs/2510.01171
- **Prompting (Meincke, Mollick, Terwiesch 2024):** default GPT-4 idea pools less diverse than
  human groups; **chain-of-thought prompting was the best strategy** (cosine ~0.255, close to
  humans); famous-persona prompts were mixed (~0.37–0.39). (read-abs; numbers from a search
  summary) https://arxiv.org/abs/2402.01727
- **Overgenerate + dedupe + rank** (Si et al.): works until the plateau; dedupe needs an
  explicit similarity measure. (read)
- **Quality-Diversity through AI Feedback (QDAIF, Bradley et al., ICLR 2024):** MAP-Elites
  archive whose **diversity axes are user-defined and measured by an LM** (sentiment, genre,
  ending, tone); quality by an LM yes/no; mutation by few-shot LM crossover. Beats non-QD
  baselines on QD score; human QD 0.772 vs 0.767 fixed-few-shot (quality slightly lower:
  3.900 vs 4.133). Failure: reward hacking at the top AI scores; axes must be specified by
  hand. (read) https://arxiv.org/html/2310.13032v4
- **Distinct-criterion critics with content personas** (CritiCS, read); **debate between two
  independent proposals** (FilmAgent's shot debate, read); **loop detector + resample**
  (Dramatron, read); **repetition filter against everything already planned** (DOC, read).

---

## 5. Answers to the six questions

**Q1. Global structure first, coherence across agents.** Every system that does long works
well plans a short middle layer first and **re-injects a selected slice of it into every
writer's prompt**: Re3 (plan + previous sections' outlines + recent summary + current item),
DOC (3-level outline + a controller that checks faithfulness per item), Dramatron (logline →
beats → scenes; the beat list was the least edited layer), Agents' Room (labelled scratchpad
read by section writers), FilmAgent (director's outline + character profiles), VideoDirectorGPT
(scene plan + consistency groupings), Lodge (global primitives, local detail in parallel).
Coherence is enforced by (a) the shared plan, (b) explicit consistency objects (characters,
settings, entity groups ↔ palette, named looks), (c) a check that each part is faithful to its
plan item (DOC's controller, FilmAgent's verify step). Failure when parts are written in
parallel without seeing each other: cross-scene logic gaps (Dramatron) and repetition across
sections (Agents' Room).

**Q2. Roles and artifacts.** Recurring roles: leader/director/orchestrator; planners by aspect
(conflict, character, setting, plot); writers by part (act, scene, voice); critic/reviewer
(sometimes several by criterion); judge/evaluator that chooses; revision/editor with minimal
intervention; library learner. Artifacts are structured text: outlines and beats, labelled
scratchpads, JSON scripts, ABC notation, scene graphs + constraint code, audio scripts, image
prompts + memory of previous rounds, critiques as "question + why". The successful ones pass
**compiled or compilable** artifacts (FilmAgent JSON, SceneCraft code, WavJourney program)
rather than prose.

**Q3. Critique without perceiving.** Four modes:
1. *Text-only reading of a symbolic artifact* (ComposerX, CoComposer, FilmAgent, CritiCS):
   catches structure, consistency and vocabulary errors; weak on expressiveness; gains over a
   single agent range from large (FilmAgent plot/camera) to nil (CoComposer aesthetics).
2. *Trained scorers / metrics* (Re3/DOC rerankers, entailment, AudioBox-Aesthetics, CLIP):
   reliable for coherence and relevance; used to **rank candidates**.
3. *Render + vision model* (SceneCraft, Idea2Img): largest measured loop gains (constraint score
   26.1 → 88.9; preference 29.8% → 56.7%).
4. *External tools* (CRITIC): tool-grounded critique works; the same critique without tools
   adds little or harms (Huang et al.).
What worked: critique grounded in an external, computed signal, and selection among
candidates. What did not: intrinsic self-judgment of creative quality (TTCW: no LLM correlated
with experts; Si et al.: below human–human agreement).

**Q4. Monotony within a work, homogenization across runs.** Within a work: repetition filters
against all prior parts (DOC), loop detectors (Dramatron), rerankers dropping repetitive
candidates (Re3), debate on repeated choices (FilmAgent), criterion-split critics (CritiCS).
Across runs: overgenerate + dedupe (Si et al.), verbalized sampling, CoT prompting, QD archives
on explicit axes (QDAIF). Persona prompting has mixed evidence; changing the model barely helps
(cross-model similarity 0.71–0.82).

**Q5. Critic independence and self-preference.** Judges prefer their own text (GPT-4 0.71–0.91
pairwise) and, more generally, familiar low-perplexity text; self-reflection degenerates once
confident (DoT); debate without a correction bias is neutral. Systems handle it by: a separate
critic role with different instructions (FilmAgent, CritiCS), pairwise judging with order
swapped (Agents' Room: 90.2% stable), randomised order (CritiCS), human or tool ground truth
(Dramatron, CRITIC). Implication: the critic should be a fresh context that sees the views and
the plan, not the writer's reasoning; it should argue from computed numbers; its preference for
"typical" must be countered by explicit diversity metrics; final ground truth is the owner in
the room.

**Q6. Stopping, failure modes, human results.** Stopping is almost always a small fixed budget
(FilmAgent M=3, Idea2Img T=3, CritiCS 3 rounds, CRITIC 3–4 or unchanged twice, ComposerX ≤12
messages) plus a verifier's TRUE; 2–3 rounds capture most of the benefit (CRITIC); more rounds
trade coherence for novelty (CritiCS), so select across rounds. MAST: termination and
verification failures are among the most frequent; a role with the final say and a high-level
objective check gave +9.4% and +15.6%. Human results: multi-agent clearly beat single-agent
on structure and on repeated-choice problems (FilmAgent Group 3.98 vs Solo 3.04; DOC/Re3
+14–28 points; CritiCS +27 creativity points), weakly or not at all on local aesthetics
(CoComposer ≈ single-agent; ComposerX good-case 18.4%), and equal compute single-agent baselines
often close the gap (Wang et al.; Debate or Vote). Humans still beat all story systems
(Agents' Room, TTCW).

---

## 6. Patterns that transfer to NEXTRACK

1. **A three-level outline before any YAML, re-injected as a selected slice.** Night arc
   (`story` + one card per track: energy target 0–9 for the leg, role in the arc, arrival
   idea, peak moment, colour/look family, what changes from the previous track) → track cue
   list → moment. Each track agent's brief = night story + its card + the previous track's
   handover + next track's card + the **ledger of what the night already uses** + its map
   digest. *(Re3 prompt recipe; DOC outline; Dramatron middle layer; Agents' Room scratchpad.)*
   Write the arc cards to a file in the show folder (or a scratch file) so the critic reads
   the same plan.

2. **A ledger and computed repetition checks, not trust.** Parallel per-track writers repeat
   each other (Agents' Room 47.50 vs 15.53 trigram repetition). Keep a running table of
   looks, arrival draws, mover moves, aims, colours, gestures per track (the report's night
   summary is most of it) and add **advice** rules that measure sameness: consecutive tracks
   with the same (look, colour, aim) signature, the longest run of identical sections, share of
   night time in the top look (Hï Ibiza: `respiracao-azul` ~8 of the first 28 min).
   `arrivals {draw_differs}`, `budget` and `exclusive` already do part of this. *(DOC's filter
   against non-ancestors; Dramatron loop detector; FilmAgent's identical shots; QDAIF axes.)*

3. **Turn the owner's four criteria into computed facts, each owned by one critic.** Keep the
   critic spec's anti-goal (no "boring" in the report): compute numbers with stated formulas,
   let critics judge. Candidate facts: *monotony* = run lengths and time shares per look/
   colour/aim, transitions per minute; *immersive drops* = peak table light-level jump and
   accents at each map drop, hit-check kick on the first 1/16; *track energy* = per-track
   agreement between the music strip and the light strip (e.g., rank correlation per bar);
   *set energy* = per-leg mean light level against the arc card's target. One critic per
   criterion, a persona only where it sharpens the critique (a club LD for drops). *(CritiCS
   criterion-split critics; SceneCraft constraint scores; TTCW binary tests; CRITIC tools.)*

4. **One change per round, then select across rounds.** The leader applies the single most
   valuable critique per round; every round's variant is built with
   `build <variant> --out <scratch>/r<N>`; an evaluator picks the best variant across all
   rounds by the plan's story (coherence) and the four criteria (quality), never "the last".
   *(Idea2Img "focus on one thing"; CritiCS evaluator; CritiCS creativity–coherence trade-off.)*

5. **Ground every critique in the views and require citations.** A critique must quote the
   report/zoom line or number it rests on (bar, clock, level). Self-critique without that
   grounding adds little or hurts. *(CRITIC w/o tools; Huang et al.; MAST "superficial
   verification".)*

6. **An independent critic.** Fresh subagent context: sees the plan, the show files and the
   views, **not** the writer's reasoning or which agent wrote what. Pairwise comparisons of
   variants with order swapped (keep only verdicts that survive the swap). Ask it for "the most
   predictable choice in this track" and "where two tracks look alike", which counters its
   familiarity bias, rather than "is this good". A different model for the critic is optional:
   cross-model homogeneity is 0.71–0.82. *(Panickssery; Wataoka; Agents' Room order swap;
   Artificial Hivemind.)*

7. **Variants, deduped by signature, for the moments that matter.** For each drop/arrival,
   generate 2–3 independent proposals (two "cinematographers"), possibly with verbalized
   sampling ("give 4 options with how typical each is"), dedupe by their compiled signature
   (layers per section), judge pairwise. Spend this budget on drops and arrivals, not on
   every cue. *(FilmAgent Debate-Judge; Si et al. dedupe; verbalized sampling; Idea2Img
   best-of-N.)*

8. **A minimum-intervention revisor for findings like the 23 bridges.** One agent, one finding
   at a time: shorten the handover to the bar the finding names or start a cue where it says,
   change nothing else. Then **verify the story is intact by diffing computed invariants**
   before/after: arrivals (track, bar, draw), moments and their bars, the peak table rows,
   look/colour time shares within a tolerance. A changed invariant is escalated to the leader,
   not silently accepted. *(CoComposer revision agent; DOC faithfulness check; MAST high-level
   objective verification +15.6%.)*

9. **Small, fixed round budget with explicit termination owner.** Max 3 critique rounds per
   track and 2 for the night; stop early when blocking findings are zero and no criterion
   metric improved for two rounds; the director owns the stop and runs a final check against
   the four criteria (not only "build passes"). *(FilmAgent M=3; CRITIC unchanged-twice;
   CritiCS 3 rounds; MAST final-say +9.4%, objective check +15.6%.)*

10. **Gestures as a tested skill library.** When the vocabulary lacks a word: the effects agent
    writes the gesture + docstring + example + test (the checklist exists), and it enters
    `vocab` for every later agent. Promote a gesture only when it serves at least one planned
    moment; prefer generalising an existing gesture over a near-duplicate. *(Voyager skill
    library; SceneCraft outer loop: library 64.5 → 88.9 constraint score.)*

11. **Memory of lessons across runs.** Keep a short lessons file (owner's room feedback, critic
    findings that turned out wrong, compiler/rig quirks such as "pingpong and blink are lit at
    full") that every agent reads. *(Reflexion episodic memory; Idea2Img memory learning the
    generator's quirks.)*

12. **Precompute the analyses; let agents read text descriptors.** Every system that conditions
    an LLM on music reads **precomputed symbolic descriptors** (DanceChat: tempo, chords, key,
    beats as text; ComposerX/ChatMusician: ABC; CustomDance: anchors), and research lighting
    models list sections/beats as missing inputs (Skip-BART). Determinism also makes variants
    comparable and critiques reproducible. Recommendation for the open question: maps and
    views are **precomputed inputs** (already the design: `lightshows/maps/` + `report` +
    `zoom`); subagents call views on demand (cheap, deterministic), never re-run audio analysis.
    A per-track **digest** (sections, drops, energy strip, voices) prepared once for the
    director saves every agent from re-reading maps. *(DanceChat, Re3's precomputed summaries,
    SceneCraft's precomputed asset retrieval.)*

13. **Keep the team small and the order fixed.** A theory-driven fixed order (arc → tracks in
    set order → moments → critique) is what Agents' Room chose; five agents did as well as six
    (CoComposer vs ComposerX); a single strong agent with good prompts often nearly matches
    discussion (Wang et al.). Add a role only where an ablation-like before/after shows value.
    *(Agents' Room; CoComposer; Wang et al.; Debate or Vote.)*

## 7. What does not transfer (and why)

- **Trained rerankers, controllers and fine-tuned agents** (Re3, DOC, Agents' Room ARFT,
  Skip-BART): need thousands of labelled examples; NEXTRACK has one owner, one room, a handful
  of shows. Replace with hand-written scoring functions (advice rules) whose formulas are
  stated.
- **Render + vision critique as in SceneCraft/Idea2Img:** the agents cannot see the room; a
  simulator image is not haze and beams, and SceneCraft's own library rests unverified on
  GPT-4V's taste. A partial version exists (`render` sim, Vorlane `--frames`), and Claude can
  read images, but treat any visual check as a weak proxy and keep numbers primary. Worth an
  experiment, not a foundation.
- **Debate as a quality engine** (Du et al.): for non-verifiable creative choices, gains
  mostly come from voting/selection; debate is neutral in expectation. Use independent
  proposals + a judge, not long argument.
- **Large-panel human evaluation** (Turing tests, MTurk, 15 professionals): the owner tests at
  the end only. Human evaluation is the backlog, not the loop.
- **Emotion → colour mappings** (the Skip-BART rule-based baseline, 2.67/7): contested and
  weakest in the only lighting user study; NEXTRACK's palette is the owner's design choice, not
  an inferred emotion.
- **Frame-level learned lighting** (Skip-BART, SeqLight): single light, no structure, no
  drops; NEXTRACK's problem is structural (arc, drops, monotony), which those models admit they
  lack.
- **Persona diversity as the main anti-monotony lever:** evidence is mixed (Meincke et al.);
  personas helped CritiCS only as critique sharpeners. Diversity must be measured, not hoped
  for.
- **Swapping models for diversity:** cross-model homogeneity 0.71–0.82 (Artificial Hivemind).
- **Open-ended agent counts and free-form group chat** (ComposerX's 12-message AutoGen chat):
  MAST shows step repetition and termination confusion are the top failures; NEXTRACK's
  Claude Code subagents should pass files, not chat.

## Sources (opened in this session unless marked)

- Re3: https://arxiv.org/abs/2210.06774 · https://ar5iv.labs.arxiv.org/html/2210.06774
- DOC: https://arxiv.org/html/2212.10077v3
- Agents' Room: https://arxiv.org/html/2410.02603
- Dramatron: https://arxiv.org/html/2209.14958
- CritiCS: https://arxiv.org/html/2410.02428v1
- FilmAgent: https://arxiv.org/html/2501.12909
- ComposerX: https://arxiv.org/html/2404.18081 · CoComposer: https://arxiv.org/html/2509.00132v1
- SceneCraft: https://arxiv.org/html/2403.01248 · Idea2Img: https://arxiv.org/html/2310.08541
- VideoDirectorGPT: https://arxiv.org/abs/2309.15091 · MovieAgent: https://arxiv.org/abs/2503.07314 · DreamFactory: https://arxiv.org/abs/2408.11788
- WavJourney: https://arxiv.org/abs/2307.14335 · ByteComposer: https://arxiv.org/abs/2402.17785 · ChatMusician: https://arxiv.org/abs/2402.16153 · MusicAgent (recalled): https://arxiv.org/abs/2310.11954
- DanceChat: https://arxiv.org/html/2506.10574v2 · CustomDance: https://arxiv.org/abs/2608.06722 · Lodge: https://arxiv.org/abs/2403.10518
- Skip-BART: https://arxiv.org/html/2506.01482 · SeqLight: https://arxiv.org/abs/2605.03660
- Voyager: https://arxiv.org/abs/2305.16291
- Self-Refine: https://arxiv.org/abs/2303.17651 · Reflexion: https://arxiv.org/abs/2303.11366 · CRITIC: https://arxiv.org/html/2305.11738v4 · Huang et al.: https://arxiv.org/html/2310.01798
- Du et al.: https://arxiv.org/abs/2305.14325 · Liang et al. MAD: https://arxiv.org/abs/2305.19118 · Debate or Vote: https://arxiv.org/abs/2508.17536 · Wang et al.: https://arxiv.org/abs/2402.18272 · MAST: https://arxiv.org/html/2503.13657
- Panickssery et al.: https://arxiv.org/html/2404.13076 · Wataoka et al.: https://arxiv.org/abs/2410.21819 · TTCW: https://arxiv.org/abs/2309.14556
- Si et al.: https://arxiv.org/html/2409.04109 · Artificial Hivemind: https://arxiv.org/html/2510.22954 · Padmakumar & He: https://arxiv.org/abs/2309.05196 · Doshi & Hauser: https://arxiv.org/abs/2312.00506 · Meincke et al.: https://arxiv.org/abs/2402.01727 · Verbalized Sampling: https://arxiv.org/abs/2510.01171 · QDAIF: https://arxiv.org/html/2310.13032v4
