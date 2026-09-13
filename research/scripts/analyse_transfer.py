"""Cross-corpus transfer: does a monitor learned on one benchmark survive on another?

    python scripts/analyse_transfer.py

Terminal-Bench and SWE-bench-style trajectories differ in task length, scaffold, edit
interface and difficulty, so they are a genuine domain shift rather than a re-split.  A
monitor that only works in-corpus is a monitor of one benchmark.

Two directions are reported, and both are informative:

* **zero-shot**: fit on corpus A, score corpus B with the same fitted coefficients.
* **in-corpus reference**: the same feature block fitted and scored inside B, which
  bounds how much of the drop is the shift and how much is the feature block itself.

The features are the same *definitions* on both sides; the differing columns between
corpora (workspace telemetry exists only where the scaffold prints file line counts) are
reported explicitly rather than silently dropped.

Writes ``results/rebuild/transfer.json``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall import evaluate as E  # noqa: E402
from agentstall.features import FEATURE_GROUPS  # noqa: E402

OUT = ROOT / "results" / "rebuild"


def load(corpus: str, w: int = 10) -> pd.DataFrame:
    d = pd.read_parquet(ROOT / "data" / "processed" / "windows" / corpus / "windows.parquet")
    tgt = "y_future_stagnation" if "y_future_stagnation" in d.columns else "y_stagnation"
    d = d[d[tgt].notna()].copy()
    d["_y"] = d[tgt].to_numpy(dtype=float)
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    a = load("tb2", args.w)
    b = load("nebius", args.w)
    print(f"tb2: {len(a)} windows | nebius: {len(b)} windows")

    res: Dict[str, object] = {"w": args.w, "n_tb2": len(a), "n_nebius": len(b),
                              "cells": [], "notes": []}
    for gname, keys in FEATURE_GROUPS.items():
        cols = [k for k in keys if k in a.columns and k in b.columns]
        stat_cols = [c + "_s" for c in cols if c + "_s" in a.columns and c + "_s" in b.columns]
        for suffix, label in (("", "raw"), ("_s", "stat")):
            cs = cols if suffix == "" else stat_cols
            if len(cs) < 2:
                continue
            for src, dst, sname, dname in ((a, b, "tb2", "nebius"), (b, a, "nebius", "tb2")):
                cell = {"group": gname, "form": label, "from": sname, "to": dname,
                        "n_features": len(cs)}
                Xs = np.nan_to_num(src[cs].to_numpy(dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
                Xd = np.nan_to_num(dst[cs].to_numpy(dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
                ys = E.binarise(src["_y"].to_numpy(dtype=float))
                yd = E.binarise(dst["_y"].to_numpy(dtype=float))
                if ys.sum() == 0 or ys.sum() == len(ys):
                    continue
                mu = Xs.mean(axis=0)
                sd = Xs.std(axis=0)
                sd[sd < 1e-9] = 1.0
                from sklearn.linear_model import LogisticRegression
                m = LogisticRegression(max_iter=2000, C=1.0)
                m.fit((Xs - mu) / sd, ys)
                zero_shot = E.safe_auc(yd, m.predict_proba((Xd - mu) / sd)[:, 1])
                in_corpus = E.fit_logistic_cv(dst, cs, y_col="_y", n_folds=5)
                cell["zero_shot_auc"] = zero_shot
                cell["in_corpus_auc"] = in_corpus["auc_mean"]
                cell["drop"] = (in_corpus["auc_mean"] - zero_shot
                                if not np.isnan(zero_shot) else float("nan"))
                res["cells"].append(cell)
                print(f"  {gname:<6} {label:<5} {sname:>6} -> {dname:<6} "
                      f"zero-shot {zero_shot:.3f}  in-corpus {in_corpus['auc_mean']:.3f}  "
                      f"drop {cell['drop']:+.3f}  ({len(cs)} features)")

    # explicit note on columns that exist on one side only
    only_a = sorted(set(a.columns) - set(b.columns))
    only_b = sorted(set(b.columns) - set(a.columns))
    feat_only_a = [c for c in only_a if not c.startswith(("y_", "f_", "s_", "_"))]
    feat_only_b = [c for c in only_b if not c.startswith(("y_", "f_", "s_", "_"))]
    res["columns_only_in_tb2"] = feat_only_a
    res["columns_only_in_nebius"] = feat_only_b
    if feat_only_a or feat_only_b:
        res["notes"].append(
            "feature columns present in only one corpus were excluded from the cross-corpus "
            f"cells: tb2-only={feat_only_a[:8]}, nebius-only={feat_only_b[:8]}")
    print(f"\ncolumns only in tb2: {feat_only_a[:6]}")
    print(f"columns only in nebius: {feat_only_b[:6]}")

    out_path = Path(args.out) if args.out else OUT / "transfer.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
