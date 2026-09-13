# GAP ANALYSIS AND AMBITIOUS PLAN — rebuilding the study around objective data

**Date:** 2026-09-12 · **Status update at the end of round 1:** see §6. G1, G2, G3, G4,
G5, G8 and G10 are now resolved or answered; G7 is answered; G6 and G9 are partly
addressed. The numbers are in `docs/REBUILD_FINDINGS_V2.md`.

**Scope:** the *data and results*, not the prose. The essay is deliberately out of scope
until Phase 9.
**Status of the existing study:** complete, verified, internally consistent — and, judged
against the literature it cites, *not yet profound*. It is a careful negative result
built on a small judged label set. This document says exactly why, then plans the
rebuild.

---

## Part 1 — What the current study actually claims

Read from the frozen artifacts (`research/docs/KEY_FINDINGS.md`,
`research/docs/REBUILD_FINDINGS.md`, `research/results/final/tb2_v5/*`):

| Claim | Number | Where |
|---|---|---|
| Best single signal family for window stagnation | ROC-AUC **0.775** | `window_metrics.json` |
| Within a run | **0.633** pooled; median per-run 0.767; chance in ~1/3 of runs | `within_run_robustness.json` |
| Task-grounded evidence (the original hypothesis) | **0.587**, loses to the baseline (paired difference excludes 0) | `paired_comparisons.json` |
| A joint model over all six families | **0.778** (+0.002, p = 0.93) | `v2/joint_model_test.json` |
| A real sentence encoder instead of the bag-of-words surrogate | **0.697** (worse) | `v2/embedding_upgrade_test.json` |
| Claimed ceiling | ROC-AUC ≈ 0.78 | `REBUILD_FINDINGS.md` §5 |
| Why the ceiling exists | "this release contains no dense objective progress signal" — 79% of runs contain no verifiable success event | `REBUILD_FINDINGS.md` §3 |
| Operational value | 36/68 episodes detected at 17% false alarms; 0% detection below a 20% false-alarm budget for the best family | `KEY_FINDINGS.md` §0 |
| The winning score's confound | within-run trend, r = 0.518 with step index, positive in 1256/1344 runs | `REBUILD_FINDINGS.md` §8 |

Two things in that table are already fatal to the "profound" claim: **the ceiling is
measured against the authors' own AI-produced judgements**, and **the winning statistic
is substantially a clock**.

---

## Part 2 — The gaps, ranked by how much they cost

### G1. The evidence base is ~50× smaller than what is already on this disk

The study annotates **45 tasks / 81 trajectories / 1,198 windows**. The raw Terminal-Bench
2.0 release in `data/raw/tb2/` has **26,052 trials across 89 tasks, 26 scaffolds, 49
models**, of which **17,432 carry full step traces**. The study's own `build_dataset.py`
samples `--n 1500` and stops. `data/raw/nebius/` holds a second, independent corpus —
**26,680 SWE-agent trajectories over 1,213 real SWE-bench instances** — that the study
loads with a loader and then never evaluates on (`results/final/v2/` uses 1,200
trajectories only for a "does an objective target exist" probe).

*Consequence:* every confidence interval in the paper is wide, and the "ceiling" is
established on a sample that cannot support a ceiling claim. The baseline's own
task-clustered bootstrap is [0.675, 0.848] — wide enough to contain every alternative,
which the study itself notes. A 0.17-wide interval does not establish a ceiling; it
establishes that the data are too thin to tell.

### G2. The labels are judgements, and that is the study's weakest link — but the fix is not the one the study tried

`KEY_FINDINGS.md` §4 item 1 says the single most valuable next step is a human re-read.
`REBUILD_FINDINGS.md` §3 concludes no objective target exists and therefore the judged
labels cannot be replaced.

**That conclusion is too strong, and it is the single biggest missed opportunity in the
project.** Two things were conflated:

* *Terminal*-Bench's release has no per-step outcome — true, and verified independently.
  No public trajectory corpus ships per-step test-execution results.
* The *Nebius* corpus carries **objective editor telemetry on every step**: 48.2% of all
  observations carry a `[File: … (N lines total)]` footer, and **95.6% of edit steps**
  carry it (`results/rebuild/editor_state_coverage.json`, 353,449 steps scanned). That
  line count is a mechanical, per-step measurement of the workspace. It changes exactly
  when the agent adds or removes lines.

From it one can compute, with no judgement anywhere:

* `ws_delta[i]` — the workspace objectively moved at step `i` or it did not.
* `noop_edit[i]` — the agent issued an edit **and the file's size did not change**: a
  mechanical definition of wasted work.
* `ws_oscillation` — the file grew and shrank repeatedly: a mechanical definition of
  thrash.

Plus, at run level, real oracles: TB2 `reward`, Nebius `target` (tests from the linked PR
applied to the patch), and `eval_logs` test transcripts.

`REBUILD_FINDINGS.md` is right that *per-step test outcomes* are absent. It is wrong that
*no* dense objective signal is present.

### G3. The evaluation protocol hides the between-task confound

The study's own numbers show the problem and then do not fix it: pooled AUC 0.775 vs
within-run 0.633 against a position baseline of 0.644. Per-task stagnation prevalence runs
0.00→0.77. A task-disjoint split prevents *memorising task identity*, but it does **not**
prevent the monitor from ranking tasks by stagnation prevalence, which is a property of
the task, not the moment.

The published literature now names this: "Beyond Resolution Rates" (arXiv 2604.02547,
9,374 trajectories / 19 agents / 500 tasks) shows the length↔failure relation **reverses**
under difficulty control — failures longer per agent (+14.0% to +111.9%), but *within
contested tasks the resolved runs are longer* (44.0 vs 39.6 steps, 63% of 416 tasks,
p = 1.9e-9).

**A monitor that has not been tested within-task has not been tested.** Nothing in the
current study reports a task-stratified, paired comparison.

### G4. The winning signal is a clock, and the study knows it but keeps the headline

`REBUILD_FINDINGS.md` §8: 93% of runs show a positive trend in the winning score, mean
correlation with step index 0.518; anchoring the threshold to the run's own opening fires
on almost everything (88% detection at 91% false alarms); detrending destroys the signal.

So the honest summary of the *published* result is: **the monitor separates regimes, but
the separating quantity is dominated by run position, and no threshold on it can be
calibrated.** The study reports both, but the abstract leads with 0.775.

The repair the study itself identified — "a **stationary stagnation statistic**… a
residual against predicted behaviour rather than a level" — was named and then never
implemented. That is the clearest technical opening in the project.

### G5. No calibration at the false-alarm rates that matter

Operationally relevant regime is 1–5% false alarms. The study's own frontier:
`B4_semantic` catches **0%** of episodes below a 20% false-alarm budget; the best false-alarm
control achieved anywhere is 5% at 21% detection; partial AUC below 5% FPR is never
reported. A monitor that cannot run at a 2% budget cannot be deployed.

### G6. No comparison against the systems the field actually uses

The study compares six of its own feature families. It does not compare against
**AgentStop** (Brave, ACM CAIS 2026 — the deployed online keep-going/stop classifier,
XGBoost on logprobs, 15–20% energy saved at <5% utility loss), **LivePlan**
(arXiv 2608.06701 — deterministic online drift detection on SWE-agent, up to +15.2%
resolution), **OpenHands' stuck detector** (5 fixed patterns), or **RedundancyBench**
(arXiv 2605.29893 — best step-level 24.88%, which is the published bar for step-level
redundancy detection). Reviewers will ask; the paper has no answer.

### G7. The "ceiling" claim overreaches, and its own cited counter-evidence is unaddressed

`REBUILD_FINDINGS.md` §5 generalises six attempts on one target into "window-level
stagnation detection on this corpus saturates at ROC-AUC ≈ 0.78 … the limit is a property
of the task and the data". Six attempts on **one labelled target in one corpus** do not
establish that. The claim needs either a second corpus or explicit scoping.

Related, the study never engages the strongest known objection to its own framing — that
most failures are **wrong-fix, not stuck**. Majgaonkar et al. (ICSE 2026, arXiv 2511.00197)
find **72–81% of failed trajectories still open the correct file**; "Beyond Final Code"
arXiv 2503.12374 finds code-error presence is **not** predictive of failure (54.61% resolve
with ≥1 error vs 54.42% with none). Both are consistent with a hard ceiling, but only if
the paper says *which* kind of failure stagnation detection can and cannot catch. Right
now it does not distinguish them.

### G8. No test of whether the claimed numbers reproduce on an objective target

The one comparison that would settle G1/G2/G7 is missing: run the first version's exact
feature families against objective targets on the bigger corpora and see whether the
ranking survives. If `semantic redundancy` stays best against a mechanical target, the
negative result is robust and worth much more. If the ranking flips, the whole first
version was measuring the label set.

### G9. No sequential framing, so no honest error guarantee

Stagnation monitoring is a **sequential decision problem** (a running test, many looks at
the data). The study thresholds a smoothed score in a fixed-horizon framing, so its false
alarm rate has no interpretation over the life of a run. There is no e-value, CUSUM,
change-point analysis or average-run-length argument anywhere in the artifacts.

### G10. The cost/benefit question is never answered, only gestured at

The paper's operational claim is "good enough to surface a warning, not good enough to
stop a run". It never computes the decision. With 26,680 runs and known rewards one can
measure exactly what a stop policy buys: tokens/steps saved, successes lost, and the
break-even precision a policy must reach to be worth running.

---

## Part 3 — What would make this revolutionary rather than merely careful

Five statements, in increasing ambition. Each is falsifiable, and each is currently
unsupported by anyone:

**R1 (feasibility).** Objective, judgement-free progress labels exist at scale: at least
10⁵ steps and 10⁴ runs carry a mechanical workspace-change signal, and ~10³ runs carry a
mechanical *no-op edit* signal. → proves the field's "there is nothing objective to
measure" assumption false.

**R2 (measurement).** Agents spend **X%** of their steps on work that objectively never
changes the workspace, and **Y%** of runs contain a *sustained* run of such steps; X and Y
are the first non-judged estimates of wasted agent compute.

**R3 (prediction).** Wasted work is *concentrated*, not diffuse: a small fraction of
windows carries most of it. If so, a runtime can act on a short warning rather than a
per-step signal — which reframes the whole problem away from step-by-step classification,
where the field is stuck at AUROC ≈ 0.6 early in a run.

**R4 (the confound, fixed).** A **position-stationary** statistic — `f(t) − mean(f(0..t))`,
computable online with no labels — removes the run-position trend (|ρ| with position from
~0.5 to ~0) while *keeping* the within-run separation, and is calibratable at a 1–5%
false-alarm budget where the first version achieved exactly 0%. If it fails, that is the
sharper result: stagnation and progress would be shown to be **non-stationary by nature**,
and the field's entire threshold-style approach would stand refuted.

**R5 (the boundary, named).** Stagnation detection and failure prediction are *different
problems with different ceilings*: stagnation is detectable (against a mechanical target)
and does **not** predict failure well; failure is driven by wrongness, not by idleness.
With 72–81% of failed runs having found the correct file, this would explain the ceiling
rather than merely report it — and would tell a practitioner precisely what a monitor is
for (cost control) and what it cannot do (rescue a wrong fix).

R1–R3 are descriptive and near-certain to land. R4 and R5 are the scientific bets, and
either outcome is publishable: R4 confirmed = a working detector; R4 refuted = a proof
that the problem as posed is ill-posed.

---

## Part 4 — The ten-hour autonomous plan

Executed in this order; each phase writes a frozen artifact before the next starts. All
work is offline (the machine has had no network since 2026-09-10; a watcher is running in
case it returns).

| # | Phase | What it produces | Kill criterion / honest fallback |
|---|---|---|---|
| 0 | Data audit | `results/rebuild/data_ledger.json` — **delivered as** `rebuild_numbers.json` + `extraction_verification.json` | — |
| 1 | Unified per-step table for **both** corpora (`src/agentstall/corpus.py`, `scripts/build_step_table.py`) | `data/processed/steps/{tb2,nebius}/{steps,runs}.parquet` | if a corpus does not parse, report the fraction of runs lost |
| 2 | Objective targets (`src/agentstall/targets.py`) | `noop_edit`, `ws_delta`, `ws_oscillation`, run oracles | if `<10%` of edit steps carry the footer, the target is unusable → say so |
| 3 | Features incl. **stationary form** (`src/agentstall/features.py`) | `windows.parquet` with `*_s` columns | position |ρ| must drop; if not, R4 fails and is reported |
| 4 | Evaluation protocol (`src/agentstall/evaluate.py`) | task-disjoint folds, task-paired tests, partial AUC, within-run AUC | — |
| 5 | Main analysis vs the **objective** target | `results/rebuild/<corpus>_w*/analysis.json` | — |
| 6 | Reproduce the first version's six families against the objective target | same file, section F | this is the R4/R5 test |
| 7 | Sequential detection with a formal error guarantee | `results/rebuild/sequential.json` — **delivered as** `waste_alarm.json` + `sequential_deadend.json` + `sustained_waste.json` | if e-value power ≈ 0, report the detectable-effect floor |
| 8 | Cost model + decision curve | `results/rebuild/value.json` — **delivered as** `cost.json` + `detector_value.json` + `on_target.json` | — |
| 9 | Cross-corpus / cross-scaffold transfer | `results/rebuild/transfer.json` | negative transfer is a result |
| 10 | Freeze, verify, update `README`/`KEY_FINDINGS`, write the plan for the essay | docs + `verify_all` additions | — |

**Recursion.** After each phase the results are re-read and the next phase's target
updated; if a phase produces a strong signal the following phases *escalate* (more
corpora, more controls, larger sweeps) rather than proceeding flatly. If a phase produces
nothing, the negative is written immediately with the measurement that shows it, and the
plan moves to the next bet. The goal is not to finish the list; it is to find the
strongest true statement the data can support within the window.

**Compute.** CPU only, no GPU, no Docker, no network. Everything is NumPy/pandas/regex,
so the whole pipeline is reproducible on the student's own machine — which matters for the
competition's reproducibility requirement.

---

## Part 5 — What the student must still decide (not the agent's call)

These are recorded here so the human author retains the scientific authority the
competition rules require:

1. **The target.** The agent proposes *mechanical workspace change* as the progress
   target because it needs no judgement. The human must decide whether they accept that
   definition — it is a substantive scientific choice, and a defensible alternative is
   "test outcome" if a corpus with per-step test results can be produced.
2. **The claim.** Whether the paper's headline becomes R4 (a working stationary detector)
   or R5 (stagnation ≠ failure), or both.
3. **The framing of the first version.** Whether the 0.775 result is superseded, or kept
   as a documented case study in how judged labels inflate a signal, which is itself a
   useful methodological contribution.

---

## Part 6 — What round 1 actually settled, and what is left

### 6.1 Gaps closed

| gap | outcome |
|---|---|
| **G1** evidence base 50× too small | closed: 41,429 trajectories / 1,256,295 steps / 1,258 tasks evaluated (was 81 / n-a / 45) |
| **G2** labels are judgements | closed: 236,137 mechanical step labels, no reader; the judged labels are shown to be the weaker target (0.660 vs 0.956 for the same family) |
| **G3** between-task confound | closed: between/within decomposition by task *and* by run, plus the 263-instance paired test (*p* = 2.6 × 10⁻⁸) |
| **G4** the winning signal is a clock | answered, negatively: two online position-stationarity transforms remove the trend (|ρ| 0.242 → 0.138) and do **not** improve detection; position still beats every learned monitor within a run. A negative with a mechanism |
| **G5** no calibration at low false-alarm rates | **STILL OPEN — a retraction.** It was recorded here as "closed: 0 false alarms from 1% to 20% at oracle-level recall", but that number is circular: the target is "k consecutive quiet windows" and the detector is "k consecutive quiet windows", so zero false alarms is definitional (it is exactly the oracle's own number). The one non-circular sequential formulation in the study is degenerate (event in 86.6% of runs; recall 1.000 with false-alarm rate 1.000). No calibration claim survives, and this gap should not be listed as answered |
| **G7** the ceiling claim overreaches | answered: the 0.78 ceiling was the *label set's*, not the task's. But the sub-claim originally recorded here — *"failed runs are better localisers: 0.620 vs 0.576 on-target, p = 3.3 × 10⁻⁴"* — is **RETRACTED**: the metric is computed against each run's own patch and inverts the sign of the comparison. Against an independent gold target solved leads (0.477 vs 0.407). The surviving, robust form is that **69.1% of failed runs already edit a gold-patch file** (vs 98.2% of solved), so localisation is bounded at 30.9% of failures. See `REBUILD_FINDINGS_V2.md` §2.29 |
| **G8** no test on an objective target | done: all six families re-scored against both targets on the same windows |
| **G10** cost/benefit never computed | done: 79% of editing is wasted; edits-to-resolve is monotone (0.245 at 3–5 edits → 0.038 at 21+); a 10% alarm budget stops 40.6% of runs and saves 53.6% of steps |
| **new** the corpus contains no dense objective signal | refuted, with the mechanism identified: editor telemetry is present on 95.8% of edit steps |

### 6.2 Gaps still open, in priority order

1. **G6 — head-to-head against the field's systems: CLOSED, offline.** The published detectors
   were reimplemented from their own descriptions and run on identical rows, folds and labels
   (`results/rebuild/detector_families.json`). On all three tasks the study's features win, and
   the deployed heuristics sit at or near chance. Two caveats are recorded with the numbers:
   AgentStop's logprob inputs are absent from this corpus, so only its feature *shape* is
   reproduced, and the wasted-edit task's 0.98 base rate makes precision uninformative there.
   What remains genuinely blocked is a hand-off comparison against **RedundancyBench's 24.88%
   step-level bar**, which needs that dataset.
2. **Capacity: CLOSED.** Window length, stride and feature form were swept on both corpora.
   Smooth curves, broad maxima, published setting within 0.021 of its own optimum, density
   irrelevant within 0.006. See `docs/REBUILD_FINDINGS_V2.md` §2.12.
3. **Multi-corpus ceiling check.** Two corpora agree qualitatively; a third (SWE-rebench /
   OpenHands) would test whether the "direction, not idleness" conclusion is general. Blocked
   by the network.
4. **Route A/B: RESOLVED.** §6.3 records which branch the data chose and why.
5. **Human spot-check.** The *instrument* now exists (`docs/human_check_sample.md`, twelve
   fixed-seed windows with a scoring script). The reading itself is the student's, by design.
6. **The new lead, now developed: refuse the edit, not the run.** Structural properties of an
   edit predict its fate at AUC 0.732 (within-task 0.729, sd 0.0006) versus 0.60–0.69 for its
   context, and the single strongest predictor is free — **small edits are the wasteful ones**
   (survival 12.6% at one line → 34.8% at eleven or more). An admission policy that refuses the
   worst 40% retains **85.8%** of all surviving edits, against 60% when refusing at random and
   100% for a perfect policy. The learned model beats the free size rule at that refusal rate
   (0.858 vs 0.796) but not at a matched admission rate on survival (0.225 vs 0.253), and both
   are reported. **The honest recommendation is the free rule with the model as a refinement.**
   Nobody has published an edit-admission policy, and this study now has the first measurement
   of one — including the measurement showing the simple version nearly matches the clever one.

### 6.3 Round 2 results — the recursion, resolved

Both routes were run, and the data chose between them.

**Route A: the unpredictable part is the observables, not the label.** Four independent waste
definitions were built on 181,263 labelled steps and scored on identical features and folds:
"the edit's file is untouched by the final patch" (AUC 0.652), "none of its lines survive"
(0.630), "fewer than half survive" (0.604), "the edit moves the file's line count" (0.836),
"the edit touches a file the issue's PR did not" (0.685). Every definition of *wasted
direction* lands in 0.60–0.69 while the pure *movement* question reaches 0.836, so the gap is
not one label's artefact. The future-aware upper bound settles it: adding the run's remaining
length moves the online AUC from 0.630 to 0.636 (**+0.006**) and adding the run's outcome
moves it to 0.635 (**+0.005**). A model allowed to see the future is indistinguishable from the
online one — so no better observable of this kind exists to be found.

**Route B therefore becomes the spine**, and it is stronger than expected: because "the run
never wastes anything" is a real, populated class (6.3% of runs), the detector can be
*calibrated* rather than asserted. A persistence rule calibrated on held-out, task-disjoint
runs reaches **recall equal to an oracle's with zero false alarms** at every budget from 20%
down to 1%. The remaining work in this branch is to optimise that alarm against *failure*
rather than against quietness, and to price it against the alternatives a developer already
has (a step budget, a token budget).

> **Correction (round 2, pass 26).** The sentence above was written before the circularity was
> noticed and must not be used. "Recall equal to an oracle's with zero false alarms" is true
> *by construction*, not by measurement: the label is "k consecutive quiet windows" and so is
> the detector. It is the oracle's own number reported as if it were the monitor's. The
> non-circular version of this task is degenerate (§2.16–§2.17 of `REBUILD_FINDINGS_V2.md`),
> so **Route B's calibration claim is withdrawn** — the spine of the paper is the negative
> result (waste is measurable and outcome-relevant, but not early-detectable from
> action-only observables), not a calibrated detector.

**Escalation taken.** Route A did not lift the online AUC above 0.60, so per the pre-registered
rule the paper's spine is B, and the search does **not** widen to new feature families of the
same kind. The one exception the data itself offers is the grader-derived label (0.685 on a
balanced base rate, above its position baseline) — a *file-level* judgement rather than a
line-level one, which is the only directionality signal that showed life.

### 6.4 Time budget for the remaining window

| phase | what | est. |
|---|---|---|
| 1 | TB2 rebuild with the fixed parser (recovers 2,487 trials) + refresh all artifacts | 25 min |
| 2 | Route A probes A1–A3 | 70 min |
| 3 | Route B: alarm-vs-failure calibration and the alternative-policy comparison | 60 min |
| 4 | Escalate on whatever phase 2/3 produced | 2–3 h |
| 5 | Network-dependent work if the watcher recovers: the second TB2 shard, the remaining SWE-agent shards, RedundancyBench/CodeTraceBench baselines | opportunistic |
| 6 | Human spot-check of 12 gold windows | 30 min |
| 7 | Freeze, tests, consistency check, docs, and a consolidated "what the evidence now supports" statement | 45 min |
