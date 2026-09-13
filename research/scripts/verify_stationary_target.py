"""Verify the target honestly: threshold selected on OTHER runs, then applied held-out.

The stationary-statistics test found S5_combined (equal-weight standardised stationary stats) on
C3_evid_sem reaching 0.53 detection at 0.182 false alarms. But its threshold was swept over
quantiles of the EVALUATION scores, which leaks: a runtime does not know the score distribution of
the run it is judging, still less of the whole benchmark.

This re-evaluates with proper held-out threshold selection (leave-one-run-out): the threshold is
chosen on other runs to hit a false-alarm budget, then frozen and applied to the held-out run.
If the target survives that, it is real. Also sweeps the statistic's own hyperparameters
(epsilon fraction, window sizes) with the same discipline, so the result is not a lucky hand-tune.

Usage: python scripts/verify_stationary_target.py
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


def s1(sc, eps_frac, m_sd, m_ratio):
    ts = sorted(t for t in sc if sc[t] == sc[t])
    if len(ts) < 12:
        return {}
    v = np.array([sc[t] for t in ts], dtype=float)
    rng = float(v.max() - v.min()) or 1.0
    eps = eps_frac * rng
    gaps, last, out = [], 0, {}
    for i, t in enumerate(ts):
        if i and abs(v[i] - v[i - 1]) > eps:
            gaps.append(i - last); last = i
        ref = max(float(np.median(gaps)) if gaps else float(max(1, i - last)), 1.0)
        out[t] = (i - last) / ref
    return out


def s4(sc, m_sd):
    ts = sorted(t for t in sc if sc[t] == sc[t])
    v = np.array([sc[t] for t in ts], dtype=float)
    return {t: (float(np.std(v[max(0, i - m_sd + 1):i + 1])) if i >= m_sd else 0.0)
            for i, t in enumerate(ts)}


def s3(sc, m_ratio):
    ts = sorted(t for t in sc if sc[t] == sc[t])
    v = np.array([sc[t] for t in ts], dtype=float)
    out = {}
    for i, t in enumerate(ts):
        if i < 2 * m_ratio:
            continue
        rec = float(np.mean(v[i - m_ratio + 1:i + 1]))
        pri = float(np.mean(v[i - 2 * m_ratio + 1:i - m_ratio + 1]))
        out[t] = rec / (abs(pri) + 1e-6)
    return out


def s2(sc, other_series, task_of, tid, task):
    ts = sorted(t for t in sc if sc[t] == sc[t])
    xs, ys = [], []
    for o, osc in other_series.items():
        if o == tid or task_of.get(o) != task:
            continue
        for t in sorted(osc):
            if osc[t] == osc[t]:
                xs.append(t); ys.append(osc[t])
    if len(xs) < 40:
        if len(ts) < 12:
            return {}
        coef = np.polyfit(np.array(ts, dtype=float), np.array([sc[t] for t in ts]), 1)
    else:
        coef = np.polyfit(np.array(xs, dtype=float), np.array(ys), 2 if len(xs) > 60 else 1)
    return {t: float(sc[t] - np.polyval(coef, t)) for t in ts if sc[t] == sc[t]}


def build_combined(series, task_of, eps_frac, m_sd, m_ratio):
    """Equal-weight combination of standardised stationary statistics, per step."""
    raw = collections.defaultdict(dict)
    for tid, sc in series.items():
        for t, v in s1(sc, eps_frac, m_sd, m_ratio).items():
            raw["S1"][(tid, t)] = v
        for t, v in s3(sc, m_ratio).items():
            raw["S3"][(tid, t)] = v
        for t, v in s4(sc, m_sd).items():
            raw["S4"][(tid, t)] = v
        for t, v in s2(sc, series, task_of, tid, task_of.get(tid)).items():
            raw["S2"][(tid, t)] = v
    Z = {}
    for k, d in raw.items():
        vals = np.array([v for v in d.values() if v == v])
        if vals.size < 50:
            continue
        mu, sd = float(np.median(vals)), float(np.std(vals)) + 1e-9
        Z[k] = {key: (v - mu) / sd for key, v in d.items() if v == v}
    comb = {}
    keys = set().union(*[set(z) for z in Z.values()]) if Z else set()
    for key in keys:
        zs = [Z[k][key] for k in Z if key in Z[k]]
        if len(zs) >= 2:
            comb[key] = float(np.mean(zs))
    return comb


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
    print(f"episodes {len(pos)}; productive regions {len(neg)}; "
          f"productive windows {len(prod_windows)}")

    results = {}
    grid = [(0.02, 5, 5), (0.05, 5, 5), (0.05, 10, 5), (0.10, 5, 10), (0.05, 3, 3)]
    for mon in ("C3_evid_sem", "B4_semantic", "B5_novelty"):
        _, series = load(mon)
        runs = sorted(series)
        print(f"\n=== {mon} ===")
        for eps, m_sd, m_ratio in grid:
            comb = build_combined(series, task_of, eps, m_sd, m_ratio)
            if not comb:
                continue
            # leave-one-run-out threshold selection: pick thr on other runs, apply to held run
            all_scores = np.array(list(comb.values()))
            det_total = 0
            fa_win = 0
            for hold in runs:
                others = {k: v for k, v in comb.items() if k[0] != hold}
                if len(others) < 100:
                    continue
                ov = np.array(list(others.values()))
                # choose threshold on others to sit at the 15% window-FA budget
                thr = float(np.quantile(ov, 0.85))
                for g in pos:
                    if g["traj"] != hold:
                        continue
                    if any(comb.get((hold, t), -1) > thr for t in g["windows"]):
                        det_total += 1
                fa_win += sum(1 for k in prod_windows
                              if k[0] == hold and comb.get(k, -1) > thr)
            det = det_total / len(pos)
            fa = fa_win / max(1, len(prod_windows))
            ok = det > 0.50 and fa < 0.20
            print(f"  eps={eps:.2f} m_sd={m_sd} m_ratio={m_ratio}: "
                  f"detection {det:.2f}  FA {fa:.3f}  {'*** TARGET MET ***' if ok else ''}")
            results[f"{mon}|eps{eps}_sd{m_sd}_r{m_ratio}"] = {
                "det": det, "fa": fa, "target_met": bool(ok)}

    json.dump(results, open(os.path.join(OUT, "stationary_target_verified.json"), "w",
                            encoding="utf-8"), indent=2)
    met = [k for k, v in results.items() if v["target_met"]]
    print(f"\nconfigurations meeting the target with held-out thresholds: {len(met)}")
    for k in met:
        print("  ", k, results[k])
    print(f"wrote {OUT}/stationary_target_verified.json")


if __name__ == "__main__":
    main()
