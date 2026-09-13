# Cross-scaffold replication of the two mechanical results

The study measures agent work without a human or a model in the loop. Two of its
claims are *mechanical*, so both should survive a change of scaffold:

1. **The three-class edit taxonomy.** Every edit is labelable from the observation
   and the agent's own final patch — `kept` (a line the step wrote reaches the
   patch), `revised` (nothing survives, but the same file is edited again later in
   the run), `dead_end` (nothing survives and the file is never touched again).
   SWE-agent reference: **kept 0.157 / revised 0.652 / dead_end 0.191** over 236,137 edits in 25,681 runs.
2. **The gold-target result.** With an *independent* gold patch per instance, failed
   runs localise at least as well as solved ones.

This document reports what happens when the same instrument is pointed at four other
agent scaffolds and one multi-scaffold corpus. Nothing here is judged by a model:
every number comes from regex and hashing over the raw trajectories.

## 0. Instrument check — the port is exact

Before any cross-scaffold claim, the new code path was run end-to-end on the
SWE-agent corpus itself (`scripts/xscaffold_calibrate.py`). It reproduces the
frozen numbers **to zero absolute difference**:

| | kept | revised | dead_end | edits | runs |
|---|---|---|---|---|---|
| frozen `dead_end.json` | 0.157 | 0.652 | 0.191 | 236,137 | 25,681 |
| re-run with the cross-scaffold code | 0.157 | 0.652 | 0.191 | 236,137 | 25,681 |

max absolute difference: **0.0e+00** (`reproduces_frozen = True`).

The check also exposed a scope question that matters for the comparison. The
frozen headline counts **every** edit, including the 16.7% of edits that sit in runs which
produced no patch at all (3,487 of 25,681 runs). Those edits can never be `kept`. Two references are therefore used below:

- **scope A (all runs):** kept 0.157 / revised 0.652 / dead_end 0.191 — used for the
  two corpora that ship a patch column, where an empty patch is a real outcome;
- **scope B (non-empty patch only):** kept 0.189 / revised 0.624 / dead_end 0.187 — used for
  the corpora whose patch has to be recovered from the transcript, where a run
  with no patch is unmeasurable rather than empty.

---

## 1. Headline table

| corpus | scaffold | runs | steps | edits | `[File: …]` footer | lines-total marker | kept | revised | dead_end |
|---|---|---|---|---|---|---|---|---|---|
| `swegym` | SWE-Gym/OpenHands-Sampled-Trajectories | 6,055 | 106,882 | 28,890 | **absent** | absent | 0.734 | 0.229 | 0.037 |
| `pi` | whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces | 7,777 | 267,162 | 28,861 | **absent** | present | 0.821 | 0.060 | 0.118 |
| `smithmarines` | Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k | 65,994 | 2,263,549 | 195,707 | **absent** | present | 0.489 | 0.276 | 0.236 |
| `thoughtworks` | thoughtworks/agentic-coding-trajectories | 15,000 | 619,394 | 113,957 | **absent** | absent | 0.706 | 0.115 | 0.179 |

Reference rows:

- SWE-agent, scope A: kept 0.157 / revised 0.652 / dead_end 0.191
- SWE-agent, scope B: kept 0.189 / revised 0.624 / dead_end 0.187

**The gold-target reference, and which way it points.** On the run's *own* final
patch, failed runs look slightly better localised than solved ones (delta -0.076, `on_target`). On the **independent gold target the sign reverses**:

| SWE-agent, gold target | solved | failed | delta | p |
|---|---|---|---|---|
| pooled `on_target_gold` | 0.477 | 0.407 | 0.070 | — |
| pooled `ever_touched_gold` | 0.982 | 0.670 | 0.311 | — |
| paired `on_target_gold` | 0.496 | 0.448 | 0.048 | 7.0e-03 |
| paired `ever_touched_gold` | 0.970 | 0.780 | 0.190 | 1.6e-23 |

Source: `results/rebuild/wrongness.json (SWE-agent / nebius SWE-agent-trajectories)`. So *the gold-target result replicates* below means
**solved runs score higher than failed runs on both gold measures** — the reversal,
not the own-patch direction.

---

## 2. Per-corpus findings

### 2.2 `swegym` — OpenHands — SWE-Gym/OpenHands-Sampled-Trajectories

**a. Structural marker.** 106,882 steps scanned, 28,890 of them edits. The SWE-agent footer appears on **0.0%** of steps and the string `(N lines total)` on **0.0%**.

Equivalent marker (names the file, no size):

```
Here's the result of running `cat -n` on /workspace/python__mypy__0.800/mypy/semanal.py:
```

Edit steps that name their target file at all: **99.9%**. Truncation notices on 0.0% of steps.

**b. Three-class taxonomy.**

| scope | edits | runs | kept | revised | dead_end |
|---|---|---|---|---|---|
| every run; a run with an empty patch wrote nothing that could ship | 28,890 | 3,765 | 0.734 | 0.229 | 0.037 |
| runs with a non-empty patch only | 28,432 | 3,673 | 0.746 | 0.222 | 0.032 |

Coverage: 28,890 of 28,890 edit steps (100.0%); 3,675 of 6,055 runs expose a non-empty final patch (60.7%).

Dead ends in absolute terms: 1,058 (0.28 per run); 78.0% of runs have none.

Among edits nothing revisits (n=8,484), 0.875 turned out to have been needed.

**c. Gold target.**

- instances with edits: 2,027; of these **15** have a gold patch in `gold_patches.parquet` (0.7% of the corpus, covering 35 runs)
- pooled: `ever_touched_gold` failed 0.414 vs solved 1.000; `on_target_gold` failed 0.251 vs solved 0.447 (n = 29 failed / 6 solved)
- within-instance: not available (too few contested instances)
- for comparison, the study's *existing* target — the run's own final patch — gives mean `on_target` 0.929 (solved 0.945 vs failed 0.927)

**d. Per-step test outcomes.**

- strict pytest/unittest pass–fail summary on 1.8% of steps
- any test marker (strict + framework summaries such as `N passed`/`N failed`, `PASSED`/`FAILED`, `test session starts`) on 9.5% of steps
- exit codes readable on 22.9% of steps; 62.1% of runs contain at least one
- 11.4% of runs contain a strict summary; 47.7% contain any test marker

**Verdicts.**

- *Footer:* ABSENT — no observation states a file's line count
- *Taxonomy:* DOES NOT REPLICATE — kept 0.734 / revised 0.229 / dead_end 0.037 (L1 1.153 from the SWE-agent vector), over 28,890 edits in 3,765 runs, i.e. 100.0% of this corpus's edit steps
- *Gold target:* REPLICATES — pooled solved runs on_target_gold 0.447 vs failed 0.251 (delta +0.196); ever_touched_gold 1.000 vs 0.414 (delta +0.586) — but the gold-covered sample is far too small to carry the claim (6 solved / 29 failed runs)
- *Test outcomes:* strict pytest/unittest summary on 1.79% of steps (9.46% with any test marker, including framework summaries); 11.4% of runs contain one

---

### 2.3 `pi` — PI agent — whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces

**a. Structural marker.** 267,162 steps scanned, 28,861 of them edits. The SWE-agent footer appears on **0.0%** of steps and the string `(N lines total)` on **0.0%**.

Literal size marker found: `(95 lines total)`

Edit steps that name their target file at all: **94.0%**. Truncation notices on 0.0% of steps.

**b. Three-class taxonomy.**

| scope | edits | runs | kept | revised | dead_end |
|---|---|---|---|---|---|
| runs whose final patch was recovered from the transcript | 11,131 | 1,956 | 0.821 | 0.060 | 0.118 |

Coverage: 11,131 of 28,861 edit steps (38.6%); 1,956 of 7,777 runs expose a non-empty final patch (25.2%).

Dead ends in absolute terms: 1,319 (0.67 per run); 73.5% of runs have none.

Among edits nothing revisits (n=6,039), 0.782 turned out to have been needed.

**c. Gold target.**

- instances with edits: 2,329; of these **0** have a gold patch in `gold_patches.parquet` (0.0% of the corpus, covering 0 runs)
- no run of this corpus touches a gold-covered instance
- for comparison, the study's *existing* target — the run's own final patch — gives mean `on_target` 0.229

**d. Per-step test outcomes.**

- strict pytest/unittest pass–fail summary on 15.6% of steps
- any test marker (strict + framework summaries such as `N passed`/`N failed`, `PASSED`/`FAILED`, `test session starts`) on 27.5% of steps
- exit codes readable on 0.8% of steps; 12.7% of runs contain at least one
- 99.2% of runs contain a strict summary; 99.9% contain any test marker

**Verdicts.**

- *Footer:* ABSENT as `[File: … (N lines total)]`; a size is stated on 0.013% of steps only (an error path), so it cannot label edits
- *Taxonomy:* DOES NOT REPLICATE — kept 0.821 / revised 0.060 / dead_end 0.118 (L1 1.265 from the SWE-agent vector), over 11,131 edits in 1,956 runs, i.e. 38.6% of this corpus's edit steps
- *Gold target:* NOT COMPUTABLE — no instance of this corpus has a gold patch in gold_patches.parquet
- *Test outcomes:* strict pytest/unittest summary on 15.62% of steps (27.49% with any test marker, including framework summaries); 99.2% of runs contain one

---

### 2.4 `smithmarines` — mini-swe-agent-plus — Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k

**a. Structural marker.** 2,263,549 steps scanned, 195,707 of them edits. The SWE-agent footer appears on **0.0%** of steps and the string `(N lines total)` on **0.0%**.

Literal size marker found: `(10 lines total)`

Edit steps that name their target file at all: **98.5%**. Truncation notices on 0.0% of steps.

**b. Three-class taxonomy.**

| scope | edits | runs | kept | revised | dead_end |
|---|---|---|---|---|---|
| runs whose final patch was recovered from the transcript | 4,123 | 1,339 | 0.489 | 0.276 | 0.236 |

Coverage: 4,123 of 195,707 edit steps (2.1%); 1,538 of 65,994 runs expose a non-empty final patch (2.3%).

Dead ends in absolute terms: 972 (0.73 per run); 48.9% of runs have none.

Among edits nothing revisits (n=1,855), 0.476 turned out to have been needed.

**c. Gold target.**

- instances with edits: 10,879; of these **0** have a gold patch in `gold_patches.parquet` (0.0% of the corpus, covering 0 runs)
- no run of this corpus touches a gold-covered instance
- for comparison, the study's *existing* target — the run's own final patch — gives mean `on_target` 0.018

**d. Per-step test outcomes.**

- strict pytest/unittest pass–fail summary on 4.3% of steps
- any test marker (strict + framework summaries such as `N passed`/`N failed`, `PASSED`/`FAILED`, `test session starts`) on 12.8% of steps
- exit codes readable on 97.0% of steps; 100.0% of runs contain at least one
- 46.6% of runs contain a strict summary; 87.3% contain any test marker

**Verdicts.**

- *Footer:* ABSENT as `[File: … (N lines total)]`; a size is stated on 0.000% of steps only (an error path), so it cannot label edits
- *Taxonomy:* DOES NOT REPLICATE — kept 0.489 / revised 0.276 / dead_end 0.236 (L1 0.697 from the SWE-agent vector), over 4,123 edits in 1,339 runs, i.e. 2.1% of this corpus's edit steps
- *Gold target:* NOT COMPUTABLE — no instance of this corpus has a gold patch in gold_patches.parquet
- *Test outcomes:* strict pytest/unittest summary on 4.28% of steps (12.81% with any test marker, including framework summaries); 46.6% of runs contain one

---

### 2.5 `thoughtworks` — multi-framework — thoughtworks/agentic-coding-trajectories

**a. Structural marker.** 619,394 steps scanned, 113,957 of them edits. The SWE-agent footer appears on **0.0%** of steps and the string `(N lines total)` on **0.0%**.

Equivalent marker (names the file, no size):

```
Here's the result of running `cat -n` on /testbed/conan/internal/cache/cache.py:
```

Edit steps that name their target file at all: **99.7%**. Truncation notices on 0.0% of steps.

**b. Three-class taxonomy.**

| scope | edits | runs | kept | revised | dead_end |
|---|---|---|---|---|---|
| runs whose final patch was recovered from the transcript | 55,742 | 6,363 | 0.706 | 0.115 | 0.179 |

Coverage: 55,742 of 113,957 edit steps (48.9%); 6,371 of 15,000 runs expose a non-empty final patch (42.5%).

Dead ends in absolute terms: 9,982 (1.57 per run); 49.6% of runs have none.

Among edits nothing revisits (n=31,943), 0.688 turned out to have been needed.

**c. Gold target.**

- instances with edits: 9,921; of these **227** have a gold patch in `gold_patches.parquet` (2.3% of the corpus, covering 348 runs)
- pooled: `ever_touched_gold` failed 0.840 vs solved 0.993; `on_target_gold` failed 0.224 vs solved 0.241 (n = 81 failed / 267 solved)
- within-instance (paired, 13 contested instances, 32 runs): `on_target_gold` failed 0.208 vs solved 0.271, mean delta +0.063, 61.5% of instances positive, Wilcoxon p = 1.4e-01; `ever_touched_gold` failed 0.846 vs solved 0.962, delta +0.115, p = 1.8e-01
- for comparison, the study's *existing* target — the run's own final patch — gives mean `on_target` 0.319 (solved 0.471 vs failed 0.251)

**d. Per-step test outcomes.**

- strict pytest/unittest pass–fail summary on 6.2% of steps
- any test marker (strict + framework summaries such as `N passed`/`N failed`, `PASSED`/`FAILED`, `test session starts`) on 17.8% of steps
- exit codes readable on 48.5% of steps; 72.4% of runs contain at least one
- 51.6% of runs contain a strict summary; 88.3% contain any test marker

**Verdicts.**

- *Footer:* ABSENT — no observation states a file's line count
- *Taxonomy:* DOES NOT REPLICATE — kept 0.706 / revised 0.115 / dead_end 0.179 (L1 1.035 from the SWE-agent vector), over 55,742 edits in 6,363 runs, i.e. 48.9% of this corpus's edit steps
- *Gold target:* REPLICATES — pooled solved runs on_target_gold 0.241 vs failed 0.224 (delta +0.017); ever_touched_gold 0.993 vs 0.840 (delta +0.153); within-instance on 13 contested instances 0.271 solved vs 0.208 failed (delta +0.063, p=0.13609738111439368)
- *Test outcomes:* strict pytest/unittest summary on 6.24% of steps (17.85% with any test marker, including framework summaries); 51.6% of runs contain one

**Split by the corpus's own `agent_framework` column.**

| framework | runs | steps | edits | footer | `cat -n` | patchable runs | edit coverage | kept | revised | dead_end | gold instances |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `mini-swe-agent` | 5,000 | 137,164 | 14,705 | 0.0% | 0.0% | 2.0% | 2.0% | 0.525 | 0.266 | 0.209 | 0 |
| `openhands` | 5,000 | 320,769 | 53,357 | 0.0% | 20.7% | 41.0% | 36.4% | 0.414 | 0.154 | 0.433 | 227 |
| `swe-agent` | 5,000 | 161,461 | 45,895 | 0.0% | 21.5% | 84.5% | 78.5% | 0.866 | 0.092 | 0.042 | 0 |

---

## 3. What the replication does and does not show

Written after the numbers above; see `results/rebuild/xscaffold_replication.json`
for the machine-readable form of every figure.

The paragraphs here are generated from the verdict blocks, so they cannot drift from
the JSON.

**`swegym`** — ABSENT — no observation states a file's line count DOES NOT REPLICATE — kept 0.734 / revised 0.229 / dead_end 0.037 (L1 1.153 from the SWE-agent vector), over 28,890 edits in 3,765 runs, i.e. 100.0% of this corpus's edit steps REPLICATES — pooled solved runs on_target_gold 0.447 vs failed 0.251 (delta +0.196); ever_touched_gold 1.000 vs 0.414 (delta +0.586) — but the gold-covered sample is far too small to carry the claim (6 solved / 29 failed runs)

**`pi`** — ABSENT as `[File: … (N lines total)]`; a size is stated on 0.013% of steps only (an error path), so it cannot label edits DOES NOT REPLICATE — kept 0.821 / revised 0.060 / dead_end 0.118 (L1 1.265 from the SWE-agent vector), over 11,131 edits in 1,956 runs, i.e. 38.6% of this corpus's edit steps NOT COMPUTABLE — no instance of this corpus has a gold patch in gold_patches.parquet

**`smithmarines`** — ABSENT as `[File: … (N lines total)]`; a size is stated on 0.000% of steps only (an error path), so it cannot label edits DOES NOT REPLICATE — kept 0.489 / revised 0.276 / dead_end 0.236 (L1 0.697 from the SWE-agent vector), over 4,123 edits in 1,339 runs, i.e. 2.1% of this corpus's edit steps NOT COMPUTABLE — no instance of this corpus has a gold patch in gold_patches.parquet

**`thoughtworks`** — ABSENT — no observation states a file's line count DOES NOT REPLICATE — kept 0.706 / revised 0.115 / dead_end 0.179 (L1 1.035 from the SWE-agent vector), over 55,742 edits in 6,363 runs, i.e. 48.9% of this corpus's edit steps REPLICATES — pooled solved runs on_target_gold 0.241 vs failed 0.224 (delta +0.017); ever_touched_gold 0.993 vs 0.840 (delta +0.153); within-instance on 13 contested instances 0.271 solved vs 0.208 failed (delta +0.063, p=0.13609738111439368)

## 4. Method, and where it could be wrong

**Corpora.** Downloaded in full and parsed locally; total 4.6 GB. Row counts:

| corpus | HF repo | rows in the corpus | rows parsed here |
|---|---|---|---|
| `swegym` | `SWE-Gym/OpenHands-Sampled-Trajectories` | — | 6,055 |
| `pi` | `whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces` | — | 7,777 |
| `smithmarines` | `Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k` | — | 65,994 |
| `thoughtworks` | `thoughtworks/agentic-coding-trajectories` | — | 15,000 |

**Where an edit's target file comes from.** This is the one place where scaffolds
genuinely differ, and it is recorded rather than assumed.

- SWE-agent (the frozen study) reads it from the observation's `[File: …]` footer.
- OpenHands, the PI agent and mini-swe-agent do not print that footer, so the target
  comes from the **tool-call arguments** (`path`), which is the same information
  the agent acted on. Coverage is reported per corpus.

**Paths.** `norm_path` strips the sandbox root (`/workspace/<repo>/`, `/testbed/`, …)
so an edit and a patch hunk referring to the same file compare equal. The frozen
study compared raw footer strings; the normalisation only makes that comparison
slightly more generous.

**Line hashes.** A written line and a patch `+` line are compared by a 6-byte
blake2b of their stripped text, with a minimum length of 3 characters — the frozen
definitions, reused verbatim.

**Recovered patches.** For the PI agent, mini-swe-agent and thoughtworks corpora the
final patch is not a column; it is taken from the agent's own printed `git diff` in
the transcript (the longest such block, else the last fenced `diff` block). A run
that never printed a diff is therefore *unmeasurable*, not *empty*, and such runs are
excluded from the taxonomy rather than scored as `kept = 0`. That is why those corpora
carry an explicit coverage fraction, and why the taxonomy verdict is only as strong as
that fraction.

**Gold target.** `gold_patches.parquet` holds gold file basenames for 927 instances.
A run is `ever_touched_gold` if any edit step aims at a file whose *basename* is in
its instance's gold set, and `on_target_gold` is the share of its edit steps that do.
Matching is by basename, so a same-named file elsewhere in the tree would count; the
gold patches are small (1–3 files) and repo-specific, so this is a mild relaxation.
Corpora whose instance ids do not intersect that set get no gold result at all.

**No model was called.** Everything is regex, hashing and arithmetic.
