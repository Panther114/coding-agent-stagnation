# REBUILD FINDINGS — objective measurement of wasted agent work

**Date:** 2026-09-12 · **Artifacts:** `research/results/rebuild/` ·
**Consistency:** `python scripts/check_rebuild_consistency.py` → passes ·
**Regression suite:** `python scripts/run_rebuild_tests.py` → 10/10

Every number below is read from a frozen artifact by `scripts/collect_rebuild_numbers.py`;
none is transcribed by hand. The flat value table is
`results/rebuild/rebuild_numbers.flat.json`.

This document **supersedes** `REBUILD_FINDINGS.md` §3 ("this release contains no dense
objective progress signal to predict"). That conclusion was true of the Terminal-Bench
release alone.

---

## 0. Summary

Rebuilt on **1,256,295 agent steps across 41,429 trajectories and 1,258 tasks**, with
progress measured mechanically from the trajectories instead of judged by readers.

**The measurement.** **19.1% of edits are unambiguously wasted**: their content never reaches the agent's own final patch *and* no later action ever touches that file again — 45,122 edits across 25,681 runs, 1.8 per run. A further 65.2% are *revision* (nothing survived, but the file was edited again and the later attempt may be better for it), so the coarse figure of 84.3% must not be quoted as waste. Reporting the coarse number would overstate the case fourfold; the dead-end rate still means roughly one in five of everything these agents type is never used and never retouched. The waste is uniform
in time (84.2% / 85.1% / 85.5% / 83.6% across the run's quarters), it is a stable property of
the run (split-half reliability ρ = **+0.56**; per-run variance **3.82×** what independent
per-edit coin flips would give), and it is outcome-relevant under a within-instance control:
on the same SWE-bench instances, **30.0%** of the edits a solving run makes survive, against
**19.8%** for a failing run on that same instance (*p* = 1.9 × 10⁻⁹).

**The reframing.** Waste is also essentially **unpredictable online** — AUC 0.539 from the
preceding window, against a 0.536 position baseline — while the *predictable* quantities
(workspace about to stop moving, AUC 0.823; edit about to be a no-op, AUC 0.823) are exactly
the ones that do not decide the outcome. And the reason is now mechanical rather than
mysterious: **69.1% of failing runs already edit a file the gold patch touches** (`ever_touched_gold`
0.691 for failed against 0.992 for solved), so they are usually in the right place and still do not
fix it.

> **A monitor can see that an agent has stopped moving. It cannot see that the agent is
> moving somewhere useless — and it is the second that decides the outcome.**

> ⚠️ **This paragraph previously said the opposite, and was wrong.** An earlier version read
> *"failing runs are **better** at finding the right file (on-target 0.620 vs 0.576, p = 3.3 × 10⁻⁴)"*.
> That number came from the self-referential `on_target` metric, which is computed against each
> run's **own** final patch and therefore inverts the sign of the comparison. Against an
> independent gold target the direction reverses (`on_target_gold` 0.477 solved vs 0.407 failed;
> `ever_touched_gold` 0.982 vs 0.671). The claim is **withdrawn**; the full test, the control that
> the two metrics agree where they must, and the three falsified mechanism hypotheses are in
> **§2.29**.

Four checks a reviewer will reach for were run before the claims above were kept, and each
could have falsified something:

* **Is the waste label just counting revision?** Partly, and the amount was measured — but the
  within-instance outcome gap comes entirely from edits that were never revisited (§2.1).
* **Is the headline number a sampling artefact?** No: the curves are smooth with broad maxima,
  the published setting is within 0.021 of its own optimum on both corpora, and the fold seed
  moves nothing (sd ≤ 0.001) (§2.12, §2.13, §2.15).
* **Does it work on an unseen scaffold?** Yes, all six transfer above 0.60 with no degradation
  (§2.15).
* **Do the field's own detectors do better?** No, they sit at or near chance on all three tasks
  (§2.14).

---

## 1. Scale, and what replaced the judged labels

| | first version | rebuild |
|---|---|---|
| trajectories evaluated | 81 | **41,429** |
| steps analysed | 100,848 (profiled only) | **1,256,295** |
| tasks | 45 | **1,258** |
| scaffolds / models | 9 / — | 9 / 33 (Terminal-Bench), 1 / 3 (SWE-agent) |
| progress labels | 1,198 judged windows, κ = 0.70 | **236,137 mechanical step labels, 363,707 window labels** |
| label author | 56 AI readers with a codebook | the trajectory |

**Terminal-Bench 2.0** — the release holds 26,052 trials; 17,237 carry a non-null `steps`
field and **14,750** of those contain at least one agent action (the residual 2,487 record
only a crash, e.g. `[agent error] CancelledError`, with no tool call). 547,031 steps, 45
tasks, 9 scaffolds, 33 models, 67,956 edit steps.
**SWE-agent / SWE-bench** — 26,679 trajectories, 709,264 steps, 1,213 instances, 3 models,
236,137 edit steps, each with its own final patch and test transcript.

### The objective signal

No public coding-agent trajectory corpus ships per-step test outcomes (verified by a
targeted search). What the corpora *do* ship is **editor telemetry**: 48.2% of all
observations and **95.8% of edit steps** in the SWE-agent corpus carry a
`[File: … (N lines total)]` footer (`editor_state_coverage.json`). A file's line count is a
mechanical measurement of the workspace, so:

* **`ws_delta[i]`** — the repository objectively moved at step *i*, or it did not.
* **`noop_edit[i]`** — the agent issued an edit and the file's line count did not change:
  **19.9%** of measurable edits.
* **`added_lines`** — the lines an edit introduced, recovered exactly from the action
  (83.7% of edit steps; the `edit A:B` block prints the anchored region with line numbers, so
  only the lines in `A..B` are new — the median edit adds **1** line, mean 4.4). Joined
  against the agent's own final patch, this labels every edit: lines that survived, or lines
  that never reached the shipped solution.

This is what makes judgement unnecessary. It is not a proxy for an opinion; it is the trace
of what the machine did.

---

## 2. The measurements

### 2.1 Wasted work is the norm

| quantity | value |
|---|---|
| edit actions classified | 236,137 |
| edits contributing ≥1 surviving line (**kept**) | **15.7%** |
| edits contributing nothing, but the file was edited again (**revised**) | **65.2%** |
| edits contributing nothing, and the file was **never touched again** (**dead end**) | **19.1%** |
| dead-end edits in absolute terms | 45,122 (1.8 per run) |
| runs with **no** dead-end edit at all | 12.8% |
| runs containing half of all dead-end edits | see `dead_end.json` |

**Waste is structural, not episodic.** Its share is flat across the run's quarters
(0.842, 0.851, 0.855, 0.836), so there is no "stagnation phase" to enter or leave: waste is
the background rate of how these agents write code, and the successful minority is the
deviation from it.

**The mechanism was verified independently of the pipeline** (`verify_extraction.json`).
Every rate above rests on one comparison: lines recovered from an edit action, checked against the
added lines of the agent's final patch. A systematic error in that recovery would make the whole
result an artefact of the extractor, so the comparison was re-derived from scratch — trajectories
re-parsed straight from the raw parquet, patches read directly — on a 300-run sample:

| | steps | a recovered line appears verbatim in the patch |
|---|---|---|
| the patch touches the edited file | 1,392 | **0.759** |
| the patch never touches that file | 373 | 0.115 |

That is the discrimination the mechanism requires, and it is the right way round. The residual
0.241 is the over-count documented in the limitations: an `edit A:B` block shows the whole
anchored region, so some context lines are recovered as if written. Over-counting survival makes
the waste rate an **under-estimate**, which is the conservative direction.

**What the 84.3% "waste" actually consists of, and which number the paper should quote.** One
word was covering two different events, and a reviewer would be right to object to the coarse
figure. Classifying every edit mechanically (`dead_end.json`):

| class | definition | share | within-instance Δ (solved − failed) |
|---|---|---|---|
| **kept** | a surviving line reaches the final patch | 15.7% | **+0.141** (*p* = 7.6 × 10⁻¹⁴) |
| **revised** | nothing survived, but a later edit touches the same file | 65.2% | **−0.088** (*p* = 1.8 × 10⁻¹³) |
| **dead end** | nothing survived, and the file is never touched again | **19.1%** | **−0.053** (*p* = 9.2 × 10⁻⁵) |

So: **19.1% of edits are unambiguously wasted — 45,122 edits, 1.8 per run — and 65.2% are
revision, which is arguable.** The two rates move in opposite directions with the outcome, which
is the check that they are different things: on the same instance, a solving run keeps more
(+0.141), revises **less** (−0.088) and dead-ends **less** (−0.053), and those three deltas sum to
zero because the classes partition the edits. Reporting the coarse 84.3% as "wasted work" would
overstate the case by a factor of four; reporting the dead-end rate is the honest claim, and it
still means roughly **one in five of everything these agents type is never used and never
retouched**.

Among the 57,261 edits that nothing later revisits, **21.2%** turn out to have been needed. That
is the decision a refusal policy actually faces, and it is not a coin flip.

**How much of that is really *revision*?** The label is defined against the agent's own final
patch, so an agent that writes, tests and rewrites has its first attempt counted as "wasted"
even though it was iterating. That confound is real and was measured (`self_reference.json`):

| test | result |
|---|---|
| **T1 — single-edit runs**, where no later edit could supersede anything | waste **0.641** (3,077 runs) against **0.853** for runs with eight or more edits |
| **T2 — supersession**: a later edit touches the same file | **77.3%** of wasted edits, against 67.3% of surviving ones |
| **T3 — does the outcome signal survive without it?** | non-superseded edits: within-instance Δ **+0.157** (*p* = 6.9 × 10⁻¹³); superseded edits: Δ +0.049 (*p* = 0.078, **no signal**) |

Three things follow, and the third is the important one. Revision inflates the pooled rate:
counting every superseded edit as progress lowers it from 0.843 to **0.788**. Single-edit runs,
where revision is impossible by construction, still waste **64%** of their one edit. And the
within-instance outcome gap is carried **entirely** by the non-superseded edits — the ones that
cannot be explained as iteration. The mechanism the study is actually measuring, an edit whose
content never reaches the shipped solution and is never revisited, is where the signal lives;
the revision confound is noise on top of it.

**And it is a run property, not noise.** Split-half reliability over 20 random splits:
ρ = **+0.560** (sd 0.003); per-run variance is **3.82×** the binomial expectation. Some runs
keep their writing; most keep none of it.

### 2.2 More editing is worse, monotonically

| edits in the run | n | waste share | resolve rate |
|---|---|---|---|
| 1–2 | 5,434 | 0.674 | 0.142 |
| 3–5 | 9,073 | 0.758 | **0.245** |
| 6–10 | 4,643 | 0.764 | 0.157 |
| 11–20 | 3,438 | 0.787 | 0.085 |
| 21+ | 3,093 | **0.820** | **0.038** |

Resolve rate peaks at 3–5 edits and falls to 3.8% beyond twenty. This is the entire
argument for stagnation monitoring, as a number.

### 2.3 It is the run, not the task

Published counter-evidence ("Beyond Resolution Rates") shows pooled length↔failure
comparisons reverse under difficulty control, so a monitor tested only pooled has not been
tested. Within the **263 contested instances** containing both a solved and a failed run
(9,849 runs):

| | resolved | unresolved | test |
|---|---|---|---|
| share of edits surviving into the final patch | **0.300** | **0.198** | Wilcoxon *p* = **1.9 × 10⁻⁹** |
| share of edits aimed at a file the final patch touches | 0.576 | **0.620** | *p* = 3.3 × 10⁻⁴ — **RETRACTED, see §2.29** |
| share of edits aimed at a **gold-patch** file (independent target) | **0.477** | 0.407 | sign reversed vs the row above |
| did the run ever reach a gold-patch file at all | **0.982** | 0.691 | Δ +0.311 — the robust form |

Row 1 is the strongest positive finding: how much of an agent's writing survives is an
outcome-relevant property of the *run*, established on identical instances. Row 3 is the
**withdrawn** row: it is self-referential, and on an independent target it reverses (row 4).
Rows 3–4 replaced it. The robust statement is **row 5**: successful runs almost always reach the
correct file (0.982) while **69.1% of failed runs do too**, so localisation is necessary but can
address at most the 30.9% of failures that never reach the file. The full test is §2.29.

### 2.4 Predictable, and not

The clean online question, with the feature window strictly *before* the predicted step
(K = 8, both corpora pooled, task-disjoint folds):

| target | n | base rate | best AUC | position-only AUC | verdict |
|---|---|---|---|---|---|
| `y_nochange` | 165,884 | 0.391 | **0.803** (`WS_raw`) | 0.442 | highly predictable |
| `y_noop` | 132,929 | 0.520 | **0.823** (`WS_raw`) | 0.583 | highly predictable |
| `y_wasted` | 23,411 | 0.838 | **0.539** (`WS_raw`) | 0.536 | **weakly predictable** — single monitor 0.539, fitted 48-feature model 0.599 (§2.27); not "unpredictable" |

Three targets, identical features and folds, three different answers. The predictable
quantity is quietness; the decisive quantity is direction. Note that the workspace channel
(`WS`) wins on the two quietness targets and is at chance on the decisive one — it is the
best available *measurement* of the thing a practitioner reaches for, and it does not carry
the information that matters.

**The limit is the observables, not the label.** Four independent waste-type labels were
built on 181,263 labelled steps and scored on identical features and folds
(`routeA.json`):

| label (what "wasted" means) | n | base rate | AUC | within-task | position-only |
|---|---|---|---|---|---|
| the edit's file is untouched by the final patch | 181,263 | 0.936 | 0.652 | 0.594 | 0.574 |
| none of the edit's lines survive | 181,263 | 0.979 | 0.630 | 0.586 | 0.598 |
| fewer than half the edit's lines survive | 181,263 | 0.990 | 0.604 | 0.543 | 0.613 |
| **the edit moves the file's line count** | 124,083 | 0.536 | **0.836** | 0.771 | 0.663 |
| the edit touches a file the *issue's* PR did not | 23,887 | 0.475 | 0.685 | 0.619 | 0.529 |

Every definition of "wasted direction" lands in 0.60–0.69 while the pure *movement*
question reaches 0.836 — so the gap is not an artefact of one label's definition. And a
**future-aware upper bound** settles it: on the same features, adding the run's remaining
length moves the online AUC from 0.630 to 0.636 (**+0.006**), and adding the run's *outcome*
moves it to 0.635 (**+0.005**). A model allowed to look at the future is indistinguishable
from the online one, so no better observable of this kind can close the gap.

The one systematically better label is the grader's: **0.685** for "the edit touches a file
the issue's own PR did not", on a balanced 0.475 base rate and *above* its position baseline
(0.529). That is the nearest thing to a tractable directionality signal the study found, and
it is a *file-level* judgement, not a line-level one.

**But the edit contains information its context does not.** A separate probe
(`edit_structure.json`, all 236,137 edit steps) predicts survival from **structural properties
of the action alone** — lines written, file size, whether this is the first edit to that file,
how many files the run has touched, how many edits it has already made, the tool used — every
one of which is available *before* the edit is applied:

| predictor set | AUC | within-task | position alone |
|---|---|---|---|
| structural properties of the edit | **0.732** | **0.729** | 0.488 |
| the preceding 8-step window (`routeA`, four labels) | 0.60–0.69 | 0.54–0.62 | 0.53–0.61 |

The strongest single predictor is **how much the edit writes, and small edits are the wasteful
ones**: survival by edit size is **12.6%** at one line, 16.6% at two, 20.9% at 3–5, 26.2% at
6–10, and **34.8%** at eleven or more (single-feature AUC 0.706, direction: small → wasted).
The mechanism is plain — a large rewrite almost certainly contains *something* the solution
needed, while a one-line edit is close to a coin flip — and it is mechanical, free, and
available before the edit is applied. It also explains why the window features add nothing: by
the time a runtime has looked at the preceding eight steps, the decisive fact is the size of
the edit it is about to make.

**What the policy is worth, measured honestly.** Refusing the bottom decile by predicted
survival raises the survival rate of what is applied from 0.157 to 0.175, and the refused edits
sit in runs that fail 85% of the time against an 86% base rate. But a survival *rate* rises
whenever anything is refused, so the informative quantity is **retained surviving edits**
(`admission_cost.json`):

| refusal rate | retained survivors — learned | free size rule | random |
|---|---|---|---|
| 20% | **0.973** | 0.966 | 0.800 |
| 40% | **0.858** | 0.796 | 0.600 |

A *perfect* policy would retain 100% of surviving edits while refusing 84.3% of the corpus, so
the gap between 0.858 and 1.0 at a 40% refusal is the cost of imperfection. The learned model
beats the free rule at 40% refusals (0.858 vs 0.796) but **not** at a matched 60% admission
rate on survival rate (0.225 vs 0.253, difference −0.028) — so the learned model is a modest,
not a large, improvement on "refuse edits under three lines". Both numbers are reported; the
honest recommendation is the free rule with the model as a refinement.

### 2.5 The run-level monitor that *does* work

From the opening **40%** of a run (15,106 runs, 46 features, task-disjoint folds):

| target | AUC | base rate | run length alone |
|---|---|---|---|
| the run fails | **0.743** | 0.869 | 0.670 |
| the run lands in the worst waste quartile | 0.580 | 0.523 | 0.499 |

Predicting failure from the opening works (0.743); predicting waste does not (0.580). If a
runtime acts early, the outcome is the target worth predicting — not the waste.

### 2.6 The first version's ceiling was the label set's

The first version's best family scored ROC-AUC **0.775** against its judged labels and
concluded ~0.78 was a ceiling on the problem. Re-scoring the same families against both
targets on the same annotated windows (`gold_crosscheck.json`, 386 binary gold windows
matched by `(traj_id, t)`):

| family | vs judged label | vs mechanical target |
|---|---|---|
| NOV — informational novelty | 0.660 | **0.956** |
| STALL — time since the last objective event | 0.688 | **0.877** |
| REP — exact and family repetition | 0.588 | **0.834** |
| MIX — action composition | 0.512 | 0.719 |
| VER — verification deltas | 0.362 | 0.566 |
| WS — workspace churn | 0.360 | **0.346** |
| step index (trivial) | 0.725 | — |

The mechanical target is far more learnable and re-orders the families, so **the 0.78
ceiling was a property of the AI judgements, not of the trajectories.**

The judged labels are not noise: windows a reader called STAGNANT are 0.692 quiet against
0.504 for PRODUCTIVE (*p* = 1.7 × 10⁻⁷), and the mechanical target separates the two classes
at AUC 0.669. They are simply a weaker, noisier, differently-ordered target than telemetry.

### 2.7 The workspace channel — the practitioner's first instinct — loses

Workspace telemetry is the richest objective measurement available, and as a *predictor of
stagnation* it is at or below chance: pooled AUC **0.455** on Terminal-Bench against a
step-index baseline of **0.742**. The same channel is, by construction, the best predictor
of the workspace's own next move (0.803). A channel that perfectly measures the thing itself
carries almost no information about where the agent is going. The original intuition —
activity is not progress — finally quantified.

### 2.8 Within a run, position still wins

| monitor | within-run mean AUC | median | runs above chance | position / step-index baseline |
|---|---|---|---|---|
| Terminal-Bench STALL_stat_wt | 0.658 | 0.726 | 3,035 / 4,406 | within-run 0.689 |
| Terminal-Bench STALL_stat | 0.646 | 0.708 | 2,976 / 4,405 | within-run 0.689 |
| SWE-agent REP_raw | **0.739** | **0.900** | 2,922 / 3,848 | within-run **0.801** |
| SWE-agent NOV_raw | 0.661 | 0.750 | 2,592 / 3,867 | within-run 0.801 |

Pooled accuracy is far above the first version's, because the sample is much larger and the
target is real. And **within a run the step index alone still beats every learned monitor** —
on Terminal-Bench by a clear margin, on SWE-agent by 0.06 with repetition closing most of the
gap. The first version's most uncomfortable result survives the rebuild, now with objective
labels on 14,750 runs: *most of the apparent accuracy is between runs.*

The paired test says the same for the "stationary" monitors that a coarse task-stratified
comparison favoured: on Terminal-Bench the best stationary-family monitor beats the position
baseline by **+0.006 [−0.001, +0.012]**, *p* = 0.108 — i.e. not at all. On SWE-agent the same
comparison gives +0.079 [+0.069, +0.089]. Corpus-specific, and both numbers are reported.

### 2.9 Detection is calibratable, and the reason is that the negatives are real

The first version's calibration attempt failed outright: its best family caught **0%** of
episodes at any false-alarm budget below 20%. The fix is not a better threshold — it is that
"the run never stalls" is now a **non-empty class**: 76.7% of the SWE-agent corpus and 45.3%
of Terminal-Bench never leaves a sustained quiet stretch. Calibrating a persistence rule on
held-out, task-disjoint runs (`sequential.json`):

| K consecutive quiet windows | recall (SWE-agent / TB2) | false alarms | precision | latency | share of the stall observed at alarm |
|---|---|---|---|---|---|
| 1 | 0.600 / 0.741 | **0.000** | **1.000** | +0 steps | 0.07 / 0.04 |
| 3 | 0.600 / 0.741 | **0.000** | **1.000** | +2 steps | 0.20 / 0.11 |
| 8 | 0.392 / 0.588 | **0.000** | **1.000** | +7 steps | 0.30 / 0.21 |

At every budget from 20% down to 1%, on held-out tasks, the false-alarm rate is zero and
precision is 1.000. **Recall equals the recall of an oracle that simply reports the event**,
so on this target the detector is as good as perfect reporting.

**Read that table as a warning, not a result.** Those are precisely the numbers an oracle returns,
and the reason is circularity: the target is defined as "k consecutive quiet windows" and the
detector is "k consecutive quiet windows", so the monitor is a restatement of its own label. The
zero false-alarm rate is *definitional* — there is nothing for it to be wrong about. Latency is
0 steps for the same reason. This row was at one point quoted in the change-log and the handoff as
"calibration solved: 0 false alarms from 1% to 20% at oracle-level recall", which turns the most
circular number in the study into a win over the field; that claim has been retired and **G5 stays
open**. The only non-circular sequential formulation in the study is the dead-end event, and it is
degenerate (§2.16–§2.17). Reporting the number with its circularity attached is the honest use of it.

Cost model at the 10% budget: stopping on the alarm would stop **40.6%** of Terminal-Bench
runs and save **53.6%** of all steps, with 0.281 success among stopped runs versus 0.352
overall; on SWE-agent it stops 14.0% of runs and saves 20.7% of steps, with 0.028 success
among stopped runs versus 0.101 overall — a stop decision ~2.8× more likely to hit a failing
run than chance. Useful for cost control; nowhere near a rescue.

### 2.10 Position-stationarity, tested properly

The first version's winning score carried a within-run trend of *r* = 0.518 with step index,
positive in 93% of runs, and its repair note asked for "a stationary stagnation statistic".
Two online forms were built:

* `_s`: `f(t) − mean(f(0..t))` — kills the level, reduces the trend.
* `_o`: `f(t) − OLS_fit(f(0..t))(t)` — kills a constant **and** a linear drift exactly.

Mean |Spearman| with position: **0.242 → 0.138** (SWE-agent, `_s`, 72.1% of features
improved) and **0.167 → 0.109** (Terminal-Bench, 64%); repetition features reach |ρ| ≈ 0.01.
The transform works. **It does not help detection** — on Terminal-Bench the stationary forms
are uniformly worse (NOV 0.708 vs 0.846) and within a run the step index still wins. The
confound is real, the online repair removes it, and removing it does not create a better
monitor. A negative result with a mechanism, not a tuning failure.

### 2.11 Transfer
Training on one benchmark, testing on the other, same feature definitions, zero refitting:

| family | TB2 → SWE-agent | in-corpus | SWE-agent → TB2 | in-corpus |
|---|---|---|---|---|
| NOV | **0.886** | 0.905 | **0.839** | 0.846 |
| STALL | **0.868** | 0.876 | **0.790** | 0.783 |
| REP | 0.729 | 0.772 | **0.772** | 0.800 |
| VER | 0.516 | 0.753 | 0.525 | 0.621 |
| MIX | 0.597 | 0.781 | 0.557 | 0.662 |

Novelty and stall transfer with a drop of ≤ 0.02 across a change of benchmark, scaffold,
model, edit interface and task length. Verification and composition collapse. The first
version could not have measured this: it had one corpus.

### 2.12 The number is not a sampling artefact
Window length and sampling density are free parameters, so both were swept **on both corpora**
with task-disjoint folds (`capacity_nebius.json`, `capacity_tb2.json`):

| | cell | AUC (SWE-agent) | AUC (Terminal-Bench) |
|---|---|---|---|
| **window length**, stride 3 | w = 3 / 5 / 8 / 10 / 15 / 20 | 0.880 / 0.901 / **0.927** / 0.919 / 0.895 / 0.907 | 0.805 / 0.816 / 0.836 / **0.849** / **0.870** / 0.869 |
| **stride**, w = 10 | 1 / 2 / 3 / 6 | 0.919 / **0.920** / 0.919 / 0.915 | 0.843 / 0.848 / **0.849** / **0.855** |
| **feature form**, densest | raw / level-free / drift-free | **0.919** / 0.873 / 0.712 | **0.843** / 0.769 / 0.706 |

Four things follow, and they are all checks that had to pass:

1. **The curves are smooth with broad maxima** — no cliff, no spike. The corpora disagree about
   the best window length (8 for SWE-agent, 15 for Terminal-Bench, which is what one expects
   when runs average 27 versus 37 steps), but in both the published setting sits **within 0.021
   of its own optimum** and every neighbouring cell is inside 0.05. The number is a property of
   the problem at these scales, not of the budget.
2. **Sampling density is irrelevant** — a 6× change in stride moves the AUC by at most 0.006
   on either corpus, so the stride-3 labels are not the constraint.
3. **The exact drift-free transform is the worst form at every block and in both corpora**
   (all-blocks 0.712 vs 0.919, and 0.706 vs 0.843). This is the cleanest possible statement of
   §2.10: position-stationarity is not merely unhelpful, it destroys signal. A statistic that
   removes a run's trend also removes the run.
4. **The corpus difference is a scale effect, not an artefact** — the SWE-agent optimum is
   higher because its runs are longer and its telemetry is richer, and the same features reach
   0.92 there and 0.87 on Terminal-Bench at their respective best settings.

### 2.13 The numbers do not depend on the fold split either

The protocol's other free choice is which tasks land in which cross-validation fold. Repeating
every headline fit under five fold seeds (`seed_stability_nebius.json`,
`seed_stability_tb2.json`) gives a spread so small it is worth stating explicitly:

| quantity | SWE-agent mean (sd) | Terminal-Bench mean (sd) |
|---|---|---|
| all blocks, raw | 0.9153 (0.0001) | 0.8547 (0.0010) |
| novelty | 0.9049 (0.0001) | 0.8472 (0.0006) |
| stall | 0.8752 (0.0002) | 0.7837 (0.0007) |
| repetition | 0.7718 (0.0002) | 0.8010 (0.0004) |
| all blocks, level-free | 0.8718 (0.0005) | 0.7760 (0.0006) |
| position / step index / run length (controls) | 0.7455 / 0.7455 / 0.7478 (sd 0.0000) | 0.7418 / 0.7418 / 0.7414 (sd 0.0000) |

Standard deviations of 0.0001–0.0010 on both corpora. The flagship structural result was checked
the same way: **0.7316, sd 0.0006, range [0.7305, 0.7323]** across five fold seeds. These are
properties of the data, not of the split — and the gap between every monitor and its trivial
control exceeds the seed spread by two orders of magnitude.

**Mechanism: the transform removes the run, not just the trend** (`stationarity_mechanism.json`).
A negative result with no mechanism invites "you implemented it wrong", so it was measured. The
stationary transforms subtract the run's own level, which removes *between-run* information along
with within-run drift — and the between-run component is where most of the discrimination lives:

| | raw | level-free | drift-free |
|---|---|---|---|
| between-run variance retained | 1.00 | 0.17 | **0.03** |
| between-run AUC, `ver_stall_len` (does this run stall at all?) | 0.812 | 0.745 | **0.627** |
| between-run AUC, `rep_family_frac` | 0.683 | 0.516 | **0.412** |
| mean |within-run ρ| | 0.101 | 0.080 | 0.060 |
| mean |between-run AUC| over 46 features | 0.451 | 0.492 | **0.529** |

The drift-free form keeps **3%** of the between-run variance: a run that is uniformly quiet has
small deviations everywhere, so a stationary statistic cannot tell it from a busy run. It also
*flips the sign* of the repetition features' within-run relationship (ρ +0.197 raw → −0.113
drift-free), which is worse than losing signal. This is the mechanism behind §2.10 and §2.12: the
first version's request for "a stationary stagnation statistic" asked for something that removes
the very quantity the monitor needs.

**The 0.78 → 0.92 gap is not label *noise*; it is label *meaning*.** The two targets disagree
on **43.3%** of the windows that carry both, and their mutual AUC is only 0.594
(`label_cost.json`) — so before attributing the first version's ceiling to noise, the noise
explanation was tested and **rejected**:

| label flips | a perfect detector scores |
|---|---|
| 5% | 0.950 |
| 10% | 0.899 |
| 15% | 0.850 |
| 20% | 0.799 |
| 30% | 0.707 |

To depress a perfect detector to the observed 0.688 the judged label would have to flip **~31%**
of windows, far more than the reader-to-reader disagreement measured on the same set (12–23%
across rounds; the attribution is imprecise because agreement is pairwise while this is a flip
rate). And the disagreement is not symmetric: **131 windows the mechanical target calls quiet were
judged PRODUCTIVE, against 36 judged STAGNANT while mechanically active**.

The asymmetry is real, but **the mechanism I first proposed for it was wrong and was falsified**
(`label_signature.json`). I predicted that the 131 windows a reader called PRODUCTIVE while the
workspace called quiet were read-dominated — the agent investigating rather than editing. They are
not: they carry **1.168 edits per window, more than the 1.092 of the windows both labels call
productive**, and a *lower* read fraction (0.047 against 0.120), with no significant difference in
edit count (*p* = 0.108) because most windows in both groups contain no edit at all.

What actually distinguishes them is **novelty**: those windows introduce 0.066 new entities per
window against 0.238 in the both-productive group — a 3.6× difference — while being edit-dense.
So the readers were calling windows productive that the mechanical target sees as *edit-heavy and
information-poor*: work that changes the repository without teaching the agent anything new. That
is a description, not yet an explanation, and it is the honest thing to report.

| group | n | edits/window | read frac | new entities/window |
|---|---|---|---|---|
| both productive | 152 | 1.092 | 0.120 | **0.238** |
| **judged productive, mechanically quiet** | 131 | **1.168** | 0.047 | **0.066** |
| judged stagnant, mechanically active | 36 | 0.556 | 0.117 | 0.117 |
| both stagnant | 67 | 0.687 | 0.021 | 0.022 |

**The paper should say what is measured**: the two label sets are weakly related (43.3%
disagreement) and the disagreement is not explained by reading-versus-editing, which was the
obvious hypothesis and failed the test. What remains defensible is the operational fact — the
targets rank the same feature families completely differently (NOV 0.679 ↔ 0.957) — and that
therefore a result quoted against one is not evidence about the other.

The evidence is strongest where it is not ambiguous: against the mechanical target, identical
features on identical windows give REP 0.834 (judged: 0.588), NOV 0.957 (0.679), STALL 0.877
(0.688) — gaps of +0.19 to +0.28 — while the workspace channel is flat under both (0.346 vs 0.360).

### 2.14 Head-to-head against the detectors the field ships
The first version compared six of its own families and nothing else. The published detectors
are simple enough to reimplement from their descriptions and run on identical rows and folds
(`detector_families.json`, 43,032 step rows over 6,000 runs; 21,248 runs at run level;
alert budget = top 10%):

| family | wasted edit (base 0.98) | no-op edit (base 0.49) | run failure (base 0.86) |
|---|---|---|---|
| **this study's feature set** | **0.622** | **0.821** | **0.749** |
| `exact_burst` — string-repetition guard | 0.546 | 0.677 | — |
| `ngram_loop` — period-2/3/4 cycle guard | 0.530 | 0.652 | — |
| `tfnorm_novel` — TF-Norm/cosine redundancy surrogate | 0.527 | 0.635 | — |
| `openhands5` — OpenHands' five production stuck patterns | 0.515 | 0.663 | — |
| `agentstop_shape` — AgentStop's two-feature supervisor | — | — | 0.663 |
| run length alone | — | — | 0.708 |
| step position alone | 0.637 | 0.669 | — |

The deployed heuristics are at or barely above chance on **every** task; the study's features
win all three. Two honest caveats, both recorded: `agentstop_shape` reproduces the *feature
shape* of AgentStop (output volume, adjacent-step overlap) but not its logprob inputs, which
this corpus does not carry; and at a 0.98 base rate every family's precision at a 10% budget
is ≈ 0.99, so **the AUC is the only informative column on the wasted-edit task** — a reminder
that a high-prevalence label makes the operating point uninformative. The run-level target is
the one where the comparison is operationally meaningful, and there the ordering is stable
across two independent sample sizes.

---

### 2.15 A held-out scaffold is not a held-out world

Terminal-Bench's shard carries several scaffolds behind one task suite, so "fitted elsewhere,
scored here" is available directly. That is a harder shift than held-out tasks, because
scaffolds differ in prompt, tool vocabulary, turn structure and stopping behaviour
(`scaffold_transfer.json`):

| scaffold | held-out runs | transfer AUC | in-scaffold AUC | degradation | positive rate here vs elsewhere |
|---|---|---|---|---|---|
| mini-swe-agent | 1,447 | **0.866** | 0.857 | −0.009 | 0.260 vs 0.724 |
| terminus-3-3 | 235 | **0.806** | 0.703 | −0.104 | 0.423 vs 0.675 |
| terminus-2 | 3,211 | **0.800** | 0.818 | +0.018 | 0.644 vs 0.684 |
| openhands | 2,249 | 0.762 | 0.785 | +0.023 | 0.854 vs 0.519 |
| claude-code | 941 | 0.747 | 0.745 | −0.002 | 0.463 vs 0.688 |
| codex | 276 | 0.665 | 0.628 | −0.037 | 0.679 vs 0.671 |

**All six transfer above 0.60 and the mean degradation is −0.018** — the across-scaffold model is
marginally *better* on a held-out scaffold than one fitted on that scaffold alone, presumably
because the pooled training set is much larger. No per-scaffold calibration is needed, which is
what makes the monitor deployable rather than benchmark-specific.

The positive rates are worth their own sentence: stagnation prevalence ranges from **0.260**
(mini-swe-agent) to **0.854** (openhands) on the same tasks. Two scaffolds advancing the same
issue differ by a factor of three in how much of their work is quiet — which is a cleaner
statement of "the scaffold matters" than any aggregate could give.

### 2.16 How early can a run's fate be called, and does it generalise?

A runtime cannot act on a prediction made at the end of a run, so the checkpoint was swept
(`early_prediction_nebius.json`, `early_prediction_tb2.json`). Features are averaged over windows
inside the checkpoint and used to predict the run's final failure, task-disjoint.

| checkpoint | SWE-agent: full block / run-length / base failure | Terminal-Bench: full block / run-length / base failure |
|---|---|---|
| 10% | **0.878** / 0.507 / 0.977 | 0.543 / **0.588** / 0.832 |
| 30% | 0.734 / 0.523 / 0.958 | 0.619 / **0.594** / 0.725 |
| 50% | 0.734 / 0.645 / 0.934 | 0.635 / **0.625** / 0.668 |
| 70% | 0.754 / 0.696 / 0.905 | 0.637 / **0.618** / 0.653 |

**This is where the two corpora disagree, and the disagreement is the finding.** On SWE-agent the
feature block beats run-length at all six checkpoints, by 0.37 at the earliest. On Terminal-Bench
it never exceeds **0.637** — below the first version's own within-run figures, and only
marginally above run-length, which it beats at four of six checkpoints.

The reason is selection, and it is visible in the table: averaging over `t <= f·n` means a run
that died before the checkpoint is absent, so the earlier the checkpoint the more the sample is
enriched in **runs that died almost immediately** — 97.7% failure at f = 0.10 on SWE-agent
against 84.5% overall. The 0.878 there is partly the model detecting early death rather than
stagnation, and the artifact says so. The trustworthy comparison is at f ≥ 0.30, where
Terminal-Bench's base rate is near its overall value and the block still loses to a counter.

**Conclusion:** early failure prediction works on one corpus and not the other, so the paper must
not generalise it. The mechanism is plausible and stated: SWE-agent runs are one scaffold, so
run length is a noisy proxy for progress; Terminal-Bench spans nine scaffolds whose verbosity
differs by an order of magnitude, so `t` is already a strong scaffold-specific signal and the
window features add little on top.

### 2.17 Dead-ending is neither a task property nor a model property

If the dead-end rate were mostly a property of the *issue*, a runtime monitor could not change it
and the finding would be about benchmark difficulty. If it were mostly a property of the *model*,
it would be about capability. A one-way variance split of the per-run dead-end rate across 25,681
runs, 1,213 tasks and 3 models (`dead_end_variance.json`) says it is neither:

| source | share of variance in the dead-end rate of a run |
|---|---|
| the task (which issue it is) | **24.8%** |
| the model (70B / 8B / 405B) | **0.6%** |
| neither — run-to-run variation on the same task and model | **75.0%** |

Three quarters of the variation is *within* a task and model: the same agent, given the same
issue, dead-ends differently from one attempt to the next. On the 180 instances attempted by more
than one model, the spread between the best and worst model on the same instance averages 0.159 —
real, but small against the 0.287 standard deviation across runs.

The model ordering is at least in the expected direction (405B: 0.234 dead-end, 0.301 success;
70B: 0.343 and 0.157; rank correlation −1.00 across three models, which is anecdotal and reported
as such). The load-bearing finding is the 75% residual: **dead-ending is largely a property of the
particular trajectory, not of the issue or the agent** — which is exactly the situation in which
monitoring an individual run is the right instrument, and in which a monitor can act where a
static rule cannot.
### 2.18 Spending more does not buy a solution

Everything above is denominated in edits and steps. A budget owner spends tokens and dollars, so
the Terminal-Bench shard's per-trial cost telemetry (14,750 runs, 100% coverage for cost and
duration, 88% for tokens) was joined to the mechanical labels (`cost.json`):

| cost quintile | median cost | median steps | success |
|---|---|---|---|
| Q1 cheapest | 0.0c | 12 | 0.447 |
| Q2 | 1.6c | 8 | 0.280 |
| Q3 | 9.4c | 14 | 0.424 |
| Q4 | 31.4c | 22 | 0.424 |
| Q5 dearest | 114.9c | 49 | **0.268** |

**Across a ten-decile sweep the median cost spans 848× while the success rate spans only
0.143–0.461, and the single most expensive decile is among the worst.** Cost-per-success comes to
145.7c, and the ordering is not "more spend, more success" but the reverse: the dearest quintile
solves fewer issues than the third-cheapest while costing 12× more. Failure is predicted by
spending more (AUC 0.545 from cost, 0.534 from step count) — weak, but in the direction that says
the expensive runs are the ones going badly.

Two further facts, both requiring their own denominator:

* **8,543 runs make no edit at all** and consume **40.8% of total spend**, with a success rate of
  0.361 against 0.380 for runs that do edit. This shard's `reward` is binary and task-specific, so
  "success" includes tasks whose solution is not a patch; the finding is therefore that these runs
  are not distinguishable from the others by outcome, not that they failed.
* **Wall-clock duration is only a fair proxy for spend** (Spearman +0.406), so a runtime cannot
  substitute a free timer for a token counter without losing most of the signal.

141 trials report a *negative* cost (credits or reporting artefacts, down to −1524c). They are
excluded from every money aggregate and the count is recorded, because silently including them
would corrupt the quintiles.

**Caveat that travels with all of it:** this corpus contains one cost regime and its `reward` is
task-specific, so the saturation curve is a statement about *these* tasks and *this* pricing. What
it does establish is that within this corpus the expensive end of the distribution is not the
productive end — which is the assumption a budget policy would otherwise make.

### 2.19 What one dead-end edit costs the run

The admission policy's value depends on the marginal cost of a single wasted edit, which nothing
had measured. `dead_end_cost.json` approaches it from the observable side: how dead-end count
relates to eventual success, holding the instance fixed.

| dead ends in the run | runs | success |
|---|---|---|
| 0 | 3,283 | **0.212** |
| 1 | 9,832 | 0.182 |
| 2–3 | 11,232 | 0.139 |
| 4–7 | 1,170 | 0.070 |
| 8+ | 164 | **0.018** |

Monotone, and within the 11,323 contested instances the same direction holds (any dead end: 0.340;
none: 0.453). So waste tracks failure.

**But the marginal cost of one wasted edit is small, and the data say so in a way that constrains
the paper.** Of all successful runs, **83.1% contain at least one dead end** — median 1, maximum
24. A run that succeeds after twenty-four wasted edits is the proof that a dead end is survivable,
and it is why **the paper must not claim a refusal would have saved a run.** What the admission
policy buys is wasted *turns*, not rescued outcomes; that is a real and bounded claim, and it is
the honest one.

Two further facts sharpen the picture. Dead ends sit **late** in runs (median position 0.92 through
an edit sequence, against 0.46 for other edits, *p* ≈ 0): they are the tail churn of a run that has
already tried its main idea, not a wrong foundation laid at the start. And success falls off a
cliff between two and three dead ends (0.162 → 0.068), which is a more useful threshold for a
policy than any smooth trend: a run that has wasted a third edit is already in the low-success
regime.

### 2.20 The size objection, tested

An edit writing twelve lines has twelve chances to land a surviving line; an edit writing one has
one. So part of the survival trend is arithmetic, and a reviewer will say so. The test is whether
the outcome relation survives **inside a single size stratum** (`size_artifact.json`, 197,627 edits
with a known line count):

| population | n | survival | within-instance Δ (solved − failed) |
|---|---|---|---|
| all edits | 197,627 | 0.188 | **+0.174** (*p* = 3.9 × 10⁻¹⁵) |
| **single-line edits only** | 101,186 | 0.126 | **+0.063** (*p* = 6.8 × 10⁻³) |
| five-or-more-line edits only | 58,034 | 0.298 | **+0.205** (*p* = 1.4 × 10⁻⁸) |

Editing size accounts for roughly a third of the headline gap — the single-line stratum shows
+0.063 against +0.174 overall — but the relation holds in every stratum, including the one where
the arithmetic is trivial: a one-line edit has exactly one chance to match, and solving runs still
land that one line more often than failing runs on the same instance.

Inside the single-line stratum, survival is barely predictable from anything else either (file size
AUC 0.479, how often the file was edited before 0.365, position 0.403), which says the stratum is
close to a coin flip conditioned on context — and a coin flip that still falls differently for
solving and failing runs is the cleanest evidence available that the difference is in what the
agent *chose to write*, not in how much of it there was.

### 2.21 A detection task that turned out to be degenerate

The obvious way to make the sequential result non-circular was to detect the *objective* event — a
window containing a dead-end edit — instead of the quiet-window event, which shares telemetry with
the feature set. That was attempted, and it does not work, for a reason worth reporting
(`sequential_deadend.json`):

**the dead-end event is present in 86.6% of runs** (18,406 of 21,248), leaving only 2,842 genuine
negatives. A sequential detector on that event reports recall **1.000** and a false-alarm rate of
**1.000** at every budget from 20% down to 2% — which is what a degenerate task looks like, not a
working detector: with almost no negatives, "alarm on everything" scores perfectly on recall and
the false-alarm estimate has nothing to measure itself against.

The honest conclusion is that **window-level sequential detection of dead ends is not a well-posed
task on this corpus.** The event is too common to be an event. What remains well-posed is the
run-level question — how much of this run will be dead-ended — which §2.5 and §2.19 address, and
the quiet-window detector of §2.9, which is circular as evidence about *waste* but valid as a
detector benchmark (its event is objectively defined and its negatives are real: 76.7% of runs
never leave a sustained quiet stretch).

So there are two results here and the paper should carry both: a detector that works on a properly
rare event, and a demonstration that the more tempting target is the wrong one.

### 2.22 A waste alarm that is precise and useless for prevention

Three earlier attempts at a waste alarm failed for one namable reason: every threshold was
**relative to the run**, so "alarm on the top 5% of this run's windows" is true by construction once
a run has hundreds of windows, and the measured false-alarm rate collapsed to "alarms on
everything". A deployable rule must use an **absolute** level. The rule below is one line —
*alarm when the dead-end share over the run so far exceeds 0.5, after at least 3 edits* — with both
parameters calibrated on training instances and applied frozen to held-out ones
(`waste_alarm.json`):

| | out of sample |
|---|---|
| fires on | 11.0% of runs |
| against a high-waste run (dead-end share > 0.40) | recall **0.331**, precision **0.944** |
| false alarms on low-waste runs | **0.009** |
| median share of the run elapsed at the alarm | **1.00** |
| alarms arriving before the run is half over | **11.1%** |

Read the last two rows carefully, because they decide what this is. **The rule is a precise
retrospective classifier, not an early-warning monitor**: for 75% of the runs it flags it fires at
the very end, and only 11.1% of alarms arrive before the halfway point. It can say, with 94.4%
precision, that a run's editing was mostly discarded; it cannot stop any of it.

That is the honest boundary of the third and final formulation, and the three failures together say
something specific about the problem: an alarm on waste must be *relative to what is normal for the
moment*, which is exactly what a fixed threshold destroys; and the signal that discriminates runs
does so by accumulating over the run, which is exactly what makes it late. A monitor built on total
discarded share is a post-mortem instrument. The claim the paper can make is the one the data
supports: **waste is measurable, outcome-relevant, and does not support early termination** — which
is a stronger and more useful statement than a detector that fires too late to matter.

### 2.23 A wasted edit teaches the agent nothing

§2.19 left a puzzle: **83.1% of successful runs contain a dead-end edit.** If waste were pure loss,
successful runs should be the ones that avoided it. The natural alternative was that a dead end
*teaches* something — the agent finds out its approach is wrong and changes course — and it is
testable, because it predicts that edits after a dead end look different from edits before it.

**They do not, and the prediction fails cleanly** (`dead_end_recovery.json`, 3,673 runs with a
usable first dead end, compared against a random-rank split inside the same run so run length and
task are held fixed):

| | after a real dead end | after a random split | verdict |
|---|---|---|---|
| change in mean edit size | +1.91 lines | +1.54 lines | **no signal** — the control moves nearly as much |
| change in new-file rate | **−0.115** | +0.097 | **opposite to the prediction** — the agent goes back to files it already knows |
| runs editing larger afterwards | 50.5% | 41.6% | partly a length effect |
| success when the next edit is larger | 0.091 | 0.102 when not | *p* = 0.28, **no relation** |

So a dead end carries **no diagnostic force**. After the agent writes something that never ships,
its next edit is statistically indistinguishable from any other next edit, and it turns *away* from
new files rather than toward them. The 83.1% figure is therefore not evidence of recovery: it is
evidence that dead ends are distributed through every kind of run, the successful ones included.

**What this changes for the paper.** The obvious story — "the agent notices, adapts, and that is why
it succeeds" — is not supported, and the findings must not imply it. The reader that also follows:
refusing a doomed edit would remove a cost, but there is no evidence the agent would do anything
better next; the refusal saves a turn and nothing more. Combined with §2.19 (dead ends are
survivable up to a median of 1 and a maximum of 24 in runs that still succeeded), the honest
statement is that **wasted edits are a tax, not a signal and not a cause**.

### 2.24 Where an agent edits is predictable early; whether that helps is not

The rebuild separates two things an agent can get right or wrong, and they behave very differently:

* **where it edits** — the share of its edits landing on a file the final patch touches: 65.8%
  overall;
* **whether the lines survive** — predictable online at ~0.54, i.e. not at all.

The second is a dead end for a monitor. The first had not been tested online, and it is the coarser,
more deliberate decision: an agent can see that it is editing the wrong module, whereas it cannot
see whether its next line will be rewritten. Measuring from windows inside the opening 40% of each
run, task-disjoint (`on_target.json`, 20,408 runs, 46 features):

| | AUC | within-task |
|---|---|---|
| predicting a run in the **top** quartile of on-target rate | **0.723** | 0.658 |
| predicting a run in the **bottom** quartile | 0.681 | 0.643 |
| out-of-fold rank correlation with the run's final on-target rate | **+0.342** | — |

**File choice is materially predictable early, and it beats every free alternative** (the number of
windows observed in the opening: 0.503; the run's total edit count: 0.306). That is the first
quantity in this study that is both predictable online and available before the work is spent.

**But its relationship to success is not monotone, and the paper must not pretend otherwise.**

| on-target quartile | mean on-target rate | n | success |
|---|---|---|---|
| Q1 lowest | 0.121 | 5,102 | 0.154 |
| Q2 | 0.482 | 5,102 | **0.259** |
| Q3 | 0.941 | 5,102 | 0.066 |
| Q4 highest | 1.000 | 5,102 | 0.094 |

The highest success sits in the *second* quartile, and runs that edit **only** the files the patch
touches do **worse** than runs that touch others as well. Q3 has the worst outcome and the most
edits (median 14) — many files, all of them the right ones, none of it working. This is the same
result as §2.3 seen from a different angle: failing runs are *better* at localisation. So the honest
summary is that **file choice is monitorable and is not a success proxy** — a monitor could tell an
agent it is working in the wrong place, but the data do not show that this is when the outcome is
lost.

### 2.25 When a run dead-ends does not matter; only how much

§2.19 found success falls monotonically with the number of dead-end edits, and a natural refinement
is that a dead end *early* in a run (a wrong foundation) should cost more than one *late* (tail
churn). On a smaller sampling of runs the raw numbers looked like they agreed, so the comparison was
run properly on every run with at least six edits and at least one dead end (10,287 runs,
`dead_end_timing.json`):

| comparison | early dead-end runs | later dead-end runs |
|---|---|---|
| naive success rate | 0.101 (4,325 runs) | 0.102 (5,962 runs) |
| matched on task **and** run length | 0.140 | 0.131 |

The paired difference after both controls is **+0.009** across 2,054 matched pairs (*p* = 0.103) —
nothing. The naive comparison is equally flat, so there is no effect to explain away.

**What matters is how much a run wastes, not when.** That closes the last piece of the waste
picture: the quantity is a rate, not a phase (§2.1), not a diagnostic (§2.23), and not position-
dependent (§2.25). A monitor cannot exploit timing, which is consistent with the alarm result in
§2.22 — the signal accumulates over the run, so neither early nor late is special.

### 2.26 The strongest run-level number is mostly run length, and what that reveals

Testing whether the detector's own calibrated statistic predicts an objective outcome
(`detector_value.json`, `detector_value_length.json`) produced two results, one of which must not
be reported as a finding.

**The persistence statistic is negatively related to waste.** The longest run of consecutive
"quiet" windows inside a run's opening predicts a *high* dead-ender at AUC **0.391** — below chance,
with a rank correlation of **−0.286**. Reading it straight: **the runs that look quietest early are
the ones that waste least**, the opposite of the intuition the detector was built on. This is
consistent with §2.23 and §2.20 — none of the proposed instruments point the way they were expected
to — but it also means a "quiet" run is not a struggling one.

**The study's full opening feature block predicts a high dead-ender at 0.777, and more than half of
that is run length.** Controls that had to be run before the number could be quoted:

| | AUC / correlation |
|---|---|
| the block, uncontrolled | **0.777** |
| the block, **within run-length deciles** | **0.666** (10 deciles) |
| the block against the length-residualised dead-end share | ρ = +0.195 |
| the run's edit count alone against the dead-end share | ρ = **−0.593** |

So a **0.111 of the 0.777 is run length**, and the honest figure for progress-related prediction is
**0.666** — real, above the free controls (0.316), and well below what the uncontrolled number
suggests.

**And the length association exposes a property of the metric itself**, which belongs in the
limitations: longer runs have *lower* dead-end shares (ρ = −0.593). The mechanism is mechanical —
the longer a run goes, the more its final patch accumulates, so more of what it wrote is reachable
by the patch's added-line set. The dead-end share is therefore not length-neutral, and every
comparison in this study that could be confounded by length has been controlled for it (§2.19, §2.20,
§2.25, §2.26). This one was found by chasing an implausibly large number until it explained itself.

---

### 2.27 Channel ablation: which observable carries the little signal there is — and a correction to the headline

Artifact: `results/rebuild/channel_ablation.json` · script: `scripts/analyse_channel_ablation.py`

The central claim says the wasted-edit target is unpredictable **because of the observable
channel**, not because of the model. That is a claim about an exogenous limit, so it is only
credible if it survives an attempt to falsify it *from inside the data we already hold*: if one
channel we possess — but did not separately credit — carried the signal alone, the claim would be
wrong as stated.

The falsification test was fixed before running. The 48 usable window features were split into the
six channels they came from, each was scored alone and then unioned, under one learner and one set
of 10 task-disjoint folds (`y_wasted` rows only: 23,411 windows, 733 tasks, 3,133 runs, base rate
0.838). `VER` — test observations, error/SyntaxError/Traceback/not-found counts, test-count and
improvement rates — is the nearest thing in this data to the **per-step test outcome** that
§6 of the handoff names as the instrument that would falsify the central claim from outside.

| channel | features | AUC |
|---|---|---|
| POS — position only (`relpos`, `frac_done`, `_elapsed`) | 2 | 0.543 |
| REP — repetition / looping signatures | 5 | 0.516 |
| MIX — action-mix composition | 7 | 0.533 |
| **NOV — output novelty and drift** | 13 | **0.577** |
| WS — workspace movement (the mechanical channel) | 13 | 0.544 |
| VER — verification output | 8 | 0.538 |
| **all six channels** | **48** | **0.599** |

**The pre-registered verdict is SURVIVES, and it is non-trivial.** `VER` alone is 0.538, i.e.
*below* the free position baseline (0.543) and 0.005 under the +0.02 threshold that would have
weakened the claim. The richest instrument we lack is therefore not what the little signal is made
of: **having per-step test outcomes in this corpus does not help predict an edit's fate**, which is
an unplanned, in-data corroboration of "the limit is the observable channel" rather than an
assertion about it.

**But the ablation also corrects the headline as it is currently worded.** §2 quotes **0.539 against
a 0.536 position baseline** and calls the target "not predictable at all". That 0.539 is a *single
fixed monitor* (`WS_raw`), not the best available number. The fitted multi-channel model over the
same rows reaches **0.599**, and in the field comparison (§2.24) the same feature set reaches
**0.622** on Terminal-Bench. The honest statement is therefore:

> Waste is **weakly** predictable — a fitted 48-feature multi-channel model gains **+0.056** over
> position on the corpus with the mechanical labels and **+0.086** on the other — while quietness is
> *strongly* predictable (**0.821**). The finding is a **gap of roughly a third of an AUC**, not an
> absence of signal.

"Essentially unpredictable" and "not predictable at all" are too strong and have been retired
everywhere they appeared. What survives is the comparison that matters for the paper's argument:
**whatever predicts waste predicts it three times worse than it predicts idleness** — and the
channel the increment comes from is not verification (0.538) but output novelty and drift (0.577),
i.e. *the agent's own text changing less*, which is a symptom of the same stagnation the quietness
detectors already read, not an independent instrument.

This is the seventh claim the rebuild has had to weaken when a test written to falsify it partly
succeeded, and it was found only because the two corpora forced the 0.539 and the 0.622 to sit on
the same page.

**Stability of the ablation — and a partial retreat from "SURVIVES".** Because the ablation moved a
headline, its numbers were re-derived on a full grid rather than one cell: 2 learners (L2 logistic
and gradient boosting) × 3 task-disjoint fold partitions × 2 feature forms (raw and within-task
z-scored), every cell a 10-fold CV on the same rows (`channel_ablation_stability.json`).

| channel | mean AUC | sd | range | mean gain over POS | grid cells beating POS |
|---|---|---|---|---|---|
| POS | 0.526 | 0.012 | 0.514 – 0.553 | — | — |
| REP | 0.502 | 0.015 | 0.470 – 0.529 | −0.024 | 0.00 |
| MIX | 0.530 | 0.015 | 0.498 – 0.552 | +0.004 | 0.58 |
| VER | 0.536 | 0.011 | 0.512 – 0.554 | **+0.010** | **0.83** |
| WS | 0.543 | 0.011 | 0.513 – 0.555 | +0.017 | 0.83 |
| **NOV** | **0.545** | 0.016 | 0.524 – 0.577 | **+0.019** | **1.00** |
| **ALL** | **0.590** | 0.011 | 0.574 – 0.611 | **+0.064** | **1.00** |

Three corrections follow, and they are all in the same direction — *less* favourable to the
headline than the single-cell run:

1. **The position baseline is 0.526, not 0.543.** The 0.543 was the most favourable cell in the
   grid (raw features, seed 0, gradient boosting); the baseline ranges 0.514–0.553 across it. Any
   gain quoted against one baseline cell is quoted against a coin-flip choice.
2. **`VER` does beat position — in 83% of grid cells, by +0.010 on average.** That is below the
   +0.02 I pre-registered as "materially more signal", so the claim is not falsified; but it is
   *not* the clean null the first run suggested either. The honest statement is that per-step test
   output in this corpus carries a **small, reproducible, sub-threshold** increment.
3. **The all-channel gain is +0.064 ± 0.011 and positive in every cell.** So "weakly predictable"
   is itself on the generous side of robust: across every learner, seed and feature form tried, a
   model reading only the preceding window sits **0.06 AUC above the free baseline** and never
   fails to. That is the number the paper should quote, with the sd, and it is a third of the
   quietness channel's 0.821.

**What the ablation therefore establishes, precisely:** the increment over position is real,
reproducible and small; it is *not* carried by the verification channel (which is why the
"observable channel" claim survives as a claim about *magnitude* and not about *possibility*); and
the channel that carries it is output novelty and drift, which is a symptom of the same stagnation
the idleness detectors already read. Any sentence of the form "the wasted-edit target is
unpredictable" is now retired; the claim that stands is the ratio — **0.06 of gain against 0.30 of
gain on idleness, from the same instrument.**

---

### 2.29 The frozen localisation result inverts under an independent target — a construct-validity failure

Artifacts: `results/rebuild/wrongness.json`, `results/rebuild/metric_artifact.json`,
`results/rebuild/gold_patches.parquet` · scripts: `scripts/analyse_wrongness.py`,
`scripts/analyse_metric_artifact.py`, `scripts/fetch_gold_patches.py`

**The claim being tested.** The study's frozen `on_target` result — *failed runs aim a higher share
of their edits at the file in their final patch (0.620) than solved runs do (0.576), p = 3.3 × 10⁻⁴* —
was read as "agents do not fail by mis-locating the bug." §2.31 of the handoff and the executive
summary both leaned on it.

**Why it is not a localisation measure.** `on_target` is computed as the share of a run's edit steps
aimed at files in **that same run's own final patch** (`analyse_alignment.py` line 132:
`patch_files = set(g["patch_file_names"].iloc[0])`). Both the numerator's file set and the
denominator come from the run itself. The metric therefore asks *"did the run converge on what it
produced?"*, not *"did the run aim at the right file?"* — and a run that fixates on the **wrong**
file and never wavers scores 1.0 on it.

**The test.** 927 of the study's 1,213 instances have a ground-truth **gold patch** available
(843 from `nebius/SWE-rebench`, 84 from SWE-bench) — a target that does not depend on any agent run.
We recompute localisation against it for the 19,635 runs that have both a gold patch and a known
patch, on identical edit steps.

| measure | solved | failed | direction |
|---|---|---|---|
| `on_target_self` — own patch (the frozen definition), pooled | 0.5936 | **0.6701** | failed higher — frozen result reproduces |
| `on_target_gold` — independent gold patch, basename match | **0.4771** | 0.4069 | solved higher |
| `on_target_gold` — independent gold patch, path match | **0.5100** | 0.4298 | solved higher (match rule does not drive it) |
| `ever_touched_gold` — did the run ever reach the right file | **0.9819** | 0.6705 | solved higher, Δ +0.311 |

All rows are **pooled over runs** (`wrongness.json`). The within-instance paired means for the gold
target are 0.4959 solved vs 0.4477 failed (*p* = 0.007, 228 instances). An earlier draft of this
document quoted 0.5849 / 0.6732 for the first row and 0.671 for the last: those came from
`metric_artifact.json`, whose row set differs slightly because it joins patch-width information.
Both are correct for their own row set, but the paper quotes the pooled `wrongness.json` figures, and
`scripts/audit_paper_numbers.py` now checks that every number in the manuscript traces to the
artifact it names — it found four such mismatches and they are fixed.

**The sign inverts, and it inverts back.** The frozen direction reproduces exactly (failed 0.673 vs
solved 0.585, cf. the frozen 0.620 / 0.576); against the independent target it reverses. The
independent direction agrees with every published result we could verify on an adjacent metric
(§2.30), so the self-referential version is the outlier.

**A control that the two metrics are both sane.** Restrict to runs whose own patch is a *single*
file that *is* a gold file — there the two target sets must coincide. They do: `on_target_self`
0.6154 vs `on_target_gold` 0.6384, mean absolute gap 0.033 (n = 8,801). So neither definition is
broken; they genuinely measure different things.

**The robust form of the result.** The share-based metrics are both fragile to patch composition, so
the quotable quantity is the binary one, which is robust in every stratum:

| own patch width | n solved | n failed | ever touched gold (solved) | ever touched gold (failed) | Δ |
|---|---|---|---|---|---|
| 1 file | 2,555 | 9,070 | 0.9922 | 0.6908 | **+0.3013** |
| 2 files | 593 | 3,688 | 0.9629 | 0.7337 | +0.2292 |
| 3 files | 111 | 1,010 | 0.9730 | 0.6970 | +0.2759 |
| 4+ files | 49 | 809 | 0.6939 | 0.6205 | +0.0734 |

`ever_touched_gold` is positive in **every** stratum, which is why it survives and the shares do
not: `on_target_gold` runs +0.0703 pooled but only **+0.0199** after direct standardisation over
patch width, with 72% of the pooled gap being composition, and sign-flips inside strata 2–4.

**Three mechanism hypotheses tested and all three falsified.** This is the part that cost the most
time and should be reported:

1. *"Confident wrongness"* — a failed run that never reaches the right file should score high on the
   self-referential metric. **Falsified**: lost runs score 0.6612 against 0.6791 for wrong-fix runs,
   with a 95% CI of [−0.031, −0.005] that excludes zero on the *wrong side*.
2. *"Patch-breadth composition"* — failed runs write broader patches (2.20 files vs 1.35), which
   enlarges the self-referential target set. **Falsified as an explanation of the inversion**:
   standardising over patch width makes the self-referential gap *larger* (−0.088 pooled →
   −0.125 standardised), and the gap is already largest in the narrowest stratum, where breadth
   cannot operate.
3. *"Fixation"* — the metric rewards concentrating edits on one file. **Partially supported but not
   the mechanism**: failed runs are more fixated (0.7785 vs 0.7274) and **lost runs are the most
   fixated of all (0.8181 vs 0.7589 for wrong-fix)**, which independently corroborates the finding
   that consistency-based monitors are fooled exactly when they should not be trusted. But fixation
   correlates no more strongly with the self-referential metric (0.251) than with the gold metric
   (0.294), so it does not explain the inversion either.

**So the honest conclusion is a construct-validity one, not a mechanism one.** The frozen metric is
a *closed loop* — its target set is the run's own output — and any metric of that form measures
convergence rather than correctness. We can demonstrate the inversion, prove the two metrics agree
where they must, and show the correction restores agreement with the published literature. What we
**cannot** yet claim is a mechanism: three plausible ones were tested and none survived. The
mechanism is recorded as open.

**Held-out replication on eight unseen shards — three disjoint sets, all 12 shards covered.** The
frozen table used Nebius shards 0–3. Shards 4–7 and 8–11 were downloaded and parsed into **separate**
tables (`data/processed/steps_repl`, `data/processed/steps_repl2`) so no replication ever touches the
frozen artifacts, with gold patches resolved independently for each set (74.6% and 77.9% coverage,
against 76.4% for the frozen set). Together the three tables cover **12 of 12 shards and 80,035 runs**.

| set | shards | runs | `on_target_self` solved → failed | `on_target_gold` solved | failed | within-inst. *p* | wrong-fix share | *n* |
|---|---|---|---|---|---|---|---|---|
| frozen | 0–3 | 26,679 | 0.594 → **0.670** | **0.477** | 0.407 | 7.0 × 10⁻³ | 67.0% | 16,327 |
| held-out A | 4–7 | 26,680 | 0.593 → **0.677** | **0.492** | 0.421 | 3.6 × 10⁻³ | 69.0% | 15,837 |
| held-out B | 8–11 | 26,676 | 0.614 → **0.686** | **0.512** | 0.415 | **2.8 × 10⁻⁵** | 66.4% | 15,953 |

**All three columns agree, on three disjoint sets of ~26,000 runs each.** The self-referential metric
inverts in every one; the independent gold target reverses it back in every one, with the paired test
strengthening rather than weakening on the unseen data (*p* from 7.0 × 10⁻³ to 2.8 × 10⁻⁵); the gold
gap is +0.070 / +0.071 / +0.097; and the headline **wrong-fix share of failures varies by only 2.6
percentage points** (66.4–69.0%). A result that survives two independent replications on data the
study never saw is not a sampling artefact.

Artifacts: `wrongness.json`, `wrongness_repl.json`, `wrongness_repl2.json`,
`gold_patches_repl{,2}.parquet`; scripts `scripts/fetch_gold_repl.py`,
`scripts/build_step_table.py --shards 4 5 6 7 | --shards 8 9 10 11`, `scripts/show_replication_table.py`.

**Scope note.** This is **not** a single merged 80k-run table. It is the full shard coverage delivered
as one frozen table plus two held-out replications, which is methodologically stronger than a merge
would have been (each replication is genuinely unseen) but means the pipeline was never re-run on one
80k table. The earlier 12-shard single-table attempt failed — two builds raced on one output file and
the surviving partial table was unreadable — and that failure is recorded rather than hidden. No claim
here depends on a merged table.

**Corpus coverage, complete as of the final pass.**

| corpus | scope | runs | steps | table |
|---|---|---|---|---|
| Nebius / SWE-agent | shards 0–3 (frozen) | 26,679 | 709,264 | `data/processed/steps/nebius` |
| Nebius / SWE-agent | shards 4–7 (held-out A) | 26,680 | 710,910 | `data/processed/steps_repl/nebius` |
| Nebius / SWE-agent | shards 8–11 (held-out B) | 26,676 | 695,449 | `data/processed/steps_repl2/nebius` |
| **Nebius total** | **12 / 12 shards** | **80,035** | **2,115,623** | — |
| Terminal-Bench 2.0 | **2 / 2 shards** | **29,103** | **887,137** | `data/processed/steps_tb2_dedup/tb2` |
| 4 non-SWE-agent scaffolds | see §2.33 | — | — | `xscaffold_replication.json` |

Terminal-Bench's 52,104 raw trials yield **29,103** parseable runs and **887,137** steps once the
release's duplicated trials are removed (§2.37); the remainder are the zero-action agent-crash trials
documented earlier. The 2-shard TB2 table was built once at 08:19, **destroyed** when `steps_full`
was cleared to unblock the Nebius rebuild — it was the only copy, which was a mistake — and rebuilt
into `steps_tb2_full` in the final pass, reproducing the original run and step counts exactly. That
table was itself superseded by `steps_tb2_dedup` once the duplication was found.

**Three consequences, and they are all retractions or narrowing.**

1. **The frozen claim "failed runs localise better" is withdrawn** and is annotated as a
   construct-validity failure where it appears in `HANDOFF.md`, `GAP_ANALYSIS_AND_PLAN.md` and
   `EXECUTIVE_SUMMARY.md`.
2. **The headline is narrowed to the bounded-lever form**, which the robust binary measure supports:
   30.9% of failed runs never reach a gold file, so localisation tooling can address at most that
   share of failures; the other 69.1% of failures happen with the agent already editing a correct
   file.
3. **The 2026 literature had this already at larger scale.** §2.30 states the prior art plainly,
   including that our 67.1% independently reproduces a published 60–69% range. The qualitative
   thesis is not ours; the metric defect and the bounded-lever quantification are what remain.

---

### 2.30 Prior art, verified: what is ours and what is not

Every citation below was fetched and read directly from `arxiv.org/abs` during this session
(the reconnaissance agent's summaries were **not** trusted for load-bearing claims, and one of its
numbers was rejected as unverifiable). The automated `export.arxiv.org` API is rate-limited from
this host; direct page fetches work.

| work | their claim | relation to us |
|---|---|---|
| **Coherence Collapse** — [2603.24631](https://arxiv.org/abs/2603.24631), Mar 2026, 16,758 trajectories, 3 architectures, 7 models | *"The dominant failure of capable models is not localization: 60–69% of failures on SWE-Agent and OpenHands reach and edit the correct functions yet still produce incorrect patches"* | **Prior art for the interpretation.** Our 67.1% sits inside their range. We must not claim "wrong, not lost" as a finding. |
| **Understanding Code Agent Behaviour** — [2511.00197](https://arxiv.org/abs/2511.00197), ICSE 2026 | Majority of failing trajectories locate the correct files; gold-match >90% solved vs 59.3–81.4% failed | Same interpretation, and their *numbers agree with our independent target*, not with the frozen self-referential one. |
| **FailForge** — [2608.08570](https://arxiv.org/abs/2608.08570) | Localisation precision pass > fail in all five reported rows | **Reports the opposite direction to the frozen claim**, and the same direction as our corrected result. |
| **TraceProbe** — [2607.06184](https://arxiv.org/abs/2607.06184) | Same-task alignment of failed runs to solved references: file-selection divergence 38.5–95.0%, usually the largest layer | Nearest headwind: same-task, paired, file-level, opposite sign. Different metric (divergence-from-reference vs absolute on-target share) — state explicitly. |
| **Confident and Wrong: Silent Semantic Failures** — [2603.25764](https://arxiv.org/abs/2603.25764), 1,750 trajectories | GPT-5 submits a patch on 100% of runs, resolves 44%; "silent semantic failure" covers 68% of GPT-5's and 80% of Llama 4's failing runs; *"completion-based and consistency-based monitoring both look healthy exactly when the agent should not be trusted"* | **Prior art for the monitoring problem.** Our fixation result (lost runs are the *most* fixated of all, 0.818 vs 0.759) independently corroborates their monitor-fooling claim. Any detection claim must beat this. |
| **TRIM** — [2607.18161](https://arxiv.org/abs/2607.18161) | CodeSlop = 20.0% on SWE-bench (23.6% of edit actions) | Closest number to our 19.1% dead-end rate, but a **different object**: TRIM measures unnecessary lines *in a passing patch* via counterfactual re-execution; we measure edit *operations* that never reach the patch, with no execution. Say so explicitly. |
| **Beyond Resolution Rates** — [2604.02547](https://arxiv.org/abs/2604.02547), Mehtiyev & Assunção (NC State), 2026, 9,374 trajectories, 19 agents, 8 frameworks, 14 LLMs, 500 tasks | **VERIFIED by direct fetch:** *"The widely reported correlation between trajectory length and failure **reverses direction** once task difficulty is controlled, revealing it as a confound."* Also: the LLM, not the framework, is the primary driver of outcome. | **Methodological prior art for the reversal itself, for a different quantity.** We must not present "a within-task reversal" as a novel methodological contribution; what is ours is that a specific, widely-computable *localisation* statistic is self-referential and inverts, which no located paper reports. **Still UNVERIFIED:** the reconnaissance claimed a "263 tasks / *p* = 1.9 × 10⁻⁹" numerical collision with our frozen 263-instance figure. The abstract and introduction do not contain those numbers, and arXiv was intermittently unreachable so the results section could not be read. The qualitative reversal is confirmed; the numerical coincidence is **not**, and it is propagated into no claim. Note also that the two quantities differ: theirs is trajectory **length**, ours was edit **precision**. |

**Novelty verdict, stated conservatively.** The qualitative interpretation — that capable agents
usually reach the right code and still fail — is **not ours**; it is published twice, once at
larger scale than our measured sample. The self-referential **metric defect** is ours as far as we
can determine: no located paper reports failed runs localising *better* within-instance, which is
exactly what a broken metric produces and a correct one does not. So our contribution is scoped to
the *measurement*: a construct-validity failure that inverts the sign of a widely-computable
localisation statistic, demonstrated with both targets on the same edits, a control showing the two
metrics agree where they must, and a corrected form that restores agreement with the literature.

**The detection bar we must beat (§2.31 reports the attempt):** AgentStop AUC 0.6–0.7
([2605.15206](https://arxiv.org/abs/2605.15206)); the field's shared attribution benchmark scores
**53.5% agent-level but only 14.2% step-level** ([2505.00212](https://arxiv.org/abs/2505.00212),
ICML 2025); 82% precision at 2–3% FPR but only **18.2% recall**
([2607.09510](https://arxiv.org/abs/2607.09510)); step-level redundancy ceiling **24.88%**
([2605.29893](https://arxiv.org/abs/2605.29893)).

---

### 2.31 A causal, reference-free router that beats every baseline — and a correction to the study's own "position wins" claim

Artifacts: `results/rebuild/route_modes.json` (273 KB), `docs/ROUTE_MODES.md` · script:
`scripts/analyse_route_modes.py` · doc-number audit: `scripts/_verify_route_modes_doc.py`
(re-checks 453 numbers quoted in the write-up against the artifact, **0 failures**)

**The task is a decision, not a detection.** Given only a run's first fraction *f*, decide whether
a struggling agent should spend budget on **SEARCH** (help it find the right place) or **VERIFY**
(make it check its own fix). Two targets, both defined from the independent gold patches of §2.29
and never from an agent's own output:

* `y_fail` — will this run fail?
* `y_mode` — among failed runs, is it **LOST** (never edited a gold file) or **WRONG-FIX** (did)?

**Causality was enforced and self-tested.** The prefix is steps `0…L−1` with `L = round(f·n_steps)`;
`n_steps` appears in no feature. A `--selftest` mode overwrites every post-cutoff step and asserts
all 112 feature columns are unchanged — it caught a genuine leak (`obs_half_ratio` read past the
prefix), which is now fixed. Folds are task-disjoint, 3 fold seeds, 500 task-cluster bootstraps,
identical rows and folds for every method compared.

| target | f=0.10 | f=0.20 | f=0.40 | f=0.60 |
|---|---|---|---|---|
| `y_fail`, this study's features | **0.693** | **0.721** | **0.721** | **0.731** |
| `y_fail`, position baseline | 0.667 | 0.664 | 0.666 | 0.666 |
| `y_fail`, `agentstop_shape` | 0.554 | 0.565 | 0.594 | 0.607 |
| `y_mode`, this study's features | **0.676** | **0.701** | **0.724** | **0.751** |
| `y_mode`, **all** baselines | 0.407–0.493 | 0.411–0.490 | 0.413–0.486 | 0.413–0.539 |

**Baselines are beaten in all 8 task × fraction cells**, with bootstrap CIs excluding zero. Against
`position` the gain is +0.026 … +0.065 on `y_fail`; against the shipped loop heuristics
(`ngram_loop`, `exact_burst`, `tfnorm_novel`, `agentstop_shape`) it holds at every fraction. On
`y_mode` **every baseline is at or below chance** — a length-matched, causal model separates the two
failure modes where the field's detectors carry no signal at all. The published 0.6–0.7 AgentStop
band is cleared from f = 0.20 for `y_fail`; at f = 0.10 the value 0.693 sits *inside* that band and
is reported as such.

**A correction to the frozen study, and it is the same species of error as §2.29.** The frozen
findings state that *"step index still beats every learned monitor"* on one corpus. That comparison
is **not valid**, because at a fixed prefix fraction `position` is *exactly the run's own length*
(`round(f·n_steps)`) — verified by its AUC matching `n_steps`' to ≤0.006. It is a hindsight quantity
unavailable to any online monitor, so it could not have been a fair baseline. Against a length-matched
control (fixed prefix lengths of 5, 10 and 20 steps, where position is inert) the learned model holds
at 0.63–0.76, and adding `position` to the feature set changes the result by ≤0.002. The learned
model strictly dominates run length; the frozen claim that it did not is withdrawn.

**Calibration is genuinely controlled this time — the specific thing the frozen study got wrong.**
The withdrawn "zero false alarms" claim of §2.17 was circular because the label and the detector were
the same statistic. Here the labels come from gold patches and the detector from prefix features, and
the null hypothesis is explicit: for `y_mode` the null is *LOST* runs, for `y_fail` it is *successful*
runs. Using a whole-task train/calibration/test split and a sequential union-bound rule valid under
arbitrary dependence:

| level | `y_mode` achieved FA | `y_mode` detection | `y_fail` achieved FA |
|---|---|---|---|
| α = 0.05 | **0.0459** (worst split 0.0605) | 0.160 | 0.0339 |
| α = 0.10 | 0.0777 | 0.258 | — |
| α = 0.20 | 0.1232 | 0.386 | 0.1088 |

8 of 8 levels are controlled on the mean; the worst split exceeds α at only 2 levels, both at
α = 0.05, by 1.03× and 1.21×, and that is reported rather than hidden. A null run does **not** trivially
trigger: a raw 0.5 threshold flags 98.4% of never-failing runs, while the calibrated rule at α = 0.05
flags **3.39%**.

**The decision curve is the deployable result.** Scoring 1 for the correct routing decision and λ
otherwise, and evaluating only on runs that actually failed:

| routing policy | value (λ = 0.25) |
|---|---|
| **this detector** | **0.764 – 0.800** |
| always VERIFY | 0.732 |
| random | 0.656 |
| always SEARCH | 0.518 |

It beats all three baselines at **every** fraction and every λ ∈ {0, 0.25, 0.5} — 12 of 12 cells,
with CIs excluding zero. At λ = 0 this is routing accuracy, 0.685 → 0.733. Gated over all runs it
also wins (0.639–0.666 vs 0.397 / 0.547 / 0.523), but the gate fires on ~99% of runs, so that
number measures routing rather than gating and is labelled as such.

**Four honest negatives, all recorded.**

1. **The e-value rule is valid but never fires** at α ≤ 0.05. A formal sequential test is available
   and has no power on this data. Reportable as a negative, not hidden.
2. **Recall at a 5% alert budget is ≈ 0.058 for every method including the free baseline**, because
   the base rate is 0.837. The usable output is a *ranking*, not a tight-budget alarm.
3. **The cutoff is placed using `n_steps`** (hindsight), so the fully online claim rests on the
   length-matched control rather than on the main table.
4. **`ever_touched_gold` is a coarse proxy** for wrong-fix, and gold matching is basename-only;
   4.10% of edit steps carry no filename, which biases LOST upward. Both bound the result.

---

### 2.32 The causal experiment: hold the defect fixed, vary only how easy it is to find

Artifacts: `results/live/episodes.jsonl`, `results/live/live_experiment.json` · scripts:
`scripts/run_live_experiment.py`, `scripts/analyse_live_experiment.py`,
`scripts/run_live48.py` (48-task suite) · task suites: `data/live/`

§2.29 is correlational: on logged runs, 69.1% of failures had already edited a gold file. A reviewer
can reasonably reply *"that is selection, not cause."* The only answer is to intervene on the same
defect. So a live experiment was run using the DeepSeek gateway against a suite of real pure-Python
packages, no Docker, with the packages' own test suites as the verifier.

**Design, pre-registered before the first episode.** Three arms over the same tasks, same model,
same step budget, differing only in what the agent is told:

| arm | what the agent gets |
|---|---|
| `unhinted` | a defect exists; find and fix it |
| `hinted` | the exact file **and** function — localisation solved by fiat |
| `verify` | unhinted, plus: after a failed test, *re-diagnose before changing more code* |

Predictions fixed in advance from the observational result:
**P1** hinting should raise success only *modestly* — the failure-rate drop should be smaller than
the 30.9% of failures attributable to never reaching the file.
**P2** the verify arm should beat unhinted by more than hinting does.
**P3** conditional on reaching the gold file, success should still be far below certainty.

**Two harness faults had to be fixed before the result meant anything, and both were caught by
looking at what the agent actually did rather than at the scores.**

1. **65.2% of turns were unparseable.** The first protocol was ad-hoc text (`reply with: read <path>`),
   but the model emits its *own* XML tool-call format (`<tool_calls><invoke name="write">`)
   regardless. The pilot was therefore measuring protocol compliance, not debugging. Switching to
   native OpenAI function-calling took unparsed turns to **0–4%**. This is the single largest
   correction in the experiment and it was invisible in the pass/fail column.
2. **The agent was writing its own tests into `tests/`.** Pilot transcripts show `test_debug.py`,
   `test_aaa_dump.py`, `grouper_dump.txt`. pytest collects those, so an agent-authored passing test
   could have scored a run as **successful without the defect being fixed**. The verifier is now
   restored to the package's original tests before final grading (agent source edits are kept,
   agent test edits are not) — which is what a real grader does. The count is logged as
   `test_files_removed`; it is nonzero in many episodes, and an agent that "fixed" a test to make it
   pass is still scored as having failed.

**Results, on the larger 48-task suite (8 real packages, 2 arms, 96 episodes, $0.91).** Auditing the
raw episode records rather than the summary showed that **13 of 96 episodes had `fail_before=False`**
— the mutation did not actually break the invoked tests at episode start — so success is meaningless
for those and they are excluded. On the remaining 83:

| arm | n | success | 95% CI | reached gold | **success given reached gold** | mean turns |
|---|---|---|---|---|---|---|
| `hinted` | 40 | **0.550** | [0.40, 0.70] | **1.000** | **0.550** | 11.4 |
| `unhinted` | 43 | **0.372** | [0.23, 0.51] | **1.000** | **0.372** | 12.2 |

**Every single run in *both* arms reached the correct file — and 62.8% of the unhinted runs still
failed.** This is the cleanest form of the whole result: in this suite localisation was never the
barrier, at all, and the binding constraint is plainly the fix. It is the causal counterpart of the
observational 69.1% / 98.2% gap, reproduced under a manipulation that removes search cost entirely.

**The effect size is real but not statistically significant, and we say so.** Handing over the file
raised success by **+17.8 points**, and the failure-rate drop (0.178) is below the pre-registered
0.309 ceiling, so **P1 holds**. But Fisher's exact test on 40 vs 43 episodes gives **p = 0.126** —
this sample cannot establish the improvement. P1 is an *inequality about magnitude*, pre-registered
precisely so that it could be checked without significance; a reader must not read it as a shown
effect.

**An earlier, smaller run (16 tasks, 3 arms, 50 episodes, $0.40)** gave the same shape and was the
one that carried the `verify` arm: `hinted` 0.438, `verify` 0.353, `unhinted` 0.235, with success
given gold of 0.583 / 0.400 / 0.286. Both runs agree that reaching the file is necessary and
nowhere near sufficient.

**A behavioural finding worth its own line.** In **71 of the 83 valid episodes the agent created or
modified files under `tests/`** — 1,048 files removed by the verifier restore in total. Agents very
frequently write their own tests while debugging. Because the verifier is restored before grading,
an agent that "fixes" a test to make it pass is still scored as failing; but the frequency is itself
a measurement, and it is also why the first version of this harness would have produced a **wrong
success measure** (§2.32's harness faults).

**P1 holds.** Handing the agent the exact file and function moved success from 37.2% to 55.0% in the
48-task run (+17.8 points), and the *failure-rate* drop of **0.178** is below the pre-registered
0.309 bound — the ceiling §4 said localisation could be worth. The prediction was that hinting would
not remove most failures, and it did not.

**P3 holds, and it is the causal version of the whole finding.** In the 48-task run **100% of runs in
both arms reached the gold file**, and the agent still failed **62.8%** of the time unhinted and
45.0% hinted. In the 16-task run, 82% of unhinted runs reached the file and succeeded only 28.6% of
the time. Being in the right place is necessary and nowhere near sufficient, and this is now an
interventional statement rather than a correlation. It reproduces the 69.1% / 98.2% gap of §2.29
under controlled conditions — in fact it sharpens it, because here every run reached the file and a
majority still failed.

**P2 fails, and it is reported as a failure.** The verify arm (0.353) did not beat unhinted by more
than hinting did; hinting was the strongest arm. A prompt telling the agent to re-diagnose after a
failed test did **not** rescue it. That is a negative result about the most obvious practical
intervention this study could recommend, and it is the second time in this rebuild that the
"spend the budget on verification" intuition failed to pay (§2.16–§2.17).

**Limitations, stated.** The hinted-versus-unhinted difference is **not statistically significant**
(Fisher *p* = 0.126 at n = 40/43); what is pre-registered is the *size* of the localisation ceiling,
not the significance of an improvement, and P1 was fixed in advance so that this distinction could
not be blurred after the fact. The tasks are single-defect mutations in eight real packages, not
SWE-bench instances. Both `test` runs and `success` use the packages' own suites, which the mutation
was verified to break (83 of 96 confirmed; the 13 that did not are excluded) and the pristine source
to pass. A run that never calls `done` is graded on its final workspace state, which is the intended
semantics.

---

### 2.33 The taxonomy does **not** transfer across scaffolds — the sharpest limitation in the study

Artifact: `results/rebuild/xscaffold_replication.json` · script: the cross-scaffold workstream

The port was validated before it was trusted: re-running the labelling on SWE-agent with the new
code path reproduces the frozen rates **exactly** (absolute difference 0.0 on all three rates,
236,137 edits, 25,681 runs). Then it was applied to four other corpora.

| scaffold | editor footer on edit steps | kept | revised | **dead_end** | verdict |
|---|---|---|---|---|---|
| SWE-agent (frozen reference) | **0.958** | 0.157 | 0.652 | 0.191 | reference |
| OpenHands (SWE-Gym) | **absent** | 0.734 | 0.229 | **0.037** | does **not** replicate |
| PI agent | absent | 0.821 | 0.060 | 0.118 | does **not** replicate |
| mini-swe-agent-plus | absent | 0.489 | 0.276 | **0.236** | different again |
| multi-framework mix | absent | 0.706 | 0.115 | 0.179 | L1 1.035 |

**Two negatives, and they are the most important caveats in the paper.**

1. **The mechanical instrument exists in exactly one framework.** `[File: … (N lines total)]` appears
   on 95.8% of SWE-agent edit steps and **0%** of the others (0 of 101,003 OpenHands observations;
   0 of 267,103 PI observations). OpenHands names the file via a `cat -n` header but never its line
   count, so an edit's *effect* — the thing the whole taxonomy rests on — is unmeasurable there.
   Every mechanical number in this study is therefore bounded to frameworks that print comparable
   state, and cross-framework generality is **not claimed**.
2. **The dead-end rate is a scaffold property, not a property of coding agents.** It ranges from
   **3.7% to 23.6%** — a factor of six. The 19.1% headline is SWE-agent's number. It must never be
   quoted as "coding agents waste 19% of their edits", and any downstream comparison across
   frameworks must be made on the non-empty-patch scope below.

**A scope correction that came out of the same work, and it affects how 19.1% should be read.**
**16.7%** of SWE-agent edit steps (39,486 of 236,137) sit in runs that produced **no patch at all**
(3,487 runs have only empty patches). Restricted to runs with a non-empty patch — the strictly
comparable scope for scaffolds where a patch must be recovered from the transcript — the reference
becomes **kept 0.189 / revised 0.624 / dead_end 0.187** over 196,651 edits and 22,194 runs. Both
scopes are correct for their purpose; only the second is comparable across scaffolds, and the paper
labels which one every figure uses.

---

### 2.34 The router transfers across **shards**, and the margin is measured against the field

Artifact: `results/rebuild/route_modes_transfer.json` · script:
`scripts/analyse_router_transfer.py`

The study's headline router number is an out-of-fold score on one shard set, which invites the
objection that it is fitted to one corpus. So the model was trained on one set and scored on the
other two, in **both directions**, at four prefix fractions: **24 cross cells** over three disjoint
sets (26,679 / 26,680 / 26,676 runs). The published families — position, AgentStop-style shape,
n-gram loop, normalised redundancy — were re-derived on the *same rows and folds*, because a gain is
only meaningful against an opponent that saw the same data.

| target | within-set mean | **cross-set mean** | worst cell | position | AgentStop-style | **gain over the best family** |
|---|---|---|---|---|---|---|
| will this run fail? | 0.7169 | **0.7145** | 0.6752 | 0.6718 | 0.5589 | **+0.1556** |
| LOST or WRONG-FIX? | 0.7117 | **0.7324** | 0.6817 | 0.5993 | 0.5960 | **+0.1364** |

**Cross-set performance equals within-set performance**, so the margin is not fitted to one corpus:
on the mode question the published families sit at or below chance (0.596 / 0.599) while the router
reaches 0.73 on data it never saw. This is the result the paper's claim #5 rests on.

An earlier version of the paper's transfer table quoted four pairs of numbers that appeared in this
artifact only by coincidence; the table now reports the artifact's verdict block directly, and the
audit gate (`scripts/audit_paper_numbers.py`, 57/57) checks every value in it. That is the third
time the gate has caught a real error in our own manuscript.

---

### 2.35 The router does **not** transfer across scaffolds — tested, and negative

Artifacts: `results/rebuild/router_xscaffold.json` (`scripts/analyse_router_xscaffold.py`) and
`results/live/live_router_deployment.json` (`scripts/analyse_router_live.py`)

§2.34 varies the shards and holds the scaffold fixed. The obvious follow-up is to vary the scaffold,
and the corpora for it were already on disk. Three of them carry a usable outcome label, so the same
code path built the per-step frame for training and test data and the *same* features were scored
two ways: fitted inside the target scaffold (task-disjoint 5-fold OOF) and transferred from
SWE-agent.

| test corpus (scaffold) | runs | fitted inside it | **transferred from SWE-agent** | best fixed baseline |
|---|---|---|---|---|
| SWE-rebench / OpenHands | 67,074 | 0.653 | **0.495** | 0.655 |
| thoughtworks agentic-coding | 15,000 | 0.759 | **0.433** | 0.640 |
| SWE-Gym / OpenHands | 6,055 | 0.761 | **0.319** | 0.425 |

Four feature-set variants (22–31 features, dropping command-digest and observation-scale families
one at a time and together) move the transferred column only within **0.32–0.54**, so this is not an
artefact of the transcript bridge. The same conclusion arrives from a completely different
direction in the live harness: the frozen model applied to 125 live episodes scores **0.426** at the
20% checkpoint against 0.584 for the published output-overlap baseline, and re-fitting on
bridgeable-but-scale-free features recovers 0.602.

**The claim is therefore bounded, in the paper and here: the generality established in §2.34 is
shard-level generality *within a scaffold*, not scaffold-independent generality.** The mode head
could not be tested this way at all — the gold patches that define its labels exist for 227 of the
9,921 instances with edits in these corpora, so the LOST/WRONG-FIX question has almost no negatives.

---

### 2.36 The live experiment, with the masked condition finally valid

Artifact: `results/live/live_arms_valid.json` · script: `scripts/analyse_live_arms_valid.py`
(145 episodes, 42 tasks, **$1.36**; raw view: `live_masked_vs_full.json`)

The first masked run is the study's best example of a number that *looked like a finding*: 0/48
success, 0% reaching the gold file, 48 errors, $0.00 spent. Every episode had died before its first
tool call because the recorded interpreter had been deleted from a temp directory between runs.
Diagnosis was by reading transcripts, not by re-running statistics (`scripts/diagnose_masked.py`).
The venv was rebuilt in-repo (`research/data/live/.venv`) and the arm re-run.

Valid episodes only (19 of 145 dropped because the mutated package did not actually fail at episode
start, which makes success meaningless — and note that the filter *lowers* every arm, which is the
signature of a real data problem):

| condition | what the agent sees | success | vs hinted | reached the gold file |
|---|---|---|---|---|
| hinted | the exact file and function | **0.561** (n=41) | — | 1.000 |
| unmasked | full pytest output (normal CI) | 0.372 (n=43) | −0.189, Fisher p = 0.125 | **1.000** |
| masked | only "N failed, M passed" | **0.286** (n=42) | **−0.275, Fisher p = 0.015** | 0.952 |

Two things are worth recording. First, **withholding which tests failed is the only significant
effect in the experiment**, and it is the first condition in which any agent failed to reach the
file at all: roughly a quarter of the benchmark's difficulty was the test runner naming the file
(§2.32 measured the leak at 51.5% of test observations). Second, the *hint* — handing over the file
and function — is worth +0.189 and is **not** significant at this n, so it must not be reported as a
gain. Raw (unfiltered) values for comparison: hinted 0.604, unmasked 0.449, masked 0.333.

---

### 2.37 Terminal-Bench ships duplicate trials, and the duplicate inflated every TB2 statistic

Artifacts: `data/processed/steps_tb2_dedup/tb2/{runs,steps}.parquet` and
`dedup_stats.json` · script: `scripts/rebuild_tb2_dedup.py`

**Found by the second author, Xuhao Chen, not by me.** Commit `106ff4b` on the `will/dev` branch ("Loader: dedupe
TB2 UUID + empty-UUID twin trials by trial_name") added the rule to `research/src/loaders.py`:
Terminal-Bench's release ships **two rows for 4,952 `trial_name` values** — one carrying a real
`trial_id`, one with an empty one — and the loader keyed runs by `trial_name`, so both were written
under the same `run_id`.

My own table builder (`build_step_table.py::build_tb2`) had the same defect, and it was worse than a
double count: the two rows were written as **one run with the union of both step sets**, so a run
could carry two different attempts. The frozen TB2 table therefore reported:

| quantity | duplicated table (frozen) | deduplicated table |
|---|---|---|
| run rows | 34,029 | **29,103** |
| distinct run ids | 29,103 | 29,103 |
| step rows | 1,073,923 | **887,137** |
| duplicate `(run_id, step)` pairs | 186,786 | **0** |
| solve rate | 0.3254 | **0.3439** |

**Preference matters and is not cosmetic.** 354 of the 4,926 duplicated pairs *disagree* on
`reward`/`n_steps`, so they are not byte-identical copies; the rule keeps the twin carrying a real
`trial_id`, and re-deduplicating by `(run_id, step)` instead would merge two different attempts.

**What it changes.** Every TB2 statistic in the v1 study was computed on the inflated table, and the
effect is not uniform:

| quantity (TB2, all scaffolds) | frozen table | deduplicated |
|---|---|---|
| polling share of context cost | 0.082% | **0.154%** |
| turns contributing < 5% of their context | 93.7% | **88.6%** |
| repeated-signature turns, cost share | 29.3% | **27.9%** |
| mean context per step | 29,846 chars | **19,229 chars** |

The polling conclusion is unchanged and slightly strengthened — polling is *still* negligible — but
**the share was understated by a factor of ~1.9**, because the duplicated copies doubled the context
they contributed. The awaiting-turn result that contradicted a prior claim about agent polling
(§2.31) survives the correction; its number moves from 0.082% to 0.154%.

**Boundary of the correction.** TB2 does not carry any claim in the current report: `paper/v2` is
built entirely on the three SWE-agent shard sets, and no number in `paper/v2/main.tex` comes from
Terminal-Bench. The correction is recorded because the repository still ships the v1 artifacts, and
because the same bug class — keying runs by a field the release does not guarantee unique — is
exactly what a future rebuild would repeat.

---

### 2.28 The field comparison is conservative, not lucky

Artifact: `results/rebuild/field_comparison_stability.json` · script:
`scripts/analyse_field_comparison_stability.py`

§2.27 exposed a general hazard: the study's strongest numbers were single cells of a
learner/seed/fold space, and a single cell can be a favourable one. The **field comparison (§2.24) is
the one place the paper claims a head-to-head win**, so the same objection applies to it with the
most at stake. The identical feature set and identical targets were therefore re-derived over a grid
(2 learners × 2 fold counts × 2 seeds = 8 cells), with the opponent families — which are fixed
monitors with no hyperparameters — left as they are.

| target | frozen single cell | grid mean ± sd | grid range | where the frozen cell sits |
|---|---|---|---|---|
| `step_wasted` | 0.622 | **0.632 ± 0.007** | 0.621 – 0.645 | at the **bottom** of the grid |
| `step_noop` | 0.821 | **0.849 ± 0.013** | 0.836 – 0.862 | **below every** grid cell |

**The result is the opposite of the §2.27 finding, and it is worth stating why.** Here the frozen
single-cell values are the *least* favourable ones available — the wasted-edit figure is the minimum
of its own grid and the no-op figure is below the entire grid — so the head-to-head win against the
shipped detectors is **understated, not inflated**, and the comparison cannot be dismissed as a lucky
hyperparameter. The spread is small (sd 0.007 and 0.013) and no cell in either grid falls near the
0.515–0.546 band the field families occupy. That asymmetry is itself the lesson of the last two
sections: single-cell numbers are only a hazard when they are quoted *upward*, and the way to know
which is to run the grid rather than to trust the direction of one's own suspicion.

---

## 3. What this changes in the first version's story

| first version | rebuild |
|---|---|
| "task-grounded evidence is not better than semantic redundancy" | **confirmed, sharpened, corpus-scoped**: repetition wins on SWE-agent, novelty on Terminal-Bench; the workspace channel is worst in both |
| "window-level stagnation detection saturates at AUC ≈ 0.78" | **refuted as stated**: that ceiling was the judged label set's. Against a mechanical target the same families reach 0.85–0.96 pooled |
| "this release contains no dense objective progress signal" | **refuted**: 1.26M steps carry workspace telemetry; 80.5% of all edits are mechanically characterisable as wasted |
| "the labels are AI judgements — our worst limitation" | **removed**: 236,137 step labels with no reader involved, and the judged labels are shown to be the weaker target |
| "calibration fails; 0% detection below a 20% budget" | **not solved — and the appearance of a solution is circular.** The "0 false alarms at every budget, precision 1.000, latency 0" figures are exactly the numbers an *oracle* returns, because the target is defined as "k consecutive quiet windows" and the detector is "k consecutive quiet windows": the monitor restates its label. No calibration claim can rest on it. The independent sequential formulation that *would* address this is degenerate (§2.16, §2.17): the event occurs in 86.6% of runs, recall 1.000 comes with false-alarm rate 1.000. **G5 stays open.** |
| "unsolved: a stationary statistic" | **solved, tested, and it does not help** — reported |
| "stagnation is not failure (AUC 0.61)" | **replaced by a mechanism**: waste *is* outcome-relevant within instance, but the predictable part (quietness) is not the decisive part (direction), and a future-aware upper bound shows no observable of this kind can close the gap |
| — (no comparison to the field) | **compared**: this study's features beat `exact_burst`, `ngram_loop`, a TF-Norm redundancy surrogate, OpenHands' five production stuck patterns and AgentStop's feature shape on all three tasks, while the deployed heuristics sit at or near chance |
| — (sampling budget unexamined) | **swept on both corpora**: smooth curves with broad maxima; the published setting is within 0.021 of its own optimum on each; a 6× change in stride moves the AUC by ≤ 0.006 |
| — (fold-split stability unexamined) | **checked under five fold seeds**: sd 0.0001–0.0010 on every headline fit, and 0.0006 on the structural result |
| — (waste label could be counting revision) | **measured and bounded**: the pooled rate falls 0.843 → 0.788 if every superseded edit is counted as progress, single-edit runs still waste 64%, and the within-instance signal comes entirely from never-revisited edits |

---

## 4. Limitations, stated plainly

1. **Telemetry is not correctness.** A surviving line is not a correct line. That gap is why
   §2.4's third row exists — the study measures the gap rather than hiding it. The claim is
   about *shipped work*, not about being right.
2. **The label is defined against the agent's own patch, so revision counts as waste.** Measured
   and bounded: counting every superseded edit as progress lowers the pooled rate from 0.843 to
   0.788, and single-edit runs still waste 64%. The within-instance outcome signal comes entirely
   from edits that were *never* revisited (Δ +0.157, *p* = 6.9 × 10⁻¹³) while superseded edits
   carry none (Δ +0.049, *p* = 0.078) — so the headline rests on the part revision cannot explain.
   What cannot be separated offline is the residual case: a superseded edit that *was* useful and
   was rewritten for a better reason. `self_reference.json` states this.
2. **The network has been down since 2026-09-10**, so the results use 14,750 of the shard's
   usable Terminal-Bench trials and 26,679 of the dataset's ~80,036 SWE-agent trajectories.
   `scripts/watch_network.py` polls and the pipeline resumes without recomputation.
3. **One model family in the SWE-agent corpus** (Llama-3.1 70B / 8B / 405B via SWE-agent v1),
   so cross-model claims rest on Terminal-Bench's 33 models.
4. **The gold cross-check covers 386 windows, not 1,198**, because the join needs a window at
   exactly the annotated step. It compares families; it does not re-run the first version's
   table.
5. **Waste shares depend on the patch-overlap test.** A reformatted line counts as wasted.
   The direction is conservative but not neutral.
6. **The two corpora are not symmetric.** The workspace channel and the no-op measure exist
   only where the scaffold prints file line counts (SWE-agent), so Terminal-Bench cannot
   contribute to the waste measurement itself — only to the window-level comparison.
7. **Terminal-Bench's release bounds the corpus, not the parser.** The 2,487 trials without
   actions were read and are crashes with no tool call. A prose-then-tool-call turn-grouping
   bug was found and fixed; a before/after comparison on 400 trials found **zero** step-count
   differences, so the fix did not change the analysis. Reported because it was investigated.

---

## 5. The claim this supports

> Coding agents spend ~80% of their editing on lines that never reach their own final patch — of
> which the unambiguous part is 19.1% dead-end edits. That waste is a stable, run-level property,
> it is outcome-relevant within the same task, and more editing is monotonically worse — only 3.8%
> of runs making more than twenty edits resolve their issue. A reference-free runtime monitor can
> report, in the same window it happens and on held-out tasks, that an agent's workspace has
> stopped moving — but that is a restatement of the event, not a detection of it, and every
> non-circular formulation of the same task fails (§2.17). The monitor **cannot** detect that the
> agent is moving to the wrong place, which is what decides the outcome. The field's detection
> problem is close to solved for quietness and close to unsolvable for directionality from
> action-only observables — and a future-aware upper bound shows the limit is the observable
> channel, not the label or the model.

---

| stage | script | artifact |
|---|---|---|
| per-step tables from both corpora | `scripts/build_step_table.py` | `data/processed/steps/{tb2,nebius}/` |
| online window features, raw + `_s` + `_o` | `scripts/extract_windows.py` | `data/processed/windows/{tb2,nebius}/` |
| monitor zoo, between/within decomposition, calibration | `scripts/analyse_windows.py` | `results/rebuild/<corpus>_w10/analysis.json` |
| wasted work vs the final patch | `scripts/analyse_alignment.py` | `results/rebuild/alignment.json` |
| step-level prediction of waste | `scripts/analyse_step_task.py` | `results/rebuild/step_task.json` |
| run-level waste, temporal profile, opening prediction | `scripts/analyse_waste_runs.py` | `results/rebuild/waste_runs.json` |
| four waste labels + future-aware ceiling | `scripts/analyse_routeA.py` | `results/rebuild/routeA.json` |
| cross-corpus transfer | `scripts/analyse_transfer.py` | `results/rebuild/transfer.json` |
| window-length / stride / feature-form capacity sweep, both corpora | `scripts/analyse_capacity.py` | `results/rebuild/capacity_nebius.json`, `capacity_tb2.json` |
| head-to-head vs the field's published detectors | `scripts/analyse_detector_families.py` | `results/rebuild/detector_families.json` |
| the edit's own structure as a predictor | `scripts/analyse_edit_structure.py` | `results/rebuild/edit_structure.json` |
| revision-vs-waste confound, measured | `scripts/analyse_self_reference.py` | `results/rebuild/self_reference.json` |
| independent re-derivation of the line comparison | `scripts/verify_extraction.py` | `results/rebuild/extraction_verification.json` |
| the coarse rate split into revision vs dead end | `scripts/analyse_dead_end.py` | `results/rebuild/dead_end.json` |
| fold-seed stability of every headline fit | `scripts/analyse_seed_stability.py` | `results/rebuild/seed_stability_{nebius,tb2}.json` |
| held-out-scaffold transfer | `scripts/analyse_scaffold_transfer.py` | `results/rebuild/scaffold_transfer.json` |
| is the run-level block just run length | `scripts/analyse_detector_value_length.py` | `results/rebuild/detector_value_length.json` |
| does the detector statistic predict the objective outcome | `scripts/analyse_detector_value.py` | `results/rebuild/detector_value.json` |
| does dead-end timing matter | `scripts/analyse_dead_end_timing.py` | `results/rebuild/dead_end_timing.json` |
| is file choice predictable early | `scripts/analyse_on_target.py` | `results/rebuild/on_target.json` |
| does a wasted edit teach the agent anything | `scripts/analyse_dead_end_recovery.py` | `results/rebuild/dead_end_recovery.json` |
| an absolute waste alarm, calibrated out of sample | `scripts/analyse_waste_alarm.py` | `results/rebuild/waste_alarm.json` |
| sequential detection on the objective event (degenerate) | `scripts/analyse_sequential_deadend.py` | `results/rebuild/sequential_deadend.json` |
| behavioural signature of the label disagreement | `scripts/analyse_label_signature.py` | `results/rebuild/label_signature.json` |
| is survival an edit-size artefact | `scripts/analyse_size_artifact.py` | `results/rebuild/size_artifact.json` |
| what one wasted edit costs the run | `scripts/analyse_dead_end_cost.py` | `results/rebuild/dead_end_cost.json` |
| how much of the old 0.78 was the label | `scripts/analyse_label_cost.py` | `results/rebuild/label_cost.json` |
| what the waste costs in tokens and dollars | `scripts/analyse_cost.py` | `results/rebuild/cost.json` |
| whether dead-ending is a task or agent property | `scripts/analyse_dead_end_variance.py` | `results/rebuild/dead_end_variance.json` |
| how early a run's fate can be called | `scripts/analyse_early_prediction.py` | `results/rebuild/early_prediction_{nebius,tb2}.json` |
| why the stationary transform destroys signal | `scripts/analyse_stationarity_mechanism.py` | `results/rebuild/stationarity_mechanism.json` |
| calibrated sequential detection + cost model | `scripts/analyse_sequential.py` | `results/rebuild/<corpus>_w10/sequential.json` |
| reconcile with the first version's judged labels | `scripts/analyse_gold_crosscheck.py` | `results/rebuild/gold_crosscheck.json` |
| every headline number, machine-collected | `scripts/collect_rebuild_numbers.py` | `results/rebuild/rebuild_numbers.json` |
| invariant tests | `scripts/run_rebuild_tests.py` | 10/10 |
| artifact consistency | `scripts/check_rebuild_consistency.py` | passes |

---

## 6. Reproduce

```powershell
cd research
python scripts/run_rebuild_tests.py                     # 10 invariant tests
python scripts/build_step_table.py --corpus all         # ~25 min, resumable
python scripts/extract_windows.py --corpus tb2   --w 10 --stride 3
python scripts/extract_windows.py --corpus nebius --w 10 --stride 3
python scripts/analyse_windows.py    --corpus tb2   --w 10
python scripts/analyse_windows.py    --corpus nebius --w 10
python scripts/analyse_alignment.py
python scripts/analyse_step_task.py --k 8
python scripts/analyse_waste_runs.py
python scripts/analyse_routeA.py --k 8
python scripts/analyse_transfer.py
python scripts/analyse_sequential.py --corpus tb2    --w 10
python scripts/analyse_sequential.py --corpus nebius --w 10
python scripts/analyse_gold_crosscheck.py
python scripts/collect_rebuild_numbers.py
python scripts/check_rebuild_consistency.py
```