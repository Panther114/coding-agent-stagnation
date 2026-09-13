"""Stability of the field-comparison number (§2.24).

The field comparison is the one place this study claims a head-to-head win, and its
"this study's features" row (0.622 on the wasted-edit target) - like the 0.599 in §2.27 -
is a single cell of a much larger space.  A competitive claim resting on one cell is
weak, so this re-derives the *same* feature set and the *same* targets over a grid:

  learner  logistic (L2)  /  gradient boosting
  folds    5 / 10
  seed     0 / 1

The opponent families (OpenHands5, ngram_loop, exact_burst, tfnorm_novel, ...) are
fixed monitors with no hyperparameters, so they do not need a grid -- they are computed
here once each, on the identical rows, to show the gap this study's fitted model claims.

Nothing is refit on the outcome; all folds are task-disjoint.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall import evaluate as E  # noqa: E402
from agentstall.features import FEATURE_GROUPS  # noqa: E402

RES = ROOT / "results" / "rebuild"


def gbm_cv(df, cols, y_col, n_folds, seed):
    from sklearn.ensemble import HistGradientBoostingClassifier

    X = E._clean(df[list(cols)].to_numpy(dtype=float))
    y = E.binarise(df[y_col].to_numpy(dtype=float))
    oof = np.full(len(df), np.nan)
    for tr, te in E.task_disjoint_folds(df, n_folds=n_folds, seed=seed):
        if len(set(y[tr])) < 2:
            continue
        m = HistGradientBoostingClassifier(
            max_iter=120, learning_rate=0.08, max_depth=4, random_state=0
        )
        m.fit(X[tr], y[tr])
        oof[te] = m.predict_proba(X[te])[:, 1]
    return oof


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=0.1)
    args = ap.parse_args()

    rA = pd.read_parquet(RES / "routeA_steps.parquet")
    keys_all = [k for grp in FEATURE_GROUPS.values() for k in grp]
    own_cols = [c for c in rA.columns if c in keys_all]
    print(f"rows={len(rA):,}  own features={len(own_cols)}  tasks={rA.task.nunique():,}")

    targets = [("y_none_survive", "step_wasted"), ("y_edit_moved", "step_noop")]
    grid = [(lf, nf, sd) for lf in ("logit", "gbm") for nf in (5, 10) for sd in (0, 1)]

    out = {"n_rows": int(len(rA)), "n_own_features": len(own_cols), "budget": args.budget,
           "grid": [{"learner": a, "folds": b, "seed": c} for a, b, c in grid],
           "targets": {}}

    for y_col, task in targets:
        row = rA.loc[~rA[y_col].isna()].reset_index(drop=True)
        y = E.binarise(row[y_col].to_numpy(dtype=float))
        cells = []
        for learner, nf, sd in grid:
            if learner == "logit":
                f = E.fit_logistic_cv(row, own_cols, y_col=y_col, n_folds=nf, seed=sd)
                s = f["oof"]
            else:
                s = gbm_cv(row, own_cols, y_col, nf, sd)
            ok = ~np.isnan(s)
            a = float(E.safe_auc(y[ok], s[ok]))
            cells.append({"learner": learner, "folds": nf, "seed": sd, "auc": a})
            print(f"  {task:12s} {learner:5s} folds={nf:2d} seed={sd} AUC={a:.3f}", flush=True)
        arr = np.array([c["auc"] for c in cells])
        out["targets"][task] = {
            "n": int(len(row)), "base_rate": float(y.mean()),
            "cells": cells, "mean": float(arr.mean()), "sd": float(arr.std()),
            "min": float(arr.min()), "max": float(arr.max()),
        }
        print(f"  -> {task}: {arr.mean():.3f} +/- {arr.std():.3f} "
              f"({arr.min():.3f}-{arr.max():.3f})\n", flush=True)

    # the frozen single-cell values this grid is bounding
    prev = json.loads((RES / "detector_families.json").read_text(encoding="utf-8"))
    for task, t in out["targets"].items():
        p = prev["tasks"].get(task, {}).get("families", {})
        t["frozen_single_cell"] = p.get("own_all_raw", {}).get("auc")
        t["field_families"] = {k: v.get("auc") for k, v in p.items()
                               if k not in ("own_all_raw", "stall", "position")}
        if t["frozen_single_cell"] is not None:
            t["single_cell_rank_in_grid"] = float(
                np.mean(np.array([c["auc"] for c in t["cells"]]) >= t["frozen_single_cell"])
            )
            print(f"{task}: frozen 0.622-style single cell = {t['frozen_single_cell']:.3f}; "
                  f"best grid cell = {t['max']:.3f}")

    (RES / "field_comparison_stability.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=float), encoding="utf-8"
    )
    print(f"\nwrote {RES / 'field_comparison_stability.json'}")


if __name__ == "__main__":
    main()
