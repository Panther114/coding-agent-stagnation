"""Is file *choice* predictable early, when line *survival* is not?

    python scripts/analyse_on_target.py

The rebuild separates two things an agent gets right or wrong:

* **where it edits** — the share of its edits landing on a file the final patch touches: 65.8%
  overall, and *higher* for failing runs (0.620 vs 0.576), so it does not by itself decide success;
* **whether the lines survive** — predictable online at ~0.54, i.e. not at all.

The second is a dead end for a monitor. The first has not been tested online. It matters because
file choice is the coarser, more deliberate decision: an agent can see it is editing the wrong
module, whereas it cannot see whether its next line will be rewritten. If on-target rate is
predictable from the opening of a run, **that** is the monitor a runtime can act on, even though it
does not by itself determine the outcome.

Measured task-disjoint, from windows inside the opening 40% of each run:

``O1`` how well the opening predicts the run's final on-target rate (regression and top/bottom
       quartile classification);
``O2`` whether it beats the free alternative — run length so far, and the number of distinct files
       the run has already touched, both available without any model;
``O3`` the payoff: success by on-target quartile, so the paper can state whether improving file
       choice is worth anything, including the inconvenient comparison with failing runs.

Writes ``results/rebuild/on_target.json``.
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
    ap.add_argument("--opening", type=float, default=0.40)
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    st = pd.read_parquet(OUT / "alignment_steps.parquet")
    runs = st.groupby(["run_id", "task"]).agg(
        on_target=("touched_target", "mean"), n_edit=("hit", "size"),
        reward=("reward", "max")).reset_index()
    print(f"{len(runs)} runs; overall on-target {runs.on_target.mean():.3f}; "
          f"success {runs.reward.mean():.3f}")

    w = pd.read_parquet(ROOT / "data" / "processed" / "windows" / "nebius" / "windows.parquet")
    n_steps = w.groupby("run_id")["n_steps"].max().rename("n")
    w = w.merge(n_steps, on="run_id", how="left")
    early = w[w["t"] <= args.opening * w["n"]]
    keys = [k for grp in FEATURE_GROUPS.values() for k in grp]
    cols = [c for c in early.columns if c in keys and not c.endswith(("_s", "_o"))]
    agg = early.groupby("run_id")[cols].mean()
    agg["n_win_opening"] = early.groupby("run_id").size()
    agg = agg.join(runs.set_index("run_id")[["on_target", "reward", "task", "n_edit"]],
                   how="inner")
    agg = agg.dropna(subset=["on_target"])
    print(f"{len(agg)} of them have opening features ({len(cols)} features)")

    res: Dict[str, object] = {"n_runs": int(len(agg)), "overall_on_target": float(runs.on_target.mean()),
                              "n_features": len(cols), "opening": args.opening}

    # ---- O1: predict the run's final on-target rate --------------------------------
    q = agg["on_target"]
    agg["_top"] = (q >= q.quantile(0.75)).astype(int)
    agg["_bottom"] = (q <= q.quantile(0.25)).astype(int)
    o1 = {}
    for label, name in (("_top", "top_quartile_on_target"), ("_bottom", "bottom_quartile_on_target")):
        if agg[label].nunique() < 2:
            continue
        f = E.fit_logistic_cv(agg, cols, y_col=label, n_folds=args.folds)
        auc = E.safe_auc(agg[label].to_numpy(dtype=float), f["oof"])
        fw = E.fit_logistic_cv(agg, cols, y_col=label, n_folds=args.folds, within_task=True)
        aucw = E.safe_auc(agg[label].to_numpy(dtype=float), fw["oof"])
        o1[name] = {"auc": auc, "auc_within_task": aucw, "base_rate": float(agg[label].mean())}
        print(f"  O1 {name:<28} AUC {auc:.3f} (within-task {aucw:.3f}), "
              f"base rate {agg[label].mean():.3f}")
    res["O1_classification"] = o1

    # regression-style: rank correlation between a linear score and the rate
    from sklearn.linear_model import LinearRegression
    X = np.nan_to_num(agg[cols].to_numpy(dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    y = agg["on_target"].to_numpy(dtype=float)
    from agentstall import evaluate as _E
    oof = np.full(len(agg), np.nan)
    tasks = np.array(sorted(agg["task"].unique()))
    rng = np.random.default_rng(0)
    rng.shuffle(tasks)
    for held in np.array_split(tasks, args.folds):
        held_set = set(held.tolist())
        tr = ~agg["task"].isin(held_set).to_numpy()
        te = agg["task"].isin(held_set).to_numpy()
        if tr.sum() < 50 or te.sum() < 10:
            continue
        mu, sd = X[tr].mean(axis=0), X[tr].std(axis=0)
        sd[sd < 1e-9] = 1.0
        m = LinearRegression().fit((X[tr] - mu) / sd, y[tr])
        oof[te] = m.predict((X[te] - mu) / sd)
    rho = _E.safe_spearman(y, oof)
    res["O1_regression_spearman"] = float(rho)
    print(f"  O1 out-of-fold rank correlation with the run's on-target rate: {rho:+.3f}")

    # ---- O2: against the free alternatives ------------------------------------------
    free = {
        "run_length_so_far": agg["n"].to_numpy(dtype=float) if "n" in agg.columns else None,
        "n_windows_opening": agg["n_win_opening"].to_numpy(dtype=float),
        "n_edits_total": agg["n_edit"].to_numpy(dtype=float),
    }
    res["O2_free_alternatives"] = {}
    for name, v in free.items():
        if v is None:
            continue
        auc = E.safe_auc(agg["_top"].to_numpy(dtype=float), v)
        res["O2_free_alternatives"][name] = auc
        print(f"  O2 free baseline {name:<22} AUC {auc:.3f} (top-quartile target)")
    if o1.get("top_quartile_on_target"):
        best = o1["top_quartile_on_target"]["auc"]
        better = [k for k, v in res["O2_free_alternatives"].items()
                  if v == v and v > best]
        res["O2_model_beats_free"] = len(better) == 0
        print(f"  -> the model {'beats' if not better else 'does NOT beat'} every free baseline"
              + (f" (beaten by {better})" if better else ""))

    # ---- O3: does file choice track the outcome? ------------------------------------
    bands = pd.qcut(agg["on_target"].rank(method="first"), 4,
                    labels=["Q1 lowest", "Q2", "Q3", "Q4 highest"])
    o3 = agg.assign(band=bands).groupby("band", observed=True).agg(
        n=("reward", "size"), success=("reward", "mean"),
        mean_on_target=("on_target", "mean"), median_edits=("n_edit", "median")).reset_index()
    res["O3_success_by_on_target"] = o3.astype({"band": str}).to_dict("records")
    print("\n  O3 success by on-target quartile")
    for r in o3.itertuples():
        print(f"     {str(r.band):<12} on-target {r.mean_on_target:.3f}  n={r.n:>5}  "
              f"success {r.success:.3f}  median edits {r.median_edits:.0f}")

    res["caution"] = ("on-target rate is HIGHER for failing runs (0.620 vs 0.576 on the within-instance "
                      "comparison), so a monitor for file choice is not a success predictor; the "
                      "payoff question in O3 is reported per quartile rather than assumed")
    print(f"\n  caution: {res['caution']}")
    with open(OUT / "on_target.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'on_target.json'}")


if __name__ == "__main__":
    main()
