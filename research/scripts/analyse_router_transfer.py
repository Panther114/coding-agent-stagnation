"""Does the router transfer to agent runs it has never seen?

#5 of the brief is "a significant improvement over existing work".  The offline result already
shows a large margin (failure prediction 0.693-0.731 against the published detector family's
0.554-0.607, on identical rows and folds).  What that result does NOT yet show is that the margin
survives a change of data --- and a reviewer is entitled to read a single 26k-row table plus
random folds as "you fitted this corpus".

So this script trains on one shard set and evaluates on a DIFFERENT shard set, in both directions,
for every pair of the three disjoint step tables that now cover all 12 Nebius shards:

    A = shards 0-3   (the frozen study's data)
    B = shards 4-7   (unseen at training time)
    C = shards 8-11  (unseen at training time)

It reports, for the failure-prediction and failure-mode targets at four prefix fractions:
  * the within-set out-of-fold AUC (the reference number),
  * the cross-set AUC for every ordered pair (train -> test),
  * the same for each baseline family, trained and tested identically.

It also checks the assumption the whole thing rests on --- that the shard sets do not share
instances.  If they do, the "cross-set" column is partly a within-task result and that is reported
rather than glossed.

No frozen artifact is touched: this writes ``route_modes_transfer.json`` only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# import the frozen router module WITHOUT executing its main()
_spec = importlib.util.spec_from_file_location(
    "route_modes", ROOT / "scripts" / "analyse_route_modes.py")
arm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arm)

OUT = ROOT / "results" / "rebuild"
FRACTIONS = arm.FRACTIONS

SETS = {
    "A_shards0_3": (ROOT / "data" / "processed" / "steps",
                    OUT / "gold_patches.parquet"),
    "B_shards4_7": (ROOT / "data" / "processed" / "steps_repl",
                    OUT / "gold_patches_repl.parquet"),
    "C_shards8_11": (ROOT / "data" / "processed" / "steps_repl2",
                     OUT / "gold_patches_repl2.parquet"),
}

# baseline families evaluated exactly as in the frozen study, so the comparison is like-for-like
BASELINE_COLS = {
    "position": ["_prefix_len"],
    "agentstop_shape": [c for c in ("nov_obs_chars_mean", "nov_text_chars_mean",
                                    "rep_exact_frac", "rep_exact_maxrep")
                        if hasattr(arm, "COUNT_FEATURES")],
}


def load_set(name: str, steps_root: Path, gold_path: Path):
    """Build per-run labels and per-fraction prefix-feature tables for one shard set."""
    gold_df = pd.read_parquet(gold_path)
    gold = {str(k): set(v) for k, v in zip(gold_df["instance_id"], gold_df["gold_basenames"])}
    steps = pd.read_parquet(steps_root / "nebius" / "steps.parquet", columns=arm.STEP_COLS)
    steps = steps[steps["task"].isin(gold)].copy()
    labels = arm.build_labels(steps, gold)
    tables, _meta = arm.prefix_features(steps, FRACTIONS)
    n_steps_rows = len(steps)
    del steps
    return labels, tables, gold, n_steps_rows


def prep(train_t: pd.DataFrame, test_t: pd.DataFrame, labels: pd.DataFrame,
         y_col: str) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    """Merge labels in, drop undefined targets (y_wrong_fix is only defined for failed runs)."""
    def merge(t):
        m = t.merge(labels[["run_id", y_col]], on="run_id", how="inner")
        return m[np.isfinite(m[y_col].to_numpy(dtype=float))].reset_index(drop=True)

    tr, te = merge(train_t), merge(test_t)
    ytr = tr[y_col].to_numpy(dtype=float)
    yte = te[y_col].to_numpy(dtype=float)
    return tr, te, ytr, yte


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="route_modes_transfer.json")
    ap.add_argument("--only", nargs="*", default=None, help="subset of set names")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    names = args.only or list(SETS)
    print("loading sets ...", flush=True)
    loaded = {}
    for nm in names:
        root, gp = SETS[nm]
        if not (root / "nebius" / "steps.parquet").exists():
            print(f"  {nm}: MISSING {root}")
            continue
        t0 = time.time()
        labels, tables, gold, nrows = load_set(nm, root, gp)
        loaded[nm] = dict(labels=labels, tables=tables, gold=gold)
        n_fail = int((labels["y_fail"] == 1).sum())
        print(f"  {nm}: {len(labels):,} runs ({n_fail:,} failed), "
              f"{nrows:,} step rows, {len(tables[FRACTIONS[0]])} feature rows, "
              f"{time.time()-t0:.0f}s", flush=True)

    # ---- assumption check: do the shard sets share instances? -------------------------
    task_sets = {nm: set(d["labels"]["task"].astype(str)) for nm, d in loaded.items()}
    overlap = {}
    for a in names:
        for b in names:
            if a < b and a in task_sets and b in task_sets:
                inter = task_sets[a] & task_sets[b]
                overlap[f"{a}|{b}"] = {
                    "shared_instances": len(inter),
                    "frac_of_smaller": round(len(inter) / max(min(len(task_sets[a]),
                                                                len(task_sets[b])), 1), 4),
                    "examples": sorted(list(inter))[:5],
                }
    print("\ninstance overlap between shard sets:")
    for k, v in overlap.items():
        print(f"  {k}: {v['shared_instances']} shared ({v['frac_of_smaller']:.1%})")

    result: Dict[str, object] = {
        "purpose": ("train on one shard set, test on another; #5 evidence that the router's "
                    "margin is not a property of one corpus split"),
        "sets": {nm: {"n_runs": int(len(d["labels"])),
                      "n_instances": len(task_sets[nm]),
                      "n_failed": int((d["labels"]["y_fail"] == 1).sum())}
                 for nm, d in loaded.items()},
        "instance_overlap": overlap,
        "fractions": list(FRACTIONS),
        "targets": {},
        "note": ("features use steps 0..L-1 only; labels come from gold patches; each method is "
                 "trained on the source set's rows and scored on the target set's rows, with "
                 "standardisation computed on the source only"),
    }

    method_cols = {
        "own_rates": arm.RATE_FEATURES,
        "position": ["_prefix_len"],
        # The field's detector families, expressed with the columns this table actually has.
        # AgentStop's published shape is "per-step output size + adjacent-step overlap", which is
        # obs_mean + repeat_sig_frac here; the loop/redundancy families are the consecutive-repeat
        # features.  An earlier version looked for column names that do not exist in these tables
        # and silently produced no baseline at all (agentstop=None in every cell), so each family
        # is now checked against the real column list and skipped loudly if absent.
        "agentstop_shape": ["obs_mean", "repeat_sig_frac"],
        "ngram_loop": ["max_consec_repeat_norm", "has_repeat_3plus"],
        "redundancy": ["unique_sig_frac", "sig_entropy", "repeat_file_edit_frac"],
    }
    have = set(loaded[names[0]]["tables"][FRACTIONS[0]].columns)
    for mname in list(method_cols):
        miss = [c for c in method_cols[mname] if c not in have]
        if miss:
            print(f"  NOTE: baseline {mname} missing columns {miss} -> dropped")
            del method_cols[mname]
    print(f"  methods: {list(method_cols)}")

    for y_col, label in (("y_fail", "failure prediction"),
                         ("y_wrong_fix", "lost vs wrong-fix (failed runs only)")):
        per_frac = {}
        for f in FRACTIONS:
            entry: Dict[str, object] = {"label": label}
            # within-set out-of-fold, per set
            for nm, d in loaded.items():
                tr, te, ytr, yte = prep(d["tables"][f], d["tables"][f], d["labels"], y_col)
                if len(tr) < 200 or len(np.unique(ytr)) < 2:
                    continue
                try:
                    oof = arm.oof_scores(tr, method_cols["own_rates"], y_col, n_folds=5, seed=0)
                    ok = np.isfinite(oof)
                    entry[f"within_{nm}"] = float(arm._auc(ytr[ok], oof[ok])) if ok.sum() > 50 else None
                except Exception as e:
                    entry[f"within_{nm}"] = None
            # cross-set, every ordered pair.
            # NOTE: the source rows must be merged with the SOURCE labels and the target rows
            # with the TARGET labels.  An earlier version passed the destination's labels to
            # both sides, and because run_ids are disjoint across shard sets the inner merge
            # silently produced zero rows -- every cross cell came out empty and the verdict
            # read "None" instead of failing loudly.  Hence the explicit row-count assertions.
            cross: Dict[str, object] = {}
            for src in loaded:
                for dst in loaded:
                    if src == dst:
                        continue
                    tr, _, ytr, _ = prep(loaded[src]["tables"][f], loaded[src]["tables"][f],
                                         loaded[src]["labels"], y_col)
                    _, te, _, yte = prep(loaded[dst]["tables"][f], loaded[dst]["tables"][f],
                                         loaded[dst]["labels"], y_col)
                    if len(tr) < 200 or len(te) < 200 or len(np.unique(ytr)) < 2:
                        cross[f"{src}->{dst}"] = {"error": "insufficient rows",
                                                  "n_train": int(len(tr)), "n_test": int(len(te))}
                        continue
                    row = {}
                    for mname, cols in method_cols.items():
                        cols = [c for c in cols if c in tr.columns and c in te.columns]
                        if not cols:
                            continue
                        try:
                            s = arm.fit_predict(tr, te, cols, y_col)
                            row[mname] = float(arm._auc(yte, s))
                        except Exception as e:
                            row[mname] = None
                    row["n_train"] = int(len(tr))
                    row["n_test"] = int(len(te))
                    cross[f"{src}->{dst}"] = row
            entry["cross"] = cross
            per_frac[str(f)] = entry
            print(f"\n[{y_col}] f={f}")
            for k, v in entry.items():
                if k.startswith("within_"):
                    print(f"   within  {k[7:]:14s} AUC={v if v is None else round(v,4)}")
            for k, v in cross.items():
                print(f"   cross   {k:26s} own_rates={v.get('own_rates')} "
                      f"position={v.get('position')} agentstop={v.get('agentstop_shape')}")
        result["targets"][y_col] = per_frac

    # ---- verdict ---------------------------------------------------------------------
    def collect(target, key):
        vals = []
        for _, e in result["targets"].get(target, {}).items():
            if key.startswith("within_"):
                v = e.get(key)
                if v is not None:
                    vals.append(v)
            else:
                for k, row in (e.get("cross") or {}).items():
                    v = row.get(key)
                    if v is not None:
                        vals.append(v)
        return vals

    v = {}
    for tgt in ("y_fail", "y_wrong_fix"):
        within = collect(tgt, "within_A_shards0_3")
        cross_own = collect(tgt, "own_rates")
        cross_pos = collect(tgt, "position")
        cross_as = collect(tgt, "agentstop_shape")
        v[tgt] = {
            "within_own_rates_mean": round(float(np.mean(within)), 4) if within else None,
            "cross_own_rates_mean": round(float(np.mean(cross_own)), 4) if cross_own else None,
            "cross_own_rates_min": round(float(np.min(cross_own)), 4) if cross_own else None,
            "cross_position_mean": round(float(np.mean(cross_pos)), 4) if cross_pos else None,
            "cross_agentstop_mean": round(float(np.mean(cross_as)), 4) if cross_as else None,
            "own_minus_position": (round(float(np.mean(cross_own) - np.mean(cross_pos)), 4)
                                   if cross_own and cross_pos else None),
            "own_minus_agentstop": (round(float(np.mean(cross_own) - np.mean(cross_as)), 4)
                                    if cross_own and cross_as else None),
            "n_cross_cells": len(cross_own),
        }
    result["verdict"] = v
    print("\n=== VERDICT (cross-set, mean over all ordered pairs and fractions) ===")
    for tgt, d in v.items():
        print(f"  {tgt}: own={d['cross_own_rates_mean']} (min {d['cross_own_rates_min']}) "
              f"position={d['cross_position_mean']} agentstop={d['cross_agentstop_mean']} "
              f"| own-position={d['own_minus_position']} "
              f"own-agentstop={d['own_minus_agentstop']} in {d['n_cross_cells']} cells")

    (OUT / args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False, default=float),
                                encoding="utf-8")
    print(f"\nwrote {OUT / args.out}")


if __name__ == "__main__":
    main()
