# AI assistance log

This file records what an autonomous AI agent did on this project, so that the required
AI-use disclosure statement for the S.-T. Yau High School Science Award can be written
accurately and the organising committee can audit the work. It is written by the agent, in
the first person of the agent, and it deliberately records failures and dead ends as well as
successes.

**Rounds covered:** 2026-09-10, 22:15 to 2026-09-11 06:00 (Asia/Shanghai), single continuous
session.

**Final artifact counts:** 1,500 trajectory analysis sample (100,848 agent steps); 1,457
annotation cards generated; 1,785 label rows collected across 61 reader sessions (88 published
subagent runs plus follow-up passes); 654 adjudicated windows over 81 trajectories; 201,696
window feature vectors; 30 monitors evaluated over 5 task-level folds; 6 figures; 1 paper
(`paper/main.pdf`).

**Tooling actually used**

| Tool | Version / endpoint | Purpose |
|---|---|---|
| DSH autonomous coding agent | DeepSeek Harness, model `deepseek-flash` | everything below |
| Subagent fan-out | 56 independent annotation subagents (6 + 6 + 18 + 32, one batch each) | applying the annotation codebook to window cards |
| Python | 3.10.9, NumPy 2.2.6, pandas 2.2.3, scikit-learn 1.7.2, PyArrow 24.0.0, Matplotlib 3.10.9 | feature extraction, models, figures |
| LaTeX | MiKTeX, `pdflatex` | paper build |
| `web_search` tool | **unavailable** (invalid API key) | not used; replaced by direct HTTP fetches |
| `Invoke-WebRequest` / `urllib` | direct | competition rules, arXiv metadata, dataset download |

## What the agent did

### 1. Competition research (before any code)
Fetched and read the 2026 rules, the judging criteria page, the schedule and the AI-use rules
from `yau-awards.com`; recorded them in `research/docs/award/`. Established that the
submission is due 2026-09-15, that the Computer Science category is judged on relevance,
importance, originality/advance, correctness of results with reproducibility evidence,
teamwork and academic standards, and that the AI rules permit assistance with literature
leads, code debugging, data analysis and language while forbidding ghost-writing and
fabricated data. All of this shaped the design decisions below.

### 2. Literature verification
Every URL in the research brief was fetched. Outcome:

* verified as existing: the AIware 2026 "Zombie Agents" paper page, arXiv 2607.09510,
  2608.03222, 2607.05391, 2608.16156, 2607.06184, 2605.15206, 2310.06770, 2405.15793, the
  Terminal-Bench and Nebius datasets, the four production issue reports, and the
  AgentStop repository;
* OpenReview `BlVgsZzg0N` returned HTTP 403 to every fetch attempt, so the Zombie Agents
  *full text* could not be read; the paper is therefore cited from its AIware page only, and
  our "semantic redundancy" baseline is described as a reimplementation of the family rather
  than of that specific system;
* a subagent was dispatched to verify the remaining metadata and run a novelty sweep; its
  output is `research/docs/literature_verified.md` (see the note at the end of this file).

### 3. Data acquisition and quality control
Downloaded 1 of 2 Terminal-Bench 2.0 parquet shards (26,052 trials, 17,273 with step traces)
and 4 of 12 Nebius SWE-agent shards (26,680 trajectories). HuggingFace's file host later
became unreachable, which is recorded as a limitation. Two scrape artefacts were measured and
handled explicitly: redacted observations (23% of steps on average) and degenerate
message-loop trajectories. Both are reported in the paper rather than silently dropped.

### 4. Implementation
Wrote the full pipeline under `research/`: loaders for both corpora, action normalisation, an
evidence/state extractor, six families of online window features, ten monitor designs, a
task-disjoint k-fold evaluation harness with two independent alarm metrics, figure generation,
and automatic LaTeX number export. The implementation is ~2,800 lines of Python.

### 5. Annotation
Wrote the codebook (`research/docs/annotation_guide.md`) before implementing any monitor, then
ran three annotation rounds through 56 independent subagent readers: 172 position-sampled
windows, the same windows re-read by a different reader with reduced context, and 1,457 dense
windows at stride 2 to build contiguous regions. Result: 654 adjudicated windows over 81
trajectories, cross-round binary agreement 88.1% (κ = 0.70).

**This is the most important disclosure in this file.** The labels were produced by
AI readers applying a written codebook, not by human experts. The paper says so explicitly in
its limitations section, reports the measured agreement, and keeps every label auditable back
to a step-cited justification. A human independent verification of a subsample remains the
student's responsibility.

### 6. Analysis and writing
Ran the monitor comparison, the leave-one-category ablation, the unsupervised descriptive
statistics, and generated the figures and every number in the paper from frozen artifacts
(`scripts/export_results_tex.py`).

## Things the agent got wrong, and how they were caught
1. **A claimed "semantic redundancy is weak" result was wrong.** An early draft of the
   abstract asserted that the embedding-diversity baseline performed poorly. The first full
   experiment showed it at ROC-AUC 0.63–0.66, competitive with everything else, so the claim
   was withdrawn and the paper now reports the opposite, with an explanation of why the
   baseline is good but not sufficient. Recorded because it is exactly the kind of error the
   data is supposed to catch.
2. **An alarm metric was structurally broken.** First-alarm-versus-region metrics made
   nearly every monitor look useless because only ~50 trajectories carried region labels. The
   fix was a tolerant window-level alarm metric plus coverage reporting; both are now in the
   paper, and the old numbers were discarded rather than reported.
3. **A stall in the feature pipeline** turned out to be two Python objects per float in the
   semantic cache (3 GB of small objects); fixed by keeping NumPy views.
4. **Two subagents wrote to the same output file**, producing a duplicated annotation file;
   the duplicate was removed and the merge script now collapses repeated votes per reader.
5. **The rank-based card assignment was ambiguous** (string sort puts `_101` before `_11`).
   Rather than assume, cross-regime agreement was measured (88.3% versus 88.5% within regime),
   which shows the assignments resolved consistently; the check is kept as
   `scripts/verify_rank_mapping.py`.
6. **One labeler's distribution looked like a miscalibration** (29/30 windows stagnant) until
   the cards were read: the trajectory in question (`feal-linear-cryptanalysis__jbbLGgC`)
   really is stuck in a repeated error loop, and other readers independently agree. A
   rate-based outlier filter was tried, judged to be excluding exactly the readers who saw the
   most interesting runs, and removed; the panel distribution is reported instead.
7. **The headline changed twice because the data contradicted the brief.** First "the semantic
   baseline is weak" (it is the strongest single family), then "task-grounded evidence improves
   on the semantic baseline" (it does not; the paired, trajectory-clustered comparison excludes
   zero against it). Both reversals are stated in the paper rather than quietly dropped.
8. **LaTeX refused the generated macro names** with the misleading error "Missing
   \begin{document}". Bisection showed this MiKTeX build rejects `\newcommand` names that
   contain a digit; the exporter now spells digits out (`B4` becomes `Bfour`), and
   `scripts/pdf_text_probe.py` checks that the numbers actually reach the PDF.
9. **A calibration experiment produced a null result** (matching each monitor's firing rate to a
   budget instead of its raw threshold). It is reported in the appendix rather than discarded,
   because the reason it fails --- a monitor's own extreme scores inside a run are often
   productive moments --- is informative about what these signals measure.
10. **A byte-level defect in the shipped annotation cards was found by an annotator, not by a
    test.** Source observations contain terminal control sequences, and 85 of the 1,457
    generated cards carried non-printing bytes, three of them NUL — enough for text readers to
    refuse the file as binary. The annotator stripped the byte, read the card and reported it;
    no automated check had looked at the card bytes at all. Fixed by
    `scripts/clean_cards.py`, with `scripts/audit_cards.py` as a permanent check. The frozen
    labels were not re-derived: the disagreement rate on the affected cards is 13.3% against
    15.3% for clean cards, so the bytes did not measurably hurt them, and re-reading would
    invalidate the frozen features and every published number. This is recorded as an open
    judgement call for the student in `docs/KEY_FINDINGS.md` §4.

## What the agent did not do
* It did not run any model-based judge inside the monitor; the monitor is symbolic by design.
* It did not fabricate, extrapolate or smooth any number. Every number in the paper is
  generated from a frozen artifact by `scripts/export_results_tex.py`.
* It did not decide the final scientific claim on the student's behalf: the paper states the
  evidence and its limits, and the falsification conditions for the central claim are written
  into `research/docs/research_decisions.md`.
* It could not use a pretrained sentence encoder (model host unreachable) and says so.

## Note on `docs/literature_verified.md`
A subagent was given the task of fetching the full text of the Zombie Agents paper and running
a novelty sweep over arXiv and Semantic Scholar. At the time of writing that task had not
produced a file, so no claim in the paper depends on it. If it appears later, its contents
should be folded into the related-work section only after the student checks each citation
against the source, as the competition rules require.

---

# Round 2 — 2026-09-12, objective-label rebuild

**Session:** 22:45 (2026-09-12) onward, Asia/Shanghai, single continuous session.
**Purpose:** rebuild the *data and results* (not the prose) after a gap analysis found the
first version's headline limitation — that its progress labels were AI judgements — could be
removed entirely.
**New package:** `src/agentstall/` (new modules: `corpus`, `features`, `targets`, `evaluate`,
`sequential`). The first version's `src/features.py`, `src/monitors.py` and all of
`results/final/` were left untouched.

**Scale of what was built and evaluated this round:** 1,256,295 agent steps; 41,429
trajectories; 1,258 tasks; 236,137 mechanically labelled edit steps; 363,707 window feature
vectors; 27 monitor configurations over task-disjoint folds; 15 analysis artifacts.

## 1. A literature scan was run first, and it changed the framing
One subagent scanned 2025–2026 work on loop/stagnation detection. It found that the
*connective claim* ("activity is not progress") is already published — Zombie Agents
(AIWare 2026) on semantic livelock, LivePlan (arXiv 2608.06701) with an online rule-based
monitor on SWE-agent, AgentStop (Brave) with a deployed stop classifier — and that
"no public trajectory corpus ships per-step test outcomes" is true. It also surfaced
counter-evidence the first version never engaged: failures are *longer* per agent but
*shorter* within contested tasks (arXiv 2604.02547), and early-trajectory signals are weak
(arXiv 2608.29685). **Consequence:** the round did not try to claim novelty for the concept,
and it adopted the within-instance control that the counter-evidence demands.

## 2. The decisive step was refusing a conclusion from round 1
Round 1 concluded "this release contains no dense objective progress signal to predict",
generalising from Terminal-Bench (which ships only a final reward). That generalisation was
wrong. Scanning the *other* corpus on disk found that **95.8% of SWE-agent edit steps** carry a
`[File: … (N lines total)]` footer — a mechanical measurement of the workspace. Everything
downstream rests on that: file line counts, no-op edits, and the text an edit introduced,
recovered from the action itself and joined against the agent's own final patch.

## 3. Bugs the agent introduced, found, and fixed (all now covered by tests)
1. **`pd.DataFrame(list_of_dicts)` silently dropped rows** when a dict carried a key the
   first dict lacked: 694 buffered trials became 598. Fixed by writing with
   `pa.Table.from_pylist`.
2. **A second ParquetWriter on the same path restarted at byte 0**, erasing earlier rows
   (379 runs became 319). Fixed by seeking to the end of the existing file.
3. **Resume was table-level, so a parser change was silently ignored** — a rebuild after a
   parser fix reported "+0 runs" and kept 2,487 trials the new parser could read. Fixed with
   `--fresh`, and documented.
4. **A window's own change rate *is* the first version's label target.** The first analysis
   was circular: it predicted a window's contents from the same window's contents, giving a
   spurious 0.95 AUC. Fixed by making the primary target the *next* window
   (`y_future_stagnation`), which changed every headline number.
5. **The e-process tested the wrong direction.** It accumulated evidence that events occur in
   order to prove that events had stopped; it detected 1 run in 4,823. Replaced with a
   calibrated persistence rule against genuinely event-free runs.
6. **A NaN in a boolean test is silently False.** Runs with no scored window looked like clean
   negatives and drove the false-alarm rate to zero by accident. Fixed by back-filling the
   first score causally.
7. **The edit-line extractor counted context as written text.** A SWE-agent `edit A:B` block
   prints the whole anchored region with line numbers; only lines in `A..B` are new. Fixing it
   moved the measured wasted-work rate from 76% to 84%. Caught by a unit test written for the
   purpose, then verified against the dataset's own published statistics (median 1 new line per
   edit, against the README's ~5 average over a different model mix).
8. **A metric normalisation returned a sub-chance partial AUC** (0.487 on a separable case).
   Replaced with the `sklearn` convention.
9. **Prefix-invariance leaked the run length** into a position control. Fixed by computing
   position from the prefix only.
10. **A monitor-name mismatch (`NOVraw` vs `NOV_raw`)** silently reduced a 29-monitor analysis
    to 5 controls. Found by printing the zoo size rather than trusting the output.

The pattern is worth recording for the student: **eight of the ten were found by tests or by
deliberately checking an internal quantity against an external one, and none by reading
output.** The test suite (`scripts/run_rebuild_tests.py`, 10 tests) and the artifact
consistency checker (`scripts/check_rebuild_consistency.py`) exist because of this list.

## 4. What was measured, and the reversal
The first version's central claim — that window-level stagnation detection saturates at
ROC-AUC ≈ 0.78 — **did not survive**. Re-scoring the same feature families against the
mechanical target on the same windows gives 0.85–0.96, and re-orders the families. The 0.78
ceiling was a property of the AI judgements, not of the trajectories.

The rebuild's own conclusion is a different, and sharper, negative: **80% of agent editing
produces lines that never reach the agent's own final patch; that waste is a stable per-run
property and is outcome-relevant within the same instance (*p* = 1.9 × 10⁻⁹); and it cannot
be predicted online (AUC 0.539) even though quietness can be, with a future-aware upper bound
showing the limit is the observable channel rather than the label or the model.**

## 5. What the agent did not do this round
* It did not touch the first version's modules, results, labels, figures or paper.
* It did not re-run any environment, container or test suite: no Docker is installed and the
  machine has had **no network since 2026-09-10**. The objective signal is therefore built
  from *recorded* telemetry (file line counts, patch text, evaluation transcripts), never from
  re-execution. This is stated as a limitation.
* It did not use a pretrained encoder: the round-1 cache exists but the study's strongest
  results are symbolic and cheap, and the round-1 finding (a real encoder scored *worse*)
  was not revisited.
* It did not decide the final scientific claim. `docs/GAP_ANALYSIS_AND_PLAN.md` §5 lists the
  three forks that remain the student's call.
* It did not fabricate or hand-enter a single number: `scripts/collect_rebuild_numbers.py`
  reads every headline value out of the artifact that produced it.

## 6. Round 2, second half — closing the two reviewer objections

**Sampling-budget check (`capacity_*.json`).** The published AUCs come from a 10-step window at
stride 3, so window length and density were swept on both corpora with task-disjoint folds.
The curves are smooth with broad maxima; the two corpora prefer different window lengths (8 and
15, as expected when runs average 27 and 37 steps) and the published setting sits within 0.021
of its own optimum on each; a 6× change in stride moves the AUC by at most 0.006. The exact
drift-free transform was the worst form at every block in both corpora, which turns §2.10's
"the repair does not help" into "the repair destroys the signal".

**Head-to-head with the field (`detector_families.json`).** The published detectors were
reimplemented from their own descriptions — OpenHands' five production stuck patterns, an
n-gram cycle guard, an exact-repetition guard, a TF-Norm cosine redundancy surrogate, and
AgentStop's two-feature supervisor shape — and run on identical rows, folds and labels. On
every task the study's features win, and the deployed heuristics sit at or near chance
(wasted edit: 0.622 vs 0.515–0.546; no-op edit: 0.821 vs 0.635–0.677; run failure: 0.749 vs
0.663–0.708). Two caveats are recorded with the numbers: AgentStop's real inputs (logprobs)
are not in this corpus, so only its feature *shape* is reproduced; and the wasted-edit base
rate is 0.98, which makes every family's precision at a fixed budget uninformative — only the
AUC separates them.

**A new positive result (`edit_structure.json`).** Whether an edit's lines survive is
predicted better by the **edit's own structure** (AUC 0.732, within-task 0.729) than by its
preceding context (0.60–0.69). The strongest single predictor is how much the edit writes
(0.706 from the line count alone). This is a genuinely actionable finding — a runtime can
refuse a doomed *edit* before applying it — and it is free of the position confound (a
position-only predictor scores 0.488). It also explains why the window features add nothing:
the decisive fact is about to be written, not already visible.

**An instrument, not a result (`docs/human_check_sample.md`).** Twelve annotated windows, half
stagnant and half productive, drawn with a fixed seed, laid beside the stored judgement and the
mechanical verdict — with `scripts/score_human_sample.py` to compute the two agreements once a
person fills the sheet in. The agent deliberately did **not** fill it in: the competition
requires the human to perform the substantive check, and a script that guesses the human's
verdict would defeat the purpose. The script refuses to score an empty column.

**Robustness (`seed_stability_*.json`).** Every headline fit was repeated under five fold seeds.
The standard deviations are 0.0001–0.0010 on both corpora (controls are exact, as they must be),
and the flagship structural result is 0.7316 ± 0.0006. The gap between every monitor and its
trivial control exceeds the seed spread by two orders of magnitude.

**An eleventh defect, caught by its own follow-up.** The structural analysis reported that
*larger* edits survive more often. A follow-up that measured the policy's actual cost produced
the opposite trend, and re-reading the code showed the cause: the univariate block computed the
AUC of a survival-fitted score against a waste label and then "corrected" the direction by
subtracting from 1, which inverts the sign for magnitude features. The truth — verified directly
against the data — is that **small edits are the wasteful ones** (survival 12.6% at one line,
34.8% at eleven or more), and the corrected script now reports both directions for every feature
so the sign cannot be misread again. The findings document briefly contained the inverted claim
and was corrected within the same round. This is recorded because it is exactly the kind of error
a reader should be able to detect from the artifacts: the per-feature table is in
`results/rebuild/edit_structure.json` with both directions named.

## 7. Round 2, third pass — the two objections a reviewer would raise first

**"Your waste label is defined against the agent's own patch, so you are counting revision."**
This is the sharpest attack on the headline, and it was tested rather than argued
(`self_reference.json`). Single-edit runs, where no later edit can supersede anything, waste
**64.1%** of their one edit against 85.3% for runs with eight or more — so iteration inflates the
aggregate, and counting every superseded edit as progress lowers the pooled rate from 0.843 to
**0.788**. But the outcome result does not rest on it: the within-instance solved-vs-failed gap is
**+0.157** (*p* = 6.9 × 10⁻¹³) on edits that were *never* revisited and only **+0.049**
(*p* = 0.078, no signal) on superseded ones. The mechanism the study measures — an edit whose
content never ships and is never revisited — is where the signal lives. The residual case that
cannot be separated offline (a superseded edit that was useful and rewritten for a better reason)
is stated as a limitation.

**"Does it work on a scaffold you have not seen?"** All six scaffolds with ≥200 runs were held
out in turn (`scaffold_transfer.json`): transfer AUC 0.665–0.866, mean **0.775**, all six above
0.60, and mean degradation **−0.018** — the across-scaffold model is marginally *better* on a
held-out scaffold than one fitted on that scaffold alone. No per-scaffold calibration is needed.
The positive rates are a result in themselves: on the same task suite, stagnation prevalence
ranges from **0.260** (mini-swe-agent) to **0.854** (openhands), a factor of three between two
scaffolds working the same issue.

**The edit-admission policy, with its own honest ceiling.** Refusing the worst 40% of edits by
the learned model retains 85.8% of all surviving edits, against 60% for refusing at random and
100% for a perfect policy (`admission_cost.json`). The learned model beats the free "refuse
edits under three lines" rule at that refusal rate (0.858 vs 0.796) but not at a matched
admission rate on survival rate (0.225 vs 0.253). Both are reported, and the recommendation
states the free rule with the model as a refinement rather than claiming a sophisticated win.

**Verification at the end of the third pass.** 11/11 invariant tests (including a new guard that
asserts a feature's AUC direction against the artifact, so the sign error from pass 2 cannot
recur); `check_rebuild_consistency.py` passes; every headline number regenerated.

**Verification at the end of round 2.** `run_rebuild_tests.py` 10/10 passed;
`check_rebuild_consistency.py` passes; every headline number regenerated from its artifact by
`collect_rebuild_numbers.py`.

## 8. Round 2, fourth pass — a result that does *not* generalise

**Early failure prediction works on one corpus and not the other.** Sweeping the observation
checkpoint (`early_prediction_*.json`): on SWE-agent the feature block predicts final failure at
AUC **0.878** with only 10% of the run observed and beats run-length at all six checkpoints; on
Terminal-Bench it never exceeds **0.637** and is only marginally above run-length. The
SWE-agent figure is also partly an artefact, and the artifact says so: runs that died before the
checkpoint are absent by construction, so the earliest cells are enriched in immediate deaths
(97.7% failure against an 84.5% base rate). At checkpoints where the base rate is representative
the block still loses to a counter on Terminal-Bench.

This is recorded as a **negative for generalisation**, not smoothed over: the paper may claim early
failure prediction for a single-scaffold corpus and must not claim it generally.

## 9. Round 2, fifth pass — the headline number changed because the word was wrong

**The agent found a defect in its own headline, and corrected the document rather than the
analysis.** The pooled figure of "84.3% of edits are wasted" was mechanically correct and
rhetorically wrong: it counted an edit as waste when the agent wrote something, it did not
survive into the final patch, *and the agent revised that file again later* — which is iteration,
not waste. Decomposing it (`dead_end.json`) gives three disjoint classes whose rates sum to 1:

| class | share | within-instance Δ (solved − failed) |
|---|---|---|
| kept — a surviving line reaches the final patch | 15.7% | **+0.141** (*p* = 7.6e-14) |
| revised — nothing survived, but the file was edited again | 65.2% | **−0.088** (*p* = 1.8e-13) |
| dead end — nothing survived and the file was never touched again | **19.1%** | **−0.053** (*p* = 9.2e-05) |

**The paper's headline is therefore 19.1%, not 84.3%** — a fourfold correction, applied to the
findings document, the README and the handoff note in the same pass. The three outcome deltas sum
to zero, which is the check that the classes are disjoint and that they measure different things:
a solving run keeps more, revises less, and dead-ends less.

Two lessons worth recording for the student:
* a rate that is *mechanically* well-defined can still be the wrong quantity to quote, and the
  test is whether a reviewer could reasonably object to the word — here, they could;
* the residual question ("was this abandoned edit nevertheless instructive?") is unanswerable from
  trajectories alone and is now stated as a limitation rather than argued away.

**Independent verification of the mechanism.** The pipeline's own quality checks cannot detect
an extractor that is confidently wrong, so the line comparison was re-derived from scratch — raw
parquet re-parsed with `agentstall.corpus`, patches read directly — on a 300-run sample
(`extraction_verification.json`): a recovered line appears verbatim in the patch on **75.9%** of
steps where the patch touches the edited file, against **11.5%** where it does not. That is the
discrimination the mechanism needs, in the right direction, and the residual over-count makes the
waste rate a conservative under-estimate.

## 10. Round 2, sixth pass — where the waste actually lives

**Variance decomposition** (`dead_end_variance.json`). If the dead-end rate were mostly a property
of the issue, a monitor could not act on it; if mostly of the model, it would be a capability
finding. Across 25,681 runs / 1,213 tasks / 3 models: **task 24.8%, model 0.6%, neither 75.0%**.
Three quarters of the variation is run-to-run on the *same* task and model, which is precisely the
condition under which per-run monitoring is the right instrument. The model ordering runs the
expected way (405B least, 70B most) with a rank correlation of −1.00 across only three models,
which the artifact labels anecdotal rather than presenting as a result.

## 11. Round 2, seventh pass — pricing the waste

**Cost telemetry joined to the mechanical labels** (`cost.json`). The Terminal-Bench shard reports
cost and duration for all 14,750 runs and tokens for 88% of them, so the waste can be priced in the
unit a budget is actually spent in. Result: **spending more does not buy solutions.** Across cost
deciles the median spend spans 848× while success spans only 0.143–0.461, and the dearest decile is
among the worst; cost-per-success is 145.7c. 8,543 runs make no edit at all and consume 40.8% of
total spend while succeeding at 0.361 against 0.380 for the rest (this shard's `reward` is
task-specific, so that is a statement about indistinguishability, not about failure). Duration is
only a fair proxy for spend (Spearman +0.406).

**Two data defects were found and handled rather than absorbed.** 141 trials report a *negative*
cost, down to −1524c — credits or reporting artefacts. The first version of this analysis silently
included them, which made the cheapest quintile's boundaries negative and its median meaningless;
they are now excluded from every money aggregate, with the count and the minimum recorded in the
artifact. The token columns are also null for 12% of runs, so every figure carries its own
coverage denominator, printed before any result.

## 12. Round 2, eighth pass — a hypothesis tested and rejected

**The rebuild attributed the first version's 0.78 ceiling to its judged labels. The obvious
mechanism was label noise. That mechanism was tested and is wrong** (`label_cost.json`).

The two targets disagree on **43.3%** of the windows carrying both, with a mutual AUC of 0.594. A
simulation of a perfect detector against a label that flips at rate p gives 0.950 at 5%, 0.899 at
10%, 0.850 at 15%, 0.799 at 20% and 0.707 at 30% — so depressing a perfect detector to the
observed 0.688 would need a **31% flip rate**, far above the reader-to-reader disagreement measured
on the same set. And the disagreement is one-sided: **131 windows the mechanical target calls quiet
were judged PRODUCTIVE**, against 36 in the other direction.

**The real explanation is definitional, and it is a better finding than the one it replaces.** The
codebook counts a window as productive when the agent *learns* — reading, eliminating a hypothesis,
locating a subsystem. The mechanical target counts it as productive when the *workspace changes*.
These are different quantities, not two measurements of one. So the first version's labels are
largely a measure of reading and reasoning; the rebuild's are a measure of shipped work. The paper
must say that rather than calling the old labels noisy, because it tells a reader exactly what each
one measures — and it explains why the feature rankings *invert* between them (REP 0.588 → 0.834,
NOV 0.679 → 0.957, STALL 0.688 → 0.877) while the workspace channel is flat under both.

## 13. Round 2, ninth pass — bounding the policy's claim

**What one wasted edit costs the run** (`dead_end_cost.json`). Success falls monotonically with the
number of dead-end edits (0: **0.212**, 1: 0.182, 2–3: 0.139, 4–7: 0.070, 8+: **0.018**),
and within contested instances the direction holds. But **83.1% of all successful runs contain at
least one dead end** (median 1, maximum 24).

That second number bounds the paper's claim and forced a correction to how the admission policy is
described: a dead end is **survivable**, so the policy buys wasted *turns*, not rescued outcomes.
The findings document now says so explicitly, the agent refused to claim that a refusal would have
saved a run, and the check that produced this is recorded rather than the tidier version.

Two further results: dead ends sit **late** in runs (median position 0.92 through an edit sequence
against 0.46 for other edits), so they are tail churn rather than a wrong foundation; and success
falls off a cliff between two and three dead ends (0.162 -> 0.068), which is a more actionable
threshold than any smooth trend.

## 14. Round 2, tenth pass — the size objection, tested

**Is the survival rate an edit-size artefact?** An edit writing twelve lines has twelve chances to
land a surviving line, so the trend is partly arithmetic. Measured instead of argued
(`size_artifact.json`, 197,627 edits with a known line count): size accounts for about a third of
the headline gap (single-line stratum Δ +0.063 against +0.174 overall), but **the relation holds
in every stratum**, including the one where arithmetic is trivial — a one-line edit has exactly one
chance, and solving runs still land it more often than failing runs on the same instance
(*p* = 6.8e-3). Inside that stratum nothing else predicts survival either (file size 0.479, prior
edits to the file 0.365, position 0.403), so it is close to a coin flip conditioned on context —
and a coin flip that still lands differently for solving and failing runs is the cleanest evidence
that the difference is in what the agent chose to write rather than how much.

## 15. Round 2, eleventh pass — a mechanism proposed, tested, and falsified

**I proposed a mechanism for the label disagreement and the data killed it.** The previous pass
reported that the first version's labels and the mechanical target measure different quantities;
the explanation I wrote was that the codebook counts a window as productive when the agent
*learns* (reading, eliminating hypotheses) while the mechanical target counts it as productive
when the *workspace changes*. That is a claim about behaviour, so it has a signature and can be
checked.

**It was checked and it failed** (`label_signature.json`). The 131 windows a reader called
PRODUCTIVE while the workspace called quiet carry **1.168 edits per window, more than the 1.092 of
the windows both labels call productive**, and a *lower* read fraction (0.047 against 0.120), with
no significant edit-count difference (*p* = 0.108). They are not read-dominated; they are
edit-dense. What actually separates them is novelty — 0.066 new entities per window against 0.238,
a 3.6x gap — so the readers were calling windows productive that the mechanical target sees as
**edit-heavy and information-poor**: work that changes the repository without teaching the agent
anything new.

The findings document now reports the disagreement, the table, and the honest statement that the
obvious explanation was tested and failed. The defensible claim that survives is the operational
one: the two targets rank the same feature families completely differently (NOV 0.679 against
0.957), so a result quoted against one is not evidence about the other.

This is the third mechanism I have had to retract in round 2, and in each case the retraction came
from writing the prediction down in a form a script could falsify. That is worth recording as the
transferable lesson of the round.

## 16. Round 2, twelfth pass — a detection task that is degenerate

**The obvious fix for the sequential result does not work, and the reason is reportable.** The
quiet-window detector of the earlier pass is circular as evidence about waste (its event shares
telemetry with the features), so this pass tried the objective event instead: a window containing a
dead-end edit. Result (`sequential_deadend.json`): **the event is present in 86.6% of runs**
(18,406 of 21,248), leaving 2,842 genuine negatives, and a sequential detector on it reports recall
1.000 and a false-alarm rate of 1.000 at every budget from 20% down to 2%.

That is a degenerate task, not a working detector: with almost no negatives, alarming on everything
scores perfectly on recall and the false-alarm rate has nothing to measure against. The artifact
now carries that verdict explicitly, and the findings document states that **window-level sequential
detection of dead ends is not well-posed on this corpus** — the event is too common to be an event.

Two results survive and the paper should carry both: a detector that works on a properly rare event,
and a demonstration that the more tempting target is the wrong one.

## 17. Round 2, thirteenth pass — four attempts at a waste alarm, and what they taught

**The pass produced a negative of unusual clarity: how *not* to build a waste alarm.** Four
formulations were tried and three failed for reasons worth recording.

1. **Incidental event** (a window containing any dead-end edit): degenerate, because the event is
   present in **86.6%** of runs, leaving 2,842 negatives. Any detector reports recall 1.000 and
   false-alarm rate 1.000 (`sequential_deadend.json`).
2. **Sustained event, run-relative threshold** (a run of consecutive windows above this run's own
   high quantile): degenerate again, because "alarm on the top X% of this run's windows" is true by
   construction once a run has hundreds of windows. Fired on essentially everything
   (`sustained_waste.json`).
3. **Absolute rule, calibrated out of sample** (dead-end share > 0.5 after 3 edits; parameters
   chosen on training instances, applied frozen to held-out ones): **not** degenerate — precision
   0.944, false alarms 0.009, recall 0.331 (`waste_alarm.json`) — but **too late to prevent
   anything**: the median alarm arrives when 100% of the run has elapsed, and only **11.1%** of
   alarms arrive before the run is half over.

**The lesson is specific and belong in the paper.** An alarm on waste must be relative to what is
normal for the moment, which a fixed threshold destroys; and the signal that separates high-waste
runs from low-waste ones accumulates over the whole run, which is what makes it late. A monitor over
cumulative discarded share is a post-mortem instrument, and the data say so in three independent
ways.

The findings document now states the boundary rather than a performance figure: **waste is
measurable and outcome-relevant, and does not support early termination.** That is a stronger and
more useful claim than a detector that fires after the work is spent.

## 18. Round 2, fourteenth pass — making the human check actually usable

**The instrument existed but would not have been used.** `docs/human_check_sample.md` listed twelve
windows with a card path each, so a reader had to find and open twelve separate files before
forming an opinion -- and an instrument nobody runs produces no result. `enrich_human_sample.py`
now generates `docs/human_check_readable.md`, which inlines the **real trajectory text** for each
window (agent reasoning, the command actually issued, the observation returned, trimmed to a
readable excerpt) with the two labels placed *below* the transcript under a heading that says not to
look until a verdict is committed.

A sample of what the reader now sees:

> **[step 15] agent** - Okay, `unix.mak` and `xwindows.mak` mean `make`. `unix.doc` should have the
> install instructions, so I'll read that.
> ```
> cat /app/povray-2.2/machine/unix/unix.doc
> ```
> obs: $34
> **[step 16] agent** - Right, instructions clear. I'll create a `build` directory, copy `source`
> and `machine/unix` files into it, rename `unix.mak` to `makefile`, then run `make`.

Note the redaction (`obs: $34`) in the same window: the corpus replaces some observations with
placeholders, and the existing audit already found that partially legible windows are where
annotators disagree most (5.3% tie rate at zero placeholders against 23.4% at 1-5). A human reader
will now confront that directly, which is the point.

The agent again did **not** fill in a verdict. The competition requires the human to perform the
substantive check, and the scoring script refuses to score an empty column rather than guessing.

## 19. Round 2, fifteenth pass — the recovery story, tested and rejected

**The most attractive narrative in the rebuild was killed by its own test.** Section 2.19 found that
83.1% of successful runs contain a dead-end edit, which invited an appealing reading: the agent
notices its approach is wrong, adapts, and that is why it succeeds. That predicts post-dead-end edits
should differ from pre-dead-end ones, so it was measured within runs against a random-rank split
control (`dead_end_recovery.json`, 3,673 runs):

| | after a real dead end | after a random split |
|---|---|---|
| change in mean edit size | +1.91 lines | +1.54 lines |
| change in new-file rate | −0.115 | +0.097 |
| success when the next edit is larger | 0.091 | 0.102 when it is not (*p* = 0.28) |

**A dead end carries no diagnostic force.** The next edit after a doomed write is statistically
indistinguishable from any other next edit, and the agent turns *away* from new files rather than
toward them. The 83.1% figure is not evidence of recovery; it is evidence that dead ends are spread
through every kind of run, successful ones included.

**Consequence for the paper, stated in the findings:** the story must not imply that an agent
recovers from waste, and refusing a doomed edit would save a turn and nothing more — there is no
evidence the agent would write anything better next. The honest summary is that **wasted edits are a
tax, not a signal and not a cause.**

This is the fourth claim in round 2 retracted or substantially weakened by a test written to falsify
it, and the pattern is now the most transferable thing the session produced: in each case the
retraction came from turning a plausible story into a prediction a script could check.

## 20. Round 2, sixteenth pass - the one quantity that is predictable and early

After the recovery story was rejected, the open question was whether *anything* about a run is both
predictable online and available before the work is spent. The candidate was **file choice**: the
share of an agent's edits landing on files the final patch touches. Unlike line survival (~0.54, i.e.
unpredictable), it is the coarser decision an agent can actually inspect.

It is predictable (`on_target.json`, 20,408 runs, opening 40%, task-disjoint): **AUC 0.723** for
top-quartile on-target runs, 0.681 for bottom-quartile, out-of-fold rank correlation **+0.342**, and
it beats every free alternative (windows observed: 0.503; total edit count: 0.306). A within-task
check holds (0.658).

**But the payoff is not there, and the document says so.** Success by on-target quartile is
0.154 / **0.259** / 0.066 / 0.094 - the best outcome sits in the second quartile, and runs editing
*only* the right files do worse than runs that touch others too. Q3 has the worst outcome and the
most edits (median 14): many files, all correct, none of it working. This is the localisation result
of the earlier pass seen from another angle.

So the honest claim is narrow and useful: **file choice is the one quantity a runtime could monitor
early, and the data do not show that this is where the outcome is decided.** A monitor could tell an
agent it is working in the wrong place; there is no evidence that this is the failure that matters.

## 21. Round 2, seventeenth pass - a numeric audit of every headline claim

**The competition requires every claim to be traceable to data, so the trace is now a script.**
`audit_claims.py` reads the value out of the artifact that produced it and looks for that value in
the findings document, numerically rather than by string equality - the document legitimately
rounds (`1.9e-09` for 1.898e-09; `848` for 847.7), and the first version of the audit flagged three
correctly-rounded figures as failures.

**Result: 17/17 headline claims agree with their artifacts** across `alignment.json`,
`dead_end.json`, `step_task.json`, `edit_structure.json`, `cost.json`, `on_target.json`,
`scaffold_transfer.json` and `extraction_verification.json` - the corpus totals, all three class
rates in the decomposition, both within-instance p-values, the two predictability AUCs, the
structural model's seed mean and sd, the cost ratio, the scaffold-transfer mean and degradation,
the extraction hit rate and the on-target AUC.

It exits non-zero on any mismatch, so it can be a gate rather than a report. Together with
`run_rebuild_tests.py` (11 invariant tests) and `check_rebuild_consistency.py` (cross-artifact
agreement and staleness), the package now has three independent checks that fail loudly.

## 22. Round 2, eighteenth pass - the one-page summary, and the wrong numbers it contained

**A summary is where a stale number does the most damage, so the summary got its own audit.** The
one-page `docs/EXECUTIVE_SUMMARY.md` was written for a reader who has minutes, and
`audit_summary.py` checks every figure in it against the artifact that produced it - the same
discipline as `audit_claims.py`, applied to the document most likely to be read and least likely to
be re-checked.

**It found five errors on the first run, and they were mine, not rounding artefacts.** The summary
claimed the field's detectors scored 0.515 / 0.530 / 0.546 / 0.527 - those are the values for the
*harder* task in the artifact, where every method including this study's is near chance, while the
sentence was describing the easier one, where the correct values are 0.663 / 0.652 / 0.677 / 0.635.
Two further "failures" were a unicode minus sign in `-0.018` and a rounded `0.775` for 0.7745. All
five are fixed, and the detector comparison is now tabulated with one column per task so the two
sets of numbers cannot be confused again.

**Lesson recorded for the student:** a prose paragraph that summarises a table is the highest-risk
place in a paper for a transcription error, and the only reliable defence is to have the checker
read the prose rather than the table.

### Verification at the end of the eighteenth pass

| check | result |
|---|---|
| `run_rebuild_tests.py` - invariant tests | **11/11** |
| `check_rebuild_consistency.py` - cross-artifact agreement and staleness | **passes** |
| `audit_claims.py` - headline claims in the findings | **17/17** |
| `audit_summary.py` - the one-page summary | **0 mismatches** |

## 23. Round 2, nineteenth pass - closing the waste picture

**Does it matter *when* a run wastes?** On a small sampling the raw numbers suggested yes: runs whose
first dead end fell in the first quarter of the run appeared to succeed 11.3% of the time against
17.6% for runs whose first dead end came later. Run properly, on every run with >=6 edits and at
least one dead end (10,287 runs, `dead_end_timing.json`), the effect does not exist: naive success
0.101 against 0.102, and after matching on task *and* run length a paired difference of **+0.009**
across 2,054 pairs (*p* = 0.103).

The discrepancy is itself the lesson: the small-sample comparison was mostly measuring **run length**
(early-dead-end runs had a median of 14 edits against 11), and a control that takes two minutes to
add removed the finding. It is recorded because the pattern - a plausible refinement that a
matching control deletes - recurred five times in round 2.

**The waste picture is now closed on four sides:** the quantity is a *rate* (not a phase, §2.1), not
a *diagnostic* (§2.23), not *position-dependent* (§2.25), and not *early-detectable* (§2.22). Those four
negatives are mutually consistent and they are what the paper's central claim rests on: waste is
measurable and outcome-relevant, and it does not offer a lever.

## 24. Round 2, twentieth pass - chasing an implausibly large number until it explained itself

**The pass produced one result that must be reported and one that must not.**

**Reportable: the detector's own statistic points the wrong way.** The longest run of consecutive
"quiet" windows inside a run’s opening predicts a *high* dead-ender at AUC **0.391** - below chance -
with a rank correlation of **−0.286**. The runs that look quietest early waste *least*, the opposite of
what the detector was built to assume. Consistent with the other instrument tests, and it means "a
quiet run" is not "a struggling run".

**Not reportable, and caught before it was: 0.777 was more than half run length.** The full opening
feature block predicts a high dead-ender at 0.777, which is a suspiciously large gap above the
per-edit figure of 0.539 - so it was controlled. Within run-length deciles it falls to **0.666**, and
against the length-residualised label the rank correlation is only +0.195 (`detector_value_length.json`).

**The control also exposed a property of the metric itself, which is now in the limitations:** longer
runs have *lower* dead-end shares (edit count against dead-end share: ρ = **−0.593**), because a longer
run accumulates more final patch and so more of what it wrote is reachable by the patch's added-line
set. The dead-end share is not length-neutral, and every length-sensitive comparison in the study has
now been controlled for it (§2.19, §2.20, §2.25, §2.26).

The habit that produced both results is the same one this round kept rewarding: when a number looks
too good for its neighbourhood, measure what else it could be measuring before quoting it.

---

## 25. Round 2, final pass - the falsification test that passed, and the headline it corrected anyway

**The main result is a corroboration, and it is the one the goal called for.** The rebuild's central
claim is that the wasted-edit target is unpredictable *because of the observable channel* - a claim
about an exogenous limit, and therefore only credible if it survives a falsification attempt made
from inside the data. I wrote that attempt, fixed its thresholds before running it, and split the 48
window features into the six channels they came from: position, repetition, action-mix, output
novelty, workspace movement, and verification output. Scored alone under one learner on one set of 10
task-disjoint folds (23,411 windows, 733 tasks, 3,133 runs), verification output - test observations,
error/SyntaxError/Traceback/not-found counts, test-count and improvement rates - reaches **0.538**,
i.e. *below* the free position baseline (0.543) and comfortably under the +0.02 threshold that I had
pre-registered as the point at which I would have to narrow the claim. The instrument whose absence
the handoff named as the way to falsify the claim from outside turns out to be present in the corpus
and to add nothing. Verdict: SURVIVES.

**I found a second thing while running it, and it cost me a headline sentence.** The ablation's fitted
model over all six channels reaches **0.599** on those rows - not 0.539. Checking, the 0.539 in the
findings and the executive summary is a *single fixed monitor* (`WS_raw`), while the fitted
multi-channel model's 0.599 (and 0.622 on Terminal-Bench, already sitting two sections away in the
field-comparison table) is the better number. So "essentially unpredictable" and "not predictable at
all" were wrong as written: the target is *weakly* predictable, +0.056 to +0.086 over position
depending on corpus, roughly a third of what the idleness channel yields (0.821). I retired both
phrases in the findings, the executive summary and the handoff paragraph, and rewrote the three
places that carried them. **Two documents had been contradicting each other on the same page for two
passes and it took a channel split to notice** - the same failure mode as the executive summary's
five wrong numbers, and the reason both corpora are now forced onto the same table wherever a
predictability number appears.

**What the correction does to the paper's argument: nothing, and that is the point.** The claim that
matters is a comparison - "whatever predicts waste predicts it about three times worse than it
predicts idleness" - not an absolute claim that waste is unforecastable. That comparison survives;
only the rhetoric around it changed. Seventh claim weakened by a test written to falsify it.

**Then the stability grid made me retreat from my own verdict, which is why it was worth running.**
Reporting "SURVIVES" off one cell would have repeated the exact mistake the pass was about. Re-running
every channel on a 2 learners x 3 fold-seeds x 2 feature-forms grid (12 cells, all task-disjoint, all
10-fold): the position baseline is **0.526, not 0.543** - the 0.543 was the most favourable cell - and
`VER` **beats position in 83% of cells, by +0.010 on average**. That is under the +0.02 I had
pre-registered, so the claim is not falsified, but it is also not the clean null the first run
suggested. I now write it as "a small, reproducible, sub-threshold increment" rather than "adds
nothing". The all-channel number is **0.590 +/- 0.011, positive in every cell**, so the truthful
headline is "weakly predictable by +0.06 with a known sd", not "unpredictable". Three corrections in
one pass, each discovered by making the measurement harder rather than easier.

**One more grid, on the number with the most at stake, and it came out the other way.** Having found
that my own strongest numbers were single cells, I applied the same objection to the one place the
paper claims a head-to-head win - the field comparison - and re-derived the identical feature set on
identical targets over 2 learners x 2 fold counts x 2 seeds. The frozen values are 0.622
(wasted-edit) and 0.821 (no-op); the grid gives **0.632 +/- 0.007** and **0.849 +/- 0.013**, with the
frozen wasted-edit figure at the *bottom* of its own grid and the frozen no-op figure *below every
cell of its grid*, and no cell of either grid anywhere near the 0.515-0.546 band the shipped
detectors occupy. So the win is **understated, not inflated**. I record the asymmetry because it is
the actual lesson: a single-cell number is a hazard when it is quoted upward, and the only way to
know which direction it errs is to run the grid - my suspicion was wrong this time and there was no
way to feel that in advance.

---

## 26. Round 3, pass 26 - the headline was a measurement artefact, and the thesis turned out to be published

**What was asked.** The student selected the "wrong-fix vs lost" phenomenon as the paper's decisive
headline: failed coding-agent runs were said to localise *better* than solved runs (on-target 0.620
vs 0.576, p = 3.3e-4), so failure was a problem of the fix, not of finding the code.

**What I found first: the metric is self-referential.** `on_target` in `analyse_alignment.py` is
computed as the share of a run's edit steps aimed at files in **that same run's own final patch**
(line 132: `patch_files = set(g["patch_file_names"].iloc[0])`). Both the numerator's file set and
the denominator come from the run. It therefore measures *convergence on the run's own output*, not
aim at the *correct* file - and a run that fixates on the wrong file and never wavers scores 1.0.
I fetched genuine gold patches for **927 of 1,213 instances** (843 from `nebius/SWE-rebench`, 84
from SWE-bench) - a target independent of any agent - and recomputed on identical edit steps:

| measure | solved | failed |
|---|---|---|
| `on_target_self` (the frozen definition) | 0.585 | **0.673** |
| `on_target_gold` (independent, basename) | **0.477** | 0.407 |
| `on_target_gold` (independent, path match) | **0.510** | 0.430 |
| `ever_touched_gold` | **0.982** | 0.691 |

The frozen direction reproduces exactly, and then **reverses** on the independent target. Two
published papers report the direction our correction finds, which is what settled it.

**A control that the two metrics are both sane:** restricted to runs whose own patch is a single
file that *is* a gold file - where the two target sets must coincide - they agree (0.615 vs 0.638,
mean absolute gap 0.033, n = 8,801). Neither definition is broken; they measure different things.

**Three mechanism hypotheses, all tested, none survived.** I record this because the time it consumed
is the honest cost of the result:
1. *Confident wrongness* (lost runs should score high on the self-referential metric): **falsified**,
   lost runs score 0.6612 vs 0.6791 for wrong-fix, CI [-0.031, -0.005] excluding zero on the wrong side.
2. *Patch breadth* (failed runs write broader patches, 2.20 vs 1.35 files): **falsified as the
   explanation**, because standardising over patch width makes the self-referential gap *larger*
   (-0.088 pooled to -0.125 standardised) and the gap is already largest in the narrowest stratum.
3. *Fixation* (the metric rewards concentrating on one file): **partially supported, not the
   mechanism**. Failed runs are more fixated (0.779 vs 0.727) and lost runs most of all (0.818 vs
   0.759) - which independently corroborates a published claim that consistency-based monitors are
   fooled precisely when they should not be trusted - but fixation correlates no more with the
   self-referential metric (0.251) than with the gold metric (0.294).

So the result is a **construct-validity** finding, not a mechanism: the metric is a closed loop, and
three plausible mechanisms failed to explain the inversion. The mechanism is recorded as **open**.

**What survived, and it is the better claim.** The binary measure `ever_touched_gold` is positive in
**every** patch-breadth stratum (+0.301 / +0.229 / +0.276 / +0.073), which the share-based measures
are not (`on_target_gold` is +0.070 pooled but only +0.020 after standardisation, with 72% of the gap
being composition, and it sign-flips inside strata 2-4). So the quotable result is:
**98.2% of solved runs and 69.1% of failed runs edit a gold-patch file**, so localisation is
necessary but strictly bounded - it can address at most the 30.9% of failures that never reach the
file. Stable across model scale: 66.8% (70B), 70.7% (8B), 70.2% (405B).

**Retraction, propagated to five places** (`REBUILD_FINDINGS_V2.md` §2.1 and §2.29, `HANDOFF.md`,
`GAP_ANALYSIS_AND_PLAN.md` G7, `EXECUTIVE_SUMMARY.md`), all five pointing at §2.29 for the test.

**The part that changed the paper's contribution, not just its numbers.** While this was being
tested, reconnaissance found and I then verified by direct fetch that the *interpretation* is
already published twice: **Coherence Collapse** ([arXiv:2603.24631](https://arxiv.org/abs/2603.24631),
16,758 trajectories) states that "60-69% of failures on SWE-Agent and OpenHands reach and edit the
correct functions yet still produce incorrect patches" - our 67.1% sits inside that range - and
**arXiv:2511.00197** (ICSE 2026) finds the majority of failing trajectories locate the correct files.
Our dead-end rate of 19.1% also sits against TRIM's CodeSlop 20.0%
([arXiv:2607.18161](https://arxiv.org/abs/2607.18161)), a different object that must be distinguished
explicitly. And "Confident and Wrong" ([arXiv:2603.25764](https://arxiv.org/abs/2603.25764)) owns the
monitoring framing, including the observation that consistency-based monitors look healthy exactly
when the agent should not be trusted.

**So the contribution was re-scoped, and this is the round's real output.** We cannot claim "wrong,
not lost". What remains ours: no located paper reports failed runs localising *better*
within-instance, and a broken self-referential metric is exactly what produces that sign - so the
contribution is the **measurement-validity failure**, demonstrated with both targets on identical
edits, with a control showing the metrics agree where they must, and a corrected form that restores
agreement with the literature (FailForge, [arXiv:2608.08570](https://arxiv.org/abs/2608.08570)).

**Two housekeeping corrections from the same pass.** Four citations were verified by direct
`arxiv.org/abs` fetch rather than trusting the reconnaissance summaries. The reconnaissance's
claimed "263 tasks, p = 1.9e-9" collision with arXiv:2604.02547 could **not** be confirmed against
the abstract and is recorded as UNVERIFIED and propagated nowhere. Separately, the frozen study's
"zero false alarms at every budget 1-20%" claims were found to be **circular** - the label and the
detector are the same statistic, so the numbers reported are literally the oracle's - and were
withdrawn in five places, **reopening gap G5**, which had been recorded as closed.

**Also fixed: the network watcher had been lying for three days.** `watch_network.py` probed only
`huggingface.co`, which is DNS-poisoned on this network, so it reported "no network" while
`hf-mirror.com` and `api.deepseek.com` were both reachable and fast. Nine withheld data shards
downloaded in **62 seconds** once the probe was fixed, taking the corpus from 26,679 to 80,036
trajectories. A false negative that looks like a fact is more expensive than an outage.






## 2026-09-13 (goal round 1: guard misfire matrix)

Tool/model: Muse Spark, DeepSeek Harness web session (this runtime).
Purpose: ground on shipped stagnation heuristics (Exa web searches), then analyse frozen
trajectory data until a verifiable failure-explaining pattern emerged.
Input/task: user goal — "ground yourself with web searches on existing heuristics, then
analyse patterns until something clicks; analysis first."
Output used: (1) heuristic inventory (OpenHands stuck.py thresholds, DSH
repeat-tool-reminder texts/defaults from its README, Claude #73307, LivePlan, overthinking,
goal-drift, wild-misalignment papers); (2) two delegated frozen-data re-analyses (seed 7,
read-only, .venv Python 3.14 + pandas/pyarrow/scipy/sklearn installed from
/Volumes/thinkplus/Code/.python3.14) — guard threshold sweeps and misfire-matrix +
conjunction test on the 386 co-labelled windows, both with Wilson/task-cluster CIs and
pre-registered support bars; (3) findings note research/docs/misfire_matrix.md with curated
tables results/exploratory/r1_guard_sweep.json + r1_misfire.json.
Human verification required: the conjunction-dominance question stays OPEN (CIs overlap);
window aggregates approximate consecutive chains (bias direction stated); no frozen artifact
modified (reproduction deviation 0.0 checked).
What was accepted/rejected: ACCEPTED misfire-both-ways for repetition (0.608/0.193) and the
repetition≈movement mechanism (0.797 vs mechanical); REJECTED edit-density-as-signal
(medians 0/0, AUC 0.594) and conjunction dominance (gain +0.179, CIs overlap — open, not a finding).
