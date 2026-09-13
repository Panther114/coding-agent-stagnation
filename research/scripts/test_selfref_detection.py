"""Self-referential detection done properly: rank the current score within the run's own history.

The trailing-window z-score failed because once a run enters stagnation its own recent history is
polluted -- the reference drifts with it. The run's *whole* score distribution is a stable
reference: a runtime knows it, needs no labels, and it is exactly the calibration the previous test
showed was missing.

Three label-free rules, compared under identical episode accounting:

  A  global threshold      : fixed quantile of all labelled productive windows  (needs labels)
  D  within-run rank       : percentile of the current score in the run's own scores (label-free)
  E  within-run rank, sustained for m steps                                    (label-free)

Report episodes detected, median latency, and false alarms per productive region. Also report the
"peak vs the run's productive median" rule as the upper reference, since that one uses labels.
"""
from __future__ import annotations

import bisect
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


def first_sustained(sc, steps, rule, m):
    run = 0
    for t in steps:
        v = sc.get(t)
        if v is None or v != v:
            continue
        if rule(t, v):
            run += 1
            if run >= m:
                return t - (m - 1)
        else:
            run = 0
    return None


def evaluate(by_traj, series, rule_factory, m, pos, neg):
    det, lat = 0, []
    for g in pos:
        sc = series[g["traj"]]
        steps = sorted(sc)
        t0 = first_sustained(sc, sorted(g["windows"]), rule_factory(sc, steps), m)
        if t0 is not None:
            det += 1
            lat.append(t0 - min(g["windows"]))
    fp = 0
    for g in neg:
        sc = series[g["traj"]]
        steps = sorted(sc)
        if first_sustained(sc, sorted(g["windows"]), rule_factory(sc, steps), m) is not None:
            fp += 1
    return det, lat, fp


def main() -> None:
    out = {}
    for mon in ("B4_semantic", "L_sem", "B5_novelty", "C3_evid_sem"):
        by_traj, series = load(mon)
        regs = []
        for tid, rs in by_traj.items():
            regs += regions_of(rs)
        pos = [g for g in regs if g["label"] == 1]
        neg = [g for g in regs if g["label"] == 0]
        base_lab = [series[g["traj"]].get(t) for g in neg for t in g["windows"]]
        base_lab = [v for v in base_lab if v is not None and v == v]
        if not base_lab:
            continue
        print(f"\n=== {mon}: {len(pos)} episodes, {len(neg)} productive regions ===")

        # ---- A: global labelled quantile ----
        for q in (0.80, 0.90):
            thr = float(np.quantile(base_lab, q))
            det, lat, fp = evaluate(by_traj, series,
                                    lambda sc, steps, thr=thr: (lambda t, v: v > thr), 1, pos, neg)
            print(f"  A global q={q:.2f}:  detect {det:>2}/{len(pos)} "
                  f"({100*det/len(pos):>3.0f}%)  lat {st.median(lat) if lat else float('nan'):>4.0f}"
                  f"  FA {fp:>3}/{len(neg)} ({100*fp/len(neg):>3.0f}%)")
            out.setdefault(mon, {})[f"A_q{q}"] = {"det": det, "fp": fp,
                                                  "lat": st.median(lat) if lat else None}

        # ---- D/E: within-run rank (label-free) ----
        def rank_rule(q, m):
            def factory(sc, steps):
                vals = sorted(v for v in (sc.get(t) for t in steps) if v is not None and v == v)
                if not vals:
                    return lambda t, v: False

                def rule(t, v):
                    r = bisect.bisect_right(vals, v) / len(vals)
                    return r >= q
                return rule
            return factory

        for q in (0.80, 0.90, 0.95):
            for m in (1, 3):
                det, lat, fp = evaluate(by_traj, series, rank_rule(q, m), m, pos, neg)
                tag = "D" if m == 1 else "E"
                print(f"  {tag} within-run rank q={q:.2f} m={m}: detect {det:>2}/{len(pos)} "
                      f"({100*det/len(pos):>3.0f}%)  "
                      f"lat {st.median(lat) if lat else float('nan'):>4.0f}  "
                      f"FA {fp:>3}/{len(neg)} ({100*fp/len(neg):>3.0f}%)")
                out.setdefault(mon, {})[f"{tag}_q{q}_m{m}"] = {
                    "det": det, "fp": fp, "lat": st.median(lat) if lat else None}

        # ---- reference: peak vs the run's labelled productive median ----
        det = 0
        for g in pos:
            rv = [series[g["traj"]].get(t) for t in g["windows"]]
            rv = [v for v in rv if v is not None and v == v]
            nv = [series[h["traj"]].get(t) for h in neg if h["traj"] == g["traj"]
                  for t in h["windows"]]
            nv = [v for v in nv if v is not None and v == v]
            if rv and nv and max(rv) > float(np.median(nv)):
                det += 1
        print(f"  REF peak > run's productive median (uses labels): {det}/{len(pos)} "
              f"({100*det/len(pos):.0f}%)")
        out.setdefault(mon, {})["REF_peak_vs_run_median"] = {"det": det}

    json.dump(out, open(os.path.join(OUT, "selfref_detection.json"), "w", encoding="utf-8"),
              indent=2)
    print(f"\nwrote {OUT}/selfref_detection.json")


if __name__ == "__main__":
    main()
