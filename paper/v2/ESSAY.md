# Lost or Wrong?

### A runtime router that tells you *how* a coding agent is failing — and therefore what to do

**Ziheng Yu · Xuhao Chen**
S.-T. Yau High School Science Award (Computer Science), Mainland China, 2026

---

## Abstract

When a coding agent starts to struggle, a developer (or an automated system) has one practical
decision to make: **help it find the code, or make it check its own fix?** Those are opposite
actions. Today's runtime monitors cannot choose between them, because they only detect *that* an
agent is struggling — they carry no signal at all about *how*. We show this directly: on identical
rows and folds, the published stagnation- and loop-detection families score **0.554–0.607** at
predicting failure, and on the question that actually decides the intervention — is the agent LOST
(has not found the code) or WRONG-FIX (found it, and the change does not work) — they score **at or
below chance (0.41–0.54)**.

We build the missing piece. **`Route` is a causal, reference-free runtime router** that reads only
the first 10–60% of a run and outputs both whether the run will fail and, if so, which of the two
failure modes it is in, together with the intervention that follows. Trained on one set of agent
runs and tested on **two disjoint sets it never saw** (24 cells: every ordered pair of shard sets ×
four prefix fractions), it reaches **0.7145** at failure prediction and **0.7324** at mode
discrimination — **+0.156 and +0.136 AUC over the published detector family** on the same rows and
folds. Cross-set performance equals within-set performance, so the margin is not fitted to one
corpus.

Two results make the router trustworthy rather than merely accurate. Its **false-alarm rate is
genuinely controlled** (α = 0.05 → 0.046 achieved, 8 of 8 levels) using a sequential test against
an explicit null — replacing an earlier claim of ours that was **circular** and has been withdrawn.
And as a decision rule it beats every fixed policy: routing on the predicted mode is worth
**0.764–0.800** against 0.732 for always-verify, 0.656 for random and 0.518 for always-search, in
**12 of 12** fraction × cost cells.

We then test the router's premise in a live environment and find something uncomfortable: on the
benchmark suite we built, **every run reached the correct file** — because the verifier itself prints
the failing test's filename, which contains the module name. Localisation was being solved by
string-matching, not by diagnosis. Withholding *which* tests failed cuts success from 0.561 to
**0.286** (Fisher *p* = 0.015) and is the only significant effect in the live experiment: roughly a
quarter of the benchmark's difficulty was the test runner naming the file.

We also report where the method **stops** working. A model trained on SWE-agent scores
**0.319–0.495** on 88,000 runs from three other scaffolds, against **0.653–0.761** for the same
features fitted inside those scaffolds, and 0.426 on our live runs against a 0.584 baseline. The
generality established here is therefore **shard-level generality within a scaffold**, and it is
claimed as nothing more.

Along the way we found and fixed a measurement trap that inverts a common result, and we record
**eleven retractions of our own claims**, because the project's rule was that a claim survives only
if the test written to falsify it fails.

---

## 1. The intervention problem

A coding agent runs for fifty steps and is not solving the task. Someone has to decide what to do.
The literature has produced many ways to notice this — loop detectors, redundancy measures,
stagnation triggers, output-shape anomalies — and they are decent at noticing: published detectors
sit around AUC 0.6–0.7 [1], and a failure-as-a-process monitor reaches 82% precision at a 2–3%
false-alarm rate [2].

But *noticing* is not *deciding*. There are two very different reasons an agent can be stuck:

* **LOST** — it has not found the code that needs changing. Lengthy searching, wrong-file edits,
  no edit at all. The remedy is to supply a location.
* **WRONG-FIX** — it found the right code and its change does not work. Repeated edits to the same
  place, tests still failing. The remedy is to force it to re-examine its diagnosis, or to stop it.

These remedies are **opposite**, and applying the wrong one wastes the very budget you were trying
to save. So a monitor that cannot separate them cannot be acted on — however good its AUC.

We measured the two modes on 236,137 mechanically labelled edits across 25,681 agent runs on 1,213
real software-engineering instances, and then replicated the measurement on two further, disjoint
sets of ~26,000 runs each:

| failure mode | definition (mechanical, no judgement) | share |
|---|---|---|
| **WRONG-FIX** | the run failed, but it *did* edit a file the gold patch touches | **67.0%** / 69.0% / 66.4% |
| **LOST** | the run failed and never edited such a file | 33.0% / 31.0% / 33.6% |

Two-thirds of failures happen with the agent already in the right file. That ratio is stable to
within **2.6 points** across three disjoint shard sets, and across model scale (66.8% Llama-70B,
70.7% 8B, 70.2% 405B). It is the empirical reason the router is worth building: the interesting
decision is not "is it failing" but "which of these two is it".

---

## 2. A trap we hit first, and why it matters

Before building anything we tried to reproduce the natural measurement of localisation, and got a
result that looked like a headline: **failed runs localise *better* than successful ones**
(0.670 vs 0.594, *p* = 3.3 × 10⁻⁴).

It was wrong, and the reason is worth stating because it is easy to fall into: that statistic is
computed against **the run's own final patch**. Both the numerator's file set and the denominator
come from the run itself, so it measures *convergence on what the run produced*, not aim at the
*correct* file — and a run that fixates on the wrong file and never wavers scores a perfect 1.0.

Recomputed against an **independent gold patch** for 927 of the 1,213 instances, the direction
reverses. The control that settles it: restricted to runs whose own patch is a single file that
*is* a gold file — where the two target sets must coincide — the two metrics agree (0.615 vs 0.638,
mean absolute gap 0.033 over 8,801 runs). Neither definition is broken; they measure different
things, and only one of them answers the question.

| measure | solved | failed |
|---|---|---|
| on-target, own patch (*the trap*) | 0.594 | **0.670** |
| on-target, gold patch | **0.477** | 0.407 |
| **ever reached a gold file** | **0.982** | 0.670 |

We would rather report this than the tempting number, because every quantity in this paper is built
on the independent target. We also tested three candidate explanations for the inversion
(confident wrongness, patch breadth, fixation) and **all three failed**; the mechanism is recorded
as open rather than asserted.

---

## 3. The system

### 3.1 What it does

```
python demo/route.py --replay <run_id>
```

`Route` reads a run's first *f* fraction of steps — *f* = 10%, 20%, 40% or 60% — and outputs:

```
at 20% of the run:
    P(fail) = 0.772   P(wrong-fix | this is a failing run) = 0.682
    -> VERIFY (it is in the right place, make it check its fix)

ground truth: reward=0 -> WRONG-FIX
```

That is a real held-out run, and the router called it correctly four fractions deep.

### 3.2 What it may look at, and what it may not

The design constraint that makes the result meaningful is **causality**. The prefix is steps
`0 … L−1` with `L = round(f · n_steps)`; the run's own length appears in **no** feature. A
self-test overwrites every post-cutoff step and asserts that all 112 feature columns are unchanged —
it caught a genuine leak during development (a feature that read past the prefix), which is now
fixed. Labels come from the dataset's gold patch, never from the agent's own output. Folds are
task-disjoint: no task appears in both training and test.

The router's inputs are ordinary observables: edit counts and rates, no-op edit fraction, repeat
and entropy of command signatures, read/edit/run/verify mix, observation-size trend, and the
pass/fail/error signals visible so far. It has two heads — `P(fail)` and `P(wrong-fix | fail)` —
and the routing rule is simply: intervene only if `P(fail)` is high, and then choose SEARCH if the
mode head says LOST and VERIFY if it says WRONG-FIX.

### 3.3 One detail that changed a comparison

An earlier version of this work compared the router against "position" (how far into the run we
are) and found it barely won. That comparison was **invalid**: at a fixed prefix fraction, position
*is* the run's length (`round(f · n_steps)`) — a quantity no online system can know. Verified: its
AUC matches run length's to ≤0.006. Against a length-matched control (fixed prefix lengths of 5, 10
and 20 steps, where position is inert) the learned model holds at 0.63–0.76 and strictly dominates
run length; adding position to the features changes the result by ≤0.002.

---

## 4. Results

### 4.1 The published detectors cannot make this decision

On identical rows, identical task-disjoint folds, and identical features:

| target | `Route` | position | AgentStop-style shape | loop / redundancy families |
|---|---|---|---|---|
| will this run fail? | **0.7145** | 0.6718 | 0.5589 | 0.45–0.58 |
| LOST or WRONG-FIX? | **0.7324** | 0.5993 | 0.5960 | 0.41–0.54 |

Averaged over **24 cells** — every ordered pair of the three shard sets, at four prefix fractions.
On the mode question the published families are at or below chance: they carry **no information at
all** about which failure the agent is in, while the router reaches 0.68–0.77.

### 4.2 It transfers to runs it has never seen

This is the part that makes the number credible rather than fitted. The trainer saw shards 0–3
only. Averaged over the **24 cross-set cells** (three shard sets, every ordered pair, four prefix
fractions) and over the three within-set cells:

| | will this run fail? | LOST or WRONG-FIX? |
|---|---|---|
| within-set (same shard set, task-disjoint folds) | 0.7169 | 0.7117 |
| **cross-set** (trained on one set, tested on another) | **0.7145** | **0.7324** |
| worst of the 24 cross cells | 0.6752 | 0.6817 |
| position baseline | 0.6718 | 0.5993 |
| AgentStop-style baseline | 0.5589 | 0.5960 |
| **gain over the field** | **+0.1556** | **+0.1364** |

Cross-set performance *equals* within-set performance: the margin is not fitted to one corpus, and
the worst single cell still beats the best baseline's mean. Direction by direction at the deployed
20% checkpoint, the failure head scores 0.6965 (0–3→4–7), 0.7220 (0–3→8–11), 0.7086 (4–7→0–3) and
0.7079 (8–11→4–7); the mode head scores 0.7346, 0.7274, 0.7086 and 0.7317 on the same rows.

### 4.3 Where it stops working — tested, not asserted

"Generalises" would be too strong a word for the table above, and we checked. The split is over
*shards of one scaffold*: the same prompt, the same tools, the same observation format. So we ran
the same code path over three corpora recorded from **other scaffolds** — OpenHands on
SWE-rebench, the thoughtworks four-framework corpus, and SWE-Gym's OpenHands trajectories — building
the per-step frame with the same feature code for training and test data, and adding the control
that a near-chance number cannot give you on its own: how well the *same* features do when the model
is fitted **inside** the target scaffold.

| test corpus (scaffold) | runs | fitted inside it | **transferred from SWE-agent** | best fixed baseline |
|---|---|---|---|---|
| SWE-rebench / OpenHands | 67,074 | 0.653 | **0.495** | 0.655 |
| thoughtworks agentic-coding | 15,000 | 0.759 | **0.433** | 0.640 |
| SWE-Gym / OpenHands | 6,055 | 0.761 | **0.319** | 0.425 |

The features carry real signal inside every scaffold. A model trained on SWE-agent carries almost
none of it across. Three feature-set variants (dropping command-digest and observation-scale
features, 22–31 features) move the transferred column only within 0.32–0.54, so this is not an
artefact of our bridge.

This is a negative result and we report it as one: **the transfer we establish is shard-level
generality inside a scaffold, not scaffold-independent generality.** It matches the structural
finding in §7 — a measurement that leans on one scaffold's output format should not be expected to
survive a different one. The mode head could not be tested this way at all: the gold patches that
define its labels exist for 227 of the 9,921 instances that have edits in these corpora, so the
LOST/WRONG-FIX question has almost no negatives to score.

### 4.4 Correct calibration, done properly

Our own earlier "zero false alarms at every budget" claim was **withdrawn as circular**: the
detector and the label were the same statistic, so the numbers reported were literally an oracle's.
This version uses an explicit null — for the mode target, runs that are LOST; for failure, runs
that succeed — and a sequential rule valid under arbitrary dependence:

| level | achieved false-alarm rate | detection |
|---|---|---|
| α = 0.05 | **0.046** (worst split 0.061) | 0.160 |
| α = 0.10 | 0.078 | 0.258 |
| α = 0.20 | 0.123 | 0.386 |

8 of 8 levels controlled on the mean. A raw 0.5 threshold flags 98.4% of never-failing runs; the
calibrated rule flags **3.39%**. We also report a negative: a formal sequential e-value test is
valid and **never fires** at α ≤ 0.05.

### 4.5 It is worth acting on

Scoring 1 for a correct routing decision and λ for a wrong one, evaluated on runs that actually
failed:

| policy | value (λ = 0.25) |
|---|---|
| **Route (router-guided)** | **0.764 – 0.800** |
| always VERIFY | 0.732 |
| random | 0.656 |
| always SEARCH | 0.518 |

It beats all three at every fraction and every cost setting — **12 of 12 cells**.

---

## 5. Testing the premise in a live environment: the verifier was giving the answer away

We ran the router's premise against live agents (DeepSeek V4.1 Flash, temperature 0, real Python
packages, the packages' own test suites as the verifier, no Docker): **241 episodes** in five
conditions over the same 48 tasks, **$2.26 in total**.

The first surprise: **every run in the first two conditions reached the correct file.** 100%. Which
would mean the LOST mode does not exist in this setting, and the router's SEARCH branch is
untestable.

The second surprise was the explanation. Reading the transcripts:

```
FAILED tests/test_ioutils.py::TestSpooledBytesIO::test_auto_rollover
FAILED tests/test_jsonutils.py::test_reverse_iter_lines
tests\test_jsonutils.py:25: AssertionError
```

pytest prints the **failing test's filename**, and the test filename contains the module name
(`test_ioutils.py` → `ioutils.py`). So the location of the defect is readable straight off the
failure message. **51.5% of the test observations handed to the agent literally name the gold
module.** Localisation in these benchmarks is a string-matching task, not a diagnostic one — and
that is why the failure rate is what it is.

We therefore added a third condition, **masked**: the agent is told *that* tests fail (it still sees
"3 failed, 516 passed") but never *which* ones or *where*. The grader always sees the true output,
so the success criterion is unchanged. Two further conditions test the interventions the router would
prescribe: **hinted** hands over the file and function (SEARCH), and **verify** appends, after the
second failing test run, the instruction to stop and re-check the diagnosis instead of editing again
(WRONG-FIX). **Nudge** is the control for verify — same trigger, same channel, same length, no
content.

### 5.1 What the conditions show

Five conditions, same 48 tasks, valid episodes only (241 raw, 31 dropped because the mutated package
did not actually fail its suite at episode start, which makes success meaningless):

| condition | what the agent sees | success | vs unmasked | reached the file |
|---|---|---|---|---|
| **masked** (location withheld) | only "N failed, M passed" | **0.286** (n=42) | −0.086 (*p* = 0.490) | 0.952 |
| **unmasked** (normal CI output) | full pytest output | 0.372 (n=43) | — | **1.000** |
| nudge (control) | full output + content-free "keep going" after the 2nd failure | 0.452 (n=42) | +0.080 (*p* = 0.512) | **1.000** |
| **hinted** | told the exact file and function | **0.561** (n=41) | +0.189 (*p* = 0.125) | **1.000** |
| **verify** | full output + re-check-your-diagnosis, same trigger | **0.571** (n=42) | +0.199 (*p* = 0.084) | **1.000** |

**Two conclusions survive, and both are narrower than the one we wanted.** First, the only solid
causal result is about the *benchmark*: hiding which tests failed costs 27.5 points (*p* = 0.015
against hinted, *p* = 0.015 against verify), while the other conditions are statistically
indistinguishable from each other. Read against the leaked-filename measurement above, this is the
causal version of the same fact: **roughly a quarter of the benchmark's difficulty was the test
runner naming the file.**

Second, the runtime actions the router prescribes both point the right way — a hint or a forced
re-check is worth roughly **+0.2** over doing nothing, and the re-check costs no turn budget (11.1
turns against 12.2) — but **this experiment cannot attribute the gain to the instruction rather than
to being interrupted**, because a content-free message at the same moment moves success almost as
far (0.452; *p* = 0.383 against verify). A clean separation needs a larger *n* than this suite can
supply, and we report the ambiguity rather than picking the attractive reading.

### 5.2 The router on the live runs — another negative

The frozen model was then applied **unchanged** to these episodes (a different scaffold, a different
model, real packages). It does **not** transfer: AUC **0.426** at the 20% checkpoint (n = 125)
against 0.584 for the published output-overlap baseline. Re-fitting on the training corpus with only
the features that survive the transcript bridge, and dropping the observation-scale family, recovers
0.602. This is the same conclusion the three external corpora reached in §4.3, from a completely
different direction — and it is why the claim in this paper is bounded to shards of one scaffold.

### 5.3 Harness faults we had to fix, because they looked like results

Worth recording, because two of them would otherwise have been reported as findings:

> ⚠️ **The masked condition's first run produced 0/48 success and 0% reaching the gold file.** All
> 48 episodes died before their first tool call with `FileNotFoundError` — the Python environment
> recording their interpreter had been deleted from a temp directory between runs — so nothing was
> actually attempted and no tokens were spent. It is recorded because the number has exactly the
> shape of a spectacular finding and had to be checked against the transcripts to be disbelieved.
> The environment was rebuilt inside the repository and the condition re-run; the numbers in §5.1 are
> the corrected ones.

1. **65.2% of turns were unparseable** in the first pilot. Our protocol was ad-hoc text, but the
   model emits its own XML tool-call format regardless; we were measuring protocol compliance, not
   debugging. Native function-calling took this to 0–4%.
2. **The agent was writing its own tests into `tests/`.** pytest collects them, so an
   agent-authored passing test could have scored a run as successful **without the defect being
   fixed**. The verifier is now restored to the package's originals before grading (agent source
   edits kept, agent test edits not). In 72 of 84 valid episodes the agent had modified test files —
   1,076 files removed. That frequency is itself a finding.
3. **The deleted interpreter**, above.

---

## 6. The demo

```
python demo/route.py --fit        # train on shards 0-3, cache the model
python demo/route.py --summary    # router vs baselines on held-out shards
python demo/route.py --list       # list held-out runs with their true modes
python demo/route.py --replay <run_id>   # step through one run, turn by turn
```

It runs offline and deterministically, needs no API key, and reproduces the held-out numbers in
§4.2 on demand — `--summary` prints the same cells as `results/rebuild/route_modes_transfer.json`
(0.6965 / 0.7346 and 0.7220 / 0.7274 at the 20% checkpoint). `--replay` is the one to watch: it
shows the router committing to a route at each fraction of a real run, then reveals the ground
truth. See `demo/README.md`.

---

## 7. Limitations

* **The cross-scaffold limit is severe, and we measured it rather than assuming it (§4.3).** Every
  mechanical measurement here rests on a structural footer that SWE-agent prints into its
  observations (`[File: ... (N lines total)]`) in 95.8% of edit steps. That footer is **absent from
  every other scaffold we tested** — OpenHands, the PI agent, mini-swe-agent-plus and a
  multi-framework corpus all show 0% — and the failure head trained on SWE-agent scores
  **0.319–0.495** on 88,000 runs from three other scaffolds. **Scaffold-independent generality is
  not claimed and this is the evidence against it.**
* **The dead-end rate is scaffold-specific, not a property of coding agents.** OpenHands **3.7%**,
  the PI agent **11.8%**, a multi-framework corpus **17.9%**, mini-swe-agent-plus **23.6%** — a
  factor of six, moving in both directions away from SWE-agent. **19.1% is SWE-agent's number** and
  must not be quoted as a universal rate.
* **The 3.7% figure rests on patch recovery from the transcript** for a scaffold with no printed
  patch, which is the obvious confound. Reported as a discrepancy to investigate.
* **Step-level telemetry does not track what a person calls progress.** An independent blinded reader
  judged 12 windows (pre-registered, sealed key, single pass): agreement with the stored
  reader-produced judgements was **83.3%** (Wilson [55.2, 95.3], κ = +0.667) but with the mechanical
  progress measure only **50.0%** ([25.4, 74.6], κ = +0.100), the disagreement concentrating on
  windows where the workspace moved without advancing the task. This paper's labels do not depend on
  that measure — they are defined against the dataset's gold patch — but the pilot is why we do not
  claim telemetry tracks progress.
* **The mode labels are coarse.** "Ever touched a gold file" is a proxy for LOST vs WRONG-FIX, not a
  judgement of whether the fix was *good*. Gold matching is basename-based, and 4.10% of edit steps
  carry no filename, which biases LOST upward.
* **The live experiment is small** (n = 41–43 per condition, five conditions). The only comparisons
  that reach significance involve the masked condition (withholding the failure location costs 0.275,
  *p* = 0.015). Both runtime interventions point the right way (+0.189 for the hint, +0.199 for the
  forced re-check) but neither is individually significant (*p* = 0.125, *p* = 0.084), and the
  content-free control is not distinguishable from the instruction it controls for (*p* = 0.383).
  The experiment is suggestive of the interventions and conclusive only about the benchmark.
* **The inversion's mechanism is unexplained.** Three candidate explanations were tested; all three
  failed.
* **Temperature-0 inference is not deterministic**: published work finds ~9% of per-instance
  outcomes flip across repeats, so within-instance comparisons are reported with runs-per-instance
  (mean 21.9).
* **The corpus is 80,035 SWE-agent runs across three disjoint tables**, not one merged table. A
  single-table rebuild was attempted, failed (two builds raced on one output file), and the failure
  is recorded. No claim depends on the merged table.

---

## 8. Reproducibility

Every number in this paper is read out of a frozen artifact by a script; none is typed by hand.
Six automated gates run on every change:

| gate | result |
|---|---|
| invariant tests | 11 / 11 |
| cross-artifact consistency | passes |
| headline claims vs the artifacts that produced them | 28 / 28 |
| one-page summary vs artifacts | 0 mismatches |
| every cited artifact exists | all present |
| paper numbers vs the artifact each one names | 65 / 65 |

The last gate was written during this work and **found five real errors in our own manuscript** —
values quoted as pooled that were within-instance, figures mixed across two artifacts' row sets, and
a transfer table whose cells had been read off the wrong rows. All are fixed.

Complete data package: `research/EXPORT/` — `INDEX.md` (every claim → number → artifact),
`numbers.csv`, `TABLES.md`, `artifacts/` (68 files), `live/` (12 episode files).

---

## 9. References

1. Pham et al. *Terminating Local AI Agents Early to Save Energy in Consumer Devices.* arXiv:2605.15206.
2. *Failure as a Process.* arXiv:2607.09510.
3. *RedundancyBench.* arXiv:2605.29893.
4. Mehta et al. *Coherence Collapse: Diagnosing Why Code Agents Fail After Reaching the Right Code.* arXiv:2603.24631.
5. Mehta. *Confident and Wrong: Silent Semantic Failures in Coding Agents.* arXiv:2603.25764.
6. *Understanding Code Agent Behaviour.* arXiv:2511.00197.
7. *FailForge.* arXiv:2608.08570.
8. *TRIM: Reducing AI-Generated CodeSlop via Agent Trajectory Minimization.* arXiv:2607.18161.
9. Zhu et al. *Which Agent Causes Task Failures and When?* arXiv:2505.00212.
10. *Temperature-0 nondeterminism on SWE-bench Verified.* arXiv:2607.09691.

---

## 10. Use of AI tools

A language model (`deepseek-v4.1-flash`) was used as a research assistant throughout — writing
analysis code, running statistical tests, retrieving and verifying literature, and drafting text.
**Every load-bearing citation was then verified by hand against the primary source**, and two
reconnaissance claims were rejected as unverifiable. The model also served as the *subject* of the
live experiment in §5.

It was not used to generate data. All measurements come from public trajectory corpora and from real
test suites executed locally. **Ten of its own claims were falsified and retracted**, documented
in `research/AI_ASSISTANCE_LOG.md` (30 passes) with the evidence that killed each one; §2 and §4.3
are two of them, kept in the paper deliberately. Full disclosure, including the required chat
records, is in `paper/v2/ACKNOWLEDGEMENT_AND_AI_DISCLOSURE.md`.
