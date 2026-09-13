"""Does regime detection survive the whole-run control?

The mid/edge finding could still be "this run is bad" rather than "this episode is happening". The
decisive control is to ask, **within a single run**, whether the monitor separates that run's
stagnant episodes from its own productive regions. That is the question a runtime faces and it
cannot be answered by run-level recognition.

Also compute what a runtime actually needs: per-episode detection and the false-alarm cost of
achieving it.
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

GOLD = "data/annotations/tb2/adjudicated.csv"
W = 10


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


rows = [r for r in csv.DictReader(open(GOLD, encoding="utf-8")) if r["binary"] != ""]
by_traj = collections.defaultdict(list)
for r in rows:
    by_traj[r["traj_id"]].append(r)
for t in by_traj:
    by_traj[t].sort(key=lambda r: int(r["t"]))

scores = collections.defaultdict(dict)
for r in pq.read_table("results/final/tb2_v5/monitor_scores.parquet",
                       columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist():
    if r["w"] == W:
        scores[r["monitor"]][(r["traj_id"], r["t"])] = r["score"]

print("=== WITHIN-RUN AUC: does the monitor order a run's own windows correctly? ===")
print(f"  {'monitor':14}{'runs':>6}{'median':>9}{'>0.5':>8}{'>=0.70':>8}{'pooled':>9}")
summary = {}
for mon in ("B4_semantic", "L_sem", "C3_evid_sem", "C4_all_hand", "B1_step30",
            "B5_novelty", "B2_exact_rep3"):
    per_run = {}
    ys_all, ss_all = [], []
    for tid, rs in by_traj.items():
        ys, ss = [], []
        for r in rs:
            v = scores[mon].get((tid, int(r["t"])))
            if v is None or v != v:
                continue
            ys.append(int(r["binary"])); ss.append(v)
        if len(set(ys)) > 1:
            a = roc_auc(np.array(ys), np.array(ss))
            if np.isfinite(a):
                per_run[tid] = a
        ys_all += ys; ss_all += ss
    if not per_run:
        continue
    vals = sorted(per_run.values())
    med = st.median(vals)
    above = sum(1 for v in vals if v > 0.5)
    high = sum(1 for v in vals if v >= 0.70)
    pooled = roc_auc(np.array(ys_all), np.array(ss_all))
    summary[mon] = {"runs": len(vals), "median": med, "share_above": above/len(vals),
                    "share_ge70": high/len(vals), "pooled": pooled}
    print(f"  {mon:14}{len(vals):>6}{med:>9.3f}{above/len(vals):>8.2f}{high/len(vals):>8.2f}{pooled:>9.3f}")

# ---- what a runtime needs: per-episode detection at a controlled false-alarm cost ----
print("\n=== EPISODE-LEVEL detection (the operational question) ===")
regions = []
for tid, rs in by_traj.items():
    cur = None
    for r in rs:
        lab = int(r["binary"]); t = int(r["t"])
        if cur and lab == cur["label"]:
            cur["windows"].append(t); cur["end"] = max(cur["end"], t)
        else:
            if cur: regions.append(cur)
            cur = {"traj": tid, "label": lab, "start": t, "end": t, "windows": [t]}
    if cur: regions.append(cur)
pos_regs = [g for g in regions if g["label"] == 1]
neg_regs = [g for g in regions if g["label"] == 0]
print(f"  {len(pos_regs)} stagnant episodes, {len(neg_regs)} productive regions")

for mon in ("B4_semantic", "L_sem", "C3_evid_sem", "B1_step30"):
    print(f"\n  {mon}:")
    for q in (0.90, 0.95, 0.99):
        # threshold = q-th quantile of the monitor's scores on labelled PRODUCTIVE windows
        base = [scores[mon].get((g["traj"], t)) for g in neg_regs for t in g["windows"]]
        base = [v for v in base if v is not None and v == v]
        if not base:
            continue
        thr = float(np.quantile(base, q))
        det = 0; lat = []; fp_reg = 0
        for g in pos_regs:
            vs = [(t, scores[mon].get((g["traj"], t))) for t in sorted(g["windows"])]
            vs = [(t, v) for t, v in vs if v is not None and v == v]
            if not vs:
                continue
            fired = [t for t, v in vs if v > thr]
            if fired:
                det += 1
                lat.append(min(fired) - min(g["windows"]))
        for g in neg_regs:
            vs = [scores[mon].get((g["traj"], t)) for t in g["windows"]]
            vs = [v for v in vs if v is not None and v == v]
            if vs and max(vs) > thr:
                fp_reg += 1
        print(f"    at {q:.0%} productive quantile (thr={thr:.3f}): episodes detected "
              f"{det}/{len(pos_regs)} ({100*det/len(pos_regs):.0f}%), "
              f"median latency {st.median(lat) if lat else float('nan'):.0f} steps, "
              f"false alarms {fp_reg}/{len(neg_regs)} productive regions fired")

json.dump({"within_run": summary,
           "n_stagnant_episodes": len(pos_regs),
           "n_productive_regions": len(neg_regs)},
          open("results/final/v2/regime_detection.json", "w", encoding="utf-8"), indent=2)
print("\nwrote results/final/v2/regime_detection.json")
