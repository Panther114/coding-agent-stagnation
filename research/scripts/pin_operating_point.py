"""Where exactly does the best configuration stand, under both false-alarm accountings?

The objective is "<20% false alarm rate and >50% detection rate". False alarms can be counted two
ways, and they are not interchangeable:

  window-level : share of labelled PRODUCTIVE WINDOWS that produce an alarm (strict)
  episode-level: share of PRODUCTIVE REGIONS that produce any alarm (operational -- a runtime
                 acts once per episode, not once per window)

Both are reported; the strict one was used throughout earlier work and is kept as the headline so
nothing gets flattered by the choice. Also sweeps the smoothing of the monitor score, which has not
been tried: the score is computed per window, so a run's window-level score series is itself a
signal that can be smoothed before thresholding.

Usage: python scripts/pin_operating_point.py
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


def smooth(sc, k):
    """Rolling mean over the last k window-scores (causal)."""
    ts = sorted(sc)
    v = np.array([sc[t] for t in ts], dtype=float)
    out = {}
    for i, t in enumerate(ts):
        lo = max(0, i - k + 1)
        out[t] = float(np.mean(v[lo:i + 1]))
    return out


def detrend_self(sc, frac=0.20):
    """Remove the run's own opening linear trend (observed before any stall)."""
    ts = sorted(sc)
    if len(ts) < 12:
        return dict(sc)
    x = np.array(ts, dtype=float)
    y = np.array([sc[t] for t in ts])
    k = max(12, int(frac * len(ts)))
    coef = np.polyfit(x[:k], y[:k], 1)
    return {t: float(v - np.polyval(coef, t)) for t, v in zip(ts, y)}


def main() -> None:
    gold = [r for r in csv.DictReader(open(GOLD, encoding="utf-8")) if r["binary"] != ""]
    by_traj = collections.defaultdict(list)
    for r in gold:
        by_traj[r["traj_id"]].append(r)
    for t in by_traj:
        by_traj[t].sort(key=lambda r: int(r["t"]))
    regs = []
    for tid, rs in by_traj.items():
        regs += regions_of(rs)
    pos = [g for g in regs if g["label"] == 1]
    neg = [g for g in regs if g["label"] == 0]
    prod_windows = [(g["traj"], t) for g in neg for t in g["windows"]]
    n_steps = {t: max(int(r["n_steps"]) for r in rs) for t, rs in by_traj.items()}
    print(f"episodes {len(pos)}; productive regions {len(neg)}; productive windows "
          f"{len(prod_windows)}")

    overall = []
    for mon in ("C3_evid_sem", "B4_semantic", "B5_novelty", "C4_all_hand"):
        _, series = load(mon)
        for k_sm in (1, 3, 5):
            for dm in (False, True):
                proc = {}
                for tid, sc in series.items():
                    s = smooth(sc, k_sm)
                    proc[tid] = detrend_self(s) if dm else s
                # opening baseline from the processed series
                base = {}
                for tid, sc in proc.items():
                    lim = 0.15 * n_steps.get(tid, 1)
                    b = [v for t, v in sc.items() if t <= lim]
                    if len(b) >= 5:
                        base[tid] = (float(np.mean(b)), float(np.std(b)) + 1e-6)
                for k in (0.0, 0.5, 1.0, 1.5, 2.0):
                    for m in (1, 2, 3):
                        det_w = fa_w = 0
                        for tid, t in prod_windows:
                            if tid not in base:
                                continue
                            mu, sd = base[tid]
                            v = proc[tid].get(t)
                            if v is not None and v > mu + k * sd:
                                fa_w += 1
                        det_ep = 0
                        for g in pos:
                            tid = g["traj"]
                            if tid not in base:
                                continue
                            mu, sd = base[tid]
                            thr = mu + k * sd
                            run = 0
                            for t in sorted(g["windows"]):
                                v = proc[tid].get(t)
                                if v is None:
                                    continue
                                if v > thr:
                                    run += 1
                                    if run >= m:
                                        det_ep += 1
                                        break
                                else:
                                    run = 0
                        fa_ep = 0
                        for g in neg:
                            tid = g["traj"]
                            if tid not in base:
                                continue
                            mu, sd = base[tid]
                            thr = mu + k * sd
                            run = 0
                            for t in sorted(g["windows"]):
                                v = proc[tid].get(t)
                                if v is None:
                                    continue
                                if v > thr:
                                    run += 1
                                    if run >= m:
                                        fa_ep += 1
                                        break
                                else:
                                    run = 0
                        det = det_ep / len(pos)
                        fw = fa_w / len(prod_windows)
                        fe = fa_ep / len(neg)
                        row = {"monitor": mon, "smooth": k_sm, "detrend": dm, "k": k, "m": m,
                               "det": det, "fa_window": fw, "fa_episode": fe,
                               "met_window": bool(det > 0.50 and fw < 0.20),
                               "met_episode": bool(det > 0.50 and fe < 0.20)}
                        overall.append(row)

    rows = sorted(overall, key=lambda r: -r["det"])
    print("\nbest detection overall (any false-alarm level):")
    for r in rows[:6]:
        print(f"  {r['monitor']:12} sm{r['smooth']} detr{int(r['detrend'])} k={r['k']:.1f} m{r['m']}: "
              f"det {r['det']:.2f}  FA_win {r['fa_window']:.3f}  FA_ep {r['fa_episode']:.3f}")

    for label, key in (("STRICT (window-level FA < 20%)", "met_window"),
                       ("EPISODE-level FA < 20%", "met_episode")):
        ok = [r for r in rows if r[key]]
        print(f"\n{label}: {len(ok)} configurations")
        for r in sorted(ok, key=lambda r: -r["det"])[:8]:
            print(f"  {r['monitor']:12} sm{r['smooth']} detr{int(r['detrend'])} "
                  f"k={r['k']:.1f} m{r['m']}: det {r['det']:.2f}  "
                  f"FA_win {r['fa_window']:.3f}  FA_ep {r['fa_episode']:.3f}")

    json.dump({"rows": rows,
               "met_window": sum(1 for r in rows if r["met_window"]),
               "met_episode": sum(1 for r in rows if r["met_episode"])},
              open(os.path.join(OUT, "operating_point.json"), "w", encoding="utf-8"), indent=2)
    print(f"\nwrote {OUT}/operating_point.json")


if __name__ == "__main__":
    main()
