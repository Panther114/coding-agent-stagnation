"""Why position-stationarity destroys signal.

    python scripts/analyse_stationarity_mechanism.py

The rebuild reports a clean negative: two online position-stationary transforms remove the
run-position trend (mean |ρ| 0.242 → 0.138) and make the monitor **worse**, with the exact
drift-free form the worst of all (all-blocks 0.712 against 0.919 raw). A negative with no
mechanism invites "you implemented it wrong", so this measures the mechanism directly.

The hypothesis is specific and testable: **the transform removes between-run information as
well as within-run trend.** Subtracting a run's own running level leaves *deviations*, and a run
that is uniformly quiet has small deviations everywhere — so a drift-free statistic cannot tell
a quiet run from a busy one, which is exactly the discrimination the raw statistic gets for free
from the level.

Three measurements settle it:

``M1`` how much of the raw feature's between-run variance the transform removes, against how much
       of its within-run variance it removes. A well-behaved "trend removal" should spare the
       former.
``M2`` the AUC of each form against a target that is purely **between** runs (does this run stall
       at all?) versus one that is purely **within** (which windows of a stalling run are quiet?).
       The hypothesis predicts the drift-free form is catastrophic between runs and comparable
       within.
``M3`` the fraction of runs whose transformed scores are near-constant, which is what "the
       deviations vanished" looks like.

Writes ``results/rebuild/stationarity_mechanism.json``.
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

OUT = ROOT / "results" / "rebuild"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="nebius")
    ap.add_argument("--top", type=int, default=6)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    df = pd.read_parquet(ROOT / "data" / "processed" / "windows" / args.corpus / "windows.parquet")
    primary = "y_future_stagnation" if "y_future_stagnation" in df.columns else "y_stagnation"
    df = df[df[primary].notna()].copy()
    run_mean = df.groupby("run_id")[primary].transform("mean")
    df["_between_label"] = (run_mean > run_mean.median()).astype(float)   # run-level
    df["_within_label"] = (df[primary] - run_mean)                        # window-level deviation

    # feature keys that exist in all three forms
    base = [c for c in df.columns
            if not c.endswith(("_s", "_o")) and c + "_s" in df.columns and c + "_o" in df.columns
            and not c.startswith(("y_", "f_", "_"))]
    print(f"{args.corpus}: {len(df)} windows, {df.run_id.nunique()} runs, "
          f"{len(base)} features with all three forms")

    res: Dict[str, object] = {"corpus": args.corpus, "n_features": len(base), "features": {}}
    rows: List[Dict[str, float]] = []
    for c in base:
        raw = df[c].to_numpy(dtype=float)
        lev = df[c + "_s"].to_numpy(dtype=float)
        fit = df[c + "_o"].to_numpy(dtype=float)
        g = df.groupby("run_id")[c]
        between_raw = float(g.mean().var())

        def between_share(v: np.ndarray) -> float:
            s = pd.Series(v, index=df.index)
            b = float(s.groupby(df["run_id"]).mean().var())
            return b / between_raw if between_raw > 0 else float("nan")

        rows.append({
            "feature": c,
            "between_var_retained_level": between_share(lev),
            "between_var_retained_fit": between_share(fit),
            "auc_raw_between": E.safe_auc(df["_between_label"].to_numpy(dtype=float), raw),
            "auc_lev_between": E.safe_auc(df["_between_label"].to_numpy(dtype=float), lev),
            "auc_fit_between": E.safe_auc(df["_between_label"].to_numpy(dtype=float), fit),
            "auc_raw_within": E.safe_spearman(df["_within_label"].to_numpy(dtype=float), raw),
            "auc_lev_within": E.safe_spearman(df["_within_label"].to_numpy(dtype=float), lev),
            "auc_fit_within": E.safe_spearman(df["_within_label"].to_numpy(dtype=float), fit),
        })
    rdf = pd.DataFrame(rows)
    # rank by the raw feature's between-run discrimination
    rdf = rdf.reindex(rdf["auc_raw_between"].abs().sort_values(ascending=False).index)
    res["features"] = rdf.to_dict("records")

    print("\nbetween-run discrimination (does this run stall at all?)")
    print(f"  {'feature':<24} {'raw':>7} {'level-free':>11} {'drift-free':>11}   "
          f"between-var kept (lev / fit)")
    for r in rdf.head(args.top).itertuples():
        print(f"  {r.feature:<24} {r.auc_raw_between:>7.3f} {r.auc_lev_between:>11.3f} "
              f"{r.auc_fit_between:>11.3f}   {r.between_var_retained_level:>6.2f} / "
              f"{r.between_var_retained_fit:>5.2f}")

    print("\nwithin-run discrimination (which windows of a stalling run are quiet?)")
    print(f"  {'feature':<24} {'raw':>7} {'level-free':>11} {'drift-free':>11}")
    for r in rdf.head(args.top).itertuples():
        print(f"  {r.feature:<24} {r.auc_raw_within:>+7.3f} {r.auc_lev_within:>+11.3f} "
              f"{r.auc_fit_within:>+11.3f}")

    summ = {
        "mean_abs_between_raw": float(rdf["auc_raw_between"].abs().mean()),
        "mean_abs_between_lev": float(rdf["auc_lev_between"].abs().mean()),
        "mean_abs_between_fit": float(rdf["auc_fit_between"].abs().mean()),
        "mean_abs_within_raw": float(rdf["auc_raw_within"].abs().mean()),
        "mean_abs_within_lev": float(rdf["auc_lev_within"].abs().mean()),
        "mean_abs_within_fit": float(rdf["auc_fit_within"].abs().mean()),
        "mean_between_var_retained_fit": float(rdf["between_var_retained_fit"].mean()),
        "mean_between_var_retained_level": float(rdf["between_var_retained_level"].mean()),
    }
    res["summary"] = summ
    print(f"\nmean |between-run AUC|  raw {summ['mean_abs_between_raw']:.3f}  "
          f"level-free {summ['mean_abs_between_lev']:.3f}  "
          f"drift-free {summ['mean_abs_between_fit']:.3f}")
    print(f"mean |within-run rho|   raw {summ['mean_abs_within_raw']:.3f}  "
          f"level-free {summ['mean_abs_within_lev']:.3f}  "
          f"drift-free {summ['mean_abs_within_fit']:.3f}")
    print(f"between-run variance retained: level-free {summ['mean_between_var_retained_level']:.2f}, "
          f"drift-free {summ['mean_between_var_retained_fit']:.2f}")

    with open(OUT / "stationarity_mechanism.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'stationarity_mechanism.json'}")


if __name__ == "__main__":
    main()
