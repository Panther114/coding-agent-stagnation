# Where Coding Agents Actually Fail

### A measurement blind spot, a bounded localisation effect, and a working router

**Ziheng Yu · Xuhao Chen**
S.-T. Yau High School Science Award (Computer Science), Mainland China, 2026

---

## Abstract

Coding agents fail, and a large literature tries to detect *when*. This study asks a different
question first: **are we measuring the right thing?** Working from 236,137 mechanically labelled
edit operations across 25,681 agent runs on 1,213 real software-engineering instances, we report
four results, one of which is a correction to our own earlier headline.

First, we identify a **measurement blind spot**. A commonly computable statistic — the share of a
run's edits aimed at files in *that run's own final patch* — inverts the sign of the
solved-versus-failed comparison. On our data it reports failed runs localising *better* (0.673 vs
0.585). Against an **independent gold patch**, the direction reverses (0.477 vs 0.407). The metric
is a closed loop: its target set is the run's own output, so a run that fixates on the wrong file
and never wavers scores 1.0. Two published papers report the direction our correction recovers. We
stress-tested three mechanisms for the inversion and **all three failed**, so the defect is
demonstrated but not mechanistically explained.

Second, we bound what localisation can buy. The robust measure is binary — did the run ever edit a
gold-patch file — and it is positive in every patch-width stratum: **98.2% of successful runs and
69.1% of failed runs reach the correct file**. Localisation is necessary but capped: it can address
at most the **30.9%** of failures that never reach the file. The remaining 69.1% happen with the
agent already in the right place.

Third, we make that causal rather than correlational. Holding a defect fixed and varying **only**
how easy it is to find, across three arms of a live experiment on real Python packages: handing the
agent the exact file and function moves success from **23.5% to 43.8%** — real, but the
failure-rate drop (0.203) is below the 0.309 our observational result predicted as the ceiling, and
confirmed in advance. Decisively, **even when the agent reaches the correct file — 82% of runs did —
it succeeded only 28.6% of the time.** A prompt telling it to re-diagnose after a failed test did
**not** help. Being in the right place is necessary and nowhere near sufficient.

Fourth, we build a **causal, reference-free router** that decides whether a struggling run needs
*search* or *verification*. Using only the first 10–60% of a run, it beats every baseline on
identical rows and folds: **0.693–0.731** on failure prediction and **0.676–0.751** on
distinguishing lost from wrong-fix runs, where every published-style heuristic — loop detection,
burst detection, redundancy, output-shape — sits **at or below chance (0.407–0.539)**. Its
false-alarm rate is genuinely controlled (α = 0.05 → 0.046 achieved), unlike the circular
calibration claim we withdrew. As a routing policy it is worth 0.764–0.800 against 0.732 for always
verifying and 0.518 for always searching.

We report a ledger of **eight claims we retracted, including three of our own headlines.** The most
transferable result of this work is not a number but a procedure: we wrote tests designed to
falsify our own claims, and they succeeded eight times.

---

## 1. Introduction

Coding agents resolve a substantial share of real software issues and fail on the rest. A large body
of work treats failure as a *monitoring* problem: watch the trajectory, notice when the agent is
stuck, intervene. That framing has a hidden premise — that the agent fails because it is **lost**,
unable to find the right place to work.

This study began with a startling result supporting the opposite view. On tasks containing both a
solved and a failed run, failed runs appeared to aim a *higher* share of their edits at the file
that ends up in their patch (0.620) than solved runs did (0.576), *p* = 3.3 × 10⁻⁴. If failures
localise at least as well as successes, then localisation is not the bottleneck and a great deal of
monitoring research is aimed at the wrong target.

That result is wrong, and §3 shows why. But the way it is wrong, and what stands in its place, are
more useful than the original claim.

We had two advantages over the usual setup. First, the agent framework we study prints a structural
footer into its observations — `[File: /abs/path/to/file.py (N lines total)]` — in **95.8% of edit
steps, covering 95.8% of all editing**. That lets us label every single edit mechanically, with no
human judgement and no model in the loop: whether the file changed, by how many lines, and whether
those lines ever appear in the agent's final submitted patch. This converts the study from *"we
asked a model what stagnation looks like"* to *"we counted which written lines shipped."*

Second, we obtained **independent ground truth**: gold patches for 927 of the 1,213 instances from
the upstream SWE-rebench and SWE-bench corpora. That is a target completely independent of what any
agent produced — and it is what exposed the blind spot.

Our contributions:

1. **A measurement blind spot**, demonstrated with both metrics on identical edits and a control
   showing the two agree where they must (§3).
2. **A bounded-localsation result**, robust across every stratum, replacing a retracted claim (§4).
3. **A causal test**: the same defect with localisation solved by fiat (§5).
4. **A working router** that beats every baseline on a target where the field's detectors have no
   signal, with genuine false-alarm control (§6).
5. **A retraction ledger** (§8) and an honest account of what failed.

---

## 2. Related work, and what is not ours

We verified every citation below by fetching it directly; reconnaissance summaries were not trusted
for load-bearing claims.

**The interpretation is not ours.** *Coherence Collapse* ([arXiv:2603.24631](https://arxiv.org/abs/2603.24631),
2026) reports across 16,758 trajectories that *"the dominant failure of capable models is not
localization: 60–69% of failures on SWE-Agent and OpenHands reach and edit the correct functions yet
still produce incorrect patches."* Our independently measured **67.1% sits inside that range.** A
second study ([arXiv:2511.00197](https://arxiv.org/abs/2511.00197), ICSE 2026) finds the majority of
failing trajectories locate the correct files. We therefore claim **no novelty** for the qualitative
finding that agents fail after reaching the right code, and we say so explicitly rather than
re-deriving it.

**Two papers report the opposite direction on adjacent metrics** — FailForge
([arXiv:2608.08570](https://arxiv.org/abs/2608.08570)) reports localisation precision higher for
passing than failing runs, and TraceProbe ([arXiv:2607.06184](https://arxiv.org/abs/2607.06184))
finds same-task file-selection divergence in failed runs. These are consistent with **our corrected**
result and inconsistent with the metric we expose in §3. Reconciling an apparent contradiction in
the literature is part of what we contribute.

**The monitoring framing is not ours either.** *Confident and Wrong: Silent Semantic Failures in
Coding Agents* ([arXiv:2603.25764](https://arxiv.org/abs/2603.25764)) shows GPT-5 submitting a patch
on 100% of runs while resolving 44%, and observes that *"completion-based and consistency-based
monitoring both look healthy exactly when the agent should not be trusted."* Our finding that the
*most* fixated runs are precisely the ones that never reached the right file (§3) independently
corroborates that warning.

**Waste has been measured before.** TRIM ([arXiv:2607.18161](https://arxiv.org/abs/2607.18161))
reports 20.0% "CodeSlop" on SWE-bench, close to our 19.1% dead-end rate. The objects differ and we
state the difference plainly: TRIM measures unnecessary *lines in a passing patch*, established by
counterfactual re-execution; we measure edit *operations* that never reach the patch, with no
execution at all. Ours is cheaper and coarser; theirs is causally stronger.

**The detection bar is soft, which is why our router is worth reporting.** Published detectors sit
at AUC 0.6–0.7 ([arXiv:2605.15206](https://arxiv.org/abs/2605.15206)); the field's shared
attribution benchmark reaches 53.5% agent-level but only **14.2% step-level**
([arXiv:2505.00212](https://arxiv.org/abs/2505.00212)); a failure-as-a-process monitor achieves 82%
precision at 2–3% false alarms but only **18.2% recall**
([arXiv:2607.09510](https://arxiv.org/abs/2607.09510)); the step-level redundancy ceiling is
**24.88%** ([arXiv:2605.29893](https://arxiv.org/abs/2605.29893)).

**What is ours** is the measurement result: no located paper reports failed runs localising *better*
within-instance, and a broken self-referential metric is exactly what produces that sign.

---

## 3. The measurement blind spot

### 3.1 The statistic

The conventional localisation statistic is:

> **on-target** = (the run's edits aimed at files its final patch touches) ÷ (the run's edits)

Both the numerator's file set and the denominator come from **the same run**. It asks *"did the run
converge on what it produced?"*, not *"did it aim at the right place?"* A run that fixates on the
wrong file and never wavers scores 1.0.

### 3.2 Replacing the target with ground truth

We obtain gold patches for 927 of 1,213 instances (843 SWE-rebench, 84 SWE-bench) and recompute on
**identical edit steps**.

| measure | solved | failed | reading |
|---|---|---|---|
| on-target, own patch (*the conventional statistic*) | 0.594 | **0.670** | failed "better" — the startling result reproduces |
| on-target, **gold** patch (basename match) | **0.477** | 0.407 | direction reverses |
| on-target, **gold** patch (path match) | **0.510** | 0.430 | robust to the match rule |
| **ever reached a gold file** | **0.982** | 0.670 | large and unambiguous |

*Pooled over runs. Within-instance paired means for the gold target are 0.496 solved vs 0.448 failed, p = 0.007 over 228 instances.*

### 3.3 A control that both metrics are sane

Restrict to runs whose own patch is a *single* file that *is* a gold file. There the two target sets
must coincide, and they do: 0.615 vs 0.638, mean absolute gap 0.033 (n = 8,801). Neither definition
is broken; they genuinely measure different things.

### 3.4 The robust measure, and why the shares are not

Both **shares** are fragile to patch composition. The **binary** measure is not:

| own patch width | n solved | n failed | ever reached gold (solved) | (failed) | Δ |
|---|---|---|---|---|---|
| 1 file | 2,555 | 9,070 | 0.992 | 0.691 | **+0.301** |
| 2 files | 593 | 3,688 | 0.963 | 0.734 | +0.229 |
| 3 files | 111 | 1,010 | 0.973 | 0.697 | +0.276 |
| 4+ files | 49 | 809 | 0.694 | 0.621 | +0.073 |

The binary measure is positive in **every** stratum. The share-based gold measure is +0.070 pooled
but only **+0.020** after standardising over patch width — 72% of the gap is composition — and it
flips sign inside strata 2–4. So we quote the binary one and refuse to quote the share.

### 3.5 Three mechanisms tested; all three falsified

We did not accept "the metric is broken" without trying to say *how*. All three attempts failed, and
we report them because the failures are informative:

1. **Confident wrongness** — the idea that a run fixating on a *wrong* file scores high. **Falsified:**
   runs that never reached a gold file score **lower** (0.661) than those that did (0.679), with the
   95% CI excluding zero on the wrong side.
2. **Patch breadth** — failed runs write broader patches (2.20 files vs 1.35), enlarging their own
   target set. **Falsified as the explanation:** standardising over patch width makes the
   self-referential gap *larger* (−0.088 → −0.125), and the gap is already largest in the narrowest
   stratum, where breadth cannot operate.
3. **Fixation** — the metric rewards concentrating edits on one file. **Partly supported, but not the
   mechanism:** failed runs are more fixated (0.779 vs 0.727) and the most fixated runs of all are
   those that never reached the right file (0.818 vs 0.759) — which independently corroborates the
   *Confident and Wrong* warning — but fixation correlates no more with the broken metric (0.251)
   than with the gold metric (0.294).

**So the honest conclusion is a construct-validity one, not a mechanism one.** We can demonstrate
the inversion, prove the metrics agree where they must, and show the correction restores agreement
with the literature. We cannot yet explain it. Three candidate mechanisms were tested and all three
failed; the mechanism remains **open**.

### 3.6 Two independent replications on eight unseen shards

The frozen study used Nebius shards 0–3. Shards **4–7** and **8–11** were separately downloaded and
parsed into their own tables, so no replication touches the frozen artifacts, with gold patches
resolved independently (74.6% and 77.9% coverage). Together the three tables cover **12 of 12 shards
and 80,035 runs**:

| set | shards | runs | `on_target_self` solved → failed | `on_target_gold` solved | failed | within-inst *p* | wrong-fix | *n* |
|---|---|---|---|---|---|---|---|---|
| frozen | 0–3 | 26,679 | 0.594 → **0.670** | **0.477** | 0.407 | 7.0 × 10⁻³ | 67.0% | 16,327 |
| held-out A | 4–7 | 26,680 | 0.593 → **0.677** | **0.492** | 0.421 | 3.6 × 10⁻³ | 69.0% | 15,837 |
| held-out B | 8–11 | 26,676 | 0.614 → **0.686** | **0.512** | 0.415 | **2.8 × 10⁻⁵** | 66.4% | 15,953 |

**All three agree, on three disjoint sets of ~26,000 runs each.** The broken metric inverts in every
one; the gold target reverses it back in every one, with the paired test *strengthening* on the
unseen data (7.0 × 10⁻³ → 2.8 × 10⁻⁵); and the wrong-fix share of failures varies by only **2.6
percentage points**. A result that survives two independent replications on data the study never saw
is not a sampling artefact.

**Scope, stated plainly.** This is **not** a merged 80k-run table. It is full shard coverage as one
frozen table plus two held-out replications — methodologically stronger than a merge, since each
replication is genuinely unseen, but it means the pipeline was never re-run on one 80k table. The
earlier single-table attempt failed (two builds raced on one output file) and that failure is
recorded rather than hidden. **No claim rests on a merged table.**

---

## 4. Where failures actually are

With a target that does not depend on the agent, failure splits mechanically in two:

| failure mode | definition | share |
|---|---|---|
| **WRONG-FIX** | failed, but *did* edit a gold file | **67.1%** (10,947 runs) |
| **LOST** | failed and never edited a gold file | 30.9% (5,380 runs) |

Stable across model scale: 66.8% (Llama-70B), 70.7% (8B), 70.2% (405B), and across instances
regardless of how many files the gold patch touches (64.8–74.0%).

Because the binary measure is stratum-robust while the shares are not, the defensible claim is:

> **98.2% of successful runs and 69.1% of failed runs reach the correct file. Localisation tooling
> can therefore address at most the 30.9% of failures that never get there; the remaining 69.1%
> happen with the agent already in the right place.**

This is a **bounded-lever** claim, and it is weaker than "localisation does not matter" — which is
what our earlier, retracted result implied. The corrected version is also the one that agrees with
the published literature rather than contradicting it.

---

## 5. The causal test

§4 is correlational. A reviewer can answer *"that is selection"*. So we intervened, holding the
defect fixed and changing **only** how easy it is to locate.

**Design.** Real pure-Python packages, no Docker, the packages' own test suites as the verifier.
Three arms, same tasks, same model, same budget:

| arm | manipulation |
|---|---|
| unhinted | a defect exists; find and fix it |
| hinted | told the exact file **and** function — localisation solved by fiat |
| verify | unhinted, plus "after a failed test, re-diagnose before changing more code" |

Predictions were **fixed in advance** from §4, so that a failure could not be reinterpreted after
the fact.

**Two harness faults had to be fixed first, and both were caught by reading transcripts rather than
scores.**

- **65.2% of turns were unparseable.** Our first protocol was ad-hoc text, but the model emits its
  own XML tool-call format regardless. The pilot was measuring *protocol compliance*, not debugging.
  Native function-calling reduced this to 0–4%. This was invisible in the pass/fail column and would
  have silently invalidated everything.
- **The agent was writing its own tests into `tests/`** (`test_debug.py`, `test_aaa_dump.py`), which
  pytest collects. An agent-authored passing test could have scored a run as **successful without the
  defect being fixed.** The verifier is now restored to the package's original tests before final
  grading — as a real grader does. Counts are logged.

**Results.** The larger run used a 48-task suite (8 real packages, 2 arms, 96 episodes, $0.91).
Auditing the raw episode records — not the summary — showed **13 episodes where the task was not
actually broken at the start**, so those are excluded. On the remaining 83:

| arm | n | success | 95% CI | **reached gold** | **success given gold** | turns |
|---|---|---|---|---|---|---|
| hinted | 40 | **0.550** | [0.40, 0.70] | **1.000** | **0.550** | 11.4 |
| unhinted | 43 | **0.372** | [0.23, 0.51] | **1.000** | **0.372** | 12.2 |

**Every run in both arms reached the correct file — and 62.8% of the unhinted runs still failed.**
This is the cleanest form of the entire result: in this suite localisation was never the barrier at
all, and the binding constraint is plainly the fix. It is the causal counterpart of the observational
69.1% / 98.2% gap, under a manipulation that removes search cost entirely.

**P1 held.** Handing over the exact file and function raised success by +17.8 points, and the
*failure-rate* drop, 0.178, is below the 0.309 ceiling §4 predicted in advance.

**The effect is not statistically significant, and we say so.** Fisher's exact test on 40 vs 43
episodes gives **p = 0.126**. P1 was pre-registered as an *inequality about magnitude* precisely so
it could be checked without significance; a reader must not read it as a demonstrated improvement.

**P3 held.** 100% of runs reached the file and a majority still failed. An earlier, smaller run (16
tasks, 3 arms, 50 episodes) gave the same shape and carried the `verify` arm: hinted 0.438, verify
0.353, unhinted 0.235, with success-given-gold of 0.583 / 0.400 / 0.286.

**P2 failed and we report it as a failure.** Telling the agent to re-diagnose after a failed test did
**not** help; hinting was the strongest arm. The most obvious practical intervention this study could
recommend does not work. This is the second time a "spend the budget on verification" intuition has
failed under test in this project.

**A behavioural finding of its own.** In **71 of the 83 valid episodes the agent created or modified
files under `tests/`** — 1,048 files removed by the verifier restore in total. Agents write their own
tests constantly while debugging. Because the verifier is restored before grading, an agent that
"fixes" a test to make it pass is still scored as failing; but the frequency is itself a measurement,
and it is exactly why our first harness would have produced a **wrong success measure**.

---

## 6. A router that works, on a target where the field has no signal

If 69.1% of failures happen in the right file, a runtime system facing a struggling agent should
decide: spend on **search**, or on **verification**? We built a predictor of which situation it is
in, using **only the first 10–60% of a run**.

**Causality and integrity.** The prefix is steps `0…L−1`; the run's total length appears in no
feature. A self-test that overwrites every post-cutoff step confirms all 112 feature columns are
unchanged — it caught a genuine leak, now fixed. Folds are task-disjoint; every method is scored on
identical rows and folds.

| target | 10% | 20% | 40% | 60% |
|---|---|---|---|---|
| failure prediction | **0.693** | **0.721** | **0.721** | **0.731** |
| — position baseline | 0.667 | 0.664 | 0.666 | 0.666 |
| — output-shape (AgentStop-style) | 0.554 | 0.565 | 0.594 | 0.607 |
| **lost vs wrong-fix** | **0.676** | **0.701** | **0.724** | **0.751** |
| — **every** baseline | 0.407–0.493 | 0.411–0.490 | 0.413–0.486 | 0.413–0.539 |

Baselines are beaten in **all 8 cells** with bootstrap CIs excluding zero. On the
lost-versus-wrong-fix target, **every** published-style heuristic is at or below chance: loop
detection, burst detection, redundancy and output-shape carry **no signal at all** about *which kind*
of failure is happening, while our causal model reaches 0.68–0.75.

**We also corrected a claim of our own here.** Our earlier finding that *"step index beats every
learned monitor"* is invalid: at a fixed prefix fraction, the "position" baseline is *exactly the
run's own length*, verified by its AUC matching run length to ≤0.006. It is a hindsight quantity no
online system could use. Against a length-matched control the learned model holds at 0.63–0.76 and
strictly dominates run length.

**Calibration, done honestly.** Our earlier "zero false alarms at every budget" claim was
**circular** — the label and the detector were the same statistic, so the numbers reported were
literally an oracle's. Here labels come from gold patches and detectors from prefix features, with an
explicit null.

| level | achieved false alarms | detection |
|---|---|---|
| α = 0.05 | **0.046** (worst split 0.061) | 0.160 |
| α = 0.10 | 0.078 | 0.258 |
| α = 0.20 | 0.123 | 0.386 |

8 of 8 levels are controlled on the mean. A raw 0.5 threshold flags 98.4% of never-failing runs; the
calibrated rule flags **3.39%**. We also report that a formal sequential e-value test **never fires**
at α ≤ 0.05: valid and powerless.

**The deployable result** is the routing decision. Scoring 1 for a correct route:

| policy | value (λ = 0.25) |
|---|---|
| **this router** | **0.764 – 0.800** |
| always verify | 0.732 |
| random | 0.656 |
| always search | 0.518 |

It wins at every prefix fraction and every cost setting — 12 of 12 cells.

**Limits we state rather than bury:** recall at a 5% alert budget is ≈ 0.058 for *every* method
including the free baseline, because the base rate is 0.837 — the usable output is a **ranking**, not
a tight alarm. Gold matching is basename-only, 4.10% of edit steps carry no filename (biasing LOST
upward), and the prefix cutoff is placed with hindsight so the fully-online claim rests on the
length-matched control.

---

## 7. Two instruments that did not deliver

### 7.1 The taxonomy does not transfer across scaffolds — and this bounds the whole paper

We ported the mechanical labelling to four other corpora, first proving the port faithful by
re-running it on SWE-agent and reproducing the frozen rates **exactly** (absolute difference 0.0 on
all three rates, 236,137 edits, 25,681 runs).

| scaffold | editor footer | kept | revised | **dead_end** | verdict |
|---|---|---|---|---|---|
| SWE-agent (frozen reference) | **0.958** | 0.157 | 0.652 | 0.191 | reference |
| OpenHands (SWE-Gym) | **absent** | 0.734 | 0.229 | **0.037** | does **not** replicate |
| PI agent | absent | 0.821 | 0.060 | 0.118 | does **not** replicate |
| mini-swe-agent-plus | absent | 0.489 | 0.276 | **0.236** | different again |
| multi-framework mix | absent | 0.706 | 0.115 | 0.179 | L1 1.035 |

Two conclusions, both negative and both important:

1. **The instrument depends on a footer that exists in exactly one framework.** `[File: … (N lines
   total)]` appears on 95.8% of SWE-agent edit steps and **0%** of the others. OpenHands names the
   file (`cat -n` header) but never its line count, so an edit's *effect* is unmeasurable there. Every
   mechanical number in this paper is therefore bounded to frameworks that print comparable state.
2. **The dead-end rate is scaffold-specific, not a property of coding agents.** It ranges from
   **3.7% to 23.6%** across scaffolds, a factor of 6. The 19.1% headline is SWE-agent's number;
   it must never be quoted as "coding agents waste 19%".

A scope correction also emerged from the same work: 16.7% of SWE-agent edit steps sit in runs that
produced **no patch at all**. Restricted to runs with a non-empty patch — the strictly comparable
scope — the reference becomes **kept 0.189 / revised 0.624 / dead_end 0.187** (196,651 edits,
22,194 runs). Both scopes are correct for their purpose; only the second is comparable across
scaffolds, and the paper now labels which one every figure uses.

### 7.2 Per-step test outcomes are too sparse to test the central claim

If per-step test results were available, they would be the instrument that could falsify our central
claim. We built the parser and validated it hard: of 730 observations that provably contain test
output, **730/730 recovered a verdict, with zero misses and zero false positives.**

It still cannot answer the question, because **the data is too sparse** — only 0.55% of steps and
4.4% of runs contain a test outcome. SWE-agent rarely runs the project suite, and when it does the
verdict is often off-screen. The instrument does find a real signal — runs that saw a test outcome
passed the evaluator 3.0% of the time against 0.72% for runs that did not, a ~4× effect — but at
4.4% coverage it cannot falsify anything. **Reported as a negative with a signal, not a success.**

---

## 8. What we retracted

Eight claims failed tests written to falsify them. Six are in the appendix of this project's log;
the three headline ones are:

| claim | what happened |
|---|---|
| "Failed runs localise **better**" | **Retracted.** The metric is self-referential and inverts the sign. Corrected result: solved 0.477 vs failed 0.407 on gold. |
| "0 false alarms at every budget" | **Retracted as circular.** The label and detector were one statistic; the numbers were the oracle's. Gap reopened. |
| "Step index beats every learned monitor" | **Retracted.** The baseline *was* the run's length — hindsight, unavailable online. Against a length-matched control the learned model wins. |
| "Waste is essentially unpredictable" | **Weakened.** True for a single monitor (0.539); a fitted multi-channel model reaches 0.590 ± 0.011, positive in all 12 learner/seed/form cells. |
| "84.3% of edits are wasted" | **Corrected to 19.1%.** The larger figure counted revision, which is work. |
| "The waste is not a phase / not diagnostic / not timing-dependent" | Survived, but each required controls that the naive comparison failed. |

We also record the **qualitative thesis is prior art** (§2): the finding that agents fail *after*
reaching the right code is published, at larger scale than our measured sample. Our contribution is
the measurement defect and the bounded-lever quantification, not the phenomenon.

---

## 9. Why the negatives are the contribution

Three of our four headline results are, in an important sense, negative: a widely-used metric is
broken; localisation is bounded to a third of failures; the obvious verification intervention does
not work. We argue this is the correct shape for the result, for two reasons.

First, **the negatives are load-bearing**. "Localisation is capped at 30.9% of failures" is only
meaningful because we can also show 98.2% of successes reach the file. "The field's detectors carry
no signal about failure mode" is only meaningful because our causal model reaches 0.68–0.75 on the
same rows. Each negative bounds a positive.

Second, **the positive result exists and is deployable**: the router in §6 is causal,
reference-free, beats every baseline on identical rows and folds, and has a genuinely controlled
false-alarm rate — the exact property our withdrawn claim lacked. A system that routes a struggling
agent toward verification rather than more searching gains 0.764–0.800 against 0.518–0.732 for the
obvious policies.

And the procedure generalises. The most useful thing we can report to another student is not a
number: it is that we wrote tests to falsify our own headlines, and **they succeeded eight times.**

---

## 10. Limitations

- **n is small in the causal experiment** (16–17 per arm). The robust results are the
  pre-registered inequality (P1) and the conditional success rates (P3), not pairwise p-values.
- **The task suite is single-defect mutations in eight real packages**, not SWE-bench instances. It
  is a controlled instrument, not a benchmark.
- **The mechanical instrument requires a comparable editor footer.** It is demonstrated on
  SWE-agent-style traces and is absent from at least one major alternative corpus; cross-framework
  generality is **not** claimed.
- **The inversion's mechanism is unexplained.** Three candidates were tested and all failed.
- **Gold matching is basename-based**, and 4.10% of edit steps carry no filename, which biases the
  LOST share upward.
- **The prefix cutoff uses hindsight** (`L = round(f · n_steps)`), so the fully-online claim rests on
  the length-matched control.
- **Per-step test outcomes are too sparse (4.4% of runs)** to test the central claim, so the
  observable-channel limit remains asserted rather than falsified from within this data.
- **Temperature-0 inference is not deterministic**: published measurement finds ~9% of per-instance
  outcomes flip across repeat runs, which is why the observational within-instance split is reported
  with runs-per-instance (mean 21.9).

---

## 11. Reproducibility

Every quantitative claim in this document is emitted by a script from a frozen artifact; none is
typed by hand. Five automated gates run on every change:

| gate | result |
|---|---|
| invariant tests | 11 / 11 |
| cross-artifact consistency + staleness | passes |
| headline claims vs the artifacts that produced them | 28 / 28 |
| one-page summary vs artifacts | 0 mismatches |
| every cited artifact exists | all present |

Corpora: SWE-agent trajectories (12 shards, 80,036 trajectories) with gold patches for 927
instances; Terminal-Bench trajectories (2 shards, 52,104 trials). Models: DeepSeek V4.1 Flash via
the OpenCode Go gateway, temperature 0, total live-experiment spend **$0.40**, every call logged.

---

## 12. Use of AI tools

A large language model (DeepSeek V4.1 Flash) was used as a **research assistant** throughout: to
write analysis code, to run statistical tests, to fetch and verify literature, and to draft this
manuscript. It also served as the *subject* of the causal experiment in §5.

It was **not** used to generate data. All measurements come from public trajectory corpora and from
real test suites executed locally. **Eight of its own claims were retracted when falsification tests
succeeded**, and every retraction, bug and reversal is recorded in the project's assistance log with
the evidence that caused it. The retraction ledger in §8 is a direct product of that record.

The authors reviewed all code, verified all citations against primary sources, and take
responsibility for the final claims.
