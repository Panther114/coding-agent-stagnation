# Stagnation annotation guide (codebook v1)

This codebook defines the label that the monitors are evaluated against. It is written
to be applied by a reader who sees the **whole** trajectory, while every monitor is
restricted to the **prefix** at the moment of scoring. The two are deliberately kept
separate; leakage control is described in §5.

## 1. Unit of annotation

One **window**: `w` consecutive agent steps `[t-w+1, t]` at the end of which a runtime
monitor would have to decide whether to warn or stop. Default `w = 10` steps.
We annotate windows, not steps, because a single step is rarely informative: a step
that only reads a file can be the most productive step of a run.

## 2. The three channels of progress

A step contributes to progress if it moves **at least one** of the following:

| Channel | Question | What counts |
|---|---|---|
| **E — epistemic** | Did the agent learn something new *and relevant to this task*? | a new relevant file/function/symbol/error signature/test name becomes known; a hypothesis is ruled out by evidence; the search space narrows. |
| **I — implementation** | Did the agent make a durable, task-relevant change? | a file that plausibly matters to the task is created or modified in a way that survives (not immediately undone); a previously broken artefact becomes well-formed. |
| **V — verification** | Did objective evidence about correctness improve? | a failing test passes / failure count falls / build goes from failing to succeeding / the error signature moves from an earlier failure to a later one (i.e. progress past the previous blocker). |

The window is scored on the evidence available **inside the window**, using the
surrounding trajectory only to judge whether the new information was *already known*
or whether a change *survived*.

## 3. Labels

| Label | Meaning |
|---|---|
| `PRODUCTIVE` | At least one channel advanced. The agent is doing something that a competent engineer would call "getting somewhere". |
| `REGRESSION` | The agent un-does its own earlier success: a passing test breaks, an earlier correct localization is abandoned without replacement, the repository stops building. Not stagnant (yet), but not progress. |
| `STAGNANT` | **No channel advanced, and the agent kept expending actions/compute.** Repetition is allowed to be surface-different: the test is whether anything new and task-relevant was learned, durably changed, or objectively verified. |
| `DONE_REDUNDANT` | The task had already been completed and verified inside or before the window, and the agent keeps working (re-reading, re-verifying, re-explaining) without a new goal. A distinct inefficiency class; reported both merged with `STAGNANT` and separately. |
| `BLOCKED_EXTERNAL` | Progress is impossible for reasons outside the agent's control inside the window (dependency download in flight, network unreachable, missing hardware, rate limit). Not the agent's fault; excluded from the binary task and reported. |
| `UNCERTAIN` | The evidence does not let a careful reader decide. Excluded from the binary task. |

Binary task: **positive = `STAGNANT` + `DONE_REDUNDANT`**, **negative = `PRODUCTIVE` + `REGRESSION`**;
`BLOCKED_EXTERNAL` and `UNCERTAIN` are excluded (and their counts reported).

## 4. Decision procedure (apply in order)

1. **Is the task already complete and verified** (a test suite that previously failed now
   passes, or the required output artefacts exist and were validated) and does the window
   add no new goal? → `DONE_REDUNDANT`.
2. **Is progress blocked by something outside the agent's control** (a package download
   that has not finished, a network or hardware failure, an external service refusing)?
   → `BLOCKED_EXTERNAL`.
3. **Did a channel advance inside the window?**
   - new *relevant* information became known (relevant = plausibly in scope of the task
     statement, the reported error, or the artefact being produced), or
   - a durable change to a plausible artefact survived the window, or
   - verification state improved (test/build outcome, failure count, error moved past a
     previous blocker) →
     → `PRODUCTIVE`.
4. **Did verification state get worse, or was an earlier success undone?** → `REGRESSION`.
5. **Otherwise** → `STAGNANT`.
6. If applying 1–5 leaves a genuine tie, → `UNCERTAIN`.

### Worked distinctions

* *Repeated `pytest` invocations where each run fixes a further failure* — the observable
  command repeats but the failure set shrinks: `PRODUCTIVE` (verification channel).
* *Repeated `pytest` invocations that return the identical failure signature with no edit
  in between* — `STAGNANT`.
* *Reading many files in a directory the task statement points at, ending with the
  function that raises the error* — `PRODUCTIVE` even though nothing was written
  (epistemic channel).
* *Re-issuing the same search with paraphrase and getting the same match set* —
  `STAGNANT` (nothing new became known).
* *Editing file A, reverting, editing file B, reverting, editing file A again* — no durable
  change and no verification movement: `STAGNANT`; if a previously passing verification
  broke, `REGRESSION`.
* *A single long `pip install` / `make` / model download with no output yet* —
  `BLOCKED_EXTERNAL` (or `PRODUCTIVE` if the build output advances the verification state).
* *A long compile that starts failing later* — the window where the failure appears is
  `REGRESSION`, not `STAGNANT`.
* *The agent says "the task is complete" and re-reads three files* — `DONE_REDUNDANT` if the
  completion was genuinely verified, otherwise `STAGNANT`.

## 5. Leakage control

* The **annotator** reads the entire trajectory, because judging whether information was
  already known, or whether a change survived, requires the future.
* The **monitor** at step `t` may use only: the task statement, the actions and tool outputs
  of steps `≤ t`, and the diffs those actions imply (as visible in their outputs). It may
  not use the reference patch, future steps, hidden tests, the final reward, or any
  annotation assigned to a later step.
* Window features for step `t` are computed from a window ending at `t`; no feature is
  normalised with corpus statistics that include the evaluation trajectories' future steps.
* The train/test split is by **task**, so no monitor can memorise a task.

## 6. How gold labels are produced in this study

1. A stratified sample of trajectories is drawn (scaffold × outcome × length).
2. Windows are sampled at evenly spaced positions across each trajectory ("position sample")
   so that the label distribution is not dominated by the detector's own opinion, plus a
   small deliberate set of *control* windows (clear expected-productive and expected-stagnant
   cases) used to check that the labels are not degenerate.
3. Independent readers apply this codebook to the annotation cards without seeing any monitor
   score. Agreement between readers is reported, as is self-consistency of the primary reader
   on a re-labelled subset.
4. Disagreements are adjudicated against the codebook; the adjudicated label is gold.

## 7. Known limitations of the labels

* Stagnation is a graded phenomenon; forcing it into windows creates boundary cases where the
  window cuts a productive interval in half. Such windows are labelled by the *majority* of
  step-level evidence and flagged `boundary=true`.
* `DONE_REDUNDANT` depends on knowing that completion was real, which is not always
  observable in the trace.
* Observation truncation (5,000 characters in the Terminal-Bench corpus) can hide evidence
  that the agent actually saw; windows whose only ambiguity comes from truncation are marked
  `uncertain_reason=truncation`.
