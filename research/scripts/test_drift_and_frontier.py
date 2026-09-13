"""TEST 3 + the frontier: how much of the detector's failure is score drift?

Test 1 (opening baseline) failed hard -- 88% detected at 91% false alarms -- because the opening
score sits far below later scores, so a threshold anchored to the opening flags almost every later
window. Before trying anything else, quantify the drift, because if the score has a strong
within-run trend then:

  * no fixed threshold can work, and
  * Detector A's apparent respectability (57% / 46%) is partly an accident of where the pooled
    quantile happens to fall relative to that trend.

The decisive test is whether **detrending** helps. If removing each run's trend and then
thresholding improves the detection/false-alarm trade materially, the obstacle was drift and it is
removable. If not, the obstacle is noise, and no calibration will fix it.

Also report the full frontier over pooled quantiles (Test 3), not three arbitrary points.

Usage: python scripts/test_drift_and_frontier.py
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

GOLD = "../datasets/annotations/tb2/adjudicated.csv"
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
    n_steps = {t: max(int(r["n_steps"]) for r in rs) for t, rs in by_traj.items()}
    series = collections.defaultdict(dict)
    for r in pq.read_table(SCORES, columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist():
        if r["w"] == W and r["monitor"] == mon:
            series[r["traj_id"]][r["t"]] = r["score"]
    return by_traj, n_steps, series


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


def detect_fp(sc_used, pos, neg, thr, m):
    def hit(sc, steps):
        run = 0
        for t in steps:
            v = sc.get(t)
            if v is None or v != v:
                continue
            if v > thr:
                run += 1
                if run >= m:
                    return True
            else:
                run = 0
        return False
    det = sum(1 for g in pos if hit(sc_used[g["traj"]], sorted(g["windows"])))
    fp = sum(1 for g in neg if hit(sc_used[g["traj"]], sorted(g["windows"])))
    return det, fp


def main() -> None:
    out = {}
    for mon in ("B4_semantic",):
        by_traj, n_steps, series = load(mon)
        regs = []
        for tid, rs in by_traj.items():
            regs += regions_of(rs)
        pos = [g for g in regs if g["label"] == 1]
        neg = [g for g in regs if g["label"] == 0]
        print(f"=== {mon}: {len(pos)} episodes, {len(neg)} productive regions ===")

        # ---------- quantify within-run trend ----------
        print("\n--- 1. within-run score trend ---")
        slopes, corrs = [], []
        for tid, sc in series.items():
            ts = sorted(t for t in sc if sc[t] == sc[t])
            if len(ts) < 10:
                continue
            x = np.array(ts, dtype=float)
            y = np.array([sc[t] for t in ts])
            s = np.polyfit(x, y, 1)[0]
            slopes.append(s)
            corrs.append(float(np.corrcoef(x, y)[0, 1]))
        slopes = np.array(slopes); corrs = np.array([c for c in corrs if np.isfinite(c)])
        print(f"  runs: {len(slopes)}; mean slope {slopes.mean():+.5f} per step "
              f"(median {np.median(slopes):+.5f})")
        print(f"  runs with a positive trend: {int((slopes>0).sum())}/{len(slopes)}")
        print(f"  mean |correlation| of score with step: {np.abs(corrs).mean():.3f} "
              f"(median {np.median(np.abs(corrs)):.3f})")
        out["n_runs_trended"] = int(len(slopes))
        out["mean_slope"] = float(slopes.mean())
        out["runs_positive_trend"] = int((slopes > 0).sum())
        out["mean_abs_corr_with_step"] = float(np.abs(corrs).mean())

        # ---------- detrend each run, then repeat the detector ----------
        print("\n--- 2. does detrending help? (remove each run's linear trend) ---")
        detr = collections.defaultdict(dict)
        for tid, sc in series.items():
            ts = sorted(t for t in sc if sc[t] == sc[t])
            if len(ts) < 10:
                detr[tid] = dict(sc)
                continue
            x = np.array(ts, dtype=float); y = np.array([sc[t] for t in ts])
            b, a = np.polyfit(x, y, 1)
            for t in sc:
                if sc[t] == sc[t]:
                    detr[tid][t] = float(sc[t] - (a + b * t))
        base_all = [detr[g["traj"]].get(t) for g in neg for t in g["windows"]]
        base_all = [v for v in base_all if v is not None and v == v]
        print(f"  {'threshold':>18}{'m':>3}{'detect':>9}{'FA':>9}")
        for q in (0.70, 0.80, 0.90, 0.95):
            thr = float(np.quantile(base_all, q))
            for m in (1, 3):
                det, fp = detect_fp(detr, pos, neg, thr, m)
                print(f"  {f'detrended q={q:.2f}':>18}{m:>3}"
                      f"{f'{det}/{len(pos)} ({100*det/len(pos):.0f}%)':>9}"
                      f"{f'{fp}/{len(neg)} ({100*fp/len(neg):.0f}%)':>9}")
                out.setdefault("detrended", {})[f"q{q}_m{m}"] = {"det": det, "fp": fp}

        # ---------- frontier on the raw score (Test 3) ----------
        print("\n--- 3. full frontier, raw score, pooled labelled quantile ---")
        base_raw = [series[g["traj"]].get(t) for g in neg for t in g["windows"]]
        base_raw = [v for v in base_raw if v is not None and v == v]
        frontier = []
        for q in np.arange(0.50, 0.9999, 0.05):
            thr = float(np.quantile(base_raw, q))
            det, fp = detect_fp(series, pos, neg, thr, 1)
            tpr = det / len(pos); fpr = fp / len(neg)
            frontier.append((round(float(q), 2), tpr, fpr))
            print(f"  q={q:.2f}: detect {tpr:.2f}  FA {fpr:.2f}")
        out["frontier_raw"] = frontier

        # ---------- the key comparison at matched false-alarm rate ----------
        print("\n--- 4. matched comparison: detection when false alarms are pinned to 10% ---")
        for label, used, base in (("raw", series, base_raw),
                                  ("detrended", detr, base_all)):
            # find threshold giving ~10% FA
            best = None
            for q in np.arange(0.50, 0.9999, 0.01):
                thr = float(np.quantile(base, q))
                det, fp = detect_fp(used, pos, neg, thr, 1)
                fpr = fp / len(neg)
                if fpr <= 0.12:
                    if best is None or det > best[1]:
                        best = (q, det, fp)
            if best:
                print(f"  {label:10} q={best[0]:.2f}  detect {best[1]}/{len(pos)} "
                      f"({100*best[1]/len(pos):.0f}%)  FA {best[2]}/{len(neg)} "
                      f"({100*best[2]/len(neg):.0f}%)")
                out.setdefault("fa10", {})[label] = {"det": best[1], "fp": best[2],
                                                     "q": float(best[0])}

    json.dump(out, open(os.path.join(OUT, "drift_frontier_test.json"), "w", encoding="utf-8"),
              indent=2)
    print(f"\nwrote {OUT}/drift_frontier_test.json")


if __name__ == "__main__":
    main()
