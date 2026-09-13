"""Does multi-scale context beat any single timescale?

Motivation from the record, not from hope:
  * window-size sensitivity in the first study was strongly non-monotone. The semantic family
    scored 0.565 at w=6, 0.742 at w=10, 0.759 at w=20, 0.615 at w=30. A signal that peaks at an
    interior window length and collapses on both sides is a signal whose *timescale matters*.
  * stagnation episodes in the labels have varied durations: `extract-elf` runs 21 windows of
    post-completion churn, `feal-linear` polls for 13, `pvBcxmV` is blocked for 5. One fixed
    window cannot be the right lens for all three.
  * the pooled within-run result is bimodal (median 0.767, some runs 0.00). A single scale may be
    right for some runs and wrong for others.

So test the obvious consequence: concatenate representations at two timescales (w=10 and w=20,
the two the frozen feature table stores) and ask whether a model over both beats the better single
scale, under the identical task-disjoint folds and the identical windows used everywhere else.

This is a controlled comparison: same windows, same folds, same feature definitions; the only
change is how many timescales are visible.

Usage: python scripts/test_multiscale.py
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
GOLD = "data/annotations/tb2/adjudicated.csv"
OUT = "results/final/v2"
os.makedirs(OUT, exist_ok=True)
SCALES = (10, 20)


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
    tab = pq.read_table(FEATS).to_pylist()
    cols = [c for c in tab[0] if isinstance(tab[0][c], (int, float)) and not c.startswith("_")]
    print(f"feature columns: {len(cols)}")
    by_key = {}
    for r in tab:
        by_key[(r["traj_id"], r["w"], r["t"])] = r
    print(f"window rows: {len(by_key)}")

    gold = [r for r in csv.DictReader(open(GOLD, encoding="utf-8")) if r["binary"] != ""]
    print(f"gold windows: {len(gold)}")

    rows = []
    for g in gold:
        tid, t = g["traj_id"], int(g["t"])
        vecs = {}
        ok = True
        for w in SCALES:
            r = by_key.get((tid, w, t))
            if r is None:
                ok = False
                break
            vecs[w] = np.array([float(r.get(c, np.nan)) for c in cols], dtype=float)
        if not ok:
            continue
        # require at least one finite value per block
        if not all(np.isfinite(v).any() for v in vecs.values()):
            continue
        rows.append({"traj": tid, "t": t, "task": g["task"], "y": int(g["binary"]),
                     "vecs": vecs})
    print(f"windows with both scales available: {len(rows)}")
    if len(rows) < 200:
        print("too few windows to evaluate")
        return

    y = np.array([r["y"] for r in rows])
    tasks = sorted({r["task"] for r in rows})
    rng = np.random.default_rng(11)
    folds = np.array_split(rng.permutation(len(tasks)), 5)
    task_of = [r["task"] for r in rows]

    def build(scale_list):
        blocks = [np.vstack([r["vecs"][w] for r in rows]) for w in scale_list]
        X = np.hstack(blocks)
        # median-fill then standardise on the training fold inside the loop
        return X

    def fit_eval(scale_list, C=0.5):
        from sklearn.linear_model import LogisticRegression
        X = build(scale_list)
        pred = np.full(len(y), np.nan)
        for f in folds:
            test = {tasks[i] for i in f}
            tr = np.array([t not in test for t in task_of])
            te = ~tr
            mu = np.nanmedian(X[tr], axis=0)
            Xf = np.where(np.isfinite(X), X, mu)
            sd = np.nanstd(Xf[tr], axis=0)
            sd[sd < 1e-9] = 1.0
            Xs = (Xf - mu) / sd
            m = LogisticRegression(C=C, max_iter=2000, class_weight="balanced")
            m.fit(Xs[tr], y[tr])
            pred[te] = m.predict_proba(Xs[te])[:, 1]
        return roc_auc(y, pred), pred

    print("\n=== task-disjoint ROC-AUC, identical windows and folds ===")
    res = {}
    for scales in ((10,), (20,), (10, 20)):
        a, _ = fit_eval(list(scales))
        name = "w=" + "+".join(str(s) for s in scales)
        res[name] = a
        print(f"  {name:12} {a:.3f}")

    # v1 reference points on the same windows
    stored = {}
    for r in pq.read_table(SCORES, columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist():
        stored[(r["monitor"], r["traj_id"], r["w"], r["t"])] = r["score"]
    for mon in ("B4_semantic", "L_sem", "C1_evidence", "B2_exact_rep3", "C4_all_hand"):
        for w in (10, 20):
            s = np.array([stored.get((mon, r["traj"], w, r["t"]), np.nan) for r in rows])
            a = roc_auc(y, s)
            if np.isfinite(a):
                res[f"v1_{mon}_w{w}"] = a
    print("\n  v1 references on the same windows:")
    for k, v in res.items():
        if k.startswith("v1_"):
            print(f"    {k:22} {v:.3f}")

    best_single = max(res["w=10"], res["w=20"])
    multi = res["w=10+w=20"]
    print(f"\nbest single scale {best_single:.3f}  ->  multi-scale {multi:.3f}  "
          f"({multi - best_single:+.3f})")
    best_v1 = max((v, k) for k, v in res.items() if k.startswith("v1_"))
    print(f"best v1 monitor  {best_v1[0]:.3f} ({best_v1[1]})  ->  "
          f"multi-scale {multi:.3f} ({multi - best_v1[0]:+.3f})")
    print(f"best v1 single-scale semantic {max(res.get('v1_B4_semantic_w10', 0), res.get('v1_B4_semantic_w20', 0)):.3f}")

    json.dump({"auc": res, "n_windows": len(rows), "scales": list(SCALES),
               "positive_rate": float(y.mean())},
              open(os.path.join(OUT, "multiscale_test.json"), "w", encoding="utf-8"), indent=2)
    print(f"\nwrote {OUT}/multiscale_test.json")


if __name__ == "__main__":
    main()
