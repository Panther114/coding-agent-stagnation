"""Is waste predictable from the *edit itself*?

    python scripts/analyse_edit_structure.py

The rebuilt result is that whether an edit's lines survive is unpredictable from the
preceding window (AUC ~0.54).  That is a statement about *preceding context*.  It leaves a
different and more useful question open: does the edit carry the information itself?

That matters because it separates two failure explanations:

* if the edit's own structure predicts survival, then a runtime could refuse a doomed edit
  *before applying it* — a different and much more actionable intervention than stopping a
  run; and
* if it does not, then whether writing survives is close to a coin flip conditional on what
  the agent decided to do, and no amount of monitoring this channel will change that.

The predictors are structural properties of the action plus the file it targets, all
available before the edit is applied: how many lines it writes, how large the file is, whether
this is the first edit to that file, how many distinct files the run has touched, how far into
the run it is, how many lines the file has gained so far, and whether the edit is a
create/replace/insert.  These are *not* the window features, so this is an independent test.

Writes ``results/rebuild/edit_structure.json``.
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
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seeds", type=int, nargs="+", default=None,
                    help="if given, repeat the headline fit across fold seeds and report the spread")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    st = pd.read_parquet(OUT / "alignment_steps.parquet")
    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet",
                            columns=["run_id", "step", "is_edit", "file_total", "file_shown",
                                     "added_lines_n", "edit_lines", "tool", "n_cmds", "verb",
                                     "obs_chars", "st_sig"])
    d = st.merge(steps, on=["run_id", "step"], how="left")
    d = d[d["is_edit"].fillna(0) > 0].copy()
    print(f"{len(d)} edit steps over {d.run_id.nunique()} runs")

    # ---- structural predictors, all knowable before the edit is applied ----------------
    d["n_added"] = d["n_added"].fillna(0.0)            # lines this edit writes
    d["file_size"] = d["file_total"].fillna(-1.0)      # size of the target file
    d["edit_lines"] = d["edit_lines"].fillna(0.0)
    d["n_cmds"] = d["n_cmds"].fillna(0.0)
    d["obs_chars"] = d["obs_chars"].fillna(0.0)
    g = d.groupby("run_id")
    d["edit_rank"] = g.cumcount().astype(float)                      # which edit this is
    d["n_edits_run"] = g["step"].transform("size").astype(float)
    d["file_edits_before"] = g.apply(
        lambda x: x.groupby("file_shown").cumcount(), include_groups=False
    ).reset_index(level=0, drop=True).astype(float)
    # cumulative distinct-file count, computed per run
    seen: Dict[str, int] = {}
    dist: List[float] = []
    for rid, grp in d.groupby("run_id", sort=False):
        s = set()
        for f in grp["file_shown"].astype(str):
            s.add(f)
            dist.append(float(len(s)))
    d["distinct_files_so_far"] = dist
    d["tool_is_create"] = (d["tool"].astype(str).str.lower() == "create").astype(float)
    d["tool_is_replace"] = (d["tool"].astype(str).str.lower().isin(
        ["str_replace", "edit", "insert", "replace"]).astype(float))
    d["relpos"] = d["edit_rank"] / d["n_edits_run"].clip(lower=1)
    d["log_added"] = np.log1p(d["n_added"])
    d["log_file_size"] = np.log1p(d["file_size"].clip(lower=0))

    struct_cols = ["n_added", "log_added", "file_size", "log_file_size", "edit_lines", "n_cmds",
                   "obs_chars", "edit_rank", "n_edits_run", "file_edits_before",
                   "distinct_files_so_far", "tool_is_create", "tool_is_replace", "relpos"]

    res: Dict[str, object] = {"n_edit_steps": int(len(d)), "n_runs": int(d.run_id.nunique()),
                              "features": struct_cols, "targets": {}}
    for lab, name in (("hit", "survives"),):
        y = (1.0 - d[lab].to_numpy(dtype=float))
        f = E.fit_logistic_cv(d, struct_cols, y_col=lab, n_folds=args.folds)
        auc = E.safe_auc(y, -d[lab].to_numpy(dtype=float))
        # logistic predicting `hit` directly, then negate the score for a waste direction
        yw = 1.0 - y
        fw = E.fit_logistic_cv(d, struct_cols, y_col=lab, n_folds=args.folds)
        res["targets"]["wasted"] = {
            "n": int(len(d)), "base_rate": float(yw.mean()),
            "auc_struct": E.safe_auc(yw, fw["oof"]),
            "auc_struct_within_task": E.safe_auc(
                yw, E.fit_logistic_cv(d, struct_cols, y_col=lab, n_folds=args.folds,
                                      within_task=True)["oof"]),
            "auc_position_only": E.safe_auc(yw, d["relpos"].to_numpy(dtype=float)),
        }
        c = res["targets"]["wasted"]
        print(f"\nwasted edit (base rate {c['base_rate']:.3f}, n={c['n']}):")
        print(f"  structural features      AUC {c['auc_struct']:.3f}")
        print(f"  structural, within-task  AUC {c['auc_struct_within_task']:.3f}")
        print(f"  position alone           AUC {c['auc_position_only']:.3f}")

    # Per-feature univariate signal.  ``hit`` means the edit landed a surviving line, so the
    # waste label is ``1 - hit``; ranking large values of a feature as "wasteful" is the right
    # direction only when the feature grows with waste.  Both directions are reported so the
    # sign can never be misread again -- an earlier version of this script flipped it and the
    # findings document briefly claimed the opposite of what the data shows.
    univ = []
    yw = 1.0 - d["hit"].to_numpy(dtype=float)
    for c in struct_cols:
        v = d[c].to_numpy(dtype=float)
        up = E.safe_auc(yw, v)          # high value -> wasted
        down = E.safe_auc(yw, -v)       # low value  -> wasted
        univ.append({"feature": c, "auc_high_means_wasted": up,
                     "auc_low_means_wasted": down,
                     "auc": max(up, down) if up == up and down == down else float("nan")})
    res["univariate"] = sorted(univ, key=lambda x: -(x["auc"] if x["auc"] == x["auc"] else 0))
    print("\nstrongest single structural predictors of waste (direction-corrected, "
          "AUC >= 0.5):")
    for u in res["univariate"][:8]:
        d_txt = "high->wasted" if u["auc_high_means_wasted"] >= u["auc_low_means_wasted"] \
            else "low->wasted"
        print(f"  {u['feature']:<24} AUC {u['auc']:.3f}  ({d_txt})")

    with open(OUT / "edit_structure.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)

    if args.seeds:
        spread = []
        yw = 1.0 - d["hit"].to_numpy(dtype=float)
        for seed in args.seeds:
            f = E.fit_logistic_cv(d, struct_cols, y_col="hit", n_folds=args.folds, seed=seed)
            spread.append(E.safe_auc(yw, f["oof"]))
        # The model is fitted on `hit` (survival), so its score ranks *survival*; the AUC of
        # that score against the waste label is therefore the *low* value. The waste-direction
        # AUC is 1 - that, which is what the headline quotes.
        res["seed_spread"] = {
            "seeds": args.seeds,
            "auc_waste_direction": [float(1.0 - v) for v in spread],
            "mean": float(1.0 - np.mean(spread)),
            "sd": float(np.std(spread)),
            "min": float(1.0 - np.max(spread)), "max": float(1.0 - np.min(spread)),
            "note": "survival-fitted scores negated for the waste direction",
        }
        with open(OUT / "edit_structure.json", "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2, default=float)
        s = res["seed_spread"]
        print(f"\nstructural model across fold seeds (waste direction): mean {s['mean']:.4f} "
              f"sd {s['sd']:.4f} range [{s['min']:.4f}, {s['max']:.4f}]")

    print(f"\nwrote {OUT / 'edit_structure.json'}")


if __name__ == "__main__":
    main()
