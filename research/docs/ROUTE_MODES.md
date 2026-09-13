# SEARCH or VERIFY — an early, causal detector of *how* a run is failing

`scripts/analyse_route_modes.py` → `results/rebuild/route_modes.json`.
Everything below is read back out of that artifact; no number is retyped by hand.

---

## 0. Bottom line

A coding agent fails in one of two ways. **WRONG-FIX**: it edited a file the gold patch
touches but its change did not resolve the issue. **LOST**: it never edited a gold file at
all. On this corpus **64.3% of failures are wrong-fix** (67.0% among failures that edited
anything). A runtime that can tell the two apart can spend its one unit of help in the right
place — **SEARCH** for a lost run, **VERIFY** for a wrong-fix run.

What was built and what it says:

| question | answer |
|---|---|
| Is the failure mode predictable from the first 10% of a run, with no lookahead? | **Yes for failure** (AUC 0.693) and **yes for mode** (AUC 0.676) |
| Does it beat the free `position` baseline? | **Yes at every fraction**, by +0.026…+0.065 (failure) and +0.270…+0.339 (mode); bootstrap CI over tasks excludes 0 in every cell |
| Does it beat the published detectors (`agentstop_shape`, `ngram_loop`, `exact_burst`, `tfnorm_novel`)? | **Yes at every fraction and for every published family**, and it is the only family above chance on the mode task |
| Does it clear the top of AgentStop's published 0.6–0.7 range? | **Yes from f = 0.20** on the failure task (0.721–0.731); at f = 0.10 it is 0.693, inside the range, not above it |
| Is there a rule with a *controlled* false-alarm rate? | **Yes**: a sequential union-bound rule over the four checkpoints; measured false alarms on held-out LOST runs 0.046 at α = 0.05 (target 0.05), 0.123 at α = 0.20 |
| Does the routing decision beat always-SEARCH, always-VERIFY and random? | **Yes at every fraction and every partial-credit weight** (λ = 0, 0.25, 0.5); Δ = +0.021…+0.090, CIs exclude 0 |
| What is *not* established | the detection rate at a tight false-alarm budget is low (16.0% at α = 0.05); `position` is not available online, so the honest online comparison is length-matched, where the AUC holds (0.63–0.74) but the sample is small; the e-value combination rule is valid but never fires at α ≤ 0.05 |

**One-line verdict.** The detector beats every baseline on identical rows and folds, beats
the published heuristic families by a wide margin, and is the first thing in this study to
put a *number* on the wrong-fix/lost split that is not circular — but its honest value is a
ranking, not a tight-budget alarm: at α = 0.05 it catches 16% of wrong-fix runs.

---

## 1. The question

The runtime decision is *where to spend budget*, and the two failure modes call for opposite
interventions. The measurable form of that question is: **given only the first fraction f of
a run's steps, is the eventual failure a wrong-fix or a lost run?**

That is a different target from "will this run fail" (which the frozen study already
reported) and from "is this step wasted" (AUC 0.539, essentially unpredictable) — and it is
the one that maps onto an action.

---

## 2. Data and coverage (honest)

| quantity | value |
|---|---|
| runs in the corpus | 26,679 |
| instances in the corpus | 1,213 |
| instances with a gold patch | 927 (76.4%) |
| runs whose instance has a gold patch — **usable** | **20,341 (76.2%)** |
| edit steps | 173,417 |
| edit steps with no file name recorded | 7,109 (**4.10%**) |

Coverage is the first honest limit: **23.8% of runs cannot be labelled** at all, because the
dataset's patch field does not cover their instance. They are excluded, not imputed. The
4.10% of edit steps whose file is unrecorded can only make `ever_touched_gold` too *low*: a
run whose only gold-touching edit is invisible is mislabelled LOST. That biases the lost
class upward and cannot be repaired from this corpus.

---

## 3. Labels and base rates

Built in `build_labels`, from `results/rebuild/gold_patches.parquet` only — the dataset's own
patch field, which does not depend on any agent run.

| label | n | rate |
|---|---|---|
| `y_fail = 1 − reward` | 20,341 | **0.8373** |
| `ever_touched_gold` among failed runs | 17,031 | **0.6428** |
| `ever_touched_gold` among failed runs *with ≥1 edit* | 16,327 | **0.6705** |
| `ever_touched_gold` among successful runs | 3,310 | 0.9813 |
| mean `on_target_gold` (failed / successful) | — | 0.4069 / 0.4771 |
| failed runs that never edited anything at all (LOST by definition) | 704 | — |

Two independent checks that the labels are the same objects the frozen study measured:

* `ever_touched_gold` = 0.6705 (failed, edited) against the frozen **0.671**, and 0.9813
  (successful) against the frozen **0.982**;
* `on_target_gold` 0.4069 failed vs 0.4771 successful, against the frozen 0.407 / 0.477.

The headline split is therefore reproducible from the frozen artifacts by a second
implementation — this script re-derives it from the steps table rather than reading
`wrongness.json`.

**The noise floor.** Runs per instance: mean **21.9**, median 14, p90 50.4, max 98. Only
**228 instances (24.6%)** contain both a success and a failure, so a within-instance claim
rests on those; temperature-0 inference flips ~9% of per-instance outcomes, which is the
floor on any within-instance contrast here. Within those 228 instances, the prefix failure
detector's per-instance AUC is **0.584** (66.2% of instances above chance) — real, and
materially below the pooled 0.721, which is the usual direction of that correction.

---

## 4. Protocol

**Prefix, not window.** For run *r* with `n_steps = n` and fraction *f*,
`L = max(1, round(f · n))`; the feature vector reads steps `0 … L-1` only. `n_steps` is used
to *place the cutoff* — the protocol is literally "the first fraction f of the run" — and
appears in **no feature**.

**No-lookahead, proved mechanically.** `python scripts/analyse_route_modes.py --selftest`
overwrites every step at and after each cutoff with garbage (obs length, signature, edit
flag, file name, test counts, verb, family, status string) and re-derives the features; all
**112 feature columns** at f = 0.10 and f = 0.40 come back identical. The first run of that
test *failed* — it caught a real leak in `obs_half_ratio`, whose second half originally ran
to the end of the run instead of the end of the prefix. That is why the check exists and why
the current version passes.

**Folds.** Whole tasks are held out (`agentstall.evaluate.task_disjoint_folds`), so no task
appears in both train and test. Three fold seeds; every method is scored on identical rows
and identical folds. All hyperparameters are fixed before scoring (`LogisticRegression(C=1)`,
`HistGradientBoostingClassifier(max_iter=200, lr=0.05, depth=3)`); nothing was tuned on the
evaluation folds, and every fraction is reported rather than the best one.

**Uncertainty.** 500 bootstrap resamples of **whole tasks** (the unit the folds hold out).
The point AUC is the mean over fold seeds (sd over seeds ≤ 0.006 for every fitted method);
the CI is computed on the fold-seed-averaged score. Pairwise deltas are computed inside the
same bootstrap sample, so they are paired.

---

## 5. Methods on the table

| method | what it is |
|---|---|
| `position` | the free baseline: the prefix's step count = `round(f·n)`. See §8 — at a fixed fraction this **is** the run's own length, so it is simultaneously the study's strong baseline and a hindsight quantity |
| `agentstop_shape` | AgentStop's feature shape — per-step output length (`text_chars`) and adjacent-step overlap (identical `sig`), fitted task-disjointly |
| `ngram_loop` | the frozen study's period-2/3/4 cycle guard, reimplemented (`analyse_detector_families.py` is *not* modified); prefix mean of the flag |
| `exact_burst` | the frozen study's "3 identical signatures in a trailing window of 5"; prefix mean |
| `tfnorm_novel` | the frozen study's TF-Norm/cosine redundancy surrogate, faithful to its tokenisation of `targets_str` (74% of steps carry one); prefix mean |
| `edit_rate_free` | one free feature on its own: edits per step so far |
| `own_rates` (**primary**) | 34 prefix features that do **not** grow with the prefix: edit rate, no-op-edit share, distinct files per edit, repeat-file-edit share, test/verify/run/read/search rates, signature and command-family diversity and entropy, repeat-signature share, longest identical-signature streak, observation length mean/last/slope/half-ratio, text-to-observation ratio, error rate, pass/fail/error counts seen so far |
| `own_all` | the task's full requested list = `own_rates` + 15 raw counts (edit count, distinct files, test invocations, passes, failures, …). These counts grow with the prefix, so this family carries length information; it is reported and flagged, not used as the primary |
| `own_gbm_rates`, `own_gbm_all` | the same two feature sets under gradient boosting, fixed hyperparameters |
| `own_rates_plus_position` | `own_rates` plus `_prefix_len` — the incremental-value test over the free baseline |

---

## 6. Results — `y_fail` (does the run fail?), n = 20,341, base rate 0.8373

AUC summary (mean over 3 fold seeds; `*` marks a cell where `own_rates` beats that baseline
with a paired bootstrap CI over tasks that excludes 0):

| method | f = 0.10 | f = 0.20 | f = 0.40 | f = 0.60 |
|---|---|---|---|---|
| `position` (free) | 0.667 * | 0.664 * | 0.666 * | 0.666 * |
| `agentstop_shape` | 0.554 * | 0.565 * | 0.594 * | 0.607 * |
| `tfnorm_novel` | 0.543 * | 0.594 * | 0.627 * | 0.642 * |
| `ngram_loop` | 0.506 * | 0.515 * | 0.544 * | 0.576 * |
| `exact_burst` | 0.507 * | 0.520 * | 0.552 * | 0.578 * |
| `edit_rate_free` | 0.465 * | 0.451 * | 0.452 * | 0.455 * |
| **`own_rates`** | **0.693** | **0.721** | **0.721** | **0.731** |
| `own_all` | 0.699 | 0.725 | 0.729 | 0.743 |
| `own_gbm_rates` | 0.699 | 0.725 | 0.742 | 0.763 |
| `own_gbm_all` | 0.702 | 0.727 | 0.744 | 0.770 |
| `own_rates_plus_position` | 0.694 | 0.720 | 0.721 | 0.732 |

Full detail at f = 0.40 (method | AUC | 95% CI over tasks | recall at a 5% / 10% alert budget):

| method | AUC | 95% CI | r@5% | r@10% |
|---|---|---|---|---|
| `position` | 0.666 | [0.645, 0.687] | 0.057 | 0.114 |
| `agentstop_shape` | 0.594 | [0.566, 0.624] | 0.057 | 0.111 |
| `tfnorm_novel` | 0.627 | [0.602, 0.648] | 0.056 | 0.112 |
| `exact_burst` | 0.552 | [0.545, 0.560] | 0.057 | 0.113 |
| `ngram_loop` | 0.544 | [0.539, 0.550] | 0.058 | 0.112 |
| `edit_rate_free` | 0.452 | [0.423, 0.483] | 0.054 | 0.105 |
| **`own_rates`** | **0.721** | **[0.694, 0.745]** | 0.058 | 0.116 |
| `own_all` | 0.729 | [0.704, 0.753] | 0.059 | 0.117 |
| `own_gbm_all` | 0.744 | [0.720, 0.771] | 0.059 | 0.118 |

Paired deltas of `own_rates` against each baseline (bootstrap over tasks):
`position` **+0.026** [+0.011, +0.042] at f = 0.10, **+0.057** [+0.036, +0.078] at f = 0.20,
**+0.054** [+0.035, +0.076] at f = 0.40, **+0.065** [+0.045, +0.087] at f = 0.60;
`agentstop_shape` +0.140/+0.156/+0.126/+0.124; `tfnorm_novel` +0.151/+0.127/+0.094/+0.089.
All CIs exclude 0. Against its own boosted variants the primary logistic **loses** at
f ≥ 0.40 (`own_gbm_all` is +0.024 above it at f = 0.40 and +0.039 at f = 0.60, CI excluding
0) — reported because it is true; nothing in the design picks one.

**Published bar.** AgentStop reports 0.6–0.7 on its own task, and its feature shape reaches
0.554–0.607 here. `own_rates` is above the whole published range from f = 0.20 (0.721–0.731)
and inside it at f = 0.10 (0.693). This is a like-for-like *context*, not a like-for-like
comparison: the deployed AgentStop reads model logprobs, which this corpus does not carry.

---

## 7. Results — `y_mode` (wrong-fix vs lost, failed runs only), n = 17,031, base rate 0.6428

| method | f = 0.10 | f = 0.20 | f = 0.40 | f = 0.60 |
|---|---|---|---|---|
| `position` | 0.407 * | 0.411 * | 0.413 * | 0.413 * |
| `agentstop_shape` | 0.493 * | 0.490 * | 0.475 * | 0.470 * |
| `tfnorm_novel` | 0.449 * | 0.447 * | 0.467 * | 0.489 * |
| `ngram_loop` | 0.485 * | 0.474 * | 0.459 * | 0.453 * |
| `exact_burst` | 0.484 * | 0.473 * | 0.467 * | 0.466 * |
| `edit_rate_free` | 0.418 * | 0.435 * | 0.486 * | 0.539 * |
| **`own_rates`** | **0.676** | **0.701** | **0.724** | **0.751** |
| `own_all` | 0.678 | 0.715 | 0.756 | 0.777 |
| `own_gbm_rates` | 0.682 | 0.724 | 0.781 | 0.806 |
| `own_gbm_all` | 0.685 | 0.729 | 0.785 | 0.813 |
| `own_rates_plus_position` | 0.677 | 0.702 | 0.725 | 0.751 |

Detail at f = 0.40:

| method | AUC | 95% CI | r@5% | r@10% |
|---|---|---|---|---|
| `position` | 0.413 | [0.392, 0.432] | 0.016 | 0.052 |
| `agentstop_shape` | 0.475 | [0.436, 0.482] | 0.043 | 0.088 |
| `tfnorm_novel` | 0.467 | [0.450, 0.485] | 0.034 | 0.087 |
| `edit_rate_free` | 0.486 | [0.463, 0.507] | 0.029 | 0.071 |
| **`own_rates`** | **0.724** | **[0.707, 0.744]** | 0.065 | 0.131 |
| `own_gbm_all` | 0.785 | [0.768, 0.806] | 0.070 | 0.139 |

`own_rates` minus baseline, paired: `position` **+0.270 / +0.289 / +0.311 / +0.339** at
f = 0.10/0.20/0.40/0.60 (CI lower bounds 0.235 / 0.258 / 0.281 / 0.308); `agentstop_shape`
+0.184 / +0.211 / +0.249 / +0.282; `tfnorm_novel` +0.227 / +0.254 / +0.257 / +0.263.

**Read this one carefully.** `position` is *below* chance (0.41): among failed runs, the
longer ones (measured by the run's total length) are more often LOST. Every published family
sits at or below chance too. So beating them is not a high bar — on this task the baselines
carry no usable signal, and the honest statement is "the family is the only thing above
chance", not "it beat a hard field". The number that matters is that 0.676 is reachable from
**2.8 steps of prefix on average**.

**Sensitivity.** Restricting to failed runs that edited at least once (n = 16,327, base rate
0.6705) — dropping the trivially-lost never-edited runs — gives `own_rates`
0.684 / 0.697 / 0.713 / 0.736 and `own_gbm_all` 0.694 / 0.723 / 0.771 / 0.795. The result
survives the removal of the easy class.

---

## 8. Is it just run length? (the length-matched control)

`position` at a fixed fraction is `round(f·n)` — a strictly increasing function of the run's
own length (verified in the artifact: `integrity_checks.position_equals_run_length` shows the
prefix-length AUC and the `n_steps` AUC agreeing to ≤ 0.006 at every cell). It is a strong
baseline, and it is **not available at decision time**: at step *t* a runtime does not know
how long the run will turn out to be. So the comparison that matters is inside a fixed prefix
length, where `position` is constant and carries nothing.

| task | fraction | L | n | `own_rates` | `own_all` | `agentstop_shape` |
|---|---|---|---|---|---|---|
| y_fail | 0.10 | 5 | 880 | 0.733 | 0.739 | 0.358 |
| y_fail | 0.20 | 5 | 1,446 | 0.625 | 0.634 | 0.496 |
| y_fail | 0.20 | 10 | 458 | 0.758 | 0.774 | 0.402 |
| y_fail | 0.40 | 10 | 858 | 0.675 | 0.710 | 0.592 |
| y_fail | 0.60 | 5 | 1,963 | 0.695 | 0.707 | 0.581 |
| y_fail | 0.60 | 10 | 1,190 | 0.631 | 0.636 | 0.536 |
| y_mode | 0.10 | 5 | 842 | 0.648 | 0.653 | 0.496 |
| y_mode | 0.40 | 10 | 775 | 0.666 | 0.718 | 0.525 |
| y_mode | 0.60 | 5 | 1,413 | 0.739 | 0.747 | 0.439 |
| y_mode | 0.60 | 20 | 484 | 0.703 | 0.755 | 0.522 |

The signal is **not** run length: inside a single prefix-length band, with `position` inert by
construction, `own_rates` still sits at 0.63–0.76. The cells vary (0.625 on n = 1,446 at
L = 5 vs 0.758 on n = 458 at L = 10) because they are subsets, so the range is the honest
summary, not any single cell. In the same cells `agentstop_shape` is 0.36–0.65.

The complementary test agrees: **adding `position` to the feature set changes nothing**
(`own_rates_plus_position` is within 0.002 of `own_rates` at every fraction, CI covering 0).
The prefix features strictly dominate knowing how long the run has been going.

---

## 9. What carries the signal

From `feature_importance` (mean standardised logistic coefficient over task-disjoint folds,
alongside each feature's *univariate* AUC — which involves no fitting, so it cannot be a
selection artefact). Coefficients describe the fitted joint model; a coefficient whose sign
opposes its univariate AUC is suppression, not a discovery.

`y_fail`, f = 0.20 — looping and no-op edits:

| feature | standardised coef | standalone AUC |
|---|---|---|
| `sig_entropy` (signature diversity of the prefix) | −2.03 | 0.630 |
| `max_consec_repeat_norm` (longest identical-signature streak) | −1.98 | 0.349 |
| `noop_edit_frac` | +0.88 | 0.491 |
| `any_file_edited_twice` | −0.79 | 0.506 |
| `repeat_file_edit_frac` | +0.75 | 0.526 |
| `unique_cmdfam_frac` | −0.68 | 0.345 |

`y_mode`, f = 0.40 — repetition and evaporation of edits:

| feature | standardised coef | standalone AUC |
|---|---|---|
| `no_edit_yet` | −0.89 | 0.515 |
| `unique_cmdfam_frac` | +0.88 | **0.612** |
| `noop_edit_frac` | −0.84 | 0.409 |
| `sig_entropy` | +0.67 | 0.548 |
| `repeat_file_edit_frac` | −0.66 | 0.456 |
| `any_file_edited_twice` | +0.49 | 0.468 |

The single most informative quantity for the *mode* target is command-family diversity in
the prefix (0.612 on its own), with the no-op-edit share right behind (0.409, i.e. an
inverted signal). Both are in the requested feature families; neither is `n_steps`.

---

## 10. Calibration with formal false-alarm control

**Design.** Tasks are split three ways by whole tasks: 50% **train** (fit), 25%
**calibration** (estimate the null distribution of the score), 25% **test** (measure
everything). At each checkpoint f the p-value of a test run is `(1 + #{null_calib ≥ s}) /
(1 + n_null_calib)` against the *negative* runs of the calibration block — successful runs
for `y_fail`, LOST runs for `y_mode`. Repeated over 5 task splits (n_null ≈ 900 for `y_fail`,
≈ 1,560 for `y_mode`; n_test ≈ 4,900 / 4,289).

Two rules combine the four checkpoints, both valid under **arbitrary dependence** between
them (the prefixes are nested, so they are certainly dependent):

* **`seq_threshold`** — alarm at the first checkpoint where `p_f ≤ α/4`. The union bound gives
  sequence-level Type-I error ≤ α. This is the primary rule.
* **`e_value_mean`** — `e_f = κ·p_f^(κ−1)` is an e-value for any κ ∈ (0,1); the mean of
  e-values is an e-value under arbitrary dependence, so `mean_f e_f ≥ 1/α` has Type-I error
  ≤ α. Reported for completeness; it is much more conservative.

**Achieved rates on held-out tasks** (mean over 5 splits; max in brackets):

| task | α | false-alarm rate | detection rate |
|---|---|---|---|
| `y_mode` (alarm = "route to VERIFY"; null = LOST) | 0.05 | **0.0459** [0.0605] | 0.160 |
| | 0.10 | **0.0777** [0.0931] | 0.258 |
| | 0.20 | **0.1232** [0.1329] | 0.386 |
| | 0.50 | 0.2475 [0.2552] | 0.636 |
| `y_fail` (null = successful runs) | 0.05 | **0.0339** [0.0513] | 0.194 |
| | 0.10 | **0.0603** [0.0842] | 0.285 |
| | 0.20 | **0.1088** [0.1409] | 0.399 |
| | 0.50 | 0.2255 [0.2684] | 0.581 |

All 8 combinations are controlled at their stated α on the mean. The worst of the five task
splits exceeds its α at only **two** of the eight levels, both at α = 0.05 and by
1.03× (`y_fail`: 0.0513 measured) and 1.21× (`y_mode`: 0.0605 measured); every other
worst-split value is below its own α. That 1.21× is the exchangeability assumption (§11)
showing up as a number.

**Detection as a function of how much of the run has been watched** (means over splits,
`y_mode`): at α = 0.20 the rule has caught 15.4% of wrong-fix runs by f = 0.10, 25.0% by
f = 0.20, 32.5% by f = 0.40, 38.6% by f = 0.60, with false alarms at those same checkpoints of
4.95% / 7.54% / 9.97% / 12.32%. Detected runs fire at **26% of the run on average**, i.e. the
warning usually arrives early.

**The e-value rule.** Valid in theory, unusable here: at α ≤ 0.05 it never fires (detection
0.0); at α = 0.2 it fires with detection 0.012 (`y_mode`) and 0.075 (`y_fail`); at α = 0.5,
0.228 and 0.317. Its mean value on held-out nulls is 0.96 (`y_mode`) and 1.007 (`y_fail`) —
i.e. at worst marginally *above* the theoretical ≤ 1, which is the calibration-block/test-block
exchangeability assumption showing up as a small number rather than being asserted away.

**The null run.** The frozen study's withdrawn claim was "zero false alarms at every budget",
which was circular because label and detector were the same statistic. Here the two are
independent by construction, and the check is measured rather than asserted:

| check (f = 0.60) | value |
|---|---|
| never-failing runs flagged by a **raw 0.5 threshold** on the score | **0.984** |
| failing runs flagged by the same raw threshold | 0.995 |
| never-failing runs flagged by the **calibrated rule at α = 0.05** | **0.0339** |
| LOST runs routed to VERIFY by the raw 0.5 threshold | 0.568 |
| mean mode score, LOST runs / wrong-fix runs | 0.521 / 0.710 |

The raw-threshold row is the point: an uncalibrated logistic score flags **98.4%** of runs
that never fail, which is exactly why a probability threshold is not a false-alarm rate and
why the calibration stage is not decoration. The controlled number is 3.4% at α = 0.05.

---

## 11. Non-circularity, explicitly

1. **The label comes from the gold patch** (`gold_patches.parquet`, the dataset's patch
   field), never from the agent's own output, never from the detector's features.
2. **The detector reads steps `0 … L−1` only**, proved by `--selftest` (corrupt the future,
   features do not move).
3. **No label-derived quantity is a feature.** The two label columns (`ever_touched_gold`,
   `on_target_gold`) are computed over the whole run and are used *only* as targets.
4. **A null run does not trivially trigger**: 3.39% of never-failing runs are flagged by the
   controlled rule at α = 0.05 (§10).
5. **The free baseline is not smuggled in**: `position` is reported both as the baseline and
   as a leak diagnostic, and the primary family excludes it and every other length-carrying
   column; adding it back changes nothing.

**The assumption that keeps the control honest.** The formal guarantee is conditional on the
calibration block's null distribution being exchangeable with the test block's. Tasks differ
in difficulty, so this is an assumption, not a theorem — which is why the achieved rate is
*measured on held-out tasks over five different task splits* and the worst split is reported
alongside the mean, rather than the α being quoted as if it were achieved.

---

## 12. Decision curve: SEARCH or VERIFY

**Utility.** For a failing run with true mode *m* ∈ {WRONG-FIX, LOST}, routing *r* ∈
{VERIFY, SEARCH} yields credit **1.0** if `r = m` and **λ** otherwise — λ is the partial
credit for the wrong intervention (the wrong help is not worthless, it is the wrong bet). The
detector routes VERIFY when the prefix score exceeds 0.5. λ = 0 is the clean "correct routing
accuracy" reading.

**Conditional on the run failing** (n = 17,031 at f = 0.40), with a paired bootstrap over tasks:

| f | λ | detector | always SEARCH | always VERIFY | random | Δ vs best | 95% CI | beats all three |
|---|---|---|---|---|---|---|---|---|
| 0.10 | 0.25 | 0.764 | 0.518 | 0.732 | 0.656 | +0.032 | [+0.024, +0.039] | ✅ |
| 0.20 | 0.25 | 0.776 | 0.518 | 0.732 | 0.656 | +0.044 | [+0.035, +0.053] | ✅ |
| 0.40 | 0.25 | 0.786 | 0.518 | 0.732 | 0.656 | +0.054 | [+0.045, +0.064] | ✅ |
| 0.60 | 0.25 | 0.800 | 0.518 | 0.732 | 0.656 | +0.068 | [+0.057, +0.077] | ✅ |
| 0.10 | 0.00 | 0.685 | 0.357 | 0.643 | 0.541 | +0.042 | [+0.032, +0.052] | ✅ |
| 0.60 | 0.00 | 0.733 | 0.357 | 0.643 | 0.541 | +0.090 | [+0.076, +0.103] | ✅ |
| 0.10 | 0.50 | 0.842 | 0.679 | 0.821 | 0.770 | +0.021 | [+0.016, +0.026] | ✅ |
| 0.60 | 0.50 | 0.866 | 0.679 | 0.821 | 0.770 | +0.045 | [+0.038, +0.052] | ✅ |

The detector beats all three baselines at **every fraction and every λ**; the CI excludes 0
in all 12 cells. The best baseline is always `always_verify` — with 64.3% of failures being
wrong-fix, always-VERIFY is the right prior, and the detector's value is the ~9–13 points of
routing it adds on top (accuracy 0.685 → 0.733, verify rate 0.877 → 0.782).

**Gated over all runs** (intervene only when the failure detector fires, then route; utility
= share of failures addressed, λ = 0.25): detector 0.639 / 0.649 / 0.657 / **0.666** against
always-SEARCH 0.397, always-VERIFY 0.547, random 0.523 — beats all three at every fraction.
**Caveat:** the gate uses the raw 0.5 threshold, which fires on 99.3–100% of runs, so this arm
measures the value of *routing*, not of *gating*. The gating that is actually controlled is
the calibration rule in §10 (Type-I error ≤ α), and it intervenes far less often.

---

## 13. What failed, and what is negative

* **The e-value combination rule.** Formally valid, empirically useless at the levels anyone
  would deploy: detection 0.000 at α ≤ 0.05. The union-bound sequential threshold dominates
  it everywhere. Reported rather than dropped.
* **`position` is strong and cannot be beaten online by the margin it is beaten here.**
  `position` = the run's own length (§8) is a hindsight quantity; on the failure task it
  scores 0.664–0.667 and the prefix features add only **+0.026 at f = 0.10**. A deployment
  that genuinely has only 10% of a run's steps to look at cannot use it — but it also cannot
  claim the +0.057…+0.065 margins seen at larger f, because those are measured at a
  *hindsight-placed* cutoff. The length-matched control (§8) is the honest version of the
  claim: 0.63–0.76 inside a fixed prefix length, on samples of 450–2,000 runs.
* **Recall at a 5% budget is ~0.058 for every method**, the free baseline included. With an
  83.7% failure rate a 5% alert budget simply cannot hold many failures: precision at that
  budget is capped near 1.0 and recall near the budget itself. The operating point is
  uninformative; only the ranking is. The 10% budget is the same story (r ≈ 0.117).
* **The strongest baseline is a different method at different fractions** (`tfnorm_novel`
  early, `edit_rate_free` for the mode task late), so "the baseline" is a span, not a point.
* **The primary logistic is not the best model.** The gradient-boosted variants beat
  `own_rates` on both tasks from f = 0.20–0.40 onward (up to +0.062 on `y_mode` at f = 0.60).
  The primary is the interpretable one; the numbers for both are in the table because a
  single number chosen after the fact would be a tuned result.
* **On the mode task, beating the baselines is not evidence of a hard bar** — every published
  family is at or below chance there. The useful claim is the absolute number, 0.676–0.751.
* **The controlled detection rate is low.** 16.0% of wrong-fix runs at α = 0.05, 38.6% at
  α = 0.20. A detector that is right about the mode but fires on one run in six is a real
  tool and a modest one.
* **A raw probability threshold is a trap.** 98.4% of never-failing runs exceed 0.5 on the
  uncalibrated failure score. Any claim of the form "our monitor has few false alarms" that
  does not go through a calibration stage is measuring the class balance, not the detector.

---

## 14. Limitations

1. **The cutoff is placed with hindsight.** `L = round(f · n_steps)` needs the run's total
   length. The *features* are causal (proved), but the *comparison* — including the AUC at
   each f — conditions on knowing how long the run was. Two mitigations are reported and
   neither is a fix: the length-matched control (§8) and the exclusion of every
   length-carrying feature (§5, §8).
2. **`position` is a hindsight baseline** for the same reason; its 0.664–0.667 is the number
   a real online system could *not* have.
3. **Basename matching.** `ever_touched_gold` matches basenames against the gold set, so a
   run editing a same-named file in a different directory is counted as on-target. The frozen
   study's gold cross-check uses the same rule, so the numbers are comparable to it; the
   alternative (full paths) is not recoverable from `file_shown` for every step.
4. **4.10% of edit steps carry no file name**, which can only under-count `ever_touched_gold`
   and inflate the LOST class.
5. **`ever_touched_gold` is a coarse proxy for "wrong fix".** A run that touches a gold file
   once, incidentally, counts as wrong-fix. The mode target is therefore better read as
   "reached the right place" than as "diagnosed correctly".
6. **The mode label exists only for failures.** The decision is conditional on failing; gating
   it with the failure detector compounds two detectors' errors, and the gated arm in §12 is
   honest about not being a controlled gate.
7. **Only 228 of the 927 instances (24.6%) contain both a success and a failure**, so a
   within-instance contrast rests on 228 clusters; the mean 21.9 runs per instance is what
   makes the pooled comparison possible at all, and the ~9% outcome-flip floor applies to
   the within-instance number.
8. **`agentstop_shape` is a feature-shape reproduction**, not the deployed AgentStop: no
   logprobs, no token-level supervision. Its published 0.6–0.7 is quoted as context only.
9. **`tfnorm_novel` is faithful to the frozen implementation**, which tokenises the *target
   paths* of a command rather than the observation body — the corpus does not carry
   observation text. A "true" TF-norm over observations might behave differently; the
   frozen study's own low AUC for it (0.527/0.635) suggests not much.
10. **Per-task folds mean per-task models.** Nothing here transfers to an unseen task
    family without retraining; the fold protocol guarantees the *measurement* is
    task-general, not that the fitted model is.
11. **The bootstrap resamples tasks**, which is the right unit for the fold structure but a
    narrower uncertainty statement than resampling runs would be; runs within a task are
    strongly dependent and resampling them would understate the spread.

---

## 15. Subgroups and stability

* Fold-seed sd of every fitted method: **≤ 0.006** on both tasks (§6, §7 tables), i.e. the
  results are properties of the data, not of the split.
* The primary's margin over `position` is positive in **every** fraction and in both tasks,
  with paired CIs excluding 0 in all eight cells.
* Length-matched cells (§8) are positive in every cell tested, on 450–2,000 runs each.
* The mode result survives dropping the never-edited (trivially LOST) runs (§7 sensitivity).
* Within-instance (228 instances): 0.584 mean per-instance AUC for the failure detector at
  f = 0.40, 66.2% of instances above chance.

---

## 16. Reproduce

```bash
# causal integrity (must pass; it catches real leaks)
python scripts/analyse_route_modes.py --selftest

# full study: features (cached under _cache/route_modes), evaluation, calibration,
# decision curve, verdict -- ~27 min on this machine, resumable
python scripts/analyse_route_modes.py --stage all --seeds 3 --folds 5 --n-boot 500 --calib-seeds 5

# cheap follow-ups on the caches
python scripts/analyse_route_modes.py --stage importance   # feature_importance + leak diagnostic
python scripts/analyse_route_modes.py --stage assemble     # re-derive verdict from stored results
python scripts/analyse_route_modes.py --limit 1500         # smoke run (writes to _cache, not results)
```

Caches live in `_cache/route_modes/` (`prefix_features*.parquet`, `labels*.parquet`,
`calib*.json`, `progress_eval*.json`); `--force` recomputes. No existing script, source file
or frozen artifact was modified; `scripts/analyse_detector_families.py` was read and mirrored,
not edited. No LLM calls and no network are used.
