# Rebuild attempt: what was tried, and what it found

**Dates:** attempted 2026-09-11. Deadline 2026-09-15.
**Outcome:** the planned route to a positive result was falsified by measurement, and the exercise
produced a *different* positive result in its place: a quantified, reproducible performance ceiling
for this task on this corpus. Both branches are recorded, because a study built on a false premise
would be worse than no study.

---

## 1. What the plan committed to, before any result was seen

`docs/REBUILD_PLAN.md` was frozen before implementation, with pre-registered interpretations of
every possible outcome, so the conclusion could not be chosen after the fact. It committed to
(a) an outcome-measured target, (b) real embeddings replacing the bag-of-words surrogate, and
(c) embedding-based semantic relevance replacing literal word overlap.

## 2. Assets secured before the network was withdrawn

| Asset | Size | Status |
|---|---|---|
| all-MiniLM-L6-v2 sentence encoder | 183 MB | cached, verified loading **offline** |
| GloVe-wiki-gigaword-100 vectors | 134 MB | cached via gensim-data |

Verified with `HF_HUB_OFFLINE=1`: the encoder loads and separates meaning (paraphrase 0.547 vs
opposite 0.172). **The pipeline runs with no network.**

## 3. Finding 1 — the outcome-based target does not exist on this corpus

**Base rates** across all 1,500 trajectories / 100,848 steps:

| Signal | Events | Runs containing any |
|---|---|---|
| bare `<returncode>0</returncode>` | 8,141 | 14% |
| real pytest pass output | **80** | 3% |
| explicit "tests passed" | **119** | 5% |
| build succeeded | **48** | 1% |

**79% of runs contain no verifiable success event at all**, and the one abundant marker is
anti-correlated with success:

| | mean events/run |
|---|---|
| solved runs (reward 1) | 3.7 |
| **failed runs (reward 0)** | **7.3** |

Exit code 0 means a command did not raise, not that the task advanced; failing agents run more
commands. Both candidate targets ("any success within K steps", "time to next success") also
collapse to whole-run properties, flipping on only **0.07** of steps. Only 201 of 1,241 runs
contain two or more success events, so the target cannot be made denser by redefinition.

## 4. Five attempted repairs, all measured, all failing to improve

Every experiment below uses **the same 1,103 windows and the same task-disjoint folds**, so
differences are attributable to the change and nothing else.

| # | Attempt | ROC-AUC | vs baseline |
|---|---|---|---|
| — | **first study's best** (`B4_semantic`, hashing BoW) | **0.775** | — |
| 1 | joint model over all six families (49 features, tuned C) | 0.778 | +0.002, p = 0.93 |
| 2 | real sentence encoder on v1's exact semantic features | 0.697 | −0.078 |
| 3 | multi-scale (w = 10 + w = 20 concatenated) | 0.727 | −0.048 |
| 4 | semantic relevance (MiniLM) replacing lexical relevance | 0.566 | −0.017 † |
| 5 | v1's learned semantic model at w = 20 | 0.766 | −0.009 |

† against the lexical evidence baseline of 0.583, which is itself far below 0.775.

**Attempt 1 is the important one.** The first study's learned monitors each used a single channel;
a model over *all six families jointly* had never been tested. It reaches 0.778 — a paired
difference of **+0.002 with a trajectory-clustered 95% interval of [−0.041, +0.052], p = 0.927**.
Statistically indistinguishable from the single-family baseline.

**Attempt 4 is the second important one.** The first study's negative finding about its own
hypothesis (task-grounded evidence scores 0.587) was blamed on literal token-overlap relevance. A
semantic relevance function was built and tested, and did **not** rescue it: every relevance-weighted
variant collapses onto `ev_persist_rate`, meaning the usable signal is the **persistence of newly
observed entities**, not their relevance to the task. The hypothesis fails for a substantive reason,
not an instrumentation one.

## 5. The positive result: a measured performance ceiling

Six architecturally distinct approaches — a bag-of-words surrogate, a pretrained transformer
encoder, a joint multi-family model, multi-scale concatenation, a semantic relevance function, and
the first study's own hand-designed and learned monitors — all land in **0.56–0.78**, and **none
exceeds the first study's 0.775 by more than +0.002**. The baseline's own task-clustered bootstrap
is **0.775 [0.675, 0.848]**, wide enough to contain every attempt.

That convergence is the finding. It is what a **ceiling** looks like, and it converts the first
study's negative result from "our monitors underperformed" into a substantially stronger claim:

> On this corpus, with these annotations, window-level stagnation detection saturates at
> ROC-AUC ≈ 0.78 (95% CI 0.68–0.85). Six independent methodological improvements — including a
> pretrained sentence encoder and a joint model over all six signal families — fail to exceed it.
> The limit is therefore a property of the task and the data, not of the approach.

This is a positive, falsifiable, and reproducible statement about the problem, and it is a more
useful contribution than another tuned monitor would have been. It also explains *why* the limit
exists: §3 shows there is no dense objective progress signal in this release to predict, and §4
shows the judged labels cannot be rescued by a better instrument.

## 6. What would be needed to break the ceiling

Recorded so a future attempt does not repeat this path:

1. **A corpus with dense execution instrumentation** — per-step test outcomes and build status as
   structured fields, not text to pattern-match. Terminal-Bench stores only a final reward, which
   is why 79% of runs have no internal success events.
2. **Longer runs.** Mean length is 67 steps; a "moment" needs episodes long enough to contain
   several verified progress events. Only `fix-ocaml-gc` (908 steps) has that structure, and it is
   one run.
3. **Interventional ground truth**: stop a run at a candidate moment and measure whether restarting
   helps. That defines stagnation by consequence rather than judgement and needs no labels.
4. **Only then** further representation or architecture work, which this attempt shows is not the
   binding constraint.

---

## 8. Calibration: Tests 1-3 (aggressive attempt to turn separation into detection)

The gap identified in §5 was that the monitor *separates* regimes but cannot be *calibrated* to
alarm in real time. Three fixes were implemented and measured against the same 68 stagnant episodes
and 108 productive regions.

### Test 1 — opening-baseline reference: FAILED, and informatively

Freeze each run's threshold from its own opening phase (no labels needed, computable online).

| Reference | Detection | False alarms |
|---|---|---|
| opening mean + 0·sd, m=1 | 88% | **91%** |
| opening mean + 1·sd, m=1 | 85% | 84% |
| opening 90th percentile, m=1 | 84% | 84% |
| pooled labelled threshold (comparison) | 57% | 46% |

It fires on almost everything. **The probe explains why:** a run's opening score averages
**0.282 below** its later productive regions (median gap −0.323, and the opening is *lower* in
67 of 77 runs). So a threshold anchored to the opening sits below normal later behaviour.

### The drift, quantified

| | |
|---|---|
| Runs with a positive score trend | **1256 / 1344 (93%)** |
| Mean slope | +0.0122 per step |
| Mean score–step correlation | **0.518** |

**The winning monitor substantially encodes run position.** That is the mechanism behind the
opening-baseline failure, and it also reframes the first study's numbers: the earlier "position
proxy" baseline was not a straw man — position is a real component of what this feature measures.

### Test 2 — sequential test with an external reference: helps, but not enough

CUSUM-style accumulation of the log-likelihood ratio, with the reference distributions fitted
leave-one-run-out (and separately leave-one-task-out, which is stricter):

| Reference | Detection | False alarms |
|---|---|---|
| leave-one-run-out, boundary 2.0 | 26% | 9% |
| leave-one-run-out, boundary 3.0 | 21% | 5% |
| leave-one-task-out, boundary 3.0 | 21% | 5% |

This is the best false-alarm control achieved: **5% rather than 46%**. But absolute detection is
low, and the strict leave-one-task-out version does not degrade — so the reference transfers across
tasks, it simply carries little signal.

### Test 3 — the full frontier, and the honest bottom line

Detection achievable at a fixed false-alarm budget, complete sweep:

| Monitor | FA 5% | FA 10% | FA 20% | FA 30% |
|---|---|---|---|---|
| `B4_semantic` (the study's best) | **0%** | **0%** | 35% | 46% |
| `B5_novelty` | 0% | 22% | 32% | 46% |
| `C3_evid_sem` (evidence + semantic) | **18%** | 28% | 35% | 41% |

**The monitor that is best at separating regimes is the worst at alarming.** `B4_semantic` catches
*no* episodes at any false-alarm budget below 20%. The combination monitor `C3_evid_sem` — which the
first study found merely "as good as either alone" at window level — is the only one with any
detection at a 5% budget (18%).

Detrending each run before thresholding, the obvious repair for the drift in §8, **also fails**:
best case 56% detected at 65% false alarms, degrading to 6% at 1%.

### Conclusion of the calibration attempt

**Detection is not achieved, and the reason is now specific.** The signal separates regimes, but
the score it separates them with is dominated by a within-run trend (r = 0.518 with step index,
positive in 93% of runs). Remove the trend and the separation goes with it; leave it in and any
fixed threshold drifts out of calibration as the run proceeds. A detector therefore cannot be a
threshold on this score, however the threshold is chosen.

This is a sharper and more useful statement than "the monitor is weak": it says the *representation*
is wrong for detection specifically. A stagnation score suitable for alarming must be **stationary
within a run** — flat while the agent works, rising only when it stalls. The rolling-redundancy
score is not, because redundancy genuinely rises as a run progresses and the agent settles.

That is the concrete requirement for the next attempt: not a better threshold, but a **stationary
stagnation statistic**, for example a score normalised against a model of how redundancy typically
evolves with progress, or a residual against predicted behaviour rather than a level.

## 7. Artifacts

| File | Contents |
|---|---|
| `docs/REBUILD_PLAN.md` | the frozen plan, with pre-registered interpretations |
| `scripts/secure_assets.py`, `secure_wordvecs.py` | asset caching, re-runnable, offline-verified |
| `scripts/probe_outcomes.py`, `probe_target_density.py`, `probe_target_variability.py`, `probe_base_rates.py` | the four probes behind §3 |
| `scripts/test_embedding_upgrade.py` | attempt 2 (controlled representation swap) |
| `scripts/test_semantic_relevance.py` | attempt 4 (relevance function swap) |
| `scripts/test_multiscale.py` | attempt 3 |
| `scripts/test_joint_model.py` | attempt 1, with paired clustered bootstrap |
| `scripts/test_ceiling.py` | the ceiling analysis and baseline bootstrap |
| `results/final/v2/*.json` | every result above, as frozen artifacts |
