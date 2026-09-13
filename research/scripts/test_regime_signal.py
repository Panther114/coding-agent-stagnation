"""The decisive test: is the regime signal real, and is it the strongest result in this study?

The largest effect found anywhere in this study is the mid-region separation: the semantic monitor
holds the run's own stagnant episodes well above its productive regions, and does so in every third
of a run, while a position proxy collapses.  That is a claim about *regimes* rather than windows,
which is the right unit given the labels form contiguous episodes.

Establish it properly or drop it:
  1. paired, trajectory-clustered bootstrap of (mid-region score) - (productive score);
  2. the same for a position-matched comparison, so run position cannot explain it;
  3. how many of the 68 episodes are individually separated, and by how much;
  4. whether the effect survives removing the 33% of runs that contain no stagnant episode.

If the interval excludes zero on the matched comparison, this is the study's positive result.

Usage: python scripts/test_regime_signal.py
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


def main() -> None:
    out = {}
    for mon in ("B4_semantic", "B5_novelty", "C3_evid_sem", "B1_step30"):
        by_traj, series = load(mon)
        regs = []
        for tid, rs in by_traj.items():
            regs += regions_of(rs)
        pos = [g for g in regs if g["label"] == 1]
        neg = [g for g in regs if g["label"] == 0]

        # per-episode: mean score of the episode's interior vs the same run's productive mean
        pairs = []
        for g in pos:
            rv = [series[g["traj"]].get(t) for t in g["windows"]]
            rv = [v for v in rv if v is not None and v == v]
            nv = [series[h["traj"]].get(t) for h in neg if h["traj"] == g["traj"]
                  for t in h["windows"]]
            nv = [v for v in nv if v is not None and v == v]
            if rv and nv:
                pairs.append((g["traj"], float(np.mean(rv)), float(np.mean(nv))))
        if not pairs:
            continue
        diffs = np.array([a - b for _, a, b in pairs])
        groups = np.array([t for t, _, _ in pairs])

        rng = np.random.default_rng(3)
        uniq = np.unique(groups)
        idx_by = {g: np.where(groups == g)[0] for g in uniq}
        boot = []
        for _ in range(4000):
            pick = rng.choice(uniq, size=len(uniq), replace=True)
            idx = np.concatenate([idx_by[g] for g in pick])
            boot.append(float(np.mean(diffs[idx])))
        boot = np.array(boot)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        p = 2 * min((boot <= 0).mean(), (boot >= 0).mean())

        sep = int((diffs > 0).sum())
        line = (f"  {mon:14} episodes separated {sep:>2}/{len(diffs)} "
                f"({100*sep/len(diffs):>3.0f}%)  mean diff {np.mean(diffs):+.3f} "
                f"[{lo:+.3f}, {hi:+.3f}]  p={p:.4f}")
        print(line)
        out[mon] = {"episodes": len(diffs), "separated": sep, "mean_diff": float(np.mean(diffs)),
                    "ci": [float(lo), float(hi)], "p": float(p)}

    print("\n=== position-matched version (each episode vs its run's productive windows in the")
    print("    same third of the run), so run position cannot explain the separation ===")
    for mon in ("B4_semantic", "B1_step30"):
        by_traj, series = load(mon)
        regs = []
        for tid, rs in by_traj.items():
            regs += regions_of(rs)
        pos = [g for g in regs if g["label"] == 1]
        neg = [g for g in regs if g["label"] == 0]
        pairs = []
        for g in pos:
            n = max(int(r["n_steps"]) for r in by_traj[g["traj"]])
            pr = g["start"] / max(1, n)
            band = 0 if pr < 0.33 else (1 if pr < 0.66 else 2)
            rv = [series[g["traj"]].get(t) for t in g["windows"]]
            rv = [v for v in rv if v is not None and v == v]
            nv = []
            for h in neg:
                if h["traj"] != g["traj"]:
                    continue
                hr = h["start"] / max(1, n)
                hb = 0 if hr < 0.33 else (1 if hr < 0.66 else 2)
                if hb != band:
                    continue
                nv += [series[h["traj"]].get(t) for t in h["windows"]]
            nv = [v for v in nv if v is not None and v == v]
            if rv and nv:
                pairs.append((g["traj"], float(np.mean(rv)), float(np.mean(nv))))
        if not pairs:
            print(f"  {mon:14} no position-matched pairs")
            continue
        diffs = np.array([a - b for _, a, b in pairs])
        groups = np.array([t for t, _, _ in pairs])
        rng = np.random.default_rng(3)
        uniq = np.unique(groups)
        idx_by = {g: np.where(groups == g)[0] for g in uniq}
        boot = []
        for _ in range(4000):
            pick = rng.choice(uniq, size=len(uniq), replace=True)
            boot.append(float(np.mean(diffs[np.concatenate([idx_by[g] for g in pick])])))
        boot = np.array(boot)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        p = 2 * min((boot <= 0).mean(), (boot >= 0).mean())
        sep = int((diffs > 0).sum())
        print(f"  {mon:14} episodes {sep:>2}/{len(diffs)} ({100*sep/len(diffs):>3.0f}%)  "
              f"mean diff {np.mean(diffs):+.3f} [{lo:+.3f}, {hi:+.3f}]  p={p:.4f}")
        out[f"{mon}_position_matched"] = {"episodes": len(diffs), "separated": sep,
                                         "mean_diff": float(np.mean(diffs)),
                                         "ci": [float(lo), float(hi)], "p": float(p)}

    json.dump(out, open(os.path.join(OUT, "regime_signal.json"), "w", encoding="utf-8"),
              indent=2)
    print(f"\nwrote {OUT}/regime_signal.json")


if __name__ == "__main__":
    main()
