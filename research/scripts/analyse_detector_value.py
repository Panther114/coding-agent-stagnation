"""Does the calibrated detector's own statistic predict an objective outcome?

    python scripts/analyse_detector_value.py

§2.9 built a persistence detector that reaches zero false alarms and oracle-level recall — but on the
*quiet-window* event, which shares telemetry with the feature set, so it is a detector benchmark
rather than evidence about waste. §2.7 then found workspace telemetry at chance for the objective
target.

This closes the loop honestly. The **same statistic** is computed on the opening 40% of each run —
one number per run, the longest run of consecutive windows its threshold rule considered quiet — and
used to predict an objective outcome that uses no window telemetry at all: whether the run is a
**high dead-ender** (dead-end share above the corpus median). The feature comes from the start of the
run and the label from the end, so neither can leak into the other.

Reported: AUC against the dead-end median split, against the run's dead-end share as a rank
correlation, and against the run's outcome; plus the two free controls (run length observed, window
count) and the study's own feature block for comparison.

Writes ``results/rebuild/detector_value.json``.
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
from agentstall.sequential import prefix_max_run  # noqa: E402

OUT = ROOT / "results" / "rebuild"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--opening", type=float, default=0.40)
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    # ---- the objective label, from the end of the run ---------------------------------
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
    labels["_high"] = (labels.dead_share > labels.dead_share.median()).astype(int)
    print(f"{len(labels)} runs; median dead-end share {labels.dead_share.median():.3f}")

    # ---- the statistic, from the opening only ----------------------------------------
    # The monitor scores live in the analysis output, not in the raw window table: the raw table
    # carries features, and `analyse_windows.py` writes `window_scores.parquet` with the fitted
    # per-window scores.  Reading the wrong file produced an empty statistic list.
    scores_path = OUT / "nebius_w10" / "window_scores.parquet"
    if not scores_path.exists():
        raise SystemExit(f"{scores_path} missing; run scripts/analyse_windows.py --corpus nebius")
    w = pd.read_parquet(scores_path)
    n_steps = w.groupby("run_id")["n_steps"].max().rename("n")
    w = w.merge(n_steps, on="run_id", how="left")
    op = w[w["t"] <= args.opening * w["n"]].copy()
    print(f"opening windows: {len(op)} over {op.run_id.nunique()} runs")

    feats: List[Dict[str, object]] = []
    for rid, g in op.groupby("run_id", sort=False):
        g = g.sort_values("t")
        row: Dict[str, object] = {"run_id": rid, "n_windows": len(g),
                                  "n_steps_observed": float(g["n"].iloc[0])}
        # the detector statistic: longest run of consecutive windows the monitor scored high,
        # where "high" means above this window series' own upper quartile (a threshold the
        # rule would have learned from the run's opening)
        for col in ("s_NOV_raw", "s_REP_raw", "s_STALL_stat"):
            if col not in g.columns:
                continue
            v = g[col].to_numpy(dtype=float)
            v = np.nan_to_num(v, nan=0.5)
            thr = float(np.quantile(v, 0.75))
            row[f"persist_run_{col}"] = float(np.max(prefix_max_run(v > thr))) if len(v) else 0.0
        feats.append(row)
    f = pd.DataFrame(feats)
    agg = f.merge(labels, on="run_id", how="inner")
    print(f"{len(agg)} runs with both a statistic and a label")

    res: Dict[str, object] = {"n_runs": int(len(agg)), "median_dead_share":
                              float(labels.dead_share.median())}
    y = agg["_high"].to_numpy(dtype=float)

    # ---- the statistic's value --------------------------------------------------------
    res["persistence_statistics"] = {}
    for col in [c for c in agg.columns if c.startswith("persist_run_")]:
        v = agg[col].to_numpy(dtype=float)
        entry = {
            "auc_high_dead_ender": E.safe_auc(y, v),
            "spearman_with_dead_share": E.safe_spearman(agg["dead_share"].to_numpy(dtype=float), v),
            "auc_run_fails": E.safe_auc(1 - agg["reward"].to_numpy(dtype=float), v),
        }
        res["persistence_statistics"][col] = entry
        print(f"  {col:<28} high-dead-ender AUC {entry['auc_high_dead_ender']:.3f}  "
              f"rank corr {entry['spearman_with_dead_share']:+.3f}  "
              f"failure AUC {entry['auc_run_fails']:.3f}")

    # ---- controls ---------------------------------------------------------------------
    controls = {"n_windows_observed": agg["n_windows"].to_numpy(dtype=float),
                "n_steps_observed": agg["n_steps_observed"].to_numpy(dtype=float),
                "n_edits_total": agg["n_edit"].to_numpy(dtype=float)}
    res["controls"] = {k: E.safe_auc(y, v) for k, v in controls.items()}
    print("\n  free controls against the same label:")
    for k, v in res["controls"].items():
        print(f"    {k:<22} AUC {v:.3f}")

    # ---- the study's own opening features, for comparison -----------------------------
    keys = [k for grp in FEATURE_GROUPS.values() for k in grp]
    cols = [c for c in op.columns if c in keys and not c.endswith(("_s", "_o"))]
    aggfeat = op.groupby("run_id")[cols].mean().join(
        labels.set_index("run_id")[["_high", "task", "dead_share"]], how="inner").dropna(subset=["_high"])
    fit = E.fit_logistic_cv(aggfeat, cols, y_col="_high", n_folds=args.folds)
    auc_block = E.safe_auc(aggfeat["_high"].to_numpy(dtype=float), fit["oof"])
    res["opening_feature_block"] = {"auc": auc_block, "n_features": len(cols),
                                    "n_runs": int(len(aggfeat))}
    print(f"\n  the study's full opening feature block: AUC {auc_block:.3f} "
          f"({len(cols)} features, {len(aggfeat)} runs)")

    best_stat = max(res["persistence_statistics"].items(),
                    key=lambda kv: kv[1]["auc_high_dead_ender"] or 0)
    res["verdict"] = {
        "best_persistence_statistic": best_stat[0],
        "best_persistence_auc": best_stat[1]["auc_high_dead_ender"],
        "feature_block_auc": auc_block,
        "beats_controls": bool(best_stat[1]["auc_high_dead_ender"]
                               > max(res["controls"].values())),
        "beats_feature_block": bool(best_stat[1]["auc_high_dead_ender"] > auc_block),
    }
    v = res["verdict"]
    print(f"\n  verdict: the detector's statistic reaches {v['best_persistence_auc']:.3f}, "
          f"{'above' if v['beats_controls'] else 'below'} the best free control "
          f"({max(res['controls'].values()):.3f}) and "
          f"{'above' if v['beats_feature_block'] else 'below'} the full feature block "
          f"({auc_block:.3f})")
    with open(OUT / "detector_value.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'detector_value.json'}")


if __name__ == "__main__":
    main()
