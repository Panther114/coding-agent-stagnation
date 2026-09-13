"""Cross-scaffold generalisation: train on all scaffolds but one, test on the held-out one.

This is the strongest within-corpus generalisation test we can run without new annotation:
the monitor is fitted on annotated windows from every scaffold except one, then evaluated on
that scaffold's windows. Reporting per-scaffold AUC answers "does this monitor work on a
scaffold I did not train on?", which is what a runtime vendor would need to know.

Usage: python scripts/run_cross_scaffold.py --run results/final/tb2_final --corpus tb2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import numpy as np  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

import paths  # noqa: E402
from evaluation import window_metrics  # noqa: E402
from features import ALL_FEATURES, CHANNELS, FEATURE_CHANNEL  # noqa: E402

GROUPS = {
    "auction/repetition": [f for f in ALL_FEATURES if FEATURE_CHANNEL.get(f) == "REP"],
    "novelty": [f for f in ALL_FEATURES if FEATURE_CHANNEL.get(f) == "NOV"],
    "evidence": [f for f in ALL_FEATURES if FEATURE_CHANNEL.get(f) == "EVID"],
    "verification": [f for f in ALL_FEATURES if FEATURE_CHANNEL.get(f) == "VER"],
    "workspace": [f for f in ALL_FEATURES if FEATURE_CHANNEL.get(f) == "WORK"],
    "semantic": [f for f in ALL_FEATURES if FEATURE_CHANNEL.get(f) == "SEM"],
}
GROUPS["evidence+verification"] = GROUPS["evidence"] + GROUPS["verification"]
GROUPS["evidence+semantic"] = GROUPS["evidence"] + GROUPS["semantic"]
GROUPS["all channels"] = [f for ch in CHANNELS for f in ALL_FEATURES if FEATURE_CHANNEL.get(f) == ch]
# the hand-designed evidence monitor, as an unfitted reference point
GROUPS["evidence (hand score)"] = None


def fit_predict(Xtr, ytr, Xte, seed=0) -> np.ndarray:
    mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0) + 1e-9
    clf = LogisticRegression(max_iter=3000, C=1.0, class_weight="balanced", random_state=seed)
    clf.fit((Xtr - mu) / sd, ytr)
    return clf.predict_proba((Xte - mu) / sd)[:, 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--out", default=None)
    ap.add_argument("--min-train", type=int, default=40)
    ap.add_argument("--min-test", type=int, default=15)
    args = ap.parse_args()

    rows = pq.read_table(os.path.join(args.run, "window_features.parquet")).to_pylist()
    rows = [r for r in rows if r["w"] == args.w and r["binary"] is not None]
    scaffolds = sorted({r["agent"] for r in rows})
    print(f"{len(rows)} labelled windows over {len(scaffolds)} scaffolds")

    out: Dict[str, Any] = {"scaffolds": scaffolds, "groups": {}}
    for gname, feats in GROUPS.items():
        per_scaffold = {}
        for s in scaffolds:
            te = [r for r in rows if r["agent"] == s]
            tr = [r for r in rows if r["agent"] != s]
            if len(te) < args.min_test or len(tr) < args.min_train:
                continue
            y_te = np.array([r["binary"] for r in te])
            if len(set(y_te.tolist())) < 2:
                continue
            if feats is None:
                # unfitted hand score: use the recorded feature values directly if present
                continue
            cols = [ALL_FEATURES.index(f) for f in feats]
            Xtr = np.nan_to_num(np.array([[r[f] for f in feats] for r in tr], dtype=float),
                                nan=0.0, posinf=0.0, neginf=0.0)
            Xte = np.nan_to_num(np.array([[r[f] for f in feats] for r in te], dtype=float),
                                nan=0.0, posinf=0.0, neginf=0.0)
            y_tr = np.array([r["binary"] for r in tr])
            if len(set(y_tr.tolist())) < 2:
                continue
            p = fit_predict(Xtr, y_tr, Xte)
            m = window_metrics(y_te, p)
            per_scaffold[s] = {"n": len(te), "positive_rate": float(y_te.mean()),
                               "roc_auc": m["roc_auc"], "pr_auc": m["pr_auc"]}
        vals = [v["roc_auc"] for v in per_scaffold.values() if v["roc_auc"] == v["roc_auc"]]
        out["groups"][gname] = {
            "per_scaffold": per_scaffold,
            "n_scaffolds": len(per_scaffold),
            "mean_auc": float(np.mean(vals)) if vals else None,
            "min_auc": float(np.min(vals)) if vals else None,
            "max_auc": float(np.max(vals)) if vals else None,
            "n_above_chance": int(sum(1 for v in vals if v > 0.5)),
        }
        if vals:
            print(f"  {gname:26} mean={np.mean(vals):.3f} range=[{np.min(vals):.3f},{np.max(vals):.3f}] "
                  f"scaffolds={len(vals)}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
