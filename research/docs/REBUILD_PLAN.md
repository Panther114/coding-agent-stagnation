# Rebuild plan: from a negative result to a positive one

**Status:** in progress. Written 2026-09-11, before implementation started, at the user's request.
**Deadline:** Yau High School Science Award, 2026-09-15.
**Decisions taken (user, 2026-09-11):** 4 days; international network enabled; success = a genuinely
predictive monitor on an objective target; labels stay AI-annotated but move to measured outcomes;
extend the current paper rather than replace it; include a theoretical spine; keep the old negative
result visible as the baseline step in the chain.

---

## 1. Why the first study could not produce a positive result

Full diagnosis is in conversation; the ranked causes, with the evidence for each:

| # | Bottleneck | Evidence | Fixable? |
|---|---|---|---|
| 1 | **The label is a judgement, so it has a noise ceiling** | Two independent readers agreed only 88% of the time; 25.5% of the observations they read were blanked to placeholders. A monitor cannot exceed `1 − label_error`. | Yes, by changing the target |
| 2 | **The evidence channel tested lexical overlap, not relevance** | A task saying "set up a web server" scores zero relevance for a discovery about `flask`. So the hypothesis was measured with a broken instrument. | Yes, with embeddings |
| 3 | **The winning channel was itself a stub** | `B4_semantic` used hashing bag-of-words; it cannot tell `rm -rf build` from `delete the build directory`. It won anyway (0.775). | Yes, with a real encoder |
| 4 | **Circularity between definition and monitors** | Progress was *defined* as "E or I or V advanced"; monitors then measured E, I, V. All families land in a narrow 0.55–0.78 band. | Yes, by blinding |
| 5 | **Dataset fights the question** | 39% of windows come from runs with a single class; 20 windows split on the completion boundary and all were dropped. | Partly, by restriction |
| 6 | **Evaluation is underpowered** | Task-disjoint folds leave ~220 training windows for 30 monitors; thresholds were tuned on the annotated set. | Yes, by design |

**The one-sentence diagnosis:** I asked monitors to predict a partly unobservable label, measured
the gap, and treated it as an engineering failure. Bottlenecks 1 and 4 are logical; 2 and 3 are
instrument failures.

## 2. The new approach

### 2.1 A formal target (the theoretical spine)

Define the **potential** of a run at step *t* as the probability it eventually solves the task:

```
Phi(t) = P(solve | prefix up to t)
```

A window is **productive** if it raises this potential, **stagnant** if it does not. This is the
definition the first study gestured at but never operationalised, and it has three properties the
old one lacked:

1. **It is causal.** Progress is about the future, not about whether information arrived.
2. **It is measurable.** `Phi` is estimated from **execution outcomes**, not from a reader's
   opinion: does the test newly pass, does the build newly succeed, does a run finish.
3. **It resolves the two open codebook questions.** "A counter advanced but the agent learned
   nothing" and "verification after completion" both become answerable: neither changes the
   probability of solving, because the task is already solved in the second case and the counter
   carries no information in the first.

### 2.2 The task

Predict, at step *t* and using only what is visible at *t*:

> **Y(t) = 1 if the agent achieves verified progress within the next K steps** — a test that newly
> passes, a build that newly succeeds, or the run reaches completion.

Measured from execution records, not judged. Windows are labelled by this rule automatically, at
every step of every trajectory, with no annotator in the loop.

### 2.3 The anti-circularity rule (this is what makes it a real result)

A monitor that watches verification signals could predict "verified progress" by reading the very
thing it predicts. So the **primary monitors are blinded**: they see the agent's text, actions and
workspace changes, but **not** the verification state (exit codes, test results, error
signatures). Verification features are built as a **separate, explicitly-labelled ceiling
baseline** — reported to show how much the answer is simply readable off the environment, and never
mixed into the blinded model.

### 2.4 Channels

| Channel | Representation | What it asks |
|---|---|---|
| Semantic redundancy | **real encoder** (all-MiniLM-L6-v2, 384-d, cached locally) | is behaviour still moving? |
| Semantic novelty | encoder + entity extraction | is new information arriving? |
| **Relevance-weighted evidence** | encoder similarity between task statement and each discovery | **is the new information about the task?** (the hypothesis, properly armed this time) |
| Repetition | actions, normalised | is it repeating? |
| Workspace | file churn | is the workspace changing? |
| *Verification (ceiling only)* | exit codes, test state | how much is readable off the environment? |

## 3. Implementation stages

Each stage writes a frozen artifact and is independently checkable.

| Stage | Deliverable | Script |
|---|---|---|
| 0 | Network assets cached and verified offline | `scripts/secure_assets.py` |
| 1 | Outcome-based labels at every step (`verified_progress`), with K sensitivity | `scripts/build_outcome_labels.py` |
| 2 | Encoder embeddings for every step and every task statement | `scripts/embed_semantics_v2.py` |
| 3 | New feature families incl. semantic relevance | `src/features_v2.py` |
| 4 | Monitors: blinded primary set + verification ceiling | `src/monitors_v2.py` |
| 5 | Evaluation: within-run primary, between-run secondary, K-sweep | `scripts/run_experiments_v2.py` |
| 6 | Comparison to the old study's numbers, same pipeline both ways | `scripts/compare_v1_v2.py` |
| 7 | Figures, tables, macros, paper integration | `scripts/make_figures_v2.py`, exporters |

## 4. What each outcome means (pre-registered interpretation)

Written before seeing results, so the conclusion cannot be chosen after the fact:

- **Primary monitors predict verified progress at meaningfully above chance within a run** →
  positive result. The study's claim becomes: *stagnation is detectable from behaviour alone,
  before the environment confirms it.*
- **Only the verification ceiling predicts** → the honest result becomes: *progress is readable
  only after the environment reports it*, and the paper's contribution is quantified — how much
  earlier the blinded monitors fall short, and why.
- **Semantic relevance beats lexical relevance materially** → the first study's negative finding is
  explained as an instrument failure, and the hypothesis is partially rehabilitated.
- **Blinded monitors fail while unblinded succeed** → the interesting finding becomes *how much of
  "detecting stagnation" is just reading the test output*, which is a genuinely useful negative
  result and a warning for the field.

I commit to reporting whichever branch the data lands in, and to saying which branch it was.

## 5. Known risks

| Risk | Mitigation |
|---|---|
| Network access is withdrawn mid-work | All assets cached locally in stage 0; the pipeline then runs fully offline |
| Outcome labels are too sparse (verified progress may be rare) | K-sensitivity sweep; report prevalence per K; fall back to between-run framing if within-run is empty |
| The blinded signal genuinely is weak | Then that is the result, and it is stronger than the first study's because the instrument is now sound |
| Encoder inference on 100k steps is slow on CPU | Batch and cache embeddings once; measured before committing |
| Time | Stages are ordered so that stopping after stage 5 still yields a complete, reportable result |

---

*This plan is frozen at the time of writing. Deviations, if any, are recorded in
`docs/KEY_FINDINGS_V2.md` with the reason.*
