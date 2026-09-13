# Why stagnation detectors fail: the misfire matrix (Goal R1, 2026-09-13)

**Question:** shipped stagnation guards (OpenHands 5-pattern halt, DSH `[3,5,8]` nudge,
Claude-Code-style same-tool+args counters) all watch *repetition or movement*. Do those
signals coincide with human-validated stagnation? **Answer: no — they misfire in both
directions, with measured rates.** Repetition tracks workspace quietness (≈0.80 precision),
not judged stagnation (≈0.39).

## Grounding: what the field ships (Exa survey, same round)

| guard | measures | fires at | documented failure |
|---|---|---|---|
| OpenHands action-obs / action-error | same action + same obs/err | 4+ / 3+ identical | kills legit sleep-poll waits (#5355) |
| OpenHands monologue / ping-pong / context-loop | message/pattern counts | 3+ / 6 cycles / 10+ | — |
| DSH repeat-tool-reminder | exact consecutive (tool+canonical args) | [3,5,8], advisory only | ignored; paraphrase evades (#3819: 1139 calls, fired 2×) |
| Claude Code | budgets, $ ceiling, PreToolUse hook | operator-set | hooks fire after damage |
| Practitioner norm | spend ($2–3/task beats steps) | budget | says nothing about progress |
| SWE-agent doctrine | cost, syntax, lint+revert | deterministic | no semantic detection by policy |
| LivePlan | plan-phase violation, oscillation | rule → LLM advise (+15.2%) | executor non-compliance top regression |

## Data and method

386 windows carrying both an AI-reader codebook label (103 STAGNANT = 90 + 13 DONE_REDUNDANT;
283 PRODUCTIVE = 281 + 2 REGRESSION; human-pilot agreement 10/12, κ≈0.67) and a mechanical
quiet-share target (`gold_matched_windows.parquet`, seed 7, `.venv` Python 3.14 +
pandas/pyarrow/scipy/sklearn). Window aggregates are APPROXIMATIONS of consecutive-chain
guards (stated bias: aggregates smooth bursts → understate burst precision, overstate recall;
frac/maxrep corr = 0.903). Full tables: `results/exploratory/r1_guard_sweep.json`,
`results/exploratory/r1_misfire.json`. Reproduction check: label-signature group means
re-derived with max abs deviation 0.0.

## The misfire matrix (Wilson 95% CIs)

| signal | false-alarm side | miss side |
|---|---|---|
| **Repetition** (rep_exact_frac) | P(reader-PROD \| rep≥0.5) = **0.608 [0.527, 0.685]** (87/143) | P(reader-STAG \| rep≤0.1) = **0.193 [0.142, 0.258]** (34/176) |
| **Movement** (quiet share) | P(reader-PROD \| active) = **0.662** (131/198) | P(reader-STAG \| quiet) = **0.191** (36/188) |

Pre-registered bar (≥0.25 AND ≥0.15): **repetition misfires both ways = CONFIRMED.**
No single-channel operating point reaches precision ≥0.80 at recall ≥0.30 vs reader labels
(best gated: QUIET≥0.9 at 0.516/0.466; REP≥0.6 at 0.436/0.466).

## Why: repetition measures movement, not stagnation

REP≥0.5 predicts the *mechanical* target at precision **0.797 [0.724, 0.855]** (recall 0.576) —
vs 0.392 against readers. Same features, same windows: the signal is real, its object is
quietness. Consistent with frozen `detector_families.json` (shipped families ≈chance on waste,
0.65–0.68 on no-op) and `gold_crosscheck.json` (REP 0.588 judged / 0.834 objective).

## Conjunction test (pre-registered, HONEST NEGATIVE)

Guard = high-rep AND long-verification-stall AND low-novelty. Best cell (K=20, nov≤0.05):
precision **0.607 [0.287, 0.857]** at recall 0.330 — gain **+0.179** over best single (+0.216
vs rep-only) but CIs overlap → **dominance NOT SUPPORTED** (underpowered: 56 firings).
Directionally promising, evidentially open. Needs more labels or step-level chains.

## Dead sub-claim, recorded

Edit density does **not** separate reader labels (medians 0/0, 66%/85% zeros; single-feature
AUC 0.594 max; MIX family 0.512). The group-mean gap is zero-inflation plus tail. Effort ≠
evidence either.

## Behavioral identities of the four cells (exemplars)

- **Fired-but-productive (iterative editing):** `extract-moves…ZE44RbF` t45, `feal-diff…WrYCeFB`
  t33, `feal-linear…923TJt4` t33 (rep 0.9, maxrep 10) — the false alarms a halt-guard would kill.
- **Not-fired-but-stagnant (read-drift / quiet thrash):** `build-pov-ray…bMc6qiA` t33/39/48,
  `compile-compcert…qeLnFSj` t60, `crack-7z…M36nRdr` t27 (rep 0.0) — the misses that burn budget.
- **Fired-and-stagnant (canonical dead loops):** `crack-7z…Mp364LH` t195, `extract-elf…rUUxEg5`
  t27 (DONE_REDUNDANT), `extract-moves…vRcGj7U` t101.
- **Within-run episode:** `bMc6qiA` is a miss at t33/39/48 and a hit at t81/153/177 — the same
  run drifts from undetectable to detectable stall. Episodes, not windows.
- **Bonus:** DONE_REDUNDANT windows average 0.50 quiet — post-completion churn looks *active*,
  so quiet-guards structurally miss the "done but still typing" class.

## Prescription (what a guard must be to respect the reader's diagonal)

1. Never halt on repetition alone: 61% of high-rep windows are productive by human-validated
   labels. Repetition is a *candidate generator*, not a verdict.
2. The onlydeployed-safe conjunction shape is repetition AND no-verification-movement AND
   no-novelty — directionally +0.18 precision here, unproven; treat as experiment, not control.
3. Separate instruments for separate objects: quiet-detector (works, 0.82), done-detector
   (safe economics: stopping a finished run costs nothing), rigidity/edit-quality signals
   (open). One score cannot serve three quantities — this round measured why.

## Limits and follow-ups

386 enriched windows, TB2-only, single rater for the human anchor; window aggregates stand in
for consecutive chains (step-level tables exist: `data/processed/steps/`, exact burst semantics
re-testable); conjunction CIs need ~3× labels to resolve. No frozen artifact was modified;
analysis stack (`.venv`, Python 3.14.7) is git-ignored and reproducible via pip.
