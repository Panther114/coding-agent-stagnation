"""Structural detectors, vectorised. Same design as before, fast enough to sweep.

Both detectors (a) subtract a trend estimated from OTHER runs of the same task, and (b) reference
the run's detrended opening phase -- label-free, uncontaminated, and stationary once the drift is
removed. That combination is what the earlier failures pointed to:
  opening baseline alone fails because of drift (91% FA);
  no fixed threshold works while the drift is present;
  the run's recent history is contaminated once a stall begins.

Usage: python scripts/test_structural_detectors.py
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


def detrend(series, task_of, mode):
    """Detrend each run. Task mode groups runs by task ONCE (not per run)."""
    out = {}
    # group steps by task first, so the task-trend fit is not O(runs^2)
    task_xy = collections.defaultdict(lambda: ([], []))
    if mode == "task":
        for tid, sc in series.items():
            task = task_of.get(tid)
            xs, ys = task_xy[task]
            for t in sorted(sc):
                if sc[t] == sc[t]:
                    xs.append(t); ys.append(sc[t])
    task_coef = {}
    if mode == "task":
        for task, (xs, ys) in task_xy.items():
            if len(xs) >= 60:
                task_coef[task] = np.polyfit(np.array(xs, dtype=float), np.array(ys), 2)

    for tid, sc in series.items():
        ts = sorted(t for t in sc if sc[t] == sc[t])
        if len(ts) < 12:
            continue
        x = np.array(ts, dtype=float)
        y = np.array([sc[t] for t in ts])
        coef = task_coef.get(task_of.get(tid)) if mode == "task" else None
        if coef is None:
            k = max(12, int(0.20 * len(ts)))
            coef = np.polyfit(x[:k], y[:k], 1)
        out[tid] = {t: float(v - np.polyval(coef, t)) for t, v in zip(ts, y)}
    return out


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
    task_of = {g["traj"]: g["traj"].split("__")[0] for g in regs}
    n_steps = {t: max(int(r["n_steps"]) for r in rs) for t, rs in by_traj.items()}
    print(f"episodes {len(pos)}; productive regions {len(neg)}; productive windows "
          f"{len(prod_windows)}")

    results = {}
    best = None
    for mon in ("C3_evid_sem", "B4_semantic", "B5_novelty", "C4_all_hand", "L_sem"):
        _, series = load(mon)
        for dmode in ("task", "self"):
            dtr = detrend(series, task_of, dmode)
            if not dtr:
                continue
            # rank-normalise each detrended run: scale-free across runs
            rank = {}
            for tid, sc in dtr.items():
                ts = sorted(sc)
                v = np.array([sc[t] for t in ts])
                order = np.argsort(np.argsort(v))
                rank[tid] = {t: float(order[i]) / max(1, len(ts) - 1)
                             for i, t in enumerate(ts)}
            # opening baselines per run for both z and rank variants
            open_frac = 0.15
            base_z, base_q = {}, {}
            for tid, sc in dtr.items():
                lim = open_frac * n_steps.get(tid, 1)
                b = [v for t, v in sc.items() if t <= lim]
                if len(b) >= 5:
                    base_z[tid] = (float(np.mean(b)), float(np.std(b)) + 1e-6)
                br = [v for t, v in rank.get(tid, {}).items() if t <= lim]
                if len(br) >= 5:
                    base_q[tid] = float(np.quantile(br, 0.90))

            def evaluate(kind, k, m):
                det = 0
                for g in pos:
                    tid = g["traj"]
                    if kind == "z":
                        if tid not in base_z:
                            continue
                        mu, sd = base_z[tid]
                        thr = mu + k * sd
                        sc = dtr[tid]
                        vals = [sc.get(t) for t in sorted(g["windows"])]
                    else:
                        if tid not in base_q:
                            continue
                        thr = base_q[tid]
                        sc = rank[tid]
                        vals = [sc.get(t) for t in sorted(g["windows"])]
                    run = 0
                    hit = False
                    for v in vals:
                        if v is None:
                            continue
                        if v > thr:
                            run += 1
                            if run >= m:
                                hit = True
                                break
                        else:
                            run = 0
                    if hit:
                        det += 1
                fa = 0
                for tid, t in prod_windows:
                    if kind == "z":
                        if tid not in base_z:
                            continue
                        mu, sd = base_z[tid]
                        v = dtr[tid].get(t)
                        if v is not None and v > mu + k * sd:
                            fa += 1
                    else:
                        if tid not in base_q:
                            continue
                        v = rank[tid].get(t)
                        if v is not None and v > base_q[tid]:
                            fa += 1
                return det / max(1, len(pos)), fa / max(1, len(prod_windows))

            for kind, ks in (("z", (-0.5, 0.0, 0.5, 1.0, 1.5, 2.0)),
                             ("rank", (0.80, 0.85, 0.90, 0.95))):
                for k in ks:
                    for m in (1, 2, 3):
                        det, fa = evaluate(kind, k, m)
                        tag = f"{mon}|{dmode}|{kind}={k}|m{m}"
                        ok = det > 0.50 and fa < 0.20
                        results[tag] = {"det": det, "fa": fa, "target_met": bool(ok)}
                        if ok and (best is None or det > best[0]):
                            best = (det, fa, tag)
                            print(f"  *** TARGET MET *** {tag}: det {det:.2f} FA {fa:.3f}")

    top = sorted([kv for kv in results.items() if kv[1]["fa"] < 0.20],
                 key=lambda kv: -kv[1]["det"])
    print("\nbest under a 20% false-alarm budget:")
    for tag, r in top[:10]:
        print(f"  {tag:48} det {r['det']:.2f}  FA {r['fa']:.3f}"
              f"  {'MET' if r['target_met'] else ''}")
    n_met = sum(1 for r in results.values() if r["target_met"])
    print(f"\nconfigurations meeting the target: {n_met}/{len(results)}")
    json.dump({"results": results, "best": best, "n_met": n_met},
              open(os.path.join(OUT, "structural_detectors.json"), "w", encoding="utf-8"),
              indent=2)
    print(f"wrote {OUT}/structural_detectors.json")


if __name__ == "__main__":
    main()
