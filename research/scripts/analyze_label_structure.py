"""Structural analysis: are the labels regions or points, and does the evaluation respect that?

The annotation guide has always said that consecutive windows of the same label merge into
contiguous stagnant and productive *regions*.  Every metric reported so far scores windows
independently, as if the labels were point labels.  If they are really regions, then:

  a) the classification target is not "is this moment stalled" but "which regime is this moment in";
  b) a monitor should be *persistently* high across a region, not high at isolated windows;
  c) scoring at the region level is the operationally meaningful test, and the per-window AUC
     understates a detector that is right about regimes;
  d) a stagnation episode has a *duration*, and durations are what a runtime reacts to.

Measure all of that from the gold set before proposing anything new.
"""
from __future__ import annotations

import collections
import csv
import json
import statistics as st
import sys

sys.stdout.reconfigure(encoding="utf-8")
GOLD = "../datasets/annotations/tb2/adjudicated.csv"
W = 10

rows = [r for r in csv.DictReader(open(GOLD, encoding="utf-8")) if r["binary"] != ""]
print(f"binary windows: {len(rows)}")

by_traj = collections.defaultdict(list)
for r in rows:
    by_traj[r["traj_id"]].append(r)
for t in by_traj:
    by_traj[t].sort(key=lambda r: int(r["t"]))

# ---- 1. region structure: merge consecutive same-label windows ----
regions = []
for tid, rs in by_traj.items():
    cur = None
    for r in rs:
        lab = int(r["binary"])
        t = int(r["t"])
        if cur and lab == cur["label"]:
            cur["windows"].append(t)
            cur["end"] = max(cur["end"], t)
        else:
            if cur:
                regions.append(cur)
            cur = {"traj": tid, "task": r["task"], "label": lab, "start": t, "end": t,
                   "windows": [t]}
    if cur:
        regions.append(cur)

pos_regions = [g for g in regions if g["label"] == 1]
neg_regions = [g for g in regions if g["label"] == 0]
print(f"\n=== region structure (consecutive same-label windows merged) ===")
print(f"  productive regions: {len(neg_regions)}")
print(f"  stagnant regions  : {len(pos_regions)}")
print(f"  windows in stagnant regions: {sum(len(g['windows']) for g in pos_regions)}")
print(f"  windows in productive regions: {sum(len(g['windows']) for g in neg_regions)}")

# duration in STEPS spanned (end - start + W)
durs = [(g["end"] - g["start"]) + W for g in pos_regions]
print(f"\n  stagnant episode duration (steps, +W):")
print(f"    min {min(durs)}  median {st.median(durs)}  mean {st.mean(durs):.0f}  max {max(durs)}")
print(f"    quartiles: q1 {sorted(durs)[len(durs)//4]}  q3 {sorted(durs)[3*len(durs)//4]}")
print(f"    episodes >= 20 steps: {sum(1 for d in durs if d >= 20)}")
print(f"    episodes >= 30 steps: {sum(1 for d in durs if d >= 30)}")

# ---- 2. does a monitor score higher in the MIDDLE of a region than at its edge? ----
print(f"\n=== is the signal regime-like or edge-like? ===")
import numpy as np
import pyarrow.parquet as pq

scores = {}
for r in pq.read_table("results/final/tb2_v5/monitor_scores.parquet",
                       columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist():
    if r["w"] == W:
        scores[(r["monitor"], r["traj_id"], r["t"])] = r["score"]

for mon in ("B4_semantic", "L_sem", "B1_step30"):
    mid, edge, out = [], [], []
    for g in pos_regions:
        ws = sorted(g["windows"])
        if len(ws) >= 3:
            inner, outer = ws[1:-1], [ws[0], ws[-1]]
        else:
            inner, outer = ws, []
        for t in inner:
            v = scores.get((mon, g["traj"], t))
            if v is not None and v == v:
                mid.append(v)
        for t in outer:
            v = scores.get((mon, g["traj"], t))
            if v is not None and v == v:
                edge.append(v)
    for g in neg_regions:
        for t in g["windows"]:
            v = scores.get((mon, g["traj"], t))
            if v is not None and v == v:
                out.append(v)
    line = f"  {mon:14}"
    if mid:
        line += f" stagnant-mid {np.mean(mid):+.3f} (n={len(mid)})"
    if edge:
        line += f" | stagnant-edge {np.mean(edge):+.3f} (n={len(edge)})"
    if out:
        line += f" | productive {np.mean(out):+.3f} (n={len(out)})"
    print(line)

# ---- 3. per-region detectability: can a monitor rank this region above productive windows? ----
print(f"\n=== per-region detection (a runtime decides once per episode, not per window) ===")
for mon in ("B4_semantic", "L_sem", "C3_evid_sem"):
    hits = miss = 0
    margins = []
    for g in pos_regions:
        rv = [scores.get((mon, g["traj"], t)) for t in g["windows"]]
        rv = [v for v in rv if v is not None and v == v]
        if not rv:
            continue
        nv = []
        for h in neg_regions:
            if h["traj"] != g["traj"]:
                continue
            for t in h["windows"]:
                v = scores.get((mon, h["traj"], t))
                if v is not None and v == v:
                    nv.append(v)
        if not nv:
            continue
        peak, base = max(rv), float(np.median(nv))
        if peak > base:
            hits += 1
        else:
            miss += 1
        margins.append(peak - base)
    tot = hits + miss
    if tot:
        print(f"  {mon:14} regions where peak score exceeds the run's productive median: "
              f"{hits}/{tot} ({100*hits/tot:.0f}%)  median margin {st.median(margins):+.3f}")

# ---- 4. how many runs even contain a stagnant region? ----
has_pos = {g["traj"] for g in pos_regions}
print(f"\n=== coverage ===")
print(f"  trajectories with >=1 stagnant region: {len(has_pos)} of {len(by_traj)}")
print(f"  trajectories with both classes: "
      f"{sum(1 for t, rs in by_traj.items() if len({int(r['binary']) for r in rs}) > 1)}")

out = {
    "n_windows": len(rows),
    "n_productive_regions": len(neg_regions),
    "n_stagnant_regions": len(pos_regions),
    "windows_in_stagnant_regions": sum(len(g["windows"]) for g in pos_regions),
    "episode_median_steps": st.median(durs),
    "episode_max_steps": max(durs),
    "episodes_ge20": sum(1 for d in durs if d >= 20),
    "trajectories_with_stagnant_region": len(has_pos),
    "trajectories_total": len(by_traj),
}
json.dump(out, open("results/final/v2/label_structure.json", "w", encoding="utf-8"), indent=2)
print(f"\nwrote results/final/v2/label_structure.json")
