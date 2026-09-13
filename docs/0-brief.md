# Research Execution Brief: Online Progress and Stagnation in Coding Agents

**Working domain:** Coding-agent reliability / software-engineering agents  
**Target:** S.-T. Yau High School Science Award (Computer Science), Mainland China, 2026  
**Submission deadline:** 2026-09-15  
**Research style:** Small, empirical, data-first, technically defensible, high practical relevance  
**Priority:** Strong evidence and a clean research result > complicated implementation > long paper

---

## 0. Read This First: Academic-Integrity Constraint

This project is for the S.-T. Yau High School Science Award. The 2026 rules explicitly state that AI may be used as an **assistant rather than a substitute**. AI may help with literature-search leads, debugging, data-analysis assistance, structural organization, language polishing, and draft figures, but the student must personally perform the central topic conception, research design, core argument, experimental validation, and substantive academic expression. Direct AI ghostwriting of the main paper is prohibited, AI use must be disclosed, and relevant AI chat records must be submitted.

Official rules:

- https://www.yau-awards.com/show-86-59.html
- https://www.yau-awards.com/page-rule.html

Therefore, if you are an autonomous coding/research agent receiving this file:

1. **Do not fabricate data, citations, experiments, or claims.**
2. **Do not silently decide the final scientific claim.** Explore alternatives and present evidence.
3. You may autonomously perform literature retrieval, coding, dataset preparation, exploratory analysis, experiment execution, statistical analysis, figure generation, and drafting of notes/structures.
4. For any major research-design fork, record:
   - alternatives considered,
   - evidence for each,
   - what you chose provisionally,
   - why,
   - what would falsify that choice.
5. Produce a **research package and paper scaffold**, not a falsely human-authored final submission. The student must inspect raw results, make the final scientific decisions, independently verify the experiments, and write/rewrite the substantive final report.
6. Keep a complete `AI_ASSISTANCE_LOG.md` recording what you did, because the competition requires AI-use disclosure.

This is not bureaucracy. It also improves the research: every claim should be traceable to data or literature.

---

# 1. Starting Point

The motivating phenomenon is simple:

> Coding agents can remain computationally active for a long time while accomplishing little or nothing useful.

They may continue:

- searching,
- reading files,
- editing,
- reverting,
- invoking tools,
- testing,
- generating tokens,
- or exploring new directions,

while actual task progress has stalled.

The naive version of the research question was:

> Can we detect when a coding agent is working but making no actual progress, using changes in external program state rather than the agent's own language or repeated commands?

**Do not lock onto that formulation.** It contains an unproven assumption: that external program state is the best definition or signal of progress.

A coding agent can make substantial progress without modifying a file: locating the correct subsystem, eliminating a hypothesis, discovering the root cause, or learning which test is relevant. Conversely, it can modify many files while moving in the wrong direction.

The deeper object of study is therefore **progress in a task-directed trajectory**, not file change.

---

# 2. North-Star Research Question

Treat this as a starting research program, not a fixed title:

> **Can we determine online, without knowing the correct solution in advance, whether a coding agent's recent computation is still producing meaningful task-relevant progress?**

A more operational version:

> **Can a lightweight, reference-free monitor distinguish productive coding-agent activity from stagnation using only the task specification and the trajectory observed so far, while keeping false interruptions very low?**

Potential research questions:

### RQ1 — Detectability
Can coding-agent stagnation be detected from a trajectory prefix without access to the gold patch, future actions, hidden tests, hidden model states, or final outcome?

### RQ2 — Signal value
Which observable signals carry the most information about stagnation?

Candidate families include:

- exact action repetition,
- semantic redundancy,
- newly acquired task-relevant evidence,
- verification/test changes,
- persistent workspace changes,
- reversions/regressions,
- breadth or localization of exploration,
- error-state changes,
- action diversity,
- phase-specific behavior,
- completion-verifier score,
- or combinations of these.

### RQ3 — Operational value
Can a stagnation monitor save meaningful steps/tokens/time while preserving productive or ultimately successful trajectories?

### Optional RQ4 — Generalization
Does a monitor learned/tuned on one agent/model/scaffold transfer to others?

**Do not attempt all four unless the data makes them cheap.** A clean RQ1–RQ3 study is enough.

---

# 3. Core Concept to Explore: Marginal Task-Relevant Progress

One promising conceptual distinction is between **completion** and **marginal progress**.

Let the observed prefix through step \(t\) be:

\[
\tau_{\le t} = \{x, a_1,o_1,\ldots,a_t,o_t,s_t\}
\]

where:

- \(x\) = task specification,
- \(a_t\) = action/tool call,
- \(o_t\) = observation/tool output,
- \(s_t\) = observable environment/workspace state.

A completion verifier asks roughly:

\[
C_t = P(\text{task is already solved} \mid \tau_{\le t})
\]

But a stagnation monitor may care more about:

\[
g_t = \text{useful task-relevant advancement contributed by recent step(s)}
\]

and a rolling quantity:

\[
G_t = \sum_{i=t-w+1}^{t} g_i
\]

A trajectory can have low completion but high marginal progress:

- locating the right package,
- identifying a root cause,
- finding a discriminating test,
- eliminating a plausible hypothesis.

A trajectory can have high completion but near-zero marginal progress:

- repeated verification,
- irrelevant exploration after a mostly correct patch,
- edit/revert cycles,
- searching unrelated files.

This distinction is a strong conceptual lead, **not an assumption to force into the results**.

---

# 4. Important Taxonomy: What Could Count as Progress?

Investigate whether progress is better represented as multiple channels rather than one scalar.

## 4.1 Epistemic progress
The agent learns something relevant that reduces uncertainty.

Examples:

- identifies the faulty subsystem,
- rules out a suspected cause,
- discovers which test reproduces the issue,
- identifies a necessary dependency or constraint,
- narrows candidate functions/files,
- discovers why a prior approach failed.

Potential observable proxies:

- new relevant identifiers,
- new error signature,
- reduced search scope,
- first access to later-relevant function,
- non-redundant evidence in tool output,
- elimination of repeated hypotheses.

## 4.2 Implementation progress
The agent makes a durable change plausibly connected to the task.

Potential proxies:

- persistent diff rather than immediate edit/revert churn,
- modification of functions relevant to the issue,
- reduced patch churn,
- movement toward a simpler or more localized patch,
- no-op vs substantive edits.

## 4.3 Verification progress
Objective evidence of correctness improves.

Potential proxies:

- failing test becomes passing,
- failure count decreases,
- error signature changes in a useful direction,
- build advances further,
- targeted tests are added or executed,
- relevant test coverage is reached.

## 4.4 Regression / negative progress
A later state loses previously achieved evidence or correctness.

Examples:

- passing test breaks,
- relevant change is reverted without replacement,
- agent abandons correct localization,
- error set expands,
- repository becomes unbuildable.

One possible study result is that a **multi-channel notion of progress** outperforms any single source.

Another possible result is that one channel dominates. Let the data decide.

---

# 5. Critical Prior Work — Mandatory Reading

The following are not optional background. They are close enough to the project that the final contribution must be explicitly differentiated from them.

Before implementing the final method, read each paper at least through the abstract, method, experiments, limitations, and discussion. Create `literature_notes.md` containing:

- exact claim,
- target problem,
- data,
- inputs available to the method,
- method,
- evaluation metric,
- limitations,
- overlap with this project,
- remaining gap.

## A. Zombie Agents: Detecting Semantic Livelock in Long-Horizon Autonomous Software

**Simarjot Khanna, AIware 2026**

Links:

- https://2026.aiwareconf.org/details/aiware-2026-papers/10/Zombie-Agents-Detecting-Semantic-Livelock-in-Long-Horizon-Autonomous-Software
- https://openreview.net/pdf?id=BlVgsZzg0N

Why it matters:

This is the closest paper to the original idea. It explicitly studies **semantic livelock**: agents continue generating tokens and calling tools but stop making progress.

Its Convergence Monitor fingerprints action-observation states with a frozen embedding model and watches rolling semantic diversity. It reports real SWE-agent trajectories where string-level repetition guards would miss semantic cycling.

Critical limitation stated by the paper itself:

> semantic diversity is a proxy rather than the goal.

The paper specifically identifies **goal-conditioned progress** as future work and notes the risk of high-diversity but irrelevant “hallucination spirals.”

Implication:

**Do not claim novelty for detecting loops with semantic similarity.**  
If this project succeeds, likely novelty lies in task-grounded or evidence-grounded progress rather than pure semantic convergence.

---

## B. Failure as a Process: An Anatomy of CLI Coding Agent Trajectories

**Xiangxin Zhao et al., 2026**

- https://arxiv.org/abs/2607.09510

Why it matters:

This is a large process-oriented empirical study of coding-agent failure. It collected 3,843 trajectories across seven frontier models and three scaffolds and manually analyzed 1,794 complete valid trajectories, covering more than 63,000 execution steps.

Key result:

- failures are often driven by **epistemic errors**;
- failure processes often begin early;
- outwardly normal execution can continue after the decisive error;
- final-outcome evaluation hides when and how the trajectory became unrecoverable.

Implication:

Do not equate visible activity with progress.  
Investigate information acquisition and validation, not just edits.

Also distinguish:

\[
\text{stagnation} \neq \text{eventual failure}
\]

A productive trajectory may ultimately fail. A successful trajectory may still contain a long wasteful plateau.

---

## C. Fail-Fast, Restart-Smart: Early Failure Prediction and Restart for SWE Agentic Tasks

**Chenyu Wang et al., 2026**

- https://arxiv.org/abs/2608.03222

Why it matters:

FailFast trains a lightweight 0.6B monitor to predict **future failure from observable trajectory prefixes**. It does not require policy logits or hidden states and transfers across policies. On SWE-bench Verified, the reported monitor saves roughly 14.6–20.4% of execution tokens at a target 5% false-positive rate.

Implication:

Do not simply build another “will this run fail?” classifier.

The project should carefully distinguish:

- probability of final failure,
- current lack of marginal progress,
- semantic looping,
- task completion,
- and irrecoverability.

Operational evaluation under a **fixed false-positive/false-stop budget** is especially relevant.

---

## D. LLM-as-a-Verifier: A General-Purpose Verification Framework

**Jacky Kwok et al., Stanford / Berkeley / NVIDIA, 2026**

- https://arxiv.org/abs/2607.05391
- https://github.com/llm-as-a-verifier/llm-as-a-verifier
- https://llm-as-a-verifier.com/

Why it matters:

This work provides fine-grained verification and includes online progress tracking for coding agents.

Its progress tracker asks, approximately:

> Given everything the agent has done so far, would the CURRENT state already complete the task?

This produces a completion-like progress curve.

Research opportunity:

Test whether **change in task-grounded evidence / marginal progress** provides information that an absolute completion score misses.

However, do not assume it will. It may be a strong baseline.

---

## E. TRCA: Transition-wise Rubric Credit Assignment for Long-horizon LLM Agents

**Huan Zhang et al., 2026**

- https://arxiv.org/abs/2608.16156

Why it matters:

TRCA performs step-level credit assignment using three rubric families:

- **Evidence**
- **Execution**
- **Invalidity**

and explicitly rewards newly covered evidence/execution conditions as **incremental task progress**.

This is conceptually close to “marginal task-relevant progress.”

Important boundary:

TRCA is primarily a reinforcement-learning / credit-assignment method and is evaluated on ALFWorld, WebShop, and search QA rather than as a coding-agent runtime stagnation detector.

Implication:

Read this carefully before claiming conceptual originality around “new evidence.”

Potential project gap may be adapting/testing a similar conceptual decomposition for **reference-free runtime stagnation detection in real coding trajectories**, not inventing the concept of incremental evidence credit.

---

## F. What Resolve Rate Hides: Trajectory Structure Diagnostics for Coding Agents (TraceProbe)

**Rui Shu et al., 2026**

- https://arxiv.org/abs/2607.06184

Why it matters:

TraceProbe normalizes coding-agent traces into a canonical action taxonomy and diagnoses anti-patterns such as search loops and verification skips. It shows that trajectory structure contains important information hidden by final pass/fail.

Reported finding worth examining:

- file choice can be too coarse;
- function-level localization and completion behavior are more informative;
- search loops are among the more stable anti-patterns.

Implication:

Avoid crude “number of files touched” features as your core method.  
Function-level or task-conditioned localization may be stronger if available.

---

## G. AgentStop: Terminating Local AI Agents Early to Save Energy in Consumer Devices

**Dzung Pham et al., ACM CAIS 2026**

- https://arxiv.org/abs/2605.15206
- https://brave.com/blog/agentstop/
- https://github.com/brave-experiments/AgentStop

Why it matters:

AgentStop uses low-cost execution signals to terminate trajectories predicted to be unproductive, primarily to reduce energy and compute. It reports roughly 15–20% waste reduction with small utility degradation in its evaluated settings.

Implication:

Again, early stopping exists.  
The scientific contribution must be about **what state is detected and how it is evidenced**, not merely adding a stop button.

---

## H. SWE-bench: Can Language Models Resolve Real-World GitHub Issues?

**Carlos Jimenez et al., ICLR 2024**

- https://arxiv.org/abs/2310.06770
- https://www.swebench.com/original.html
- https://github.com/SWE-bench/SWE-bench

Why it matters:

SWE-bench provides the standard repository-level issue-solving setting and objective fail-to-pass evaluation framework.

Read enough to understand:

- task construction,
- repository context,
- patch evaluation,
- fail-to-pass tests,
- why software-engineering tasks are long-horizon.

---

## I. SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering

**John Yang et al., 2024**

- https://arxiv.org/abs/2405.15793

Why it matters:

This provides the agent-computer interaction background underlying many publicly available SWE trajectories.

---

# 6. Real Production Evidence: This Is Not a Toy Problem

Use these as motivation, not as core experimental evidence.

## OpenCode no-progress loop

- https://github.com/anomalyco/opencode/issues/43603

Reported behavior: an agent repeatedly tries to find/inspect a nonexistent or unresolved path using varied natural-language intents without gaining useful information.

This is a direct example of why:

\[
\text{different commands} \not\Rightarrow \text{progress}
\]

## OpenCode exact tool-call loop

- https://github.com/anomalyco/opencode/issues/45442

A reported subagent issued **364 identical grep calls over roughly 50 minutes**, consuming very large token/cache budgets while remaining marked “running.”

This is the easy form of stagnation.

A good monitor should catch it, but catching this alone is not research-worthy.

## Claude Code watchdog false positives

Examples:

- https://github.com/anthropics/claude-code/issues/85265
- https://github.com/anthropics/claude-code/issues/86499

Reported watchdog behavior shows the opposite failure mode: a timeout/stall detector can terminate **healthy long-running work**.

This makes false-stop control scientifically important.

The real problem is not:

> stop inactive agents.

It is:

> distinguish **productive slowness** from **unproductive activity**.

---

# 7. Public Data Sources

The project should be **data-first**. Prefer existing public trajectory corpora over spending the limited time generating new runs.

## 7.1 Terminal-Bench 2 trajectories — strong first choice

Dataset:

- https://huggingface.co/datasets/yoonholee/terminalbench-trajectories

Current dataset card reports approximately:

- 52,104 total trajectories,
- 89 tasks,
- 26 agent scaffolds,
- 49 underlying models,
- 109 agent/model combinations,
- 34,462 trials with step-level trajectories,
- median ~21 steps,
- mean ~47 steps.

Available per trajectory includes combinations of:

- task name,
- agent/scaffold,
- model,
- reward/pass,
- duration,
- token counts/cost when available,
- ordered messages,
- tool calls,
- observations.

Advantages:

- many modern agents/models,
- broad diversity,
- manageable download size,
- direct terminal/tool traces,
- useful for cross-agent generalization.

Limitation:

- not every row includes full trajectory steps;
- observations may be truncated;
- direct workspace snapshots/diffs may not always be available.

Start here unless a technical blocker appears.

---

## 7.2 Nebius SWE-agent trajectories

Dataset:

- https://huggingface.co/datasets/nebius/SWE-agent-trajectories

Contains **80,036 SWE-agent trajectories** over SWE-bench-related tasks, with fields including generated patches and evaluation logs.

Advantages:

- huge corpus,
- directly relevant to software-engineering agents,
- used by related prior work,
- useful for reproducing/benchmarking semantic-livelock findings.

Limitation:

- narrower scaffold diversity than Terminal-Bench;
- full dataset is several GB uncompressed.

Use a sample initially.

---

## 7.3 SWE-bench / SWE-bench Verified

- https://github.com/SWE-bench/SWE-bench
- https://www.swebench.com/

Use as a source of task definitions and objective test semantics.

Do **not** spend the project attempting full local SWE-bench evaluation unless already configured; official evaluation is resource-intensive. Existing trajectories and evaluation logs are likely sufficient for this short study.

---

# 8. Definition Problem: The Most Important Scientific Work

The hardest part is not training a classifier.

It is defining **stagnation without circularity**.

Do not define:

> stagnation = low value of the metric we propose

and then show that the metric detects stagnation.

That proves nothing.

Instead create an independent human-readable labeling protocol.

A useful provisional definition:

> **A trajectory interval is stagnant when the agent continues consuming actions/compute but, over a sustained interval, fails to acquire materially new task-relevant evidence, make durable task-relevant implementation progress, or improve objective verification, until either it changes strategy, recovers, terminates, or the interval ends.**

Treat that wording as provisional. Refine it after reading sample trajectories.

### Candidate annotation labels

At each segment/window rather than every token:

- `PRODUCTIVE`
- `RECOVERY`
- `STAGNANT`
- `BLOCKED_EXTERNALLY`
- `COMPLETION/REDUNDANT_VERIFICATION`
- `UNCERTAIN`

Possible collapse for binary experiments:

- positive = `STAGNANT`
- negative = `PRODUCTIVE` + `RECOVERY`
- exclude or separately report ambiguous/external blocking.

### Important edge cases

**Not necessarily stagnant:**

- repeated compile-test cycles where each failure reveals a new issue,
- searching several files while narrowing the hypothesis,
- a long tool call that is genuinely executing,
- waiting on a dependency installation,
- re-reading a small amount of context after compaction,
- repeated verification if required to establish correctness.

**Potentially stagnant:**

- repeated search with no new relevant evidence,
- different commands serving the same failed investigation intent,
- edit/revert/edit oscillation with no net improvement,
- broad exploration that never gets closer to relevant code,
- repeated tests yielding the same unchanged failure without a changed hypothesis,
- persistent work on an invalid root-cause assumption,
- continued execution after task completion.

The annotation guide itself may become a useful small contribution.

---

# 9. Prevent Label Leakage

This is essential.

The detector should be evaluated as **online** and **reference-free**.

At step \(t\), the detector may use only information that a real runtime could know by step \(t\):

Allowed:

- task statement,
- trajectory prefix,
- tool calls so far,
- tool outputs so far,
- visible test/build output,
- current workspace state if available,
- current diff if available.

Forbidden at inference time:

- gold/reference patch,
- future trajectory,
- final reward,
- hidden benchmark tests,
- known successful solution,
- annotations from later steps.

The **annotation process** may inspect the full trajectory to assign ground truth, but the **detector input must not**.

Keep this separation explicit in code.

---

# 10. Research Strategy: Explore Before Committing to a Method

Do not immediately build a complex model.

Follow this sequence.

## Phase A — Inspect trajectories manually

Read at least 20–30 diverse trajectories:

- successful short,
- successful long,
- failed short,
- failed long,
- obvious loops,
- subtle drift,
- productive repeated debugging,
- task-completed-but-agent-keeps-going.

Write a short taxonomy based on actual observations.

Ask:

- What does true stagnation look like?
- When is repetition productive?
- When is novelty useless?
- Which signals are visible without a gold solution?
- Which apparent signals fail immediately?

This phase should influence the research design.

## Phase B — Build the simplest baselines first

Before inventing a new score, establish how far trivial rules go.

Possible baselines:

### B1. Step budget
Alarm after \(N\) steps.

### B2. Exact repeated tool call
Hash `(tool_name, normalized_arguments)` and alarm after \(k\) repetitions.

### B3. Repeated tool family
Same command category / same target repeatedly.

### B4. Semantic redundancy
Reproduce a simplified Zombie-Agents-style rolling embedding diversity score.

### B5. No observable workspace change
If enough state is available.

### B6. Completion verifier
Use LLM-as-a-Verifier progress/completion score if affordable and reproducible.

These baselines make the final result interpretable.

## Phase C — Explore candidate signal families

Only after baseline analysis.

Do not assume all of these should be used.

---

# 11. Candidate Signal Families

## 11.1 Action repetition

Features:

- exact tool-call duplicate rate,
- normalized command duplicate rate,
- n-gram recurrence,
- repeated same file/path,
- repeated same search query,
- periodic action cycles.

Pros: almost free.  
Cons: trivial, easy to evade with surface variation.

---

## 11.2 Semantic trajectory redundancy

Embed recent `(action, observation)` representations.

Possible features:

\[
D_t = 1 - \text{mean pairwise cosine similarity}
\]

or:

- distance from recent centroid,
- nearest previous-state similarity,
- recurrence period,
- rolling entropy / cluster count.

Pros: catches semantic loops with different wording.  
Cons: novelty is not progress.

Must compare directly against Zombie Agents.

---

## 11.3 Task-relevant evidence gain

This may be the most promising area.

Question:

> Did this step add new evidence relevant to the task that was not already present?

Possible implementations range from cheap to expensive:

### Cheap heuristic
Extract new:

- file/function identifiers,
- stack traces,
- error signatures,
- test names,
- dependency names,
- symbols,
- paths.

Weight them by lexical/embedding relevance to the task.

### Embedding-based
Represent newly observed information and task statement; measure novelty × task relevance.

Conceptually:

\[
E_t =
\text{Novelty}(o_t \mid o_{<t})
\times
\text{Relevance}(o_t, x)
\]

Do not over-trust this equation; test variants.

### LLM-rubric judge
Ask a small verifier whether the transition produced new evidence relevant to the task, similar in spirit to TRCA.

Pros: semantically strong.  
Cons: cost, latency, reproducibility, possible judge bias.

An important result could be that cheap proxies approximate the LLM judge well enough.

---

## 11.4 Verification delta

Extract signals from tool output:

- test pass/fail count,
- changed failing tests,
- build success level,
- error category,
- exit code,
- lint/static errors.

Examples:

\[
V_t = \Delta (\text{passing relevant tests})
\]

or discrete:

- `IMPROVED`
- `UNCHANGED`
- `REGRESSED`
- `NO_VERIFICATION`

This is objective and likely high-value when available.

---

## 11.5 Workspace progress

If traces or reconstructed repositories provide enough state:

- diff size,
- changed functions,
- persistent edits,
- edit/revert cycles,
- net change,
- patch churn,
- repeated touches to same lines.

Be cautious.

`+300 lines` is not progress merely because it is a large change.

Potentially stronger:

- **persistent** change rather than raw change,
- task-relevant localization,
- reduced churn.

---

## 11.6 Search/localization dynamics

Possible features:

- number of unique files examined,
- concentration vs expansion,
- repeated searches over same region,
- first access to task-relevant symbols,
- function-level focus.

TraceProbe suggests file-level choice alone may be too coarse, so prefer finer-grained function/symbol behavior where possible.

---

## 11.7 Regression / reversal

Potential indicators:

- previously passing test fails,
- error becomes worse,
- edit is undone,
- agent reopens already-discarded hypothesis,
- same state is revisited after a cycle.

A state-recurrence graph may expose oscillations:

\[
s_i \approx s_j,\quad j-i > 1
\]

especially if intermediate actions consume significant compute.

---

## 11.8 Completion or verifier scores

Use LLM-as-a-Verifier or a simpler judge as a baseline/feature.

Important distinction:

\[
\Delta C_t = C_t - C_{t-k}
\]

may be more relevant to stagnation than absolute \(C_t\).

But empirically test:

- absolute completion,
- slope,
- variance,
- plateau length.

---

## 11.9 Phase-aware features — optional extension

Progress may mean different things in different workflow phases:

1. localization/exploration,
2. diagnosis,
3. implementation,
4. verification,
5. completion.

A file read during exploration can be productive.  
Twenty file reads after a completed patch may not be.

If the basic study is already working, explore phase-conditioned thresholds/features.

Do not make phase modeling mandatory; it can easily consume the project.

---

# 12. Candidate Modeling Approaches

Prefer interpretability and speed.

Recommended order:

1. threshold rules,
2. logistic regression,
3. decision tree,
4. random forest / gradient-boosted trees,
5. only then a learned neural/LLM monitor if clearly justified.

Reasons:

- small labeled dataset,
- easier ablation,
- easier explanation,
- less leakage risk,
- faster iteration,
- stronger scientific interpretability for a short project.

The paper should not become:

> “We fine-tuned a model and F1 increased.”

The valuable part is identifying **which observable signals actually correspond to progress**.

---

# 13. Evaluation Design

## 13.1 Unit of prediction

Explore at least two:

### Window-level stagnation classification
Given the last \(w\) steps, classify current window.

### Alarm/event evaluation
Run detector sequentially and record first alarm.

Operational event evaluation is more realistic.

---

## 13.2 Primary operational objective

A false stop is much more expensive than failing to stop one wasteful run.

Therefore do not optimize ordinary accuracy alone.

A strong framing is:

\[
\max \text{wasted execution prevented}
\]

subject to:

\[
\text{false-stop rate} \le \epsilon
\]

where \(\epsilon\) might be 1%, 5%, or another defensible threshold.

Report performance at multiple thresholds.

---

## 13.3 Metrics

At minimum:

- precision,
- recall,
- F1 or PR-AUC,
- false-stop rate,
- detection delay,
- steps saved,
- tokens saved where token data exists,
- fraction of successful/productive runs interrupted.

Better:

- savings at fixed false-stop rate,
- recall at fixed false-stop rate,
- cross-agent transfer,
- confidence intervals via bootstrap.

---

## 13.4 Define waste carefully

Possible operational definition:

If stagnation begins at annotated step \(t_s\) and the detector alarms at \(t_a\),

\[
\text{avoidable waste saved}
=
\max(0, t_{\text{end}} - t_a)
\]

but only if alarm is after/within a genuinely stagnant region.

Alternative:

Compute excess steps relative to annotated recovery/termination.

The exact formula should follow the annotation scheme.

Do not quietly count productive steps as “saved.”

---

# 14. The Essential Ablation Study

If a combined monitor works, determine why.

Suggested feature groups:

- `REP`: exact/action repetition
- `SEM`: semantic redundancy
- `EVID`: task-relevant evidence gain
- `VER`: verification delta
- `WORK`: workspace/diff dynamics
- `COMP`: completion-verifier signal

Compare:

- REP only
- SEM only
- EVID only
- VER only
- WORK only
- COMP only
- simple combinations
- full model

Then remove one group at a time.

Questions:

- Does task relevance materially improve semantic novelty?
- Does verification dominate everything when present?
- Does workspace state add anything after evidence/verification?
- Can cheap signals approach an LLM verifier?
- Are features agent-specific?

A negative result is acceptable if clearly established.

---

# 15. Strong Adversarial / Counterexample Cases

Construct or identify trajectory examples that break naive detectors.

## Case 1 — Productive repetition

```
run targeted test
fix error A
run targeted test
fix error B
run targeted test
fix error C
```

Surface semantics repeat; actual verification improves.

Desired detector: **do not alarm**.

## Case 2 — Diverse hallucination spiral

```
inspect unrelated API
search package docs
rewrite config
check network
inspect unrelated dependency
```

High semantic diversity; no useful task-relevant evidence.

Desired detector: **alarm**.

## Case 3 — Information-only progress

```
read traceback
inspect call site
search symbol
identify root cause
```

No file changes.

Desired detector: **do not alarm**.

## Case 4 — High workspace churn

```
edit
revert
edit alternative
revert
edit original approach
```

Many file changes but little durable progress.

Desired detector: possibly **alarm**.

## Case 5 — Healthy slow operation

A long compilation, dependency install, model run, or network request.

Desired detector: **do not alarm solely because time passed**.

## Case 6 — Completed-but-keeps-working

Task appears verified, but agent continues rereading/rechecking indefinitely.

This may be a distinct inefficiency class rather than stagnation. Decide whether to include or report separately.

---

# 16. Dataset Sampling Plan for a Short Project

Do not try to annotate thousands of trajectories manually.

A high-quality small study is better.

Possible plan:

### Stage 1 — Exploration
Sample ~30 trajectories stratified by:

- outcome,
- length,
- scaffold/model.

Develop the taxonomy and annotation guide.

### Stage 2 — Main labeled set
Target roughly **100–250 trajectories**, prioritizing longer ones where stagnation can exist.

Possible stratification:

- half successful / half failed if practical,
- multiple scaffolds,
- multiple models,
- length buckets.

Annotate only trajectory intervals/windows required for evaluation rather than every line if time-constrained.

### Stage 3 — Unlabeled scale-up
Once a detector is defined, run it over thousands of trajectories for descriptive analysis.

This can produce compelling data:

- estimated stagnation prevalence,
- where it occurs,
- which agents exhibit it,
- average potential wasted steps,
- common patterns.

But clearly separate **model-inferred prevalence** from manually verified ground truth.

---

# 17. Avoid Dataset Confounds

Check for:

- duplicate tasks,
- repeated trials of same task,
- model/scaffold imbalance,
- length as an accidental predictor,
- final reward leaking into features,
- task IDs memorized by train/test split,
- observations containing explicit final grading,
- hidden metadata leakage.

For any learned model, prefer:

- task-disjoint train/test split,
- and if possible scaffold/model holdout experiments.

A classifier that memorizes “this task is hard” is not a stagnation detector.

---

# 18. Statistical Analysis

Keep it simple and credible.

For binary comparisons:

- bootstrap 95% confidence intervals,
- precision-recall curves,
- paired comparisons on same trajectories where possible.

For ablations:

- report absolute metric changes,
- confidence intervals,
- not only p-values.

For prevalence claims:

- manually validate samples,
- provide uncertainty.

Do not overstate statistical significance on a tiny labeled dataset.

---

# 19. A Potential Minimal Method — Only a Starting Baseline

If an implementation must begin before the literature/data inspection is complete, create a deliberately simple modular pipeline:

```text
trajectory
    ↓
normalize tool/action/observation
    ↓
feature extraction
    ├─ repetition
    ├─ semantic novelty
    ├─ task relevance
    ├─ evidence novelty
    ├─ verification delta
    └─ workspace churn (if available)
    ↓
rolling window
    ↓
simple classifier / threshold model
    ↓
stagnation probability
    ↓
alarm only after sustained confidence
```

A possible conceptual score:

\[
P_t =
w_E E_t +
w_V V_t +
w_W W_t
-
w_R R_t
-
w_G G_t
\]

where:

- \(E_t\) = evidence gain,
- \(V_t\) = verification improvement,
- \(W_t\) = durable workspace progress,
- \(R_t\) = redundancy,
- \(G_t\) = regression/churn.

Do **not** treat this as the final method.  
The variables, weights, and even additive form should be determined or rejected based on evidence.

---

# 20. What Would Make the Research Actually Interesting?

The paper should aim to establish at least one non-obvious empirical finding.

Examples of **possible** findings, not claims:

- Task-conditioned evidence novelty detects stagnation substantially better than semantic diversity.
- Verification change is extremely predictive but sparse; evidence novelty fills the gap before testing begins.
- Filesystem/diff activity is surprisingly weak after controlling for task relevance.
- Exact repetition catches only a small minority of real stagnant windows.
- Most waste occurs in a small number of long plateaus.
- A simple interpretable detector performs nearly as well as an expensive LLM verifier.
- Progress signals are strongly phase-dependent.
- Failure prediction and stagnation detection identify meaningfully different trajectories.
- A monitor tuned on one scaffold generalizes poorly/well to others.

The project becomes strong when the result is:

> “We measured something people currently assume but have not isolated clearly.”

---

# 21. Claims to Avoid Unless the Data Proves Them

Do not write:

- “This is the first stuck-agent detector.”
- “Existing systems only use repeated commands.”
- “External state is the true measure of progress.”
- “Semantic novelty is useless.”
- “Failure prediction is equivalent to stagnation detection.”
- “Our method solves infinite loops.”
- “Our approach generalizes to all coding agents.”
- “The monitor is safe” without false-positive evidence.

Safer contribution language:

> We study...

> We operationalize...

> We compare...

> We find evidence that...

> Under the evaluated trajectories...

> At a fixed false-stop budget...

---

# 22. Research Gap to Test — Not Automatically Claim

A promising gap suggested by the current literature is:

> **Lightweight, online, reference-free estimation of marginal task-relevant progress in coding-agent trajectories, evaluated specifically for stagnation detection rather than final-failure prediction or task-completion scoring.**

The combination that appears relatively underexplored is:

- coding-specific,
- online,
- reference-free,
- stagnation-focused,
- marginal/incremental progress,
- low-cost observable signals,
- explicit false-stop control.

But this must be re-checked against the literature before being claimed as novel.

Run additional searches for:

- `"coding agent" progress monitor stagnation`
- `"software agent" trajectory stagnation`
- `"agent" semantic livelock`
- `"coding agent" early termination`
- `"coding agent" progress estimation`
- `"trajectory prefix" software engineering agent`
- `"reference-free" coding agent trajectory`
- `"task progress" autonomous software engineering`
- `"goal-conditioned progress" agent`
- `"process reward" coding agent`
- `"stuck detection" LLM agent`
- `"loop detection" autonomous agent`
- `"agent failure prediction" SWE-bench`

Search arXiv, ACM DL, OpenReview, Google Scholar/Semantic Scholar, GitHub, Hugging Face, conference proceedings, and recent technical reports.

Record every close work and explicitly compare it.

---

# 23. A Concrete Autonomous Workflow

The research agent should execute the following loop, while retaining freedom to revise the method.

## Step 1 — Literature map
Produce `literature_notes.md` and `related_work_matrix.csv`.

Columns:

- title
- year
- venue
- URL/DOI
- problem
- dataset
- online/offline
- reference-free?
- predicts failure?
- detects stagnation?
- progress definition
- inputs
- model cost
- main result
- limitations
- overlap with this project

Do this **before finalizing the method**.

## Step 2 — Acquire data
Download a manageable sample of Terminal-Bench 2 trajectories.

Create reproducible scripts:

```text
scripts/
  download_data.py
  inspect_trajectory.py
  sample_trajectories.py
```

Never commit massive datasets unnecessarily.

## Step 3 — Exploratory trajectory study
Generate:

- length distribution,
- pass/fail distribution,
- tool-call categories,
- repeated-call statistics,
- example trajectories.

Create `notes/trajectory_taxonomy.md`.

## Step 4 — Annotation protocol
Draft a precise stagnation definition.

Manually label an exploratory subset.

Revise definitions after disagreements/edge cases.

Save:

```text
data/annotations.csv
docs/annotation_guide.md
```

## Step 5 — Baselines
Implement trivial and prior-work-inspired baselines first.

Save every run configuration.

## Step 6 — Candidate signal exploration
Compute features and visualize their distributions for productive vs stagnant windows.

Avoid committing to a model before seeing this.

## Step 7 — Minimal model
Train/tune only after feature behavior is understood.

Use task-disjoint split.

## Step 8 — Evaluation
Produce:

- PR curve,
- savings vs false-stop curve,
- detection-delay distribution,
- ablation table,
- counterexample analysis.

## Step 9 — Robustness
If time permits:

- another scaffold,
- another model,
- another dataset,
- different window lengths,
- different annotation thresholds.

## Step 10 — Freeze results
Create immutable:

```text
results/final/
```

containing:

- raw metrics,
- experiment config,
- seed,
- generated plots,
- summary tables.

Only claims supported by this directory may enter the final report.

---

# 24. Project Structure

Recommended:

```text
research/
├─ README.md
├─ AI_ASSISTANCE_LOG.md
├─ literature_notes.md
├─ related_work_matrix.csv
├─ requirements.txt
├─ config/
│  └─ experiments.yaml
├─ data/
│  ├─ raw/
│  ├─ processed/
│  ├─ samples/
│  └─ annotations.csv
├─ docs/
│  ├─ annotation_guide.md
│  ├─ trajectory_taxonomy.md
│  └─ research_decisions.md
├─ src/
│  ├─ loaders.py
│  ├─ normalize.py
│  ├─ features/
│  │  ├─ repetition.py
│  │  ├─ semantic.py
│  │  ├─ evidence.py
│  │  ├─ verification.py
│  │  └─ workspace.py
│  ├─ baselines.py
│  ├─ models.py
│  └─ evaluation.py
├─ scripts/
│  ├─ download_data.py
│  ├─ inspect_trajectory.py
│  ├─ annotate.py
│  ├─ run_baselines.py
│  ├─ run_experiments.py
│  └─ make_figures.py
├─ results/
│  ├─ exploratory/
│  └─ final/
├─ figures/
└─ paper/
   ├─ evidence_table.md
   ├─ outline.md
   └─ student_draft_notes.md
```

Keep implementation small.

---

# 25. Paper Strategy: Data > Prose

The final research report does not need to be long.

A strong paper can be built around:

1. one precise problem,
2. one defensible operational definition,
3. 2–4 baselines,
4. one simple proposed formulation,
5. one well-labeled dataset/sample,
6. one strong ablation,
7. two or three figures,
8. honest limitations.

Suggested structure:

## Abstract
Only after results are frozen.

## 1. Introduction
Problem:
coding agents may remain active without meaningful progress.

Motivation:
cost, latency, reliability, unattended execution.

Gap:
existing work covers semantic livelock, failure prediction, trajectory diagnostics, and completion verification; the exact investigated gap must be stated narrowly.

Contributions:
only what experiments actually establish.

## 2. Related Work
Organize by concept rather than paper chronology:

- coding-agent trajectory evaluation,
- semantic loop/livelock detection,
- early failure prediction,
- progress/verifier models,
- step-level credit assignment.

## 3. Problem Definition
Define:

- trajectory,
- observable prefix,
- stagnation,
- online/reference-free constraints,
- false stop.

## 4. Data and Annotation
This may be one of the most important sections.

Explain:

- dataset,
- sampling,
- annotation rule,
- ambiguity,
- leakage prevention.

## 5. Methods
Baselines first, then proposed method.

Keep equations minimal and meaningful.

## 6. Results
Lead with the strongest result.

Useful tables:

- baseline comparison,
- ablation,
- performance at fixed false-stop rates.

Useful figures:

- example productive vs stagnant trajectories,
- savings-vs-false-stop curve,
- feature/ablation plot.

## 7. Failure Analysis
Show where the detector gets it wrong.

This increases credibility.

## 8. Limitations
Potentially:

- annotation subjectivity,
- limited models/tasks,
- truncated observations,
- no hidden repository state,
- model-dependent semantic embeddings,
- retrospective public traces,
- detector does not prove irrecoverability.

## 9. Conclusion
One narrow empirical statement.

---

# 26. Evidence Table Before Writing

Before producing prose, generate:

`paper/evidence_table.md`

Example:

| Proposed claim | Supporting experiment | Figure/table | Confidence | Caveat |
|---|---|---|---|---|
| Semantic diversity misses diverse drift | manually labeled cases + baseline | Fig. 2 | medium | small sample |
| Evidence features improve recall at 5% false-stop | ablation | Table 2 | high | dataset A only |
| Method generalizes across scaffold | holdout scaffold | Table 3 | medium | two scaffolds |

If a sentence in the paper cannot point to:

- a source,
- an experiment,
- or an explicitly labeled hypothesis,

it probably does not belong.

---

# 27. Minimum Viable Research Result

Given the extremely short schedule, the minimum viable strong project is **not** a deployed plugin.

It is:

- a defensible stagnation annotation scheme,
- ~100+ carefully sampled real trajectories or windows,
- several baseline detectors,
- one simple task-grounded progress signal,
- evaluation under a false-stop constraint,
- one meaningful empirical finding,
- reproducible code and plots.

If time collapses, sacrifice:

1. UI,
2. integration with live coding tools,
3. complex model,
4. large paper.

Do **not** sacrifice:

1. valid labels,
2. leakage control,
3. baselines,
4. data quality,
5. reproducibility.

---

# 28. Best-Case Extension If Results Arrive Early

Only if the core experiment is already complete.

## A. Live sidecar prototype

Build a simple sidecar for a coding harness:

```text
agent → tools → monitor → log/alarm
```

It need not autonomously kill the agent. A real-time warning is enough to demonstrate applicability.

## B. Recovery policy

When stagnation is detected, compare:

- do nothing,
- warning,
- force summary,
- ask agent to restate current evidence,
- restart from clean context,
- restart while preserving diff.

This becomes a separate question and can explode scope. Avoid unless core work is done.

## C. Cross-agent transfer

Train/tune on one set, evaluate another.

This is highly valuable if cheap.

---

# 29. Stop Conditions / Decision Rules

The research agent should not stubbornly preserve the initial hypothesis.

### If semantic redundancy alone is extremely strong:
Investigate where it fails and whether task grounding gives measurable improvement. If not, report that.

### If task-relevance scoring is noisy:
Simplify it. Do not build a huge judge.

### If workspace state is unavailable:
Drop it. The project does not depend on file hashes.

### If annotation is too subjective:
Narrow stagnation to a more objective subtype, e.g.:

- repeated investigation with no novel evidence,
- edit/revert oscillation,
- unchanged verification loop.

A narrower reliable study beats a vague broad one.

### If public trajectories lack sufficient information:
Use Terminal-Bench + Nebius together or generate a very small controlled trajectory set.

### If the combined method fails:
A careful empirical result showing **why common progress proxies fail** can still be publishable-quality high-school research.

---

# 30. Research Philosophy for This Project

The project should answer a real question rather than demonstrate a clever score.

The strongest process is:

```text
observe phenomenon
→ define it independently
→ inspect prior work
→ construct competing explanations
→ measure simple signals
→ test counterexamples
→ quantify tradeoffs
→ accept what the data says
```

Do not reverse this into:

```text
invent metric
→ tune it
→ define success to match it
→ write paper
```

---

# 31. Initial Hypotheses — Treat as Disposable

These are useful starting hypotheses, not desired conclusions.

### H1
Exact action repetition will have high precision but low recall for real stagnation.

### H2
Semantic redundancy will detect oscillatory loops but miss high-diversity irrelevant exploration.

### H3
Task-conditioned evidence novelty will add useful information beyond raw semantic novelty.

### H4
Verification delta will be highly reliable where available but too sparse to detect early exploration stagnation alone.

### H5
Raw file/diff activity will be a weak progress proxy unless conditioned on persistence or relevance.

### H6
A simple multi-signal model may approach the utility of an expensive LLM verifier at much lower monitoring cost.

### H7
Failure prediction and stagnation detection will disagree on a non-trivial subset of trajectories.

Try to falsify them.

---

# 32. High-Value Questions to Answer From the Data

If time allows, answer some of these descriptively:

- How common are long repeated-action loops?
- How common are semantic loops without exact repetition?
- How common is diverse but irrelevant exploration?
- Do successful runs contain stagnant intervals?
- How much of failed-run length occurs after the first stagnation interval?
- Is stagnation more common during search, edit, or verification?
- What fraction of stagnation can a simple exact-repeat guard catch?
- Does the best feature differ by scaffold/model?
- Are longer runs inherently more likely to be labeled stagnant?
- How much waste could theoretically be removed at a 1%, 5%, or 10% false-stop rate?

These can yield impactful results even with a simple method.

---

# 33. Reproducibility Requirements

Every experiment must record:

- dataset/version,
- sample IDs,
- filtering criteria,
- feature config,
- window size,
- model name/version,
- random seed,
- train/test split,
- thresholds,
- metric implementation,
- date/time,
- API/verifier configuration if used.

Never overwrite final results.

Use machine-readable JSON/CSV outputs.

All plots should be regenerable from scripts.

---

# 34. AI-Assistance Logging

Create `AI_ASSISTANCE_LOG.md`.

For each AI-assisted action, record:

```markdown
## YYYY-MM-DD HH:MM

Tool/model:
Purpose:
Input/task:
Output used:
Human verification required:
What was accepted/rejected:
```

The student must ultimately make the disclosure consistent with the official Yau rules.

Never hide AI involvement.

---

# 35. Recommended Immediate Priority Order

Given the short remaining time:

1. **Read the six closest 2026 papers first:** Zombie Agents, Failure as a Process, FailFast-RestartSmart, LLM-as-a-Verifier, TRCA, TraceProbe.
2. Download a sample of Terminal-Bench trajectories.
3. Manually inspect 20–30.
4. Freeze a narrow operational definition of stagnation.
5. Label a modest high-quality sample.
6. Implement exact-repetition + semantic-diversity baselines.
7. Test one or two task-grounded signals.
8. Build the smallest interpretable combined model.
9. Evaluate savings at a fixed false-stop rate.
10. Run one ablation and one failure analysis.
11. Freeze data/results.
12. Only then prepare the paper evidence table and outline.

Do not spend the first half of the project designing architecture.

---

# 36. The Intended Intellectual Center

The strongest current conceptual framing is:

> **Activity is not progress. Novelty is not necessarily progress either. A useful runtime monitor must estimate whether new actions are producing task-relevant evidence or verified advancement.**

But even this must survive experiment.

The final result could support it, weaken it, or replace it.

That is the point of the research.

---

# 37. One-Sentence Mission for the Research Agent

> **Investigate, with real coding-agent trajectory data and rigorous baselines, whether useful online stagnation detection is possible without knowing the correct solution, determine which observable signals actually correspond to marginal task-relevant progress, and produce a compact reproducible evidence package from which the student can independently form and write the final research argument.**

---

# 38. Core Bibliography / Links

### Mandatory
1. Khanna, S. **Zombie Agents: Detecting Semantic Livelock in Long-Horizon Autonomous Software.** AIware 2026.  
   https://2026.aiwareconf.org/details/aiware-2026-papers/10/Zombie-Agents-Detecting-Semantic-Livelock-in-Long-Horizon-Autonomous-Software  
   https://openreview.net/pdf?id=BlVgsZzg0N

2. Zhao, X. et al. **Failure as a Process: An Anatomy of CLI Coding Agent Trajectories.** 2026.  
   https://arxiv.org/abs/2607.09510

3. Wang, C. et al. **Fail-Fast, Restart-Smart: Early Failure Prediction and Restart for SWE Agentic Tasks.** 2026.  
   https://arxiv.org/abs/2608.03222

4. Kwok, J. et al. **LLM-as-a-Verifier: A General-Purpose Verification Framework.** 2026.  
   https://arxiv.org/abs/2607.05391  
   https://github.com/llm-as-a-verifier/llm-as-a-verifier

5. Zhang, H. et al. **TRCA: Transition-wise Rubric Credit Assignment for Long-horizon LLM Agents.** 2026.  
   https://arxiv.org/abs/2608.16156

6. Shu, R. et al. **What Resolve Rate Hides: Trajectory Structure Diagnostics for Coding Agents.** 2026.  
   https://arxiv.org/abs/2607.06184

7. Pham, D. et al. **AgentStop: Terminating Local AI Agents Early to Save Energy in Consumer Devices.** ACM CAIS 2026.  
   https://arxiv.org/abs/2605.15206  
   https://github.com/brave-experiments/AgentStop

### Foundations / datasets
8. Jimenez, C. E. et al. **SWE-bench: Can Language Models Resolve Real-World GitHub Issues?** ICLR 2024.  
   https://arxiv.org/abs/2310.06770  
   https://github.com/SWE-bench/SWE-bench

9. Yang, J. et al. **SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering.** 2024.  
   https://arxiv.org/abs/2405.15793

10. **Terminal-Bench 2.0 trajectories**  
    https://huggingface.co/datasets/yoonholee/terminalbench-trajectories

11. **Nebius SWE-agent trajectories**  
    https://huggingface.co/datasets/nebius/SWE-agent-trajectories

### Production motivation
12. OpenCode issue #43603 — no effective no-progress/loop detection  
    https://github.com/anomalyco/opencode/issues/43603

13. OpenCode issue #45442 — 364 repeated grep calls / long-running subagent loop  
    https://github.com/anomalyco/opencode/issues/45442

14. Claude Code issue #85265 — stall watchdog kills healthy long-running requests  
    https://github.com/anthropics/claude-code/issues/85265

15. Claude Code issue #86499 — cascading stall-watchdog failures  
    https://github.com/anthropics/claude-code/issues/86499

### Competition rules
16. S.-T. Yau High School Science Award — 2026 AI-use rules  
    https://www.yau-awards.com/show-86-59.html

17. S.-T. Yau High School Science Award — Mainland China competition rules  
    https://www.yau-awards.com/page-rule.html

---

# 39. Final Reminder

The goal is **not** to make the most complicated detector.

The goal is to produce the clearest evidence about a practically important question.

A small result such as:

> “At a 5% false-stop rate, task-conditioned evidence change captures substantially more stagnant execution than repetition or semantic-diversity baselines, while raw workspace change adds little.”

would be far more valuable than a sophisticated model with no interpretable conclusion.

Conversely, if the data says the simple semantic baseline already works best, report that.

**The data decides the paper.**
