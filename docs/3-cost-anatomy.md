# Cost anatomy: where the budget actually goes (Goal R2, 2026-09-13)

**Question under test** (user hypothesis): a decisive cost factor at majority scale, not yet
uncovered. **Verdict: CONFIRMED — several, and they share one multiplier.**
Full censuses (not samples): TB2 14,750 runs / 452,960 steps / $7,846 cleaned spend;
Nebius 26,679 runs / 709,264 steps. Tables: `results/exploratory/r2_cost_census.json`,
`results/exploratory/r2_redo_census.json`. Seed 7. Denominators stated per metric.

## 1. Concentration (TB2 spend, deduped)

| bucket | share of spend | runs |
|---|---|---|
| failed runs (reward==0) | **77.3%** | 63.2% of runs |
| top 5% most expensive runs | **54.1%** | 738 runs |
| steps past step 30 ("tail tax", lower bound) | **~55% of input tokens** | 31% of runs exceed 30 steps |
| no-edit runs (n_edit==0) | **40.8%** (prior claim re-verified exactly) | 58.3% of runs |
| runs >100 steps | 31.7%, reward 15.6% | 5.2% |
| C-c-interrupted runs (kill hung foreground work) | **20.4%** (NEW) | 7.5%, 2.8× mean length, reward 26% vs 36% |
| top 1% runs | 27.0% | 148 runs |

Cost per solved run: $1.45. Context economics: **44 input tokens per output token**
corpus-wide (median run 20×, p90 159×). Reading dominates context: TB2 top obs sources
cat 16%, python3 8%, cd 7%, ls 7%; verbs: run 51% of steps, read 10% steps but 19% of
obs-chars. Nebius differs in kind (edit 36% steps / 46% obs) — scaffold shapes the burn.

## 2. Redo economy (step shares)

| bucket | TB2 | Nebius |
|---|---|---|
| same-file re-edits beyond first | 1.9% steps (LOWER BOUND: 29% target coverage) | **21.4% steps, 48.3% runs (NEW)** |
| re-reads (same target re-read) | 4.3% steps; **44.7% of all reads** | 8.2% steps; **45.0% of reads** |
| heavy re-readers (>10) | 3.1% runs | 6.6% runs |
| verify deserts (≥20 steps, zero tests) | **42.2% of runs**, reward −8.0pp vs tested-long | **41.0% of runs**, −2.5pp |
| verify repeats (identical test ×3+) | 0.09% runs — negligible | 0.13% — negligible |
| error-chain "theater" (all-error ×4+) | 0.04% — negligible (two len-187 loops) | 0.045% — negligible |
| combined redo union | 52.3% runs / 85% steps | 69.6% runs / 89% steps |

Scaffold tell: Nebius #1 re-edited file is `reproduce.py` (26,490 re-edits, 2,311 file-runs),
then `reproduce_bug.py` — the harness's own reproduce-script loop is the single largest
measured redo bucket anywhere. TB2 top: shared_heap.c, out.html, bottle.py.

## 3. Small or dead (reported for honesty)

Sleep/wait polling: 3.7% runs, 5.0% spend (deduped; corrects last round's as-stored 4.3%).
Theater-analogue and verify-repeat loops: <0.15% runs — real but rare; not cost levers.
Sleep finding stands, sized as niche.

## 4. The unifying mechanism (the actual "decisive factor")

No single *behavior* reaches majority scale — but one *mechanism* does: **context re-reads
make cost superlinear in run length** (44× in/out; tail 55% lower bound). Every
length-inflating behavior — thrash, re-discovery, waiting, puttering, failed runs that
don't stop — compounds through this multiplier. Failed-run spend (77%), the top-5% (54%),
no-edit runs (41%), C-c runs (20%) are overlapping faces of "runs that go long burn
quadratically," not independent levers. Union overlaps confirm it (revision×desert 8,109
Nebius runs).

## 5. Data-quality flag (action required, not this round)

`runs.parquet` carries 17,237 rows for 14,750 distinct run_ids: 2,487 runs parsed twice
(steps mirrored: 547,031 rows = 358,889 clean + 188,142 doubled; +20.5% cost / +17.2% steps
as-stored). All headline shares above are DEDUPED (keep-first); as-stored values kept in the
census appendix. Corrections to last round's as-stored numbers: C-c 24.5%→**20.4%**,
C-c runs 1,393→**1,100**. Open question: whether frozen `windows.parquet`-derived metrics
(AUCs — rank-based, likely robust) vs count claims need a rebuild pass. Recommend a
dedup-verification pass before quoting any absolute counts downstream.

## 6. Prescription (cost-ordered)

1. **Shorten runs, don't sharpen monitors**: step budgets keyed to the tail (the >100-step
   5% burns 32% at 16% success) beat any signal upgrade — the multiplier does the work.
2. **Kill conditions with teeth**: C-c-pattern (hung foreground work, 20% spend) and
   post-completion puttering are detectable cheaply and safe to stop.
3. **Done-detection before stuck-detection**: stopping finished runs costs nothing.
4. **Scaffold fix with measured payoff**: reuse/stabilize reproduce scripts (21% Nebius steps).
5. **Background waits + output-novelty gating** for the 3–8% poll/wait footprint — cheap,
   precise, small.

## Limits

TB2 costs only (Nebius has no cost columns); tail-tax uniform-step assumption is a stated
lower bound; TB2 revision is a lower bound (target coverage 29%); complaint-to-corpus bridge
covers 8/10 themes (speculation-without-action and subagent fan-out need no-tool/scaffold
parsing — open). No frozen artifact modified.
