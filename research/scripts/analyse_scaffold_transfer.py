"""Does the monitor work on a scaffold it has never seen?

    python scripts/analyse_scaffold_transfer.py

Terminal-Bench 2.0's shard carries several agent scaffolds behind the same task suite, so
"held-out scaffold" is available directly: fit on the other scaffolds, score the held-out one.
That is a harder shift than held-out tasks, because the scaffolds differ in prompt, tool
vocabulary, turn structure and stopping behaviour — the same differences that broke the first
version's cross-corpus story.

Reported per scaffold, in both directions of comparison:

* **transfer AUC** — fitted elsewhere, scored here;
* **in-scaffold reference** — cross-validated within that scaffold's own tasks, the ceiling for
  a monitor that is allowed to know the scaffold;
* **degradation** — the difference, which is the quantity that says whether a scaffold-specific
  calibration is necessary.

A monitor that transfers is one a runtime can deploy without per-scaffold tuning. One that does
not is still useful, but the paper has to say so.

Writes ``results/rebuild/scaffold_transfer.json``.
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
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--min-runs", type=int, default=200)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    df = pd.read_parquet(ROOT / "data" / "processed" / "windows" / args.corpus / "windows.parquet")
    primary = "y_future_stagnation" if "y_future_stagnation" in df.columns else "y_stagnation"
    df = df[df[primary].notna()].copy()
    y = df[primary].to_numpy(dtype=float)
    keys = [k for grp in FEATURE_GROUPS.values() for k in grp]
    cols = [c for c in df.columns if c in keys]
    print(f"{args.corpus}: {len(df)} windows, {df.run_id.nunique()} runs, "
          f"{df.agent.nunique()} scaffolds, {len(cols)} features")
    counts = df.groupby("agent").run_id.nunique().sort_values(ascending=False)
    print(f"scaffolds with >= {args.min_runs} runs: "
          f"{int((counts >= args.min_runs).sum())}")
    for name, n in counts.head(12).items():
        print(f"    {name:<24} {n:>5} runs")

    from sklearn.linear_model import LogisticRegression

    res: Dict[str, object] = {"corpus": args.corpus, "n_features": len(cols),
                              "scaffolds": {}}
    for scaffold, n_runs in counts.items():
        if n_runs < args.min_runs:
            continue
        sel = (df["agent"] == scaffold).to_numpy()
        if sel.sum() < 500:
            continue
        X = np.nan_to_num(df[cols].to_numpy(dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
        mu = X[~sel].mean(axis=0)
        sd = X[~sel].std(axis=0)
        sd[sd < 1e-9] = 1.0
        yb = E.binarise(y)
        if yb[~sel].sum() == 0 or yb[sel].sum() == 0:
            continue
        model = LogisticRegression(max_iter=3000, C=1.0)
        model.fit((X[~sel] - mu) / sd, yb[~sel])
        transfer = E.safe_auc(y[sel], model.predict_proba((X[sel] - mu) / sd)[:, 1])
        sub = df[sel]
        in_scaf = E.fit_logistic_cv(sub, cols, y_col=primary, n_folds=5)["auc_mean"]
        # controls on the held-out scaffold
        pos = E.safe_auc(y[sel], sub["relpos"].to_numpy(dtype=float))
        entry = {
            "n_runs": int(n_runs), "n_windows": int(sel.sum()),
            "transfer_auc": transfer, "in_scaffold_auc": in_scaf,
            "degradation": (in_scaf - transfer) if not np.isnan(transfer) else float("nan"),
            "left_out_positive_rate": float(yb[sel].mean()),
            "other_scaffolds_positive_rate": float(yb[~sel].mean()),
            "position_auc_here": pos,
        }
        res["scaffolds"][scaffold] = entry
        print(f"  {scaffold:<24} transfer {transfer:.3f}  in-scaffold {in_scaf:.3f}  "
              f"degradation {entry['degradation']:+.3f}  (pos rate {entry['left_out_positive_rate']:.3f} "
              f"vs {entry['other_scaffolds_positive_rate']:.3f} elsewhere)")

    vals = [v for v in res["scaffolds"].values() if not np.isnan(v["transfer_auc"])]
    if vals:
        tr = np.array([v["transfer_auc"] for v in vals])
        ic = np.array([v["in_scaffold_auc"] for v in vals])
        dg = np.array([v["degradation"] for v in vals])
        res["summary"] = {
            "n_scaffolds": len(vals),
            "mean_transfer_auc": float(tr.mean()),
            "mean_in_scaffold_auc": float(ic.mean()),
            "mean_degradation": float(np.nanmean(dg)),
            "max_degradation": float(np.nanmax(dg)),
            "n_scaffolds_above_0.6_transfer": int((tr > 0.6).sum()),
        }
        s = res["summary"]
        print(f"\nacross {s['n_scaffolds']} scaffolds: transfer mean {s['mean_transfer_auc']:.3f}, "
              f"in-scaffold mean {s['mean_in_scaffold_auc']:.3f}, "
              f"mean degradation {s['mean_degradation']:+.3f}, max {s['max_degradation']:+.3f}; "
              f"{s['n_scaffolds_above_0.6_transfer']} of {s['n_scaffolds']} transfer above 0.60")

    with open(OUT / "scaffold_transfer.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'scaffold_transfer.json'}")


if __name__ == "__main__":
    main()
