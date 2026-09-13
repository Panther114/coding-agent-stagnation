# Handoff — how to turn the rebuild into the paper

> **Start with `EXECUTIVE_SUMMARY.md`** — the whole rebuild in two minutes, machine-audited. This file says how to turn it into a paper.

**Audience:** the student authors (Ziheng Yu, Xuhao Chen) and their advisor.
**Purpose:** the rebuild produced the *evidence*; this file says which claim each artifact
supports, what the paper can and cannot say, and which decisions are yours.
**Rule the rebuild followed:** no number here is typed by hand. Every value is emitted by
`scripts/collect_rebuild_numbers.py` from the artifact that produced it.

---

## 1. The one-paragraph version you would write

> Coding agents spend most of their editing on code that never reaches their own final answer.
> Across 1,256,295 steps in 41,429 trajectories on 1,258 tasks, only 15.7% of edits contribute a
> surviving line to the agent's final patch. A further 65.2% are revision; the unambiguous waste is
> the **19.1% dead ends** — 45,122 edits whose content never shipped and whose file was never
> touched again. Quote the dead-end rate, not the coarse one. The waste is not a
> phase — its share is flat across every quarter of a run (84.2%, 85.1%, 85.5%, 83.6%) — and it
> is a property of the run rather than of the moment: split-half reliability ρ = +0.56, and
> per-run variance 3.8× what independent coin flips would give. Pooled length-and-failure
> comparisons are the standard way to report this, and the standard way to be wrong about it, so
> the comparison is made *within* task: on the 263 instances that contain both a solved and a
> failed run, a solving run puts 30.0% of its edits on surviving lines against 19.8% for a
> failing run on that same instance (*p* = 1.9 × 10⁻⁹). The waste is therefore real and
> outcome-relevant. It is also **not where a monitor can help**: whether an edit's lines survive
> is only weakly predictable in practice — a single monitor gets 0.539 against a 0.536 position
> baseline, and a fitted 48-feature model lifts that only to 0.599, a third of the 0.821 the
> idleness channel gives, with **no** help from the per-step test output in the corpus (§2.27);
> a model given the run's own outcome improves the first number by 0.005. What does predict an
> edit's fate is the edit itself — chiefly how much it writes (survival 12.6% at one line rising
> to 34.8% at eleven or more) — which points at *edit admission* rather than run termination:
> refusing the worst 40% of edits by a learned model retains 85.8% of all surviving edits,
> against 60% for refusing at random.

## 2. Claim → artifact → what it does and does not support

| claim you may write | artifact | does **not** support |
|---|---|---|
| 15.7% of edits survive, counting each edit once; 19.5% is the *run-averaged* per-run precision and the median run's precision is 0 | `alignment.json` (`kind_shares.genuine` vs `pooled.mean_precise` vs `pooled.median_precise`), `rebuild_numbers.flat.json` | that a surviving line is a *correct* line; the two percentages are the same quantity under different weighting and must be labelled as such — never quoted as if they disagreed |
| waste is flat across the run (not an episode) | `waste_runs.json` → `temporal_profile` | that waste is not clustered within a run |
| waste is a run property (ρ = +0.56, var 3.8×) | `waste_runs.json` → `split_half_*`, `waste_share_variance` | that the property has a cause |
| outcome-relevant within instance (*p* = 1.9 × 10⁻⁹) | `alignment.json` → `within_instance` | causality: solving runs might edit more because they are near success |
| **localisation is bounded, not absent**: 98.2% of solved runs and **69.1% of failed runs** edit a gold-patch file, so localisation tooling can address at most the 30.9% of failures that never reach it | `wrongness.json` → `failure_decomposition`, `metric_artifact.json` → `patch_breadth.strata` | the frozen claim *"failed runs localise better (0.620 vs 0.576)"* — **RETRACTED**: that metric is computed against each run's own patch and inverts the sign; against an independent gold target solved leads (0.477 vs 0.407). See `REBUILD_FINDINGS_V2.md` §2.29 |
| quietness is predictable (AUC 0.823), direction is not (0.539) | `step_task.json` → `base_rates`, `monitors` | that no observable could do better — see `routeA.json` |
| the limit is the observable channel (+0.006 from future knowledge) | `routeA.json` → `a3_ceiling` | that a *richer instrument* (e.g. per-step test output) would also fail |
| the 0.78 ceiling was the label set's | `gold_crosscheck.json` | that the judged labels are worthless (they separate at AUC 0.669) |
| the field's shipped detectors are at chance | `detector_families.json` | a comparison with AgentStop's real model (logprobs absent) |
| the head-to-head win is **conservative**: frozen 0.622 / 0.821 against grid means 0.632 ± 0.007 / 0.849 ± 0.013, with no grid cell near the 0.515–0.546 band the opponent families occupy | `field_comparison_stability.json` | that the win is large — it is modest and the frozen numbers **understate** it; also that the opponent families need a grid (they are fixed monitors with no hyperparameters) |
| numbers are not sampling artefacts | `capacity_nebius.json`, `capacity_tb2.json`, `seed_stability_*.json` | anything about window lengths outside 3–20 |
| edit structure predicts fate (0.732, sd 0.0006) | `edit_structure.json` | that the prediction is causal |
| edit admission retains 85.8% of surviving edits at 40% refusal | `admission_cost.json` | **any claim about outcomes** — a refused edit is not deleted, and offline replay cannot see what the agent would have done next |
| dead-end vs revision decomposition | `dead_end.json` | the residual 'abandoned but instructive' case — unanswerable offline, stated as a limitation |
| revision-vs-waste confound | `self_reference.json` | that no residual revision case exists — stated as a limitation |
| dead-end *timing* does not matter | `dead_end_timing.json` | anything about when waste occurs — naive 0.101 vs 0.102, matched +0.009 (*p* = 0.103) |
| what the waste costs in money | `cost.json` | any general pricing claim — one corpus, one price regime, and 141 trials carry a *negative* cost |
| file choice is predictable early (0.723) but does **not** track success | `on_target.json` | that good localisation helps — success by on-target quartile is 0.154 / **0.259** / 0.066 / 0.094, non-monotone |
| every headline number, audited | `audit_claims.py` (28/28), `audit_summary.py` (0 mismatches) | — these are gates, not results |
| held-out scaffold transfer (0.665–0.866, all >0.60) | `scaffold_transfer.json` | that scaffolds outside Terminal-Bench behave the same |
| held-out scaffold transfer (0.665–0.866, all >0.60) | `scaffold_transfer.json` | that scaffolds outside Terminal-Bench behave the same |
| early failure prediction (**does not generalise**) | `early_prediction_{nebius,tb2}.json` | any general claim — SWE-agent 0.878 at 10% observed, Terminal-Bench 0.637 maximum; report per corpus or not at all |
| **do not claim** a calibrated detector: the "zero false alarms at every budget 1–20%, precision 1.000, latency 0" figures are the **oracle's own numbers** and are circular — the label is "k consecutive quiet windows" and so is the detector | `sequential.json` → `oracle`, `persistence_sweep`; `check_zero_false_alarm_claim.py` | any calibration claim at all. **G5 stays open**; the non-circular sequential task is degenerate (`sequential_deadend.json`, `sustained_waste.json`). Verified mechanically: no artifact contains a zero-false-alarm budget grid that is not an oracle's |
| spent waste is **weakly but reproducibly** predictable: +0.064 ± 0.011 over position, positive in all 12 learner/seed/form cells | `channel_ablation.json`, `channel_ablation_stability.json` | any sentence of the form "waste is unpredictable" — retired; the position baseline is 0.526, not the 0.543 of the single most favourable cell |
| the limit is the observable channel's **magnitude**, not its possibility | `channel_ablation_stability.json` | that per-step test output adds nothing — it beats position in 83% of cells by +0.010, sub-threshold but reproducible; the increment is carried by novelty drift (NOV, +0.019, 12/12 cells, its own §2.27) |
| sequential dead-end detection is a **degenerate** task on this corpus | `sequential_deadend.json` | any detector comparison — the event occurs in 86.6% of runs, so recall 1.000 comes with a false-alarm rate of 1.000 |
| the persistence statistic does **not** predict waste | `detector_value.json` | that monitoring is useless *in general* — this is one statistic family; correlation is ρ = −0.286, AUC 0.391, i.e. anti-correlated |
| the 0.777 opening-block AUC is **not** length-neutral | `detector_value_length.json` | reporting it as an unconditional result — within-decile 0.666, residual ρ = +0.195 while edit count alone gives ρ = −0.593 |
| the "waste is not a phase" claim survives a *stationarity-mechanism* probe | `stationarity_mechanism.json` | that flatness implies the mechanism is per-edit rather than per-run — both survive; see §2.25 |
| edit cost is not a proxy for edit outcome | `label_cost.json`, `label_signature.json` | that cheaper edits are better — the relationship is weak and sign-unstable across corpora |

## 3. Seven things the paper must say, and where they go

1. **The strongest objection to the whole genre is answered, not ignored.** Most failures are
   wrong-fix rather than stuck: failed runs find the right file *more* often than successful
   ones. Put this in the introduction as the reason the paper measures *shipped work* rather
   than *idleness*, and again in the discussion as the boundary of what any monitor can do.
2. **The rebuild refutes the first version's headline, and that is a result.** Write it as a
   methodological finding — an AI-judged target produced a 0.78 ceiling and a 0.775 headline on
   the same data where a mechanical target gives 0.85–0.96 — not as an embarrassment. It is the
   most transferable message in the paper for other students.
3. **Every negative is reported with the measurement that produced it.** The negatives here
   (position-stationarity destroys signal; a future-aware bound gains 0.006; the learned
   admission model loses to a free size rule at a matched budget) are what make the positives
   credible.
4. **The two corpora are not symmetric and the paper says so.** Terminal-Bench cannot contribute
   to the waste measurement at all (its scaffolds do not print file line counts); it contributes
   the 45-task, 9-scaffold, 33-model generalisation and the cross-scaffold comparison. SWE-agent
   contributes the telemetry, the waste measurement and the 1,213 instances.
5. **Say that the waste picture is closed on four sides.** The quantity is a *rate* (not a phase),
   not a *diagnostic* (the agent does not learn from it), not *timing*-dependent, and not
   *early*-detectable. Those four negatives are mutually consistent and they are the spine of the
   central claim: waste is measurable and outcome-relevant, and it does not offer a lever. If a
   reader asks "so what should a runtime do?", the honest answer from this data is: nothing that
   this monitor enables — and that is the finding.
6. **Report the result that does not generalise.** Early failure prediction reaches 0.878 on
   SWE-agent at 10% of the run and 0.637 on Terminal-Bench — the corpus with nine scaffolds
   disagrees with the corpus with one. Say it per corpus; do not average it away.
7. **Say what would falsify the central claim.** Concretely: a corpus with per-step test outcomes
   where the wasted-edit AUC is materially above 0.54 would falsify "the limit is the observable
   channel", and any experiment where an agent that is refused a doomed edit recovers better
   than the offline ceiling predicts would falsify the admission analysis.

## 4. The three decisions that are yours, not the agent's

1. **The progress target.** "The workspace moved" is mechanical and label-free, which is why it
   is used. It is *not* the same as "the agent was right". You may accept it, or argue for a
   test-verified target and accept the cost (no such corpus exists publicly; you would have to
   re-run environments).
2. **The headline.** The rebuild supports two different papers: *"we measured waste objectively
   and showed monitoring is the wrong instrument for it"* (the negative, better-evidenced), or
   *"we found an edit-admission policy that retains 86% of surviving edits"* (the positive,
   smaller and with an unmeasured counterfactual). The first is the stronger paper; the second is
   the more novel artefact. You can lead with either and put the other second.
3. **How to present the superseded first version.** Superseded, or kept as a documented case study
   in label-induced ceilings. Both are defensible; the second is more useful to other students.

## 5. The one check only you can do

`docs/human_check_sample.md` — twelve windows, half judged stagnant and half productive, drawn
with a fixed seed, with a scoring script. Read the trajectory for each, commit to your own
verdict, *then* compare. It answers the only question the rebuild cannot answer about itself:
does a mechanical definition of progress agree with a person's reading? If it does, the paper
gains a human-checked label set for the price of an hour. If it does not, the rebuild's target
is wrong and every number above it changes — which is worth discovering before submission rather
than after.

## 6. What is still blocked

The machine has had **no network since 2026-09-10**. Three items need it and are otherwise
ready:

* the second Terminal-Bench shard and the 8 remaining SWE-agent shards (would roughly double
  both corpora; the pipeline resumes without recomputation — `scripts/watch_network.py`);
* RedundancyBench (arXiv 2605.29893), whose 24.88% step-level bar is the one published number
  that would let the paper claim a head-to-head win on someone else's benchmark;
* a third corpus (SWE-rebench / OpenHands trajectories) to test whether "direction, not
  idleness" generalises.

## 7. Reproducing in one command each

```powershell
cd research
python scripts/run_rebuild_tests.py            # 11 invariant tests
python scripts/check_rebuild_consistency.py    # cross-artifact agreement + staleness
python scripts/audit_claims.py                 # 28/28 headline claims vs their artifacts
python scripts/audit_summary.py                # 0 mismatches exec summary vs artifacts
python scripts/check_doc_references.py         # every cited artifact exists
python scripts/collect_rebuild_numbers.py      # every headline number, regenerated
```

Everything else is listed in `README.md` and `docs/REBUILD_FINDINGS_V2.md` §6.
