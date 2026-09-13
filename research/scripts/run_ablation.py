"""Leave-one-channel-out ablation, measured with the same protocol as the main run.

For each fold the model is trained on all features except one channel and evaluated on the
held-out tasks; the drop relative to the full model attributes usefulness to the channel.
This answers "if I delete this signal family, how much worse is the monitor?" --- the
component-level question that the monitor zoo in the main run only answers pairwise.

Usage: python scripts/run_ablation.py --run results/final/tb2 --corpus tb2 --out results/final/tb2/ablation.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from typing import Any, Dict, List, Sequence

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import numpy as np  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

import paths  # noqa: E402
from evaluation import window_metrics  # noqa: E402
from features import ALL_FEATURES, CHANNELS, FEATURE_CHANNEL  # noqa: E402

CHANNEL_FEATURES: Dict[str, List[str]] = {
    ch: [f for f in ALL_FEATURES if FEATURE_CHANNEL.get(f) == ch] for ch in CHANNELS
}


def fit_score(Xtr: np.ndarray, ytr: np.ndarray, Xte: np.ndarray, seed: int) -> np.ndarray:
    mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0) + 1e-9
    clf = LogisticRegression(max_iter=3000, C=1.0, class_weight="balanced", random_state=seed)
    clf.fit((Xtr - mu) / sd, ytr)
    return clf.predict_proba((Xte - mu) / sd)[:, 1]


def _f(x: Any, signed: bool = False) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "  n/a"
    if v != v:
        return "  n/a"
    return f"{v:+.3f}" if signed else f"{v:.3f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--out", required=True)
    ap.add_argument("--folds", type=int, default=5,
                    help="task-level folds used for the ablation (independent of the main run)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rows = pq.read_table(os.path.join(args.run, "window_features.parquet")).to_pylist()
    cfg = json.load(open(os.path.join(args.run, "run_config.json"), encoding="utf-8"))
    w = cfg["args"]["w"]
    labelled = [r for r in rows if r["binary"] is not None and r["w"] == w]
    have_sem = cfg.get("has_semantic", False)
    # Rebuild task-level folds here rather than trusting the run's fold column, so the
    # ablation is well-defined even when the run used a single fold.
    tasks = sorted({r["task"] for r in labelled})
    task_fold = {t: i % args.folds for i, t in enumerate(tasks)}
    for r in labelled:
        r["fold"] = task_fold[r["task"]]
    print(f"{len(labelled)} labelled windows over {len(tasks)} tasks, {args.folds} folds "
          f"(full run used {cfg['folds']})")

    channels = [c for c in CHANNELS if CHANNEL_FEATURES[c] and (c != "SEM" or have_sem)]
    X = np.array([[r.get(f, np.nan) for f in ALL_FEATURES] for r in labelled], dtype=float)
    y = np.array([r["binary"] for r in labelled], dtype=int)
    fold = np.array([r["fold"] for r in labelled], dtype=int)
    results: Dict[str, Any] = {"n_windows": len(labelled), "channels": channels,
                               "folds": int(cfg["folds"]), "w": w}

    def evaluate(keep_idx: Sequence[int]) -> Dict[str, Any]:
        p = np.full(len(y), np.nan)
        for f in sorted(set(fold.tolist())):
            tr, te = fold != f, fold == f
            if len(set(y[tr].tolist())) < 2 or te.sum() == 0:
                continue
            Xtr = np.nan_to_num(X[tr][:, list(keep_idx)], nan=0.0, posinf=0.0, neginf=0.0)
            Xte = np.nan_to_num(X[te][:, list(keep_idx)], nan=0.0, posinf=0.0, neginf=0.0)
            p[te] = fit_score(Xtr, y[tr], Xte, args.seed)
        ok = ~np.isnan(p)
        m = window_metrics(y[ok], p[ok])
        return {"roc_auc": m["roc_auc"], "pr_auc": m["pr_auc"], "f1_best": m["f1_best"],
                "n": int(ok.sum())}

    all_idx = list(range(len(ALL_FEATURES)))
    full = evaluate(all_idx)
    results["full"] = full
    results["per_channel_alone"] = {}
    results["leave_one_out"] = {}
    for ch in channels:
        idxs = [ALL_FEATURES.index(f) for f in CHANNEL_FEATURES[ch]]
        alone = evaluate(idxs)
        results["per_channel_alone"][ch] = alone
        keep = [i for i in all_idx if i not in set(idxs)]
        loo = evaluate(keep)
        results["leave_one_out"][ch] = {
            **loo,
            "delta_roc": (loo["roc_auc"] - full["roc_auc"]) if loo["roc_auc"] == loo["roc_auc"] else None,
            "delta_pr": (loo["pr_auc"] - full["pr_auc"]) if loo["pr_auc"] == loo["pr_auc"] else None,
        }
        d_roc = results["leave_one_out"][ch]["delta_roc"]
        d_pr = results["leave_one_out"][ch]["delta_pr"]
        print(f"  {ch:5} alone roc={_f(alone['roc_auc'])} | without roc={_f(loo['roc_auc'])} "
              f"(delta {_f(d_roc, signed=True)})")
    print(f"full model roc={_f(full['roc_auc'])} pr={_f(full['pr_auc'])}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
