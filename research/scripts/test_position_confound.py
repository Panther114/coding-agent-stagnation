"""Is the region-level signal real, or is it run position?

`B1_step30` ("how far into the run are we") scored highest in the mid-region analysis, which is a
warning: if stagnant episodes cluster late in runs, a position proxy looks like a detector. That
would be the same whole-run trap in a new costume. Test it directly, and test whether region-level
detection survives after controlling for position.
"""
from __future__ import annotations

import collections
import csv
import json
import statistics as st
import sys

sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
import pyarrow.parquet as pq

GOLD = "../datasets/annotations/tb2/adjudicated.csv"
W = 10

rows = [r for r in csv.DictReader(open(GOLD, encoding="utf-8")) if r["binary"] != ""]
by_traj = collections.defaultdict(list)
for r in rows:
    by_traj[r["traj_id"]].append(r)
for t in by_traj:
    by_traj[t].sort(key=lambda r: int(r["t"]))

# ---- where in a run do stagnant windows sit? ----
rel = []
for tid, rs in by_traj.items():
    n = max(int(r["n_steps"]) for r in rs)
    for r in rs:
        rel.append((int(r["t"]) / max(1, n), int(r["binary"])))
pos = [p for p, y in rel if y == 1]
neg = [p for p, y in rel if y == 0]
print("=== run-relative position of each class ===")
print(f"  stagnant   mean {np.mean(pos):.3f}  median {np.median(pos):.3f}  n={len(pos)}")
print(f"  productive mean {np.mean(neg):.3f}  median {np.median(neg):.3f}  n={len(neg)}")
print(f"  -> position alone separates them by {abs(np.mean(pos)-np.mean(neg)):.3f} in relative terms")

# AUC of position alone
def roc_auc(y, s):
    y = np.asarray(y); s = np.asarray(s, dtype=float)
    ok = ~np.isnan(s); y, s = y[ok], s[ok]
    if y.size == 0 or y.min() == y.max(): return float("nan")
    order = np.argsort(s, kind="mergesort"); ss = s[order]
    ranks = np.empty(len(s), dtype=float); i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j+1] == ss[i]: j += 1
        ranks[order[i:j+1]] = (i+j)/2.0 + 1; i = j + 1
    n1, n0 = int((y==1).sum()), int((y==0).sum())
    return (ranks[y==1].sum() - n1*(n1+1)/2) / (n1*n0)

y_all = np.array([y for _, y in rel])
p_all = np.array([p for p, _ in rel])
print(f"  position-only ROC-AUC: {roc_auc(y_all, p_all):.3f}")

# ---- position-matched comparison: within a narrow position band, does the monitor still work? ----
scores = collections.defaultdict(dict)
for r in pq.read_table("results/final/tb2_v5/monitor_scores.parquet",
                       columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist():
    if r["w"] == W:
        scores[r["monitor"]][(r["traj_id"], r["t"])] = r["score"]

print("\n=== position-matched: ROC-AUC inside run-position bands (removes the position advantage) ===")
bands = [(0.0, 0.33), (0.33, 0.66), (0.66, 1.01)]
hdr = f"  {'monitor':14}" + "".join(f"{f'{a:.2f}-{b:.2f}':>12}" for a, b in bands) + f"{'pooled':>10}"
print(hdr)
for mon in ("B1_step30", "B4_semantic", "L_sem", "C3_evid_sem", "C5" if False else "C4_all_hand"):
    cells = []
    ys_all, ss_all = [], []
    for a, b in bands:
        ys, ss = [], []
        for tid, rs in by_traj.items():
            n = max(int(r["n_steps"]) for r in rs)
            for r in rs:
                pr = int(r["t"]) / max(1, n)
                if not (a <= pr < b):
                    continue
                v = scores[mon].get((tid, int(r["t"])))
                if v is None or v != v:
                    continue
                ys.append(int(r["binary"])); ss.append(v)
        if len(set(ys)) > 1:
            cells.append(roc_auc(np.array(ys), np.array(ss)))
        else:
            cells.append(float("nan"))
        ys_all += ys; ss_all += ss
    pooled = roc_auc(np.array(ys_all), np.array(ss_all))
    print(f"  {mon:14}" + "".join(f"{c:>12.3f}" if np.isfinite(c) else f"{'--':>12}"
                                  for c in cells) + f"{pooled:>10.3f}")

print("\n=== the key question: does the semantic monitor beat the position proxy, position-matched? ===")
for a, b in bands:
    ya, sa, sb = [], [], []
    for tid, rs in by_traj.items():
        n = max(int(r["n_steps"]) for r in rs)
        for r in rs:
            pr = int(r["t"]) / max(1, n)
            if not (a <= pr < b):
                continue
            va = scores["B4_semantic"].get((tid, int(r["t"])))
            vb = scores["B1_step30"].get((tid, int(r["t"])))
            if va is None or vb is None or va != va or vb != vb:
                continue
            ya.append(int(r["binary"])); sa.append(va); sb.append(vb)
    if len(set(ya)) > 1 and len(ya) > 30:
        aa, ab = roc_auc(np.array(ya), np.array(sa)), roc_auc(np.array(ya), np.array(sb))
        print(f"  band {a:.2f}-{b:.2f}: semantic {aa:.3f}  position {ab:.3f}  "
              f"diff {aa-ab:+.3f}  (n={len(ya)})")
