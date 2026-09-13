# Coding-agent stagnation study — research package

This directory holds a complete, reproducible study of one question:

> **Which observable signals let an online, reference-free monitor tell that a coding agent has
> stopped making task-relevant progress?**

It was produced for the S.-T. Yau High School Science Award (Computer Science), 2026, by
Qichen Tong and Ke Chuang Jiang, with an autonomous AI agent doing the implementation,
annotation logistics and drafting (see `AI_ASSISTANCE_LOG.md`).

## Start here

| If you want to… | Read |
|---|---|
| understand the result in plain language | `docs/KEY_FINDINGS.md` |
| **read the whole rebuild in two minutes** | **`docs/EXECUTIVE_SUMMARY.md`** |
| **read the rebuild: objective labels, 41k trajectories, the new headline** | **`docs/REBUILD_FINDINGS_V2.md`** |
| **write the paper: claim → artifact → what it does and does not support** | **`docs/HANDOFF.md`** |
| **see what was wrong with the first version and what fixed it** | **`docs/GAP_ANALYSIS_AND_PLAN.md`** |
| **do the one human check the rebuild cannot do for itself** | **`docs/human_check_sample.md`** |
| see what must still be done before submitting | `docs/SUBMISSION_CHECKLIST.md` |
| check how the labels were defined | `docs/annotation_guide.md` |
| know what the AI did, and where it went wrong | `AI_ASSISTANCE_LOG.md` |
| read the paper | `../paper/main.pdf` (source: `../paper/main.tex`) |
| audit a specific number | `results/final/tb2_final/paper_numbers.json` and the table it came from |
| audit a rebuild number | `results/rebuild/rebuild_numbers.flat.json` |

## Layout

```
research/
├─ src/                     monitor implementation (~2,000 lines, stdlib + NumPy)
│   ├─ loaders.py           Terminal-Bench 2.0 and SWE-agent trajectory loaders
│   ├─ normalize.py         scaffold-independent action canonicalisation
│   ├─ evidence.py          entity and verification-state extraction from tool output
│   ├─ features.py          the six online feature families
│   ├─ monitors.py          baselines, channel monitors, learned monitors, alarm policy
│   ├─ run_config.py        the monitor zoo (baselines B*, channels C*, learned L*)
│   ├─ evaluation.py        window metrics and per-run alarm metrics
│   └─ alarm_eval.py        per-window alarm metrics with tolerance and coverage
├─ scripts/                 one script per pipeline stage, each writing a frozen artifact
├─ data/
│   ├─ raw/                 downloaded corpora (Terminal-Bench 2.0 shard, Nebius shards)
│   ├─ processed/tb2/       analysis sample, window features, semantic representations
│   └─ annotations/tb2/
│       ├─ cards_dense/     1,457 annotation cards (task, window, context)
│       ├─ labels_*.csv     every reader's raw labels (61 sessions)
│       ├─ adjudicated.csv  the gold labels used in the paper
│       ├─ agreement.json   label stability and reader calibration statistics
│       └─ gold_regions.json merged stagnant/productive step ranges per trajectory
├─ results/
│   ├─ exploratory/         data-quality profiling and trace examples
│   └─ final/
│       ├─ tb2_final/       the run the paper reports: metrics, scores, ablations, figures
│       ├─ summary_tb2.json corpus statistics
│       └─ runtime.json     measured monitor cost
├─ figures/                 figures as generated
└─ docs/                    codebook, findings, checklist, verified literature, award rules
```

## What the study found (one paragraph)

Activity is not progress, and novelty is not progress either. Across 1,500 Terminal-Bench 2.0
trajectories (45 tasks, 9 scaffolds, 100,848 steps) with 1,198 independently annotated windows
(88.1% cross-round binary agreement, κ = 0.70), the strongest single family of runtime signals is
**rolling semantic redundancy** of successive steps (ROC-AUC 0.775 globally, 0.633 within a run).
**Task-grounded evidence** — weighting newly observed files, symbols and error signatures by whether
they concern the task statement — does **not** beat it on its own (0.587, paired difference −0.193
with an interval excluding zero), and only reaches parity in combination (0.688). **Exact
repetition** (0.608), **verification deltas** (0.558) and **workspace churn** (0.557) are all
significantly worse, which is the empirical case against the monitor a practitioner reaches for
first. Inside a single run every monitor falls to AUC 0.55–0.68, close to a trivial "how far into
the run are we" baseline (0.644), so most of the apparent accuracy is between-run. The labels are
better read as *episodes* than as windows: 68 sustained stall episodes (median 16 steps), and at
that unit a monitor calibrated on the run's own opening 15% separates 83% of them from the same
run's productive work where a run-position proxy separates 12 of 36. That yields an alarm — smooth
over 3 windows, alarm above μ + 1.0σ — that flags 53% of stall episodes at a 17% per-window false
alarm rate with zero median latency, and 56% at 18% under a nested protocol that selects every
parameter on held-out runs. Good enough to justify surfacing a warning, not good enough to justify
stopping a run.

## Reproducing

```powershell
cd research
python scripts/build_dataset.py --corpus tb2 --n 1500 --out data/processed/tb2 --windows 10 --stride 3 --seed 11
python scripts/embed_semantics.py --corpus tb2
python scripts/build_gold.py --corpus tb2
# the paper's numbers come from this run directory; ./paper/generated_tb2.tex is exported from it
python scripts/run_experiments.py --corpus tb2 --w 10 --w-extra 20 --folds 5 --out results/final/tb2_v5
python scripts/run_ablation.py --run results/final/tb2_v5 --folds 5 --out results/final/tb2_v5/ablation.json
python scripts/run_cross_scaffold.py --run results/final/tb2_v5 --out results/final/tb2_v5/cross_scaffold.json
python scripts/compare_monitors.py --run results/final/tb2_v5 --out results/final/tb2_v5/paired_comparisons.json
python scripts/make_figures.py --run results/final/tb2_v5 --corpus tb2 --outdir ../paper/figures
python scripts/make_regime_figure.py --run results/final/tb2_v5 --out ../paper/figures/fig_regimes_tb2_w10.png
python scripts/export_results_tex.py --run results/final/tb2_v5 --corpus tb2 --out ../paper/generated_tb2.tex
python scripts/export_ablation_tex.py --run results/final/tb2_v5 --out ../paper/ablation_macros.tex
python scripts/verify_all.py
cd ../paper && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

Everything except the annotation step runs offline once the corpora are in `data/raw/`. The
monitor itself needs only the standard library and NumPy; it costs
`results/final/runtime.json` → 0.33 ms per step to build a window's features and 3 µs to score
it.

## The rebuild attempt (2026-09-11)

A follow-up set out to convert the negative result into a positive one. **Its two central premises
were tested and both failed**, which is recorded in `docs/REBUILD_FINDINGS.md` and reported in the
paper's discussion:

* `docs/REBUILD_PLAN.md` — the plan, frozen before implementation, with pre-registered
  interpretations of every possible outcome.
* `docs/REBUILD_FINDINGS.md` — what was done, and what it found.
* `scripts/secure_assets.py`, `scripts/secure_wordvecs.py` — cache a real encoder
  (all-MiniLM-L6-v2, 183 MB) and word vectors (GloVe, 134 MB). **Both load with the network off**,
  so the pipeline needs no internet.
* `scripts/probe_outcomes.py`, `probe_target_density.py`, `probe_target_variability.py`,
  `probe_base_rates.py` — four probes establishing that this release contains almost no objective
  progress signal (79% of runs have none).
* `scripts/test_embedding_upgrade.py` — the controlled representation swap: v1's exact semantic
  features over bag-of-words (0.775) versus a real encoder (0.697).

## The rebuild, round 2 (2026-09-12): `src/agentstall/`

The "no objective signal exists" conclusion above was true of Terminal-Bench's release alone.
A second rebuild mines **objective** progress labels out of editor telemetry in both corpora and
rebuilds the study on 41,429 trajectories / 1,256,295 steps. Read
`docs/REBUILD_FINDINGS_V2.md`; the gap analysis that motivated it is
`docs/GAP_ANALYSIS_AND_PLAN.md`.

Headlines: **19.1% of edits are unambiguously wasted** — their lines never reach the agent's own final patch *and* no later action touches that file again (45,122 edits, 1.8 per run). A further 65.2% are revision, so the coarse 80% figure must not be quoted as waste; waste is
evenly spread through the run yet is a stable per-run property (split-half ρ = +0.56); it is
outcome-relevant within the same instance (30.0% vs 19.8% surviving edits, *p* = 1.9 × 10⁻⁹); and
it is **unpredictable online** (AUC 0.539) while quietness is highly predictable (AUC 0.823) — a
future-aware upper bound shows the limit is the observable channel, not the label.

Three further results carry the paper:

* **An edit's own structure predicts its fate better than its context does** (AUC 0.732,
  within-task 0.729, versus 0.60–0.69 for the preceding window), and the strongest single
  signal is free: **small edits are the wasteful ones** (survival 12.6% at one line rising to
  34.8% at eleven or more). So the actionable intervention is *refuse the edit*, not stop the
  run — and refusing the worst 40% by the learned model retains 85.8% of all surviving edits
  against 60% for refusing at random.
* **Head-to-head, the field's shipped detectors lose.** Reimplemented from their descriptions and
  run on identical rows and folds, OpenHands' five production stuck patterns, an n-gram cycle
  guard, an exact-repetition guard and a TF-Norm redundancy surrogate all sit at or near chance,
  while this study's features reach 0.62 / 0.82 / 0.75 on the three tasks.
* **The number is not a sampling artefact.** Window length, stride and feature form were swept on
  both corpora: smooth curves, broad maxima, the published setting within 0.021 of its own
  optimum, and a 6× change in stride worth at most 0.006. Every headline fit was repeated under
  five fold seeds (sd 0.0001–0.0010), and **all six scaffolds transfer above 0.60 with mean
  degradation −0.018** — a held-out scaffold is not a held-out world.
* **The waste label is not just counting revisions.** The label is defined against the agent's own
  patch, which a reviewer will object to. Measured: single-edit runs, where revision is
  impossible, still waste 64%; counting every superseded edit as progress lowers the pooled rate
  from 0.843 to 0.788; and the within-instance outcome signal comes **entirely** from edits that
  were never revisited (Δ +0.157, *p* = 6.9 × 10⁻¹³) while superseded edits carry none
  (Δ +0.049, *p* = 0.078).

`docs/human_check_sample.md` is the instrument for the one check only a person can do.

The new package and its stage scripts:

| stage | script | artifact |
|---|---|---|
| per-step tables from both corpora | `scripts/build_step_table.py` | `data/processed/steps/{tb2,nebius}/` |
| online window features, raw + two causal stationary forms | `scripts/extract_windows.py` | `data/processed/windows/{tb2,nebius}/` |
| monitor zoo, between/within decomposition, calibration | `scripts/analyse_windows.py` | `results/rebuild/<corpus>_w10/analysis.json` |
| wasted work vs the final patch | `scripts/analyse_alignment.py` | `results/rebuild/alignment.json` |
| step-level prediction of waste | `scripts/analyse_step_task.py` | `results/rebuild/step_task.json` |
| run-level waste, temporal profile, opening prediction | `scripts/analyse_waste_runs.py` | `results/rebuild/waste_runs.json` |
| label-vs-observable probes, future-aware ceiling | `scripts/analyse_routeA.py` | `results/rebuild/routeA.json` |
| cross-corpus transfer | `scripts/analyse_transfer.py` | `results/rebuild/transfer.json` |
| window-length / stride / feature-form sweep, both corpora | `scripts/analyse_capacity.py` | `results/rebuild/capacity_{nebius,tb2}.json` |
| head-to-head vs the field's shipped detectors | `scripts/analyse_detector_families.py` | `results/rebuild/detector_families.json` |
| the edit's own structure as a predictor | `scripts/analyse_edit_structure.py` | `results/rebuild/edit_structure.json` |
| revision-vs-waste confound, measured | `scripts/analyse_self_reference.py` | `results/rebuild/self_reference.json` |
| independent re-derivation of the line comparison | `scripts/verify_extraction.py` | `results/rebuild/extraction_verification.json` |
| dead-end vs revision decomposition | `scripts/analyse_dead_end.py` | `results/rebuild/dead_end.json` |
| is dead-ending a task or agent property | `scripts/analyse_dead_end_variance.py` | `results/rebuild/dead_end_variance.json` |
| what the waste costs in tokens and dollars | `scripts/analyse_cost.py` | `results/rebuild/cost.json` |
| how much of the old 0.78 was the label | `scripts/analyse_label_cost.py` | `results/rebuild/label_cost.json` |
| what one wasted edit costs the run | `scripts/analyse_dead_end_cost.py` | `results/rebuild/dead_end_cost.json` |
| is survival an edit-size artefact | `scripts/analyse_size_artifact.py` | `results/rebuild/size_artifact.json` |
| behavioural signature of the label disagreement | `scripts/analyse_label_signature.py` | `results/rebuild/label_signature.json` |
| sequential detection on the objective event (degenerate) | `scripts/analyse_sequential_deadend.py` | `results/rebuild/sequential_deadend.json` |
| an absolute waste alarm, calibrated out of sample | `scripts/analyse_waste_alarm.py` | `results/rebuild/waste_alarm.json` |
| does a wasted edit teach the agent anything | `scripts/analyse_dead_end_recovery.py` | `results/rebuild/dead_end_recovery.json` |
| is file choice predictable early | `scripts/analyse_on_target.py` | `results/rebuild/on_target.json` |
| does dead-end timing matter | `scripts/analyse_dead_end_timing.py` | `results/rebuild/dead_end_timing.json` |
| is the run-level block just run length | `scripts/analyse_detector_value_length.py` | `results/rebuild/detector_value_length.json` |
| does the detector statistic predict the objective outcome | `scripts/analyse_detector_value.py` | `results/rebuild/detector_value.json` |
| which observable channel carries the little wasted-edit signal | `scripts/analyse_channel_ablation.py` | `results/rebuild/channel_ablation.json` |
| is that ablation stable across learner / seed / feature form | `scripts/analyse_channel_ablation_stability.py` | `results/rebuild/channel_ablation_stability.json` |
| is the head-to-head field comparison a lucky hyperparameter cell | `scripts/analyse_field_comparison_stability.py` | `results/rebuild/field_comparison_stability.json` |
| the sustained-event formulation (degenerate) | `scripts/analyse_sustained_waste.py` | `results/rebuild/sustained_waste.json` |
| the coarse waste rate split into revision vs dead end | `scripts/analyse_dead_end.py` | `results/rebuild/dead_end.json` |
| held-out-scaffold transfer | `scripts/analyse_scaffold_transfer.py` | `results/rebuild/scaffold_transfer.json` |
| fold-seed stability | `scripts/analyse_seed_stability.py` | `results/rebuild/seed_stability_{nebius,tb2}.json` |
| edit-admission policy and what it costs | `scripts/analyse_admission.py`, `analyse_admission_cost.py` | `results/rebuild/admission{,_cost}.json` |
| human spot-check instrument (12 windows) | `scripts/make_human_sample.py` | `docs/human_check_sample.md` |
| score the human sheet once filled in | `scripts/score_human_sample.py` | `results/rebuild/human_check_scored.json` |
| render the human check with its transcripts inline | `scripts/enrich_human_sample.py` | `docs/human_check_readable.md` |
| calibrated sequential detection + cost model | `scripts/analyse_sequential.py` | `results/rebuild/<corpus>_w10/sequential.json` |
| reconcile with the first version's judged labels | `scripts/analyse_gold_crosscheck.py` | `results/rebuild/gold_crosscheck.json` |
| every headline number, machine-collected | `scripts/collect_rebuild_numbers.py` | `results/rebuild/rebuild_numbers.json` |
| invariant tests | `scripts/run_rebuild_tests.py` | 11/11 |
| artifact consistency | `scripts/check_rebuild_consistency.py` | passes |
| every headline claim checked against its artifact | `scripts/audit_claims.py` | 28/28 |
| the one-page summary checked against the artifacts | `scripts/audit_summary.py` | 0 mismatches |
| every artifact cited in the docs actually exists | `scripts/check_doc_references.py` | all cited artifacts exist |

The first version's modules (`src/features.py`, `src/monitors.py`, …) and its results
(`results/final/`) are frozen and untouched.

## Checking the result

One command runs every check that guards the paper:

```powershell
python scripts/verify_all.py                                    # everything below, in order
```

and the individual pieces:

```powershell
python scripts/selftest_figure_audit.py                         # proves the figure auditor can detect a real overlap
python scripts/audit_figure_text.py --json results/final/fig_audit.json   # every figure: overlaps, clipping, printed font size
python scripts/check_figure_edges.py                            # no ink at a raster edge (a cropped glyph)
python scripts/check_figures.py --run results/final/tb2_v5      # figure content: series, panels, colour separation
python scripts/measure_label_widths.py                          # label widths in points, to size against panel widths
python scripts/audit_numbers.py                                 # 42 headline macros vs the frozen artifacts
python scripts/verify_paper_pdf.py                              # those values really reach the compiled PDF
python scripts/check_macro_coverage.py                          # exported values the short paper no longer prints
python scripts/compare_dropped_values.py                        # what the 28-page draft printed and this one does not
python scripts/which_run_matches_macros.py                      # which frozen run the paper's macros came from
python scripts/run_tests.py                                     # 11 invariant tests, incl. the online restriction
```

At the time of writing: 11/11 tests pass, 42/42 audited macro values match, the figure audit reports
zero defects across all five figures, no figure has ink at its raster edge, and the compiled PDF is
19 pages and contains every headline value.

The geometric checks are necessary but not sufficient, so they were supplemented by rendering every
figure and every figure page of `main.pdf` to PNG and reading them. That pass is what caught the
defects the measurements could not see: a caption overprinted on a legend, a legend printed across a
coloured bar, a low-contrast annotation sitting on the longest bar, and an axis label trimmed at the
figure edge. Each of those now has a measurement behind it — `check_figure_edges.py` catches the
trimmed label, and the width table from `measure_label_widths.py` is what the axis labels are sized
against.

Two provenance notes that matter when re-running any of this:

* **The paper's macros were exported from `results/final/tb2_v5`**, not from `tb2_final`. Several run
  directories exist (`tb2_v2`…`tb2_v6`, `tb2_dense`, `tb2_cal`, `tb2_cv`, `tb2_round1`), and auditing
  against the wrong one reports dozens of phantom mismatches. `scripts/which_run_matches_macros.py`
  identifies the run a macro set came from by scoring every run on the headline quantities; the
  figure scripts and the number audit default to that run.
* The figures are drawn at the width the paper prints them (6.5 in) with their intended font sizes, so
  the sizes the audit measures are the sizes the reader sees. They are rendered at 400 dpi because
  `\includegraphics` scales them to the text width.

## Integrity notes

* The labels were produced by AI readers applying a written codebook, not by human experts.
  This is stated in the paper's limitations, and the artifact keeps every reader's raw output
  and step-cited justification so the labels can be re-checked by hand.
* No number in the paper is typed by hand: `paper/generated_tb2.tex` is emitted from the frozen
  run by `scripts/export_results_tex.py`, and `scripts/pdf_text_probe.py` verifies that the
  values actually reach the PDF.
* Two claims were withdrawn when the data contradicted them; both reversals are recorded in
  `AI_ASSISTANCE_LOG.md` and reflected in the paper's framing.

### Rebuild-specific integrity notes

* **The rebuild's labels involve no reader at all.** They are read out of the recorded
  trajectories (file line counts, patch text), so the "AI readers judged the labels" objection
  does not apply to `docs/REBUILD_FINDINGS_V2.md`. `docs/human_check_sample.md` exists for the
  one check that still needs a person.
* **Ten defects introduced during the rebuild were found and fixed**, each by a test or by
  checking an internal quantity against an external one, and each is listed in
  `AI_ASSISTANCE_LOG.md` §3 with the number that exposed it. One of them — a target computed
  from the same steps its features described — had produced a spurious 0.95 AUC before it was
  caught; the fix changed every headline number.
* **Nothing was extrapolated to fill a gap.** Where a measurement does not exist the artifact
  records `null` rather than an estimate: Terminal-Bench cannot contribute to the waste
  measurement (its scaffolds do not print file line counts), `y_waste` is `null` there, and the
  findings say so.
* **The artifacts are self-checking.** `scripts/run_rebuild_tests.py` (10 invariant tests,
  including a structural check that no feature reads a target) and
  `scripts/check_rebuild_consistency.py` (cross-artifact agreement and staleness) both pass,
  and every headline number is regenerated from its artifact by
  `scripts/collect_rebuild_numbers.py`.
