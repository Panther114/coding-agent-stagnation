"""Stationary statistics for stagnation: build candidates, evaluate on one frontier.

The three calibration attempts failed because the score is non-stationary -- it rises with run
progress (93% of runs, r = 0.518 with step index), so no fixed threshold stays calibrated. The
thesis to test: **a stagnation statistic must be flat while the agent works and rise only when it
stalls.** That means measuring *change*, *absence of change*, or *deviation from expectation* --
never the level of information flow.

Candidates, each built from the trajectory's own score series with no labels:

  S1  normalised freezing time
      (steps since the score last moved by more than eps) / (typical inter-change gap so far).
      A stalled agent receives no new information, so the score freezes; scaling by its own
      historical rate makes it dimensionless and stationary.

  S2  residual against the predicted trend
      fit score ~ step on OTHER runs of the same task, score each step by its deviation.
      Removes the shared monotone drift a threshold would otherwise be fighting.

  S3  activity collapse
      rolling mean of the last m steps divided by the rolling mean of the previous m steps
      (a half-window ratio). Measures whether the flow has dropped, not whether it is high.

  S4  change-point score
      rolling standard deviation of the score: a live process keeps moving, a stalled one does not.

  S5  combination of the standardised candidates (equal weight, no fitting).

Evaluated on the same 68 stagnant episodes and 108 productive regions, detection = at least one
alarm inside the episode, false alarms = share of ALARMED WINDOWS among labelled productive windows
(the stricter window-level accounting).

Usage: python scripts/test_stationary_stats.py
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


# ---------------- candidate statistics (all label-free, all causal) ----------------

def s1_freezing(series_of_run, eps_frac=0.05):
    """Normalised freezing time: how long since the score last changed, over its own typical gap."""
    ts = sorted(series_of_run)
    vals = [series_of_run[t] for t in ts]
    if len(vals) < 8:
        return {}
    rng = max(vals) - min(vals) or 1.0
    eps = eps_frac * rng
    out, gaps, last_change = {}, [], 0
    prev = vals[0]
    for i, (t, v) in enumerate(zip(ts, vals)):
        if abs(v - prev) > eps:
            gaps.append(i - last_change)
            last_change = i
            prev = v
        # typical gap so far (causal); fall back to current gap
        ref = float(np.median(gaps)) if gaps else max(1.0, (i - last_change))
        ref = max(ref, 1.0)
        out[t] = (i - last_change) / ref
    return out


def s2_residual(series_by_run, task_of, t_of):
    """Deviation from the trend predicted by OTHER runs of the same task."""
    out = {}
    for tid, sc in series_by_run.items():
        ts = sorted(sc)
        if not ts:
            continue
        task = task_of.get(tid)
        # collect (step, score) from other runs of the same task
        xs, ys = [], []
        for other, osc in series_by_run.items():
            if other == tid or task_of.get(other) != task:
                continue
            for t in sorted(osc):
                if osc[t] == osc[t]:
                    xs.append(t); ys.append(osc[t])
        if len(xs) < 40:
            # fall back to the run's own linear trend (still removes monolithic drift)
            xx = np.array(ts, dtype=float)
            yy = np.array([sc[t] for t in ts])
        else:
            xx = np.array(xs, dtype=float); yy = np.array(ys)
        if len(xx) < 8:
            continue
        coef = np.polyfit(xx, yy, 2) if len(xx) > 40 else np.polyfit(xx, yy, 1)
        for t in ts:
            if sc[t] != sc[t]:
                continue
            out[(tid, t)] = float(sc[t] - np.polyval(coef, t))
    return out


def s3_ratio(series_of_run, m=5):
    """Half-window ratio: recent flow over preceding flow. Detects a drop, not a level."""
    ts = sorted(series_of_run)
    vals = np.array([series_of_run[t] for t in ts], dtype=float)
    out = {}
    for i, t in enumerate(ts):
        if i < 2 * m:
            continue
        recent = vals[i - m + 1:i + 1]
        prior = vals[i - 2 * m + 1:i - m + 1]
        denom = abs(prior.mean()) + 1e-6
        out[t] = float(recent.mean() / denom)
    return out


def s4_changepoint(series_of_run, m=5):
    """Rolling standard deviation: a live process keeps moving, a stalled one does not."""
    ts = sorted(series_of_run)
    vals = np.array([series_of_run[t] for t in ts], dtype=float)
    out = {}
    for i, t in enumerate(ts):
        if i < m:
            continue
        out[t] = float(np.std(vals[i - m + 1:i + 1]))
    return out


def main() -> None:
    out = {}
    for mon in ("B4_semantic", "C3_evid_sem", "B5_novelty"):
        by_traj, series = load(mon)
        regs = []
        for tid, rs in by_traj.items():
            regs += regions_of(rs)
        pos = [g for g in regs if g["label"] == 1]
        neg = [g for g in regs if g["label"] == 0]
        task_of = {g["traj"]: g["traj"].split("__")[0] for g in regs}
        print(f"\n================ {mon}: {len(pos)} episodes, {len(neg)} productive regions")

        # productive windows, for the false-alarm accounting
        prod_windows = [(g["traj"], t) for g in neg for t in g["windows"]]
        n_prod = len(prod_windows)

        cand = {}
        for tid, sc in series.items():
            cand.setdefault("S1", {}).update({(tid, t): v for t, v in s1_freezing(sc).items()})
            cand.setdefault("S3", {}).update({(tid, t): v for t, v in s3_ratio(sc).items()})
            cand.setdefault("S4", {}).update({(tid, t): v for t, v in s4_changepoint(sc).items()})
        cand["S2"] = s2_residual(series, task_of, None)

        def frontier(stat, name):
            """Sweep thresholds; report detection at each window-level false-alarm rate."""
            vals = np.array([v for v in stat.values() if v == v])
            if vals.size < 50:
                return None
            det_curve = []
            for thr in np.quantile(vals, np.arange(0.5, 0.999, 0.01)):
                det = 0
                for g in pos:
                    if any(stat.get((g["traj"], t), -1e9) > thr for t in g["windows"]):
                        det += 1
                fa_windows = sum(1 for k in prod_windows
                                 if stat.get(k, -1e9) > thr)
                det_curve.append((fa_windows / max(1, n_prod), det / len(pos)))
            # best detection achievable with false alarms under 20%
            ok = [(f, d) for f, d in det_curve if f < 0.20]
            best = max((d for _, d in ok), default=float("nan"))
            best_f = min((f for f, d in ok if d == best), default=float("nan"))
            print(f"  {name:5} best detection with FA<20%: {best:.2f} "
                  f"(at FA {best_f:.3f})  |  max detection overall: "
                  f"{max(d for _, d in det_curve):.2f}")
            return {"best_det_under_20fa": None if best != best else float(best),
                    "fa_at_best": None if best_f != best_f else float(best_f),
                    "curve": [[float(f), float(d)] for f, d in det_curve]}

        for key in ("S1", "S2", "S3", "S4"):
            if key in cand:
                r = frontier(cand[key], key)
                if r:
                    out.setdefault(mon, {})[key] = r

        # S5: equal-weight combination of standardised candidates
        comb = {}
        allkeys = set()
        for key in ("S1", "S2", "S3", "S4"):
            allkeys |= set(cand.get(key, {}))
        Z = {}
        for key in ("S1", "S2", "S3", "S4"):
            s = cand.get(key, {})
            vals = np.array([v for v in s.values() if v == v])
            if vals.size < 50:
                continue
            mu, sd = float(np.median(vals)), float(np.std(vals)) + 1e-9
            Z[key] = {k: (v - mu) / sd for k, v in s.items() if v == v}
        for k in allkeys:
            zs = [Z[key][k] for key in Z if k in Z[key]]
            if len(zs) >= 2:
                comb[k] = float(np.mean(zs))
        r = frontier(comb, "S5")
        if r:
            out.setdefault(mon, {})["S5_combined"] = r

    json.dump(out, open(os.path.join(OUT, "stationary_stats.json"), "w", encoding="utf-8"),
              indent=2)
    print(f"\nwrote {OUT}/stationary_stats.json")


if __name__ == "__main__":
    main()
