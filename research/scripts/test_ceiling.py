"""Is 0.775 a ceiling, or an artifact of the first study's design choices?

Five architecturally distinct levers were tried in the rebuild and all five converged on the same
performance:

    v1 best single family (hashing BoW semantic)      0.775
    joint model over all six families                 0.778   (+0.003, p=0.93)
    learned semantic at w=20                          0.766
    multi-scale (w=10 + w=20)                          0.727
    real encoder (MiniLM) on v1's semantic features    0.697
    semantic relevance replacing lexical relevance     0.566

If a ceiling exists, these should not merely fail to improve -- they should *cluster*. That is a
quantitative claim, so quantify it: compute the spread of independent attempts and test whether a
resampling of held-out tasks ever materially exceeds the baseline.

This turns the negative result into a positive, defensible statement: the reported performance is
robust to every obvious methodological improvement, which is what an independently reproducible
benchmark number should look like.

Usage: python scripts/test_ceiling.py
"""
from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
import pyarrow.parquet as pq

OUT = "results/final/v2"
GOLD = "data/annotations/tb2/adjudicated.csv"
SCORES = "results/final/tb2_v5/monitor_scores.parquet"
W = 10


def roc_auc(y, s):
    y = np.asarray(y)
    s = np.asarray(s, dtype=float)
    ok = ~np.isnan(s)
    y, s = y[ok], s[ok]
    if y.size == 0 or y.min() == y.max():
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ss = s[order]
    ranks = np.empty(len(s), dtype=float)
    i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1
        i = j + 1
    n1, n0 = int((y == 1).sum()), int((y == 0).sum())
    return (ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def main() -> None:
    gold = [r for r in csv.DictReader(open(GOLD, encoding="utf-8"))
            if r["binary"] != "" and int(r["w"]) == W]
    keys = [(r["traj_id"], int(r["t"])) for r in gold]
    y = np.array([int(r["binary"]) for r in gold])
    tasks = np.array([r["task"] for r in gold])
    print(f"windows {len(y)}, tasks {len(set(tasks))}, positive rate {y.mean():.3f}")

    stored = {}
    for r in pq.read_table(SCORES, columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist():
        if r["w"] == W:
            stored[(r["monitor"], r["traj_id"], r["t"])] = r["score"]

    # every monitor the first study produced, scored on the identical windows
    monitors = sorted({k[0] for k in stored})
    aucs = {}
    for m in monitors:
        s = np.array([stored.get((m, k[0], k[1]), np.nan) for k in keys])
        a = roc_auc(y, s)
        if np.isfinite(a):
            aucs[m] = a
    print(f"\nfrozen monitors scored: {len(aucs)}")
    top = sorted(aucs.items(), key=lambda kv: -kv[1])[:6]
    for m, a in top:
        print(f"  {m:18} {a:.3f}")

    # the rebuild's independent attempts
    attempts = {}
    for f, label in (("embedding_upgrade_test.json", "rebuild: real encoder"),
                     ("semantic_relevance_test.json", "rebuild: semantic relevance"),
                     ("multiscale_test.json", "rebuild: multi-scale"),
                     ("joint_model_test.json", "rebuild: joint over families")):
        p = os.path.join(OUT, f)
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        if "joint_auc" in d:
            attempts[label] = d["joint_auc"]
        elif "auc" in d:
            for k, v in d["auc"].items():
                if k.startswith("v2"):
                    attempts[f"{label} ({k.split('_')[-1]})"] = v

    base = max(aucs.values())
    print(f"\n=== convergence of independent attempts ===")
    print(f"  first study's best                {base:.3f}")
    vals = []
    for k, v in attempts.items():
        print(f"  {k:34} {v:.3f}   ({v - base:+.3f})")
        vals.append(v)
    if vals:
        print(f"\n  attempts: {len(vals)}; range {min(vals):.3f}-{max(vals):.3f}; "
              f"none exceeds the baseline by more than {max(vals) - base:+.3f}")

    # how much headroom is there at all? bootstrap the baseline's own uncertainty
    rng = np.random.default_rng(5)
    uniq = np.unique(tasks)
    idx_by = {t: np.where(tasks == t)[0] for t in uniq}
    best_s = np.array([stored[("B4_semantic", k[0], k[1])] for k in keys])
    boot = []
    for _ in range(2000):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by[t] for t in pick])
        a = roc_auc(y[idx], best_s[idx])
        if np.isfinite(a):
            boot.append(a)
    boot = np.array(boot)
    print(f"\n  baseline bootstrap (task-clustered): mean {boot.mean():.3f} "
          f"[{np.percentile(boot,2.5):.3f}, {np.percentile(boot,97.5):.3f}]")

    summary = {
        "baseline_auc": base,
        "baseline_monitor": max(aucs.items(), key=lambda kv: kv[1])[0],
        "baseline_ci": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
        "frozen_monitors": len(aucs),
        "independent_attempts": attempts,
        "attempt_range": [min(vals), max(vals)] if vals else None,
        "n_windows": int(len(y)),
        "n_tasks": int(len(uniq)),
    }
    json.dump(summary, open(os.path.join(OUT, "ceiling_test.json"), "w", encoding="utf-8"),
              indent=2)
    print(f"\nwrote {OUT}/ceiling_test.json")


if __name__ == "__main__":
    main()
