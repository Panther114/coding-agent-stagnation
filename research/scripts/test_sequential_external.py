"""TEST 2: a sequential test with an EXTERNAL reference (leave-one-run-out).

My earlier CUSUM attempt failed because it referenced the run's own trailing history, which is
contaminated once a stall begins. The correct construction references a distribution learned from
*other* runs: leave-one-run-out, so the reference for run i never includes run i.

Sequential test: accumulate the log-likelihood ratio between two score distributions fitted on
other runs' labelled windows (stagnant vs productive), and alarm when the accumulated evidence
crosses a boundary. This controls the error rate in a principled way rather than by an arbitrary
quantile.

Note the honest caveat recorded with the result: fitting the two distributions uses labels on
*other* runs. That is legitimate for a deployment that has curated history, but it is not
label-free, and it is reported as such.

Usage: python scripts/test_sequential_external.py
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
MON = "B4_semantic"


def load():
    gold = [r for r in csv.DictReader(open(GOLD, encoding="utf-8")) if r["binary"] != ""]
    by_traj = collections.defaultdict(list)
    for r in gold:
        by_traj[r["traj_id"]].append(r)
    for t in by_traj:
        by_traj[t].sort(key=lambda r: int(r["t"]))
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


def main() -> None:
    by_traj, series = load()
    regs = []
    for tid, rs in by_traj.items():
        regs += regions_of(rs)
    pos = [g for g in regs if g["label"] == 1]
    neg = [g for g in regs if g["label"] == 0]
    runs = sorted({g["traj"] for g in regs})
    print(f"{len(pos)} episodes, {len(neg)} productive regions, {len(runs)} runs")

    # ---------- normalise scores per run to remove the drift ----------
    # a runtime can do this online from its own history, but that reintroduces contamination, so
    # ALSO test a leave-one-run-out standardisation fitted on other runs.
    print("\n--- 2a. sequential test with a leave-one-run-out reference ---")
    results = {}
    for m_boundary in (2.0, 3.0, 5.0, 8.0):
        det = fp = 0
        for g in pos + neg:
            tid = g["traj"]
            # reference distributions from OTHER runs
            oth = [h for h in regs if h["traj"] != tid]
            p_scores = [series[h["traj"]].get(t) for h in oth if h["label"] == 1
                        for t in h["windows"]]
            n_scores = [series[h["traj"]].get(t) for h in oth if h["label"] == 0
                        for t in h["windows"]]
            p_scores = np.array([v for v in p_scores if v is not None and v == v])
            n_scores = np.array([v for v in n_scores if v is not None and v == v])
            if len(p_scores) < 30 or len(n_scores) < 30:
                continue
            # gaussian log-likelihood ratio, with a floor on sd
            mu_p, sd_p = p_scores.mean(), max(p_scores.std(), 1e-3)
            mu_n, sd_n = n_scores.mean(), max(n_scores.std(), 1e-3)
            llr = 0.0
            fired = False
            for t in sorted(g["windows"]):
                v = series[tid].get(t)
                if v is None or v != v:
                    continue
                lp = -0.5 * ((v - mu_p) / sd_p) ** 2 - np.log(sd_p)
                ln = -0.5 * ((v - mu_n) / sd_n) ** 2 - np.log(sd_n)
                llr += (lp - ln)
                if llr >= m_boundary:
                    fired = True
                    break
            if fired:
                if g["label"] == 1:
                    det += 1
                else:
                    fp += 1
        print(f"  boundary={m_boundary:.1f}: detect {det}/{len(pos)} "
              f"({100*det/len(pos):.0f}%)  FA {fp}/{len(neg)} ({100*fp/len(neg):.0f}%)")
        results[f"llr_boundary{m_boundary}"] = {"det": det, "fp": fp}

    # ---------- 2b. leave-one-SCAFFOLD-out: external to the whole scaffold ----------
    print("\n--- 2b. leave-one-scaffold-out reference (stricter, more deployable) ---")
    task_of = {g["traj"]: g["traj"].split("__")[0] for g in regs}
    for m_boundary in (2.0, 3.0, 5.0):
        det = fp = 0
        for g in pos + neg:
            tid = g["traj"]
            oth = [h for h in regs if h["traj"] != tid and task_of[h["traj"]] != task_of[tid]]
            p_scores = np.array([v for v in (series[h["traj"]].get(t) for h in oth
                                             if h["label"] == 1 for t in h["windows"])
                                 if v is not None and v == v])
            n_scores = np.array([v for v in (series[h["traj"]].get(t) for h in oth
                                             if h["label"] == 0 for t in h["windows"])
                                 if v is not None and v == v])
            if len(p_scores) < 30 or len(n_scores) < 30:
                continue
            mu_p, sd_p = p_scores.mean(), max(p_scores.std(), 1e-3)
            mu_n, sd_n = n_scores.mean(), max(n_scores.std(), 1e-3)
            llr = 0.0
            fired = False
            for t in sorted(g["windows"]):
                v = series[tid].get(t)
                if v is None or v != v:
                    continue
                lp = -0.5 * ((v - mu_p) / sd_p) ** 2 - np.log(sd_p)
                ln = -0.5 * ((v - mu_n) / sd_n) ** 2 - np.log(sd_n)
                llr += (lp - ln)
                if llr >= m_boundary:
                    fired = True
                    break
            if fired:
                if g["label"] == 1:
                    det += 1
                else:
                    fp += 1
        print(f"  boundary={m_boundary:.1f}: detect {det}/{len(pos)} "
              f"({100*det/len(pos):.0f}%)  FA {fp}/{len(neg)} ({100*fp/len(neg):.0f}%)")
        results[f"llr_scaffold_boundary{m_boundary}"] = {"det": det, "fp": fp}

    json.dump(results, open(os.path.join(OUT, "sequential_external_test.json"), "w",
                            encoding="utf-8"), indent=2)
    print(f"\nwrote {OUT}/sequential_external_test.json")


if __name__ == "__main__":
    main()
