"""Multi-scale ensemble alarm: does agreeing across window sizes improve the trade?

The single-scale detector (B5_novelty, 3-window smoothing, opening baseline) reaches 0.53 detection
at 0.166 window-level false alarms. Because a stall has no fixed duration -- labelled episodes run
from 10 to 312 steps -- a detector built on one context width is necessarily right for some
episodes and wrong for others. The frozen feature table stores two context widths (w=10 and w=20),
so the natural test is whether requiring or aggregating agreement across widths improves the
trade-off.

Variants:
  single   : the documented detector at w=10
  max      : alarm when either width's smoothed score exceeds its own opening baseline
  min      : alarm only when BOTH widths exceed their baselines (consensus, fewer false alarms)
  mean     : the average of the two standardised scores against the opening baseline

Usage: python scripts/test_multiscale_alarm.py
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
MON = "B5_novelty"
K_SMOOTH = 3
K_SD = 1.0
OPEN_FRAC = 0.15


def series_for(w, mon=MON):
    s = collections.defaultdict(dict)
    for r in pq.read_table(SCORES, columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist():
        if r["w"] == w and r["monitor"] == mon:
            s[r["traj_id"]][r["t"]] = r["score"]
    return s


def smooth(sc, k=K_SMOOTH):
    ts = sorted(t for t in sc if sc[t] == sc[t])
    v = np.array([sc[t] for t in ts], dtype=float)
    return {t: float(np.mean(v[max(0, i - k + 1):i + 1])) for i, t in enumerate(ts)}


def zscore_against_opening(sm, n, frac=OPEN_FRAC):
    lim = frac * n
    b = [v for t, v in sm.items() if t <= lim]
    if len(b) < 5:
        return {}
    mu, sd = float(np.mean(b)), float(np.std(b)) + 1e-6
    return {t: (v - mu) / sd for t, v in sm.items()}


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
        cur = None
        for r in rs:
            lab, t = int(r["binary"]), int(r["t"])
            if cur and lab == cur["label"]:
                cur["windows"].append(t); cur["end"] = max(cur["end"], t)
            else:
                if cur:
                    regs.append(cur)
                cur = {"traj": tid, "label": lab, "start": t, "end": t, "windows": [t]}
        if cur:
            regs.append(cur)
    pos = [g for g in regs if g["label"] == 1]
    neg = [g for g in regs if g["label"] == 0]
    prod_windows = [(g["traj"], t) for g in neg for t in g["windows"]]
    print(f"episodes {len(pos)}; productive regions {len(neg)}; productive windows "
          f"{len(prod_windows)}")

    Z = {}
    for w in (10, 20):
        s = series_for(w)
        Z[w] = {}
        for tid, sc in s.items():
            Z[w][tid] = zscore_against_opening(smooth(sc), n_steps.get(tid, 1))

    def evaluate(agg, thr):
        det = fa_w = 0
        for g in pos:
            tid = g["traj"]
            if not all(tid in Z[w] for w in (10, 20)):
                continue
            fired = False
            for t in sorted(g["windows"]):
                vals = [Z[w][tid].get(t) for w in (10, 20)]
                vals = [v for v in vals if v is not None]
                if not vals:
                    continue
                score = {"single": vals[0] if len(vals) == 1 else Z[10][tid].get(t),
                         "max": max(vals), "min": min(vals),
                         "mean": float(np.mean(vals))}[agg]
                if score is not None and score > thr:
                    fired = True
                    break
            if fired:
                det += 1
        for tid, t in prod_windows:
            if not all(tid in Z[w] for w in (10, 20)):
                continue
            vals = [Z[w][tid].get(t) for w in (10, 20)]
            vals = [v for v in vals if v is not None]
            if not vals:
                continue
            score = {"single": Z[10][tid].get(t), "max": max(vals), "min": min(vals),
                     "mean": float(np.mean(vals))}[agg]
            if score is not None and score > thr:
                fa_w += 1
        return det / max(1, len(pos)), fa_w / max(1, len(prod_windows))

    print(f"\n{'aggregate':10}{'threshold':>11}{'detection':>11}{'FA_win':>9}")
    results = {}
    best = None
    for agg in ("single", "max", "min", "mean"):
        for thr in (0.0, 0.5, 0.75, 1.0, 1.25, 1.5):
            det, fa = evaluate(agg, thr)
            ok = det > 0.50 and fa < 0.20
            results[f"{agg}|{thr}"] = {"det": det, "fa": fa, "met": bool(ok)}
            mark = "  *** MET ***" if ok else ""
            print(f"{agg:10}{thr:>11.2f}{det:>11.2f}{fa:>9.3f}{mark}")
            if ok and (best is None or det > best[0]):
                best = (det, fa, agg, thr)

    met = [k for k, v in results.items() if v["met"]]
    print(f"\nconfigurations meeting the target: {len(met)}")
    if best:
        print(f"best: {best[2]} at threshold {best[3]} -> detection {best[0]:.2f} "
              f"at FA {best[1]:.3f}")
    json.dump({"results": results, "best": best, "n_met": len(met)},
              open(os.path.join(OUT, "multiscale_alarm.json"), "w", encoding="utf-8"), indent=2)
    print(f"wrote {OUT}/multiscale_alarm.json")


if __name__ == "__main__":
    main()
