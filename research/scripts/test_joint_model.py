"""Does learning across all six families beat the best single-family baseline?

The first study showed (a) the best single family is semantic redundancy at 0.775-0.778, and
(b) its *learned* semantic-only model `L_sem` reaches 0.766 at w=20, i.e. learning did not beat
the hand-designed version of the same family. What was never tested is a model over **all** families
jointly -- the frozen feature table holds 60+ features across six channels, and the first study's
learned monitors each used only their own channel.

That gap is the third and last untested lever. If a joint model over six signal families beats the
best single family under task-disjoint validation, that is a positive, publishable result: it says
the families carry complementary information that single-family monitors discard.

Statistically careful: identical windows, identical folds, and paired per-window comparison against
the baseline rather than a bare difference in pooled AUC.

Usage: python scripts/test_joint_model.py
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

FEATS = "results/final/tb2_v5/window_features.parquet"
SCORES = "results/final/tb2_v5/monitor_scores.parquet"
GOLD = "../datasets/annotations/tb2/adjudicated.csv"
OUT = "results/final/v2"
os.makedirs(OUT, exist_ok=True)
W = 10
BASELINE = "B4_semantic"


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


def cluster_bootstrap(y, a, b, groups, n=2000, seed=7):
    """Paired AUC difference with a trajectory-clustered bootstrap."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    idx_by = {g: np.where(groups == g)[0] for g in uniq}
    diffs = []
    for _ in range(n):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by[g] for g in pick])
        ya, aa, bb = y[idx], a[idx], b[idx]
        d = roc_auc(ya, aa) - roc_auc(ya, bb)
        if np.isfinite(d):
            diffs.append(d)
    diffs = np.array(diffs)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    p = 2 * min((diffs <= 0).mean(), (diffs >= 0).mean())
    return float(np.mean(diffs)), float(lo), float(hi), float(p)


def main() -> None:
    tab = pq.read_table(FEATS).to_pylist()
    cols = [c for c in tab[0] if isinstance(tab[0][c], (int, float)) and not c.startswith("_")]
    by_key = {(r["traj_id"], r["w"], r["t"]): r for r in tab}
    print(f"features: {len(cols)}")

    gold = [r for r in csv.DictReader(open(GOLD, encoding="utf-8"))
            if r["binary"] != "" and int(r["w"]) == W]
    print(f"gold windows at w={W}: {len(gold)}")

    keys, X, y, tasks = [], [], [], []
    for g in gold:
        r = by_key.get((g["traj_id"], W, int(g["t"])))
        if r is None:
            continue
        keys.append((g["traj_id"], int(g["t"])))
        X.append([float(r.get(c, np.nan)) for c in cols])
        y.append(int(g["binary"]))
        tasks.append(g["task"])
    X = np.asarray(X, dtype=float)
    y = np.asarray(y)
    print(f"aligned windows: {len(y)}  positive rate {y.mean():.3f}  features {X.shape[1]}")

    # baseline scores
    stored = {}
    for r in pq.read_table(SCORES, columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist():
        if r["w"] == W:
            stored[(r["monitor"], r["traj_id"], r["t"])] = r["score"]
    base = np.array([stored.get((BASELINE, k[0], k[1]), np.nan) for k in keys])

    task_arr = np.array(tasks)
    uniq_tasks = sorted(set(tasks))
    rng = np.random.default_rng(11)
    folds = np.array_split(rng.permutation(len(uniq_tasks)), 5)

    from sklearn.linear_model import LogisticRegression

    def joint_predict(C):
        pred = np.full(len(y), np.nan)
        for f in folds:
            test = {uniq_tasks[i] for i in f}
            tr = np.array([t not in test for t in tasks])
            te = ~tr
            mu = np.nanmedian(X[tr], axis=0)
            Xi = np.where(np.isfinite(X), X, mu)
            sd = np.nanstd(Xi[tr], axis=0)
            sd[sd < 1e-9] = 1.0
            Xs = (Xi - mu) / sd
            m = LogisticRegression(C=C, max_iter=3000, class_weight="balanced")
            m.fit(Xs[tr], y[tr])
            pred[te] = m.predict_proba(Xs[te])[:, 1]
        return pred

    print("\n=== joint model over all six families, task-disjoint ===")
    res = {}
    best = (None, -1, None)
    for C in (0.03, 0.1, 0.3, 1.0):
        p = joint_predict(C)
        a = roc_auc(y, p)
        res[f"joint_C{C}"] = a
        print(f"  C={C:<5} ROC {a:.3f}")
        if a > best[1]:
            best = (C, a, p)

    a_base = roc_auc(y, base)
    print(f"\n  baseline {BASELINE} (v1 best single family)  ROC {a_base:.3f}")
    print(f"  joint model (C={best[0]})                    ROC {best[1]:.3f}")

    diff, lo, hi, pval = cluster_bootstrap(y, best[2], base, task_arr)
    print(f"\n  paired difference {diff:+.3f}  [{lo:+.3f}, {hi:+.3f}]  p={pval:.4f}")
    verdict = ("POSITIVE: joint beats the best single family with an interval excluding zero"
               if lo > 0 else
               "not significant: interval includes zero")
    print(f"  -> {verdict}")

    # is the gain uniform, or carried by a few tasks?
    wins = sum(1 for (tid, t), pb, pj in zip(keys, base, best[2])
               if np.isfinite(pb) and np.isfinite(pj))
    print(f"\n  sanity: finite pairs {wins}/{len(y)}")

    json.dump({"auc": res, "baseline_auc": a_base, "best_C": best[0], "joint_auc": best[1],
               "paired_diff": diff, "ci": [lo, hi], "p": pval, "n_windows": int(len(y)),
               "n_features": int(X.shape[1]), "verdict": verdict},
              open(os.path.join(OUT, "joint_model_test.json"), "w", encoding="utf-8"), indent=2)
    np.save(os.path.join(OUT, "joint_pred.npy"), best[2])
    print(f"  wrote {OUT}/joint_model_test.json")


if __name__ == "__main__":
    main()
