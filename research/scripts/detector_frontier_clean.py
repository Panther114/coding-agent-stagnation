"""Recompute the frontier cleanly, and pin the detectors at exactly matched false-alarm rates.

Previous run hit a quantile boundary bug (arange past 1.0) and reported zeros. Fix and report the
detection each detector achieves when false alarms are pinned to 5%, 10%, 20%.
"""
from __future__ import annotations

import collections
import csv
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
import pyarrow.parquet as pq

GOLD = "data/annotations/tb2/adjudicated.csv"
SCORES = "results/final/tb2_v5/monitor_scores.parquet"
OUT = "results/final/v2"
W = 10


def load(mon):
    gold = [r for r in csv.DictReader(open(GOLD, encoding="utf-8")) if r["binary"] != ""]
    by_traj = collections.defaultdict(list)
    for r in gold:
        by_traj[r["traj_id"]].append(r)
    for t in by_traj:
        by_traj[t].sort(key=lambda r: int(r["t"]))
    series = collections.defaultdict(dict)
    for r in pq.read_table(SCORES, columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist():
        if r["w"] == W and r["monitor"] == mon:
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
    out = {}
    for mon in ("B4_semantic", "B5_novelty", "C3_evid_sem"):
        by_traj, series = load(mon)
        regs = []
        for tid, rs in by_traj.items():
            regs += regions_of(rs)
        pos = [g for g in regs if g["label"] == 1]
        neg = [g for g in regs if g["label"] == 0]
        base = np.array([v for v in (series[g["traj"]].get(t) for g in neg for t in g["windows"])
                         if v is not None and v == v])
        print(f"\n=== {mon}: {len(pos)} episodes, {len(neg)} productive regions ===")

        # sweep every possible threshold: use observed scores as candidate cutoffs
        cands = np.unique(np.concatenate([base, np.array(
            [v for g in pos for v in (series[g["traj"]].get(t) for t in g["windows"])
             if v is not None and v == v])]))
        curve = []
        for thr in cands:
            det = sum(1 for g in pos
                      if any((series[g["traj"]].get(t, -9) or -9) > thr for t in g["windows"]))
            fp = sum(1 for g in neg
                     if any((series[g["traj"]].get(t, -9) or -9) > thr for t in g["windows"]))
            curve.append((fp / len(neg), det / len(pos)))
        curve.sort()
        # cumulative max for a monotone frontier
        best = -1
        front = []
        for fpr, tpr in curve:
            best = max(best, tpr)
            front.append((fpr, best))
        # collapse
        collapsed = {}
        for fpr, tpr in front:
            collapsed[fpr] = max(collapsed.get(fpr, 0), tpr)
        fs = sorted(collapsed)

        print(f"  {'FA budget':>10}{'detection':>12}")
        matched = {}
        for target in (0.05, 0.10, 0.20, 0.30):
            got = max((tpr for fpr, tpr in collapsed.items() if fpr <= target),
                      default=float("nan"))
            matched[target] = got
            print(f"  {target:>10.2f}{got:>12.2f}")
        # area under the frontier
        xs = np.array(fs); ys = np.array([collapsed[f] for f in fs])
        auc = float(np.trapezoid(ys, xs) / (xs[-1] - xs[0])) if xs[-1] > xs[0] else float("nan")
        print(f"  area under the detection/false-alarm frontier: {auc:.3f}")
        out[mon] = {"matched": matched, "curve_auc": auc, "n_pos": len(pos), "n_neg": len(neg),
                    "frontier": [[float(f), float(collapsed[f])] for f in fs][::max(1, len(fs)//50)]}

    json.dump(out, open(os.path.join(OUT, "detector_frontier.json"), "w", encoding="utf-8"),
              indent=2)
    print(f"\nwrote {OUT}/detector_frontier.json")


if __name__ == "__main__":
    main()
