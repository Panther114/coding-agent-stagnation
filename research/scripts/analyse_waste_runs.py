"""Waste at the unit a practitioner acts on: the whole run.

The step-level result (§2.3 of the rebuild findings) is that a wasted *edit* is essentially
unpredictable from the surrounding window (AUC 0.574).  That is a negative about a specific
question.  This script asks the two questions that follow from it:

1. **Is waste a property of the run, or noise?**  If runs differ reliably in how much of
   their writing survives, then waste is a run-level regime and a run-level monitor is the
   right instrument, even though the step-level one is not.  Measured by the spread of
   per-run survival across runs and by a run-level split-half reliability: split each run's
   edit steps into two halves at random and correlate the survival of the halves.  A run
   property has a positive split-half correlation; independent per-edit coin flips do not.

2. **Can the opening of a run predict its waste?**  Features from the first ``--opening``
   fraction of the run predicting whether the run lands in the worst waste quartile, and
   whether it fails.  This is the only horizon at which a monitor could inform a decision
   before the work is spent.

Also reported: the **temporal profile** of waste (is it front-loaded, back-loaded, or
even?), which determines whether early warning is possible in principle.

Writes ``results/rebuild/waste_runs.json``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall import evaluate as E  # noqa: E402

OUT = ROOT / "results" / "rebuild"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--opening", type=float, default=0.4,
                    help="fraction of the run used to predict its own outcome")
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    st = pd.read_parquet(OUT / "alignment_steps.parquet")
    runs = pd.read_parquet(OUT / "alignment_runs.parquet")
    print(f"{len(st)} edit steps over {st.run_id.nunique()} runs")

    # ---- 1. is waste a run property? -------------------------------------------------
    st = st.sort_values(["run_id", "step"]).reset_index(drop=True)
    st["rank_in_run"] = st.groupby("run_id").cumcount()
    st["n_in_run"] = st.groupby("run_id")["step"].transform("size")
    st["relpos"] = st["rank_in_run"] / (st["n_in_run"] - 1).replace(0, np.nan)

    half_corr = []
    rng = np.random.default_rng(0)
    for _ in range(20):
        a_vals, b_vals = [], []
        for rid, g in st.groupby("run_id", sort=False):
            if len(g) < 4:
                continue
            idx = rng.permutation(len(g))
            ha = g.iloc[idx[: len(g) // 2]]
            hb = g.iloc[idx[len(g) // 2:]]
            if len(ha) < 2 or len(hb) < 2:
                continue
            a_vals.append(1.0 - ha["hit"].mean())
            b_vals.append(1.0 - hb["hit"].mean())
        if len(a_vals) > 50:
            half_corr.append(float(stats.spearmanr(a_vals, b_vals).statistic))
    res: Dict[str, object] = {
        "split_half_spearman_mean": float(np.mean(half_corr)) if half_corr else float("nan"),
        "split_half_spearman_sd": float(np.std(half_corr)) if half_corr else float("nan"),
        "n_splits": len(half_corr),
    }
    print(f"\nsplit-half reliability of per-run waste (20 random splits): "
          f"rho = {res['split_half_spearman_mean']:+.3f} "
          f"(sd {res['split_half_spearman_sd']:.3f})")

    # within-run spread of the waste share vs binomial expectation
    per_run = st.groupby("run_id").agg(n=("hit", "size"), waste=("hit", lambda s: 1 - s.mean()),
                                       task=("task", "first"), reward=("reward", "first"))
    per_run = per_run[per_run["n"] >= 4]
    obs_var = float(per_run["waste"].var())
    p = float(1.0 - st["hit"].mean())
    exp_var = float((p * (1 - p) * (1.0 / per_run["n"])).mean())
    res["waste_share_variance"] = {"observed": obs_var, "expected_if_independent": exp_var,
                                  "ratio": obs_var / exp_var if exp_var > 0 else float("nan"),
                                  "pooled_waste_rate": p, "n_runs": int(len(per_run))}
    print(f"per-run waste share: observed var {obs_var:.4f} vs {exp_var:.4f} if every edit "
          f"were an independent coin flip (ratio {obs_var / exp_var:.2f}x); "
          f"pooled waste rate {p:.3f}")

    # ---- temporal profile -----------------------------------------------------------
    prof = []
    for lo, hi, name in ((0.0, 0.25, "first_quarter"), (0.25, 0.5, "second_quarter"),
                         (0.5, 0.75, "third_quarter"), (0.75, 1.01, "last_quarter")):
        sel = st[(st.relpos >= lo) & (st.relpos < hi)]
        prof.append({"segment": name, "n": int(len(sel)), "waste": float(1.0 - sel["hit"].mean())})
    res["temporal_profile"] = prof
    print("waste by position in the run:",
          ", ".join(f"{x['segment']} {x['waste']:.3f}" for x in prof))

    # ---- 2. can the opening predict the run? ----------------------------------------
    win = pd.read_parquet(ROOT / "data" / "processed" / "windows" / "nebius" / "windows.parquet")
    n_steps = win.groupby("run_id")["n_steps"].max()
    first = win.merge(n_steps.rename("n"), on="run_id")
    opening = first[first["t"] <= (args.opening * first["n"])]
    agg_cols = [c for c in opening.columns
                if c.startswith(("mix_", "rep_", "nov_", "ws_", "ver_", "ent_"))
                and not c.endswith(("_s", "_o"))]
    agg = opening.groupby("run_id")[agg_cols].mean()
    agg = agg.join(per_run[["waste", "n", "task", "reward"]], how="inner")
    agg = agg.dropna(subset=["waste"])
    print(f"\nopening features for {len(agg)} runs (first {args.opening:.0%} of steps, "
          f"{len(agg_cols)} features)")

    out: Dict[str, object] = {"n_runs_with_opening": int(len(agg))}
    for label, target in (("worst_waste_quartile",
                           (agg["waste"] >= agg["waste"].quantile(0.75)).astype(int)),
                          ("failed", (1 - agg["reward"]).astype(int))):
        d = agg.assign(_y=target.to_numpy())
        if d["_y"].nunique() < 2:
            continue
        f = E.fit_logistic_cv(d, agg_cols, y_col="_y", n_folds=args.folds)
        auc = E.safe_auc(d["_y"].to_numpy(dtype=float), f["oof"])
        base = float(d["_y"].mean())
        out[label] = {"auc": auc, "base_rate": base, "n": int(len(d)),
                      "n_features": len(agg_cols),
                      "auc_from_nsteps_alone": E.safe_auc(
                          d["_y"].to_numpy(dtype=float), d["n"].to_numpy(dtype=float))}
        print(f"  predict {label:<22} from the opening: AUC {auc:.3f} "
              f"(base rate {base:.3f}, run length alone {out[label]['auc_from_nsteps_alone']:.3f})")

    # concentration of waste in the worst runs, for the record
    q = per_run["waste"]
    res["waste_distribution"] = {
        "p10": float(q.quantile(0.10)), "median": float(q.median()),
        "p90": float(q.quantile(0.90)), "frac_runs_above_0.5": float((q > 0.5).mean()),
        "frac_runs_below_0.1": float((q < 0.1).mean()),
    }
    print(f"\nper-run waste share: p10 {q.quantile(0.10):.3f}, median {q.median():.3f}, "
          f"p90 {q.quantile(0.90):.3f}; {(q > 0.5).mean():.1%} of runs waste more than half")

    res.update({"opening_targets": out})
    with open(OUT / "waste_runs.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    per_run.to_parquet(OUT / "waste_by_run.parquet")
    print(f"\nwrote {OUT / 'waste_runs.json'}")


if __name__ == "__main__":
    main()
