# Coding agents: automated stagnation, and what a runtime can actually detect

This repository holds the complete research package behind a study of one question:

> **Which observable signals let an online, reference-free monitor tell that a coding agent has
> stopped making task-relevant progress — and what can a runtime legitimately do about it?**

Written for the **S.-T. Yau High School Science Award (Computer Science), 2026**, by Qichen Tong
and Ke Chuang Jiang, with an autonomous AI agent doing the implementation, annotation logistics
and drafting. Every AI contribution is logged in `research/AI_ASSISTANCE_LOG.md`.

**Submission deadline: 2026-09-15.** The scientific state of this repository changes daily right
now; the documents below are the authoritative record, not this file.

## Read in this order

| | |
|---|---|
| `research/README.md` | the full map of the package, and every script → artifact pairing |
| `research/docs/EXECUTIVE_SUMMARY.md` | the rebuild in two minutes |
| `research/docs/KEY_FINDINGS.md` | the result in plain language |
| `research/docs/REBUILD_FINDINGS_V2.md` | objective labels, 41k trajectories, the current headline |
| `research/docs/HANDOFF.md` | claim → artifact → what it does and does not support |
| `research/docs/GAP_ANALYSIS_AND_PLAN.md` | what is still broken, ranked, and what is retracted |
| `research/AI_ASSISTANCE_LOG.md` | what the AI did, every defect it introduced, every retraction |
| `paper/main.pdf` | the report itself (source: `paper/main.tex`) |

## Layout

```
paper/      LaTeX report; generated_tb2.tex and tables_tb2.tex are emitted from a frozen run
research/
  src/        monitor implementation (~2,000 lines + the agentstall package; stdlib + NumPy)
  scripts/    one script per pipeline stage; each writes a frozen artifact
  data/       processed tables and annotations (versioned); raw corpora (NOT versioned)
  results/    frozen artifacts: JSON for every headline number, parquet for scores
  docs/       findings, codebooks, literature verification, award rules
  figures/    figures as generated
main_idea.md  the original research proposal
```

## Reproducing

The corpora are not in this repository. To fetch them (~6.1 GB), then rebuild from scratch:

```powershell
cd research
python scripts/download_data.py            # + fetch_missing_shards.py, xscaffold_download.py
python scripts/build_step_table.py         # per-step tables, both corpora
python scripts/extract_windows.py          # online window features
python scripts/analyse_windows.py          # the monitor zoo
```

Most stages are already done, and **their artifacts are committed**, so you do not need the raw
corpora to check the results — only to regenerate them.

## Checking the result

These five gates are the project's integrity contract. They are expected to pass on a clean
clone, reading only the versioned artifacts:

```powershell
cd research
python scripts/run_rebuild_tests.py          # invariant tests
python scripts/check_rebuild_consistency.py  # cross-artifact agreement and staleness
python scripts/audit_claims.py               # every headline claim vs its artifact
python scripts/audit_summary.py              # the one-page summary vs the artifacts
python scripts/check_doc_references.py       # every artifact cited in the docs exists
```

`python scripts/verify_all.py` runs the wider suite.

## Ground rules

* **Never overwrite a frozen artifact.** New results are written alongside old ones; the old
  number stays auditable.
* **No number without an artifact, no citation without a check.** Where a measurement does not
  exist the artifact records `null` rather than an estimate.
* **Retractions are kept, not hidden.** When the data contradicted a claim, the claim was
  withdrawn and the reversal recorded in `research/AI_ASSISTANCE_LOG.md`.
* The AI-assisted status of this work is disclosed rather than obscured; the raw reader outputs
  and adjudication records are in `research/data/annotations/`.
