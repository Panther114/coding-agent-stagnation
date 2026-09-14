# Notes for the co-author — Xuhao Chen (branch `will/dev`, GitHub `willuhd`)

**Short version: your work is in `main`, byte-for-byte; your branch is untouched; one thing in your
packet needs fixing, and one thing you found broke two of my numbers.**

Written 2026-09-13 ~19:00 CST by the AI agent that has been working on `main`, for **the second
author of the report, Xuhao Chen**. You are not an outside contributor: the pilot you built and the
bug you found are author contributions, and the report's acknowledgement page lists them under
分工说明 (division of labour) for that reason. If someone *outside* the two authors judged the 12
windows, that one fact belongs in 来自他人的帮助 instead — see the end of this file.

## Why there is no merge commit

`will/dev` and `main` have **unrelated git histories** — your branch starts from its own
`Initial commit` (09:31) taken from this repository, so git sees two different trees with no common
ancestor, and `git diff main...origin/will/dev` refuses ("no merge base"). Merging would have meant
resolving ~2,600 paths as add/add conflicts across a folder restructure, so instead I identified
exactly what your branch *adds* and copied those files across, verifying each one against your blob:

```powershell
git restore --source=origin/will/dev -- <path>
git hash-object <path>                      # must equal
git rev-parse origin/will/dev:<path>
```

(A first attempt piped `git show` through `Set-Content -NoNewline`, which silently collapsed every
file to a single line. The per-file hash comparison is what caught it. Worth knowing.)

## What came across

| your thing | where it now lives | checked how |
|---|---|---|
| Blinded human pilot packet (12 cards, sealed key, `SHA256SUMS`, packet, README) | `research/docs/human_check_blind/` | all 18 files verified identical to your blobs; sealed-key chain re-verified (see below) |
| `make_human_blind_packet.py`, `score_human_sample_ci.py` | `research/scripts/` | `--selftest` passes **5/5**; a full re-run reproduces `human_check_blind_scored.json` with **zero differences** |
| Pilot result | `research/results/rebuild/human_check_blind_scored.json` | identical to yours |
| R1/R2 results | `research/results/exploratory/{r1_misfire,r1_guard_sweep,r2_cost_census,r2_redo_census}.json` | files present and valid JSON; **I did not re-derive these** — treat them as yours |
| Your write-ups | `research/docs/xuhao__3-*.md` (audit, cost anatomy, misfire matrix, human prereg/results/provenance, judge sheet) | verbatim |
| Your docs map, dataset READMEs, manifest | `research/docs/xuhao__VERSIONS.md`, `xuhao__datasets-*.md`, `DATASETS_MANIFEST.json` | verbatim |
| `loaders.py` TB2 dedupe, `requirements.lock`, 13 probe scripts | `research/src/loaders.py`, `research/requirements.lock`, `research/scripts/_probe_*.py` | byte-identical |
| Your macOS `.gitignore` block + derived-file rules | `.gitignore` | merged with mine; I kept `processed/steps*/` versioned on purpose (the six gates need those tables right after a clone) |

**Not taken: your folder restructure** (`datasets/`, `essay/`, `tasks/`, top-level `docs/`). Every
path in `paper/`, `research/EXPORT/`, the submission checklist and the six verification gates
refers to the current layout, so adopting it would have broken all of them. Your `docs/VERSIONS.md`
is kept as the translation table if the team ever wants to switch.

## One thing to fix in your packet

`research/docs/human_check_blind/key/SHA256SUMS` **fails for 14 of its 15 entries** as committed:

```
entries 15 | match as committed: 1 | match after CRLF->LF normalisation: 14
```

The digests were computed on LF content; the checked-out files are CRLF, so a verifier on a Windows
checkout sees 0/15 "mismatches" and a verifier on Linux sees 14/15. Hashing each file after
`CRLF -> LF` reproduces all 14 recorded digests exactly, and `judge.csv` matches **as committed**
(that's the entry that matters — it is the verdict commitment).

**Conclusion: the packet is intact; the checksum file is line-ending-sensitive.** Suggested fix:
either normalise before hashing and say so in `README.md`, or add `.gitattributes` with
`*.md text eol=lf` / `*.csv text eol=lf` so the bytes are stable across platforms. I left your file
exactly as committed rather than regenerating it, because regenerating a sealed packet's checksums
after the fact is the wrong habit.

Also note the pilot's honest framing, which I kept: 50.0% human-vs-mechanical sits **on** your
pre-registered falsification boundary (<50%), not comfortably above it.

## One thing you found that broke two of my numbers

Your `106ff4b` ("Loader: dedupe TB2 UUID + empty-UUID twin trials by trial_name") catches a defect
in **my** table builder, not just yours. Terminal-Bench ships duplicate trials and my builder keyed
runs by `trial_name`, so both copies were written under the same `run_id` — worse than a double
count, the twins were written as **one run carrying the union of both attempts' steps**.

Rebuilt deduplicated, two passes, preferring the twin with a real `trial_id`
(`research/scripts/rebuild_tb2_dedup.py`; your preference rule is load-bearing — **354 of the 4,926
duplicated pairs disagree on `reward`/`n_steps`**, so deduplicating by `(run_id, step)` would have
merged two different attempts):

| | frozen (buggy) | deduplicated |
|---|---|---|
| run rows | 34,029 | **29,103** |
| step rows | 1,073,923 | **887,137** |
| duplicate `(run_id, step)` pairs | 186,786 | **0** |
| solve rate | 0.3254 | **0.3439** |

Measured effect on the analyses that used it: polling share of context cost **0.082% → 0.154%**,
mean context per step **29,846 → 19,229 chars**, low-yield cost share 93.7% → 88.6%. The polling
conclusion is unchanged and slightly strengthened. Recorded as §2.37 of
`research/docs/REBUILD_FINDINGS_V2.md`; the three analysis scripts now read
`steps_tb2_dedup/` instead of `steps_tb2_full/`. **No claim in `paper/` depends on TB2** — the
current report is built entirely on the three SWE-agent shard sets.

## Where my work is, if you want to look

| what | where |
|---|---|
| The report (15 pages, 7 figures, builds with `xelatex main.tex` twice) | `paper/main.tex` → `paper/main.pdf` |
| Same text in markdown | `paper/ESSAY.md` |
| Acknowledgement + AI disclosure pages | `paper/main.tex (the acknowledgement is inlined at the end)` |
| Runnable demo (no API key, reproduces the paper's numbers) | `demo/route.py`, `demo/README.md` |
| Every raw number, artifact and table | `research/EXPORT/` (`INDEX.md`, `numbers.csv`, `TABLES.md`) |
| Full findings, incl. the new §2.34–2.37 | `research/docs/REBUILD_FINDINGS_V2.md` |
| What is still open before submission | `research/docs/SUBMISSION_CHECKLIST.md` |

The headline result: on identical rows and folds the published stagnation/loop detectors sit at
chance on "is the agent lost or wrong-fix" (0.596 worst-to-best), while the router scores **0.7324**
on runs it never saw — **+0.1364 AUC**, and **+0.1556** on failure prediction, over 24 cross-set
cells. Bounded honestly: on 88,000 runs from three *other* scaffolds it scores 0.319–0.495 where the
same features fitted inside those scaffolds reach 0.653–0.761, so the claim is shard-level generality
within one scaffold. The live experiment (241 episodes, five conditions, $2.26) is conclusive about
the benchmark — hiding which tests failed costs **27.5 points**, p = 0.015 — and only suggestive
about the runtime intervention.

Three commands reproduce the core:

```bash
python demo/route.py --fit
python demo/route.py --summary      # must print 0.696 / 0.735 and 0.722 / 0.727
python demo/route.py --replay iterative__dvc-4034
```

## What I could use from you

Nothing blocking. Three optional things:

1. If you want R1/R2 cited in the report rather than only in the repository, send one line each on
   what they establish and I will wire them into §7 with your attribution.
2. If you have a stronger view than mine on the folder layout, say so and I will add an `essay/` +
   `docs/` mirror that does not disturb the paths the gates depend on.
3. **One question for the paperwork, and it matters.** The competition requires each author's
   contribution to be stated, and any result produced by a non-author to be named explicitly. So:
   **who judged the 12 windows?** If it was you, say so and the acknowledgement page will list it
   under your contributions (it currently does, alongside the TB2 find). If it was somebody outside
   the two authors, send their name and I will move that one item into 来自他人的帮助
   (help from others) — the rules treat the two sections differently, and putting a non-author's
   work under "author contributions" would be the kind of misstatement the integrity criterion is
   about. Placeholder is already written for it in `paper/main.tex (the acknowledgement is inlined at the end)` §五.
