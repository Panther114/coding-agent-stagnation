# Executive summary — what this study found

## ⚠️ Current headline (read this first)

> **A runtime monitor can tell *how* a coding agent is failing, and the published ones cannot.**
> When an agent is stuck, the useful decision is whether it is **LOST** (has not found the code) or
> **WRONG-FIX** (found it, and its change does not work) — opposite interventions. On identical rows
> and folds, the published stagnation- and loop-detection families score 0.5589 at predicting failure
> and **0.5960** on the mode question, i.e. at or below chance. A causal router reading only the
> first 10–60% of a run scores **0.7145 / 0.7324** — a gain of **+0.1556** and **+0.1364 AUC**.
>
> **It transfers, and the transfer is bounded — both were tested rather than asserted.** Trained on
> one shard set and scored on the other two in both directions at four fractions (24 cells), cross-set
> performance **equals** within-set performance (0.7145 vs 0.7169; 0.7324 vs 0.7117). The same model
> applied to **88,000 runs from three other scaffolds** scores **0.319–0.495** where the identical
> features fitted *inside* those scaffolds score 0.653–0.761, and it scores 0.426 on our own 125 live
> episodes against a 0.584 baseline. **The generality claimed is shard-level generality within a
> scaffold, and nothing more.**
>
> **A measurement trap, found first and corrected.** The conventional localisation statistic — the
> share of a run's edits aimed at files in *that run's own final patch* — reports failed runs
> localising **better** (0.670) than solved runs (0.594). It is self-referential: a run that fixates
> on the wrong file scores 1.0. Against an **independent gold patch** the direction reverses
> (0.477 vs 0.407), and it reverses again on both held-out sets.
>
> **The live experiment produced one solid effect, and it is about the benchmark; the interventions
> point the right way but do not reach significance.** Every run in the first two conditions reached
> the correct file, because pytest prints the failing test's filename, which contains the module name
> (51.5% of test observations literally name the gold module). Withholding *which* tests failed drops
> success from **0.561 to 0.286** (Fisher *p* = 0.015) and is the only condition in which any run
> failed to find the file. Both runtime interventions --- handing over the file (0.561) and the
> re-check instruction the router prescribes for WRONG-FIX (0.571) --- are ~+0.2 over no intervention
> (0.372) but are **not** individually significant (*p* = 0.125 and 0.084), and a content-free
> "keep going" message at the same trigger reaches 0.452, which the experiment cannot distinguish
> from the instruction it controls for (*p* = 0.383). Reported as suggestive, not as a gain.
>
> **Ten of our own claims were retracted**, each by a test written to falsify it: "failed runs
> localise better" (metric artefact), "zero false alarms at every budget" (circular), "step index
> beats every learned monitor" (the baseline *was* the run's length), a 48-episode condition
> reporting 0/48 success (a deleted interpreter, not a result), a transfer table whose cells came
> from the wrong rows, and the cross-scaffold claim this summary now states as a bound.
>
> **What is not ours.** The *qualitative* finding that agents usually reach the right code and fail
> anyway is prior art ([arXiv:2603.24631](https://arxiv.org/abs/2603.24631), 60–69% of failures on
> 16,758 trajectories; our 67.0% sits inside that range). We reproduce it, at scale, rather than
> discover it. What is new here is the measurement defect that hid the direction of the effect, the
> router that acts on it, and the bounds on both.
>
> **And it replicates twice on unseen data.** All 12 Nebius shards are covered (80,035 runs) as one
> frozen table plus two held-out replications:
>
> | set | shards | runs | self solved → failed | gold solved | gold failed | within-inst *p* | wrong-fix |
> |---|---|---|---|---|---|---|---|
> | frozen | 0–3 | 26,679 | 0.594 → **0.670** | **0.477** | 0.407 | 7.0e-03 | 67.0% |
> | held-out A | 4–7 | 26,680 | 0.593 → **0.677** | **0.492** | 0.421 | 3.6e-03 | 69.0% |
> | held-out B | 8–11 | 26,676 | 0.614 → **0.686** | **0.512** | 0.415 | **2.8e-05** | 66.4% |
>
> The broken metric inverts in all three sets, the correction reverses it back in all three, and the
> wrong-fix share varies by **2.6 points**. The **sharpest limitation** is cross-scaffold: the editor
> footer the mechanical instrument needs exists in **one** framework (95.8% of SWE-agent steps, 0% of
> the others), and the dead-end rate is scaffold-specific — **3.7% to 23.6% across four other
> scaffolds**, so 19.1% must never be quoted as a universal rate.

---

**One page.** For the full evidence and every artifact, see `REBUILD_FINDINGS_V2.md`; for what each
claim rests on and what it cannot support, `HANDOFF.md`; for the rewritten report,
`../paper/v2/main.tex`. Every number here is machine-audited against its artifact by
`scripts/audit_claims.py`, `scripts/audit_summary.py` (this file) and
`scripts/audit_paper_numbers.py`.

---

## The question

Coding agents can run for a long time while accomplishing nothing useful. The original version of
this study asked whether a runtime can tell that an agent has stopped making progress, labelled
windows with a written codebook applied by AI readers, and reported that detection saturates at
ROC-AUC ≈ 0.78.

**That ceiling was the label set's, not the task's.** Re-scoring the identical features on identical
windows against a mechanical target gives **0.85–0.96**, and the feature families *re-rank*. The
labelled set and the mechanical target disagree on **43.3%** of the windows that carry both.

## What replaced the labels

No public coding-agent corpus ships per-step test outcomes — but **95.8% of edit steps carry an
editor footer**, `[File: … (N lines total)]`. That line count is a mechanical measurement of the
workspace, so three things become decidable without any reader:

* whether the workspace moved at a step;
* whether an edit changed **nothing** (19.9% of measurable edits);
* whether the lines an edit wrote appear in the agent's own final patch.

On that basis the study covers **1,256,295 steps · 41,429 trajectories · 1,258 tasks**, with
**236,137 mechanically labelled edits**.

## The measurement

**19.1% of edits are unambiguously wasted** — their content never reaches the final patch *and* no
later action touches that file again. 45,122 edits, 1.8 per run. A further 65.2% are *revision*
(the file was edited again), which is why the coarse "84% wasted" figure must not be quoted.

| class | share | within-instance Δ (solved - failed) |
|---|---|---|
| kept | 15.7% | +0.141 (*p* = 7.6 × 10⁻¹⁴) |
| revised | 65.2% | -0.088 (*p* = 1.8 × 10⁻¹³) |
| **dead end** | **19.1%** | -0.053 (*p* = 9.2 × 10⁻⁵) |

Waste is **not** an episode: its share is flat across every quarter of a run (0.842 / 0.851 / 0.855
/ 0.836). It is a property of the run: split-half reliability ρ = +0.56, per-run variance 3.8× what
independent coin flips give. And **75% of its variation is run-to-run on the same task and model**
(task 24.8%, model 0.6%) — the condition under which monitoring an individual run is the right
instrument.

## The central negative

Two questions that look alike behave oppositely. Predicting from the preceding window:

| target | best AUC |
|---|---|
| the workspace is about to stop moving | **0.823** |
| the next edit changes nothing | **0.823** |
| the next edit's lines never reach the final patch | **0.539** single monitor / **0.590 ± 0.011** fitted 48-feature model (position baseline 0.536 single-monitor, 0.526 over the full grid — §2.27) |

**Activity is monitorable; direction is not.** A future-aware upper bound moves the third number by
**+0.006**, so the limit is the observable channel rather than the model or the label — and a
channel ablation tests that directly: the per-step *test output* already in the corpus scores 0.538, **below**
the position baseline, while the only channel that carries the increment is novelty drift (0.577), a
symptom of the same stagnation the idleness detectors read. So the honest form of the third row is
*weakly* predictable: across 2 learners × 3 fold seeds × 2 feature forms the fitted model sits
**+0.064 ± 0.011** over position and is positive in every one of the 12 cells — but that is a third
of the 0.821 idleness reaches, the free baseline is 0.526 rather than the 0.543 of the single most
favourable cell, and test output on its own beats position in 83% of cells by a sub-threshold +0.010.
Per-step test outcomes were the instrument the handoff named as the way to falsify the central claim;
they are present in the corpus, and they do not close the gap. And the
failure that decides outcomes is a *direction* error: **69.1% of failed runs already edit a file
the gold patch touches** (against 98.2% of successful runs), so they are usually in the right place
and still do not fix it. Localisation is necessary but strictly bounded — it can address at most the
30.9% of failures that never reach the file.

> ⚠️ **Correction (pas 29).** This paragraph previously read *"failed runs are **better** at
> localising (0.620 vs 0.576 on-target, p = 3.3 × 10⁻⁴)"*. That was wrong: the metric is
> self-referential (it measures against each run's own patch) and inverts the sign. On an
> independent gold target, solved runs lead (0.477 vs 0.407). See §2.29 of
> `REBUILD_FINDINGS_V2.md`.

## What a monitor can and cannot do

* **File choice is predictable early** (AUC 0.723 for a run's final on-target rate from its opening
  40%), and it beats every free alternative. But its relation to success is non-monotone — the best
  outcome sits in the *second* quartile, and runs editing only the right files do worse.
* **An edit's own structure predicts its fate** (AUC 0.732, within-task 0.729) better than its
  context, and the strongest signal is free: **small edits are the wasteful ones** (survival 12.6%
  at one line, 34.8% at eleven or more).
* **A waste alarm is precise and useless for prevention**: a calibrated absolute rule reaches
  precision 0.944 and false alarms 0.009, but the median alarm arrives when **100%** of the run has
  elapsed.
* **Waste is a tax, not a signal.** 83.1% of successful runs contain a dead end, and after one the
  agent's next edit is statistically indistinguishable from any other (*p* = 0.28) — it does not
  learn, it does not change course.
* **Spending more buys less**: success spans 0.143–0.461 across cost deciles while median cost spans
  **848×**, and the dearest decile is among the worst. 8,543 runs make no edit at all and consume
  40.8% of total spend.

## Against the field

The published detectors were reimplemented from their own descriptions and run on identical rows and
folds. None of them separates anything:

| detector | predicting a no-op edit | predicting a wasted edit |
|---|---|---|
| OpenHands' five production stuck patterns | 0.663 | 0.515 |
| an n-gram cycle guard | 0.652 | 0.530 |
| an exact-repetition guard | 0.677 | 0.546 |
| a TF-Norm redundancy surrogate | 0.635 | 0.527 |
| AgentStop's feature shape (run-level) | — | 0.663 (run failure; this study 0.749) |
| **this study's features** | **0.821** (0.849 ± 0.013 over a learner/fold/seed grid) | **0.622** (0.632 ± 0.007 over the same grid) |

Novelty and stall also transfer across corpora with a drop of ≤0.02, and **all six scaffolds
transfer above 0.60** (mean 0.775, mean degradation -0.018).

## What failed, and is reported as having failed

Four of the agent's own claims were retracted when a test written to falsify them succeeded: a
headline number fourfold too high; an explanation of the label gap that the behavioural signature
contradicted; a sequential detection target that turned out to be degenerate (the event occurs in
86.6% of runs); and the attractive "the agent notices and adapts" story. Early failure prediction
works on one corpus (0.878) and not the other (0.637) and must not be generalised.

## What only a person can finish

`docs/human_check_readable.md` holds twelve annotated windows with their transcripts inline, ready
to read and score. It answers the one question the rebuild cannot answer about itself: does a
mechanical definition of progress agree with a human reading? One hour of a person's time, and it
is the last open item in the study.
