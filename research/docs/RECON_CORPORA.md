# RECON_CORPORA — public HF corpora of LLM coding-agent trajectories

Reconnaissance for the agent-stall / coding-agent-behaviour project.
Scope: public HuggingFace datasets containing **multi-step coding-agent trajectories**
(agent tool calls **and** the resulting observations), with priority on

1. scaffolds **other than SWE-agent** (OpenHands, mini-swe-agent, PI, Terminus, Claude Code, Codex, R2E, SWE-rebench…), and
2. **per-step** test / verification outcomes (not just one final reward).

Already held: `nebius/SWE-agent-trajectories` (12 shards), `yoonholee/terminalbench-trajectories` (2 shards).

---

## Method & evidence standard

* Search: `https://huggingface.co/api/datasets?search=<term>&full=true&limit=100` over 21 terms
  (`agent trajectories`, `swe-bench trajectories`, `swe-rebench`, `openhands`, `swe-agent`,
  `coding agent`, `software engineering agent`, `swe-smith`, `r2e-gym`, `swe-gym`, `nemotron`,
  `terminal-bench`, `agent rollouts`, `agentic coding`, `code agent`, `trajectories`, …).
  → **1,047 unique repo ids** (`research/_cache/recon/hf_index.json`).
* Row counts come from the **HF datasets-server `/info`** endpoint and, independently, from
  **Parquet footers read over HTTP** (`pyarrow.ParquetFile` on an fsspec URL — footer + leading
  row groups only, no shard downloaded whole). Where the two disagree, the Parquet figure is quoted.
* **Per-step outcome rates below are measured**, not quoted from cards: for each corpus a sample of
  up to 120 rows was parsed into assistant actions vs. observations, and observations were regex-scored
  for executed-test verdicts (`pytest` summaries, `PASSED/FAILED/ERROR <testid>`, `Ran N tests`,
  `AssertionError`/`Traceback`, non-zero exit codes). Scripts:
  `research/scripts/recon_hf_search.py`, `recon_hf_verify.py`, `recon_parquet.py`,
  `recon_perstep_wide.py`, `recon_nemotron.py`, `recon_mirror.py`.
* Raw evidence: `research/_cache/recon/` (`_perstep_wide.json`, `_perstep_real.json`,
  `_structured_summary.json`, `datasets/*.json`, `datasets/*.README.md`, `parquet/*.samples.json`).

**Column legend for the table**

* `%obs w/ test verdict` — share of *observation* messages carrying an executed-test verdict.
* `%rows w/ test verdict` — share of sampled rows where **at least one** step carries a test verdict.
  This is the column that matters for per-step supervision.

---

## Ranked shortlist

| # | repo id | rows (verified) | size | scaffold(s) | per-step test outcomes? | schema notes | why it matters |
|---|---|---|---|---|---|---|---|
| 1 | `nebius/SWE-rebench-openhands-trajectories` | **67,074** | 1.9 GB, 1 file (`trajectories.parquet`) | **OpenHands v0.54.0** (function calling) | **YES — strong.** 18.1 % obs; **100 % rows**. 691 `pytest` summaries, 604 non-zero exits, 366 `PASSED/FAILED` testids per 120 rows | `trajectory_id, instance_id, repo, trajectory (JSON str, OpenHands message list w/ tool_calls), tools, model_patch, exit_status, resolved, gen_tests_correct, pred_passes_gen_tests` | The flagship non-SWE-agent corpus. Real GitHub issues (1,823 repos), 64.3 avg turns (longest of any candidate — good for stall/long-horizon work). Per-trajectory **agent-written-test** verdicts are unique. Licence is clean CC-BY-4.0. |
| 2 | `thoughtworks/agentic-coding-trajectories` | **15,000** | 310 MB, 1 file (`sessions.parquet`) | **exactly balanced: `swe-agent` 5,000 / `mini-swe-agent` 5,000 / `openhands` 5,000** | YES — moderate. 4.1 % obs; **38.3 % rows**. 41 traces, 11 `pytest` summaries, 7 testids, 7 `git diff` per 120 rows | `session_id, source_dataset, source_id, agent_framework, recorded_model, messages_json, n_turns, max_isl, total_tokens, ground_truth_meta_json` | **The single best cross-scaffold artifact found.** One schema, one file, three scaffolds × 5,000 sessions drawn from the same three upstream corpora — removes the schema-matching confound from any cross-scaffold comparison. 618 K turns, p50 36 turns/session. |
| 3 | `nvidia/Nemotron-Terminal-Corpus` | `dataset_adapters/swe` **31,661**; `dataset_adapters/code` **31,960**; `synthetic_tasks/…/software_engineering/medium` **10,602**; `…/debugging/medium` **11,467** (31 files total) | 7.8 GB | **Terminus-2** (all 31,960 code rows); `model = DeepSeek-V3.2`; code source = OpenCodeReasoning | YES — **highest rate found.** code 88.3 % rows / swe 65 % / debugging 85 % / SWE-tasks 60 %. 104 testids + 13 `pytest` summaries per 60 code rows | `conversations (list<struct<content,role>>), agent, model, model_provider, date, task, episode, run_id, trial_name, enable_thinking[, source]` | A second, fully independent non-SWE-agent scaffold (Terminus) with **per-step test verdicts in most rows**, spanning 12 task domains (debugging, security, data science, sysadmin, dependency management…). NVIDIA-hosted, CC-BY-4.0, 92 k downloads. `conversations` is a *native list column*, not a JSON string. |
| 4 | `whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces` | **7,777** | 286 MB, 2 files (`data/train-0000{0,1}-of-00002.parquet`) | **PI agent** (`bash`, `read`, `edit`, `write`) | YES — **highest obs-level rate.** 19.0 % obs; **100 % rows**. 730 `pytest` summaries, 267 testids, 88 `AssertionError` per 120 rows | `task_id, messages (JSON str), tools (JSON str), num_turns` | The densest per-step test signal of any candidate, on SWE-rebench-V2 Python issues. **Caveat: only successful traces** (pass@1 0.507) → survivorship bias, no failure arm. Also the only new corpus with any editor-footprint markers (2 `(N lines total)`). |
| 5 | `Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k` | **65,994** | 1.5 GB, 47 files (`data/train-*.parquet`) | **mini-swe-agent-plus** (bash code-block loop, no function calling) | YES — 9.5 % obs; **77.5 % rows**. 173 `pytest` summaries, 99 tracebacks, 45 testids per 120 rows | `instance_id, messages (JSON str)` | The canonical **mini-swe-agent** corpus, and it is *not* the closed-source SWE-agent scaffold. All 65,994 are resolved runs (10,894 issues) → success-only again. MIT. |
| 6 | `nvidia/SWE-Zero-openhands-trajectories` | **318,115** | 11.4 GB, 64 files (`data/train-*-of-00064.parquet`) | **OpenHands** (`dataset` col = `nebius/SWE-rebench`) | YES — 7.6 % obs; **83.3 % rows**. 219 non-zero exits, 74 testids, 31 `pytest` summaries per 120 rows | `instance_id, repo, license, trajectory_id, trajectory (JSON str), model_patch, dataset` | By far the largest OpenHands pool (~4.7× the Nebius corpus) and therefore the strongest basis for a scale-robust cross-scaffold comparison. Per-row `license` field. 11.4 GB is the main cost. |
| 7 | `SWE-Gym/OpenHands-SFT-Trajectories` | **491** | **9.9 MB**, 1 file (`data/train.success.oss-00000-of-00001.parquet`) | **OpenHands** | YES — 17.6 % obs; **82.5 % rows** | `messages (JSON str)` | Trivially cheap (10 MB) OpenHands positive arm with a high per-step test rate — good as a fast unit-test fixture for the new loader. |
| 8 | `SWE-Gym/OpenHands-Sampled-Trajectories` | **6,055** | 287 MB, 3 files (`data/train.raw-*-of-00003.parquet`) | **OpenHands** (gpt-4o / claude-3-5-sonnet) | YES — 14.0 % obs; **49.2 % rows**; **plus a structured `test_result` object** | `instance_id, run_id, resolved, messages (JSON str), tools (JSON str), test_result`. `test_result` = `{apply_patch_output, git_patch, report:{empty_generation, error_eval, failed_apply_patch, resolved, test_timeout}, test_output}` | The only candidate exposing harness **evaluation metadata as a parsed dict** (`empty_generation`, `test_timeout`, `failed_apply_patch`) alongside the transcript — useful for supervised stall labels. Observations use the OpenHands `OBSERVATION:\nHere's the files and directories…` header (measured 351/1122 obs). Contains failures, not just successes. |
| 9 | `nvidia/SWE-Hero-openhands-trajectories` | **34,269** | 2.2 GB, 14 files (`data/train-*-of-00014.parquet`) | **OpenHands** | PARTIAL (verified present, rate not yet measured — see open items) | `dataset, instance_id, license, model_patch, repo, trajectory (JSON str), trajectory_id` | Mid-size OpenHands sibling of #6; useful as a second OpenHands replication arm. CC-BY-4.0. |
| 10 | `SWE-Factory/DeepSWE-Agent-Kimi-K2-Trajectories-2.8K` | **2,809** | 226 MB, 1 JSONL | **DeepSWE agent** (Kimi-K2) | YES — 20 verdicts / 164 obs steps in the first row-set; 13 non-zero exits | `messages (list, native — single JSONL)`. Also `…-Rejection-Sampling` (**729** rows, 59 MB) | Non-SWE-agent scaffold with real per-step test output; the rejection-sampling sibling gives an explicit negative arm. MIT. |
| 11 | `JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified` | **1,785** | 38 MB, 1 file (`data/train-00000-of-00001.parquet`) | mini-swe-agent-style shell loop; **teacher models recorded per step** | YES — 11.1 % obs; **67.5 % rows** | `messages, instance_id, n_turns, n_messages, selected_models (per-step model list), resolved, exit_status` | `selected_models` and `exit_status` (`Submitted` / `LimitsExceeded`) give **per-step model routing and termination reason** — directly useful for stall/handoff analysis. MIT. |
| 12 | `AlienKevin/SWE-smith-rs-minimax-m2.5-trajectories` | **5,251** | 79 MB, 21 files | SWE-agent ACI on **SWE-smith-rs** (Rust) | YES — 14.5 % obs; **97.5 % rows**; 684 `pytest` summaries, 422 `git diff` per 120 rows | `messages, instance_id, resolved, model, traj_id, patch` | Cheap, high per-step-test density, **Rust** (language diversity vs. the Python-dominated rest). MIT. Sibling `…-gpt-5-mini-trajectories` = **3,953** rows / 51 MB / 16 files. |
| 13 | `R2E-Gym/R2EGym-SFT-Trajectories` | **3,231** | 53 MB, 1 file | **OpenHands** (Claude-Sonnet-3.5-v2) | Likely yes (same agent-loop format as #8); **not yet measured** | `messages` | The OpenHands arm the Nebius card uses for its own comparison table; completes the R2E picture. |
| 14 | `hanspeterlyngsoeraaschoujensen/terminal-bench-pro-eval-trajectories` | **22** | **0.3 MB**, 1 file | **OpenHands** (model = `nebius/SWE-rebench-openhands-Qwen3-30B-A3B`) on Terminal-Bench-Pro | YES — 13.6 % rows; 7 `pytest` summaries | `instance_id, benchmark, model, messages, n_iterations, n_tool_calls, total_generation_time_s, total_tool_time_s, total_input_tokens, total_output_tokens, timings, resolved` | `timings` is a **per-iteration event list** (`{iteration, step_type: generation\|tool, time_s, tool_name, input_tokens, output_tokens}`) — explicit per-step telemetry. Tiny and free; a good format template. |
| 15 | `mlfoundations-dev/terminal-bench-traces-local` | **1,189** | 6.0 MB, 1 file | **Terminus** (claude-3-7-sonnet-20250219) | WEAK — 8.5 % obs but **only `Traceback`, no test verdicts**; 16.7 % rows | `conversations, agent, model, date, task, episode, run_id, trial_name` | Cheap Terminus sample; useful as the *predecessor* format to the Nemotron Terminus-2 corpus (#3) for a format-drift study. |
| 16 | `r2e-edits/SWE-smith-trajectories-R2E-v2` | **5,016** | 144 MB, 1 file | R2E agent on SWE-smith | YES — 11.2 % obs; **82.5 % rows**; 244 tracebacks, 96 `pytest` summaries, 93 `git diff` | `messages, instance_id` | SWE-smith replayed under a different scaffold with real per-step test output — a scaffold-swap pair against `SWE-bench/SWE-smith-trajectories`. |
| 17 | `OpenHands/CodeScout_Eval_Rollouts` | **12,711** | 196 MB, 36 files | **OpenHands / CodeScout** (localisation sub-agent) | NO executed tests (0/152 obs) — it is a localisation agent | 36 configs (`<model>/<benchmark>`), each `chat_messages, instance_id, metrics, prediction` | Not a solve-trajectory corpus, but `metrics` carries per-rollout token/cost accounting across 12 model configs — a ready-made cost/behaviour covariate table. |
| 18 | `sunnydubey1111/agent-trajectory-sentinel` | **3,581** | 6.4 MB, 1 file | 33 corpora (AutoGen, LangGraph, Ollama, Gemini); **not coding agents** | Step-level **telemetry** yes; **no code/test outcomes at all** | `uid, episode_id, corpus, model, failure_class, tau, T, n_steps, steps (JSON: text, action, latency_s, output_tokens, token_logprobs), metadata` | **Not a coding corpus** — flagging because it is the nearest published artifact to the stall-detection framing: injected `failure_class` ∈ {`looping` 269, `context_corruption` 266, `goal_drift` 235, `tool_cascade` 197, `wrong_document` 72, `malformed_json` 70, `rate_limit` 64, `timeout` 60, healthy 2,348} **with the exact onset step `tau`**. Read it as a *labeling/telemetry design template*, not as data. |
| 19 | `agent-data/misc-merged-claude-code-traces-v1` | **32,133** | 1.1 GB, 11 files | Claude Code (claude-sonnet-4-5) | NO — 0 verdicts | `id, source_table, source_repo, messages_json, system_prompt, user_prompt, assistant_response, model, timestamp, request_id, tools_json, gitdiff, claude_log, chatml, has_empty_response, content_hash` | ⚠️ **Not full sessions.** 120 rows yielded only 32 assistant / 152 observation messages and many `has_empty_response=true`. These are **per-API-request fragments**, not multi-step trajectories — do not treat as a Claude Code trajectory corpus without reconstruction. |
| 20 | `MaxDevv/real-pi-coding-agent-traces-sessions` | **UNVERIFIED** (no parquet; 998 JSONL files) | 579 MB | **PI agent, real human–AI sessions** | not yet measured | JSONL session logs: `{cwd, id, timestamp, type, version}` event records | Genuine *organic* (not benchmark-generated) PI coding sessions — the only organic, human-in-the-loop corpus found. Needs a session-reconstruction loader. Licence `other`. |
| 21 | `mondk/agentic-coding-traces` | **417** (982 files) | 127 MB | Claude Code / Codex / GLM-5.2 mixed | not yet measured | 323 `*.jsonl` session-event logs (`{payload, timestamp, type}`) + `.metadata`/`.TAG` sidecars | Small but genuinely multi-vendor scaffold logs (Kimi-K3-Codex, GLM-5.2-Agent). Apache-2.0. |
| 22 | `0xSero/glm-5.2-nf3-hybrid-terminal-bench-2.1-traces` | **UNVERIFIED** (no parquet; 657 files) | 55 MB | **Terminus-2** on Terminal-Bench 2.1 | not yet measured | per task: `recording.cast` (asciinema), `terminus_2.pane` (terminal pane dump), `trajectory.json`, plus 117 `.txt` | Full-fidelity **terminal recordings**, not just text — lets you recover timing/retry structure that message lists lose. MIT. 60 `.cast`/`.pane` task artifacts across 4 quantisation settings. |
| 23 | `Lottolabs/terminal-bench-2.1-qwen3.8-27b-traces` | **1,157** (datasets-server, single `text` column); row count per task dir **UNVERIFIED** | 55.6 MB, 502 files | local `qwen3.8-27b` harness on Terminal-Bench 2.1 | not yet measured | `text` column only; tree holds 45 `.md` transcripts, 47 `.jsonl`, 142 `.json`, 45 `.db`, 117 `.txt`. Card claims *"Complete agent trajectories, verifier output, timing and token usage for all 89 Terminal-Bench 2.1 tasks"* | Card explicitly advertises **verifier output + per-task timing and token usage** — a candidate per-step-verification source worth opening. MIT. |

---

## Explicit negative findings (measured, worth not re-checking)

* **The SWE-agent `[File: /abs/path (N lines total)]` editor footer exists in the corpus you already hold and almost nowhere else.**
  Measured on 5 rows of `nebius/SWE-agent-trajectories`: **106 occurrences** of `[File:` and 106 of `lines total`.
  By contrast, across **360 sampled rows** of `SWE-bench/SWE-smith-trajectories` (`tool`, `xml` *and* `ticks` configs)
  the count was **zero**. SWE-smith observations are plain terminal output (`OBSERVATION:\n<bash output>`).
  → A feature built on the editor footer **will not transfer** to any new corpus; the portable signal is
  test-verdict text inside observations.
* **`SWE-bench/SWE-smith-trajectories` row count is config-split, not 49,897.** Datasets-server reports
  **76,002** rows total across three configs (`tool` / `xml` / `ticks`). The Nebius card's "49,897" is a
  different snapshot/filter — quote the API figure and name the config.
* **`harithoppil/terminal-bench-2-trajectories` is single-turn despite its name.** 7,093 rows over 4 splits,
  but the schema is `task_name, model, agent, prompt, response, reward, elapsed_seconds, is_ml_related` —
  one prompt, one response, one reward. First sampled row has `response == ""`. **Not** a trajectory corpus.
* **`AlienKevin/SWE-ZERO-12M-trajectories` is 12,290,800 rows and 27.1 GB of mini-swe-agent-1 format with
  zero per-step test verdicts** (0 verdicts in 1,475 observations / 120 rows). Size ≠ per-step supervision.
  Columns: `instance_id, repo, messages, trajectory_format, exit_status, duration_sec`; Apache-2.0.
* **`SWE-Gym/OpenHands-Verifier-Trajectories`** (5,272 rows) is an **LLM-as-judge** corpus, not an execution corpus:
  messages are `[system judge prompt, user "=== INTERACTION LOG ===" (70 KB), assistant "<judgement>YES</judgement>"]`.
  The embedded log *does* retain test output, but there are only ~2 messages/row, so it is a **label source**,
  not a step sequence.
* **`R2E-Gym/R2EGym-TestingAgent-SFT-Trajectories`** (2,281 rows, `messages, exit_reasons, num_steps`) is a
  **test-generation** agent (writes a repro script), low trajectory yield in sampling (14.2 % rows) — secondary.

## Gating / access

* **`Intelligent-Internet/swebench-pro-gpt-5-codex-ii-agent-trajectories`** — `gated=auto`; the datasets-server
  returns **HTTP 401** unauthenticated, so its schema is **UNVERIFIED**. This was the only Codex-scaffold
  trajectory candidate surfaced by the search. Needs an HF token with accepted terms.
* Everything else in the table is **`gated=False` and public**; all were readable anonymously from this network.
* Licences: `cc-by-4.0` (Nebius OpenHands, both NVIDIA OpenHands corpora, Nemotron-Terminal-Corpus);
  `mit` (mini-swe-agent-plus, DeepSWE, JetBrains, SWE-smith + SWE-smith-rs, SWE-Gym OpenHands-SFT,
  0xSero, Lottolabs); `apache-2.0` (mondk, SWE-ZERO-12M, ubicloud R2E); `other` (PI real sessions,
  thoughtworks derivative-multi-source, sentinel mixed-see-licensing). Several are **blank** — notably
  `R2E-Gym/R2EGym-SFT-Trajectories`, `SWE-Gym/OpenHands-Sampled-Trajectories`,
  `whitecircle/swe-rebench-v2-…-pi-agent-…`, `OpenHands/CodeScout_Eval_Rollouts`. Treat blanks as
  "no licence granted", and note that `thoughtworks` is a derivative whose per-row terms follow `source_dataset`
  (5,000 of the 15,000 rows carry Anthropic-generated Claude 3.7 Sonnet text and inherit Anthropic's usage policy).

## Operationally important notes

* **Observations are stored as JSON strings, not nested columns**, in almost every target
  (`trajectory`, `messages`, `messages_json`, `conversations`-as-string). Loaders must `json.loads` per row.
  The exception is `nvidia/Nemotron-Terminal-Corpus`, whose `conversations` is a real
  `list<struct<content:string, role:string>>`.
* **Two role conventions coexist.** OpenHands/SWE-agent corpora alternate `assistant` → `tool`/`user`;
  the meta-judge corpus puts the whole trajectory inside one `user` message. Any step extractor must key on
  the observation prefix (`OBSERVATION:`, `<output>`, `Here's the files and directories…`) as well as on role.
* **Success-only bias is common.** #4 (PI), #5 (mini-swe-agent-plus) and `SWE-Gym/OpenHands-SFT` contain only
  resolved runs. #1, #3, #6, #8 and #11 contain genuine failures — prefer those for anything that models failure.
* `huggingface.co` became unreachable from this network mid-recon (connect timeout, not rate limiting);
  `https://hf-mirror.com` served every endpoint identically. Set `HF_ENDPOINT=https://hf-mirror.com` if fetches hang.

---

## DOWNLOAD PLAN

Ordered by (marginal evidence gained) ÷ (bytes). All paths are repo-relative on `main`.
Total for steps 1–6 ≈ **4.0 GB**; steps 7–10 add ≈ **12.5 GB**.

### Priority 1 — get a usable cross-scaffold panel for < 1 GB (do first)

1. `thoughtworks/agentic-coding-trajectories` → **`sessions.parquet`** (310 MB, 15,000 rows).
   Single file; yields `swe-agent` + `mini-swe-agent` + `openhands` at exactly 5,000 each under one schema.
   Highest information-per-byte in this whole list — start here.
2. `whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces` →
   **`data/train-00000-of-00002.parquet`** and **`data/train-00001-of-00002.parquet`** (286 MB, 7,777 rows).
   Densest per-step test signal (100 % of rows); adds a fourth scaffold (PI).
3. `SWE-Gym/OpenHands-SFT-Trajectories` → **`data/train.success.oss-00000-of-00001.parquet`** (9.9 MB, 491 rows).
   Free OpenHands fixture with 82.5 % per-step-test rows — use it to unit-test the new loader in seconds.
4. `JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified` →
   **`data/train-00000-of-00001.parquet`** (38 MB, 1,785 rows). Adds per-step model routing + `exit_status`.
5. `hanspeterlyngsoeraaschoujensen/terminal-bench-pro-eval-trajectories` →
   **`data/train-00000-of-00001.parquet`** (0.3 MB, 22 rows). Near-free; supplies the per-iteration
   `timings` event schema to crib for a telemetry extractor.

### Priority 2 — the two heavyweight non-SWE-agent corpora

6. `nebius/SWE-rebench-openhands-trajectories` → **`trajectories.parquet`** (1.9 GB, 67,074 rows).
   One file, no sharding. The primary OpenHands corpus; 100 % of sampled rows carry per-step test verdicts
   and it uniquely has agent-written-test scores (`gen_tests_correct`, `pred_passes_gen_tests`).
   If bandwidth is tight, stream it with `hf_hub_download` + `pq.ParquetFile.iter_batches` over the
   **17 row groups** rather than materialising it.
7. `nvidia/Nemotron-Terminal-Corpus` → **`dataset_adapters/code.parquet`** (815 MB, 31,960 rows)
   **+ `dataset_adapters/swe.parquet`** (1.1 GB, 31,661 rows) **+ `synthetic_tasks/skill_based/medium/debugging/data_filtered.parquet`** (329 MB, 11,467 rows).
   The Terminus-2 arm, and the highest per-step-verdict rate measured (88.3 % of code rows).
   `code.parquet` and `swe.parquet` share a schema so they concatenate cleanly.
   *(Optional later: the other 11 `synthetic_tasks/skill_based/*` domains, ~1.3 GB — debugging / security /
   data-science / sysadmin diversity.)*

### Priority 3 — scale, diversity and negative arms

8. `nvidia/SWE-Zero-openhands-trajectories` → shards **`data/train-00000-of-00064.parquet` … `-00015`** (≈ 2.9 GB, ≈ 80 k rows).
   **Do not fetch all 64 shards up front** (11.4 GB). Start with 16 shards; validated against #6 before expanding.
9. `Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k` →
   **`data/train-00000-of-00047.parquet` … `-00009`** (≈ 320 MB, ≈ 14 k rows). Same staging logic:
   10 of 47 shards is enough to characterise mini-swe-agent behaviour.
10. `SWE-Factory/DeepSWE-Agent-Kimi-K2-Trajectories-2.8K` →
    **`DeepSWE-Agent-Kimi-K2-Trajectories-2.8K.jsonl`** (226 MB, 2,809 rows) and
    **`DeepSWE-Agent-Kimi-K2-Trajectories-Rejection-Sampling.jsonl`** (59 MB, 729 rows).
    JSONL, so stream line-by-line; the rejection-sampling file is the negative arm.

### Priority 4 — cheap supplements, fetch opportunistically

11. `R2E-Gym/R2EGym-SFT-Trajectories` → **`data/train-00000-of-00001.parquet`** (53 MB, 3,231 rows) — OpenHands/R2E.
12. `SWE-Gym/OpenHands-Sampled-Trajectories` → **`data/train.raw-00000-of-00003.parquet`** (67 MB, 2,019 rows)
    — carries the structured `test_result` dict.
13. `AlienKevin/SWE-smith-rs-minimax-m2.5-trajectories` → **`data/train-00020-of-00021.parquet`** +
    2 further shards (≈ 8 MB) — Rust-language arm, MIT.
14. `r2e-edits/SWE-smith-trajectories-R2E-v2` → **`data/train-00000-of-00001.parquet`** (144 MB, 5,016 rows).
15. `mlfoundations-dev/terminal-bench-traces-local` → **`data/train-00000-of-00001.parquet`** (6 MB, 1,189 rows).
16. `mondk/agentic-coding-traces` → the 323 `*.jsonl` under **`.raw_sources/hf_downloads/`** only
    (ignore the 327 `.lock` / 325 `.metadata` files) — small Claude Code / Codex / GLM session logs.
17. `Lottolabs/terminal-bench-2.1-qwen3.8-27b-traces` → the 47 `*.jsonl` **plus `medium/result.json` (9.9 MB)**
    and the 45 `*.md` transcripts (≈ 25 MB total; skip the 45 `.db` files) — the cheapest way to test the
    card's claim of per-task verifier output.

### Deliberately deferred

* `AlienKevin/SWE-ZERO-12M-trajectories` (27.1 GB, 12.3 M rows) — **no per-step test outcomes measured**; skip
  unless raw volume alone is the goal.
* `MaxDevv/real-pi-coding-agent-traces-sessions` (579 MB) and `0xSero/glm-5.2-…` (55 MB) — organic/native-format
  corpora that need a session-reconstruction loader before they are usable. Revisit once the
  JSON-string loaders exist.
* `agent-data/misc-merged-claude-code-traces-v1` (1.1 GB) — **request-level fragments, not sessions**.
  Defer until someone verifies the fragments can be re-stitched by `request_id`/`content_hash`.
* `Intelligent-Internet/swebench-pro-gpt-5-codex-ii-agent-trajectories` — blocked on HF token + accepted gate terms.

---

## Open items (do not treat as verified)

* `nvidia/SWE-Hero-openhands-trajectories` — existence, row count (34,269) and schema verified; **per-step test rate not measured**.
* `R2E-Gym/R2EGym-SFT-Trajectories` — row count (3,231) and schema (`messages`) verified; **per-step test rate not measured**.
* `MaxDevv/real-pi-coding-agent-traces-sessions`, `mondk/agentic-coding-traces`,
  `0xSero/glm-5.2-nf3-hybrid-terminal-bench-2.1-traces`, `Lottolabs/terminal-bench-2.1-qwen3.8-27b-traces` —
  file inventories verified, **row counts and observation formats UNVERIFIED** (no Parquet; JSONL/native formats).
* `Intelligent-Internet/swebench-pro-gpt-5-codex-ii-agent-trajectories` — **entirely UNVERIFIED** (gated).
* `DCAgent/…` and `DCAgent2/…` repos (Terminus-2 traces over SWE-Gym / SWE-rebench / terminal-bench-2) appeared
  repeatedly in search but were **not individually verified**; they look like derivative re-exports of corpora
  already ranked above.
