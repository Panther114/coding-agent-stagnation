"""The stagnation alarm: a documented, runnable detector.

Specification, all quantities computable online from the run's own history:

  1. Monitor score s(t)      : any of the frozen monitors' per-window scores (default B5_novelty,
                               relevance-blind novelty). Higher = more stagnant.
  2. Smoothing               : s_bar(t) = mean of the last K scores, K = 3.
                               The score is a window statistic and therefore noisy; averaging
                               three consecutive windows is what makes the series usable, and it
                               was worth 9 points of detection over the unsmoothed score.
  3. Baseline                : mu, sd = mean and standard deviation of s_bar over the run's own
                               first 15% of steps. No labels, no other runs, and -- crucially --
                               observed before a stall can plausibly begin (only 5 of 68 episodes
                               start that early).
  4. Alarm rule              : alarm at the first step where s_bar(t) > mu + 1.0 * sd.
  5. Episode decision        : an episode is flagged if any of its windows alarms.

Why this works when the earlier attempts failed:
  * the level of s is non-stationary (rises with run progress, r = 0.52), which broke every fixed
    pooled threshold -- anchoring the baseline to the run's own opening removes that;
  * the run's RECENT history is contaminated once a stall begins, which broke every trailing-window
    reference -- the opening is fixed before the stall;
  * the raw window score is noisy, which capped detection regardless of threshold -- smoothing
    three windows fixes it.

Verified result (see results/final/v2/nested_validation.json): 5-fold nested validation over 80
runs, configuration chosen on training folds only. Detection 0.559 (38/68 episodes) at a
window-level false-alarm rate of 0.181.

Usage: python scripts/stagnation_alarm.py --run results/final/tb2_v5
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
import pyarrow.parquet as pq

GOLD = "data/annotations/tb2/adjudicated.csv"
W = 10
DEFAULT_MONITOR = "B5_novelty"
K_SMOOTH = 3
K_SD = 1.0
OPEN_FRAC = 0.15


def load_scores(run: str, monitor: str):
    series = collections.defaultdict(dict)
    tab = pq.read_table(os.path.join(run, "monitor_scores.parquet"),
                        columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist()
    for r in tab:
        if r["w"] == W and r["monitor"] == monitor:
            series[r["traj_id"]][r["t"]] = r["score"]
    return series


def smooth(sc: dict, k: int = K_SMOOTH) -> dict:
    ts = sorted(t for t in sc if sc[t] == sc[t])
    v = np.array([sc[t] for t in ts], dtype=float)
    return {t: float(np.mean(v[max(0, i - k + 1):i + 1])) for i, t in enumerate(ts)}


def baseline(sm: dict, n_steps: int, frac: float = OPEN_FRAC):
    lim = frac * n_steps
    b = [v for t, v in sm.items() if t <= lim]
    if len(b) < 5:
        return None
    return float(np.mean(b)), float(np.std(b)) + 1e-6


def alarms(sm: dict, n_steps: int, k_sd: float = K_SD, frac: float = OPEN_FRAC):
    base = baseline(sm, n_steps, frac)
    if base is None:
        return [], None
    mu, sd = base
    thr = mu + k_sd * sd
    fired = [t for t in sorted(sm) if sm[t] > thr]
    return fired, thr


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="results/final/tb2_v5")
    ap.add_argument("--monitor", default=DEFAULT_MONITOR)
    ap.add_argument("--out", default="results/final/v2/alarm_artifact.json")
    args = ap.parse_args()

    gold = [r for r in csv.DictReader(open(GOLD, encoding="utf-8")) if r["binary"] != ""]
    by_traj = collections.defaultdict(list)
    for r in gold:
        by_traj[r["traj_id"]].append(r)
    for t in by_traj:
        by_traj[t].sort(key=lambda r: int(r["t"]))
    n_steps = {t: max(int(r["n_steps"]) for r in rs) for t, rs in by_traj.items()}
    series = load_scores(args.run, args.monitor)
    print(f"monitor {args.monitor}; runs scored {len(series)}")

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

    det = lat = 0
    latencies = []
    fa_w = prod_w = 0
    fa_ep = 0
    for tid in by_traj:
        sc = series.get(tid)
        if not sc:
            continue
        sm = smooth(sc)
        fired, thr = alarms(sm, n_steps.get(tid, 1))
        fset = set(fired)
        for g in regs:
            if g["traj"] != tid:
                continue
            hit = sorted(fset & set(g["windows"]))
            if g["label"] == 1:
                if hit:
                    det += 1
                    latencies.append(hit[0] - g["start"])
            else:
                prod_w += len(g["windows"])
                fa_w += len(fset & set(g["windows"]))
                if hit:
                    fa_ep += 1

    result = {
        "monitor": args.monitor, "k_smooth": K_SMOOTH, "k_sd": K_SD, "open_frac": OPEN_FRAC,
        "episodes": len(pos), "episodes_detected": det,
        "detection_rate": det / max(1, len(pos)),
        "median_latency_steps": float(np.median(latencies)) if latencies else None,
        "productive_windows": prod_w, "false_alarm_windows": fa_w,
        "false_alarm_window_rate": fa_w / max(1, prod_w),
        "productive_regions": len(neg), "false_alarm_regions": fa_ep,
        "false_alarm_region_rate": fa_ep / max(1, len(neg)),
        "target_met_window_level": bool(det / max(1, len(pos)) > 0.50
                                        and fa_w / max(1, prod_w) < 0.20),
    }
    json.dump(result, open(args.out, "w", encoding="utf-8"), indent=2)
    print(json.dumps(result, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
