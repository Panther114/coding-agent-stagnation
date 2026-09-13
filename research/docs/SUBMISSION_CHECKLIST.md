# Submission checklist — what is ready and what only you can do

Deadline: **2026-09-15 24:00** (registration and upload window opened 2026-07-01). Category:
**Computer Science**. The rules, the judging criteria and the AI-use policy are saved under
`research/docs/award/`.

**Rewritten 2026-09-13 15:50 CST to describe `paper/v2/`, not the earlier `paper/` draft.** The old
draft is still on disk and still compiles; nothing in it is submitted any more.

## 0. What the submission is now

| | |
|---|---|
| Title | **Lost or Wrong?** A runtime router that tells you *how* a coding agent is failing — and therefore what to do |
| Authors | Ziheng Yu, Xuhao Chen |
| Report source | `paper/v2/main.tex` → `paper/v2/main.pdf` (**12 pages**: cover, abstract, contents, 8 pages of body, references page, 2-page acknowledgement). **Build with `xelatex main.tex` (twice)** — the cover page and acknowledgement are Chinese, and `pdflatex` cannot set them. |
| Same text in markdown, for rewriting | `paper/v2/ESSAY.md` |
| Mandatory acknowledgement + AI disclosure | in the PDF (`paper/v2/main.tex (the acknowledgement is inlined at the end)`) and in markdown at `paper/v2/ACKNOWLEDGEMENT_AND_AI_DISCLOSURE.md` |
| Every raw number, table and artifact | `research/EXPORT/` (`INDEX.md`, `numbers.csv`, `TABLES.md`, `artifacts/`, `live/`, `MANIFEST.json`) |
| Executable demonstration | `demo/route.py` + `demo/README.md` (offline, no API key; `--fit --summary --list --replay --live`) |
| Full narrative record | `research/docs/REBUILD_FINDINGS_V2.md`, `research/AI_ASSISTANCE_LOG.md` |

The one-sentence version, if you need to defend it: *published runtime monitors can say that an agent
is struggling but not whether it is **lost** or **wrong-fix**, and those two call for opposite
interventions; a causal router that reads only the first 10–60% of a run separates them at 0.71–0.73
against 0.60–0.67 for every published family on identical rows, and it is honest about where that
stops working.*

## 1. Required by the competition — status

| # | Requirement | Status |
|---|---|---|
| 1 | Research report PDF: cover page, abstract + keywords, table of contents, body, references on a separate page | **Done.** Cover page, abstract, contents, body, references page and the acknowledgement page are all in `paper/v2/main.tex`. The cover's bracketed fields (school, province, instructor, Chinese names) are the only blanks. |
| 2 | Acknowledgement page, 1–2 pages / 500–1500 字: background, instructor relationship, **whether guidance was paid**, division of labour, difficulties and how they were solved | **Skeleton in the PDF** (2 pages), as `paper/v2/main.tex (the acknowledgement is inlined at the end)`. Sections 二 (instructor relationship) and 三 (division of labour) contain `[待填写]` fields; §三 already carries the second author's concrete contributions (blinded human pilot, TB2 duplicate-trial find); §五 asks who, if anyone **outside the two authors**, helped. |
| 3 | AI-use disclosure: tool name and version, stages, purpose, time, frequency | **Done** (acknowledgement §四), sourced from `research/AI_ASSISTANCE_LOG.md` (32 passes). |
| 4 | AI chat records uploaded as supporting material | **Yours.** I cannot export the session transcripts; the harness keeps them. |
| 5 | Academic-integrity declaration, signed by students and instructor, stamped by the school | **Yours.** A signature block is at the end of the acknowledgement page. |
| 6 | Instructor information form, signed and stamped (1–2 instructors) | **Yours.** |
| 7 | Plagiarism report (CNKI / PaperPass etc.) for the final PDF; over the threshold is disqualifying | **Yours** — it must be generated from *your* final PDF after you rewrite it. No copy exists in this repository. |
| 8 | CS category explicitly encourages an executable package / source / video as evidence of authenticity | **Done, and better than a video:** `demo/route.py` reproduces the paper's held-out numbers on demand. |

## 2. What is still open in the PDF

1. **Cover page fields** — `paper/v2/main.tex`, the `titlepage` block: school, province/country,
   instructor name(s), and both Chinese names. I did not invent the Chinese characters.
2. **Acknowledgement §二, §三 and §五** — instructor relationship, whether guidance was paid, and the
   remaining division-of-labour fields. `paper/v2/main.tex (the acknowledgement is inlined at the end)`. §三 already names **Xuhao
   Chen** (the second author) for the blinded human pilot and the TB2 duplicate-trial find; §五 is
   for help from people **outside the two authors** only.
3. Optional: the competition's own report template is linked from the rules page
   (「下载研究报告模板」). If its cover layout differs from this one, copy its layout and keep the
   title, authors and abstract.

## 2b. The second author's branch (`will/dev`, GitHub `willuhd`)

**The two authors are Ziheng Yu and Xuhao Chen; `willuhd` is Xuhao Chen.** There is no third
contributor. `will/dev` has its own git history (a fresh import taken from this repository at 09:31
plus his commits), so his work is **imported into this branch, not merged**: his files were copied
across and each one verified byte-for-byte against the branch blob (`research/src/loaders.py`,
`research/scripts/make_human_blind_packet.py`, `research/scripts/score_human_sample_ci.py`, the probe
scripts, `research/docs/human_check_blind/`, `research/docs/xuhao__3-*.md`,
`research/results/exploratory/*.json`, `research/results/rebuild/human_check_blind_scored.json`,
`research/requirements.lock`, `research/docs/DATASETS_MANIFEST.json`). His layout restructure
(`datasets/`, `essay/`, `tasks/`, top-level `docs/`) was **not** adopted, because every path in this
branch's documents, the export package and the six verification gates refers to the current layout;
his `docs/VERSIONS.md` is a translation table if you ever want to switch.

Two of his contributions are load-bearing or checkable:

* **A blinded human pilot** — 12 windows judged blind, with a pre-registered protocol, sealed key and
  Wilson/κ/McNemar statistics. Re-verified here: the scoring script's self-tests pass and re-running
  it reproduces the committed result exactly (83.3% agreement with the stored judgements, 50.0% with
  the mechanical measure). It is reported in the report's limitations, §7.
* **A real bug in our TB2 numbers** — Terminal-Bench ships duplicate trials, and the frozen table
  double-counted them (34,029 run rows over 29,103 ids; 1,073,923 steps with 186,786 duplicate
  step rows). Rebuilt deduplicated: **29,103 runs / 887,137 steps**. Two TB2 statistics move
  (polling share 0.082% → 0.154%; mean context per step 29,846 → 19,229 chars); no claim in
  `paper/v2` depends on TB2. Recorded as §2.37 of `REBUILD_FINDINGS_V2.md`.

One thing for him to fix: `research/docs/human_check_blind/key/SHA256SUMS` fails for 14 of its 15
entries as committed, because the digests were computed on LF content and the checked-out files are
CRLF. Normalising CRLF→LF reproduces all 14 exactly, and `judge.csv` matches as committed — the
packet is intact, the checksum file is line-ending-sensitive.

## 3. Verify these yourself before submitting

1. Run the demo and watch it reproduce the paper: `python demo/route.py --fit`, then
   `--summary`. The four numbers printed must equal the cells in
   `research/results/rebuild/route_modes_transfer.json` (0.6965 / 0.7346 and 0.7220 / 0.7274 at the
   20% checkpoint). If they do not, something has been edited and you need to know why.
2. Re-run the gates: `research/scripts/run_rebuild_tests.py`, `check_rebuild_consistency.py`,
   `audit_claims.py`, `audit_summary.py`, `check_doc_references.py`, `audit_paper_numbers.py`.
   All six must be green (11/11, passes, 28/28, 0 mismatches, all present, 57/57).
3. After rewriting the essay, re-run `audit_paper_numbers.py`. It reads `paper/v2/main.tex` and
   checks every number against the artifact it names — **it has already caught five real errors in
   our own manuscript**, including a transfer table whose cells came from the wrong rows. If you
   rewrite the LaTeX, it protects you; if you rewrite only the markdown essay, port the numbers back
   into the LaTeX for the check to mean anything.
4. Open three citations and confirm they resolve. Two citations are earlier versions of our own
   claims (arXiv:2603.24631, arXiv:2603.25764) and are deliberately reported as prior art.
5. Read §4.3 (cross-scaffold negative) and §5 (live experiment) once more before you defend it.
   Those are the two places a judge will push, and the paper already concedes both.

## 4. The three claims to lead with, and the two you must not make

**Lead with:** (1) the two failure modes exist and are measurable at scale — 67.0 / 69.0 / 66.4% of
failures happen with the agent already inside a gold file, across three disjoint shard sets;
(2) the published detector families carry **no** usable signal about which mode it is (0.41–0.54, at
or below chance) while the router reaches 0.7324 on data it never saw; (3) a decision rule on the
predicted mode beats every fixed policy in 12 of 12 cells.

**Do not claim:** (a) that the router generalises across scaffolds — it was tested and it does not
(0.32–0.50 on 88,000 runs from three other corpora); (b) that the router improves live task success
— the live experiment measures the *premise*, and its one significant effect is that withholding the
failing test's location costs 27.5 points.

## 5. If you get another day

The live experiment is where the remaining value is. One extra condition would close the loop: run
the masked condition **with the router fused in** — when the router says WRONG-FIX, force a
re-check of the agent's own diagnosis; when it says LOST, supply the file. That is the intervention
the paper argues for, and it is the only experiment that would show the router *improving* outcomes
rather than predicting them. The harness already supports it (`research/scripts/run_live48.py`), the
API cost is about \$1.40 for 145 episodes at current prices, and the arms would be directly
comparable to the three already recorded.
