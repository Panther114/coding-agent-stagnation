"""Is the strong opening-block result real, or is it run length in disguise?

    python scripts/analyse_detector_value_length.py

`analyse_detector_value.py` reports that the study's opening feature block predicts whether a run
is a high dead-ender at **AUC 0.792** — far above the per-edit predictability of 0.539, and a
suspiciously large gap. The obvious explanation is that the block is largely reading **how much work
the run will do**, not how productively it will do it: a run that edits a lot has a higher chance of
a high dead-end share, and the opening of a long run already looks different.

That is testable directly. Two controls:

``M1`` **length-matched**.  Split runs into length deciles; within each decile, recompute the block's
       AUC. If the 0.792 collapses toward 0.5, the result was length.
``M2`` **length-residualised**.  Regress the run's dead-end share on its observed length, then ask
       how well the block predicts the *residual*.

Only what survives both is a statement about progress rather than about size.

Writes ``results/rebuild/detector_value_length.json``.
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
    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet",
                            columns=["run_id", "step", "file_shown"])
    d = st.merge(steps, on=["run_id", "step"], how="left").sort_values(["run_id", "step"])
    later = {}
    for _rid, g in d.groupby("run_id", sort=False):
        files = g["file_shown"].astype(str).to_numpy()
        idx = g.index.to_numpy()
        for k in range(len(idx) - 1):
            cur = files[k]
            later[idx[k]] = bool(cur) and (files[k + 1:] == cur).any()
    d["revisited_later"] = d.index.map(lambda i: later.get(i, False))
    d["dead_end"] = ((d["hit"] == 0) & (~d["revisited_later"])).astype(float)
    labels = d.groupby(["run_id", "task"]).agg(
        dead_share=("dead_end", "mean"), n_edit=("hit", "size"),
        reward=("reward", "max")).reset_index()

    scores_path = OUT / "nebius_w10" / "window_scores.parquet"
    w = pd.read_parquet(scores_path)
    n_steps = w.groupby("run_id")["n_steps"].max().rename("n")
    w = w.merge(n_steps, on="run_id", how="left")
    op = w[w["t"] <= args.opening * w["n"]].copy()
    keys = [k for grp in FEATURE_GROUPS.values() for k in grp]
    cols = [c for c in op.columns if c in keys and not c.endswith(("_s", "_o"))]
    feat = op.groupby("run_id")[cols].mean()
    feat["n_windows"] = op.groupby("run_id").size()
    feat["n_steps_total"] = op.groupby("run_id")["n"].first()
    agg = feat.join(labels.set_index("run_id")[["dead_share", "n_edit", "task", "reward"]],
                    how="inner").dropna(subset=["dead_share"])
    agg["_high"] = (agg.dead_share > agg.dead_share.median()).astype(int)
    print(f"{len(agg)} runs; block of {len(cols)} features; "
          f"median dead-end share {agg.dead_share.median():.3f}")

    res: Dict[str, object] = {"n_runs": int(len(agg)), "n_features": len(cols)}
    y = agg["_high"].to_numpy(dtype=float)
    fit = E.fit_logistic_cv(agg, cols, y_col="_high", n_folds=args.folds)
    base = E.safe_auc(y, fit["oof"])
    res["uncontrolled_auc"] = base
    print(f"\n  uncontrolled: AUC {base:.3f}")

    # ---- M1: within length deciles ----------------------------------------------------
    agg["_decile"] = pd.qcut(agg["n_edit"].rank(method="first"), 10, labels=False)
    within: List[float] = []
    for dec, g in agg.groupby("_decile"):
        if g["_high"].nunique() < 2 or len(g) < 100:
            continue
        f = E.fit_logistic_cv(g, cols, y_col="_high", n_folds=5)
        a = E.safe_auc(g["_high"].to_numpy(dtype=float), f["oof"])
        if a == a:
            within.append(a)
    res["M1_within_length_deciles"] = {
        "mean_auc": float(np.mean(within)) if within else float("nan"),
        "n_deciles": len(within), "per_decile": within,
    }
    print(f"  M1 within length deciles: mean AUC {np.mean(within):.3f} "
          f"over {len(within)} deciles (range {min(within):.3f}-{max(within):.3f})"
          if within else "  M1: no decile had both classes")

    # ---- M2: residualise the label on observed length ---------------------------------
    from sklearn.linear_model import LinearRegression
    Xl = np.log1p(agg["n_edit"].to_numpy(dtype=float)).reshape(-1, 1)
    yv = agg["dead_share"].to_numpy(dtype=float)
    rng = np.random.default_rng(0)
    tasks = np.array(sorted(agg["task"].unique()))
    rng.shuffle(tasks)
    resid = np.full(len(agg), np.nan)
    for held in np.array_split(tasks, args.folds):
        hs = set(held.tolist())
        tr = ~agg["task"].isin(hs).to_numpy()
        te = agg["task"].isin(hs).to_numpy()
        if tr.sum() < 50 or te.sum() < 10:
            continue
        m = LinearRegression().fit(Xl[tr], yv[tr])
        resid[te] = yv[te] - m.predict(Xl[te])
    ok = ~np.isnan(resid)
    auc_resid = E.safe_auc(agg["_high"].to_numpy(dtype=float)[ok] * 1.0, resid[ok])
    # AUC of the block against a residual-based label: use rank correlation instead, which does
    # not need a threshold on a continuous residual
    X = np.nan_to_num(agg[cols].to_numpy(dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    oof = np.full(len(agg), np.nan)
    rng2 = np.random.default_rng(1)
    tasks2 = np.array(sorted(agg["task"].unique()))
    rng2.shuffle(tasks2)
    for held in np.array_split(tasks2, args.folds):
        hs = set(held.tolist())
        tr = ~agg["task"].isin(hs).to_numpy()
        te = agg["task"].isin(hs).to_numpy()
        if tr.sum() < 50 or te.sum() < 10:
            continue
        mu, sd = X[tr].mean(axis=0), X[tr].std(axis=0)
        sd[sd < 1e-9] = 1.0
        m = LinearRegression().fit((X[tr] - mu) / sd, resid[tr])
        oof[te] = m.predict((X[te] - mu) / sd)
    rho = E.safe_spearman(resid, oof)
    res["M2_residual"] = {"spearman_with_length_residual": float(rho),
                          "n": int(ok.sum())}
    print(f"  M2 predicting the *length-residualised* dead-end share: rank correlation {rho:+.3f}")

    # how much of the label is length?
    from scipy import stats
    rho_len = stats.spearmanr(agg["n_edit"], agg["dead_share"]).statistic
    res["length_vs_label_spearman"] = float(rho_len)
    print(f"  how much is length alone: rank correlation between edit count and dead-end share "
          f"{rho_len:+.3f}")

    res["verdict"] = (
        "If the within-decile mean and the residual correlation are both near 0.5 and 0, the "
        "opening block is reading run size rather than run quality and the 0.792 must not be "
        "reported as progress prediction.")
    print(f"\n  {res['verdict']}")
    with open(OUT / "detector_value_length.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'detector_value_length.json'}")


if __name__ == "__main__":
    main()
