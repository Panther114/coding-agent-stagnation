"""The decisive comparison: sequential-external vs pooled-threshold, on one ROC.

The sequential test with an external reference reached 21% detection at 5% false alarms. That is
only a result if the pooled threshold does *worse* at the same false-alarm rate -- otherwise it is
the same detector with a different dial. Put both on one detection/false-alarm curve, over the
full sweep, and report the detection each achieves at matched false-alarm rates.

Usage: python scripts/compare_detectors_roc.py
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

GOLD = "data/annotations/tb2/adjudicated.csv"
SCORES = "results/final/tb2_v5/monitor_scores.parquet"
OUT = "results/final/v2"
W = 10
MON = "B4_semantic"


def load():
    gold = [r for r in csv.DictReader(open(GOLD, encoding="utf-8")) if r["binary"] != ""]
    by_traj = collections.defaultdict(list)
    for r in gold:
        by_traj[r["traj_id"]].append(r)
    for t in by_traj:
        by_traj[t].sort(key=lambda r: int(r["t"]))
    series = collections.defaultdict(dict)
    for r in pq.read_table(SCORES, columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist():
        if r["w"] == W and r["monitor"] == MON:
            series[r["traj_id"]][r["t"]] = r["score"]
    return by_traj, series


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
    by_traj, series = load()
    regs = []
    for tid, rs in by_traj.items():
        regs += regions_of(rs)
    pos = [g for g in regs if g["label"] == 1]
    neg = [g for g in regs if g["label"] == 0]
    print(f"{len(pos)} episodes, {len(neg)} productive regions")

    # ---------- detector A: pooled labelled quantile, full sweep ----------
    base = np.array([v for v in (series[g["traj"]].get(t) for g in neg for t in g["windows"])
                     if v is not None and v == v])
    A = []
    for q in np.arange(0.30, 1.0001, 0.01):
        thr = float(np.quantile(base, min(q, 1.0)))
        det = sum(1 for g in pos
                  if any((series[g["traj"]].get(t) or -9) > thr for t in g["windows"]))
        fp = sum(1 for g in neg
                 if any((series[g["traj"]].get(t) or -9) > thr for t in g["windows"]))
        A.append((det / len(pos), fp / len(neg)))

    # ---------- detector B: sequential LLR, leave-one-run-out, full sweep ----------
    # precompute per-region the running LLR path once per run-exclusion, then sweep boundaries
    paths = {}
    for g in pos + neg:
        tid = g["traj"]
        oth = [h for h in regs if h["traj"] != tid]
        p = np.array([v for v in (series[h["traj"]].get(t) for h in oth if h["label"] == 1
                                  for t in h["windows"]) if v is not None and v == v])
        n = np.array([v for v in (series[h["traj"]].get(t) for h in oth if h["label"] == 0
                                  for t in h["windows"]) if v is not None and v == v])
        if len(p) < 30 or len(n) < 30:
            continue
        mu_p, sd_p = p.mean(), max(p.std(), 1e-3)
        mu_n, sd_n = n.mean(), max(n.std(), 1e-3)
        run = 0.0
        peak = -1e9
        for t in sorted(g["windows"]):
            v = series[tid].get(t)
            if v is None or v != v:
                continue
            run += (-0.5 * ((v - mu_p) / sd_p) ** 2 - np.log(sd_p)) - \
                   (-0.5 * ((v - mu_n) / sd_n) ** 2 - np.log(sd_n))
            peak = max(peak, run)
        paths[(tid, g["start"], g["label"])] = peak

    B = []
    for bnd in np.arange(-4.0, 12.01, 0.25):
        det = sum(1 for g in pos if paths.get((g["traj"], g["start"], 1), -1e9) >= bnd)
        fp = sum(1 for g in neg if paths.get((g["traj"], g["start"], 0), -1e9) >= bnd)
        B.append((det / len(pos), fp / len(neg)))

    print(f"\n=== detection rate at matched false-alarm rates ===")
    print(f"  {'FA':>6}{'pooled (A)':>13}{'sequential (B)':>16}{'gain':>8}")
    rows = []
    for target in (0.02, 0.05, 0.10, 0.20, 0.30):
        a = max([t for f, t in A if f <= target], default=float("nan"))
        b = max([t for f, t in B if f <= target], default=float("nan"))
        gain = (b - a) if (a == a and b == b) else float("nan")
        rows.append({"fa": target, "pooled": a, "sequential": b, "gain": gain})
        print(f"  {target:>6.2f}{a:>13.2f}{b:>16.2f}{gain:>+8.2f}")

    # AUC of the detection/false-alarm curve, a single summary
    def curve_auc(pts):
        pts = sorted(pts)
        xs = [f for f, _ in pts]; ys = [t for _, t in pts]
        return float(np.trapezoid(ys, xs) / (xs[-1] - xs[0])) if xs[-1] > xs[0] else float("nan")

    auc_a, auc_b = curve_auc(A), curve_auc(B)
    print(f"\n  area under the detection/false-alarm curve: pooled {auc_a:.3f}  "
          f"sequential {auc_b:.3f}  ({auc_b - auc_a:+.3f})")

    json.dump({"matched": rows, "curve_auc_pooled": auc_a, "curve_auc_sequential": auc_b,
               "n_episodes": len(pos), "n_productive_regions": len(neg),
               "curve_pooled": A, "curve_sequential": B},
              open(os.path.join(OUT, "detector_roc.json"), "w", encoding="utf-8"), indent=2)
    print(f"\nwrote {OUT}/detector_roc.json")


if __name__ == "__main__":
    main()
