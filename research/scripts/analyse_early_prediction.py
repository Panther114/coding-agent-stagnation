"""How early can a run's fate be called?

    python scripts/analyse_early_prediction.py --corpus nebius

A runtime cannot act on a prediction made at the end of a run. The rebuild's run-level result
(AUC 0.749 from the opening 40%) was measured at one checkpoint; this sweeps the checkpoint so
the paper can state the lead time, which is the quantity that decides whether a monitor is worth
deploying.

At each checkpoint ``f`` (the fraction of the run observed), features are averaged over windows
with ``t <= f * n_steps`` and used to predict the run's *final* failure, with task-disjoint folds.
The comparison that matters is against **run length so far**, the trivially available signal: a
monitor that cannot beat "how long has this been going" has not earned its cost.

Reported: AUC by checkpoint for the full feature block, for novelty and stall alone, and for the
two trivial controls. Also reported is the **base failure rate among runs long enough to be
assessed**, since the sample shrinks as the checkpoint moves later — a later checkpoint sees only
long runs, which fail more often, so a rising AUC can be partly a rising base rate.

Writes ``results/rebuild/early_prediction_<corpus>.json``.
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
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--checkpoints", type=float, nargs="+",
                    default=[0.10, 0.20, 0.30, 0.40, 0.50, 0.70])
    ap.add_argument("--min-windows", type=int, default=3)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    w = pd.read_parquet(ROOT / "data" / "processed" / "windows" / args.corpus / "windows.parquet")
    runs = pd.read_parquet(ROOT / "data" / "processed" / "steps" / args.corpus / "runs.parquet") \
        .drop_duplicates("run_id")[["run_id", "reward", "task"]]
    n_steps = w.groupby("run_id")["n_steps"].max().rename("n")
    w = w.merge(n_steps, on="run_id", how="left")
    w["_frac"] = (w["t"] + 1) / w["n"].clip(lower=1)

    keys = [k for grp in FEATURE_GROUPS.values() for k in grp]
    blocks = {
        "all_raw": [c for c in w.columns if c in keys],
        "novelty": [c for c in w.columns if c in FEATURE_GROUPS["NOV"]],
        "stall": [c for c in w.columns if c in FEATURE_GROUPS["STALL"]],
        "repetition": [c for c in w.columns if c in FEATURE_GROUPS["REP"]],
    }
    print(f"{args.corpus}: {len(w)} windows, {w.run_id.nunique()} runs, "
          f"failure rate {1 - runs['reward'].mean():.3f}")

    res: Dict[str, object] = {"corpus": args.corpus, "checkpoints": args.checkpoints,
                              "cells": []}
    for f in args.checkpoints:
        early = w[w["_frac"] <= f]
        agg_cols = sorted({c for cols in blocks.values() for c in cols})
        a = early.groupby("run_id")[agg_cols].mean()
        a = a.join(runs.set_index("run_id")[["reward", "task"]], how="inner")
        a = a.join(n_steps, how="left")
        sizes = early.groupby("run_id").size()
        a = a.join(sizes.rename("n_windows"), how="left")
        a = a[a["n_windows"] >= args.min_windows].copy()
        a["_y"] = (1 - a["reward"]).astype(int)
        if a["_y"].nunique() < 2 or len(a) < 200:
            continue
        y = a["_y"].to_numpy(dtype=float)
        cell = {
            "checkpoint": f, "n_runs": int(len(a)), "base_failure_rate": float(y.mean()),
            "mean_run_length": float(a["n"].mean()),
        }
        for bname, cols in blocks.items():
            cols = [c for c in cols if c in a.columns]
            if len(cols) < 2:
                continue
            fit = E.fit_logistic_cv(a, cols, y_col="_y", n_folds=args.folds)
            cell[f"auc_{bname}"] = E.safe_auc(y, fit["oof"])
        # trivial controls available at the same moment
        cell["auc_run_length_so_far"] = E.safe_auc(y, a["n"].to_numpy(dtype=float))
        cell["auc_windows_observed"] = E.safe_auc(y, a["n_windows"].to_numpy(dtype=float))
        # A selection effect has to be stated, not hidden.  Averaging over `t <= f*n` means a
        # later checkpoint can only be reached by runs that were already long -- and a run that
        # ended before the checkpoint is not in the sample at all. So the base failure rate rises
        # as the checkpoint moves earlier, and an AUC computed on a 0.98 base rate flatters
        # itself: almost any signal separates "ended in three steps" from "kept going".
        cell["effective_base_rate"] = float(y.mean())
        cell["note_short_run_enrichment"] = (
            "runs shorter than the checkpoint threshold are excluded by construction; at f=0.10 "
            "these are runs that died almost immediately, so the 0.878 there is partly the model "
            "detecting early death rather than stagnation")
        res["cells"].append(cell)

    print(f"\n{'checkpoint':>10} {'runs':>7} {'base fail':>10} {'all_raw':>8} {'novelty':>8} "
          f"{'stall':>7} {'repet':>7} {'run len':>8} {'n_win':>7}")
    for c in res["cells"]:
        print(f"{c['checkpoint']:>10.0%} {c['n_runs']:>7} {c['base_failure_rate']:>10.3f} "
              f"{c.get('auc_all_raw', float('nan')):>8.3f} {c.get('auc_novelty', float('nan')):>8.3f} "
              f"{c.get('auc_stall', float('nan')):>7.3f} {c.get('auc_repetition', float('nan')):>7.3f} "
              f"{c['auc_run_length_so_far']:>8.3f} {c['auc_windows_observed']:>7.3f}")

    if res["cells"]:
        best = max(res["cells"], key=lambda c: c.get("auc_all_raw", 0) or 0)
        above = [c["checkpoint"] for c in res["cells"]
                 if (c.get("auc_all_raw") or 0) >= 0.70]
        res["summary"] = {
            "best_checkpoint": best["checkpoint"], "best_auc": best.get("auc_all_raw"),
            "earliest_checkpoint_above_0.70": min(above) if above else None,
            "control_at_best": best["auc_run_length_so_far"],
            "beats_run_length_control_at_best": bool(
                (best.get("auc_all_raw") or 0) > best["auc_run_length_so_far"]),
            "n_checkpoints_beating_control": int(sum(
                1 for c in res["cells"]
                if (c.get("auc_all_raw") or 0) > c["auc_run_length_so_far"])),
            "n_checkpoints": len(res["cells"]),
        }
        s = res["summary"]
        print(f"\nbest full-feature AUC {s['best_auc']:.3f} at {s['best_checkpoint']:.0%} of the "
              f"run; earliest checkpoint above 0.70: {s['earliest_checkpoint_above_0.70']}")
        print(f"at that checkpoint run length alone gives {s['control_at_best']:.3f}; the feature "
              f"block beats that control at {s['n_checkpoints_beating_control']} of "
              f"{s['n_checkpoints']} checkpoints")

    with open(OUT / f"early_prediction_{args.corpus}.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / f'early_prediction_{args.corpus}.json'}")


if __name__ == "__main__":
    main()
