"""TEST 1: the opening-baseline detector.

Freeze each run's threshold from its own opening phase -- legitimate online, needs no labels --
then alarm when the score exceeds it for m consecutive steps. Sweep the opening fraction and the
multiplier to find the achievable detection / false-alarm frontier, and compare against the
pooled-threshold baseline (57% detected at 46% false alarms).

Two reference forms, because the opening sits ~0.28 below later productive regions:
  R1  mu_open + k*sd_open                (absolute offset from the opening)
  R2  quantile of the opening scores     (scale-free within the run)
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


def alarm_within(sc, steps, rule, m):
    run = 0
    for t in steps:
        v = sc.get(t)
        if v is None or v != v:
            continue
        if rule(v):
            run += 1
            if run >= m:
                return True
        else:
            run = 0
    return False


def evaluate(by_traj, n_steps, series, rule_factory, m, pos, neg):
    det = 0
    for g in pos:
        sc = series[g["traj"]]
        if alarm_within(sc, sorted(g["windows"]), rule_factory(g["traj"], sc), m):
            det += 1
    fp = 0
    for g in neg:
        sc = series[g["traj"]]
        if alarm_within(sc, sorted(g["windows"]), rule_factory(g["traj"], sc), m):
            fp += 1
    return det, fp


def main() -> None:
    out = {}
    for mon in ("B4_semantic", "B5_novelty"):
        by_traj, n_steps, series = load(mon)
        regs = []
        for tid, rs in by_traj.items():
            regs += regions_of(rs)
        pos = [g for g in regs if g["label"] == 1]
        neg = [g for g in regs if g["label"] == 0]
        print(f"\n================ {mon}: {len(pos)} episodes, {len(neg)} productive regions")

        # baseline for comparison: pooled labelled threshold at q=0.80
        base_all = [series[g["traj"]].get(t) for g in neg for t in g["windows"]]
        base_all = [v for v in base_all if v is not None and v == v]
        thr_pool = float(np.quantile(base_all, 0.80))
        det, fp = evaluate(by_traj, n_steps, series, lambda tid, sc: (lambda v: v > thr_pool),
                           1, pos, neg)
        print(f"  pooled labelled threshold q=0.80: detect {det}/{len(pos)} "
              f"({100*det/len(pos):.0f}%)  FA {fp}/{len(neg)} ({100*fp/len(neg):.0f}%)")
        out.setdefault(mon, {})["pooled_q80"] = {"det": det, "fp": fp}

        # ---- R1: opening mean + k*sd ----
        print("\n  R1: opening mean + k*sd_open (opening = first N% of steps)")
        for frac in (0.10, 0.20):
            for k in (0.0, 0.5, 1.0, 1.5, 2.0):
                def mk(tid, sc, frac=frac, k=k):
                    lim = frac * n_steps[tid]
                    early = [v for t, v in sc.items() if t <= lim and v == v]
                    if len(early) < 5:
                        return lambda v: False
                    thr = float(np.mean(early)) + k * float(np.std(early))
                    return lambda v: v > thr
                for m in (1, 3):
                    det, fp = evaluate(by_traj, n_steps, series, mk, m, pos, neg)
                    print(f"    frac={frac:.0%} k={k:.1f} m={m}: detect {det:>2}/{len(pos)} "
                          f"({100*det/len(pos):>3.0f}%)  FA {fp:>3}/{len(neg)} "
                          f"({100*fp/len(neg):>3.0f}%)")
                    out.setdefault(mon, {})[f"R1_f{frac}_k{k}_m{m}"] = {"det": det, "fp": fp}

        # ---- R2: quantile of the opening scores ----
        print("\n  R2: quantile of the opening scores")
        for frac in (0.10, 0.20):
            for q in (0.90, 0.95, 1.00):
                def mk2(tid, sc, frac=frac, q=q):
                    lim = frac * n_steps[tid]
                    early = [v for t, v in sc.items() if t <= lim and v == v]
                    if len(early) < 5:
                        return lambda v: False
                    thr = float(np.quantile(early, q))
                    return lambda v: v > thr
                for m in (1, 3):
                    det, fp = evaluate(by_traj, n_steps, series, mk2, m, pos, neg)
                    print(f"    frac={frac:.0%} q={q:.2f} m={m}: detect {det:>2}/{len(pos)} "
                          f"({100*det/len(pos):>3.0f}%)  FA {fp:>3}/{len(neg)} "
                          f"({100*fp/len(neg):>3.0f}%)")
                    out.setdefault(mon, {})[f"R2_f{frac}_q{q}_m{m}"] = {"det": det, "fp": fp}

    json.dump(out, open(os.path.join(OUT, "opening_baseline_test.json"), "w", encoding="utf-8"),
              indent=2)
    print(f"\nwrote {OUT}/opening_baseline_test.json")


if __name__ == "__main__":
    main()
