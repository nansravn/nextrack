# A — Orchestration practice in agent harnesses (research notes for NEXTRACK project 2)

Date: 2026-11-07. Scope: how multi-agent create → critique → iterate loops are built and run
today, especially inside Claude Code, and what transfers to an autonomous light-show team.

**Marking.** **[read]** = I opened the source in this session (file on disk, web page, or repo
file through `gh api`). **[read: abstract]** = only the abstract or search snippets.
**[recalled]** = from memory, not verified in this session. **[measured]** = I ran a
read-only command in this session.

Contents
1. Deep entries (the six most relevant systems)
2. Short entries (other systems and evidence)
3. Answers to the six questions, with evidence
4. The architecture question: analyses precomputed or on demand
5. Patterns that transfer to NEXTRACK
6. What does not transfer

---

## 1. Deep entries

### 1.1 superpowers 7.0.0: subagent-driven-development (SDD) and its siblings

**What it is.** A Claude Code plugin of skills. SDD runs an implementation plan in the main
session (the *controller*), which dispatches a fresh implementer subagent per task, a task
reviewer after each, scoped re-reviews in a capped fix loop, and one final whole-branch
review. Local path:
`~/.claude/plugins/cache/claude-plugins-official/superpowers/7.0.0/skills/subagent-driven-development/`
(`SKILL.md`, `implementer-prompt.md`, `task-reviewer-prompt.md`, `re-review-prompt.md`,
`scripts/{sdd-workspace,task-brief,review-package}`). **[read, all files in full]**

**Roles.**
- *Controller* (the main session following the skill as a written rite). Holds the plan, the
  spec and cross-task context; never writes code ("Never fix findings yourself in the
  controller session — your context stays clean for coordination, and controller fixes skip
  review"). Makes *rulings* instead of stopping: "Record every decision in the ledger as
  `Ruling: <what you decided> — <why> — <what it costs if wrong>`, and keep going." **[read]**
- *Implementer* (fresh general-purpose subagent per task). Implements, tests (TDD evidence),
  commits, self-reviews, reports. Must not dispatch subagents: "In real sessions, every
  reviewer a worker spawned duplicated the task review the controller dispatched anyway — a
  full extra review seat per task." **[read]**
- *Task reviewer* (fresh subagent). Two verdicts in one pass: spec compliance (missing /
  extra / misunderstood) and quality (Critical / Important / Minor). Read-only. **[read]**
- *Scoped re-reviewer* (fresh subagent per fix round). Verdicts each prior finding
  ADDRESSED / NOT ADDRESSED and checks only the fix diff for new breakage; out-of-scope
  observations go to the ledger, "they never extend the loop". **[read]**
- *Final reviewer* (`requesting-code-review/code-reviewer.md`), on the most capable model,
  with a "Declined to judge" list so nothing is set aside silently. **[read]**

**What each role receives (the handoff is files, not pasted text).**
- `scripts/task-brief PLAN N` extracts one task's text to `<workspace>/task-N-brief.md`.
  The dispatch carries: one line on where the task fits; the brief path ("read this first —
  it is your requirements"); interfaces from earlier tasks; the controller's resolution of
  ambiguities; the report-file path and report contract. "Never make a subagent read the
  whole plan file." **[read]**
- "A dispatch prompt describes one task, not the session's history … a real session's
  dispatch hit 42k chars of which 99% was pasted history." **[read]**
- The implementer writes its full report to `task-N-report.md` and returns ≤ 15 lines:
  status (`DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT`), commits, one-line test
  summary, concerns, report path. **[read]**
- `scripts/review-package PLAN BASE HEAD` writes commit list + stat + `git diff -U10` to a
  file; "the output never enters your own context". The reviewer receives three paths
  (brief, report, package) plus the global constraints copied verbatim. **[read]**
- Rationale: "Everything you paste into a dispatch prompt — and everything a subagent prints
  back — stays resident in your context for the rest of the session … Hand artifacts over as
  files." **[read]**

**How critique is kept independent.**
- Reviewers never get the controller's session history (requesting-code-review: "Hand it
  precisely crafted context, never your session's history. That keeps the reviewer on the
  work product, not your thought process"). **[read]**
- "Do Not Trust the Report … Design rationales in the report are claims too: 'left it per
  YAGNI' … is the implementer grading their own work … a stated rationale never downgrades a
  finding's severity." **[read]**
- The controller must not pre-judge: "If the prompt you are writing contains 'do not flag,'
  'don't treat X as a defect,' 'at most Minor,' or 'the plan chose' — stop: you are
  pre-judging." **[read]**
- Plan-mandated defects are still reported ("The plan's authorship does not grade its own
  work; the human decides"). **[read]**
- Brainstorming's *builder check* (`brainstorming/builder-check-prompt.md`): a fresh agent
  who "will not be able to talk to the person who wrote it" reads the design and lists only
  the questions where "a wrong guess would matter", ranked; the author sorts them into
  answered / minor (author's call, marked) / theirs (owner). One round only. **[read]**

**Stopping criteria and anti-churn.**
- Task done = review clean, or every open finding parked with a ruling at the cap.
- Minor findings never enter the loop (ledgered as deferred minors, triaged by the final
  review).
- Fix loop: max 5 rounds. Rounds 1–3 resume the same implementer (context intact); rounds
  4–5 a fresh implementer on a more capable model ("A loop that survives three resumes
  usually means the implementer cannot see its own problem"). **[read]**
- The *breaker*: at round 5 the controller adjudicates each open finding (reviewer wrong →
  park; real but not load-bearing → park; real and load-bearing → rule the smallest change).
  "Adjudicate only at the cap. Adjudicating earlier to end a loop is pre-judging with a
  different name." "Past the cap, rounds don't converge — the failure is structural." **[read]**
- Final review: exactly ONE fix dispatch for the full findings list and one scoped
  re-review; "Per-finding fixers each rebuild context and re-run suites; a real session's
  final-review fix wave cost more than all its tasks combined." No second wave. **[read]**
- Rationalization table: "The loop without reviews is just unverified churn. Reviews are the
  loop's brakes and steering." **[read]**

**State between iterations.** A per-plan workspace `.superpowers/sdd/<plan>/` (git-ignored)
with `progress.md` whose first line names the plan. "Conversation memory does not survive
compaction. In real sessions, controllers that lost their place have re-dispatched entire
completed task sequences — the single most expensive failure observed." Resume rule: tasks
with a `Task N: complete` line are done; a task whose last line is a fix round is mid-loop.
"After compaction, trust the ledger and `git log` over your own recollection." **[read]**

**Cost control.** Explicit model per dispatch ("An omitted model inherits your session's
model — often the most capable and most expensive"); cheapest tier for transcription tasks;
mid tier as the floor for reviewers ("the cheapest models routinely take 2-3× the turns on
multi-step work — costing more overall"); most capable for the final review and for
escalation. "Batch small same-shape work" into one dispatch. Never parallel implementers on
shared code ("conflicts"). Waiting: bounded 5–10 minute stretches, never short polling.
**[read]**

**Human checkpoints.** Continuous execution, no "should I continue?". Exactly four stop
classes: irreversible/destructive, security-sensitive, a side effect outside the worktree
that norms say to ask about (merge, push, publish), and a plan so broken every path is a
guess. At the end, every `Ruling:` line goes to the human under "Rulings I made", each with
its cost if wrong: "A ruling that dies with the workspace was a decision made in secret."
**[read]**

**Evidence of what worked/failed** (all from the skill's own text, observed in "real
sessions"): re-dispatch of completed sequences after compaction; 42k-char dispatches of
pasted history; worker-spawned reviewers duplicating seats; final fix waves costing more than
all tasks. These are practitioner observations, not controlled studies. **[read]**

**dispatching-parallel-agents** (`skills/dispatching-parallel-agents/SKILL.md`): one agent
per independent problem domain, all dispatched in one message; each gets specific scope,
clear goal, constraints ("Do NOT change production code"), expected output. Don't use when
failures are related, when the full system state is needed, or with shared state. After:
check for conflicts, run the full suite, spot-check ("Agents can make systematic errors").
**[read]**

**writing-skills** (`skills/writing-skills/SKILL.md`, `testing-skills-with-subagents.md`):
"Writing skills IS Test-Driven Development applied to process documentation." RED = run a
pressure scenario with a subagent *without* the skill and record rationalizations verbatim;
GREEN = minimal skill; REFACTOR = close loopholes. Key empirical claims:
- A description that summarized the workflow ("code review between tasks") made an agent do
  ONE review instead of two; descriptions must state only triggering conditions. **[read]**
- "Match the Form to the Failure": prohibitions work for discipline failures; for
  wrong-shaped output use a positive recipe/contract; for omitted elements use a REQUIRED
  slot in a template. "In head-to-head wording tests … the prohibition arm produced clearly
  more of the unwanted content than the recipe arm … and trended worse than even the
  no-guidance control." Nuance clauses ("unless it matters") degraded a winning recipe from
  consistent to noisy. **[read]**
- Micro-tests: one fresh-context sample per call, always a no-guidance control, 5+ reps per
  variant, read every flagged match by hand; "Variance is a metric." **[read]**
- "Mechanical constraints (if it's enforceable with regex/validation, automate it—save
  documentation for judgment calls)." **[read]**

**diagnosing-superpowers** (`skills/diagnosing-superpowers/`): after-the-fact analysis of a
session transcript by seven parallel analyst subagents (skill timeline, plan adherence,
repeated work, stumbles, quality evidence, request conflicts, cost and time); "Every finding
cites `path:line`. No citation, no finding." Useful as a model for a NEXTRACK retro of an
agent-team run. **[read: SKILL.md and two analyst prompts]**

---

### 1.2 Anthropic engineering: the four guidance pieces

**(a) "Building effective agents"** — https://www.anthropic.com/engineering/building-effective-agents **[read]**
- Workflows = "LLMs and tools are orchestrated through predefined code paths"; agents =
  "LLMs dynamically direct their own processes and tool usage".
- *Orchestrator-workers*: a central LLM "dynamically breaks down tasks, delegates them to
  worker LLMs, and synthesizes their results"; subtasks "aren't pre-defined, but determined
  by the orchestrator based on the specific input".
- *Evaluator-optimizer*: "one LLM call generates a response while another provides
  evaluation and feedback in a loop". Two signs of fit: responses "can be demonstrably
  improved when a human articulates their feedback", and the LLM can provide such feedback.
- Principles: simplicity, transparency (show planning steps), and the agent-computer
  interface ("poka-yoke your tools": change arguments so mistakes are harder).
- Stopping: "include stopping conditions (such as a maximum number of iterations)"; agents
  "pause for human feedback at checkpoints or when encountering blockers"; get "ground truth"
  from the environment at each step. Autonomy means "higher costs, and the potential for
  compounding errors".

**(b) "How we built our multi-agent research system"** — https://www.anthropic.com/engineering/multi-agent-research-system **[read]**
- Lead agent plans and saves the plan to memory (context > 200k gets truncated); spawns
  3–5 subagents in parallel; each receives "an objective, an output format, guidance on the
  tools and sources to use, and clear task boundaries"; a CitationAgent post-processes.
- Numbers: multi-agent (Opus 4 lead, Sonnet 4 workers) "outperformed single-agent Claude
  Opus 4 by 90.2%" on their internal research eval; on BrowseComp token usage explained
  ~80% of performance variance; agents ≈ 4× chat tokens, multi-agent ≈ 15×.
- Failure modes observed: "spawning 50 subagents for simple queries", endless searching,
  subagents distracting each other, duplicated work from vague delegation, preference for
  SEO content farms (caught only by human testers).
- Effort scaling rules embedded in the lead prompt: simple = 1 agent, 3–10 tool calls;
  comparisons = 2–4 subagents, 10–15 calls each; complex = 10+ subagents with divided
  responsibilities.
- Does not fit when "all agents must share the same context or depend heavily on one
  another"; coding has fewer parallelizable subtasks.
- Evaluation: start with ~20 realistic queries ("small samples suffice when early effect
  sizes are large"); a single LLM-judge call outputting 0.0–1.0 scores and pass/fail matched
  humans best; "end-state evaluation rather than turn-by-turn analysis".
- Reliability: resume from failure instead of restarting; full tracing; synchronous
  subagent batches are a bottleneck but simpler.
- Context: "Subagents call tools to store their work in external systems, then pass
  lightweight references back to the coordinator" (avoids the game of telephone).
- "Small changes to the lead agent can unpredictably change how subagents behave";
  "instilling good heuristics rather than rigid rules".

**(c) "Effective context engineering for AI agents"** — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents **[read]**
- Context is "a finite resource with diminishing marginal returns" (attention budget,
  context rot). System prompts at the "right altitude".
- Minimal viable tool set ("If a human engineer can't definitively say which tool should be
  used in a given situation" the agent can't either).
- "Diverse, canonical examples" over laundry lists of edge cases.
- Hybrid retrieval: some data up front for speed (CLAUDE.md), the rest just in time
  (glob/grep).
- Long horizon: compaction (back-and-forth flow), structured note-taking such as a NOTES.md
  ("iterative development with clear milestones"), sub-agents returning "a condensed,
  distilled summary … (often 1,000-2,000 tokens)" (parallel exploration).

**(d) "Writing effective tools for agents"** — https://www.anthropic.com/engineering/writing-tools-for-agents **[read]**
- Prototype → evaluate with realistic, verifiable tasks → let Claude analyze concatenated
  eval transcripts and rewrite the tools; use held-out test sets to avoid overfitting.
- Track tool calls, tokens, runtime, tool errors. Consolidate tools; namespace them; return
  meaningful names, not ids; offer `response_format` concise/detailed; truncate by default
  (Claude Code caps tool responses at 25,000 tokens); error messages that state the fix.
- Relevance to NEXTRACK: the show tools already follow this (findings name the value and
  the fix; `path:line: rule-id: message`). This is the agent-computer interface.

---

### 1.3 Anthropic: generator–evaluator harnesses for long, subjective work

**(a) "Harness design for long-running application development"** (Prithvi Rajasekaran,
March 2026) — https://www.anthropic.com/engineering/harness-design-long-running-apps **[read]**

The single most relevant source for a creative critic loop.
- Roles: planner, generator, evaluator (GAN-inspired). Agents communicated through files:
  "one agent would write a file, another agent would read it and respond".
- Why a separate evaluator: agents "reliably skew positive when grading their own work";
  "Tuning a standalone evaluator to be skeptical turns out to be far more tractable" than
  making a generator self-critical. Caveat: the evaluator "is still an LLM that is inclined
  to be generous towards LLM-generated outputs".
- Subjective taste made gradable: four criteria (design quality, originality, craft,
  functionality); originality penalized "telltale signs of AI generation like purple
  gradients over white cards"; weighting design quality and originality above craft and
  functionality "pushed the model toward more aesthetic risk-taking".
- Calibration: "few-shot examples with detailed score breakdowns"; for QA, "Out of the box,
  Claude is a poor QA agent", tuned by reading logs and updating the prompt where its
  judgment diverged from the author's.
- Perception: the evaluator used Playwright MCP to interact with the live page "rather than
  scoring a static screenshot". (NEXTRACK's agents have no equivalent: they only read text
  views.)
- Sprint contracts: before each sprint the generator proposed what "done" meant and how to
  verify it, the evaluator reviewed until agreement (sprint 3 had 27 criteria).
- Iterations: 5–15 per generation; scores "improved over iterations before plateauing";
  "I regularly saw cases where I preferred a middle iteration over the last one."
- Cost: solo run 20 min / $9 with a broken result vs full harness 6 h / $200 ("over 20x
  more expensive"); later harness ≈ 4 h / $124.70.
- Simplification over time: "every component in a harness encodes an assumption about what
  the model can't do on its own"; sprints were removed with a newer model; the evaluator
  moved to a single end-of-run pass. "The evaluator … is worth the cost when the task sits
  beyond what the current model does reliably solo."

**(b) "Effective harnesses for long-running agents"** — https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents **[read]**
- Initializer agent (sets up environment, writes a feature list of 200+ features all marked
  failing, a `claude-progress.txt`, an `init.sh`) and a coding agent that makes incremental
  progress, one feature per session.
- Coding agents may only flip the `passes` field; "It is unacceptable to remove or edit
  tests because this could lead to missing or buggy functionality." JSON chosen because the
  model is less likely to overwrite it than Markdown.
- Failure modes: one-shotting (runs out of context mid-feature), declaring victory early,
  marking features done without end-to-end testing. Fix for the last: test "as a human user
  would" with browser automation.
- Start-of-session routine: `pwd`, read git log and progress file, pick the highest-priority
  undone feature, run `init.sh`, smoke-test before new work.

---

### 1.4 Claude Code orchestration primitives (official docs)

All **[read]** in this session unless marked.

**Subagents** — https://code.claude.com/docs/en/sub-agents
- Files in `.claude/agents/` (project, version-controlled) or `~/.claude/agents/`; markdown
  body = system prompt. Frontmatter: `name`, `description` (required), `tools`,
  `disallowedTools`, `model` (`sonnet|opus|haiku|fable|inherit|<id>`), `permissionMode`,
  `maxTurns`, `skills` (preloaded in full), `mcpServers`, `hooks`, `memory`
  (`user|project|local` → `.claude/agent-memory/<name>/MEMORY.md`, first 200 lines/25 KB
  loaded), `background`, `omitClaudeMd`, `effort`, `isolation: worktree`,
  `autoCompactWindow`, `color`, `initialPrompt`. Unrecognized fields are silently ignored;
  some malformed files are skipped silently (`claude plugin validate .claude/agents`).
- Context received: fresh context; its own system prompt (not Claude Code's); the delegation
  message; CLAUDE.md hierarchy (unless Explore/Plan or `omitClaudeMd`); git status;
  preloaded skills. Not the parent's history, invoked skills or files read. A *fork*
  inherits the whole conversation (cheaper via shared prompt cache, but drops isolation).
- Nesting up to 3 layers by default (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`); concurrent
  subagents capped at 20 (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`).
- Only the summary returns; transcripts at
  `~/.claude/projects/{project}/{session}/subagents/agent-{id}.jsonl`; resume via
  `SendMessage` to the agent id/name with history intact.
- Model resolution: per-invocation `model` → frontmatter → `CLAUDE_CODE_SUBAGENT_MODEL` →
  session model.
- Best practices: focused descriptions (combined description budget 15,000 tokens), limit
  tools, cheaper models for lookups, check project agents into git, "Keep iterative,
  multi-phase, or latency-sensitive work in the main conversation. A non-fork subagent
  starts cold."
- Example: a read-only `db-reader` whose `PreToolUse` hook exits 2 on write SQL — "the
  system prompt tells the subagent to refuse write requests, so the hook is a backstop".

**Skills** — https://code.claude.com/docs/en/skills
- `.claude/skills/<name>/SKILL.md` with supporting files loaded on demand; keep SKILL.md
  under 500 lines. Fields include `context: fork` + `agent` (run the skill as a task in a
  subagent), `allowed-tools`, `disallowed-tools`, `model`, `effort`, `hooks`, `paths`,
  `disable-model-invocation`, and `` !`command` `` dynamic context injection (output
  inlined before Claude sees the skill; a failing command aborts the skill).
- **Compaction limit (important for skill-as-orchestrator):** "after summarization, Claude
  Code re-attaches the most recent invocation of each skill, keeping the first 5,000 tokens
  of each", within a combined 25,000-token budget. A long rite loses its tail after
  compaction; the ledger and short references must carry the state.

**Hooks** — https://code.claude.com/docs/en/hooks
- Events include `PreToolUse`, `PostToolUse`, `SubagentStart`, `SubagentStop`, `Stop`,
  `TaskCreated`, `TaskCompleted`, `TeammateIdle`, `PreCompact`, `PostCompact`.
- `Stop`/`SubagentStop` can block stopping (exit 2 or `decision: "block"` + `reason`):
  a deterministic "you are not done" gate. `PreToolUse` returns `permissionDecision`
  `allow|deny|ask|defer`. Only exit 2 blocks (exit 1 does not). `type: "prompt"` and
  `type: "agent"` hooks let a model decide (agent hooks experimental). The `stop_hook_active`
  loop guard was in the part of the page I did not read **[recalled]**.

**Agent teams** (experimental, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) — https://code.claude.com/docs/en/agent-teams
- Lead + teammates (full Claude Code sessions), shared task list with dependencies and file
  locking, mailboxes, direct messaging, plan approval. Quality gates via `TeammateIdle`,
  `TaskCreated`, `TaskCompleted` hooks (exit 2 keeps working / rejects).
- Patterns: parallel review with distinct lenses; "competing hypotheses" where teammates try
  to disprove each other ("Sequential investigation suffers from anchoring").
- Limits: no session resumption of in-process teammates, task status can lag, one team per
  session, no nested teams, teammates start in the lead's permission mode, "The lead can stop
  early too". "Start with 3-5 teammates"; "Avoid file conflicts". Costs: "approximately 7x
  more tokens than standard sessions when teammates run in plan mode" (costs page).
- Messages from agents are never user consent ("A teammate can't approve a permission prompt
  or supply consent on your behalf").

**Dynamic workflows** (research preview) — https://code.claude.com/docs/en/workflows, plus
the bundled `workflow-authoring` reference loaded in this session, plus the blog
https://claude.dev/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code/
- A JavaScript script the runtime executes: `agent(prompt, {schema, model, effort,
  isolation, agentType, label, phase})`, `parallel()` (barrier), `pipeline()` (no barrier,
  the default), `phase()`, `log()`, `args`, `budget`, `workflow()` (one level of nesting).
  Intermediate results stay in script variables, not in Claude's context.
- Docs' comparison: subagents/skills/teams = "Claude, turn by turn" decides; workflows =
  "The script". Workflows are "Resumable in the same session" (longest unchanged prefix of
  `agent()` calls returns cached results; `Date.now()`/`Math.random()` throw to keep replays
  deterministic).
- Limits: "No mid-run user input … For sign-off between stages, run each stage as its own
  workflow"; up to 16 concurrent agents (min(16, CPUs − 2)); 1,000 agents per run; a
  `Large workflow` warning above 25 agents or 1.5M projected tokens; size guideline default
  `medium` (< 10 agents). Saved to `.claude/workflows/` and run as `/<name>`.
- Quality patterns (workflow-authoring): adversarial verify ("spawn N independent skeptics
  per finding, each prompted to REFUTE … Default to refuted=true if uncertain"),
  perspective-diverse verify, judge panel, loop-until-dry ("keep spawning finders until K
  consecutive rounds return nothing new"; dedup against *all seen*, not *confirmed*, "else
  judge-rejected findings reappear every round and it never converges"), multi-modal sweep,
  completeness critic, "No silent caps".
- The blog names the three failure modes of one-context orchestration: **agentic laziness**
  ("addressing 35 of the 50 items in a security review"), **self-preferential bias** ("prefer
  its own results or findings, especially when asked to verify or judge them against a
  rubric"), **goal drift** ("especially after compaction … 'don't do X' constraints can get
  lost"). Patterns: classify-and-act, fan-out-and-synthesize, adversarial verification,
  generate-and-filter, tournament, loop until done. "Comparative judgment is more reliable
  than absolute scoring." For taste tasks: "give a review agent a rubric. The task is
  complete when the review agent feels like it has met the criteria." No quantitative
  benchmarks; example runs 14 agents / 482k tokens (review) and 22 agents / 1.1M tokens
  (deep research). "Most traditional coding tasks do not need a panel of 5 reviewers";
  "parallelism and specialization have to earn their coordination cost". Workflows can ship
  inside a skill, framed "as a template instead of a script that needs to be run verbatim".

**Claude Agent SDK** — https://code.claude.com/docs/en/agent-sdk/overview and `/agent-loop`
- The same loop, tools, hooks, subagents, skills and CLAUDE.md as Claude Code, as a
  Python/TypeScript library (or `claude -p --output-format json`). Bounds: `max_turns`,
  `max_budget_usd` (covers subagents; may overshoot by one response), `effort`;
  `ResultMessage` carries `subtype` (`success`, `error_max_turns`, `error_max_budget_usd`,
  …), `total_cost_usd`, `num_turns`, `session_id`. Permission modes `default`,
  `acceptEdits`, `plan`, `dontAsk`, `auto`, `bypassPermissions`.
- Note: "Anthropic does not allow third party developers to offer claude.ai login or rate
  limits for their products"; an SDK program normally runs on an API key (per-token
  billing).
- The workflow blog's verdict: static harnesses built with the SDK or `claude -p` "need to
  work for all edge cases, they are usually more generic."

---

### 1.5 Measuring skills and agent teams: skill-creator, bmad-eval, "Demystifying evals"

**Anthropic `skill-creator`** — local copy
`~/.claude/skills/synced/…/skill-creator/` (`SKILL.md`, `agents/grader.md`,
`agents/comparator.md`, `agents/analyzer.md`, `scripts/run_loop.py`) **[read]**
- Loop: draft skill → 2–3 realistic test prompts saved as case folders (`evals/<case>/`
  with `prompt.md`, `case.yaml`, `graders/`, `files/`, the layout `claude plugin eval`
  reads) → for each case spawn **two subagents in the same turn**: with the skill and a
  baseline (no skill for a new skill; a snapshot of the old version when improving) →
  while they run, draft objectively verifiable assertions → capture `total_tokens` and
  `duration_ms` from each completion notification into `timing.json` ("the only
  opportunity") → grade (grader subagent; scripts for programmatic checks) →
  `aggregate_benchmark` (pass rate, time, tokens, mean ± stddev, delta) → analyst pass →
  HTML viewer for the human → read `feedback.json` → improve → `iteration-N+1/`.
- Stop: "The user says they're happy", "The feedback is all empty", or "You're not making
  meaningful progress".
- Grader: "A passing grade on a weak assertion is worse than useless"; PASS needs evidence of
  "genuine task completion, not just surface-level compliance"; "The burden of proof to pass
  is on the expectation"; also extracts and verifies implicit claims; critiques the evals.
- Blind comparator: two outputs labelled A/B without knowing which skill produced them;
  rubric generated per task (content + structure, 1–5); assertions are secondary evidence.
- Analyzer: flags assertions that always pass in both configurations (non-discriminating),
  always fail, high variance (flaky), and time/token trade-offs.
- Improvement advice: generalize from feedback rather than overfit the few examples; "Keep
  the prompt lean"; "Explain the why" instead of ALL-CAPS MUSTs; if every run rewrote the
  same helper, bundle it as a script.
- Description optimization (`run_loop.py`): 20 trigger queries (near-miss negatives), 60/40
  train/held-out split, each query run 3 times, up to 5 iterations, best description chosen
  by held-out score "to avoid overfitting".

**BMAD `bmad-eval`** — `docs/toolsmith/bmad-eval.md` in github.com/bmad-code-org/BMAD-METHOD **[read]**
- Four modes: baseline (beats the bare model?), variant (does a section earn its place?),
  quality (rubric), trigger. "A skill the bare model matches should be retired, not patched.
  The bare model improves with each release, so a baseline run is worth repeating."
- "Write rubric entries a wrong output cannot pass"; "Three runs per case is the floor";
  each case runs in a clean temp folder with a fresh home (no memory, settings or project
  instructions leak in); runs are never overwritten so history stays comparable; read
  transcripts: several attempts → vague instruction; same helper rewritten → bundle a script.

**"Demystifying evals for AI agents"** — https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents **[read]**
- Task / trial / grader / transcript / outcome. Code, model and human graders (human =
  gold, calibrates model graders). Capability evals (start low, hill to climb) vs regression
  evals (near 100%); capability tasks graduate into the regression suite. pass@k vs pass^k
  (consistency). "20-50 simple tasks drawn from real failures is a great start." "Grade what
  the agent produced, not the path it took." Subjective tasks: structured rubrics, one
  isolated judge per dimension, an "Unknown" escape hatch.

---

### 1.6 BMAD-METHOD (v6.12 stable, v7 preview)

**What it is.** A widely used (55k stars **[read]**) "agile AI-driven development" method
shipped as skills/plugins for Claude Code, Codex and others: persona agents (analyst, PM,
architect, UX, PO "Sofia", dev), a ticket tree, plans with machine-readable status, and
build/review skills. Repo: https://github.com/bmad-code-org/BMAD-METHOD (docs read through
`gh api`). Older versions had Scrum Master "Bob" writing "hyper-detailed" story files that
carry all context to the Dev agent, and QA "Quinn" **[read: search snippets]**; v6/v7 docs
center on `bmad-build`, `bmad-build-auto`, `bmad-code-review`. **[read]**

**Roles and artifacts.** Planning artifacts (PRD, architecture "spine", epics, tickets in
`tickets.toml` with `after` dependencies) → one *plan file* per ticket whose frontmatter
`status` is the orchestration state (`draft → ready-for-dev → in-progress → in-review →
built → done`, plus `blocked`, `dropped`), with `baseline_revision`, `risk`,
`followup_review_recommended`, `deferred` findings (summary, evidence, location, severity),
and an `Auto Run Result` section. "Build Auto never moves a ticket to `done`" (human or
orchestrator does). Checkpoint fields `plan_checkpoint` / `done_checkpoint` are honoured by
the orchestrator, not the worker. **[read: docs/build/autonomous-development-loops.md]**

**Critique.** `bmad-code-review`: several lenses review the same diff "independently and in
parallel"; then *triage* verifies each finding's claimed consequence, assigns severity from
the verified consequence, dismisses noise "with a recorded reason — never silently", and
routes survivors to **patch** (one clear fix), **defer** (pre-existing, never one this change
caused) or **decision needed** (several reasonable fixes; lists them and recommends one).
Depth `quick` (1 reviewer, default inside build loops) vs `thorough` (several lenses).
"Without intent, the reviewers can only judge the diff against itself" — the plan is passed
as intent; no-plan mode cannot tell a deliberate choice from a mistake. **[read:
docs/build/review-a-change.md]**

**Stopping / anti-churn.** "Stop when the findings are mostly low-value notes about exotic
corner cases. That is accidental complexity, not quality. Non-trivial findings on a third
pass of agentic review usually mean something is wrong upstream of this change: weak
internal design, a contradiction, or ambiguity in the rules. Fix that instead of running
another pass." **[read]**

**Subagent patterns** (`docs/toolsmith/subagent-patterns.md`) **[read]**:
- "Keep the Parent from Reading First" — "the most common failure. If the parent reads every
  file before starting subagents, the tokens are already spent". Tell the parent what to
  discover, not read; what each subagent returns; where its role ends.
- "Use Files as Shared State": the parent holds paths and a plan, not the data.
- Patterns: delegated reading, temp-file assembly, shared file pipeline, lead and workers,
  parallel perspectives, generate and select.
- "Make Perspectives Independent … Give each one the material and a strong persona or lens,
  not your conclusion. A reviewer handed your opinion tends to confirm it."
- "Always Provide a Fallback" (inline, one role at a time) and say so. "Start small."

---

## 2. Short entries

**wshobson/agents** — https://github.com/wshobson/agents **[read: README + agent-teams plugin files]**
Marketplace of 94 plugins / 202 agents / 185 skills / 105 commands, one source format adapted
to many harnesses. Its `agent-teams` plugin (`commands/team-review.md`) spawns one
`team-reviewer` teammate per dimension (security, performance, architecture, testing,
accessibility), then the lead deduplicates by file:line, takes the higher severity on
conflict, and reports by severity. No measured results; its own LLM-judge layer is "not
validated against human labels". Lesson: lens-per-reviewer + mechanical dedup; breadth of
agents is not evidence of quality.

**GitHub spec-kit** — https://github.com/github/spec-kit **[read: README +
templates/commands/converge.md]**
Commands `constitution → specify → (clarify) → plan → tasks → implement → converge`, plus
`analyze` and `checklist` **[recalled: what analyze/checklist do — cross-artifact
consistency and "unit tests for English"]**. `/converge` re-reads spec/plan/tasks "as the
sole source of intent", assesses the code ("completion claims are not evidence"), and is
APPEND-ONLY: it appends a `## Phase N: Convergence` of new tasks to `tasks.md` and must leave
`tasks.md` "byte-for-byte unchanged" when everything is satisfied. "Repeat implement and
converge until convergence reports `Converged`." The constitution is "non-negotiable"; a MUST
violation is the highest-severity finding. Lesson: an append-only gap list with a byte-exact
"no change" as the convergence signal.

**claude-flow / Ruflo** — https://github.com/ruvnet/claude-flow **[read: README]**
"Queen-led hierarchy", consensus protocols (Raft, Byzantine, Gossip), 98–100+ agents, 406
MCP tools, vector memory. Benchmarks are self-published (runtime speed, not task quality);
no SWE-bench-style quality evidence. Lesson: infrastructure complexity with no shown quality
gain; not a model to copy.

**Cognition, "Don't Build Multi-Agents"** (Walden Yan, 2025-06-12) — https://cognition.com/blog/dont-build-multi-agents **[read]**
"Share context, and share full agent traces, not just individual messages"; "Actions carry
implicit decisions, and conflicting decisions carry bad results" (Flappy Bird example:
two subagents produce a Mario-style background and a non-Flappy bird). Recommends a
single-threaded agent with a compression model for long contexts. Lesson for NEXTRACK:
parallel track writers make implicit style decisions; the director's contract (palette,
looks, story, arc) must be the shared context, and transitions need one owner.

**MAST, "Why Do Multi-Agent LLM Systems Fail?"** (Cemri, Pan et al., NeurIPS 2025) — https://arxiv.org/html/2503.13657v3 **[read]**
1,642 annotated traces; 14 failure modes in 3 groups. Largest: step repetition 15.7%,
reasoning-action mismatch 13.2%, unaware of termination conditions 12.4%, disobey task spec
11.8%, incorrect verification 9.1%, no/incomplete verification 8.2%, premature termination
6.2%. Interventions: better role specs +9.4% (ChatDev); adding a high-level task-objective
verification step +15.6%. "Systems with explicit verifiers … generally show fewer total
failures", but "the presence of a verifier is not a silver bullet"; "sole reliance on
final-stage, low-level checks is inadequate" → multi-level verification.

**Self-preference bias** — Panickssery, Bowman, Feng, "LLM Evaluators Recognize and Favor
Their Own Generations" (NeurIPS 2024) **[read: abstract]**. LLM evaluators score their own
outputs higher than humans would; GPT-4 recognizes its own text (73.5% in a 3-way test);
self-recognition correlates linearly with self-preference.

**Self-correction** — Kamoi et al., "When Can LLMs Actually Correct Their Own Mistakes?"
(TACL 2024) **[read: abstract]**: no prior work shows successful self-correction with
feedback from prompted LLMs in general tasks; self-correction "works well in tasks that can
use reliable external feedback". Huang et al., "Large Language Models Cannot Self-Correct
Reasoning Yet" (ICLR 2024) **[recalled]**: intrinsic self-correction often degrades
reasoning. Self-Refine (Madaan et al. 2023) **[recalled]**: same-model feedback loops improve
open-ended generation by human preference, with most gains in the first iterations.
Multi-agent debate (Du et al. 2023) **[recalled]**: several instances arguing improve
factuality. Net: critique helps most when anchored on external facts or a separate,
calibrated judge; pure self-critique is weak.

**LangGraph reflection** — https://github.com/langchain-ai/langgraph-reflection **[read]**
(archived 2026-04-01). Main agent → critique agent; loop ends when the critique returns no
messages; examples: LLM-as-judge and Pyright (deterministic) as the critic. No iteration
cap stated. LangGraph *supervisor* (a supervisor LLM routing to worker agents via handoff
tools) **[recalled]**.

**CrewAI hierarchical process** — https://docs.crewai.com/en/learn/hierarchical-process **[read]**
Agents with `role`, `goal`, `backstory`; `Process.hierarchical` adds a manager (`manager_llm`
or `manager_agent`) that "allocates tasks among crew members" and "evaluates outcomes to
ensure they meet the required standards". Sequential is the default.

**AutoGen AgentChat** — https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/termination.html **[read]**
Reflection = `RoundRobinGroupChat` of a primary and a critic; termination composed from
conditions, e.g. `MaxMessageTermination(10) | TextMentionTermination("APPROVE")`; also
`TokenUsageTermination`, `TimeoutTermination`, `HandoffTermination` (pause for a human),
`ExternalTermination`, `FunctionalTermination`. Lesson: always pair a judgment-based stop
("APPROVE") with a hard cap. `SelectorGroupChat` (LLM picks the next speaker) **[recalled]**.

**OpenAI Agents SDK** — https://openai.github.io/openai-agents-python/multi_agent/ **[read]**
Orchestration via LLM (agents-as-tools: a manager keeps control; handoffs: control moves to a
specialist) vs via code (structured outputs to route, chaining, a `while` loop where an
evaluator agent judges the task agent's output "until the evaluator says the output passes
the required criteria", parallel with `asyncio.gather`). Code orchestration is "more
predictable" in speed, cost and performance.

---

## 3. Answers to the six questions

### 3.1 Skill-as-orchestrator vs scripted workflow vs SDK program

| | Skill as orchestrator (main session follows a rite) | Scripted workflow (Claude Code dynamic workflow) | SDK program (Agent SDK / `claude -p`) |
|---|---|---|---|
| Who decides next step | The model, turn by turn, guided by the rite | The script (deterministic control flow) | Your code |
| State | Ledger files + git (context is lossy) | Script variables; runtime journal; resumable by cached prefix | Your program; sessions resumable by id |
| Human in loop | Natural: same session, can ask, owner can steer | None mid-run ("run each stage as its own workflow" for sign-off) | Only what you build (`canUseTool`, hooks) |
| Scale | A few delegations per turn; 20 concurrent subagents | Dozens–hundreds of agents; 16 concurrent | Unbounded, your infra |
| Repeatable | The instructions | The orchestration itself (`.claude/workflows/`) | The program |
| Billing | Subscription | Subscription (counts toward limits) | Normally API key |

**When each fits.**
- *Skill rite*: iterative loops that need judgment between steps, rulings, and an owner who
  may look in; tasks with sequential dependencies (SDD: "Keep iterative, multi-phase … work
  in the main conversation" — subagent docs). Evidence: SDD runs whole plans this way. **[read]**
- *Workflow*: one well-scoped fan-out with a fixed shape: N independent items × same
  stages, adversarial verification, judge panels, loop-until-dry, tournaments. "Reach for a
  workflow when a task needs more agents than one conversation can coordinate, or when you
  want the orchestration codified." The workflow-authoring reference recommends a *hybrid*:
  scout inline, then call a workflow per phase, "You stay in the loop; each workflow is one
  well-scoped fan-out." **[read]**
- *SDK program*: unattended, scheduled or CI runs (regression evals of the team, nightly
  re-critique), hard budget caps (`max_budget_usd`), custom permission callbacks. The
  workflow blog calls static SDK harnesses "usually more generic". **[read]**

**Failure modes.**
- *Skill rite*: context fills; after compaction the skill body is re-attached only up to
  5,000 tokens (skills docs) and conversation memory is lost — controllers "re-dispatched
  entire completed task sequences" (SDD); goal drift and dropped "don't do X" constraints
  (workflow blog); agentic laziness (35/50 items); self-preferential bias if the controller
  judges its own work; the controller "fixes it myself" and skips review (SDD
  rationalization table); the description summarizing the workflow makes agents follow the
  description, not the body (writing-skills). Mitigations: ledger with identity line, short
  SKILL.md with references, scripts for bookkeeping, explicit per-role prompts as files.
- *Workflow*: no mid-run input; a failed agent mid-fan-out reruns everything started after
  it on resume; schema-validation retries; cost spikes (warning at > 25 agents / 1.5M
  tokens); barrier latency if `parallel()` is used where `pipeline()` would do; research
  preview (subject to change); the script's quality pattern is only as good as the prompts;
  non-converging loops if dedup is against "confirmed" instead of "seen". **[read]**
- *SDK program*: you own auth, permissions (`dontAsk`/`bypassPermissions` risks), retries,
  observability; budget cap can overshoot by one response; no interactive steering; a
  generic static harness under-fits each new task. **[read]**

### 3.2 Roles: definition, context received, handoffs

- **Definition.** Claude Code: `.claude/agents/<role>.md` (prompt + tools + model +
  permissions + hooks + memory) or prompt templates inside a skill folder dispatched to
  `general-purpose` (SDD, skill-creator `agents/*.md`, diagnosing `prompts/*.md`). BMAD:
  persona skills (`bmad-agent-*`) with `customize.toml`. CrewAI: role/goal/backstory. MAST:
  better role specs alone +9.4%. **[read]**
- **Context received.** Converging practice: the task brief file, the binding constraints
  verbatim, paths to inputs, an output contract — never the orchestrator's history (SDD,
  requesting-code-review, multi-agent research: "objective, output format, tools and
  sources, clear task boundaries"). CLAUDE.md loads automatically in subagents and workflow
  agents ("don't tell them to re-read those"); Explore/Plan skip it. Context engineering:
  just-in-time file reads over pasted dumps. **[read]**
- **Handoffs.** Files with fixed names and formats, short status replies:
  SDD (brief → report file + 15-line status → review package → findings verbatim →
  appended fix reports → ledger lines); BMAD (plan file with frontmatter status, `deferred`
  entries, `## Code Review` dated blocks); Anthropic long-running harness (feature JSON with
  `passes`, progress txt, git commits); harness-design (agents write and read files; sprint
  contracts); workflows (JSON via `schema`). Severity-tagged findings with location
  (`file:line`) everywhere. **[read]**

### 3.3 Keeping the critic independent, and whether it matters

Techniques (all **[read]**):
1. **Fresh context, no author history**: SDD, requesting-code-review, subagent defaults.
2. **No author rationale as evidence**: "Do Not Trust the Report"; rationales "never downgrade
   a finding's severity" (SDD).
3. **No orchestrator pre-judgment**: ban on "do not flag … the plan chose" (SDD); "Give each
   one the material and a strong persona or lens, not your conclusion. A reviewer handed your
   opinion tends to confirm it" (BMAD).
4. **But give intent**: "Without intent, the reviewers can only judge the diff against
   itself" (BMAD). Intent (spec, goals, rubric) ≠ rationale (why I did X).
5. **Adversarial framing**: refuters defaulting to "refuted" (workflow-authoring); teammates
   disproving each other (agent teams); "someone trying to break the work" persona (BMAD).
6. **Diverse lenses over identical reviewers**: "diversity catches failure modes redundancy
   can't" (workflow-authoring); lens-per-reviewer (wshobson, BMAD thorough).
7. **Blind comparison**: A/B without knowing which produced which (skill-creator
   comparator).
8. **Separate model or tier** for review/judgment (SDD final review on the most capable
   model; BMAD lenses "run some on another model").
9. **Calibration**: few-shot score breakdowns, read logs and fix divergence from human
   judgment (harness-design); calibrate LLM graders against humans (demystifying evals).

Evidence it matters:
- Self-preference: LLM judges favor their own generations, linked to self-recognition
  (Panickssery et al.) **[read: abstract]**; "agents reliably skew positive when grading their
  own work" (harness-design) **[read]**; "self-preferential bias" named as a failure mode of
  one-context orchestration (workflow blog) **[read]**.
- Intrinsic self-correction rarely works without reliable external feedback (Kamoi et al.)
  **[read: abstract]**.
- Explicit verifiers reduce failures; a task-objective verification step +15.6% (MAST),
  but verifiers are "not a silver bullet". **[read]**
- Anchoring: "once one theory is explored, subsequent investigation is biased toward it"
  (agent teams). **[read]**
- Counter-evidence/limits: even a separate evaluator "is still an LLM that is inclined to be
  generous" (harness-design); a critic without perception ("poor QA agent out of the box")
  needs tuning; independence alone does not make the judge right. **[read]**

### 3.4 State between iterations; stopping; avoiding churn

**State.** Files + git, never conversation memory: SDD ledger (`progress.md`, identity first
line, per-task completion lines, fix-round lines, rulings, deferred minors), BMAD plan
frontmatter status, Anthropic `claude-progress.txt` + feature JSON + git, NOTES.md
(context engineering), skill-creator `iteration-N/` folders with `benchmark.json` and
`feedback.json`, workflow journals. **[read]**

**Stopping criteria found.**
- Gate passes: review clean (SDD), `Converged` / byte-identical `tasks.md` (spec-kit),
  critique returns nothing (LangGraph reflection), "APPROVE" (AutoGen), evaluator says
  criteria pass (OpenAI SDK), rubric met (workflow blog). **[read]**
- Hard caps: 5 fix rounds then adjudication (SDD); one final fix wave (SDD);
  `MaxMessageTermination`, `max_turns`, `max_budget_usd`, `budget.total`, 1,000 agents.
  **[read]**
- Discovery convergence: loop until K consecutive rounds find nothing new; "two rounds in a
  row make no progress" (workflows docs). **[read]**
- Diminishing value: stop when findings are "mostly low-value notes about exotic corner
  cases"; a third non-trivial pass means an upstream problem (BMAD). "You're not making
  meaningful progress" (skill-creator). **[read]**
- Plateau/regression: scores plateau; a middle iteration was sometimes better than the last
  (harness-design) → keep all iterations and pick, don't assume last = best. **[read]**

**Anti-churn devices.** Minor findings never loop (SDD); scoped re-reviews cannot wander;
out-of-scope observations go to a ledger; dedup against everything already seen; one fix
dispatch for many findings; append-only gap lists; "Never ignore an escalation or force the
same model to retry without changes"; escalate model at round 4; triage that dismisses
unsubstantiated findings with a recorded reason (BMAD); grader burden of proof on PASS.
MAST shows why: step repetition (15.7%) and unawareness of termination (12.4%) are the
most frequent failure modes. **[read]**

### 3.5 Cost, parallelism, human checkpoints, permissions

- **Cost evidence**: multi-agent ≈ 15× chat tokens, single agent ≈ 4×; tokens explain ~80% of
  research quality variance (multi-agent research); harness 20× the cost of a solo run but
  solo was broken (harness-design); agent teams ≈ 7× in plan mode (costs docs); workflow
  warning at 25 agents / 1.5M tokens; example workflow runs 482k–1.1M tokens. **[read]**
- **Controls**: explicit model per dispatch, cheap tiers for mechanical work, mid tier floor
  for reviewers (SDD); `effort` per agent; size guideline; `budget` in scripts;
  `max_budget_usd`; small slice first ("run the workflow on a small slice first"); batch
  same-shape work; files instead of pasted context; prompt-cache sharing in fan-outs;
  shut down teammates. **[read]**
- **Parallelism limits**: 20 concurrent subagents; 16 per workflow; 3–5 teammates; 3–5
  parallel research subagents; never parallel writers on shared files (SDD, agent teams,
  dispatching-parallel-agents); worktree isolation for parallel writers (expensive). **[read]**
- **Human checkpoints**: SDD's four stop classes + "Rulings I made" at the end; BMAD
  `plan_checkpoint`/`done_checkpoint` honoured by the orchestrator, and "Build Auto never
  moves a ticket to done"; brainstorming HARD-GATE before building; agent-team plan approval;
  workflows ask approval per permission mode and cannot pause for input. **[read]**
- **Permissions**: least-privilege `tools`/`disallowedTools` per role; `PreToolUse` hooks
  as a deterministic backstop ("the hook is a backstop" for a prompt rule); messages from
  other agents are never user consent; workflow agents' prompts are "text the script
  computed", not user requests, for the auto-mode classifier; SDK `dontAsk` for headless.
  **[read]**

### 3.6 Measuring whether a skill or team got better

- Baseline vs with-skill (or old vs new) on the same cases, run in parallel, several runs
  per case (≥ 3), pass rate + tokens + time with mean ± stddev (skill-creator, bmad-eval).
  **[read]**
- Assertions a wrong output cannot pass; graders with burden of proof on PASS; analyst pass
  to drop non-discriminating assertions; flaky = high variance. **[read]**
- Blind pairwise comparison for subjective quality (skill-creator comparator;
  "comparative judgment is more reliable than absolute scoring", workflow blog). **[read]**
- Capability set from real failures (20–50 tasks) that graduates into a regression set kept
  near 100%; pass^k when consistency matters; calibrate LLM judges against human labels;
  read transcripts, not just scores (demystifying evals, BMAD). **[read]**
- Held-out sets to avoid overfitting to the cases you iterate on (writing-tools, skill-creator
  description loop). **[read]**
- Retire what the bare model already does (bmad-eval) and remove harness components as models
  improve (harness-design). **[read]**
- Process metrics from transcripts: repeated work, re-dispatches, stumbles, cost per turn
  (diagnosing-superpowers analysts; MAST taxonomy as a labelling scheme). **[read]**

---

## 4. The architecture question: analyses precomputed or run on demand

Evidence from the sources, applied to NEXTRACK:
- Context engineering recommends a **hybrid**: data that every step needs and that is stable
  goes up front or into files; the rest is fetched just in time with cheap tools. **[read]**
- Deterministic facts should come from tools, not agents: self-correction works with
  "reliable external feedback" (Kamoi); "if it's enforceable with regex/validation,
  automate it" (writing-skills); ground truth from the environment (building effective
  agents); the critic spec's own anti-goal "Opinions dressed as facts" and "Drift". **[read]**
- Handing artifacts over as files and returning references avoids the game of telephone
  (multi-agent research, SDD, BMAD "files as shared state"). **[read]**
- Size check **[measured]**: `nextrack_show.py report hi-ibiza-pulso` prints 370 lines,
  ~51 KB (roughly 13k tokens) for the whole 44-minute night, including the 23
  `show-advice: bridges` lines. A whole-night critic can read it in one context; a per-track
  critic needs only its slice plus the neighbours' transitions.

Reading: **precompute the heavy, slow, audio-dependent analyses (musical maps) once per
track as committed inputs** (they need `uv sync --group analysis`, audio and rekordbox, not
available to every agent and not in CI), and **let agents run the cheap deterministic views
(`build`, `report`, `zoom`, `vocab`) just in time** after every edit, because those views
change with the show. Subagents should never "compute" a fact an existing tool computes; a
subagent on demand is for judgment (critique, design) or for a new analysis that does not
exist yet (then it becomes a tool with a test, like a gesture). Cache report outputs per
iteration in the run workspace so the critic and director read the same bytes.

---

## 5. Patterns that transfer to NEXTRACK

Roles assumed from the critic spec: a **director** (theme, night arc, `show.yml`), **track
writers** (one track file each), a **critic**, an **effects agent** (new gestures: code +
tests). Each pattern names its backing source.

1. **The director is a controller following a written rite (project skill), not a workflow.**
   The night loop is sequential and judgment-heavy (arc → tracks → critique → rulings), and
   the owner may look in. Put the rite in `.claude/skills/<show-team>/SKILL.md` (short, < 500
   lines, references for details) and the roles in `.claude/agents/*.md`. Backing: SDD; Claude
   Code docs ("Keep iterative, multi-phase … work in the main conversation"; skills vs
   subagents); building effective agents (start simple).

2. **A run workspace and ledger that survive compaction.** One folder per run (git-ignored,
   like `.superpowers/sdd/<plan>/`) with `ledger.md` whose first line names the show and
   goal; lines for each track's state, each critique round, each ruling (`Ruling: what —
   why — cost if wrong`), deferred minors. Resume from the ledger and `git log`, never from
   memory; the skill body after compaction keeps only 5,000 tokens. Backing: SDD; effective
   harnesses (progress file + git); skills docs (compaction re-attach limit).

3. **Briefs and reports as files; short replies.** The director writes a per-track brief
   (the track's role in the arc, energy target, looks allowed, neighbours' handover/bridge,
   the map path) with exact values only in the brief; the writer writes a report file and
   returns ≤ 15 lines (status, files changed, `build` result, concerns). Never paste the
   night's history into a dispatch. The director lists, it does not read ahead: "Keep the
   Parent from Reading First". Backing: SDD; BMAD subagent patterns; multi-agent research.

4. **Facts are tools, judgment is agents.** `build`, `report`, `zoom`, rules, advice and
   `check_repo.py` are the gates and the senses; no agent re-derives a number. The critic
   judges only what the manual lists under "left to judgment". A new kind of fact the critic
   needs becomes a tested function in `show_views.py`, not a prompt. Backing: Kamoi
   (external feedback); writing-skills ("automate it"); building effective agents (ground
   truth); the critic spec's anti-goals.

5. **An independent critic with intent but without rationale.** Fresh subagent, read-only
   (`tools: Read, Grep, Glob, Bash` with a `PreToolUse` hook allowing only
   `nextrack_show.py report|zoom|vocab` and `nextrack_map.py show`), on the most capable
   model. It receives: the show path, the night's `story` and plan (intent), the owner's four
   criteria as a rubric, the report/zoom outputs (files). It does not receive the director's
   or writers' reasoning, and the dispatch never says what not to flag. Treat writers'
   reports as claims. Backing: SDD; BMAD ("not your conclusion"; "without intent…");
   harness-design; Panickssery.

6. **Make the owner's four criteria gradable and weighted, then calibrate.** One
   criterion per lens, each tied to report evidence: *not monotonous* → minutes per
   look/colour/aim, repeated arrivals, strips that stay flat; *immersive at the drops* → peak
   table (light before → at), hit checks (kick on the hit, dark before); *follows each track's
   energy* → music vs light strips per track; *follows the set's energy* → the light-level
   arc across legs vs the music's. Weight the two the owner fears most (monotony, drops)
   above craft, as harness-design weighted originality to push away from safe, generic
   output. Calibrate with few-shot examples from the owner's room feedback (the backlog of
   project 3) and allow "unknown" when a `~` hides the level. Backing: harness-design;
   demystifying evals (one judge per dimension, Unknown escape hatch).

7. **Findings with severity, evidence and a route.** Each critic finding cites the report
   line or bar (`Track · bar · view`), a severity (Critical / Important / Minor), and a route:
   *patch* (one clear fix: send to the track writer), *decision needed* (several good fixes:
   the director rules and ledgers it), *defer* (pre-existing, outside this goal). Minor never
   loops. Backing: SDD; BMAD triage; diagnosing-superpowers ("No citation, no finding").

8. **A capped fix loop with scoped re-critique.** Per track: up to 3 rounds resuming the same
   writer, then a fresh writer on a stronger model, cap 5, then the director adjudicates and
   ledgers. Re-critique judges only the open findings and the changed bars (from a
   before/after report diff); new observations elsewhere go to the ledger, not the loop.
   Whole night: one final critique, one fix wave, one scoped re-critique, no second wave.
   Backing: SDD; MAST (step repetition, termination unawareness).

9. **Stop on convergence, not on fatigue.** Done when (a) `build` and `check_repo` are clean,
   (b) the advice targeted by the goal holds, (c) the critic has no Critical/Important
   finding, or two consecutive rounds bring nothing new, or the cap is hit. A non-trivial
   finding on a third pass means an upstream problem (the arc, a look, a missing gesture):
   go up a level instead of looping. Backing: workflow-authoring (loop-until-dry); BMAD
   (third pass); skill-creator (no meaningful progress); AutoGen (judgment stop OR cap).

10. **Keep every iteration as a variant and choose by blind pairwise comparison.** Build each
    candidate with `build --out <workspace>/iter-N`; at the end a fresh judge compares the
    best two report excerpts A/B without labels, against the rubric. The last iteration is
    not assumed best. Backing: harness-design ("preferred a middle iteration");
    skill-creator comparator; workflow blog (comparative judgment).

11. **Parallel only where nothing is shared.** `show.yml` belongs to the director only.
    Track writers can run in parallel only on tracks whose handover/bridge pairs do not touch
    each other; a transition (outgoing handover + incoming bridge) has one owner. Exploration
    of alternatives runs in parallel safely as `--out` variants in separate folders. 3–5
    concurrent agents is the practical range. Backing: SDD (never parallel implementers);
    agent teams ("Avoid file conflicts", 3–5); Cognition (implicit decisions conflict);
    dispatching-parallel-agents.

12. **Gestures are software: run them through SDD as-is.** When the critic or a writer finds
    the vocabulary lacks a word, the director writes a mini-spec (name, params, example, what
    the room should feel), and an effects implementer follows CLAUDE.md's "Add a gesture"
    checklist with TDD; a task reviewer checks spec + quality; the gesture enters the
    vocabulary only after review. Backing: SDD; CLAUDE.md change checklists; writing-tools
    (prototype, evaluate, refine).

13. **A builder check on the night design before any track is written.** A fresh agent reads
    the director's arc/plan and lists only the questions it would have to guess where a wrong
    guess matters; the director answers, marks its own calls, and sends only the owner's
    questions to the backlog. Backing: brainstorming builder-check; harness-design sprint
    contracts (agree "done" before building).

14. **Batch same-shape work.** The first task (23 bridge advice lines) is about a dozen
    transitions, each flagged twice (handover and bridge), and the advice already names the
    fix (`end the handover by bar 161`, `start a cue … at or before bar 18`). One dispatch per
    transition or a batch for the mechanical ones, then one critique of the whole night
    focused on "story preserved": moments and arrivals unchanged, minutes per look within a
    tolerance, peaks and hit checks not worse. Make the "story preserved" part a
    deterministic before/after diff of report sections where possible. Backing: SDD (batch
    small same-shape work); spec-kit (completion claims are not evidence).

15. **Explicit model and effort per role.** Director and critic: most capable model. Track
    writers: mid tier (they work from prose). Mechanical trims: cheapest tier, low effort.
    Never let a dispatch inherit by accident. Backing: SDD model selection; multi-agent
    research (Opus lead, Sonnet workers); costs docs.

16. **Human checkpoints only where they matter, enforced by hooks.** The run never asks
    "continue?"; it stops only for SDD's four classes. `nextrack_lights.py apply` is denied
    by a `PreToolUse` hook (not just a prompt rule), merges/pushes stay the owner's, and the
    end report lists every ruling with its cost if wrong, plus what to test in the room.
    Backing: SDD; hooks docs; subagent docs (hook as backstop); agent-team docs (agent
    messages are not consent).

17. **Measure the team with a small regression set, baseline runs and owner calibration.**
    Cases: Hï Ibiza's bridge task, a monotony case, a weak-drop case, a "new gesture needed"
    case, each with a frozen show snapshot. Graders: code (rules/advice counts, report-metric
    deltas, `check_repo`, tests), model (rubric judge per criterion, calibrated), human (the
    owner's room verdict as gold). Run with and without the team skill (or old vs new), ≥ 3
    runs per case, record tokens and minutes per run, never overwrite results. Retire any role
    or step the bare model matches. Backing: skill-creator; bmad-eval; demystifying evals;
    harness-design (remove components as models improve).

18. **Use a dynamic workflow only for a fixed-shape fan-out inside the rite.** Good fits: one
    critic lens per criterion over the whole night, then adversarially verify each finding
    (refuters default to "refuted"); generate three arc variants and run a tournament;
    critique all 15 tracks in a `pipeline()`. Each is one well-scoped workflow the director
    launches and reads; sign-off happens between workflows. Backing: workflows docs and
    workflow-authoring (hybrid; no mid-run input); workflow blog (patterns).

19. **Retro from transcripts.** After each run, analyst subagents read the session and
    subagent transcripts for repeated work, re-dispatches, stumbles and cost hot spots, and
    propose skill edits, each tested RED/GREEN before it lands. Backing:
    diagnosing-superpowers; writing-skills; writing-tools ("let Claude analyze transcripts").

---

## 6. What does not transfer (and why)

- **Ground truth by tests or a browser.** In code, tests and Playwright give the critic
  external feedback on the *goal*. For lights, the goal (immersion, monotony) has no oracle:
  the agents cannot see or hear the room, and the owner's test comes only at the end. The
  text views are proxies (the light level is "an index … never lux"). So critic verdicts on
  feel are uncalibrated until owner feedback accumulates; treat them as hypotheses, keep the
  hard gates for facts, and expect harness-design's warning ("inclined to be generous") to
  apply more, not less. (harness-design, Kamoi, the critic spec)
- **Spec-compliance review as the main lens.** SDD's reviewer asks "missing / extra /
  misunderstood" against a spec with exact values. A night has a story, not acceptance
  criteria; most findings are taste. The structure (fresh reviewer, severities, capped loop)
  transfers; the rubric does not.
- **Agent teams as the backbone.** Experimental, no resume for in-process teammates, task
  status lag, lead can stop early, teammates inherit the lead's permission mode, ~7× tokens.
  The show has shared state (`show.yml`, transitions) and sequential dependencies, the case
  the docs say subagents or one session handle better. (agent-teams docs)
- **Wide parallel breadth à la research systems.** The 90% gain came from breadth-first
  search on independent sub-questions; a night is coupled (Cognition's Flappy Bird). Parallel
  writers without a strong shared contract produce an incoherent night.
- **Heavy frameworks and personas.** claude-flow's consensus hierarchies, BMAD's full agile
  ceremony (PRD, epics, sprint planning, scrum roles), wshobson's 200-agent catalogue: built
  for software teams and large codebases; for one owner, one night, ~15 tracks, they add
  coordination cost with no shown quality gain. Borrow BMAD's triage and stop rule, not its
  ceremony.
- **An SDK program now.** It means API-key billing, your own permission handling, no live
  steering, and a "more generic" static harness; the owner works in Claude Code sessions on a
  subscription. Revisit for unattended regression evals or nightly re-critique (`claude -p`
  with `--max-budget-usd`).
- **Exhaustive "ultracode" defaults.** "Token cost is not a constraint" fits audits; here
  most edits are small YAML changes and the budget should scale with the goal (a bridge trim
  needs no five-reviewer panel). (workflow blog: "most traditional coding tasks do not need a
  panel of 5 reviewers")
- **Description-trigger optimization.** Valuable for skills that must fire on their own;
  the show-team roles are dispatched explicitly by the rite, so trigger evals matter only for
  the one entry skill.
- **The existing `lightshow` skill's gate.** It requires the owner's approval of a pt-BR
  proposal per track before writing (`.claude/skills/lightshow/SKILL.md`, step 4). That
  conflicts with end-to-end autonomy; the new rite should replace the per-track approval with
  the end-of-run report and the room test, while keeping its hard rule that writing into
  SoundSwitch is the owner's call. **[read]**
- **"Last iteration wins" and "more rounds converge".** Both are contradicted by the
  evidence (middle iterations preferred; past the cap rounds don't converge); do not build
  them in.

---

### Source index

Local **[read]**: superpowers 7.0.0 skills at
`~/.claude/plugins/cache/claude-plugins-official/superpowers/7.0.0/skills/`
(subagent-driven-development and its prompts and scripts, requesting-code-review,
brainstorming + builder-check-prompt, dispatching-parallel-agents, writing-skills +
testing-skills-with-subagents, diagnosing-superpowers); skill-creator at
`the bundled skill-creator skill (anthropics/skills) `;
the bundled `workflow-authoring` reference; NEXTRACK `lightshows/shows/README.md`,
`docs/superpowers/specs/2026-11-06-show-critic-design.md` (sections Why, Goals, Advice),
`.claude/skills/lightshow/SKILL.md` (head).

Web **[read]**: anthropic.com/engineering/{building-effective-agents,
multi-agent-research-system, effective-context-engineering-for-ai-agents,
writing-tools-for-agents, harness-design-long-running-apps,
effective-harnesses-for-long-running-agents, demystifying-evals-for-ai-agents};
code.claude.com/docs/en/{sub-agents, skills, hooks, agent-teams, workflows, costs,
agent-sdk/overview, agent-sdk/agent-loop}; claude.dev/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code;
github.com/bmad-code-org/BMAD-METHOD (README, docs/build/review-a-change.md,
docs/build/autonomous-development-loops.md, docs/toolsmith/subagent-patterns.md,
docs/toolsmith/bmad-eval.md); github.com/wshobson/agents (README,
plugins/agent-teams/commands/team-review.md, skills/multi-reviewer-patterns/SKILL.md);
github.com/github/spec-kit (README, templates/commands/converge.md); github.com/ruvnet/claude-flow;
cognition.com/blog/dont-build-multi-agents; arxiv.org/html/2503.13657v3 (MAST);
github.com/langchain-ai/langgraph-reflection; docs.crewai.com hierarchical process;
AutoGen termination tutorial; openai.github.io/openai-agents-python/multi_agent/.

Web **[read: abstract]**: Panickssery et al. 2024 (arXiv 2404.13076); Kamoi et al. 2024
(arXiv 2406.01297). **[recalled]**: Huang et al. 2024; Self-Refine; multi-agent debate;
LangGraph supervisor; AutoGen SelectorGroupChat; spec-kit analyze/checklist details;
`stop_hook_active`.

**[measured]**: `uv run --no-sync scripts/nextrack_show.py report hi-ibiza-pulso` (read-only;
working tree unchanged): 370 lines, 50,895 bytes, 23 `show-advice` lines.
