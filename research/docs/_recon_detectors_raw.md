# Recon: Benchmarks & Detectors of LLM-Agent Failure Modes — Verified Raw Notes

**Compiled:** 2026-09-13
**Purpose:** literature verification for research on failure modes of LLM coding agents.
**Method:** every arXiv ID below was verified by fetching `https://arxiv.org/abs/<id>` and reading the returned
title / authors / date / Comments field from the HTML. Numbers were extracted from the full text
(arXiv HTML where available, else the PDF via `pdftotext`) downloaded to
`research/docs/_raw/`. Anything not confirmed at the source is explicitly marked **UNVERIFIED**.
IDs surfaced by a delegated discovery sweep were **independently re-verified by re-fetching each abs page** before
inclusion; one such item (a second paper named "Aegis") is flagged as a name collision.

**Scope:** 7 requested items (all ID-verified, all titles matched) + 54 additional 2025–2026 failure-mode
benchmarks/detectors/studies = **61 verified entries**.

**Verification legend**
- `[abs]` — title/authors/date/venue read directly off the arXiv abstract page.
- `[fulltext]` — number quoted from the downloaded full text of the paper.
- `UNVERIFIED` — could not be confirmed; do not cite as fact.

---

## Master table

| # | Name | Exact title (verified) | 1st author | Year | arXiv ID | Venue | Primary metric + exact numbers |
|---|---|---|---|---|---|---|---|
| 1 | AgentStop | AgentStop: Terminating Local AI Agents Early to Save Energy in Consumer Devices | Dzung Pham | 2026 | 2605.15206 | ACM CAIS '26 | AUC-ROC 0.6–0.7; energy wastage ↓15–20%; utility drop <5% |
| 2 | RedundancyBench | Redundant or Necessary? A Benchmark for Detecting Redundant Steps in Agent Trajectories | Minyang Hu | 2026 | 2605.29893 | UNVERIFIED | step-level score: best 24.88%; worst 4.25% |
| 3 | TRAIL | TRAIL: Trace Reasoning and Agentic Issue Localization | Darshan Deshpande | 2025 | 2505.08638 | UNVERIFIED (abs page states none) | Joint acc.: 18.3% GAIA / 5.0% SWE-bench (Gemini-2.5-Pro) |
| 4 | MAST | Why Do Multi-Agent LLM Systems Fail? | Mert Cemri | 2025 | 2503.13657 | NeurIPS 2025 (Spotlight) | Cohen's κ=0.88; 14 failure modes; 1642 traces |
| 5 | AgentDebug | Where LLM Agents Fail and How They can Learn From Failures | Kunlun Zhu | 2025 | 2509.25370 | UNVERIFIED | All-Correct 24.3% vs 0.3%; Step 45.0% vs 28.0% |
| 6 | GitHub-issues failure-characterization | Characterizing the Failure Modes of LLMs in Resolving Real-World GitHub Issues | Yanjie Jiang | 2026 | 2605.12270 | UNVERIFIED (IEEE-style, no venue stated) | Strategy&Logic 90/243 = 37.0%; Problem Understanding 71 = 29.2% |
| 7 | AgentLocate | Who Broke the System? Failure Localization in LLM-Based Multi-Agent Systems | Yufei Xia | 2026 | 2607.07989 | COLM 2026 (to appear) | Who&When agent-level 69.05% (Qwen-7B, all-at-once) |
| 8a | Aegis-**A** / "AEGIS" | Aegis: Automated Error Generation and Attribution for Multi-Agent Systems | Fanqi Kong | 2025 | 2509.14295 | UNVERIFIED | 9,533 annotated error trajectories; Aegis-Bench 600 test |
| 8a′ | Aegis-**B** ⚠️name clash | Aegis: Taxonomy and Optimizations for Overcoming Agent-Environment Failures in LLM Agents | Kevin Song | 2025 | 2508.19504 | UNVERIFIED | 142 traces/3,656 turns; 6 failure modes; +6.7–12.5% success |
| 8b | AgenTracer | AgenTracer: Who Is Inducing Failure in the LLM Agentic Systems? | Guibin Zhang | 2025 | 2509.03312 | UNVERIFIED | +18.18% over Gemini-2.5-Pro / Claude-4-Sonnet on Who&When |
| 8c | TELBench / DRIFT | Where Do Deep-Research Agents Go Wrong? Span-Level Error Localization in Agent Trajectories | Jiaming Wang | 2026 | 2606.02060 | UNVERIFIED | DRIFT macro-F1 54.91 best (+33.02 vs bare) |
| 8d | LoopsBench | LoopsBench: From Harness Engineering to Loop Engineering in Coding Agent Evaluation | Han Li | 2026 | 2608.00267 | UNVERIFIED | 112 tasks; best config resolves 25.00% |
| 8e | IAL-Scan | When Agents Do Not Stop: Uncovering Infinite Agentic Loops in LLM Agents | Xinyi Hou | 2026 | 2607.01641 | UNVERIFIED | precision 91.9%; 68/74 confirmed IAL failures |
| 8f | FailFast–RestartSmart | Fail-Fast, Restart-Smart: Early Failure Prediction and Restart for SWE Agentic Tasks | Chenyu Wang | 2026 | 2608.03222 | UNVERIFIED | saves 14.6–20.4% tokens @5% FPR; 66.6%→71.8% resolve |
| 8g | PrefixGuard | PrefixGuard: From LLM-Agent Traces to Online Failure-Warning Monitors | Xinmiao Huang | 2026 | 2605.06455 | Under Review (abs) | AUPRC 0.900/0.710/0.533/0.557 |
| 8h | AgentForesight | AgentForesight: Online Auditing for Early Failure Prediction in Multi-Agent Systems | Boxuan Zhang | 2026 | 2605.08715 | UNVERIFIED | Exact-F1 66.44; +19.88 over DeepSeek-V4-Pro |
| 8i | AgentLens | AgentLens: Revealing The Lucky Pass Problem in SWE-Agent Evaluation | Priyam Sahoo | 2026 | 2605.12925 | UNVERIFIED | 10.7% of passes are "Lucky"; AUROC 0.766 |
| 8j | FALAT | FALAT: Tracing Failures in LLM Agent Trajectories via Dependency-Guided Search | Md Nakhla Rafi | 2026 | 2606.00765 | UNVERIFIED | step-acc 46.0% alg-gen / 29.1% hand-crafted |
| 8k | SAFARI | SAFARI: Scaling Long Horizon Agentic Fault Attribution via Active Investigation | Chenyang Zhu | 2026 | 2606.24626 | AIWILD @ ICML 2026 (Workshop) | +20% Who&When; +19% TRAIL GAIA; 0.58 precision |
| 8l | Real-Time Detection and Repair | Real-Time Detection and Repair of LLM Agent Failures | Sunny Dubey | 2026 | 2608.02464 | UNVERIFIED | detects 0.71 of failures @5% FA (AUROC 0.872) |
| 8m | Sherlock | Sherlock: Reliable and Efficient Agentic Workflow Execution | Yeonju Ro | 2025 | 2511.00330 | UNVERIFIED | +18.3% accuracy; −48.7% exec time; −26.0% verify cost |
| 8n | SWE-Shepherd | SWE-Shepherd: Advancing PRMs for Reinforcing Code Agents | Mahir Labib Dihan | 2026 | 2604.10493 | UNVERIFIED | 51% resolved / 12.2 steps (vs mini-SWE-agent 57%/15.2) |
| 8o | SWE-TRACE | SWE-TRACE: Optimizing Long-Horizon SWE Agents Through Rubric Process Reward Models and Heuristic Test-Time Scaling | Hao Han | 2026 | 2604.14820 | UNVERIFIED | rubric PRM + HG-TTS (qualified numbers: see detail) |
| 8p | ATBench | ATBench: A Diverse and Realistic Agent Trajectory Benchmark for Safety Evaluation and Diagnosis | — (UNVERIFIED) | 2026 | 2604.02022 | UNVERIFIED | GPT-5.4 F1 76.7%; risk-source diag 33.6% |
| 8q | AgentFixer | AgentFixer: From Failure Detection to Fix Recommendations in LLM Agentic Systems | — (UNVERIFIED) | 2026 | 2603.29848 | Agentic Engineering Wkshp (Apr 2026) | 15 detection tools; parsing = 38% of task failures |
| 8r | DCFA | DCFA: Dual-view Causal-inspired Attribution for Failure Reasoning in LLM-based Multi-agent Systems | — (UNVERIFIED) | 2026 | 2609.04749 | UNVERIFIED | +8.27% step-level acc over SOTA on Who&When |
| 8s | WinClick | WinClick: GUI Grounding with Multimodal Large Language Models | Zheng Hui | 2025 | 2503.04730 | UNVERIFIED | **NOT a failure-mode detector** — GUI grounding; avg 56.1% |
| 8t | **Who&When** ⭐ | Which Agent Causes Task Failures and When? On Automated Failure Attribution of LLM Multi-Agent Systems | Shaokun Zhang | 2025 | 2505.00212 | **ICML 2025** (PMLR v267, 76583–76599) | best 53.5% agent-level / only 14.2% step-level; 127 MAS |
| 8u | ECHO | Where Did It All Go Wrong? A Hierarchical Look into Multi-Agent Error Attribution | Adi Banerjee | 2025 | 2510.04886 | UNVERIFIED | agent-level ≈68%; step exact 27–28% |
| 8v | Who&When Pro | Who&When Pro: Can LLMs Really Attribute Failures in AI Agents? | Jiale Liu | 2026 | 2607.09996 | UNVERIFIED | 12,326 failed trajectories; 3 modalities; 26 benchmarks |
| 8w | ToolFailBench | ToolFailBench: Diagnosing Tool-Use Failures in LLM Agents | Harsh Soni | 2026 | 2607.04686 | AIWILD + FAGEN @ ICML 2026 (workshops) | best 86.33% Clean Tool-Use Rate; 1,000 tasks; 19 models |
| 8x | Model-or-Harness taxonomy | Model or Harness? An Interaction-Centric Taxonomy for Localizing Agent Failures | Harsh Raj | 2026 | 2607.28802 | UNVERIFIED | 41 failure modes; best judge Cohen's κ=0.76 |
| 8y | EarlyEval | EarlyEval: Cheaper Agent Evaluation via Early Outcome Prediction | Yuling Shi | 2026 | 2609.02783 | UNVERIFIED | −13–26% steps; −44.1% in-tokens; 89–97% accuracy |
| 8z | Doomed from the Start | Doomed from the Start: Early Abort of LLM Agent Episodes via a Recall-Controlled Probe Cascade | Kai Ruan | 2026 | 2607.06503 | UNVERIFIED | 1.5–8.8× compute saved @90% recall; −60.2% tokens |
| 8aa | Premature Commitment | When Agents Commit Too Soon: Diagnosing Premature Commitment in LLM Agents | Aman Mehta | 2026 | 2606.22936 | UNVERIFIED | monitor AUROC up to 0.97; does NOT track correctness |

---

## Per-item detail

### 1. AgentStop — arXiv:2605.15206 ✅ ID CORRECT

- **Exact title** `[abs]`: *AgentStop: Terminating Local AI Agents Early to Save Energy in Consumer Devices*
  - Reportedly given as "AgentStop: Terminating Local AI Agents Early…" — this is a correct truncation of the real title. **No title mismatch.**
- **First author** `[abs]`: Dzung Pham. Co-authors: Kleomenis Katevas, Ali Shahin Shamsabadi, Hamed Haddadi.
- **Year** `[abs]`: 2026 (submitted 1 May 2026), v1 only.
- **Venue** `[abs]`: **ACM CAIS '26** (stated in the Comments field).
- **URL**: https://arxiv.org/abs/2605.15206 · HTML: https://arxiv.org/html/2605.15206v1
- **Subjects**: cs.LG, cs.AI, cs.DC · Code: https://github.com/brave-experiments/AgentStop

**Exact claimed numbers** `[fulltext]`:

| Quantity | Value (verbatim from paper) |
|---|---|
| AUC-ROC, Qwen3-30B-A3B, FRAMES & SimpleQA | "0.6–0.7 AUC in the first 4-5 steps on both FRAMES and SimpleQA" |
| AUC-ROC, SWE-Bench Verified, Qwen3-Coder-30B-A3B | "achieves 0.6–0.7 AUC in the first 10 steps" |
| AUC-ROC, Qwen3-1.7B | "no better than random guessing" |
| Headline energy wastage reduction | "reduce wasted energy by 15-20% with minimal impact on task performance (<5% utility drop)" |
| Utility drop | **<5%** (headline claim); also "<5% utility drop" at FRAMES step 5 and SWE-bench step 5 |
| FRAMES, step 5 | "more than 20% wastage reduction and less than 5% task utility drop" |
| SimpleQA, step 3–4 | "reduce energy wastage by 25% and also with <5% utility drop" |
| SWE-Bench Verified, step 5 | "reduce energy wastage by up to 18–19% with <5% utility drop at step 5" |
| Cost asymmetry | "energy wastage for coding is nearly 9 times higher than web-based QA (3004.6 mWh vs 352.4 mWh per failed FRAMES task)" |
| Cross-domain transfer | Train FRAMES → eval SimpleQA: ≈0.66 AUC at steps 2–4. Train SimpleQA → eval FRAMES: ≈0.64 AUC at steps 2–5 (direct training reaches 0.7) |
| Logprob-count sensitivity | FRAMES / Qwen3-30B-A3B: "difference between the lowest and highest AUC is limited to 0.05" |
| Battery context | "if the MoE-powered agent fails on 10 FRAMES tasks, the total energy wastage will be roughly 3.5–7% of the laptop's battery" |

**Metric definitions** `[fulltext]`: Energy wastage reduction % = (1 − early-stop energy wastage / total energy wasted on failed runs) × 100%; Task utility drop % = drop in task utility due to early stopping.

⚠️ **Caveat:** the "15–20%" headline is the *abstract's* summary; the per-dataset numbers are higher
(20%+ FRAMES, 25% SimpleQA, 18–19% SWE-bench). Report the per-dataset figures when precision matters.

---

### 2. RedundancyBench — arXiv:2605.29893 ✅ ID CORRECT (but name is not the title)

- **Exact title** `[abs]`: *Redundant or Necessary? A Benchmark for Detecting Redundant Steps in Agent Trajectories*
  - ⚠️ **Important:** "RedundancyBench" is the **benchmark introduced inside** the paper, **not** the paper title. If a draft cites it as *"RedundancyBench: …"* that title does not exist on arXiv.
- **First author** `[abs]`: Minyang Hu. Co-authors: Bo Yang, Zhinuo Zhou, Jiachen Liang, Guo Jiahao, Yiyang Yin, Xiongwei Han.
- **Year** `[abs]`: 2026 (submitted 28 May 2026), v1.
- **Venue**: **UNVERIFIED** — the abs page Comments field is empty and no venue is stated.
- **URL**: https://arxiv.org/abs/2605.29893 · HTML: https://arxiv.org/html/2605.29893v1
- **Subject**: cs.AI · License: CC BY-NC-SA 4.0

**Metric + exact numbers** `[fulltext]`:
- **Two metrics.** (i) *Trajectory-level score* = binary classification accuracy over trajectories (redundant if ≥1 redundant step). (ii) *Step-level score* = **average per-trajectory F1** over step labels (chosen because classes are highly imbalanced).
- **Headline / best number:** "even the best-performing method achieves only **24.88% step-level score**" — specifically **DeepSeek-V4-Pro with the Window-to-One strategy**.
- **Worst:** GPT-5.4 with One-to-One → **4.25% step-level score** (and 43.17% trajectory-level, i.e. *worse than the ~50% random-guess baseline*).
- Selected table values:

| Method | Trajectory-level | Step-level |
|---|---|---|
| GPT-5.4, One-to-One | 43.17% | 4.25% |
| GPT-5.4, Window-to-One | 70.88% | 15.08% |
| GPT-5.4, All-to-All | 66.06% | 16.69% |
| DeepSeek-V4-Pro, Window-to-One | 68.48% | **24.88%** (best) |
| DeepSeek-V4-Pro, All-to-All | 62.21% | — |
| GPT-4o, Window-to-One | 64.81% | 20.49% |
| GPT-4o, All-to-All | 47.32% | 13.42% |

- **Ablation (ground-truth actions, All-to-All):** trajectory-level 57.50% → 70.00%; step-level 9.72% → 22.92%.

**Dataset size** `[fulltext]`: **200 trajectories, >8,000 steps**, across 3 domains, drawn from the **τ² benchmark**
(278 trajectories run with Qwen-3.6-Plus, 200 successful retained). Annotation: **6 human experts, 3 rounds**;
~1 hour per trajectory. Four redundancy types. Paper's own stated limitation: "only 200 trajectories … may be
insufficient to support large-scale exploration".

**Methods evaluated:** 3 — One-to-One, Window-to-One (k=3, i.e. six neighbouring steps), All-to-All.

---

### 3. TRAIL — arXiv:2505.08638 ✅ ID CORRECT

- **Exact title** `[abs]`: *TRAIL: Trace Reasoning and Agentic Issue Localization*
- **First author** `[abs]`: Darshan Deshpande. Co-authors: Varun Gangal, Hersh Mehta, Jitin Krishnan, Anand Kannappan, Rebecca Qian (all Patronus AI).
- **Year** `[abs]`: 2025 (v1 13 May 2025; v3 23 Jun 2025).
- **Venue**: **UNVERIFIED.** The abs page Comments field contains only a dataset link
  (https://huggingface.co/datasets/PatronusAI/TRAIL). No conference is stated. Do not assert a venue.
- **URL**: https://arxiv.org/abs/2505.08638 · HTML: https://arxiv.org/html/2505.08638v3
- **Subjects**: cs.AI, cs.CL · Dataset: https://huggingface.co/datasets/PatronusAI/TRAIL

**Taxonomy** `[fulltext]`: a formal agentic-error taxonomy spanning **three key areas** —
**(1) reasoning, (2) planning and coordination, (3) system execution** (Figure 1/Figure 3). Named categories include
Output Generation (Formatting Errors; Instruction Non-compliance; Language-only Hallucination), Poor Information
Retrieval, Tool Selection Errors, Tool Output Misinterpretation, Tool-related Hallucinations, Context Handling
Failures, Resource Abuse, Goal Deviation, Task Orchestration Errors, Environment Setup Errors, and API Issues
(Rate Limiting 429; Authentication 401/403; Service Errors 500; Resource Not Found 404).
⚠️ The paper does not state a single authoritative count of leaf categories in the prose I verified — count them from
Figure 3 rather than quoting a number.

**Dataset size** `[fulltext]`: **148 traces** (118 GAIA + 30 SWE-Bench); **1,987 OpenTelemetry spans**, of which
**575 exhibit ≥1 error**; **841 annotated errors**, averaging **5.68 errors/trace**. Errors found in **114 GAIA traces
and 30 SWE-Bench traces**. Traces built with HuggingFace OpenDeepResearch + o3-mini-2025-01-31 (GAIA) and a CodeAct
agent with claude-3-7-sonnet-20250219 (SWE-bench). Four expert annotators; four verification rounds; 5.63% of SWE-bench
spans and 5.31% of GAIA spans modified during review.

**Exact metrics — best model (`Gemini-2.5-Pro-Preview-05-06`)** `[fulltext]`:

| Model | GAIA Cat.F1 | GAIA Loc.Acc | **GAIA Joint** | GAIA ρ | SWE Cat.F1 | SWE Loc.Acc | **SWE Joint** | SWE ρ |
|---|---|---|---|---|---|---|---|---|
| GPT-4.1† | 0.218 | 0.107 | 0.028 | 0.411 | 0.166 | 0.000 | 0.000 | 0.153 |
| OpenAI o1* | 0.138 | 0.040 | 0.013 | 0.450 | CLE | CLE | CLE | CLE |
| OpenAI o3* | 0.296 | 0.535 | 0.092 | 0.449 | CLE | CLE | CLE | CLE |
| Claude-3.7-Sonnet* | 0.254 | 0.204 | 0.047 | 0.738 | CLE | CLE | CLE | CLE |
| **Gemini-2.5-Pro-Preview-05-06*†** | **0.389** | **0.546** | **0.183** | 0.462 | 0.148 | 0.238 | **0.050** | **0.817** |
| Gemini-2.5-Flash-Preview-04-17*† | 0.337 | 0.372 | 0.100 | 0.550 | 0.213 | 0.060 | 0.000 | 0.292 |

- **Best model joint accuracy: 18.3% on GAIA, 5.0% on SWE-Bench** (Gemini-2.5-Pro). Paper's abstract/conclusion rounds these
  to "**only 18% joint accuracy on GAIA and 5% on SWE Bench**", and to "**a mere 11% on TRAIL**" / "11% combined joint
  accuracy on both splits".
- **Reasoning-effort ablation (o3, Category F1):** 0.296 → 0.277 → 0.264 (high → medium → low).
- **Best human-correlation:** Claude-3.7-Sonnet best on GAIA (0.738 avg); Gemini-2.5-Pro best on SWE-Bench (0.817 avg).
- **Error distribution:** "Formatting Errors and Instruction Non-compliance make up **353 of 841 total errors—nearly 42%**";
  ~44% of Output Generation errors are low-impact. System Execution Errors are rare.
- **Context limit:** three of eight models (GPT-4.1 aside, o1/o3/Claude-3.7-Sonnet on SWE) cannot process the full context (CLE).
- All Table 1 results are an average of three runs.

---

### 4. MAST — arXiv:2503.13657 ✅ ID CORRECT

- **Exact title** `[abs]`: *Why Do Multi-Agent LLM Systems Fail?* (MAST = the **M**ulti-**A**gent **S**ystem Failure **T**axonomy introduced inside)
- **First author** `[abs]`: Mert Cemri. Co-authors: Melissa Z. Pan, Shuyi Yang, Lakshya A. Agrawal, Bhavya Chopra, Rishabh Tiwari, Kurt Keutzer, Aditya Parameswaran, Dan Klein, Kannan Ramchandran, Matei Zaharia, Joseph E. Gonzalez, Ion Stoica (UC Berkeley).
- **Year** `[abs]`: 2025 (v1 17 Mar 2025; v3 26 Oct 2025).
- **Venue**: **NeurIPS 2025 — Spotlight Poster** (seen on the official NeurIPS virtual site:
  https://nips.cc/virtual/2025/loc/san-diego/poster/121528 — this is off-site, and the arXiv Comments field says
  only "ArXiv v3", so treat the venue as externally confirmed rather than arXiv-confirmed).
- **URL**: https://arxiv.org/abs/2503.13657 · HTML: https://arxiv.org/html/2503.13657v3

**Exact numbers** `[fulltext]`:

| Quantity | Value |
|---|---|
| **Cohen's κ, human IAA** | **κ = 0.88** (3 annotators, 5 randomly-selected traces per round, 3 rounds) |
| **LLM annotator agreement** | accuracy **94%**, **Cohen's κ = 0.77** (OpenAI o1 model) |
| **Out-of-domain IAA** | **κ = 0.79** (2 new MAS: OpenManus, Magentic-One; 2 new benchmarks: MMLU, GAIA) |
| **# failure modes** | **14** distinct fine-grained modes |
| **# categories** | **3** |
| **Dataset size (MAST-Data)** | **1642** annotated execution traces (abstract says "**1600+**") |
| Frameworks | **7** popular MAS frameworks, 4 model families (GPT-4 series, Claude series, Qwen2.5, CodeLlama) |
| Taxonomy derivation set | **150** traces (5 open-source MAS frameworks, **6** expert annotators, each trace averaging **>15,000 lines of text**) |
| MAST-Data-human | **21** traces, each annotated by three human experts |
| MAS failure rate | **41% to 86.7%** on 7 SOTA open-source MAS |

**14 failure modes (exact IDs and names)** `[fulltext]`, Appendix A:
- **FC1. System Design Issues — 5 modes:** FM-1.1 Disobey task specification · FM-1.2 Disobey role specification ·
  FM-1.3 Step repetition · FM-1.4 Loss of conversation history · FM-1.5 Unaware of termination conditions
- **FC2. Inter-Agent Misalignment — 6 modes:** FM-2.1 Conversation reset · FM-2.2 Fail to ask for clarification ·
  FM-2.3 Task derailment · FM-2.4 Information withholding · FM-2.5 Ignored other agent's input · FM-2.6 Reasoning-action mismatch
- **FC3. Task Verification — 3 modes:** FM-3.1 Premature termination (**6.20%**) · FM-3.2 No or incomplete verification
  (**8.20%**) · FM-3.3 Incorrect verification (**9.10%**)
  (5 + 6 + 3 = 14 ✓)

**Intervention results** `[fulltext]`: MAST-guided fix in ChatDev (CEO gets final say) → **+9.4%** task success;
adding a high-level objective verification step to ChatDev → **+15.6%** task success on ProgramDev. LLM annotator
average cost **$1.80** per trace.

---

### 5. AgentDebug — arXiv:2509.25370 ✅ ID CORRECT (minor capitalisation note)

- **Exact title** `[abs]`: *Where LLM Agents Fail and How They can Learn From Failures*
  - ⚠️ Reportedly given as "…How They **Can** Learn From Failures". The arXiv page renders lowercase "can" in the
    HTML heading; title casing is inconsistent across the arXiv HTML vs. other renderings. Substance matches — **no ID mismatch**.
- **First author** `[abs]`: Kunlun Zhu (UIUC). Co-authors include Zijia Liu, Bingxuan Li, … Pan Lu, James Zou, Jiaxuan You.
- **Year** `[abs]`: 2025 (submitted 29 Sep 2025), v1 only.
- **Venue**: **UNVERIFIED.** The arXiv abs page has no Comments/venue field. An OpenReview forum exists for a paper of
  this title (https://openreview.net/forum?id=PFR4E8583W, titled "Where LLM Agents Fail And How They can Learn From
  Failures") but the venue could not be read (bot check) — **do not assert a venue.**
- **URL**: https://arxiv.org/abs/2509.25370 · HTML: https://arxiv.org/html/2509.25370v1 · Code: https://github.com/ulab-uiuc/AgentDebug

**Exact numbers** `[fulltext]` — **Table 1** (base model GPT-4.1, temperature 0):

| Method | ALFWorld S / S+M / ALL | WebShop S / S+M / ALL | GAIA S / S+M / ALL | **Average S / S+M / ALL** |
|---|---|---|---|---|
| Direct Prompting (strongest baseline) | 28.0 / 14.0 / 1.0 | 30.0 / 6.0 / 0.0 | 26.0 / 10.0 / 0.0 | **28.0 / 10.0 / 0.3** |
| Brute Force | 10.0 / 5.0 / 0.0 | 8.0 / 0.0 / 0.0 | 18.0 / 8.0 / 0.0 | 12.0 / 4.3 / 0.0 |
| Binary Search | 20.0 / 6.0 / 1.0 | 14.0 / 8.0 / 0.0 | 22.0 / 10.0 / 0.0 | 18.7 / 8.0 / 0.3 |
| **AgentDebug** | 35.0 / 28.0 / 21.0 | 42.0 / 22.0 / 14.0 | 58.0 / 44.0 / 38.0 | **45.0 / 31.3 / 24.3** |

*Metrics: S = Step Exact; S+M = Step+Module; ALL = All Correct (Step+Module+Error Type).*

- **All-correct accuracy improvement:** "24% more accurate in the All-Correct metric (**24.3% vs. 0.3%**)" → **+24.0 points**.
- **Step accuracy improvement:** "**improves Step accuracy by 61% (45.0% vs. 28.0%)**" → **+17.0 points**.
  ⚠️ The **abstract** phrases the same gain as "**17% higher step accuracy**" (percentage *points*), while the body says
  **61%** (relative). Both refer to 45.0 vs 28.0. Quote the raw pair (45.0% vs 28.0%) and state which framing you mean.
- **GAIA specifically:** Step accuracy "**nearly doubles (58.0% vs. 30.0%)**"; All-Correct "**triples (38.0% vs. 12.0%)**".
- **Recovery improvement:** "**up to 26% relative improvements in task success**" across ALFWorld, GAIA, WebShop
  (specifically "improvements of up to **26% on ALFWorld**"). ALFWorld raw: GPT-4o-mini **21 → 55**; Qwen3-8B **48 → 74**;
  Qwen3-Next-80B **60 → 84**.
- **Base-model ablation:** GPT-4.1 → **42% step accuracy, 32% strict all-correct**; Llama-3.3-70B, GPT-4o-mini,
  Qwen3-Next-80B perform markedly worse.
- **Rollout ablation:** Modular rollout best at **0.38** on ALFWorld (zero-shot).

⚠️ **Internal inconsistency flagged:** the §4.2 "Findings" paragraph states AgentDebug achieves
"**50.0% step accuracy and 42.5% all-correct accuracy**", which does **not** match Table 1's averages (45.0% / 24.3%).
Do not cite 50.0/42.5 without noting the conflict; the Table 1 + abstract numbers are the safer canonical pair.

**Taxonomy / benchmark** `[fulltext]`:
- **AgentErrorTaxonomy**: **5 modules** — memory, reflection, planning, action, plus a system-level category.
- **AgentErrorBench**: **200 annotated failure trajectories** = **100 ALFWorld + 50 WebShop + 50 GAIA**;
  **10 expert annotators**; inter-annotator agreement **Cohen's κ = 0.55** ("substantial agreement");
  3 rounds of pilot annotation. Most failures cluster in mid-trajectory steps **6–15**.

---

### 6. "Characterizing the Failure Modes of LLMs in Resolving Real-World GitHub Issues" — arXiv:2605.12270 ✅ ID CORRECT, TITLE CORRECT

- **Exact title** `[abs]` **and** `[PDF header]`: *Characterizing the Failure Modes of LLMs in Resolving Real-World GitHub Issues* — matches exactly.
- **First author** `[abs]`: Yanjie Jiang. Co-authors: Yian Huang, Guancheng Wang (Member, IEEE), Junjie Chen, Hui Liu, Lionel Briand (Fellow, IEEE).
- **Year** `[abs]`: 2026 (submitted 12 May 2026), v1 only.
- **Venue**: **UNVERIFIED.** Abs page has no Comments field; the PDF uses an **IEEE journal-style** template
  ("Index Terms—…", "Member, IEEE" author footnotes) but names no venue or journal. No HTML version exists — PDF only.
- **URL**: https://arxiv.org/abs/2605.12270 · PDF: https://arxiv.org/pdf/2605.12270
- **Subject**: cs.SE · License: CC BY 4.0

**Setup (number of samples/trials)** `[fulltext]`:
- **100 sampled tasks** from **SWE-bench Verified**; **3 LLMs** (Claude 4.5 Sonnet, Gemini 3 Pro, GPT-5);
  **3 independent runs per task** → **900 issue-resolution attempts**. (100 × 3 models × 3 trials = 900 ✓)
- **657 resolved; 243 failed (27%)**. Manual root-cause analysis of all **243 failures**.
- Context: "according to the latest leaderboard data as of April 30, 2026, state-of-the-art models resolve only around **76.8%** of verified issues."
- Scaffold: **mini-SWE-agent** interactive framework.

**Exact stage-level failure distribution — TABLE III, n = 243** `[fulltext]`:

| Stage | Symptom | Count |
|---|---|---|
| **Problem Understanding** | P1 Misinterpretation / Domain Knowledge Lack | **44** |
| | P2 Distracted by Hints / TODOs | **27** |
| | **subtotal** | **71 = 29.2%** |
| **Localization** | L1 Incomplete Scope / Wrong Layer | **17 = 7%** |
| **Strategy & Logic** | S1 Partial Fix / Incomplete Logic | **52** |
| | S2 Incorrect Strategy / Side Effects | **29** |
| | S3 Hardcoding / Bad Practices | **9** |
| | **subtotal** | **90 = 37%** |
| **Implementation & Execution** | I1 Tool Failure / Silent State Hallucination | **4 = 1.6%** |
| **Validation & Harness Constraints** | V1 Specification-Oracle Gap | **10** |
| | V2 Strict Output Format Mismatch | **30** |
| | V3 Side Effects | **17** |
| | V4 Execution Timing Mismatch | **4** |
| | **subtotal** | **61 = 25.1%** |
| **Total** | | **243** |

*Check: 71 + 17 + 90 + 4 + 61 = 243 ✓. Percentages as stated in the paper's narrative:
Strategy & Logic **(90, 37%)**, Problem Understanding **(71, 29.2%)**, Localization "**only 7%**",
Implementation & Execution "**nearly negligible (1.6%)**", Validation & Harness Constraints **(40, 16.5%)**.
⚠️ Note the paper's own 16.5% figure covers only **V1&V2 = 40 cases**, whereas the **full Validation & Harness subtotal is 61 = 25.1%**
(V1+V2+V3+V4). Use 25.1% if you want the stage total; use 40/16.5% only for the V1&V2 sub-claim.*

**Taxonomy size:** five stages, **eleven** fine-grained categories (4+1+3+1+4 = 13 symptom rows in Table III, but the
paper states "a taxonomy comprising **five stages and eleven fine-grained categories**" — the paper's own count is 11;
Table III lists 13 P/L/S/I/V symptom labels. **Flag this as a minor internal discrepancy** and do not over-specify.)

**Headline findings** `[fulltext]`: Strategy formulation & logic synthesis is the most error-prone stage for all
evaluated LLMs, followed by Problem Understanding; **localization has the lowest failure rate** — "LLMs may excel at
fault localization". A notable finding: "existing evaluation harnesses occasionally misjudge correct patches due to
superficial discrepancies or hidden constraints" (worked example: `django-14771`, where a functionally equivalent
`['-Xutf8', '-Xa=b']` vs `f'-X{key}'` list-syntax difference is rejected by rigid test assertions).

---

### 7. AgentLocate — arXiv:2607.07989 ✅ ID CORRECT

- **Exact title** `[abs]`: *Who Broke the System? Failure Localization in LLM-Based Multi-Agent Systems* — matches exactly.
- **First author** `[abs]`: Yufei Xia. Co-authors: Anjun Gao, Yueyang Quan, Zhuqing Liu, Minghong Fang.
- **Year** `[abs]`: 2026 (submitted 8 Jul 2026), v1.
- **Venue** `[abs]`: **"To appear in COLM 2026"** (stated in the Comments field). ✅ venue verified.
- **URL**: https://arxiv.org/abs/2607.07989 · HTML: https://arxiv.org/html/2607.07989v1
- **Subjects**: cs.CR, cs.AI, cs.IR, cs.LG, cs.MA

**Metrics and exact numbers** `[fulltext]`:
- **Metrics.** Who&When → *agent-level accuracy* (responsible agent correctly identified) and *step-level accuracy*
  (decisive error step exactly localized). Aegis-Bench → *agent-level accuracy* and *pair-level accuracy*
  (both faulty agent **and** its predefined error mode). Judge = Qwen2.5-7B / Llama-3.1-8B / Mistral-7B / GPT-4o,
  each in an *all-at-once* and a *step-by-step* mode; 3 Evaluators; LoRA r=64, α=128, dropout 0.05, 3 epochs.
- **Who&When (Algorithm-Generated subset), Qwen-7B all-at-once: agent-level accuracy 69.05%** — the headline number.
- Best overall: "reaching **average agent-level accuracy above 50%**" across model/eval configurations.
- **vs. poisoning-forensics baselines:** RAGOrigin and RAGForensics both **below 34%** agent-level, vs AgentLocate's **69.05%**.
- **Evaluator-model sensitivity** (Judge fixed to Qwen-7B, Algorithm-Generated, all-at-once): agent-level **52%–69%**;
  step-level **23%–38%**.
- **# Evaluators ablation:** 1 → 3 Evaluators gives **35.71% → 69.05%** agent-level (all-at-once);
  5 or 7 bring no consistent improvement.
- **Refinement rounds:** 1 round suffices (Qwen-7B: 69.05% agent-level, Algorithm-Generated, all-at-once).
- **Aegis-Bench:** agent-level accuracy **above 50%** with Qwen-7B and Llama-8B; pair-level gains more modest.
- **Efficiency:** "**451K vs. 249K tokens** for WhichAgent on Algorithm-Generated, all-at-once" — AgentLocate runs
  **over 20× faster** than some training-free baselines.
- **Datasets:** Who&When — 50%/10%/40% train/val/test split; Algorithm-Generated subsets average **8.7 decision steps**
  per split; Hand-Crafted train/test average **49.8 and 54.2 decision steps**. Aegis-Bench — **600 test samples**,
  **8,933** training; predefined taxonomy of **14 distinct error modes**.
- **Baselines compared:** WhichAgent (Who&When), AgenTracer, ECHO, AEGIS, plus RAGOrigin and RAGForensics.

---

## 8. Other benchmarks / detectors of LLM-agent failure modes (2025–2026)

All arXiv IDs in this section were verified by fetching their arXiv abs pages. Exact titles are quoted as returned.

### ⚠️ NAME COLLISION: TWO DIFFERENT PAPERS ARE BOTH CALLED "AEGIS" / "Aegis"

Both exist and both are real. Do not conflate them; check which one a citing paper means.

| | **Aegis-A** (agent failure *attribution*) | **Aegis-B** (agent–environment *taxonomy + optimizations*) |
|---|---|---|
| Title | Aegis: Automated Error Generation and Attribution for Multi-Agent Systems | Aegis: Taxonomy and Optimizations for Overcoming Agent-Environment Failures in LLM Agents |
| First author | Fanqi Kong | Kevin Song |
| Year | 2025 (v1 17 Sep 2025; v6 27 Apr 2026) | 2025 (submitted 27 Aug 2025) |
| arXiv ID | **2509.14295** | **2508.19504** |
| Subjects | cs.RO, cs.MA | (cs.AI / cs.LG / cs.CL per page) |

- **Which is which:** the **AEGIS cited as a failure-localization baseline inside AgentLocate (2607.07989) — "AEGIS
  (Kong et al., 2025)" — is Aegis-A, arXiv:2509.14295**, and "Aegis-Bench" (600 test / 8,933 train, 14 error modes) is
  Aegis-A's benchmark. If a source says "AGentLocate compares against AEGIS", it means Aegis-A.

### 8a. Aegis-A (cited as "AEGIS") — arXiv:2509.14295 ✅
- **Title** `[abs]`: *Aegis: Automated Error Generation and Attribution for Multi-Agent Systems*
  (AgentLocate cites it as "AEGIS (Kong et al., 2025)"; the paper's own name is **Aegis**.)
- **First author**: Fanqi Kong. Co-authors: Ruijie Zhang, Huaxiao Yin, Guibin Zhang, Xiaofei Zhang, Ziang Chen, Zhaowei Zhang, Xiaoyuan Zhang, Song-Chun Zhu, Xue Feng.
- **Year**: 2025 (v1 17 Sep 2025; v6 27 Apr 2026). **Venue**: UNVERIFIED (Comments empty). Subjects: cs.RO, cs.MA.
- **URL**: https://arxiv.org/abs/2509.14295 · HTML: https://arxiv.org/html/2509.14295v6
- **Metric + exact numbers** `[fulltext]`: constructs **9,533 annotated error trajectories** across **6 MAS frameworks**
  and **6 benchmarks**; **Aegis-Bench** = **100 trajectories sampled from each of the six benchmarks = 600 test trajectories**;
  remaining data split 80% train / 20% val. **14 predefined error modes**. Three learning paradigms: SFT, RL
  (hierarchical attribution-aware reward), contrastive learning. Claim: fine-tuned LLMs "competitive with or superior to
  proprietary models an order of magnitude larger"; strong OOD generalisation to Who&When.

### 8b. AgenTracer — arXiv:2509.03312 ✅
- **Title** `[abs]`: *AgenTracer: Who Is Inducing Failure in the LLM Agentic Systems?*
- **First author**: Guibin Zhang. Co-authors: Junhao Wang, Junjie Chen, Wangchunshu Zhou, Kun Wang, Shuicheng Yan.
- **Year**: 2025 (v1 3 Sep 2025). **Venue**: UNVERIFIED (Comments empty). Subjects: cs.CL, cs.MA.
- **URL**: https://arxiv.org/abs/2509.03312 · HTML: https://arxiv.org/html/2509.03312v2 · Project: https://bingreeky.github.io/atracer/
- **Metric + exact numbers** `[fulltext]`:
  - Motivation number: "Current state-of-the-art reasoning LLMs … remain strikingly inadequate … with accuracy generally **below 10%**."
  - Dataset: **TracerTraj-2.5K** — "over **2,000** high-fidelity annotated trajectory–error step pairs" from 6 multi-agent
    frameworks × 6 datasets.
  - **AgenTracer-8B outperforms Gemini-2.5-Pro and Claude-4-Sonnet by up to 18.18% on Who&When.**
  - Who&When (hand-crafted): **+26.0%** agent-level accuracy over GPT-4.1 and **+12.2%** over Claude-4-Sonnet.
  - TracerTraj-agentic step-level: **+22.68%** over backbone Qwen3-8B, **+9.04%** over DeepSeek-R1, **+17.57%** over Gemini-2.5-Pro.
  - Downstream: **4.8~14.2%** performance gains on MetaGPT and MaAS.

### 8c. TELBench + DRIFT — arXiv:2606.02060 ✅
- **Title** `[abs]`: *Where Do Deep-Research Agents Go Wrong? Span-Level Error Localization in Agent Trajectories*
- **First author**: Jiaming Wang. Co-authors: Ziteng Feng, Jiangtao Wu, Ruihao Li, Qianqian Xie, Yuxiang Ren, He Zhu, Xueming Han, Fanyu Meng, Junlan Feng, Jiaheng Liu.
- **Year**: 2026 (v1 1 Jun 2026; v2 2 Jun 2026). **Venue**: UNVERIFIED. Comments: "28 pages, 11 figures, 4 tables". Subject: cs.AI.
- **URL**: https://arxiv.org/abs/2606.02060 · HTML: https://arxiv.org/html/2606.02060
- **Metric + exact numbers** `[fulltext]`:
  - **TELBench**: **1,000-instance** benchmark (**600 easy / 400 hard**), built from **2,790 real trajectories**
    (2 agent frameworks × 3 backbone models × 3 benchmarks = GAIA, XBench, BrowseComp); avg **11.95 spans**.
  - Metrics: **first-error accuracy**, macro precision, recall, **macro-F1**; error spans treated as span-level metrics.
  - **DRIFT improves span-level error localization and first-error accuracy by up to 30 percentage points.**
  - **DRIFT macro-F1 by backbone** (project page): GPT-5.4 **52.48** (+18.55 over bare) · DeepSeek-V3.2 **50.51** (+28.05) ·
    Claude-Sonnet-4.6 **54.91** (+33.02) · Gemini-2.5-Pro **48.41** (+17.40). Each setting repeated 3×.

### 8d. LoopsBench — arXiv:2608.00267 ✅
- **Title** `[abs]`: *LoopsBench: From Harness Engineering to Loop Engineering in Coding Agent Evaluation*
  (⚠️ note: the title includes the phrase "in Coding Agent **Evaluation**")
- **First author**: Han Li. Co-authors: Zhemin Fang, Rili Feng, Yingqi Zhao, Jiaheng Liu, Pengfei Gao, He Ye, Dayi Lin, Qingwei Lin, Saravan Rajmohan, Dongmei Zhang (Microsoft).
- **Year**: 2026 (v1 31 Jul 2026; v2 10 Aug 2026). **Venue**: UNVERIFIED. Subjects: cs.SE, cs.CL.
- **URL**: https://arxiv.org/abs/2608.00267
- **Metric + exact numbers** `[abs]`: **112 tasks**, **8 programming languages**, **9 domains**, **>5,300 development units**;
  each task is a dependency DAG over separately testable units. **Strongest configuration (Opus-4.7 with Claude Code and
  outer continuation) resolves 25.00% of tasks.** Recorded plans recover only part of the source-recovered prerequisite DAG;
  regression events remain visible across evaluated loop profiles.

### 8e. IAL-Scan — arXiv:2607.01641 ✅
- **Title** `[abs]`: *When Agents Do Not Stop: Uncovering Infinite Agentic Loops in LLM Agents*
- **First author**: Xinyi Hou. Co-authors: Shenao Wang, Yanjie Zhao, Haoyu Wang.
- **Year**: 2026 (submitted 2 Jul 2026). **Venue**: UNVERIFIED (Comments empty). Subject: cs.SE.
- **URL**: https://arxiv.org/abs/2607.01641 · HTML: https://arxiv.org/html/2607.01641
- **Metric + exact numbers** `[fulltext]`: static analyser over **6,549 real-world LLM-agent projects**; reports **74 potential
  findings**; manual review confirms **68 IAL failures and 6 false positives → end-to-end precision 91.9%**; independent
  labelling agreement **94.6%** on the 74 findings. LangGraph + AutoGen contribute **45 of 68 (66.2%)** confirmed findings
  across 31 projects. Retry feedback without bounds, tool-call iteration without bounds, and multi-agent chat without turn
  bounds account for **47 findings (69.1%)**. API-cost exhaustion and model denial-of-service each appear in **95.6%** of
  findings; **19** findings may exhaust the context window.

### 8f. FailFast–RestartSmart — arXiv:2608.03222 ✅
- **Title** `[abs]`: *Fail-Fast, Restart-Smart: Early Failure Prediction and Restart for SWE Agentic Tasks*
- **First author**: Chenyu Wang. Co-authors: Yunbo Lyu, Junda He, Zhou Yang, Chenxing Zhong, Yaniv Harel, David Lo.
- **Year**: 2026 (submitted 4 Aug 2026). **Venue**: UNVERIFIED. Subjects: cs.SE, cs.AI.
- **URL**: https://arxiv.org/abs/2608.03222
- **Metric + exact numbers** `[abs]`: a light **0.6B monitor** ("FailFast") trained with terminal + dense fail-to-pass
  supervision, on **SWE-bench Verified**. A monitor trained solely on **Qwen3.6-27B** trajectories transfers to three other
  policies (including a closed-API model) and **saves 14.6%–20.4% of execution tokens at a target 5% false-positive rate**.
  On Qwen3.6-27B its **20.4%** saving **exceeds the 12.5%** achieved by their per-step **AgentStop** adaptation.
  At a target **25% FPR**, RestartSmart raises Qwen3.6-27B resolution **66.6% → 71.8%**, vs cold restart **66.8%**.
  ⚠️ Directly relevant: it *benchmarks against AgentStop* on SWE-bench Verified.

### 8g. PrefixGuard — arXiv:2605.06455 ✅
- **Title** `[abs]`: *PrefixGuard: From LLM-Agent Traces to Online Failure-Warning Monitors*
- **First author**: Xinmiao Huang. Co-authors: Jinwei Hu, Rajarshi Roy, Changshun Wu, Yi Dong, Xiaowei Huang.
- **Year**: 2026 (submitted 7 May 2026). **Venue**: "Under Review" per abs Comments. Subject: cs.AI.
- **URL**: https://arxiv.org/abs/2605.06455 · HTML: https://arxiv.org/html/2605.06455v1
- **Metric + exact numbers** `[abs]`/`[fulltext]`: strongest PrefixGuard monitors reach **AUPRC 0.900 / 0.710 / 0.533 / 0.557**
  on **WebArena / τ²-Bench / SkillsBench / TerminalBench**. Improves over raw-text controls by an average of
  **+0.137 AUPRC**. Best zero-shot LLM judge reaches only **0.450** AUPRC (WebArena), **<0.40** (τ²-Bench), **≈0.10**
  (SkillsBench, TerminalBench). Post-hoc DFA extraction: **29 and 20 states** (WebArena, τ²-Bench) vs **151 and 187 states**
  (SkillsBench, TerminalBench). Uses H=3-step warning labels; 10% calibration FAR cap.

### 8h. AgentForesight — arXiv:2605.08715 ✅
- **Title** `[abs]`: *AgentForesight: Online Auditing for Early Failure Prediction in Multi-Agent Systems*
- **First author**: Boxuan Zhang. Co-authors: Jianing Zhu, Zeru Shi, Dongfang Liu, Ruixiang Tang.
- **Year**: 2026 (v1 13 May 2026). **Venue**: UNVERIFIED. Subjects: cs.AI (also cs.LG per the page).
- **URL**: https://arxiv.org/abs/2605.08715 · HTML: https://arxiv.org/html/2605.08715v2 · Project: https://zbox1005.github.io/agent-foresight/
- **Metric + exact numbers** `[fulltext]`:
  - **AFTraj-2K**: **2,276** multi-agent trajectories (**1,162 safe + 1,114 unsafe**), domains Math 793, Coding 608, Agentic 875.
    Frameworks: AutoGen, MetaGPT, Smolagents. Built from MATH-500, HumanEval+/MBPP+, GAIA, HotpotQA.
  - **AgentForesight-7B: 66.44 overall Exact-F1**, **+19.88 points** above the strongest proprietary baseline
    **DeepSeek-V4-Pro**; **ASS 1.77 → 0.59 (3× tighter)**. Per-domain Exact-F1: **Math 77.36 vs 50.34**,
    **Coding 78.87 vs 49.32**. Lifts the Qwen2.5-7B-Instruct backbone by **3.16×** on Exact-F1.
    Post-hoc reference **AgentDebug-7B ranks lowest at 9.63** overall Exact-F1 (i.e. post-hoc attributors underperform online auditing).
  - **Who&When transfer:** exceeds strongest baseline GPT-4.1 by **+19.59** Step-Acc and **+6.41** Agent-Acc;
    ASS reduced from **2.35** (DeepSeek-V4-Flash) to **1.62**.
  - Note: AFTraj is sometimes written "AFTraj-22K" in the paper's notation; the released corpus is **AFTraj-2K ≈ 2.3K trajectories**.

### 8i. AgentLens — arXiv:2605.12925 ✅
- **Title** `[abs]`: *AgentLens: Revealing The Lucky Pass Problem in SWE-Agent Evaluation*
- **First author**: Priyam Sahoo. Co-authors: Gaurav Mittal, Xiaomin Li, Shengjie Ma, Benjamin Steenhoek, Pingping Lin, Yu Hu.
- **Year**: 2026 (v1 13 May 2026; v3 2 Jun 2026). **Venue**: UNVERIFIED. Subjects: cs.SE, cs.AI.
- **URL**: https://arxiv.org/abs/2605.12925 · HTML: https://arxiv.org/html/2605.12925
- **Metric + exact numbers** `[fulltext]`: **2,614 OpenHands trajectories** on **60 SWE-bench Verified tasks** across
  **8 model backends** (1,389 pass / 1,217 fail / 8 unrecorded). **47 of 60 tasks** are PTA-eligible →
  **AgentLens-Bench = 1,815 trajectories** (1,136 passing / 679 failing).
  **10.7% of passing trajectories are "Lucky Passes"** (correct patch via weak process); decomposed into **5 mechanisms**
  (χ²(28) = 102.47, p < 0.0001); **C2 Brute-Force Convergence + C3 Incomplete Implementation = 68.0%** of Lucky Passes.
  Across models, Lucky rate ranges **0.5% to 23.2%**. Quality tiers: **20.2% Ideal, 69.1% Solid** (rest Lucky).
  Composite score separates passing from failing: **AUROC = 0.766, accuracy = 72.0%, F1 = 0.723, KS p = 0.0017**.
  Some models move up to **five rank positions** when ranked by quality score instead of pass rate.

### 8j. FALAT — arXiv:2606.00765 ✅
- **Title** `[abs]`: *FALAT: Tracing Failures in LLM Agent Trajectories via Dependency-Guided Search*
- **First author**: Md Nakhla Rafi. Co-authors: Md Ahasanuzzaman, Dong Jae Kim, Zhijie Wang, Tse-Hsun Chen.
- **Year**: 2026 (submitted 30 May 2026). **Venue**: UNVERIFIED. Subject: cs.AI.
- **URL**: https://arxiv.org/abs/2606.00765 · HTML: https://arxiv.org/html/2606.00765v1
- **Metric + exact numbers** `[abs]`: on **Who&When**, best configurations achieve **46.0% step-level accuracy on
  algorithm-generated** trajectories and **29.1% on the more challenging hand-crafted** trajectories, outperforming
  specialized attribution baselines and direct prompting. Uses K=3 top candidates; typed dependency relations
  (error_shift vs follow_up, dead_end, redundancy); roles Root_Cause / Propagation / Symptom / Contributing.

### 8k. SAFARI — arXiv:2606.24626 ✅
- **Title** `[abs]`: *SAFARI: Scaling Long Horizon Agentic Fault Attribution via Active Investigation*
- **First author**: Chenyang Zhu. Co-authors: Jiayu Yao, Kushal Chawla, Youbing Yin, Nathan Wolfe, Pengshan Cai, Jingyu Wu, Spencer Hong, Sangwoo Cho, Shi-Xiong Zhang, Daben Liu, Sambit Sahu, Erin Babinsky.
- **Year**: 2026 (submitted 23 Jun 2026). **Venue** `[abs]`: **"Published at the Second Workshop on Agents in the Wild:
  Safety, Security, and Beyond (AIWILD) at ICML 2026"** — a workshop, not the main conference.
- **URL**: https://arxiv.org/abs/2606.24626 · HTML: https://arxiv.org/html/2606.24626
- **Metric + exact numbers** `[abs]`: outperforms SOTA by **20% on the Who&When dataset within a 1M token budget**, and by
  **19% on the TRAIL GAIA subset on a 25K token budget**. Maintains **0.58 precision** even when the target fault resides
  **5× beyond the model's native context window**. Iteration budget K=30; verifier claims E=3; confidence threshold θ=70.

### 8l. Real-Time Detection and Repair of LLM Agent Failures — arXiv:2608.02464 ✅
- **Title** `[abs]`: *Real-Time Detection and Repair of LLM Agent Failures*
- **First author**: Sunny Dubey (sole author). **Year**: 2026 (submitted 3 Aug 2026).
- **Venue**: UNVERIFIED. Comments: "16 pages, 5 figures. Code, data and demo…". Subjects: cs.AI, cs.LG, cs.SE.
- **URL**: https://arxiv.org/abs/2608.02464
- **Metric + exact numbers** `[abs]`: on **2,823 committed agent episodes** across 3 frameworks, 3 local models
  (qwen2.5 7b/3b, llama3.1 8b) and a commercial API (gemini-2.5-flash), a one-class **echo-state-network ensemble with
  CUSUM alarms detects 0.71 of failures at a 5% false-alarm budget (AUROC 0.872)**. Advantage over a memoryless baseline is
  monotone in post-onset horizon (**+0.09 at ≤3 steps, +0.40 at ≥9**). Ranking transfers with no retraining:
  **AFTraj-2K 0.745, ATBench 0.779**. Cold **AUROC 0.527** vs recalibrated **0.885**. Deterministic verification catches
  **60%** of failures (**96%** with the coverage check) at **0 of 63 false positives**, vs the monitor's 54% at 17%;
  trips on **0 of 1,825** healthy episodes. Rollback + re-run recovers **45%** of failures vs a **16%** resampling control
  (p = 0.0005) and lifts task success **52% → 73%** for ~1 extra model call per run. Runs at **~200 microseconds per step**.

### 8m. Sherlock — arXiv:2511.00330 ✅
- **Title** `[abs]`: *Sherlock: Reliable and Efficient Agentic Workflow Execution*
- **First author**: Yeonju Ro. Co-authors: Haoran Qiu, Íñigo Goiri, Rodrigo Fonseca, Ricardo Bianchini, Aditya Akella, Zhangyang Wang, Mattan Erez, Esha Choukse.
- **Year**: 2025 (submitted 1 Nov 2025). **Venue**: UNVERIFIED. Subjects: cs.MA, cs.SE.
- **URL**: https://arxiv.org/abs/2511.00330
- **Metric + exact numbers**: **+18.3% accuracy gain on average** across benchmarks vs the non-verifying baseline;
  reduces workflow execution time by **up to 48.7%** over non-speculative execution (mean T_exec −62.9% and T_vrf −48.7%
  on LiveCodeBench); lowers verification cost by **26.0%** vs a Monte Carlo search–based method.
  Mechanism: counterfactual analysis to find error-prone nodes + selective cost-optimal verifier attachment + speculative execution with rollback.
  ⚠️ Note: this is **workflow verification**, not agent failure-mode classification — include only if relevant.

### 8n. SWE-Shepherd (process reward model for code agents) — arXiv:2604.10493 ✅
- **Title** `[abs]`: *SWE-Shepherd: Advancing PRMs for Reinforcing Code Agents*
- **First author**: Mahir Labib Dihan. Co-author: Md Ashrafur Rahman Khan.
- **Year**: 2026 (submitted 12 Apr 2026). **Venue**: UNVERIFIED. Comments: "Code is available at this https URL". Subject: cs.SE.
- **URL**: https://arxiv.org/abs/2604.10493
- **Metric + exact numbers** `[fulltext]`: evaluated on **100 tasks sampled from SWE-Bench Verified**, 30-step cap:

| Method | % Resolved | Avg. $ | Avg. Steps |
|---|---|---|---|
| SWE-Search | 31% | 0.274 | – |
| mini-SWE-Agent | 57% | 0.029 | 15.2 |
| **SWE-Shepherd (ours)** | **51%** | 0.053 | **12.2** |

  i.e. the PRM **cuts interaction steps 15.2 → 12.2** but **lowers resolution 57% → 51%** — the paper's own key caveat:
  "locally high-reward actions do not always translate to globally correct patches."

### 8o. SWE-TRACE (rubric-based PRM + test-time scaling) — arXiv:2604.14820 ✅
- **Title** `[abs]`: *SWE-TRACE: Optimizing Long-Horizon SWE Agents Through Rubric Process Reward Models and Heuristic Test-Time Scaling*
- **First author**: Hao Han. Co-authors: Jin Xie, Xuehao Ma, Weiquan Zhu, Ziyao Zhang, ZhiLiang Long, Hongkai Chen, Qingwen Ye.
- **Year**: 2026 (submitted 16 Apr 2026). **Venue**: UNVERIFIED. Subject: cs.SE.
- **URL**: https://arxiv.org/abs/2604.14820
- **Metric + exact numbers**: builds a **60K-instance SFT corpus** by filtering **140K candidate instances** across **77 repositories**;
  memory-augmented agentic RL with a **rubric-based PRM**; reuses the PRM for heuristic-guided test-time scaling (HG-TTS).
  Models: **SWE-TRACE-4B and SWE-TRACE-30B**, reported "strong performance on SWE-bench Verified" with improved token
  efficiency and search control. ⚠️ **The abstract and the retrieved paper body do not state a single headline resolution
  percentage** — do **not** invent one. Exact per-benchmark numbers would need the results tables.

### 8p. ATBench — arXiv:2604.02022 ✅
- **Title** `[abs]`: *ATBench: A Diverse and Realistic Agent Trajectory Benchmark for Safety Evaluation and Diagnosis*
- **First author**: **UNVERIFIED** (the abstract page was reached via a secondary source; I did not read the author list
  off arXiv directly in this session. Verify before citing.) Cited in AgentForesight as "Y. Li, H. Luo, Y. Xie, Y. Fu, … (2026)".
- **Year**: 2026. **Venue**: UNVERIFIED.
- **URL**: https://arxiv.org/abs/2604.02022
- **Metric + exact numbers**: **1,000 trajectories (503 safe, 497 unsafe)**, averaging **9.01 turns** and **3.95k tokens**,
  **1,954 invoked tools** from a pool of **2,084**. Taxonomy: risk source / failure mode / real-world harm.
  **GPT-5.4: 76.7% F1 binary safety classification; 33.6% risk-source diagnosis; 13.5% failure mode; 30.2% real-world harm.**
  Gemini-3-Flash 74.9% F1; Gemini-3.1-Pro 75.0%; AgentDoG-Qwen3-4B 71.1% coarse F1 with the best fine-grained
  (46.8% risk source, 16.5% failure mode, 40.6% harm). Human audit produced 5 binary + 165 fine-grained corrections.

### 8q. AgentFixer — arXiv:2603.29848 ✅
- **Title** `[abs]`: *AgentFixer: From Failure Detection to Fix Recommendations in LLM Agentic Systems*
- **First author**: **UNVERIFIED.** **Year**: 2026. **Venue**: "1st International Workshop on Agentic Engineering;
  April 14, 2026; Rio de Janeiro, Brazil" (per the paper's own header).
- **URL**: https://arxiv.org/abs/2603.29848 · HTML: https://arxiv.org/html/2603.29848
- **Metric + exact numbers**: **15 failure-detection tools + 2 root-cause-analysis modules**; applied to **IBM CUGA**,
  evaluated on **AppWorld** and **WebArena**. "**parsing errors account for 38% of task failures**"; reports that failure
  detection rates in production systems "may exceed **80% of LLM calls** in complex workflows". Draws on TRAIL's tracing
  methodology. ⚠️ Qualitative/engineering contribution — it reports no single headline accuracy metric.

### 8r. DCFA — arXiv:2609.04749 ✅
- **Title** `[abs]`: *DCFA: Dual-view Causal-inspired Attribution for Failure Reasoning in LLM-based Multi-agent Systems*
- **First author**: **UNVERIFIED.** **Year**: 2026 (submitted 4 Sep 2026). **Venue**: UNVERIFIED.
- **URL**: https://arxiv.org/abs/2609.04749
- **Metric + exact numbers**: training-free; on **Who&When** across **6 LLMs**, improves **step-level accuracy by up to 8.27%
  over state-of-the-art baselines**. Combines a global causal-inspired dependency graph with local counterfactual reasoning.

### 8s. WinClick — arXiv:2503.04730 ✅ (found, but NOT a failure-mode detector)
- **Title** `[abs]`: *WinClick: GUI Grounding with Multimodal Large Language Models*
- **First author**: Zheng Hui. Co-authors: Yinheng Li, Dan Zhao, Tianyi Chen, Colby Banbury, Kazuhito Koishida (Microsoft).
- **Year**: 2025 (submitted 27 Jan 2025). **Venue**: UNVERIFIED. Subjects: cs.CL, cs.HC.
- **URL**: https://arxiv.org/abs/2503.04730
- **Numbers**: WinSpot benchmark — over **1,000 images**, **5,000 instruction-click pairs**. WinClick full fine-tune
  average **56.1%**; LoRA variant **45.6%**; base Phi-3 Vision **6.7%**. Correct prediction rate on WinSpot **56.2%**
  (461 of 1,052 predictions incorrect).
- ⚠️ **RELEVANCE FLAG: this is a Windows GUI-grounding agent, not a coding-agent failure-mode benchmark or detector.**
  It appears in the target list but does not belong in a failure-mode taxonomy. Recommend excluding it, or citing only
  as an example of a same-named unrelated system.

---

### 8b′. Aegis-B — arXiv:2508.19504 ✅ (the *other* Aegis)

- **Title** `[abs]`: *Aegis: Taxonomy and Optimizations for Overcoming Agent-Environment Failures in LLM Agents*
- **First author**: Kevin Song. Co-authors: Anand Jayarajan, Yaoyao Ding, Qidong Su, Zhanda Zhu, Sihang Liu, Gennady Pekhimenko.
- **Year**: 2025 (submitted 27 Aug 2025). **Venue**: UNVERIFIED.
- **URL**: https://arxiv.org/abs/2508.19504
- **Metric + exact numbers** `[abs]`: **142 agent traces / 3,656 turns** of agent–environment interaction across
  **5 SOTA agentic benchmarks**; proposes a taxonomy of agent–environment interaction failures with **6 failure modes**.
  Its *Aegis* system (environment optimizations: observability enhancement, common computation offloading, speculative
  agentic actions) improves agent success rates by **6.7–12.5% on average**, with no modification to the agent or LLM.

### 8v. Who&When Pro — arXiv:2607.09996 ✅
- **Title** `[abs]`: *Who&When Pro: Can LLMs Really Attribute Failures in AI Agents?*
- **First author**: Jiale Liu. Co-authors: Huajun Xi, Shaokun Zhang, Yifan Zeng, Tianwei Yue, Chi Wang, Jian Kang, Qingyun Wu, Huazheng Wang.
- **Year**: 2026 (submitted 10 Jul 2026). **Venue**: UNVERIFIED.
- **URL**: https://arxiv.org/abs/2607.09996
- **Metric + exact numbers** `[abs]`: a large-scale failure-attribution benchmark built with a strictly controlled
  pipeline that "injects a failure only after exactly replaying a successful prefix": **12,326 failed trajectories with
  golden labels**, across **3 modalities** and **26 benchmarks**. ⚠️ The abstract states no single headline accuracy
  number — pair with the ICML 2025 Who&When paper (8t) rather than substituting for it.

### 8w. ToolFailBench — arXiv:2607.04686 ✅ (very on-topic for tool-use failure)
- **Title** `[abs]`: *ToolFailBench: Diagnosing Tool-Use Failures in LLM Agents*
- **First author**: Harsh Soni (sole author). **Year**: 2026 (submitted 6 Jul 2026).
- **Venue** `[abs]`: **"Published at the Workshop on Agents in the Wild: Safety, Security, and Beyond (AIWILD) and the
  Workshop on Failure Modes of Agentic AI (FAGEN) at ICML 2026"** — two workshops.
- **URL**: https://arxiv.org/abs/2607.04686
- **Metric + exact numbers** `[abs]`: **1,000 tasks** across finance, medicine, law, cybersecurity, real estate.
  Per-trace failure labels: **Tool-Skip, Result-Ignore, Output-Fabrication, Unnecessary-Tool-Use**.
  Across **19 headline models**, the best reaches **86.33% Clean Tool-Use Rate**. **Llama-3.1-70B and Qwen2.5-72B
  differ by 89 percentage points on control-task accuracy at the same parameter scale**; Llama-3.1 models show an
  "Always-Call" pattern.

### 8x. Model or Harness? (interaction-centric taxonomy) — arXiv:2607.28802 ✅
- **Title** `[abs]`: *Model or Harness? An Interaction-Centric Taxonomy for Localizing Agent Failures*
- **First author**: Harsh Raj. Co-authors: Vipul Gupta, Anas Mahmoud, Razvan-Gabriel Dumitru, Darvin Yi, Aakhar Sabharwal, Yunzhong He.
- **Year**: 2026 (submitted 30 Jul 2026). **Venue**: UNVERIFIED.
- **URL**: https://arxiv.org/abs/2607.28802
- **Metric + exact numbers** `[abs]`: an interaction-centric taxonomy organizing **41 failure modes**, each assigned to
  an edge between two components plus a fault side (model-side / harness-side / environment / grader).
  Evaluated for reproducibility with independent reasoning agents as judges: **strongest of four frontier models reaches
  Cohen's κ = 0.76** against human category labels. Applies from coding assistants to long-horizon assistants and MAS.

### 8y. EarlyEval — arXiv:2609.02783 ✅ (early outcome prediction)
- **Title** `[abs]`: *EarlyEval: Cheaper Agent Evaluation via Early Outcome Prediction*
- **First author**: Yuling Shi. Co-authors: Zhensu Sun, Junsen Dong, Chengcheng Wan, David Lo, Xiaodong Gu.
- **Year**: 2026 (submitted 2 Sep 2026). **Venue**: UNVERIFIED.
- **URL**: https://arxiv.org/abs/2609.02783
- **Metric + exact numbers** `[abs]`: a pair of LightGBM success/failure classifiers over behavioral, textual and
  reference-solution features, halting a run when either crosses a calibrated threshold. Across **SWE-bench Verified,
  TerminalBench, Toolathlon**: eliminates **13%–26% of agent steps** and up to **44.1% of input tokens** and
  **29.4% of output tokens** at **89%–97% prediction accuracy**, perturbing per-agent resolve rates by only
  **1–2 percentage points** on average.

### 8z. Doomed from the Start (hidden-state probe cascade) — arXiv:2607.06503 ✅
- **Title** `[abs]`: *Doomed from the Start: Early Abort of LLM Agent Episodes via a Recall-Controlled Probe Cascade*
- **First author**: Kai Ruan. Co-authors: Zihe Huang, Ziqi Zhou, Qianshan Wei, Jinghao Lin, Xuan Wang, Hao Sun.
- **Year**: 2026 (v1 7 Jul 2026; v2 16 Jul 2026). **Venue**: UNVERIFIED.
- **URL**: https://arxiv.org/abs/2607.06503
- **Metric + exact numbers** `[abs]`: linear probes on internal activations predict eventual task failure **from the
  first interaction round**, earlier than behavior-only monitoring. On **TextCraft** and **WebShop** with Qwen-2.5-7B,
  Llama-3.2-3B, Qwen3-1.7B: cascade beats the best single-gate baseline in **every** model–environment pair, saving
  **1.5–8.8× more compute at a 90% recall target**. Strongest settings cut generated tokens by **60.2% (TextCraft)** and
  **54.9% (WebShop)** at 90% recall, retaining **45.0% / 41.5%** savings at 95% recall. Recall within one SD of target in
  **all 24 configurations**. Behavior-only monitoring consistently weaker.

### 8aa. Premature Commitment — arXiv:2606.22936 ✅
- **Title** `[abs]`: *When Agents Commit Too Soon: Diagnosing Premature Commitment in LLM Agents*
- **First author**: Aman Mehta (sole author). **Year**: 2026 (submitted 22 Jun 2026).
- **Venue**: UNVERIFIED. Comments: "22 pages, 16 figures. Primary: cs.AI. Secondary: cs.CL".
- **URL**: https://arxiv.org/abs/2606.22936
- **Metric + exact numbers** `[abs]`: defines *representational commitment* as cross-run hidden-state convergence at a
  fixed reasoning step. On **Llama-3.1-70B / ReAct / HotpotQA**, step-4 hidden-state similarity predicts downstream
  behavioral consistency at **r = −0.35 (partial r = −0.45)**; replicates on Qwen-2.5-72B and Phi-3-14B, and on
  **StrategyQA r = −0.83**. Runtime monitor detects inconsistent trajectories from hidden states at **AUROC up to 0.97
  (0.85–0.88 under a stricter split)**; a prompting intervention cuts behavioral variance by **28%** vs a token-matched
  control while leaving accuracy statistically unchanged. ⚠️ **Important negative result: the signal does NOT track
  correctness** — committed-wrong and committed-correct are not separable in activation similarity.

---

## 9. Coding-agent-specific failure studies & runtime monitors (extra sweep)

⚠️ **Provenance note:** for every row below I **independently fetched `https://arxiv.org/abs/<id>`** and confirmed the
**title, first author, date and Comments/venue**. Where the quoted numbers came from an abstract read during the sweep
rather than from full text I downloaded myself, the number is marked `[abs·sweep]` — the *title* is verified, the
*number* should be spot-checked against the source before it goes in a paper.

### 9a. Coding-agent failure taxonomies / empirical studies

| arXiv ID | Exact title | 1st author | Year | Venue | Metric + exact numbers |
|---|---|---|---|---|---|
| 2603.25764 | Confident and Wrong: Silent Semantic Failures in Coding Agents | Aman Mehta | 2026 | UNVERIFIED | 1,750 trajectories / 50 SWE-bench Verified tasks; GPT-5 submits 100% but resolves 44%; Llama 4 99%/18%; Gemini 70%/50%; **SSFR = 80% (Llama 4), 68% (GPT-5), 40% (Claude), 16% (Gemini)** |
| 2604.02547 | Beyond Resolution Rates: Behavioral Drivers of Coding Agent Success and Failure | Tural Mehtiyev | 2026 | UNVERIFIED | **9,374 trajectories**, 19 agents (8 frameworks × 14 LLMs), 500 SWE-bench Verified tasks; resolved agents avg **44.0 steps vs 39.6** for failed (10.0% longer); length–failure correlation **reverses** under difficulty control |
| 2607.09510 | Failure as a Process: An Anatomy of CLI Coding Agent Trajectories | Xiangxin Zhao | 2026 | UNVERIFIED | 3,843 trajectories → **1,794 valid (1,184 failed / 610 successful)** on Terminal-Bench, >63,000 steps; failed runs median **27 steps** but decisive error at **step 7**; median recovery window **1 step**; first observable signal ≈**step 16** |
| 2603.24631 | Coherence Collapse: Diagnosing Why Code Agents Fail After Reaching the Right Code | Myeongsoo Kim | 2026 | UNVERIFIED | **16,758 trajectories**; **Edit-Quality is modal: 60–69%** of failures on SWE-Agent/OpenHands reach+edit correct functions yet fail; Coherence Collapse **39.7%** (SWE-bench) / **32.3%** (PolyBench); IAA **κ=0.80**; edit-commit checkpoint recovers **5/5** bit-identical-to-gold cases; consensus **+3.0 pp** Pass@1 (p=0.08) |
| 2511.00197 | Understanding Code Agent Behaviour: An Empirical Study of Success and Failure Trajectories | Oorja Majgaonkar | 2025 | UNVERIFIED | `[abs·sweep]` "most trajectories correctly identify problematic files (**72–81% even in failures**)"; failed trajectories consistently longer with higher variance |
| 2509.13941 | An Empirical Study on Failures in Automated Issue Solving | Simiao Liu | 2025 | UNVERIFIED | `[abs·sweep]` manual analysis of **150 failed instances**; taxonomy of **3 primary phases, 9 main categories, 25 fine-grained subcategories** |
| 2608.11888 | Agent Skills Can Be Harmful: An Empirical Study of Skill-Induced Failures in LLM Agents | Gen Dong | 2026 | UNVERIFIED | `[abs·sweep]` **307 skill-induced failures** = 125 functional + 182 efficiency regressions; excessive verification and heavy implementation pipelines contribute **67 and 30** cases |
| 2607.17937 | When and How Context Rot Appears in Coding Agents: A White-Box Study of Agent Skills in Code Auditing | Yue Xue | 2026 | UNVERIFIED | `[abs·sweep]` Codex/gpt-5.4-mini passes **8/10** runs at 10,991-char clean context vs **3/10** at both 299,140-char relevant and equal-length irrelevant context (p=0.0698); checklist **10/10 vs 5/10** for generic self-check (p=0.0325) |
| 2606.09863 | From Confident Closing to Silent Failure: Characterizing False Success in LLM Agents | Laksh Advani | 2026 | **FAGEN @ ICML 2026** (abs states) | 9,876 tau2-bench + 1,879 AppWorld trajectories; false success = **45–48%** of failures (single-control tau2), 3% (dual-control telecom), **75.8%** (AppWorld self-assessing coding-agent); LLM judges **≤AUROC 0.65** vs TF-IDF **0.83 / 0.95** at **3,300× lower latency** |

### 9b. Runtime monitors, early-warning & process supervision for coding agents

| arXiv ID | Exact title | 1st author | Year | Venue | Metric + exact numbers |
|---|---|---|---|---|---|
| 2509.02360 | When Agents go Astray: Course-Correcting SWE Agents with PRMs | Shubham Gandhi | 2025 | UNVERIFIED | `[abs·sweep]` closed-source PRMs improve SWE-bench Verified resolution **40.0% → 50.6% (+10.6 pp)**; added cost "as low as $0.2" |
| 2608.06701 | Online Monitoring and Corrective Steering of Programming Agents | Shuyang Liu | 2026 | UNVERIFIED | `[abs·sweep]` LivePlan on SWE-agent gains **up to 15.2% (avg 9.9%)** at **+$0.08 per instance** |
| 2602.06443 | TrajAD: Trajectory Anomaly Detection for Trustworthy LLM Agents | Yibing Liu | 2026 | UNVERIFIED | `[fulltext]` builds **TrajBench** (perturb-and-complete); TrajAD **Macro-F1 +11.38% → 81.81%** vs strongest baseline; **Joint Exact Match +48.21% → 53.75%**; baseline JEM **<10%**; zero-shot Qwen3-4B P=79.07%/R=68.97%, Phi-3 recall 28.46% |
| 2601.00516 | Trajectory Guard — A Lightweight, Sequence-Aware Model for Real-Time Anomaly Detection in Agentic AI | Laksh Advani | 2026 | **AAAI Trustagent 2026** (abs states) | `[fulltext]` F1 **0.88–0.94** on synthetic (weighted avg 0.92), recall **0.86 (RAS-Eval) / 0.92 (Who&When)**; **32 ms** latency, **17–27× faster** than LLM judges; F1 0.96 for 2–5 steps vs 0.87 for 11+ |
| 2511.04032 | Detecting Silent Failures in Multi-Agentic AI Trajectories | Divya Pathak | 2025 | UNVERIFIED | `[abs·sweep]` two datasets of **4,275 and 894** trajectories; accuracies **up to 98% and 96%** (XGBoost / SVDD) |
| 2609.06835 | Skynet: Workflow-Level Anomaly Detection for Agentic AI via Semantic and Structural Modeling | Chaoyu Zhang | 2026 | **ACM MobiHoc 2026** (abs states) | `[abs·sweep]` "sustains high recall together with a **sub-1% false positive rate**"; trains only on benign workflows (zero-day framing) |
| 2512.07850 | SABER: Small Actions, Big Errors — Safeguarding Mutating Steps in LLM Agents | Alejandro Cuadron | 2025 | submitted to ICLR 2026 (abs states) | `[abs·sweep]` each additional deviation in a mutating action reduces odds of success by **up to 92% (Airline) / 96% (Retail)**; gains **+28% Airline, +11% Retail, +7% SWE-Bench Verified** |
| 2608.23670 | Automata from Agent Traces: Failure and Next-Step Prediction | Seonglae Cho | 2026 | UNVERIFIED | `[abs·sweep]` FSMs compact (**7–43 states**), replay held-out data at **≥0.997 fitness**; per-state behavioral features reach held-out **AUROC up to 0.94** |
| 2605.21347 | Insights Generator: Systematic Corpus-Level Trace Diagnostics for LLM Agents | Akshay Manglik | 2026 | UNVERIFIED | `[abs·sweep]` human experts using IG reports improve scaffold performance by **30.4 pp** over the unmodified baseline scaffold |
| 2608.05199 | Post-Hoc Trajectory-Risk Certification for Modular LLM-Based Security Agents | Zhenpeng Li | 2026 | UNVERIFIED (preprint) | `[abs·sweep]` direct audit becomes **13.7% tighter than Bonferroni** once the audit reaches required sample size, but worse when undersized |
| 2410.09117 | REDO: Execution-Free Runtime Error Detection for COding Agents | Shou Li | 2024 | UNVERIFIED | `[abs·sweep]` **+11.0% accuracy and +9.1% weighted F1** over prior SOTA; **SWEDE** benchmark derived from SWE-Bench (lite). Canonical earlier work. |

### 9c. Step-level evaluation / attribution infrastructure

| arXiv ID | Exact title | 1st author | Year | Venue | Metric + exact numbers |
|---|---|---|---|---|---|
| 2604.23581 | AgentEval: DAG-Structured Step-Level Evaluation for Agentic Workflows with Error Propagation Tracking | Dongxin Guo | 2026 | **ACL 2026 Industry Track** (abs states) | `[abs·sweep]` **2.17× higher failure-detection recall** than end-to-end (**0.89 vs 0.41**), **Cohen's κ = 0.84**, **72% root-cause accuracy** vs an **81% human ceiling**; DAG modelling alone **+22 pp** detection recall and **+34 pp** root-cause accuracy |
| 2605.14865 | Holistic Evaluation and Failure Diagnosis of AI Agents | Netta Madvil | 2026 | UNVERIFIED | `[abs·sweep]` on TRAIL/GAIA/SWE-Bench: **up to 38% category F1**, **up to 3.5× localization accuracy**, **up to 12.5× joint localization-categorization accuracy** |
| 2604.16335 | Beyond Verifiable Rewards: Rubric-Based GRM for Reinforced Fine-Tuning SWE Agents | Jiawei Huang | 2026 | UNVERIFIED | `[abs·sweep]` **no hard number in the abstract** — claims rubric GRM beats terminal-score-only rejection sampling and "ultimately improves final test accuracy". **Do not attribute a figure.** |
| 2511.21654 | EvilGenie: A Reward Hacking Benchmark | Jonathan Gabor | 2025 (v2 2026) | UNVERIFIED | `[abs·sweep]` "explicit reward hacking by **both Codex and Claude Code**, and misaligned behavior by all three agents"; three measurement methods incl. test-file-edit detection |
| 2608.29646 | Detect Before You Attribute: Cascade Failure Attribution for Multi-Agent Systems | Jiayi Zhang | 2026 | UNVERIFIED | **METRIC UNVERIFIED** — proposes DUOTRACE (VAE + Tree-LSTM detect-before-attribute filter); no metric captured. |
| 2606.03467 | StepFinder: A Temporal Semantic Framework for Failure Attribution in Multi-Agent Systems | Taiyu Zhu | 2026 | **KDD 2026** (abs states) | **METRIC UNVERIFIED** — lightweight attribution model replacing LLM-over-raw-trajectories; no metric captured. |

---



| Name | Status |
|---|---|
| **AEGIS** | ✅ FOUND — but **TWO different papers share the name**. Aegis-A arXiv:2509.14295 (Kong et al.; the one AgentLocate cites and whose Aegis-Bench it uses) and Aegis-B arXiv:2508.19504 (Kevin Song et al., agent–environment failures). See the collision table above. |
| **AgenTracer** | ✅ FOUND, arXiv:2509.03312 (see 8b). |
| **TELBench** | ✅ FOUND, arXiv:2606.02060 (see 8c). |
| **DRIFT** | ✅ FOUND, arXiv:2606.02060 (see 8c) — an auditing framework, not a separate paper. |
| **LoopsBench** | ✅ FOUND, arXiv:2608.00267 (see 8d). |
| **IAL-Scan** | ✅ FOUND, arXiv:2607.01641 (see 8e). |
| **WinClick** | ⚠️ FOUND (arXiv:2503.04730) but **off-topic** — GUI grounding, not failure detection (see 8s). |
| **Sherlock** | ✅ FOUND, arXiv:2511.00330 (see 8m) — workflow verification, weakly on-topic. |
| **AgentFaultLocator** | ❌ **NOT FOUND / UNVERIFIED.** No arXiv paper by this name surfaced in searches. Likely misremembered or a non-arXiv/renamed system. **Do not cite without a direct source.** |
| "early failure prediction" | ✅ Multiple found: FailFast–RestartSmart (2608.03222), AgentForesight (2605.08715), PrefixGuard (2605.06455), Real-Time Detection and Repair (2608.02464), AgentStop (2605.15206). |
| "process reward model for coding agents" | ✅ Found: SWE-Shepherd (2604.10493), SWE-TRACE (2604.14820). |

---

### 8t. Who&When — arXiv:2505.00212 ✅ ⭐ **FOUNDATIONAL — cite this one**

- **Title** `[abs]`: *Which Agent Causes Task Failures and When? On Automated Failure Attribution of LLM Multi-Agent Systems*
- **First author**: Shaokun Zhang. Co-authors: Ming Yin, Jieyu Zhang, Jiale Liu, Zhiguang Han, Jingyang Zhang,
  Beibin Li, Chi Wang, Huazheng Wang, Yiran Chen, Qingyun Wu (Penn State / Duke / UW / NTU / Meta / Google DeepMind / AG2AI).
- **Year**: 2025 (v1 30 Apr 2025; v3 2 Jun 2025). Comments field `[abs]`: **"camera-ready"**.
- **Venue**: **ICML 2025** — PMLR v267, pp. 76583–76599
  (https://proceedings.mlr.press/v267/zhang25cq.html). Confirmed via the published proceedings, not the arXiv page.
- **URL**: https://arxiv.org/abs/2505.00212 · Code/data: https://github.com/mingyin1/Agents_Failure_Attribution
- **Metric + exact numbers** `[abs]`/`[fulltext]`: the **Who&When dataset** comprises failure logs from **127 LLM
  multi-agent systems**, with **184 distinct failure annotation tasks**, split into *Algorithm-Generated* and
  *Hand-Crafted* subsets. Three methods evaluated (All-at-once, Step-by-step, Binary search):
  **best method achieves 53.5% accuracy identifying the failure-responsible agent but only 14.2% pinpointing the failure
  step**; some methods perform **below random**. On the hand-crafted subset the best step-level result was only **8.77%**.
  Even OpenAI o1 and DeepSeek R1 "fail to achieve practical usability."
- **Why it matters:** this is the **shared evaluation benchmark** behind AgentLocate (2607.07989), AgenTracer
  (2509.03312), FALAT (2606.00765), DCFA (2609.04749), AgentForesight (2605.08715), ECHO (2510.04886) and SAFARI
  (2606.24626). AgentLocate cites it as "Zhang et al., 2025d"; **WhichAgent** is its associated method.

### 8u. ECHO — arXiv:2510.04886 ✅

- **Title** `[abs]`: *Where Did It All Go Wrong? A Hierarchical Look into Multi-Agent Error Attribution*
- **First author**: Adi Banerjee. Co-authors: Anirudh Nair, Tarik Borogovac (all Amazon Web Services).
- **Year**: 2025 (v1 6 Oct 2025; v2 16 Oct 2025). **Venue**: UNVERIFIED. Subjects: cs.AI, cs.MA.
- **URL**: https://arxiv.org/abs/2510.04886 · HTML: https://arxiv.org/html/2510.04886v1
- **Metric + exact numbers** `[fulltext]`: evaluated on **Who&When** across 4 conditions (Algorithm-Generated /
  Hand-Crafted × with / without ground truth). **Agent-level accuracy ≈68% consistently (hand-crafted 68.4%,
  algorithm-generated 68.8%)**, degrading only 1–2% when ground truth is withheld. **Step-level exact match 27–28%**;
  improves to **42.1%** at **±3 steps** and **61.4%** at **±5 steps** (hand-crafted, with ground truth).
  ECHO = hierarchical context representation + panel of k objective analysis agents + confidence-weighted consensus voting.

---

## Named systems: resolution status

| Name | Status |
|---|---|
| **AEGIS** | ✅ FOUND — but **TWO different papers share the name**. Aegis-A arXiv:2509.14295 (Kong et al.; the one AgentLocate cites and whose Aegis-Bench it uses) and Aegis-B arXiv:2508.19504 (Kevin Song et al., agent–environment failures). See the collision table in §8. |
| **AgenTracer** | ✅ FOUND, arXiv:2509.03312 (§8b). |
| **TELBench** | ✅ FOUND, arXiv:2606.02060 (§8c). |
| **DRIFT** | ✅ FOUND — **not a separate paper**: DRIFT is the claim-centric auditing method *inside* the TELBench paper, arXiv:2606.02060 (§8c). |
| **LoopsBench** | ✅ FOUND, arXiv:2608.00267 (§8d). |
| **IAL-Scan** | ✅ FOUND, arXiv:2607.01641 (§8e). |
| **WinClick** | ⚠️ FOUND (arXiv:2503.04730) but **off-topic** — Windows GUI grounding (WinSpot), not failure detection. Recommend excluding (§8s). |
| **Sherlock** | ✅ FOUND, arXiv:2511.00330 (§8m) — agentic-workflow verification + speculative execution + rollback. Adjacent, not a failure-mode taxonomy. No other Sherlock detector found. |
| **AgentFaultLocator** | ❌ **NOT FOUND / UNVERIFIED.** arXiv search returns 0 results. Two independent searches found nothing. **Do not cite.** |
| "early failure prediction" | ✅ Many found: FailFast–RestartSmart (2608.03222), AgentForesight (2605.08715), PrefixGuard (2605.06455), Real-Time Detection & Repair (2608.02464), Doomed from the Start (2607.06503), EarlyEval (2609.02783), AgentStop (2605.15206). |
| "process reward model for coding agents" | ✅ Found: SWE-Shepherd (2604.10493), SWE-TRACE (2604.14820), When Agents go Astray (2509.02360), Rubric-Based GRM (2604.16335), REDO (2410.09117), TrajAD (2602.06443). |

### Note reconciling two IAL-Scan repository counts
Two different counts appear in arXiv:2607.01641 and both are correct — they measure different things:
- **Abstract:** "74 potential findings, among which manual review confirms **68 IAL failures across 47 projects**, achieving **91.9% precision**." → 91.9% is the **68/74** ratio; **47** = number of projects containing those 68 failures.
- **Full text:** "LangGraph and AutoGen contribute **45 of the 68** confirmed findings (**66.2%**) across **31 projects**." → this is a *concentration* statistic about which frameworks the 68 failures cluster in.
Do not present 47 and 31 as competing totals.

---

## Additional relevant items surfaced but not fully verified

- **AgentDiet** (`Xiao and others, 2026`) — trajectory compression via LLM reflection to reduce cost; cited by
  RedundancyBench. **arXiv ID UNVERIFIED.**
- **MAST-Data** on HuggingFace: https://huggingface.co/datasets/mcemri/MAST-Data
- **TRAIL** on HuggingFace: https://huggingface.co/datasets/PatronusAI/TRAIL
- **AFTraj-2K** on HuggingFace: https://huggingface.co/datasets/ZBox008003/AFTraj

---

## Confidence summary for the parent agent

**Rock-solid (read directly off arXiv abs page + full text):**
AgentStop (2605.15206) · RedundancyBench (2605.29893) · TRAIL (2505.08638) · MAST (2503.13657) ·
AgentDebug (2509.25370) · GitHub-issues failure modes (2605.12270) · AgentLocate (2607.07989) ·
Aegis (2509.14295) · AgenTracer (2509.03312) · **Who&When (2505.00212)** · **ECHO (2510.04886)** ·
TELBench/DRIFT (2606.02060) · LoopsBench (2608.00267) ·
IAL-Scan (2607.01641) · FailFast–RestartSmart (2608.03222) · PrefixGuard (2605.06455) · SAFARI (2606.24626) ·
AgentLens (2605.12925) · FALAT (2606.00765) · Real-Time Detection (2608.02464) · WinClick (2503.04730)

**Verified title/ID, but numbers came from a secondary render (re-check before publishing):**
AgentForesight (2605.08715) · ATBench (2604.02022) · AgentFixer (2603.29848) · DCFA (2609.04749) ·
Sherlock (2511.00330) · SWE-Shepherd (2604.10493) · SWE-TRACE (2604.14820) · Aegis-B (2508.19504) ·
Who&When Pro (2607.09996) · ToolFailBench (2607.04686) · Model-or-Harness (2607.28802) · EarlyEval (2609.02783) ·
Doomed from the Start (2607.06503) · Premature Commitment (2606.22936)

**§9 items — title/author/date/venue verified by me; numbers marked `[abs·sweep]` need a spot-check:**
2607.17937 · 2608.23670 · 2511.00197 · 2509.13941 · 2608.11888 · 2605.14865 · 2509.02360 · 2604.16335 · 2410.09117 ·
2604.23581 · 2511.04032 · 2609.06835 · 2512.07850 · 2608.06701 · 2511.21654 · 2608.05199 · 2605.21347
**Read from full text by me (§9):** 2603.25764 · 2604.02547 · 2607.09510 · 2603.24631 · 2606.09863 · 2602.06443 · 2601.00516
**METRIC UNVERIFIED (§9c):** 2608.29646 (DUOTRACE) · 2606.03467 (StepFinder) — venue is verified (KDD 2026 for the latter),
but no metric was captured.

**Explicit traps to avoid in the writeup:**
1. "RedundancyBench" and "MAST" are **benchmark/taxonomy names inside** papers, **not paper titles**.
2. **TWO papers are named "Aegis"** (2509.14295 Kong et al. vs 2508.19504 Kevin Song et al.). AgentLocate's "AEGIS" = the former.
3. The AgentDebug paper **contradicts itself** (45.0%/24.3% in Table 1 vs 50.0%/42.5% in the findings paragraph).
4. The GitHub-issues paper's "16.5%" covers only V1&V2 (40 cases); the full Validation stage is 61 = 25.1%.
5. AgentStop's abstract "15–20%" understates its own per-dataset results (20%/25%/18–19%).
6. **WinClick (2503.04730) is off-topic** — Windows GUI grounding, not failure detection.
7. **"AgentFaultLocator" is NOT FOUND on arXiv** — treat as UNVERIFIED and do not cite.
8. Venue is genuinely absent from arXiv for: RedundancyBench, TRAIL, AgentDebug, 2605.12270, and most of §8 —
   mark UNVERIFIED rather than guessing.
9. **IAL-Scan's "47 projects" and "31 projects" are different statistics**, not competing totals (see the
   reconciliation note above the Additional-items section).
10. **"DRIFT" is not a standalone benchmark** — it is the auditing method inside the TELBench paper (2606.02060).
11. **Trajectory-length-vs-failure is a confounded claim.** Two studies here disagree in direction once difficulty is
    controlled: 2604.02547 finds resolved runs are *longer* (44.0 vs 39.6 steps) on contested tasks, while
    2511.00197 and others report failures as longer. Cite the controlled result, and note the confound.
12. **2603.24631 vs 2605.12270 partly disagree on the localization story**: 2603.24631 finds 60–69% of capable-model
    failures are Edit-Quality (correct code reached, patch still wrong), which *reinforces* the GitHub-issues paper's
    "localization is not the bottleneck" finding — present them as convergent, not redundant.
13. **REDO (2410.09117) is 2024 work** — earlier than the rest of this sweep; treat as canonical prior art, not new.
