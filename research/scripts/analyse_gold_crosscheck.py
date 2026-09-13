"""Reconcile the new objective study with the first version's judged gold labels.

    python scripts/analyse_gold_crosscheck.py

The first version's 1,198 adjudicated window labels are joined to the new per-window
feature table on ``(traj_id, t)``.  Three questions are then answerable that the first
version could not answer about itself:

1. **Is the judged label recoverable from mechanical telemetry?**
   For every window carrying both, does the window's *measured* change rate differ between
   windows a reader called PRODUCTIVE and windows a reader called STAGNANT?  If the judged
   label is not even monotonically related to whether the workspace moved, the label set is
   measuring something the trajectory does not contain -- which is exactly the objection a
   reviewer will raise.

2. **Do the same feature families win?**
   The first version's headline was that semantic redundancy beats task-grounded evidence,
   exact repetition and workspace churn.  Re-scoring the same families against the judged
   labels on the *new* table (larger stride coverage, corrected turn parsing) tests whether
   that ranking survived the rebuild or was an artefact of the old loader.

3. **How much of the judged signal is position?**
   The judged AUC is decomposed into between-task and within-run parts alongside the
   objective target, so the two targets can be compared directly.

Writes ``results/rebuild/gold_crosscheck.json``.
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

OUT = ROOT / "results" / "rebuild"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--corpus", default="tb2")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    gold = pd.read_csv(ROOT / "data" / "annotations" / "tb2" / "adjudicated.csv")
    win = pd.read_parquet(ROOT / "data" / "processed" / "windows" / args.corpus / "windows.parquet")
    print(f"gold windows {len(gold)}; candidate windows {len(win)}")

    g = gold.rename(columns={"traj_id": "run_id", "t": "t"})[["run_id", "t", "gold", "binary",
                                                             "task", "kind", "n_reads"]]
    g = g.drop_duplicates(["run_id", "t"])
    merged = win.merge(g, on=["run_id", "t"], how="inner", suffixes=("", "_g"))
    res: dict = {"n_gold": int(len(g)), "n_matched": int(len(merged)),
                 "match_rate": float(len(merged) / max(1, len(g)))}
    print(f"matched {len(merged)} / {len(g)} gold windows ({res['match_rate']:.1%})")
    if len(merged) < 50:
        print("too few matches to analyse")
        return
    res["gold_distribution"] = merged["gold"].value_counts().to_dict()
    binary = merged[merged["binary"].notna() & merged["y_stagnation"].notna()].copy()
    res["n_binary"] = int(len(binary))
    print(f"binary subset: {len(binary)} windows "
          f"(stagnant {int(binary['binary'].sum())}, productive {int((1 - binary['binary']).sum())})")

    # ---- 1. does the mechanical target track the judged label? ----------------------
    prod = binary.loc[binary["binary"] == 0, "y_stagnation"].to_numpy(dtype=float)
    stag = binary.loc[binary["binary"] == 1, "y_stagnation"].to_numpy(dtype=float)
    from scipy import stats
    mw = stats.mannwhitneyu(stag, prod, alternative="greater")
    res["mechanical_vs_judged"] = {
        "mean_nochange_productive": float(prod.mean()),
        "mean_nochange_stagnant": float(stag.mean()),
        "delta": float(stag.mean() - prod.mean()),
        "mannwhitney_p": float(mw.pvalue),
        "auc_nochange_predicts_judged": E.safe_auc(binary["binary"].to_numpy(dtype=float),
                                                   binary["y_stagnation"].to_numpy(dtype=float)),
    }
    m = res["mechanical_vs_judged"]
    print(f"\nmechanical change rate: PRODUCTIVE windows {m['mean_nochange_productive']:.3f} quiet, "
          f"STAGNANT windows {m['mean_nochange_stagnant']:.3f} quiet "
          f"(delta {m['delta']:+.3f}, p={m['mannwhitney_p']:.2e})")
    print(f"  AUC of the mechanical target against the judged label: "
          f"{m['auc_nochange_predicts_judged']:.3f}")

    # ---- 2. feature families against both targets ------------------------------------
    y_judged = binary["binary"].to_numpy(dtype=float)
    y_obj = E.binarise(binary["y_stagnation"].to_numpy(dtype=float))
    all_raw = [c for c in win.columns
               if c in [k for grp in FEATURE_GROUPS.values() for k in grp] and not c.startswith("y_")]
    fam: dict = {}
    for gname, keys in FEATURE_GROUPS.items():
        cols = [c for c in all_raw if c in keys]
        if not cols:
            continue
        record = {}
        for suffix, form in (("", "raw"), ("_s", "stat")):
            cs = [c + suffix for c in cols if (c + suffix) in binary.columns]
            if len(cs) != len(cols):
                continue
            fj = E.fit_logistic_cv(binary, cs, y_col="binary", n_folds=5)
            fo = E.fit_logistic_cv(binary, cs, y_col="y_stagnation", n_folds=5)
            record[form] = {
                "auc_judged": E.safe_auc(y_judged, fj["oof"]),
                "auc_objective": E.safe_auc(y_obj, fo["oof"]),
                "ap_judged": E.safe_ap(y_judged, fj["oof"]),
            }
        if record:
            fam[gname] = record
            print(f"  {gname:<6} judged AUC {record.get('raw', {}).get('auc_judged', float('nan')):.3f}"
                  f" (stat {record.get('stat', {}).get('auc_judged', float('nan')):.3f})"
                  f" | objective AUC {record.get('raw', {}).get('auc_objective', float('nan')):.3f}"
                  f" (stat {record.get('stat', {}).get('auc_objective', float('nan')):.3f})")
    res["families"] = fam

    # ---- 3. position decomposition on the judged target ------------------------------
    ranked = sorted(fam.items(), key=lambda kv: -kv[1].get("raw", {}).get("auc_judged", -1))
    if ranked:
        gname = ranked[0][0]
        cols = [c for c in all_raw if c in FEATURE_GROUPS[gname]]
        f = E.fit_logistic_cv(binary, cols, y_col="binary", n_folds=5)
        binary = binary.assign(_best=f["oof"])
        res["position_decomposition"] = {
            "monitor": gname,
            "by_task": E.group_contrast(binary, "_best", "binary", "task"),
            "by_run": E.group_contrast(binary, "_best", "binary", "run_id"),
            "within_run": {k: v for k, v in
                           E.within_run_auc(binary, "_best", "binary").items() if k != "per_run"},
            "position_only_auc": E.safe_auc(y_judged, binary["relpos"].to_numpy(dtype=float)),
            "step_index_auc": E.safe_auc(y_judged, binary["t"].to_numpy(dtype=float)),
        }
        pd_ = res["position_decomposition"]
        print(f"\nposition decomposition for {gname} against the judged label:")
        print(f"  by task between {pd_['by_task']['between_auc']:.3f} / within "
              f"{pd_['by_task']['within_spearman']:+.3f}; by run between "
              f"{pd_['by_run']['between_auc']:.3f} / within {pd_['by_run']['within_spearman']:+.3f}")
        print(f"  within-run mean AUC {pd_['within_run'].get('mean_auc', float('nan')):.3f}"
              f" (median {pd_['within_run'].get('median_auc', float('nan')):.3f})")
        print(f"  trivial baselines: position {pd_['position_only_auc']:.3f}, "
              f"step index {pd_['step_index_auc']:.3f}")

    # ---- 4. does the label distribution match the telemetry? -------------------------
    counts = merged.groupby("gold")["y_stagnation"].agg(["mean", "count"]).to_dict("index")
    res["mean_quiet_by_gold_class"] = {k: {"mean_quiet": float(v["mean"]), "n": int(v["count"])}
                                       for k, v in counts.items()}
    print("\nmean quiet share by judged class:")
    for k, v in res["mean_quiet_by_gold_class"].items():
        print(f"   {k:<18} {v['mean_quiet']:.3f}  (n={v['n']})")

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "gold_crosscheck.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    merged.to_parquet(OUT / "gold_matched_windows.parquet", index=False)
    print(f"\nwrote {OUT / 'gold_crosscheck.json'}")


if __name__ == "__main__":
    main()
