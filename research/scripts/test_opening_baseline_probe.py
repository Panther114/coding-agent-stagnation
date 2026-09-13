"""TEST 1a: is the opening phase of a run a clean calibration reference?

The opening-baseline detector only works if a run's first steps are usually productive. Measure,
do not assume: what fraction of stagnant episodes begin inside the opening window, and how does the
opening phase's score distribution compare with the run's productive regions overall?
"""
from __future__ import annotations

import collections
import csv
import json
import os
import statistics as st
import sys

sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
import pyarrow.parquet as pq

GOLD = "../datasets/annotations/tb2/adjudicated.csv"
SCORES = "results/final/tb2_v5/monitor_scores.parquet"
W = 10
MON = "B4_semantic"


def regions_of(rs):
    regs, cur = [], None
    for r in rs:
        lab, t = int(r["binary"]), int(r["t"])
        if cur and lab == cur["label"]:
            cur["windows"].append(t); cur["end"] = max(cur["end"], t)
        else:
            if cur:
                regs.append(cur)
            cur = {"traj": r["traj_id"], "label": lab, "start": t, "end": t, "windows": [t]}
    if cur:
        regs.append(cur)
    return regs


def main() -> None:
    gold = [r for r in csv.DictReader(open(GOLD, encoding="utf-8")) if r["binary"] != ""]
    by_traj = collections.defaultdict(list)
    for r in gold:
        by_traj[r["traj_id"]].append(r)
    for t in by_traj:
        by_traj[t].sort(key=lambda r: int(r["t"]))
    n_steps = {t: max(int(r["n_steps"]) for r in rs) for t, rs in by_traj.items()}

    regs = []
    for tid, rs in by_traj.items():
        regs += regions_of(rs)
    pos = [g for g in regs if g["label"] == 1]
    neg = [g for g in regs if g["label"] == 0]

    series = collections.defaultdict(dict)
    for r in pq.read_table(SCORES, columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist():
        if r["w"] == W and r["monitor"] == MON:
            series[r["traj_id"]][r["t"]] = r["score"]

    print(f"episodes: {len(pos)} stagnant, {len(neg)} productive")

    for frac in (0.10, 0.20, 0.30):
        in_open = [g for g in pos if g["start"] <= frac * n_steps[g["traj"]]]
        print(f"\nopening {frac:.0%} of the run (baseline window):")
        print(f"  stagnant episodes beginning inside it: {len(in_open)}/{len(pos)} "
              f"({100*len(in_open)/len(pos):.0f}%)")
        # contamination: how much of the baseline window is actually labelled stagnant?
        contaminated = 0
        total = 0
        for tid, rs in by_traj.items():
            lim = frac * n_steps[tid]
            for r in rs:
                if int(r["t"]) <= lim:
                    total += 1
                    if int(r["binary"]) == 1:
                        contaminated += 1
        print(f"  labelled windows inside the window: {total}; of them stagnant: {contaminated} "
              f"({100*contaminated/max(1,total):.0f}%)")

    # score scale by opening vs productive-region mean
    print("\n=== is the opening score level representative of the run's productive level? ===")
    gaps = []
    for tid in by_traj:
        sc = series[tid]
        lim = 0.20 * n_steps[tid]
        early = [v for t, v in sc.items() if t <= lim and v == v]
        prod = [sc.get(t) for g in neg if g["traj"] == tid for t in g["windows"]]
        prod = [v for v in prod if v is not None and v == v]
        if len(early) >= 5 and prod:
            gaps.append(float(np.mean(early)) - float(np.mean(prod)))
    if gaps:
        g = np.array(gaps)
        print(f"  runs with a usable opening: {len(g)}")
        print(f"  mean(early) - mean(productive regions): mean {g.mean():+.3f} "
              f"median {np.median(g):+.3f}  sd {g.std():.3f}")
        print(f"  runs where the opening is higher than productive regions: "
              f"{int((g>0).sum())}/{len(g)}")
        print(f"  |gap| quartiles: {np.percentile(np.abs(g),[25,50,75]).round(3)}")

    # how different are score scales across runs?
    med = [np.median([v for v in series[t].values() if v == v]) for t in by_traj
           if any(v == v for v in series[t].values())]
    med = np.array([m for m in med if np.isfinite(m)])
    print(f"\n=== cross-run score-scale spread (the reason a pooled threshold fails) ===")
    print(f"  per-run median score: min {med.min():.3f}  q1 {np.percentile(med,25):.3f}  "
          f"median {np.median(med):.3f}  q3 {np.percentile(med,75):.3f}  max {med.max():.3f}")
    print(f"  sd of per-run medians: {med.std():.3f}")

    json.dump({"n_stagnant": len(pos), "n_productive": len(neg),
               "run_median_sd": float(med.std()),
               "run_median_range": [float(med.min()), float(med.max())]},
              open("results/final/v2/opening_baseline_probe.json", "w", encoding="utf-8"), indent=2)
    print("\nwrote results/final/v2/opening_baseline_probe.json")


if __name__ == "__main__":
    main()
