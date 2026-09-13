# Audit of the 12-window human-check proposal against `research/docs`

**Date:** 2026-09-13 · **Auditor:** Muse Spark (AI assistant) · **Scope:** verify every
factual and methodological claim made in the 2026-09-13 "distill + ready-to-go?" answer
against the decision trail in `research/docs`, then record what a session goal can and
cannot still achieve.

**Method:** read every `.md` in `research/docs` end-to-end except the two raw HTML dumps
(`tb2_card.txt`, `nebius_card.txt`, skimmed for schema/licence/scale only) and the cached
`_raw/` / `verify_raw/` / `lit_raw/` corpora (spot-checked). Also read `README.md`,
`TASK_12_WINDOWS.md`, `windows_to_judge.csv`, `main_idea.md` (to §1992),
`research/README.md`, `scripts/make_human_sample.py`, `scripts/score_human_sample.py`,
two annotation cards (one `cards_dense/`, one `cards/`), and probed the runtime
(`python3 --version`, `pip3 list`, artifact existence, one live HTTPS fetch).
Line/section pointers below are to the files as found on disk on 2026-09-13.

## 1. Docs inventory (what was actually read)

| file | lines | status |
|---|---|---|
| `annotation_guide.md` | 116 | read fully |
| `human_check_sample.md` | 55 | read fully |
| `human_check_readable.md` | 1269 | read fully (all 12 transcripts + label rows) |
| `KEY_FINDINGS.md` | 757 | read fully (1–717 then 718–757) |
| `REBUILD_FINDINGS.md` | 213 | read fully |
| `REBUILD_PLAN.md` | 127 | read fully |
| `REBUILD_FINDINGS_V2.md` | 1307 | read fully (1–826 then 827–1307) |
| `GAP_ANALYSIS_AND_PLAN.md` | 358 | read fully |
| `HANDOFF.md` | 152 | read fully |
| `EXECUTIVE_SUMMARY.md` | 131 | read fully |
| `RECON_CORPORA.md` | 211 | read fully |
| `RECON_LITERATURE.md` | 229 | read fully |
| `SUBMISSION_CHECKLIST.md` | 76 | read fully |
| `VERIFY_PARSER_EVIDENCE.md` | 856 | read §§1–3 fully, rest skimmed (regex evidence tables) |
| `research/README.md` | 297 | read fully |
| `AI_ASSISTANCE_LOG.md` | 854 | read §§1–6 + defect list head, rest skimmed |
| `tb2_card.txt` / `nebius_card.txt` | 1062 / 264 | skimmed (dataset scale, schema, licence) |
| `_validation_sample.txt` | 35 | read fully |
| `TASK_12_WINDOWS.md`, `windows_to_judge.csv`, `README.md` | 30 / 13 / 20 | read fully |
| `scripts/make_human_sample.py`, `scripts/score_human_sample.py` | 121 / 88 | read fully |
| `research/data/annotations/tb2/cards_dense/d_tb2_build-pov-ray__oboi8x8_24.md` | 76 | read fully |
| `research/data/annotations/tb2/cards/tb2_compile-compcert__qeLnFSj_60.md` | 74 | read fully |

Not re-read line-by-line: `award/` (rules pages, already summarised in log §1 and checklist),
`lit_raw/` / `verify_raw/` / `_raw/` caches, `_recon_detectors_raw.md` (867 lines, used only
via the verified `RECON_LITERATURE.md` synthesis).

## 2. Claim-by-claim audit of the prior answer

Verdicts: **CONFIRMED** = text supports the claim as stated; **NUANCED** = true but needs
a version/scope qualifier; **CORRECTED** = prior wording was imprecise, fix recorded here.

### 2.1 v1 (judged-label study)

| prior claim | verdict | evidence |
|---|---|---|
| ~1,500-trajectory sample, 100,848 steps, 45 tasks, 9 scaffolds, 1,198 windows, 88.1% cross-round binary agreement, κ=0.70 | NUANCED | `research/README.md` "What the study found" and §"Reproducing" confirm 1,500 / 45 / 9 / 100,848 and 1,198 windows, 88.1%, κ=0.70. But `KEY_FINDINGS.md` §1 describes an **earlier frozen run** (654 windows / 81 trajectories). Both numbers exist: `tb2_final` = 654, `tb2_v5`/`tb2_v6` = 1,198. `KEY_FINDINGS.md` §3 "Which run is authoritative" names `tb2_v5` as authoritative. Prior answer should have said "1,198 (v5; earlier draft reported 654)". |
| 56 AI readers | NUANCED | `AI_ASSISTANCE_LOG.md` §5 says 56 subagent readers (6+6+18+32 + follow-ups = 88 runs, 61 files). `KEY_FINDINGS.md` §4b counts **61 files, 1,785 rows**, median peer agreement measured over **59 readers**; §4 item 11 discusses a filename collision (`labels_refine_20` + `20b`). "56 readers" is the design count; "59–61 files/readers on disk" is the as-built count. Both true; cite as-built when discussing agreement. |
| Winner semantic redundancy 0.775 global, 0.633 within-run vs 0.644 position; evidence 0.587; workspace weakest | CONFIRMED (v5) | `research/README.md` "What the study found": 0.775 / 0.633 / position 0.644 / evidence 0.587 / repetition 0.608 / verification 0.558 / workspace 0.557. Note `KEY_FINDINGS.md` §1 quotes an older run (0.742 / 0.678 / 0.620 / 0.583 / 0.562 / 0.554). The ranking (redundancy > evidence > repetition > verification ≈ workspace) is stable across both; quote v5 numbers and name the run. |
| Alarm: 53% of 68 episodes at 17% FA, zero median latency; 56% at 18% nested | CONFIRMED | `research/README.md` "What the study found" + `KEY_FINDINGS.md` §0 table (36/68 = 53%, 17% per-window FA, 37% per-region, latency 0; nested 56% at 18%). Prior answer correctly called it warning-grade, not stop-grade. |
| Redaction drives disagreement: 0 placeholders 5.3% ties, 1–5 → 23.4% | CONFIRMED | `KEY_FINDINGS.md` §4 item 4 table: 0→5.3%, 1–5→23.4%, 6–15→18.0%, 16+→4.7%; corrected corpus rate 25.5% obs (29.7% per-traj), not the earlier 22.4%. Prior answer's "25%" shorthand is acceptable with this pointer. |
| Boundary flag unusable, detail-field defect, card-control-byte defect, rank-assignment ambiguity, strided-vs-contiguous manifest mismatch | CONFIRMED | All in `KEY_FINDINGS.md` §§4–7: boundary 0.00–1.00 across readers (median 0.11, 102/1206 cards disputed) and dropped at adjudication; detail recorded for 116/116 STAGNANT but only 12/27 DONE_REDUNDANT, 0/10 BLOCKED; 85/1457 cards had control bytes (NUL on `extract-elf__rUUxEg5_20`), fixed by `clean_cards.py`; assignment stride-18 vs documented contiguous blocks; readers keyed by `card_id` so gold unaffected. |

### 2.2 v2 (mechanical-label rebuild)

| prior claim | verdict | evidence |
|---|---|---|
| 41,429 trajs / 1,256,295 steps / 1,258 tasks / 236,137 mechanical step labels / 363,707 window labels | CONFIRMED | `REBUILD_FINDINGS_V2.md` §1 table + §0 summary; `research/README.md` rebuild §2 header. TB2 = 14,750 action-carrying trials (2,487 crash-only excluded); SWE-agent = 26,679 trajs. |
| Editor footer on 95.8% of edit steps; no-op 19.9% | CONFIRMED | `REBUILD_FINDINGS_V2.md` §1 ("95.8% of edit steps", "19.9% of measurable edits"); `research/README.md` rebuild §2. |
| Dead-end 19.1% (45,122 edits, 1.8/run) + revision 65.2%, kept 15.7%; coarse 84.3% must not be quoted as waste | CONFIRMED | §2.1 tables + `HANDOFF.md` §1 + `EXECUTIVE_SUMMARY.md` "The measurement". Prior answer correctly warned against the 4× overstatement. |
| Flat across quarters 84.2/85.1/85.5/83.6 | NUANCED | §2.1: those four shares are the **coarse** waste rate by run quarter, not the dead-end-only rate. Wording must say "coarse waste share flat" — the "no stagnation phase" inference is the authors', and it is about the background rate, not about episode clustering within a run (which §2.1 explicitly says the flatness does not rule out). |
| Split-half ρ=+0.56, per-run var 3.82× binomial | CONFIRMED | §2.1 (ρ=+0.560 sd 0.003 over 20 splits; 3.82×). |
| Within-instance solved 30.0% surviving vs failed 19.8%, p=1.9e-9, 263 contested instances | CONFIRMED | §2.3 table (Wilcoxon p=1.9e-9, 263 instances, 9,849 runs). The adjacent `on_target 0.576 vs 0.620 p=3.3e-4` row in the same table is **RETRACTED** (see §2.4 below) — prior answer correctly separated the surviving row from the withdrawn row. |
| Quiet predictable ~0.82, direction ~0.54 single / ~0.59 fitted, future-aware +0.005–0.006 | CONFIRMED with mandatory hedge | §2.4 step-task table (`y_nochange` 0.803, `y_noop` 0.823, `y_wasted` 0.539 vs position 0.536); §2.27 ablation (`ALL` 0.599 vs POS 0.543 single-cell) + stability grid (`ALL` +0.064±0.011 over POS 0.526, 12/12 cells positive; NOV +0.019 12/12; VER +0.010 10/12, sub-threshold). Prior answer's "weakly predictable, a third of idleness" matches the authors' own retirement of "unpredictable" (§2.27: '"essentially unpredictable" … retired'). Never quote 0.539 without its 0.599/0.590 fitted companion. |
| Edit structure 0.732 (within-task 0.729, sd 0.0006); small edits wasteful 12.6%→34.8% | CONFIRMED | §2.4 (`edit_structure.json`; seed-stability 0.7316 sd 0.0006); single-feature size AUC 0.706. Admission: refuse worst 40% → retain 85.8% survivors (learned) vs 79.6% size rule vs 60% random (`admission_cost.json`); learned loses to size rule at matched admission rate (0.225 vs 0.253). Prior answer reported both — correct. |
| Field detectors at/near chance; study wins 0.622/0.821 (grid 0.632±0.007 / 0.849±0.013) | CONFIRMED | §2.14 (`detector_families.json`: exact_burst 0.546/0.677, ngram 0.530/0.652, tfnorm 0.527/0.635, openhands5 0.515/0.663, agentstop_shape 0.663 run-level vs study 0.749; study 0.622/0.821) + §2.28 stability (frozen cells at/below grid minimum — win understated, not lucky). Caveats recorded: AgentStop logprobs absent (feature-shape only); wasted-edit precision uninformative at 0.98 base rate. |
| All six scaffolds transfer >0.60, mean degradation −0.018 | CONFIRMED | §2.15 `scaffold_transfer.json` (0.665–0.866; prevalence 0.260 mini-swe-agent → 0.854 openhands on same tasks). |
| Same families re-scored: NOV 0.660→0.956, STALL 0.688→0.877, REP 0.588→0.834; labels disagree 43.3%, mutual AUC 0.594 | CONFIRMED | §2.6 `gold_crosscheck.json` (386 binary gold windows matched by traj_id+t) + §2.13 `label_cost.json` (43.3% disagreement; flip-rate table: ~31% flips needed to explain 0.688 as noise vs 12–23% reader disagreement — noise explanation rejected). Behavioural signature of the 131 judged-PRODUCTIVE-but-quiet windows: 1.168 edits/window, read-frac 0.047, 0.066 new entities vs 0.238 both-productive (`label_signature.json`) — read-vs-edit hypothesis falsified, novelty gap reported instead. Prior answer summarised this correctly. |

### 2.3 Retractions and open gaps the human check inherits

| item | status in docs | consequence for the 12-window task |
|---|---|---|
| `on_target` "failed localise better (0.620 vs 0.576)" | **WITHDRAWN** as construct-validity failure (§2.29 `wrongness.json` + `metric_artifact.json`; annotated in HANDOFF/GAP/EXEC_SUMMARY). Independent gold target reverses sign (0.477 vs 0.407; ever-touched-gold 0.982 vs 0.671, Δ+0.311, robust in every patch-width stratum). Three mechanism hypotheses falsified; mechanism open. Quotable form is the bounded lever: localisation caps at 30.9% of failures. | Do not let the human check relitigate localisation. It tests quiet-vs-sensible, not file choice. |
| Sequential "0 false alarms 1–20%, precision 1.000, latency 0" | **CIRCULAR, retired** (§2.9; GAP §6.1; HANDOFF §2 "do not claim"). Target = "k consecutive quiet windows" and detector = same → oracle's numbers. Non-circular dead-end sequential task degenerate (event in 86.6% runs; recall 1.000 with FAR 1.000; §§2.16–2.17, 2.21–2.22). **G5 stays open.** | Human-vs-quiet agreement does **not** validate any alarm. Prior answer's label-vs-detector separation is required, not optional. |
| Early failure prediction 0.878 (SWE-agent 10%) vs 0.637 max (TB2) | **Per-corpus only, do not generalise** (§2.16; HANDOFF §2). Early-checkpoint enrichment (97.7% failure at f=0.10) partly explains the high cell. | Do not cite a single early-prediction number in the human-check brief. |
| Waste-alarm "precise but useless" (precision 0.944, FAR 0.009, median alarm at 100% elapsed, 11.1% before halfway) | CONFIRMED (§2.22 `waste_alarm.json`). Absolute threshold (dead-end share >0.5 after ≥3 edits), train-calibrated, held-out applied. | Supports the "measurable, outcome-relevant, not early-actionable" spine; not a substitute for the human check. |
| Dead-end timing null (+0.009 p=0.103 matched), recovery null (next-edit indistinguishable, p=0.28; new-file rate −0.115 vs +0.097 control), size-artefact bounded (single-line stratum Δ+0.063 p=6.8e-3 vs +0.174 overall), cost saturation (848× cost, success 0.143–0.461; dearest decile among worst), dead-end variance (task 24.8%, model 0.6%, residual 75%) | CONFIRMED (§§2.17–2.20, 2.23–2.26) | The docs already close the four sides the human check cannot: rate not phase, not diagnostic, not timing-dependent, not early-detectable. The check only tests whether "quiet" reads as "stalled" to a person. |
| Literature positioning | CONFIRMED | `RECON_LITERATURE.md` §§1–5 is the load-bearing synthesis: "wrong not lost" is prior art twice (Coherence Collapse 2603.24631: 60–69% reach+edit correct fn yet fail; Majgaonkar ICSE26 2511.00197 Finding 7); within-task reversal design is prior art (Beyond Resolution Rates 2604.02547); TRIM 20.0% vs our 19.1% is different-object proximity that must be stated; detection bar is soft (AgentStop 0.6–0.7; Who&When 53.5%/14.2%; Failure-as-Process 82% prec / 18.2% rec; RedundancyBench 24.88%). Novelty scoped to the self-referential metric defect + bounded lever. Prior answer's field list (Zombie, FailFast, TraceProbe, AgentStop, RedundancyBench) is consistent; cite the recon doc's IDs, not memory. |
| Corpora reconnaissance | CONFIRMED | `RECON_CORPORA.md`: editor footer is SWE-agent-only (106 hits on 5 rows vs 0/360 SWE-smith rows) — workspace features won't transfer; ranked fetch plan (thoughtworks 15k balanced 3-scaffold panel first, then OpenHands 67k, Nemotron Terminus-2, etc.); success-only bias flags; licence/access table. Relevant because the 12 windows are TB2-only. |

### 2.4 Workflow claims re-verified

| prior claim | verdict | evidence |
|---|---|---|
| n=12 underpowered for estimation; Wilson CI on 9/12 ≈ 46–91%; need ~150–200 for κ CI 0.10 | CONFIRMED as methodology (external stats, consistent with docs' own caution: "Twelve windows cannot validate 236,137 labels" in `human_check_sample.md`; baseline bootstrap [0.675,0.848] "wide enough to contain every alternative" in GAP §2/G1). Sample is fixed-seed (20260913), 6 stored-STAGNANT + 6 stored-PRODUCTIVE from 386 co-labelled windows, on-sample stored-vs-mechanical 66.7% vs 66.9% population (AUC 0.669) — `human_check_sample.md` table + `make_human_sample.py` ll.49–56. Enrichment (50/50 vs natural ~29% stagnant / 39–52% quiet) confirmed; must report marginals + per-class stats. |
| Blinding broken by docs | CONFIRMED | `human_check_sample.md` table prints stored + mechanical for all 12; `human_check_readable.md` prints both under every transcript; `results/rebuild/human_check_sample.csv` carries `binary`, `mech_stagnant`, and ~100 feature columns; `windows_to_judge.csv` itself is clean. `TASK_12_WINDOWS.md` "commit before looking at anything else" + "background, to read after" is the right rule but names the leaking file as background. Fix = blind packet + sealed key + randomised order (current order sorted by task/run/t). |
| Binary collapse loses BLOCKED/DONE/REGRESSION/UNCERTAIN | CONFIRMED | Codebook §3–4 (6 labels + ordering rule §4.2 blocked-first); `KEY_FINDINGS.md` §4 items 2–3 (20 PRODUCTIVE\|DONE_REDUNDANT held out vs 12 agreed DONE_REDUNDANT surviving; 12 BLOCKED disputes from 5 trajs; 26 PRODUCTIVE-vs-STAGNANT variation disputes incl. `break-filter-js-from-html`); `score_human_sample.py` accepts stalled/stagnant/s/progress/productive/p (+ true/false/yes/no/1/0) and silently drops anything else (returns None → excluded). Instructed UNCERTAIN + confidence + reason required. |
| Cards self-contained but heterogeneous; after-window present; outcome leaks; redaction matters | CONFIRMED | Both cards read contain Task + Before + WINDOW + After + "Your label" block. Dense card (35-step traj, obs prose) vs sparse card (71-step traj, `say="Executed shell call_…"` boilerplate, `$4x` placeholders). Both show trajectory length + final reward; readable doc adds `run solved: True/False`. TASK's "steps leading up + window" omits After. Redaction rule confirmed by §4-item-4 tie-rate table. |
| `score_human_sample.py` reports points only, no CI/difference test | CONFIRMED | ll.59–84: raw agreements + `cohen_kappa_score` (sklearn) + `human_check_scored.json`; no interval, no paired difference, no missing-data accounting beyond exclusion. |
| Label-vs-detector distinction | CONFIRMED | `y_stagnation` quiet-share >0.5 (`make_human_sample.py` l.46) is the *target*; monitors/alarms (`analyse_windows.py`, `analyse_sequential.py`, `waste_alarm.json`) are separate. Docs never claim the 12 windows validate an alarm (HANDOFF §5: "does a mechanical definition agree with a person's reading?"). |

## 3. Decision trail (why each design choice is the way it is)

- **Pre-registration:** `REBUILD_PLAN.md` froze target (Phi(t)/Y(t) verified-progress-in-K), blinded-primary + verification-ceiling, and all four outcome branches *before* implementation. `REBUILD_FINDINGS.md` then reported the falsification (79% runs no success event; exit-0 anti-correlated 3.7 solved vs 7.3 failed; joint model +0.002 p=0.93; MiniLM 0.697 < 0.775) and converted the plan into a ceiling claim — later itself superseded by V2 §3 table.
- **Gap-ranked rebuild:** `GAP_ANALYSIS_AND_PLAN.md` G1–G10 (evidence 50× too small; judgement labels; between-task confound; clock signal r=0.518 in 93% runs; no low-FAR calibration; no field comparison; ceiling overreach; no objective-target test; no sequential framing; no cost model) → R1–R5 bets → 10-phase plan. §6.1–6.4 record what closed, what stayed open (G5 retraction, on-target retraction), and the Route-A/B recursion (A: observables limit +0.006 future-aware; B: calibration circular → spine becomes the negative + edit-admission lead).
- **Human authority reserved:** `HANDOFF.md` §§4–5 (target / headline / first-version framing are the students', not the agent's; human spot-check is "the one check only you can do"); `SUBMISSION_CHECKLIST.md` §§2–4 (cover, acknowledgement, AI disclosure + chat records, integrity declaration, plagiarism report; five self-verifications incl. "open 20 cards and report your agreement").
- **Parser evidentiary standard:** `VERIFY_PARSER_EVIDENCE.md` (4,000 runs / 102,617 obs; every regex grounded in literal substrings) + `_validation_sample.txt` (1,200 runs / 31,440 obs; 267/267 verdict-shaped resolved, 0 misses). The VER-channel null (§2.27) therefore rests on a measured parser, not an assumed one.
- **Annotation protocol lessons that bind the 12-window rerun:** explicit `card_id` lists not rank ranges; `clean_cards.py` + `audit_cards.py`; `detail` mandatory per non-PRODUCTIVE label with mechanism-specific BLOCKED members; strict boundary definition; readers blind to each other's files; stratify assignment by trajectory (`KEY_FINDINGS.md` §§4,7).

## 4. What the prior answer got right, and the two wordings to retire

- Right: two-number framing (codebook fidelity vs mechanical validity), falsification-not-validation at n=12, blind-packet/key split, two-pass-or-two-rater fix for the conflated verdict, redaction/confidence/reason rules, after-window/outcome-leakage instructions, pre-registered CIs + difference test, detector-vs-target separation, field context.
- Retire: (a) "1,198 windows" without "(v5; v1-final 654)"; (b) "waste flat across quarters" without "(coarse rate)"; (c) any "unpredictable" without "weakly (+0.064±0.011), a third of idleness". All three are corrected in §2 above and already retired in V2 §§2.27/3.

## 5. Feasibility of a session goal to "address all of them and get real results"

**Verdict: feasible for instruments + pre-registration + reproducibility; blocked for the
two human numbers themselves. Do not scope a goal as "produce the agreements" — scope it as
"make the pilot airtight so one hour of human time produces auditable results".**

### 5.1 Machine-feasible in this session (no human required)

1. Blind packet: randomised 12-card order, judge-view CSV/MD with no `binary`/`mech_stagnant`/quiet-share/reward/solved columns, sealed key file + SHA. Source: `gold_matched_windows.parquet` + `human_check_sample.csv` + `cards_dense/` + `cards/`. (~1 h)
2. Judge sheet v2: one page (folk definition + codebook §4 ordering + 5 worked distinctions + after-window/outcome/redaction/boundary rules + allowed labels + confidence + step-cited reason). (~1 h)
3. Scoring upgrade without new deps: extend `score_human_sample.py` (or add `score_human_sample_ci.py`) with Wilson CIs, kappa CIs (bootstrap or analytic SE), paired difference (McNemar/exact + bootstrap), per-class precision/recall, missing/uncertain accounting, and a `--check-blind` guard that refuses to score until all 12 filled. Must be **stdlib-only**: runtime here is `python3 3.9.6` with no pandas/sklearn/numpy (`pip3 list` = altgraph/macholib/pip/setuptools only), so the upgrade cannot import pandas/sklearn; implement Wilson + bootstrap with `csv`/`json`/`random`/`math`, or vendor a minimal kappa. (~2–3 h incl. self-tests on synthetic sheets)
4. Power note + pre-reg: one-page `human_check_prereg.md` (enriched 50/50; estimands; Wilson widths at n=12; decision rule: falsify if systematic disagreement, otherwise "no gross invalidation"; ban on "validated at X%"). (~1 h)
5. Provenance: judge log template (start/end, peek declaration, prior exposure) + immutable completed-CSV convention. (~30 min)
6. Optional (only if time): expanded pool (e.g. n=50 stratified reserve from the 386) with identical blind packaging, so a second hour upgrades precision without redesign. Needs parquet/feature access — blocked on deps (see §5.3); cards-only expansion is the fallback.

### 5.2 Human-blocked (a goal must NOT claim these)

- The 12 verdicts themselves, the second-rater ceiling, and any sentence of the form "human-mechanical agreement is X [CI], human-stored is Y [CI], therefore validated". Those require 40–60 min of independent human reading plus, ideally, a second human. An autonomous goal that fills the sheet with model judgements would **fabricate the very independence the instrument exists to create** and must be explicitly forbidden in the goal text.
- Consequence: "real results" in-session = **verified instruments + frozen pre-reg + passing self-tests + blind packet ready**, not the two agreement numbers. The agreements arrive only after a person judges.

### 5.3 Environment constraints checked 2026-09-13

- Artifacts present: `gold_matched_windows.parquet`, `human_check_sample.csv`, `cards_dense/` (1,457 cards), `cards/`, all `results/rebuild/*.json` heads listed (alignment, step_task, routeA, detector_families, seed_stability, scaffold_transfer, etc.).
- Toolchain gap: no pandas/pyarrow/sklearn/numpy on `python3`; `research/requirements.txt` absent at that path. Parquet re-derivation and sklearn-kappa re-runs are therefore **not runnable here without installing deps** (network is up — `arxiv.org/abs/2603.24631 → 200` — so `pip install` is possible but changes the reproducibility story; prefer stdlib-only additions and leave the frozen pipeline untouched).
- No credential or sandbox blockers for writing under the workspace (`research/docs/` writable). Nothing in this plan needs the network except optional dep installs and literature spot-checks.

### 5.4 Recommended goal (if commissioned)

> Objective: "Deliver a blinded, pre-registered 12-window human pilot that is ready for
> one hour of independent human judging: randomised blind packet + sealed key, v2 judge
> sheet, stdlib-only scoring with Wilson/kappa-CIs + paired difference + blind-completeness
> guard, one-page pre-reg, provenance template, and self-tests; explicitly forbidding any
> model-filled verdicts."

- Deliverables: `research/docs/human_check_blind/` (packet + key + SHA), `research/docs/judge_sheet_v2.md`, `research/scripts/score_human_sample_ci.py`, `research/docs/human_check_prereg.md`, `research/docs/human_check_provenance_template.md`, this audit as `research/docs/audit.md`, all self-tests passing.
- Stop rule: goal completes when the packet scores end-to-end on synthetic sheets and a fresh reader could judge without ever seeing a label — not when agreements exist.
- Max rounds: 3–4 autonomous rounds suffice; more would idle on the human block.
- Risk: expanding beyond n=12 or re-tuning detectors in the same goal reintroduces the deps gap and scope creep; keep the goal to the pilot.

*End of audit.*
