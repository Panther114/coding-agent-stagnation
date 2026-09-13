# How to help

Thank you. This is a two-person high-school research project (Qichen Tong and Ke Chuang Jiang)
with a hard deadline of **2026-09-15**, and the most useful help is *independent verification* —
checking work the authors cannot credibly check on their own. Every task below is separable:
pick one, finish it, report it. None of them requires you to understand the whole project first.

This repository is **private** — send your GitHub username to be added as a collaborator before
you can clone it.

Setup, once:

```powershell
git clone https://github.com/Panther114/coding-agent-stagnation.git
cd coding-agent-stagnation/research
python scripts/run_rebuild_tests.py      # should pass; if it does not, tell us immediately
```

The raw corpora (~6.1 GB) are deliberately not in the repository — see `README.md`. The processed
artifacts *are*, so every task below works on a clean clone.

---

## 1. Judge 12 windows yourself — highest value, needs a human, ~45 min

This is the one check that cannot be automated, and it is on the critical path: it produces two
numbers the paper currently cannot state — how well the AI-written codebook agrees with a person,
and whether the mechanical "the workspace did not move" label matches human reading.

1. Read `docs/human_check_sample.md`. It explains the exercise in one page.
2. Open `results/rebuild/human_check_sample.csv` (12 rows). For each row, open the annotation card
   named in the doc under `data/annotations/tb2/cards_dense/`, read the trajectory, and decide:
   **stagnant or productive?**
3. Write your verdict into a `human_label` column — `true`/`false`, `1`/`0`, `stagnant`/`productive`,
   or `yes`/`no` all work. The column may not exist yet; the scorer creates it and tells you if it
   is empty.
4. `python scripts/score_human_sample.py` → writes `results/rebuild/human_check_scored.json`.

**The one rule that makes this worth doing:** decide all 12 before you look at the `gold`,
`mech_stagnant` or `agree` columns. The whole point is that your reading is independent. If you
peek, the result is worthless, and we would rather you told us you peeked.

Send back the CSV and the JSON. Do not overwrite them in a commit — send them, or open a PR.

## 2. Be the reproducibility witness — ~20 min

The strongest sentence a paper can contain is "a person who had never seen this code cloned it and
the checks passed". Please produce it literally:

```powershell
cd research
python scripts/run_rebuild_tests.py
python scripts/check_rebuild_consistency.py
python scripts/audit_claims.py
python scripts/audit_summary.py
python scripts/check_doc_references.py
```

Report the exact output, including anything that fails or warns. A failure is a valuable finding,
not an inconvenience — the project's own log records ten defects found this way.

## 3. Audit the citations — ~45 min

Every claim in `paper/refs.bib` must resolve to a real paper. Open each entry's URL and confirm that
the **title, authors, venue and identifier actually match** the entry. Then check the arXiv
identifiers quoted in the prose (in `docs/` and the paper) against arXiv's own abstract pages —
confirm the cited numbers really appear there, not just the topic.

Pay particular attention to any paper cited for a *number* (a sample size, a percentage, a p-value).
Those are the citations a reviewer will check, and a number attached to the wrong paper is worse
than no citation. Report each entry as verified-or-not, with the URL you checked on.

## 4. Re-derive a headline number independently — ~1 h

Pick any number in `docs/REBUILD_FINDINGS_V2.md` and recompute it from the committed artifact using
*your own* code path, rather than the script the authors wrote. `scripts/collect_rebuild_numbers.py`
shows where each headline number comes from, and `results/rebuild/` holds the underlying JSON.

If your number disagrees with theirs, that is a finding — report the discrepancy and both code
paths. Do not correct their number quietly.

## 5. Re-read annotation cards and report your agreement rate — ~1 h

Sample 20 cards from `data/annotations/tb2/cards_dense/`, decide the label yourself, and compare
with the stored one. Report the agreement rate. The paper's own instructions say to do this and to
print the result; an outside agreement rate is stronger evidence than an inside one.

## 6. Unblock the external comparison — needs a dataset we do not have

The one head-to-head the study cannot currently run is against **RedundancyBench**'s published
step-level ceiling of 24.88%. If you have access to that dataset (or to CodeTraceBench), running
the study's detectors on it on identical rows would close the last open comparison. Say so and we
will hand over the exact evaluation protocol.

## 7. Test generality on a third corpus

The two corpora currently agree qualitatively. A third independent one (SWE-rebench / OpenHands)
would test whether the conclusion is general or an artefact of two datasets. This needs the raw
data, so it is only worth starting if you have bandwidth and disk — ask first.

---

## Ground rules

* **Never overwrite a frozen artifact.** Add a new file alongside the old one. Several documents
  point at specific artifacts by name and a silent edit breaks the audit trail.
* **Never fabricate a number or a citation.** If a measurement does not exist, the convention here
  is to record `null` and say so. An honest gap is acceptable; an invented value is not.
* **Log anything you change.** `AI_ASSISTANCE_LOG.md` records every defect found and every claim
  retracted. If you find an error, it goes in there rather than being quietly fixed.
* **Keep the five gates green** (see `README.md`). If your change turns one red, say so in the same
  message.
* **If you contribute, you must be named.** The competition requires a detailed, truthful division
  of labour and disclosure of help from others, so tell us exactly what you did and how long it
  took — that goes into the acknowledgement page, and it is a requirement, not a courtesy.
