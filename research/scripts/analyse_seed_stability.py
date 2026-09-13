"""Are the headline AUCs stable across the random choices the protocol makes?

    python scripts/analyse_seed_stability.py --corpus nebius --seeds 0 1 2 3 4

Three things in this pipeline are random or arbitrary, and a reviewer is entitled to ask
whether a headline number survives resampling them:

* **which tasks land in which fold** — the evaluation is 5-fold task-disjoint cross-validation,
  and with 45 to 1,200 tasks a different partition could move the answer;
* **which windows are sampled** — the labels are produced at a stride;
* **the tie-breaking in the bootstrap** used for the paired comparisons.

This reports the spread of the headline quantities across fold seeds, as a range rather than a
point. If the range is wide relative to the effect, the effect is not established; if it is
narrow, the number is a property of the data rather than of the split.

Writes ``results/rebuild/seed_stability_<corpus>.json``.
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="nebius")
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    df = pd.read_parquet(ROOT / "data" / "processed" / "windows" / args.corpus / "windows.parquet")
    primary = "y_future_stagnation" if "y_future_stagnation" in df.columns else "y_stagnation"
    df = df[df[primary].notna()].copy()
    y = df[primary].to_numpy(dtype=float)
    print(f"{args.corpus}: {len(df)} windows, {df.run_id.nunique()} runs, target {primary}")

    all_keys = [k for grp in FEATURE_GROUPS.values() for k in grp]
    blocks = {"ALL_raw": [c for c in df.columns if c in all_keys],
              "NOV_raw": [c for c in df.columns if c in FEATURE_GROUPS["NOV"]],
              "REP_raw": [c for c in df.columns if c in FEATURE_GROUPS["REP"]],
              "STALL_raw": [c for c in df.columns if c in FEATURE_GROUPS["STALL"]],
              "ALL_stat": [c + "_s" for c in df.columns if c in all_keys and c + "_s" in df.columns]}
    controls = {"position": df["relpos"].to_numpy(dtype=float),
                "step_index": df["t"].to_numpy(dtype=float),
                "n_steps": df["n_steps"].to_numpy(dtype=float)}

    res: Dict[str, object] = {"corpus": args.corpus, "n_windows": int(len(df)),
                              "n_runs": int(df.run_id.nunique()), "target": primary,
                              "seeds": args.seeds, "cells": {}}
    per_block: Dict[str, List[float]] = {b: [] for b in blocks}
    per_control: Dict[str, List[float]] = {c: [] for c in controls}
    for seed in args.seeds:
        for bname, cols in blocks.items():
            cols = list(dict.fromkeys(cols))
            if len(cols) < 2:
                continue
            f = E.fit_logistic_cv(df, cols, y_col=primary, n_folds=args.folds, seed=seed)
            a = E.safe_auc(y, f["oof"])
            per_block[bname].append(a)
        for cname, cv in controls.items():
            per_control[cname].append(E.safe_auc(y, cv))
        print(f"  seed {seed}: " +
              "  ".join(f"{b} {per_block[b][-1]:.4f}" for b in per_block if per_block[b]) +
              "  |  " + "  ".join(f"{c} {per_control[c][-1]:.4f}" for c in per_control))
    for b, vals in per_block.items():
        if vals:
            res["cells"][b] = {"mean": float(np.mean(vals)), "sd": float(np.std(vals)),
                               "min": float(np.min(vals)), "max": float(np.max(vals)),
                               "values": [float(v) for v in vals]}
    for c, vals in per_control.items():
        res["cells"][c] = {"mean": float(np.mean(vals)), "sd": float(np.std(vals)),
                           "min": float(np.min(vals)), "max": float(np.max(vals)),
                           "values": [float(v) for v in vals]}

    print("\nspread across fold seeds:")
    for name, v in sorted(res["cells"].items(), key=lambda kv: -kv[1]["mean"]):
        print(f"  {name:<12} mean {v['mean']:.4f}  sd {v['sd']:.4f}  "
              f"range [{v['min']:.4f}, {v['max']:.4f}]")
    with open(OUT / f"seed_stability_{args.corpus}.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / f'seed_stability_{args.corpus}.json'}")


if __name__ == "__main__":
    main()
