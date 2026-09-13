"""Can an outcome-based target be defined densely enough to predict?

The rebuild assumes we can label every step by "did verified progress happen within the next K
steps", measured from execution outcomes.  The probe showed the explicit test/build signals are
rare.  Before building anything, measure the actual event rate and horizon statistics, and decide
the target from evidence rather than optimism.
"""
from __future__ import annotations

import collections
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
import pyarrow.parquet as pq

RAW = "data/raw/tb2/train-00000-of-00002.parquet"
PROC = "data/processed/tb2/sample_trajectories.jsonl"

# a "success event" = the environment reports something objectively good
SUCCESS_PATTERNS = [
    re.compile(r"<returncode>\s*0\s*</returncode>", re.I),
    re.compile(r"\{exit=0\}"),
    re.compile(r"\b(?:all\s+)?\d+\s+passed\b", re.I),
    re.compile(r"\btests? (?:passed|ok)\b", re.I),
    re.compile(r"build (?:succeeded|complete|completed successfully)", re.I),
    re.compile(r"SUCCESS", re.I),
]
# a "progress event" = something changed that the environment confirms
CHANGE_PATTERNS = [
    re.compile(r"ERROR SUMMARY:\s*0\s*errors?", re.I),
    re.compile(r"definitely lost:\s*0 bytes", re.I),
]

printed = 0
rows = 0
for batch in pq.ParquetFile(RAW).iter_batches(batch_size=32,
                                              columns=["trial_name", "steps", "reward"]):
    for r in batch.to_pylist():
        blob = r.get("steps")
        if not blob:
            continue
        try:
            steps = json.loads(blob)
        except Exception:
            continue
        if not steps or not any(isinstance(s, dict) for s in steps):
            continue
        rows += 1
        if printed >= 3 or rows % 4000 != 0:
            continue
        obs = [str(s.get("obs") or "") for s in steps]
        succ = [bool(any(p.search(o) for p in SUCCESS_PATTERNS)) for o in obs]
        n = len(obs)
        print(f"\ntrial {r['trial_name'][:44]}  steps={n} reward={r['reward']}")
        print(f"  steps with a success event: {sum(succ)} ({100*sum(succ)/n:.0f}%)")
        for K in (5, 10, 20, 50):
            frac = sum(1 for i in range(n)
                       if any(succ[i + 1: i + 1 + K])) / n
            print(f"    P(success within next {K:>2} steps) = {frac:.2f}")
        printed += 1

print(f"\ntrials scanned: {rows}")

# and across the whole sample, how many distinct success events per run?
print("\nsuccess-event density over the analysis sample:")
dens = []
tight = 0
for line in open(PROC, encoding="utf-8"):
    t = json.loads(line)
    obs = [s.get("obs") or "" for s in t["steps"]]
    if not obs:
        continue
    succ = [any(p.search(o) for p in SUCCESS_PATTERNS) for o in obs]
    dens.append((sum(succ), len(obs)))
    if not any(succ):
        tight += 1
tot_ev = sum(s for s, _ in dens)
tot_st = sum(n for _, n in dens)
print(f"  runs: {len(dens)}; steps: {tot_st}; success events: {tot_ev} "
      f"({100*tot_ev/max(1,tot_st):.1f}% of steps)")
print(f"  runs with zero success events: {tight} ({100*tight/max(1,len(dens)):.0f}%)")
with_ev = [s for s, _ in dens if s]
with_ev.sort()
if with_ev:
    print(f"  median events per run (among runs that have any): {with_ev[len(with_ev)//2]}")
