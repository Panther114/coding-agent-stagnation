"""Test whether "time to the next verified success" varies WITHIN a run.

The previous target (any success within K steps) turned out to be nearly constant within a run,
which makes it a whole-run property and reproduces the first study's central trap.  The target a
runtime actually needs is a *deadline*: is verified progress coming soon, or should we intervene?

Before committing, measure the within-run variability of that target.  A target that does not vary
within a run cannot be predicted within a run, and no monitor can score above chance on it.
"""
from __future__ import annotations

import collections
import json
import re
import statistics as st
import sys

sys.stdout.reconfigure(encoding="utf-8")

SUCCESS = [
    re.compile(r"<returncode>\s*0\s*</returncode>", re.I),
    re.compile(r"\{exit=0\}"),
    re.compile(r"\b(?:all\s+)?\d+\s+passed\b", re.I),
    re.compile(r"\btests? (?:passed|ok)\b", re.I),
    re.compile(r"build (?:succeeded|complete|completed successfully)", re.I),
]
PROC = "data/processed/tb2/sample_trajectories.jsonl"

def is_success(o: str) -> bool:
    return any(p.search(o) for p in SUCCESS)

runs = []
for line in open(PROC, encoding="utf-8"):
    t = json.loads(line)
    obs = [s.get("obs") or "" for s in t["steps"]]
    if len(obs) < 15:
        continue
    succ = [is_success(o) for o in obs]
    runs.append((t["traj_id"], len(obs), succ))

print(f"runs considered (>=15 steps): {len(runs)}")

# time to next success
rows = []
for tid, n, succ in runs:
    nxt = None
    gaps = [None] * n
    for i in range(n - 1, -1, -1):
        if succ[i]:
            nxt = i
        gaps[i] = None if nxt is None else nxt - i
    rows.append((tid, n, succ, gaps))

multi = [(tid, n, s, g) for tid, n, s, g in rows if sum(s) >= 2]
print(f"runs with at least 2 success events: {len(multi)}")

# how often does the binarised target flip within a run?
for K in (3, 5, 10):
    flips = []
    pos = []
    for tid, n, s, g in multi:
        y = [1 if (x is not None and x <= K) else 0 for x in g]
        pos.append(sum(y) / n)
        flips.append(sum(1 for i in range(1, n) if y[i] != y[i - 1]) / max(1, n - 1))
    print(f"\nK={K}: P(success within next {K} steps)")
    print(f"  positive rate: mean {st.mean(pos):.2f}  median {st.median(pos):.2f}  "
          f"min {min(pos):.2f}  max {max(pos):.2f}")
    print(f"  within-run label flips per step: mean {st.mean(flips):.2f}  "
          f"median {st.median(flips):.2f}")
    mixed = sum(1 for tid, n, s, g in multi
                if 0 < sum(1 if (x is not None and x <= K) else 0 for x in g) < n)
    print(f"  runs with both classes present: {mixed} of {len(multi)}")

print("\ninterpretation: a target with a low flip rate and few mixed runs is again a whole-run")
print("property. We need a target that flips often WITHIN runs, so a monitor has something to learn.")
