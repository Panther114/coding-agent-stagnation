"""A self-referential regime-change detector, tested against the global-threshold detector.

The previous test exposed a large gap. Using a *global* threshold on the monitor's score, 47% of
stagnant episodes are detected at a 36% false-alarm rate. Using the *run's own* productive baseline
as the reference, 78% of episodes are detected. So most of the detector's error is calibration, not
signal: absolute score levels differ across runs, and a fixed threshold is wrong for most of them.

That suggests the right formulation is a **change-point detector**: watch whether the flow of new
information has dropped relative to this run's own recent history, and alarm when the shift
persists. This is a genuinely different method from window classification, it is what a runtime can
actually deploy, and it yields the metrics a runtime needs (episodes caught, latency, false alarms).

Implement three detectors on the same scores and compare them under identical episode accounting:

  A. global threshold      : score > q-quantile of all labelled productive windows
  B. within-run z-score    : score > run's own trailing mean + k * trailing sd, sustained m steps
  C. CUSUM change-point    : cumulative shortfall of "information flow" below its own baseline

Report per-episode detection, latency in steps, and false alarms per run.

Usage: python scripts/test_changepoint.py
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
    # full scored series per run (every step, not only labelled windows)
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


def sustained_alarms(steps, scores, rule, m=3):
    """First step at which `rule` holds for m consecutive available steps."""
    run = 0
    for t in steps:
        v = scores.get(t)
        if v is None or v != v:
            continue
        if rule(t, v):
            run += 1
            if run >= m:
                return t - (m - 1)
        else:
            run = 0
    return None


def main() -> None:
    by_traj, series = load()
    all_regs = []
    for tid, rs in by_traj.items():
        all_regs += regions_of(rs)
    pos = [g for g in all_regs if g["label"] == 1]
    neg = [g for g in all_regs if g["label"] == 0]
    print(f"episodes: {len(pos)} stagnant, {len(neg)} productive regions")
    print(f"monitor: {MON}")

    # ---------- detector A: global threshold ----------
    base_all = [series[g["traj"]].get(t) for g in neg for t in g["windows"]]
    base_all = [v for v in base_all if v is not None and v == v]

    def detector_A(q, m=1):
        thr = float(np.quantile(base_all, q))
        det, lat = 0, []
        for g in pos:
            t0 = sustained_alarms(sorted(g["windows"]), series[g["traj"]],
                                 lambda t, v: v > thr, m)
            if t0 is not None:
                det += 1
                lat.append(t0 - min(g["windows"]))
        fp = 0
        for g in neg:
            if sustained_alarms(sorted(g["windows"]), series[g["traj"]],
                                lambda t, v: v > thr, m) is not None:
                fp += 1
        return det, lat, fp, thr

    # ---------- detector B: within-run trailing z-score ----------
    def detector_B(k, m=3, warm=8):
        det, lat = 0, []
        for g in pos:
            sc = series[g["traj"]]
            steps = sorted(sc)
            mu = sd = None
            def rule(t, v, sc=sc, steps=steps):
                nonlocal mu, sd
                hist = [sc[x] for x in steps if x < t and sc.get(x) == sc.get(x)][-warm:]
                if len(hist) < warm // 2:
                    return False
                m_, s_ = float(np.mean(hist)), float(np.std(hist)) + 1e-6
                return v > m_ + k * s_
            t0 = sustained_alarms(sorted(g["windows"]), sc, rule, m)
            if t0 is not None:
                det += 1
                lat.append(t0 - min(g["windows"]))
        fp = 0
        for g in neg:
            sc = series[g["traj"]]
            steps = sorted(sc)
            def rule2(t, v, sc=sc, steps=steps):
                hist = [sc[x] for x in steps if x < t and sc.get(x) == sc.get(x)][-warm:]
                if len(hist) < warm // 2:
                    return False
                m_, s_ = float(np.mean(hist)), float(np.std(hist)) + 1e-6
                return v > m_ + k * s_
            if sustained_alarms(sorted(g["windows"]), sc, rule2, m) is not None:
                fp += 1
        return det, lat, fp

    # ---------- detector C: CUSUM on "information flow" ----------
    def detector_C(slack, thresh, warm=8):
        def make(sc, steps):
            ref = {}
            def rule(t, v):
                hist = [sc[x] for x in steps if x < t and sc.get(x) == sc.get(x)][-warm:]
                if len(hist) < warm // 2:
                    return False
                mu = float(np.mean(hist))
                # CUSUM accumulates how far below its own mean the signal has run
                return (mu - v) > slack
            return rule
        det, lat = 0, []
        for g in pos:
            sc = series[g["traj"]]
            steps = sorted(sc)
            t0 = sustained_alarms(sorted(g["windows"]), sc, make(sc, steps), 2)
            if t0 is not None:
                det += 1
                lat.append(t0 - min(g["windows"]))
        fp = 0
        for g in neg:
            sc = series[g["traj"]]
            steps = sorted(sc)
            if sustained_alarms(sorted(g["windows"]), sc, make(sc, steps), 2) is not None:
                fp += 1
        return det, lat, fp

    out = {"monitor": MON, "n_stagnant_episodes": len(pos), "n_productive_regions": len(neg)}
    print("\n=== A. global threshold (absolute score) ===")
    for q in (0.80, 0.90, 0.95):
        det, lat, fp, thr = detector_A(q, m=1)
        print(f"  q={q:.2f} thr={thr:.3f}: detect {det}/{len(pos)} "
              f"({100*det/len(pos):.0f}%), latency med {st.median(lat) if lat else float('nan'):.0f}, "
              f"false alarms {fp}/{len(neg)}")
        out[f"A_q{q}"] = {"detected": det, "total": len(pos), "fp": fp,
                          "median_latency": st.median(lat) if lat else None}

    print("\n=== B. within-run trailing z-score (self-referential) ===")
    for k in (0.5, 1.0, 1.5, 2.0):
        det, lat, fp = detector_B(k)
        print(f"  k={k:.1f} m=3: detect {det}/{len(pos)} ({100*det/len(pos):.0f}%), "
              f"latency med {st.median(lat) if lat else float('nan'):.0f}, "
              f"false alarms {fp}/{len(neg)}")
        out[f"B_k{k}"] = {"detected": det, "total": len(pos), "fp": fp,
                          "median_latency": st.median(lat) if lat else None}

    print("\n=== C. CUSUM on information flow ===")
    for slack in (0.1, 0.2, 0.3):
        det, lat, fp = detector_C(slack, 0)
        print(f"  slack={slack:.1f}: detect {det}/{len(pos)} ({100*det/len(pos):.0f}%), "
              f"latency med {st.median(lat) if lat else float('nan'):.0f}, "
              f"false alarms {fp}/{len(neg)}")
        out[f"C_slack{slack}"] = {"detected": det, "total": len(pos), "fp": fp,
                                  "median_latency": st.median(lat) if lat else None}

    json.dump(out, open(os.path.join(OUT, "changepoint_test.json"), "w", encoding="utf-8"),
              indent=2)
    print(f"\nwrote {OUT}/changepoint_test.json")


if __name__ == "__main__":
    main()
