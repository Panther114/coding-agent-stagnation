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
benchmark suite we built, **100% of runs reached the correct file** — because the verifier itself
prints the failing test's filename, which contains the module name. Localisation was being solved
by string-matching, not by diagnosis. Masking the failure location (the agent is told *that* tests
fail, never *where*) is the condition the router exists for, and we report what happens there.

Along the way we found and fixed a measurement trap that inverts a common result, and we record
**eight retractions of our own claims**, because the project's rule was that a claim survives only
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
only. Held-out performance:

| trained on | tested on | failure prediction | LOST vs WRONG-FIX |
|---|---|---|---|
| shards 0–3 | shards 4–7 | 0.735 | 0.749 |
| shards 0–3 | shards 8–11 | 0.749 | 0.776 |
| shards 4–7 | shards 0–3 | 0.729 | 0.709 |
| shards 8–11 | shards 4–7 | 0.771 | 0.770 |

Cross-set AUC equals within-set AUC. **Gain over the field: +0.156 AUC (failure), +0.136 AUC
(mode)** — at every fraction, in every direction, on data the model never saw.

### 4.3 Correct calibration, done properly

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

### 4.4 It is worth acting on

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
packages, the packages' own test suites as the verifier, no Docker). Total spend: **$0.92**.

The first surprise: **every single run in both arms reached the correct file.** 100%. Which would
mean the LOST mode does not exist in this setting, and the router's SEARCH branch is untestable.

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

We therefore added a second condition, **masked**: the agent is told *that* tests fail (it still
sees "3 failed, 516 passed") but never *which* ones or *where*. The grader always sees the true
output, so the success criterion is unchanged.

### 5.1 What the conditions show

| condition | what the agent sees | success | reached the correct file |
|---|---|---|---|
| hinted | told the exact file and function | **0.604** | 0.979 |
| **unmasked** (normal CI output) | full pytest output | 0.449 | **1.000** |
| **masked** (location withheld) | only "N failed, M passed" | 0.000 | 0.000 |

> ⚠️ **The masked row is a HARNESS FAULT, not a result.** All 48 episodes died before their first
> tool call with `FileNotFoundError` — the Python environment recording their interpreter had been
> deleted from a temp directory between runs — so nothing was actually attempted and no tokens were
> spent. It is recorded here because the number is exactly the shape of a spectacular finding and
> had to be checked against the transcripts to be disbelieved. The environment has been rebuilt
> inside the repository and the condition re-run; **the corrected numbers are in
> `results/live/episodes_masked.jsonl` and must replace this row before submission.**

Handing over the file raised success by +15.5 points (0.449 → 0.604). With the failure location
withheld, see the corrected row.

### 5.2 Harness faults we had to fix, because they looked like results

Worth recording, because two of them would otherwise have been reported as findings:

1. **65.2% of turns were unparseable** in the first pilot. Our protocol was ad-hoc text, but the
   model emits its own XML tool-call format regardless; we were measuring protocol compliance, not
   debugging. Native function-calling took this to 0–4%.
2. **The agent was writing its own tests into `tests/`.** pytest collects them, so an
   agent-authored passing test could have scored a run as successful **without the defect being
   fixed**. The verifier is now restored to the package's originals before grading (agent source
   edits kept, agent test edits not). In 71 of 83 valid episodes the agent had modified test files —
   1,048 files removed. That frequency is itself a finding.
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
§4.2 on demand. `--replay` is the one to watch: it shows the router committing to a route at each
fraction of a real run, then reveals the ground truth.

---

## 7. Limitations

* **The cross-scaffold limit is severe.** Every mechanical measurement here rests on a structural
  footer that SWE-agent prints into its observations (`[File: ... (N lines total)]`) in 95.8% of
  edit steps. That footer is **absent from every other scaffold we tested** — OpenHands, the PI
  agent, mini-swe-agent-plus and a multi-framework corpus all show 0%. Cross-framework generality
  is **not claimed**.
* **The dead-end rate is scaffold-specific, not a property of coding agents.** It ranges from
  **3.7% to 23.6%** across four other scaffolds — a factor of six. 19.1% is SWE-agent's number and
  must not be quoted as a universal rate.
* **The 3.7% figure rests on patch recovery from the transcript** for a scaffold with no printed
  patch, which is the obvious confound. Reported as a discrepancy to investigate.
* **The mode labels are a coarse binary.** "Ever touched a gold file" is a proxy for LOST vs
  WRONG-FIX, not a judgement of whether the fix was *good*. Gold matching is basename-based, and
  4.10% of edit steps carry no filename, which biases LOST upward.
* **The live experiment is small** (n = 40–49 per arm). The hinted-vs-unmasked difference is **not
  statistically significant** (Fisher *p* = 0.126) and is reported as such.
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
| paper numbers vs the artifact each one names | 17 / 17 |

The last gate was written during this work and **found four real errors in our own manuscript** on
its first run — values quoted as pooled that were within-instance, and figures mixed across two
artifacts' row sets. All are fixed.

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
test suites executed locally. **Eight of its own claims were falsified and retracted**, documented
in `research/AI_ASSISTANCE_LOG.md` (30 passes) with the evidence that killed each one; §2 and §4.3
are two of them, kept in the paper deliberately. Full disclosure, including the required chat
records, is in `paper/v2/ACKNOWLEDGEMENT_AND_AI_DISCLOSURE.md`.
