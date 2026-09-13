# Lost or Wrong? — coding-agent failure modes and a runtime router

**S.-T. Yau High School Science Award (Computer Science), 2026.** Ziheng Yu and Xuhao Chen.

When a coding agent is stuck, the decision that matters is whether it is **LOST** (has not found the
code) or **WRONG-FIX** (found it, and its change does not work) — those call for opposite
interventions. The published stagnation and loop detectors cannot tell the two apart; a causal router
that reads only the first 10–60 % of a run can (**0.7324** on runs it never saw, against **0.5960**
for the best published family on identical rows and folds). The project also found and measured a
self-referential metric that inverts the standard comparison, and a benchmark leak that inflates
reported agent success rates.

## Start here, by role

| you are… | read this |
|---|---|
| **a judge or a reviewer of the report** | `paper/v2/main.pdf` (12 pages), then `research/EXPORT/INDEX.md` for every number → the artifact that produced it |
| **the collaborator** (you have been working on `will/dev`) | **[`COLLABORATOR_NOTES.md`](COLLABORATOR_NOTES.md)** — what was imported, what to fix in your packet, and the TB2 bug you found |
| **an author, before submitting** | `research/docs/SUBMISSION_CHECKLIST.md` — every required component, its real status, and the fields only you can fill |
| **someone who wants to run it** | `demo/README.md` — offline, deterministic, no API key |

## The four deliverables

| # | what | where |
|---|---|---|
| 1 | **Report** — cover page, abstract, contents, body, references page, 2-page Chinese acknowledgement. Build with `xelatex main.tex` **twice** (the cover and acknowledgement are Chinese; `pdflatex` cannot set them). | `paper/v2/main.tex` → `paper/v2/main.pdf`; same text in markdown at `paper/v2/ESSAY.md` |
| 2 | **Runnable demo** — `--fit --summary --list --replay --live`. `--summary` reproduces the frozen held-out numbers (0.6965 / 0.7346 and 0.7220 / 0.7274 at the 20 % checkpoint). | `demo/route.py`, `demo/README.md` |
| 3 | **Live application experiment** — 241 episodes, 48 real PyPI-package tasks, five conditions, $2.26: masked 0.286, unmasked 0.372, nudge 0.452, hinted 0.561, verify 0.571. | `research/scripts/run_live48.py`, `research/results/live/live_arms_valid.json` |
| 4 | **Data package** — every number / table / artifact behind the report | `research/EXPORT/` |

## Verification

Six gates run on every change, and all are green:

| gate | result |
|---|---|
| `research/scripts/run_rebuild_tests.py` | 11 / 11 invariant tests |
| `research/scripts/check_rebuild_consistency.py` | cross-artifact consistency passes |
| `research/scripts/audit_claims.py` | 28 / 28 headline claims trace to their artifacts |
| `research/scripts/audit_summary.py` | 0 mismatches in the executive summary |
| `research/scripts/check_doc_references.py` | every cited artifact exists |
| `research/scripts/audit_paper_numbers.py` | 65 / 65 paper numbers trace to an artifact |
| `paper/v2/verify_pdf.py` | the compiled PDF carries the current numbers, and retracted claims only inside retractions |

That last gate has caught **five real errors in our own manuscript**, including a transfer table
whose cells came from the wrong rows. The AI assistance log records **eleven retractions** of the
agent's own claims, each found by a test written to falsify it.

## Where the detail lives

`research/README.md` is the entry point to the research package. The full narrative record is
`research/docs/REBUILD_FINDINGS_V2.md`; the one-page version is
`research/docs/EXECUTIVE_SUMMARY.md`; every AI contribution, defect and retraction is in
`research/AI_ASSISTANCE_LOG.md`.

## Access

This repository is private. Send your GitHub username to be added as a collaborator.
