# 致谢页 / Acknowledgement and Disclosure of AI Use

> **Status: DRAFT SKELETON — the students must complete the marked sections.**
> The competition requires this part to be **1–2 pages (500–1500 字)** and to state the AI tool
> name and version, the specific stages and purposes of use, and the time and frequency of use,
> and to submit the AI chat records for verification. Anything not filled in here will be
> incomplete at submission. Facts below come from the project's own log
> (`research/AI_ASSISTANCE_LOG.md`, 32 recorded passes as of 2026-09-13 15:50 CST); the sections
> marked **[STUDENTS TO COMPLETE]** are ones only you can state truthfully.

---

## 1. 研究背景 (Research background)

This project studies how coding agents fail and whether a runtime system can tell *how* they are
failing in time to intervene. It uses only public trajectory corpora (SWE-agent / SWE-rebench,
Terminal-Bench, and four further open scaffolds) and locally executed test suites from eight
open-source Python packages. No human subjects, no private data.

## 2. 指导老师与参赛学生的关系 (Instructor–student relationship)

**[STUDENTS TO COMPLETE]** — must state: who the instructor(s) are; how the students came to be
introduced to them; whether the guidance was **paid or unpaid**; and what the instructor did and
did not contribute. The rules require this explicitly and treat an undisclosed paid arrangement as
grounds for disqualification.

## 3. AI 使用情况 (Use of AI tools)

**Tool.** `deepseek-v4.1-flash`, a large language model, accessed through an autonomous coding-agent
harness (DeepSeek Harness / DSH) and through the OpenCode Go model gateway. Every model call is
recorded in `research/results/rebuild/llm_ledger.jsonl` with timestamp, token counts and cost; the
live experiment's total spend was **$1.36** (145 episodes over 42 tasks, including one 48-episode
condition that had to be re-run after a harness fault).

**Stages and purposes.**

| stage | how AI was used |
|---|---|
| literature survey | searching for and retrieving published work; **every load-bearing citation was then verified by hand against the primary source**, and two reconnaissance claims were rejected as unverifiable |
| data pipeline | writing the trajectory parsers and the step-table builders |
| statistics | writing and running the analyses: task-disjoint cross-validation, bootstrap intervals, permutation/Wilcoxon tests, calibration, decision curves |
| the causal experiment | the model *is* the agent under test in the live experiment; it is the subject, not the analyst, in that part |
| the demo | writing `demo/route.py`, which the authors can run to reproduce the held-out numbers |
| drafting | producing draft manuscript text, later reviewed and rewritten by the authors |

**Time and frequency.** Four working sessions, 2026-09-10 to 2026-09-13, recorded pass by pass in
`research/AI_ASSISTANCE_LOG.md` (current total: 32 passes; the last two, passes 31–32, ran
13:50–15:50 CST on 2026-09-13). The log records each pass, each bug the AI introduced, and each
claim it retracted.

**Chat records.** Submitted separately as required. They are long; the project log is a condensed,
line-by-line index into them.

## 4. What the AI got wrong (自愿披露 / volunteered disclosure)

The rules ask for truthful disclosure. The truthful summary is that **eleven of the AI's own
conclusions were falsified by tests written to break them, and are documented as retractions**:

1. "failed runs localise *better*" — the metric was **self-referential** and inverted the sign; corrected on an independent gold target, and the correction replicated on two held-out shard sets;
2. "zero false alarms at every budget" — **circular**: the detector and the label were the same statistic, so the reported numbers were an oracle's;
3. "step index beats every learned monitor" — the baseline *was* the run's own length, i.e. hindsight unavailable online;
4. "84.3% of edits are wasted" — counted revision, which is work; corrected to **19.1%** dead ends;
5. "waste is essentially unpredictable" — weakened: a fitted model reaches 0.590 ± 0.011 over the position baseline;
6. "agents fail by being wrong, not lost" as a *novel* claim — the interpretation is prior art (arXiv:2603.24631, published on 16,758 trajectories), so the claim was re-scoped to the measurement defect;
7. a quadratic regular expression made a parser ~30× slower than necessary and stalled a full-corpus rebuild for hours;
8. a `ParquetWriter` left unclosed produced an unreadable table, and a directory deletion destroyed the only copy of another table;
9. a whole condition of the live experiment reported **0/48 success and 0% reaching the gold file** — a spectacular number that was a deleted Python interpreter, not a result; it was disbelieved only by reading the transcripts, and the condition was re-run;
10. the manuscript's own **transfer table** quoted four pairs of numbers that matched the artifact only by coincidence; an automated audit of the paper's numbers against the artifacts found it, and later found the broader finding it belongs to — that the router's generality **stops at the scaffold boundary** (0.32–0.50 on 88,000 runs from three other scaffolds);
11. the **Terminal-Bench run and step counts were inflated by duplicated trials** in the public release, and worse than a double count: the two copies of a trial had been written as one run carrying both attempts. Found by a collaborator, not by the AI. Rebuilt deduplicated, the table is 29,103 runs and 887,137 steps instead of 34,029 and 1,073,923, and every TB2 statistic was recomputed; no claim in this report depends on those tables.

We also disclose two things the AI did that were **not** wrong but were **not its own work**:

* the blinded 12-window human pilot (pre-registration, sealed key, Wilson/κ/McNemar scoring) was
  designed and run by a collaborator, and the single human judgement in it came from a person, not
  from the model;
* the duplicate-trial defect above was found by the collaborator's fix to the data loader, and the
  AI then measured what it had invalidated.

We state these because the competition's criteria include 学术道德与诚信, and because the retraction
record is itself part of the method: the project's rule was that a claim is only kept if a test
designed to falsify it fails to do so.

## 5. 分工说明 (Division of labour)

**[STUDENTS TO COMPLETE — this must be detailed and truthful.]** Required by the rules to cover the
whole process: 选题来源 (how the topic was chosen), 数据获取 (how data was obtained),
分析数据及计算 (how the analysis and computation were done), 实验设计及实施 (experiment design and
execution), and 撰写论文 (writing) — with each member's and the instructor's specific contribution
named, plus 遇到的困难及解决经过 (the difficulties encountered and how they were solved).

A working starting point, to be corrected by you:

| part | who | what |
|---|---|---|
| topic and framing | **[STUDENTS]** | |
| corpus selection and download | **[STUDENTS / AI]** | |
| parsers and step tables | **[AI, reviewed by STUDENTS]** | |
| statistical analysis | **[AI, reviewed by STUDENTS]** | |
| live experiment design | **[STUDENTS / AI]** | |
| running the live experiment | **[AI, under STUDENTS' direction]** | |
| interpretation of results | **[STUDENTS]** | |
| manuscript | **[STUDENTS, from an AI draft]** | |
| defence preparation | **[STUDENTS]** | |

## 6. 声明 (Declaration)

We declare that the research results presented are original work by the participating students; that
materials taken from others are cited and listed in the references; that the AI use described above
is complete and truthful; and that we understand the competition's academic-integrity rules.

**Authors:** Ziheng Yu, Xuhao Chen
**Instructors:** **[STUDENTS TO COMPLETE]**
**Date:** _______________
