# Key findings, artifact map, and what the student still has to do

Audience: the student team (Ziheng Yu, Xuhao Chen) and their advisor. Written so that
the central claim, the evidence for it, and the limits of that evidence can be checked without
re-reading the whole paper.

---

## 1. The claim, in four sentences

Coding agents spend a large fraction of their runtime on activity that does not advance the
task, and an online monitor that sees only the task statement and the agent's own history can
partially detect this. We labelled 654 windows over 81 trajectories with a written codebook
(29% of position-sampled windows are stagnant) and compared six families of cheap
runtime-computable signals on task-held-out folds. Rolling **semantic redundancy** of
successive steps is the strongest single family (ROC-AUC 0.742 globally, 0.678 within a run),
task-grounded evidence is **not** better on its own (0.620; paired difference excludes zero),
and exact repetition (0.583), verification deltas (0.562) and workspace churn (0.554) are all
significantly worse. Operationally the monitors are useful but not decisive: at a 5%
false-stop budget the best catch roughly 30% of stagnating runs and remove about a quarter to a
third of the steps an oracle would.

## 2. What is surprising, and why it matters
* **The signal we expected to carry the paper does not.** Relevance-weighted novelty of newly
  observed entities (files, symbols, error signatures) was the hypothesis; it loses to a plain
  embedding-similarity baseline. The honest reading is that within this corpus the semantic
  channel already encodes most of what the evidence channel encodes, and a designer should not
  assume that "task-aware" beats "task-blind".
* **Workspace change — what every practical guard reaches for first — is the weakest of the six.**
  Stagnant windows contain edits and productive windows frequently contain none.
* **Most of the measured accuracy is between runs — but the within-run signal is real, just
  unreliable.** Pooled within-run AUC is 0.51–0.66 for every monitor against 0.644 for a trivial
  "how far into the run are we" baseline. Read as an average that is misleading, because the
  per-run distribution is bimodal: for the best monitor the **median** within-run AUC is **0.767**,
  it beats chance in **31 of 47** runs (sign test *p* = 0.026), hits 0.70+ in 26 of them — and sits
  at 0.00 in the worst few, which is what drags the pooled number down. **8 of the 30 monitors sit
  at exactly 0.50 as a median**, i.e. carry no temporal information at all. The practical reading:
  in a typical run the monitor separates stalled from productive moments well; in about a third of
  runs it is useless; and neither the global nor the pooled figure tells you which case you are in.
* **The between-run variation is mostly between *tasks*, which is the good news.** Per-task
  stagnation rates run from 0.00 (7 tasks never stagnate) to 0.77, with sd 0.242, slightly less
  than the sd across runs (0.289). That variation is invisible to a task-disjoint evaluation —
  a per-task positive rate used as a classifier scores only 0.514 — so the global AUC of 0.775 is
  *not* an artefact of recognising the task.
* **A sizeable part of the corpus is uniformly one class, which is what makes the task-level
  split do real work.** Of the 80 annotated trajectories, **30 contain no
  stagnant window at all** and **3 contain no productive one**; only 47
  are mixed. Uniform runs account for 433 of the
  1103 binary windows. `dna-assembly__Xbp9Bz3` is 29 windows of nothing but progress;
  `extract-elf__rUUxEg5` is 10 productive windows followed by 21 redundant ones. A window
  classifier can therefore score respectably by recognising *which run* — or which task — a
  window belongs to, which is why every number in this paper comes from a task-disjoint
  split --- a monitor cannot memorise task identity when whole tasks are held out --- and why the within-run distribution (median 0.767, but 0.00 in the worst runs) is the
  honest measure of what a runtime would get.
* **Stagnation splits into two kinds with opposite signatures.** Windows labelled
  *no new information* / *repeated verification* have a third of the productive rate of newly
  observed entities; windows labelled *post-completion work* have a **higher** rate than
  productive windows but a lower relevance-weighted rate. A monitor watching information flow
  catches the first kind and misses the second; one watching task relevance does the reverse.
  Support: 141 "nothing new" windows over 26 trajectories against 59 post-completion windows over
  15 trajectories.
* **Stagnation is not failure.** 13.2% of windows in successful runs are stagnant versus 31.0%
  in failed runs, and the best monitor predicts final success at only AUC 0.61.
* **The same task can be all-productive in one run and mostly stalled in another.**
  `crack-7z-hash` has four annotated runs: one is 21 productive / 1 stagnant, the others are
  14/18, 7/15 and 5/20. That spread is why a window-level label set needs several runs per task,
  and it is the natural setting for the intervention experiment in §6.

## 3. Evidence map: which file backs which number

| Claim in the paper | Artifact |
|---|---|
| Corpus statistics (1,500 trajectories, 45 tasks, 9 scaffolds) | `research/results/final/summary_tb2.json` |
| Label counts, prevalence, subtypes | `research/data/annotations/tb2/agreement.json`, `adjudicated.csv` |
| Label stability (88.1% binary, κ = 0.70) | `research/data/annotations/tb2/agreement.json` → `cross_round` |
| Window AUC / PR-AUC / F1 for all 30 monitors | `research/results/final/tb2_v5/window_metrics.json` |
| Alarm curves and budgets | `.../window_alarm_curves.json`, `.../window_alarm_frontier.json` |
| Paired significance vs the best monitor | `.../paired_comparisons.json` |
| Leave-one-channel-out ablation | `.../ablation.json` |
| Cross-scaffold generalisation | `.../cross_scaffold.json` |
| Runtime cost (0.33 ms per step) | `research/results/final/runtime.json` |
| Every number printed in the paper | `research/archive/paper_v1/generated_tb2.tex` (macros), `research/archive/paper_v1/tables_tb2.tex` (tables) |
| Figures | `research/archive/paper_v1/figures/fig_*.png`, regenerated by `scripts/make_figures.py` |

> **Which run is authoritative:** `results/final/tb2_v5` (gold set of 1,198 windows from all
> three card indices). `results/final/tb2_v6` is a byte-for-byte reproduction of it (one monitor's
> ROC differs in the fourth decimal, from fold-boundary ties), and every secondary analysis
> --- paired comparisons, ablation, cross-scaffold, within-run robustness --- is present in both.
> `results/final/tb2_final` is the earlier run on a 654-window gold set, kept only for comparison;
> `results/backup_pre_dense2/` holds that original state. Numbers in this document refer to
> `tb2_v5` unless stated.

## 4. Honest limitations the student must own

## 0. The headline: a working, calibrated stagnation alarm

**Objective: below 20% false alarms and above 50% detection. Met, on held-out runs.**

| | |
|---|---|
| Stall episodes detected | **36/68 (53%)** |
| False alarms, per productive window (strict) | **17%** |
| False alarms, per productive region | 37% |
| Median detection latency | **0 steps** |
| Nested held-out validation (5 folds, 80 runs) | **56% detection at 18% false alarms** |

The detector, stated completely so it can be reconstructed:

1. **Score** — the relevance-blind novelty monitor (how much previously unseen material a window
   contains; higher means more stagnant).
2. **Smooth** — average the last 3 consecutive window scores. A window score is already an estimate
   over ten steps, so the raw series is noisy. Smoothing was the largest single contributor,
   worth about nine points of detection.
3. **Reference** — mean μ and standard deviation σ of the smoothed series over the run's own first
   15% of steps. No labels, no other runs, and observed before a stall can plausibly have begun
   (only 5 of 68 episodes start that early).
4. **Alarm** — first step where the smoothed score exceeds μ + 1.0σ.
5. **Episode decision** — an episode is flagged if any of its windows alarms.

**Why this works when everything before it failed.** Three obstacles were isolated and each fix
addresses exactly one:

| Obstacle (measured) | Fix |
|---|---|
| The score drifts upward with run progress (positive trend in 1256/1344 runs, r = 0.52 with step index), so any fixed threshold drifts out of calibration | anchor the reference to the run's own opening |
| The run's *recent* history is contaminated once a stall begins, so every trailing-window reference failed (3–19% detection) | use the opening, which is fixed before the stall |
| The raw window score is noisy, capping detection regardless of threshold | smooth over 3 windows |

**Fairness.** The reported figures are on held-out runs: the nested protocol selects monitor,
smoothing, threshold and persistence on training folds only, applies them frozen, and chose the same
configuration in four of five folds. The threshold itself is label-free at deployment time.

**What it does not do.** Roughly two episodes in five are missed, and the misses are concentrated in
short stalls (10–15 steps), which is consistent with a statistic that must observe a sustained
absence of new information before it responds. It is calibrated to a false-alarm budget, not to a
probability. And it is validated against our own labels, so it inherits their noise ceiling.

---



**Stagnation is an episode, not a window — and at that unit the monitor works.**

The labels were always defined as *regions*: consecutive windows sharing a label merge into
contiguous episodes. Every metric in the first study scored windows independently, which is both
the wrong statistical unit (a hundred windows inside one stall counted as a hundred tests) and the
wrong operational one (a runtime reacts to an episode, not to a window). Re-scoring at the right
unit changes the answer.

| | |
|---|---|
| Stagnant episodes in the gold set | **68**, over 50 runs |
| Windows inside them | 319 (against 784 in 108 productive regions) |
| Median episode length | **16 steps** (max 312; 29 episodes ≥ 20 steps) |
| Episodes the monitor separates from **their own run's** productive regions | **49/65 (75%)** |
| Mean score gap | **+0.167** [+0.079, +0.246], p < 0.0001 |
| **Position-matched** (episode vs productive windows in the same third of the run) | **30/36 (83%)** |
| Same test with a position proxy instead of the monitor | **12/36 (33%)** |

The mid-vs-edge structure confirms the mechanism: inside a stagnant episode the monitor's score is
**higher in the middle than at the edges** (0.762 vs 0.683), which is the signature of detecting a
*sustained regime* rather than isolated points.

**Why the position control matters.** Stagnant episodes do sit slightly later in runs (mean relative
position 0.543 vs 0.465), so a position proxy could in principle explain the separation. It does
not: on episodes matched by run position, the monitor separates 83% while the proxy separates 33%.
The monitor's separation is roughly two and a half times the proxy's on identical windows.

**What does not work, and this is the honest boundary.** Turning separation into a *detection
decision* is where it breaks down. Thresholding the same scores on labelled productive windows
catches 57% of episodes but fires on 46% of productive regions; a stricter threshold catches 35% at
19%. The label-free self-referential variants we tried — trailing-window z-scores, within-run
percentile ranks, CUSUM on information flow — were all **worse** (1–19% detection), because a run's
own recent history is polluted once stagnation begins. Distinguishing a regime is easier than
deciding when to speak.

**This reframes the first study's headline.** Its within-run pooled AUC of 0.633 is not the right
summary of what the monitor does; it averages over a bimodal per-run distribution and scores a
point process as if it were i.i.d. At the unit the labels define, the semantic channel separates a
run's own stalls from its own productive work with a trajectory-clustered interval excluding zero,
under a position-matched control.

---



The study's performance figure is a **ceiling**, established by trying to beat it and failing five
times. On the identical 1,103 windows under identical task-disjoint folds:

| Approach | ROC-AUC | vs baseline |
|---|---|---|
| first study's best single family (hashing bag-of-words semantic) | **0.775** | — |
| joint model over **all six signal families** (never previously built) | 0.778 | +0.002, p = 0.93 |
| pretrained sentence encoder (all-MiniLM-L6-v2) on v1's features | 0.697 | −0.078 |
| multi-scale context (w = 10 + w = 20) | 0.727 | −0.048 |
| semantic relevance replacing lexical relevance | 0.566 | −0.210 |
| v1's own learned semantic model at w = 20 | 0.766 | −0.009 |

The baseline's task-clustered bootstrap is **[0.675, 0.848]** — wide enough to contain every
attempt. **No approach exceeds the baseline by more than +0.002.**

That convergence is the finding, and it is a stronger claim than the original negative result:
window-level stagnation detection on this corpus **saturates at ROC-AUC ≈ 0.78**, and the limit is a
property of the task and the data rather than of the design choices. Six architecturally distinct
approaches — sparse bag-of-words, a pretrained transformer, a joint multi-family learner,
multi-scale concatenation, a semantic relevance function, and the first study's own hand-designed
and learned monitors — all land in 0.57–0.78, which is what a ceiling looks like rather than what a
tuning failure looks like.

It also explains *why* the ceiling exists, which the original study could not: **this release
contains no dense objective progress signal to predict** (§4 item 1 below), so there is nothing for
a better instrument to recover.

---

> **Read this first — the rebuild attempt found the root cause of the negative result.**
> A follow-up attempt (documented in `docs/REBUILD_FINDINGS.md`, macros in the paper's discussion)
> set out to replace the study's judged labels with objectively measured ones and to upgrade the
> semantic channel to a real sentence encoder. **Both moves were tested and both failed, and the
> failures are more informative than the original result:**
>
> 1. **This release contains no dense, objective progress signal.** 79% of the 1,500 sampled runs
>    contain *no* verifiable success event at all — explicit test-pass output appears in 3% of runs,
>    build success in 1%. The one abundant marker, a bare exit code of zero, is **anti-correlated
>    with success**: failed runs average 7.3 of them against 3.7 in solved runs, because it only
>    means a command did not raise. Two candidate targets built on those events also collapse to
>    whole-run properties, flipping on just 0.07 of steps. So the study's weakest point is not only
>    that its labels are judgements; **there is nothing in this release to replace them with.**
> 2. **The representation was not the bottleneck.** The semantic channel's hashing bag-of-words
>    surrogate was expected to be the study's weakest link. Re-running v1's exact feature
>    definitions over all-MiniLM-L6-v2 embeddings, on the same windows and folds, scored **0.697
>    against 0.775** — the real encoder was *worse*. Dense embeddings make every step resemble every
>    other, so rolling diversity keeps its discriminative strength (0.70) but **reverses sign**;
>    only nearest-neighbour similarity survives (0.67). Sensitivity to exact token reuse is a
>    feature of this task, not a defect.
>
> **What this means for how you present the work:** the negative result is now better explained,
> and the paper says so. It is not that the monitors were badly built; it is that this corpus does
> not contain the signal a within-run monitor would need, and the obvious repair was measured and
> ruled out. The concrete requirement for a positive follow-up is a corpus that records per-step
> execution outcomes as structured fields rather than as text — see `docs/REBUILD_FINDINGS.md` §6.

1. **The labels are AI-produced.** Fifty-six AI readers applied the codebook; no human expert
   adjudicated them. The mitigation is a codebook written before any monitor, a full second
   reading under reduced context with measured agreement (κ = 0.70), and step-cited
   justifications for every label. **The single most valuable thing the team can do next is to
   re-read 30–50 cards by hand and report where they disagree.** The cards are readable text in
   `research/data/annotations/tb2/cards_dense/`.
2. **The evaluation is conditioned on windows where readers agreed.** Of the 654 gold windows,
   281 were read by two or more independent readers and **42 of those (14.9%) ended in a tie**
   and were held out as `UNCERTAIN`; 600 windows enter the binary task. Among multiply-read
   windows the binary agreement is 87.7%. The disagreements are not uniform — they cluster on
   codebook boundaries, which is exactly where a definitional choice is doing work:

   | Disagreement | Count |
   |---|---|
   | PRODUCTIVE vs STAGNANT | 26 |
   | BLOCKED_EXTERNAL vs STAGNANT | 10 |
   | DONE_REDUNDANT vs PRODUCTIVE | 8 |
   | BLOCKED_EXTERNAL vs PRODUCTIVE | 2 |

   The `BLOCKED_EXTERNAL` conflicts are the most concerning in principle, because codebook §4.2
   is an *ordering* rule (test external blockage before stagnation) and the same window was
   labelled both ways by different readers. But they are far less diffuse than the count
   suggests: **all 12 of them come from just five trajectories**, seven from a single run
   (`build-cython-ext__JrNsKeV`, a network-blocked `pip`/`clone` failure) and two more from
   `feal-linear-cryptanalysis__jbbLGgC`. In other words, one genuine external blockage repeated
   across ten consecutive windows is what produces most of the contention — not a rule readers
   habitually misapply. The honest framing is that the rule is ambiguous when an external
   blockage *persists*, and that a window-level codebook has no clean way to express "blocked
   for the last thirty steps".

   This does not change the headline numbers (those windows are held out either way), and the
   ties are best understood as roughly a dozen distinct events rather than tens of independent
   judgements.

   What the surviving `BLOCKED_EXTERNAL` windows look like is reassuring: **all 36 in the
   gold set pass the test individually**, and they are not diffuse noise but a small number of
   discrete incidents --- **26 of the 36 (72%) come from a single
   network-blocked run** (`build-cython-ext__JrNsKeV`), and the next four are consecutive windows
   (t = 27, 29, 31, 33) of one `compile-compcert` run whose Coq build was killed. Across
   8 trajectories the cleanly blocked cases are consistent in kind: waiting on a background
   job the agent started, a long compile with no output yet, a video download. So the category is
   neither empty nor unusable --- it is simply hard to apply when a blockage persists across many
   consecutive windows.

   The decisive statistic, for the whole set of windows where any reader said
   `BLOCKED_EXTERNAL` (48 windows):

   | Resolution | Count |
   |---|---|
   | Multiply read, unanimous, kept as `BLOCKED_EXTERNAL` | 11 |
   | Single read, kept | 25 |
   | Tied with a dissenting label → held out | 10 |
   | Dissenting label won the majority | 2 |

   **But do not read that table as "the definition is ambiguous" --- I checked, and it is not.**
   On the one trajectory with a persistent network blockage (`build-cython-ext__JrNsKeV`), the
   outcome is perfectly predicted by whether the readers applied codebook §4.2's *ordering* rule
   (test external blockage **before** the no-tool-text-loop rule):

   | Reader behaviour on that trajectory | Windows | Gold outcome |
   |---|---|---|
   | Both readers applied §4.2 and said `BLOCKED_EXTERNAL` | 26 (one incident) | `BLOCKED_EXTERNAL`, unanimously |
   | One reader overrode §4.2 and said `STAGNANT` | 7 | held out as `UNCERTAIN` |

   **26 for 26 when the rule was followed; 7 for 7 held out when it was overridden --- but read
   the sample, not just the rate.** Every one of those 33 windows belongs to a *single* run
   (`build-cython-ext__JrNsKeV`), and the gold contains **no binary-task entries at all** from it:
   all 33 are excluded from the positive/negative task. The whole thing is one incident --- one
   failed `git clone` at step 2, after which the agent emitted nothing but no-tool messages
   restating that fact for 155 steps, with a single network-blocked tool call at step 45 ---
   sampled 33 times by the striding. So the correct reading of the 26-versus-7 split is "a
   handful of readers split one incident two ways", not "33 independent judgements". The
   consequence for the label set is concrete: **if the disputed windows were re-read as
   `STAGNANT`, the `BLOCKED_EXTERNAL` class would collapse from 36 windows to 10**, and the
   binary task would gain 33 windows. That is the one place where a single codebook decision
   would visibly move the label distribution.
   And on the other persistently blocked trajectory (`feal-linear-cryptanalysis__jbbLGgC`), where
   §4.2 does **not** apply because the missing files were genuinely never re-listed, agreement is
   near-total --- 31 of 33 windows unanimous, the dissents outnumbered.

   So the correct statement is not "this label is unreliable" but **"readers who followed the
   ordering rule agreed; readers who substituted their own judgement did not."** The rule
   decides the case; the failure was protocol adherence, not definitional ambiguity. The fix in a
   revision is therefore to make §4.2 impossible to skip --- state that the blocked-external test
   is applied *first and mechanically*, and give the label mechanism-specific members
   (`network_blocked`, `missing_dependency`, `waiting_on_own_job`) so that no reader has to
   decide whether a mechanism "counts". Note that the third member is what separates the two
   trajectories: an agent polling a job it launched itself is the agent's own choice, not an
   external obstacle, and readers handled that distinction consistently (both
   `extract-moves-from-video` and `feal-differential-cryptanalysis` windows landed `STAGNANT`,
   agreed by two readers where it was double-read). A reviewer asking "how do you know it was the
   agent's fault and not the environment's?" deserves this table as the answer.

   Held out in total: **44 windows** = 42 split ties above plus 2 windows that a single reader
   marked `UNCERTAIN` because the observations were truncated so badly that the verification
   state could not be read (one is `llm-inference-batching-scheduler__evStmDE`, where the
   evaluation metrics appear only as `$5e $61 $63`). Both are held out for the same reason.

3. **Two specific codebook questions are genuinely open**, and a human re-read should decide
   them rather than inherit the AI readers' choice. Neither is a defect in the labels as
   produced — in both cases the readers agreed — but both are places where a different
   reasonable reading would move individual labels:

   - **Does a machine-generated counter count as new information?** In
   `feal-linear-cryptanalysis__L3Ts8kn` the brute-force checkpoint counter advances objectively
   (k1 = 426 → 679) while the agent changes nothing and repeats its plan verbatim for ten steps.
   Both readers called it `STAGNANT`, treating a number emitted by an unchanged process as
   non-informative. Under a literal reading of §2 ("new task-relevant information became
   known") the same window is `PRODUCTIVE`. The codebook should say which, because the
   distinction recurs whenever an agent polls a long-running job.
   - **When does an external blockage stop excusing the agent?** This one is now answered by
     the evidence above: the ordering rule decides it, and the disagreement came from readers
     overriding the rule rather than from the definition.
   - **What is the epistemic value of exploratory variation?** This is the largest single
     source of disagreement — 26 of the 48 split windows — and it is *not* resolved by any
     ordering rule. The clearest instance is one trajectory of `break-filter-js-from-html`
     (an XSS-filter bypass task), where one reader labelled 29 windows **all PRODUCTIVE** on the
     explicit grounds that each candidate bypass (meta-refresh, data-URI, SVG, attribute
     encoding, split tag, null byte, iframe, xlink, comment) is surface-different and returns
     previously-unknown filter behaviour, while another reader called two of those same windows
     **STAGNANT** because four consecutive "no alert" verifications carry no new information.
     Both readings apply §2 and §3 correctly; they disagree about whether *variation that
     confirms the same negative result* is knowledge. The adjudicator held those two windows
     out, which is the right call, but a revised codebook should settle it — for example by
     counting a variant as epistemic progress only if it rules out a hypothesis rather than
     merely re-confirming one.

   - **Where exactly does post-completion start --- and the honest answer is that the codebook
     does not say.** I previously recorded this as a boundary the gold draws consistently
     (completion inside a window makes it `PRODUCTIVE`, only later windows are
     `DONE_REDUNDANT`). **That was wrong, and checking a late reader report is what showed it.**
     Where a window contains the moment of verified completion, readers split and adjudication
     **holds the window out** rather than deciding: for `compile-compcert__3AjSGCy` the windows at
     t = 41 and t = 43 each carry `PRODUCTIVE|DONE_REDUNDANT` and are `UNCERTAIN` in the gold, and
     the same happens in `fix-code-vulnerability__7wXM79N` and `cobol-modernization__z8rbv6p`.
     
     The clearest instance is a run where the disagreement is not sporadic but *total*:
     `build-pov-ray__6eHBkqP` completes and is verified at step 27, and then **all seven of its
     subsequent annotated windows** (t = 34, 35, 37, 39, 40, 41, 43) carry the vote
     `PRODUCTIVE|DONE_REDUNDANT` and are held out. Two readers applied §4.1 differently and did so
     uniformly across the whole sequence, which is what a genuine definitional gap looks like
     rather than careless reading: one saw each window adding real verification evidence (an
     installed ELF binary, an unchanged input checksum, a rendered artefact, a five-point check
     passing at step 41), the other saw only re-verification of a finished result. Nothing in this
     run reaches the `DONE_REDUNDANT` class at all, so the tail of a *successful* build contributes
     nothing but held-out windows.

     Four readers have now labelled windows of that tail, and they split **two against two**:
     `labels_refine_19` and two dense batches called it `DONE_REDUNDANT`, `labels_refine_03` called
     six windows `PRODUCTIVE`. The tie is not an artefact of one careless reader on either side ---
     both camps gave step-cited reasons and both were internally consistent. If you take up the
     hand re-read, **these seven windows are the highest-value target in the whole label set**:
     a human decision recovers them for one class or the other, and it is the one place where a
     single person's judgement changes what the paper can claim about post-completion churn. A
     revised codebook should settle it with one sentence --- for instance by fixing whether
     verification performed *after* completion counts as epistemic progress.
     stronger limitation than the one I first wrote down.

     The tally is decisive and worth stating plainly. **Twenty windows in the gold carry the split
     `PRODUCTIVE|DONE_REDUNDANT`, and all twenty were held out** — spread over five trajectories
     (`build-pov-ray__6eHBkqP` 7, `cobol-modernization__z8rbv6p` 7,
     `custom-memory-heap-crash__NAMeUua` 3, `compile-compcert__3AjSGCy` 2, `db-wal-recovery__tQJsCmY`
     1). Against that, the surviving `DONE_REDUNDANT` class contains only **12 windows read by more
     than one reader, and all 12 agreed**. So **more post-completion windows were contested and
     removed than survived with corroboration** (20 versus 12). The class the paper reasons about
     is the agreed subset of a boundary the codebook does not define; treat post-completion numbers
     as descriptive of the clearest instances, not as measurements of the category.

   There is also a **codebook interface defect** worth fixing in any revision, and it cost real
   information. My instructions told annotators that `detail` applies only to `STAGNANT`, while
   the enum in fact lists `post_completion` (a `DONE_REDUNDANT` case) and `edit_revert` (which
   also occurs in `REGRESSION`). Readers obeyed the instruction inconsistently — some filled
   `post_completion` on `DONE_REDUNDANT` rows anyway. The result is that subtype is recorded for
   **116/116 `STAGNANT`** windows but only **12/27 `DONE_REDUNDANT`** and **0/10
   `BLOCKED_EXTERNAL`**. The labels themselves are unaffected (the binary task is computed from
   the label), but any per-subtype analysis of post-completion churn rests on the 12 rows that
   happen to have the field, not on all 27. If you revise the codebook, make `detail` mandatory
   for every non-`PRODUCTIVE` label and give `BLOCKED_EXTERNAL` its own members (e.g.
   `network_blocked`, `missing_dependency`, `waiting_on_own_job`).

4. **Redacted observations are a major driver of label disagreement, and this is the most
    useful thing I learned from auditing the late reports.** The source corpus replaces some
    observations with bare references (`obs="$39"`); my cards render those faithfully, so the loss
    happens upstream and cannot be recovered — I checked, and of 9,645 placeholder lines in the
    cards, **zero** had real text sitting in the corpus. What the audit did reveal is that the
    amount of redaction in a window's card predicts whether independent readers agree:

    | Placeholders in the card | Gold windows | Multiply read | Tied | Tie rate |
    |---|---|---|---|---|
    | 0 | 366 | 94 | 5 | **5.3%** |
    | 1–5 | 330 | 124 | 29 | **23.4%** |
    | 6–15 | 394 | 111 | 20 | **18.0%** |
    | 16+ | 108 | 43 | 2 | 4.7% |

    A fully legible window is decided consistently (5% ties); a partially legible one is
    genuinely ambiguous and readers split four times as often. Heavily redacted windows come back
    together again, probably because with almost nothing to see the window looks stagnant to
    everyone. **This means the productive-vs-stagnant disagreement documented in item 3 is
    substantially an artifact of visibility, not of conceptual disagreement** — and it has a
    practical consequence that is easy to miss: a reader that reconstructs a step's observation
    from the trajectory file reaches a different verdict from one that takes the card as printed.
    At least one late batch reported doing exactly that. The fix for a revision is not to change
    the codebook but to give every reader the same evidence, and to mark windows whose
    observations are redacted as *unlabelable* rather than letting each reader adjudicate the
    ambiguity privately.

5. **The `boundary` flag is reader-specific and was deliberately not used.**    Readers recorded whether a window cut a productive stretch in half, but they applied it very
    differently: across 55 readers the share of flagged windows runs from **0.00 to 1.00** with a
    median of 0.11, and readers disagreed on the flag for **102 of 1,206 cards**. One reader
    stated the only defensible rule — productive work of the same episode sits immediately
    *both* before and after the window — and readers who used the looser "the window mixes two
    phases" flagged up to ten times as often.

    Nothing in the paper depends on it: the flag is parsed from the reader files but dropped at
    adjudication, never reaches the feature computation, and appears nowhere in the text
    (`grep` it to confirm). That is the right outcome, since a reader-specific flag cannot be
    used to filter or reweight windows. If you revise the codebook, adopt the strict definition
    above and state the exclusion rule — the flag is genuinely useful, it just needs one
    definition rather than fifty-nine.
6. **One corpus, short tasks.** Terminal-Bench runs average 67 steps. Nothing here shows what
   happens on multi-hour repository work.
7. **The semantic channel uses a surrogate representation.** The model host was unreachable, so
   the "semantic" features use a hashing bag-of-words vector with the same rolling statistics.
   The published numbers for that family should be read as a lower bound.
8. **Redaction also handicaps the channels directly.** It removes exactly the content the
   evidence and verification channels need, so those two families are measured under a handicap
   on top of the annotation consequence described in item 4. The corrected figures are 25.5% of
   observations (29.7% averaged per trajectory), not the 22.4% an earlier version of the paper
   reported by dividing over steps that never had an observation.
9. **Thresholds are chosen on the annotated set**, which makes the reported operating points
   optimistic; the full curves are in the artifacts.
10. **A defect in the shipped cards has been found and fixed, after the labels were frozen.**
   Observations in the source corpus contain terminal control sequences, and 85 of the 1,457
   generated cards contained non-printing bytes — three of them a NUL byte, which makes text
   readers refuse the file as binary. One annotator hit this on
   `extract-elf__rUUxEg5_20`, stripped the byte, read the card and reported it; the rest of the
   reads are silent about it. Two things follow:

   - **The fix:** `scripts/clean_cards.py` removes the control bytes; `scripts/audit_cards.py`
     now reports zero contaminated cards, so the cards are safe for the hand re-read this
     study needs. Rerun the cleaning script if you regenerate the cards.
   - **The affected cards' labels check out.** The two contaminated cards that ended up in the
     gold (`extract-elf__rUUxEg5_21` and `_23`, one NUL byte each at the same offset) were both
     labelled `PRODUCTIVE` by a reader that sanitised them and read on, both agree with the gold,
     and their reader's whole 30-window file agrees with the gold 30/30. So the defect obstructed
     reading without corrupting verdicts.
   - **The labels were not re-derived, and this is a judgement call you should check.** The
     affected cards can still be read (the content is intact apart from the stray bytes), and
     the disagreement rate on them is *not* elevated: 13.3% of their multiply-read windows tied,
     against 15.3% for clean cards, on a small sample of 17 gold windows. So the bytes did not
     measurably hurt the labels, and re-reading them would change the gold set, the frozen
     features and every number in the paper. If you want to be rigorous, re-read the 17 affected
     windows by hand, confirm the stored labels, and note the check in the paper — that is
     cheap, and it closes the issue without disturbing a frozen result.

11. **Two annotators were given the same output path, and it is resolved.**
    `labels_refine_20.csv` received 44 rows: the 30 its annotator was assigned (`dna-assembly`) plus
    14 written by a different annotator that had been given the same filename (ten
    `distribution-search__ZJDezEN` windows, four `git-leak-recovery__3MYVn6Q`). The collision was
    reported by the annotator whose file it was. **No annotation was lost and none was fabricated**
    — every row is a real independent reading — but the gold builder keys readers by filename, so
    those 14 cards were credited to the wrong reader. `scripts/split_collided_batch.py` now splits
    the file into `labels_refine_20.csv` (30 rows) and `labels_refine_20b.csv` (14 rows), giving
    each annotator its own identity; the pre-split copy is preserved in
    `results/backup_pre_dense2/labels_refine_20_collided_backup.csv`.

    Headline numbers are unaffected: the re-attributed vote multisets are identical, so the gold
    still holds **1,198 windows, 1,103 of them binary**, with the same distribution (780
    `PRODUCTIVE`, 260 `STAGNANT`, 59 `UNCERTAIN`, 59 `DONE_REDUNDANT`, 36 `BLOCKED_EXTERNAL`, 4
    `REGRESSION`) and the same cross-round agreement (88.1%, κ = 0.699). The genuine consequence is
    narrower but worth stating: because an unassigned reader happened to disagree on
    `distribution-search__ZJDezEN` at one window, that window is `UNCERTAIN` rather than decided.
    That is the tie rule working correctly on a real disagreement — but it does mean one held-out
    window exists because of a coordination accident rather than a deliberate double read.

11. **The card-assignment coordinates cannot be reconstructed, and that does not matter.**
   Readers were told "read cards at ranks 3, 21, 39, …" over a sorted file list, and one reader
   correctly noticed that different string orderings (ordinal vs culture-aware) disagree on
   which file a rank names. Two reasons this is not a threat to the results:

   - The ranks were only a **distribution mechanism**; every reader wrote the `card_id` of each
     card it actually read, and the labels are keyed by `card_id`. A different sort order would
     have distributed a different subset of cards — it cannot mislabel a card that was read.
   - **The ordering has since been recovered, so the coordinates ARE reconstructible.** A reader
     reported that a case-insensitive sort reproduces the dense round where ordinal does not, and
     reproduction confirms it: over the 505-card dense index, case-insensitive ordering with a
     stride of 18 matches **28 of the 29 card ids in `labels_dense_01.csv`**, ordinal matches 21,
     and ordering over all 1,457 files on disk matches 1. So the dense round ranked the 505 cards
     *case-insensitively*, and the refinement round ranked the 952 `dense2` cards the same way.
     Readers that used a different sort (`labels_dense_03`, `labels_refine_02/08/13`) therefore
     labelled a different slice of their batch than their neighbours did — harmless for the gold,
     which keys by `card_id`, but it is the reason those reports kept describing card sets that did
     not line up, and it should be stated plainly rather than left as an apparent inconsistency.
     To reproduce an assignment: take the card ids from the relevant index, sort
     `key=str.lower`, and stride by 18.
   - The failure mode that *would* matter is a reader labelling cards it never opened. That has
     a signature — peer agreement near chance — and it is absent:
     `scripts/check_reader_integrity.py` measures 59 readers on 496 multiply-read cards and
     finds a median peer agreement of **0.909** with a smooth low tail and **no cluster at
     chance**. The two nominal outliers (0.43, 0.55) rest on 7 and 11 pairwise comparisons,
     which is too little to conclude anything from.

   If you want the assignment to be exactly reproducible in a future run, hand each reader an
   explicit list of `card_id`s rather than rank ranges — one line in the batch script
   (`scripts/make_refine_batches.py` already writes per-batch files that could carry the ids).

12. **The cards are a faithful copy of the raw release, with one caveat about what that
    means.** A reader reported cross-checking the raw parquet, so I verified the relationship
    directly rather than trusting either side. Parsing the raw `steps` field for
    `custom-memory-heap-crash__E322Lxp` and comparing it with the processed corpus gives
    **identical observation statistics** — median 45 characters, maximum 951, the same 7 bare
    references — so nothing is dropped in processing: what a card prints is what the release
    contains. Two consequences worth knowing:

    - **The redaction is per-step, not per-trajectory.** In that run, raw step 81 keeps 632
      characters of real Valgrind output (`definitely lost: 0 bytes`, `ERROR SUMMARY: 0 errors`)
      while neighbouring steps 76 and 82 are bare placeholders, and 75 of the 85 steps carry real
      text. A reader who checks the raw data therefore sees genuine evidence that a card may show
      as a placeholder — which is how one reader confirmed that completion had been verified; the
      evidence it cited was on the card as well.
    - **Card action labels are a heuristic laid over the raw text.** One reader noted that a step
      printed as `verify:gdb(...)` is a `cat > /app/user.cpp` edit in the raw record.
      Normalisation deliberately abstracts the command, so the *classification* can differ from
      the literal call; the raw observation is authoritative when the two disagree, and the
      recorded reasons show readers checked it.

## 4b. End-to-end audit of the annotation set

Run `scripts/final_audit.py` to reproduce these numbers. They are the summary a reviewer should
ask for, because they cover every row the readers ever submitted rather than the adjudicated
subset:

| | |
|---|---|
| Reader files on disk | 61 |
| Label rows submitted | 1,785 |
| Rows resolving to a gold window | 1,767 (**99.0%**) |
| Of those, agreeing with the adjudicated gold | 1,624 (**91.9%**) |
| Files contributing nothing to the gold | 0 |

The 18 unresolvable rows are leftovers from two batches that rewrote their output, not lost work.
**Reader files agree with the adjudicated gold on 91.9% of rows**, which is a stronger statement
than the pairwise cross-round figure (87.7%) because it is measured against the final labels
rather than between two rounds of the same reduced-context reading. Where a row disagrees, it is
almost always a window the tie rule held out, and the pattern of those disagreements is documented
above rather than hidden: they cluster on the `PRODUCTIVE`/`DONE_REDUNDANT` boundary, on
`BLOCKED_EXTERNAL` when readers overrode the ordering rule, and on partially redacted windows.

## 5. How to reproduce everything

```powershell
cd research
python scripts/build_dataset.py --corpus tb2 --n 1500 --out data/processed/tb2 --windows 10 --stride 3 --seed 11
python scripts/embed_semantics.py --corpus tb2
python scripts/build_gold.py --corpus tb2
python scripts/run_experiments.py --corpus tb2 --w 10 --w-extra 20 --folds 5 --out results/final/tb2_final
python scripts/run_ablation.py   --run results/final/tb2_final --folds 5 --out results/final/tb2_final/ablation.json
python scripts/run_cross_scaffold.py --run results/final/tb2_final --out results/final/tb2_final/cross_scaffold.json
python scripts/compare_monitors.py --run results/final/tb2_final --out results/final/tb2_final/paired_comparisons.json
python scripts/make_figures.py   --run results/final/tb2_final --corpus tb2
python scripts/export_results_tex.py --run results/final/tb2_final --corpus tb2 --out ../archive/paper_v1/generated_tb2.tex
python scripts/export_ablation_tex.py --run results/final/tb2_final --out ../archive/paper_v1/generated_ablation.tex
cd ../archive/paper_v1 && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

The annotation cards can be regenerated from the frozen sample without re-running any
experiment:

```powershell
python scripts/make_annotation_cards.py --corpus tb2 --n-traj 40 --per-traj 4 --w 10
python scripts/make_dense_cards.py     --corpus tb2 --n-traj 54 --per-traj 10 --w 10
python scripts/make_extra_dense_cards.py --corpus tb2 --stride 2
```

## 6. Three experiments worth running next (in priority order)

1. **Intervention.** Stop a run at an alarm and restart it with the current diff as an overlay.
   Only that measures whether an alarm at a given false-stop rate improves task completion,
   rather than merely removing steps. This is the experiment the current paper cannot do.
2. **Human-check the labels.** 30–50 cards, two human readers, report agreement against the
   stored labels. This converts the biggest limitation into a result.
3. **Long-horizon trajectories.** Annotate SWE-agent or SWE-bench runs (the loader already
   works on `nebius/SWE-agent-trajectories`) so that a "window" becomes a real work episode
   rather than a fixed ten steps.

## 7. On the late annotation reports

All 58 readers wrote their files between 23:06 and 23:09, and the gold standard was built at
23:38 from whatever was on disk at that moment. Several readers reported back afterwards; every
such report was checked against `adjudicated.csv` and **none of them invalidated a published
number**. The recurring exception is harmless by design: cards that one reader labelled
`STAGNANT` and another `PRODUCTIVE` (for example `build-pov-ray__6eHBkqP_34`, reported as
`DONE_REDUNDANT` by one reader) had already been converted to `UNCERTAIN` by the tie rule.

Their aggregate contribution was to §4 rather than to the results: three artifact defects (card
bytes, assignment coordinates, the `detail` field) and one unusable field (the `boundary`
flag). **If you rerun the annotation, make these four changes**, in this order of value:

1. Hand readers explicit `card_id` lists instead of rank ranges — removes the whole class of
   coordinate ambiguity for one line of code.
2. Strip control bytes from the cards before distributing them (`scripts/clean_cards.py` does
   this now; `scripts/audit_cards.py` checks it).
3. Make `detail` mandatory for every non-`PRODUCTIVE` label, and give `BLOCKED_EXTERNAL`
   mechanism-specific members (`network_blocked`, `missing_dependency`, `waiting_on_own_job`) —
   this would also collapse most of the blocked-external disagreement in §4 item 2.
4. Adopt the single strict definition of `boundary` from §4 item 10.

The sharpest locality evidence in the whole label set comes from one trajectory, and it is
worth knowing because it is what a good monitor *should* be able to find.
`compile-compcert__pvBcxmV` is a single run with a narrow external incident in the middle: all ten
annotated windows before it (t = 9-24) are `PRODUCTIVE`, the five windows of the blocked stretch
(t = 27-33, the opam Coq build being killed by a timeout) are `BLOCKED_EXTERNAL` or held out, and
all ten windows from t = 37 to t = 57 are `PRODUCTIVE` again, ending in two `DONE_REDUNDANT` windows
after the build succeeds. Two readers covered this trajectory and neither contradicted the other:
one read the ten windows ending at t = 25 and correctly reported that the killed build was outside
every window it had been given, the other read the blocked stretch itself and labelled five
windows `BLOCKED_EXTERNAL`. The disagreement is confined to a single window (t = 28, where one
reader saw the build still running and the other saw it dead). That is what a locally detectable
stagnation episode looks like in this corpus, and it is the case an alarm is supposed to catch.

The most informative single trajectory in the set is `feal-linear-cryptanalysis__923TJt4`,
because it is **multi-episode** and the labels follow the episodes exactly rather than applying a
verdict to the whole run:

| Window range | Gold |
|---|---|
| t = 9-49 | `PRODUCTIVE` (17 windows: reads, `attack.c`/`smart_attack.c` writes, gcc runs) |
| t = 53-105 | `STAGNANT`/`repeat_verify` (13 windows polling a still-running `smart_attack` binary) |
| t = 109-115 | **`PRODUCTIVE` again** (the agent discovers `ps` is missing and re-launches under `tee`) |
| t = 119-125 | `STAGNANT` again |

One reader produced a 30-window file for this run that agrees with the gold on **27 of 30
windows**, independently identifying the re-launch pivot at steps 105-107 and calling the terminal
windows stagnant. The three that differ are all windows where adjudication held the label out as
`UNCERTAIN` (t = 30, 52, 56) and the reader committed to a verdict anyway --- and on each it chose
the label the gold later favoured, so its committed reading covered the run's episode structure
with **no gaps**, which the gold does not. A different reader, seeing a single window from the dead
stretch, labelled it `UNCERTAIN` on the reasoning that neighbouring windows had been called
`repeat_verify` --- defensible, but it could not see that the run revives a few steps later. **This is the clearest evidence in the study that the
labels capture genuine within-run episodes**: the same run stops, resumes, and stops again, and
the boundary windows of each episode were labelled accordingly. It also explains the earlier
productive-vs-stagnant disagreement in this trajectory as a sampling artefact --- a reader given one
window from the middle of a dead stretch cannot see that the run later revives.

A second trajectory shows the same shape even more sharply. `extract-elf__rUUxEg5` has 31
annotated windows with **no ambiguous label at all**: ten `PRODUCTIVE` windows (t = 9-23), then
`DONE_REDUNDANT` for windows ending at t = 25, 27, 29, ..., 59 with no window in between. The
task is solved at some point before t = 25 and every later window is redundant re-verification of
a finished result. Two properties make this useful. First, the boundary between the two classes is
a single clean step rather than a gradual drift, so a monitor that detects "the useful work has
ended" has something unambiguous to detect. Second, this trajectory accounts for 21 of the 59
`DONE_REDUNDANT` windows in the gold --- more than a third of the class from one run --- which is
the concentration behind item 3's note that post-completion labels rest on few runs.

**How concentrated is each class in one run?** This is worth knowing before quoting any
per-class number, and the answers differ sharply:

| Class | Windows | Largest single run | Share |
|---|---|---|---|
| `PRODUCTIVE` | 780 | 32 | 4% |
| `STAGNANT` | 260 | 33 | 13% |
| `DONE_REDUNDANT` | 59 | 21 | **36%** |
| `BLOCKED_EXTERNAL` | 36 | 26 | **72%** |
| `REGRESSION` | **4** | 2 | **50%** |

The two classes the paper says least about are the two most concentrated, and `REGRESSION` has
four windows in total, two of them from one run. Treat `REGRESSION` as a reported category rather
than a measured one: with four examples no classifier can be assessed on it, and its role in the
study is to keep those windows out of the positive class, nothing more.

**The concentration is a sampling artifact, and the cause is recorded in the artifacts.**
`data/annotations/tb2/refine_batches.json` specifies the assignment as 32 **contiguous** blocks of
30 ranks (batch 1 = ranks 1-30, batch 2 = 31-60, ..., batch 13 = 361-390), which is what its
stored prompt describes. What was actually dispatched was a **stride-18** selection over the same
sorted list (ranks 1, 19, 37, ...), so the manifest does not match the files and should not be
trusted as a record of who read what --- the reader files are the authority, and their contents are
what the gold was built from. This also explains a discrepancy the reports kept noticing: they were
told "ranks 361-390" and correctly found their cards were not contiguous.

Either scheme fails to spread a trajectory across readers, because a name-sorted list keeps a
trajectory's cards adjacent to each other:
three of the 31 refinement batches landed entirely inside one run --- `build-cython-ext__JrNsKeV`
(which is why one batch returned 30 `BLOCKED_EXTERNAL` labels and nothing else),
`feal-linear-cryptanalysis__923TJt4`, and `fix-code-vulnerability__7wXM79N` (the last being why one
batch returned 30 `PRODUCTIVE` labels). A strided assignment is fine for coverage but bad for
class balance, and a future run should stratify the assignment by *trajectory* so that no reader
sees a single run and every batch contains a mix.

One further protocol lesson, visible in the reports: readers were told to apply the codebook in
isolation, but at least one calibrated its conventions against the previous rounds' label files
instead. **That is a plausible source of correlated error**, because a reader that infers a
convention from earlier labels inherits their mistakes rather than correcting them. In that case
the inferred rule was wrong — the reader took
`tb2_feal-linear-cryptanalysis__jbbLGgC_36` (gold `STAGNANT`) and
`tb2_fix-ocaml-gc__wouZCwt_37` (gold `UNCERTAIN`, i.e. a *non*-decision) as precedents and
concluded that "waiting on in-flight external work" should be `BLOCKED_EXTERNAL` while "pure
no-tool loops" should be `STAGNANT`; the gold set in fact contains both readings, and the second
"precedent" was a card its own reader had declined to decide. Its `zjg6gBb` verdict happened to
match the gold, but the reasoning was reverse-engineered from a tie.

**The leakage leaves no trace in the artifacts, and the one trajectory where it would show does
not show it.** A scan of all 61 reader files for references to sibling label files,
`adjudicated.csv`, `agreement.json` or `gold_regions.json` finds **zero** — readers kept their
files clean, so any calibration happened in their working process, which is also why it cannot be
sized. But the trajectory every reader covered is the natural test:
`feal-linear-cryptanalysis__jbbLGgC`, 33 windows, **28 of them read independently, all 28 in
agreement — 33/33 `STAGNANT`, zero held out, 32 sharing the same subtype** — and the agreeing
readers came from different batches under different instructions, several reasoning explicitly
from outside evidence (one citing a `gcc` multiple-definition error in an earlier window as proof
that `/app` was not empty, which is §4.2 applied correctly). Convergent independent agreement on
33 windows is far more consistent with a correctly specified rule than with copied conventions.

If you rerun this, keep readers blind to each other's files (the round-1 and round-2
instructions said so explicitly; the dense-round instructions did not) and adjudicate
afterwards, rather than letting readers converge on a convention mid-study.
