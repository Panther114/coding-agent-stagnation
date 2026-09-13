"""Main analysis: does the monitor work, and against which target?

    python scripts/analyse_windows.py --corpus nebius --w 10

Reads ``data/processed/windows/<corpus>/windows.parquet`` and writes
``results/rebuild/<corpus>_w<w>/analysis.json``.

The analysis is organised as the questions a reviewer would ask, in order:

A  What does the corpus actually contain? (base rates of every target)
B  Which feature family predicts stagnation, and does position explain it?
C  Does the monitor survive task-disjoint training? pooled vs within-run
D  Is it calibrated at the false-alarm rates a runtime would tolerate?
E  Does it beat the trivial baselines (position, step budget, token count)?
F  Does the objective target rank the features differently from judged labels?
G  What would acting on it be worth? (cost model, decision curve)
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

GROUP_PREFIX = {
    "REP": ["rep_", "mix_distinct_verbs"],
    "MIX": ["mix_"],
    "NOV": ["nov_"],
    "WS": ["ws_"],
    "VER": ["ver_"],
}


def cols_for(df, prefixes: List[str]) -> List[str]:
    return [c for c in df.columns if not c.endswith(("_s", "_o")) and any(c.startswith(p) for p in prefixes)
            and not c.startswith("y_")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, choices=["tb2", "nebius"])
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--root", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--target", default=None,
                    help="primary target column; defaults to the predictive one when present")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    win_dir = Path(args.root) if args.root else (ROOT / "data" / "processed" / "windows" / args.corpus)
    df = pd.read_parquet(win_dir / "windows.parquet")
    out_dir = Path(args.out) if args.out else (ROOT / "results" / "rebuild" / f"{args.corpus}_w{args.w}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Which target is primary?  The retrospective one (a window's own change rate) is what
    # the first version scored, but it is circular: the features describe exactly the steps
    # the label summarises, so any feature that counts change predicts it almost by
    # definition.  The predictive target -- does the NEXT window stagnate -- is the honest
    # online question and is used as primary whenever the extraction produced it.
    retro = "y_stagnation"
    if args.target:
        primary = args.target
    elif "y_future_stagnation" in df.columns and df["y_future_stagnation"].notna().sum() > 1000:
        primary = "y_future_stagnation"
    else:
        primary = retro
    n_future = int(df[primary].notna().sum()) if primary in df.columns else 0
    if primary != retro and n_future:
        df = df[df[primary].notna()].copy()
    res: Dict[str, object] = {"corpus": args.corpus, "w": args.w, "primary_target": primary,
                              "n_windows": int(len(df)), "n_runs": int(df.run_id.nunique()),
                              "n_tasks": int(df.task.nunique())}
    print(f"{args.corpus}: {len(df)} windows (target={primary}), {df.run_id.nunique()} runs, "
          f"{df.task.nunique()} tasks")

    # ------------------------------------------------------------------ A: base rates
    A: Dict[str, object] = {}
    base_cols = [c for c in ("y_stagnation", "y_loop", "y_waste", "y_nochange",
                             "y_future_stagnation", "y_future_loop", "y_future_waste")
                 if c in df.columns]
    for col in base_cols:
        v = df[col].dropna()
        A[col] = {"mean": float(v.mean()), "median": float(v.median()),
                  "frac_zero": float((v == 0).mean()), "frac_one": float((v == 1).mean()),
                  "n": int(len(v))}
    A["reward_mean"] = float(df["reward"].mean())
    A["per_task_stagnation"] = (df.groupby("task")["y_stagnation"].mean()
                                .describe().to_dict())
    A["frac_uniform_runs"] = float(
        df.groupby("run_id")["y_stagnation"].agg(lambda s: 1.0 if
                                                 (s > 0.5).all() or (s <= 0.5).all() else 0.0).mean())
    res["A_base_rates"] = A
    print(f"A base rates: stagnation {A['y_stagnation']['mean']:.3f}, "
          f"loop {A['y_loop']['mean']:.3f}, waste {A['y_waste']['mean']:.3f}, "
          f"uniform runs {A['frac_uniform_runs']:.1%}")

    # ------------------------------------------- B: family scores + position confound
    all_raw = [c for c in df.columns if c in
               [k for g in FEATURE_GROUPS.values() for k in g] and not c.startswith("y_")]
    B: Dict[str, object] = {"groups": {}, "single_features": [], "position_confound": {}}
    for gname, keys in FEATURE_GROUPS.items():
        cols = [c for c in all_raw if c in keys]
        if not cols:
            continue
        entry = {}
        for col in cols:
            y = df["y_stagnation"].to_numpy(dtype=float)
            s = df[col].to_numpy(dtype=float)
            a = E.safe_auc(y, s)
            entry[col] = {
                "auc": a,
                "auc_flipped": (1 - a) if not np.isnan(a) else np.nan,
                "spearman": E.safe_spearman(y, s),
                "r_position": float(pd.Series(s).corr(df["relpos"], method="spearman")),
                "r_position_s": float(pd.Series(df[col + "_s"]).corr(
                    df["relpos"], method="spearman"))
                if col + "_s" in df.columns else float("nan"),
            }
            B["single_features"].append({"feature": col, **entry[col]})
        B["groups"][gname] = entry
    # how much does the stationary transform reduce the position correlation?
    raw_corrs, stat_corrs = [], []
    for col in all_raw:
        if col + "_s" in df.columns:
            rc = abs(float(df[col].corr(df["relpos"], method="spearman")))
            sc = abs(float(df[col + "_s"].corr(df["relpos"], method="spearman")))
            if not (np.isnan(rc) or np.isnan(sc)):
                raw_corrs.append(rc)
                stat_corrs.append(sc)
    B["position_confound"] = {
        "mean_abs_spearman_raw": float(np.mean(raw_corrs)) if raw_corrs else None,
        "mean_abs_spearman_stat": float(np.mean(stat_corrs)) if stat_corrs else None,
        "n_features": len(raw_corrs),
        "frac_reduced": float(np.mean(np.array(stat_corrs) < np.array(raw_corrs)))
        if raw_corrs else None,
    }
    res["B_confound"] = B
    print(f"B position |rho|: raw {B['position_confound']['mean_abs_spearman_raw']:.3f} -> "
          f"stat {B['position_confound']['mean_abs_spearman_stat']:.3f} "
          f"(reduced in {B['position_confound']['frac_reduced']:.0%} of features)")

    # ------------------------------------------------- C/D/E: monitors and controls
    y = df[primary].to_numpy(dtype=float)
    groups_task = df["task"].to_numpy()
    C: Dict[str, object] = {"monitors": []}
    monitors: Dict[str, np.ndarray] = {}
    for gname, keys in FEATURE_GROUPS.items():
        cols = [c for c in all_raw if c in keys]
        if not cols:
            continue
        for suffix, label in (("", "raw"), ("_s", "stat"), ("_o", "o")):
            cs = [c + suffix for c in cols if (c + suffix) in df.columns]
            if len(cs) != len(cols):
                continue
            key = f"{gname}_{label}"
            f = E.fit_logistic_cv(df, cs, y_col=primary, n_folds=args.folds)
            monitors[key] = f["oof"]
            C["monitors"].append({"name": key, "cv_auc": f["auc_mean"],
                                  "oof_auc": E.safe_auc(y, f["oof"]),
                                  "oof_ap": E.safe_ap(y, f["oof"]),
                                  "oof_auc_within_task": float("nan")})
            keyw = f"{gname}_{label}_wt"
            fw = E.fit_logistic_cv(df, cs, y_col=primary, n_folds=args.folds, within_task=True)
            monitors[keyw] = fw["oof"]
            C["monitors"].append({"name": keyw, "cv_auc": fw["auc_mean"],
                                  "oof_auc": E.safe_auc(y, fw["oof"]),
                                  "oof_ap": E.safe_ap(y, fw["oof"]),
                                  "oof_auc_within_task": E.safe_auc(y, fw["oof"])})
    # trivial controls
    pos_col = "relpos" if "relpos" in df.columns else "_relpos"
    controls = {
        "position_only": df[pos_col].to_numpy(dtype=float),
        "step_index": df["t"].to_numpy(dtype=float) if "t" in df.columns else df["_t"].to_numpy(dtype=float),
        "step_budget_inv": -(df["t"].to_numpy(dtype=float) if "t" in df.columns
                             else df["_t"].to_numpy(dtype=float)),
        "nsteps_taskmean": df.groupby("task")["n_steps"].transform("mean").to_numpy(dtype=float),
        "n_steps_run": df["n_steps"].to_numpy(dtype=float),
    }
    for name, s in controls.items():
        C["monitors"].append({"name": name, "cv_auc": float("nan"),
                              "oof_auc": E.safe_auc(y, s), "oof_ap": E.safe_ap(y, s)})
    res["C_monitors"] = C
    for name, s in controls.items():
        monitors[name] = np.asarray(s, dtype=float)
    print(f"monitor zoo: {len(monitors)} entries")
    for m in sorted(C["monitors"], key=lambda x: -(x["oof_auc"] if x["oof_auc"] == x["oof_auc"] else 0)):
        print(f"   {m['name']:<22} oof AUC {m['oof_auc']:.3f}  AP {m['oof_ap']:.3f}")

    # within-run behaviour for the strongest monitors (computed after the full zoo exists)
    D: Dict[str, object] = {}
    ranked = sorted([m for m in C["monitors"] if m["name"] in monitors],
                    key=lambda x: -(x["oof_auc"] if x["oof_auc"] == x["oof_auc"] else 0))
    for m in ranked[:12]:
        name = m["name"]
        if name not in monitors:
            continue
        col = "s_" + name
        df[col] = monitors[name]
        wr = E.within_run_auc(df, col, primary)
        tp = E.task_paired_test(df, col, primary)
        gc_task = E.group_contrast(df, col, primary, "task")
        gc_run = E.group_contrast(df, col, primary, "run_id")
        bm = E.burst_metrics(df, col, primary, "run_id", alert_frac=0.10)
        pa = {f"pauc_{int(b*100)}": E.partial_auc(y, monitors[name], b) for b in (0.01, 0.05, 0.10)}
        db = {f"det_at_{int(b*100)}": E.detection_at_budget(y, monitors[name], b) for b in (0.01, 0.05)}
        D[name] = {"within_run": {k: v for k, v in wr.items() if k != "per_run"},
                   "task_paired": tp, "between_within_task": gc_task,
                   "between_within_run": gc_run, "burst": bm,
                   "partial_auc": pa, "budget": db}
        def _f(v, fmt="{:.3f}"):
            try:
                if v is None or (isinstance(v, float) and np.isnan(v)):
                    return "  n/a"
                return fmt.format(v)
            except Exception:
                return "  n/a"
        print(f"   {name:<22} pooled {_f(m['oof_auc'])} | within-run {_f(wr.get('mean_auc'))} "
              f"(med {_f(wr.get('median_auc'))}, {wr.get('n_above_half', 0)}/{wr.get('n_runs', 0)}) "
              f"| task-split between {_f(gc_task.get('between_auc'))} / "
              f"within {_f(gc_task.get('within_spearman'), '{:+.3f}')} "
              f"| burst lift {_f(bm.get('lift'), '{:.2f}')} "
              f"| pAUC@5% {_f(pa.get('pauc_5'))}")
    res["D_within_run"] = D

    # pairwise: does the best stat monitor beat the position control?
    Eres: Dict[str, object] = {}
    best_stat = next((m for m in ranked if m["name"].endswith("_stat") and m["name"] in monitors),
                     None)
    if best_stat and "position_only" in monitors:
        bs = monitors[best_stat["name"]]
        cb = E.paired_bootstrap_auc(y, bs, monitors["position_only"], groups=groups_task,
                                    n_boot=args.boot)
        Eres["best_stat_vs_position"] = {"monitor": best_stat["name"], **cb}
        print(f"E {best_stat['name']} vs position: delta {cb['delta']:+.3f} "
              f"[{cb['lo']:+.3f},{cb['hi']:+.3f}] p={cb['p']:.3f}")
    res["E_comparisons"] = Eres

    with open(out_dir / "analysis.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    df.to_parquet(out_dir / "window_scores.parquet", index=False)
    print(f"wrote {out_dir / 'analysis.json'}")


if __name__ == "__main__":
    main()
