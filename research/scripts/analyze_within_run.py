"""Per-run robustness of the within-trajectory signal, written as a frozen artifact.

The paper's central caution is that most accuracy is between-run.  A pooled within-run AUC
understates the signal if the per-run distribution is bimodal, so this computes the distribution
rather than one number: median, share above chance, an exact sign test, the per-monitor spread,
a paired comparison against the step-budget baseline, and the task/run variance decomposition.

Usage: python scripts/analyze_within_run.py --run results/final/tb2_v5
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.stdout.reconfigure(encoding="utf-8")

import pyarrow.parquet as pq


def auc(pos, neg):
    if not pos or not neg:
        return None
    n = 0.0
    for p in pos:
        for q in neg:
            n += 1.0 if p > q else (0.5 if p == q else 0.0)
    return n / (len(pos) * len(neg))


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="results/final/tb2_v5")
    ap.add_argument("--ann", default="../datasets/annotations/tb2")
    ap.add_argument("--w", type=int, default=10)
    args = ap.parse_args()

    gold = [a for a in csv.DictReader(open(os.path.join(args.ann, "adjudicated.csv"),
                                          encoding="utf-8")) if a["binary"] != ""]
    lab = {(a["traj_id"], int(a["w"]), int(a["t"])): int(a["binary"]) for a in gold}
    task_of = {a["traj_id"]: a["task"] for a in gold}

    tab = pq.read_table(os.path.join(args.run, "monitor_scores.parquet"),
                        columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist()
    per = collections.defaultdict(lambda: collections.defaultdict(lambda: ([], [])))
    for r in tab:
        y = lab.get((r["traj_id"], r["w"], r["t"]))
        if y is None:
            continue
        v = r["score"]
        if v != v:
            continue
        slot = per[r["monitor"]][r["traj_id"]]
        (slot[0] if y == 1 else slot[1]).append(v)

    out = {}
    for mon, perl in per.items():
        vals = {t: auc(p, n) for t, (p, n) in perl.items() if p and n}
        if len(vals) < 5:
            continue
        xs = sorted(vals.values())
        wins = sum(1 for x in xs if x > 0.5)
        losses = sum(1 for x in xs if x < 0.5)
        out[mon] = {
            "runs": len(xs), "median": st.median(xs), "min": xs[0], "max": xs[-1],
            "q1": xs[len(xs) // 4], "q3": xs[3 * len(xs) // 4],
            "share_above_chance": wins / len(xs), "share_ge_0_70": sum(1 for x in xs if x >= 0.70) / len(xs),
            "wins": wins, "losses": losses, "sign_p": sign_test(wins, losses),
        }

    # paired against the step-budget baseline
    base = "B1_step30"
    best = max(out, key=lambda m: out[m]["median"])
    bp = {t: auc(p, n) for t, (p, n) in per[base].items() if p and n} if base in per else {}
    mp = {t: auc(p, n) for t, (p, n) in per[best].items() if p and n}
    paired = [(mp[t], bp[t]) for t in mp if t in bp]
    vs = {"best": best, "n": len(paired),
          "wins": sum(1 for a, b in paired if a > b),
          "median_gain": st.median([a - b for a, b in paired]) if paired else None}

    # variance decomposition: how much of the between-run variation is between tasks
    by_task = collections.defaultdict(list)
    by_traj = collections.defaultdict(list)
    for a in gold:
        by_task[a["task"]].append(int(a["binary"]))
        by_traj[a["traj_id"]].append(int(a["binary"]))
    task_rate = {t: sum(v) / len(v) for t, v in by_task.items()}
    traj_rate = {t: sum(v) / len(v) for t, v in by_traj.items()}
    rates = list(task_rate.values())
    conc = tot = 0
    for i in range(len(rates)):
        for j in range(i + 1, len(rates)):
            if rates[i] == rates[j]:
                continue
            tot += 1
            conc += 1 if rates[i] > rates[j] else 0
    var = {"task_sd": st.pstdev(rates), "run_sd": st.pstdev(list(traj_rate.values())),
           "zero_tasks": sum(1 for r in rates if r == 0.0),
           "task_rate_auc": conc / max(1, tot)}

    path = os.path.join(args.run, "within_run_robustness.json")
    json.dump({"per_monitor": out, "vs_step_budget": vs, "variance": var}, open(path, "w",
              encoding="utf-8"), indent=2)
    print(f"wrote {path}")
    print(f"  best by median within-run AUC: {best} "
          f"(median {out[best]['median']:.2f}, {out[best]['wins']}/{out[best]['runs']} above chance, "
          f"p={out[best]['sign_p']:.4f})")
    print(f"  beats step budget in {vs['wins']}/{vs['n']} runs, median gain {vs['median_gain']:+.3f}")
    print(f"  variance: task sd {var['task_sd']:.3f}, run sd {var['run_sd']:.3f}, "
          f"task-rate AUC {var['task_rate_auc']:.3f}, zero tasks {var['zero_tasks']}")


if __name__ == "__main__":
    main()
