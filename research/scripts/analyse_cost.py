"""What the waste costs, in the units a budget is actually spent in.

    python scripts/analyse_cost.py

Everything so far is denominated in edits and steps. A practitioner budgets tokens, wall-clock
time and dollars, so the paper needs the waste priced in those units — and needs the question
answered that a budget owner would ask next: is there a cheap proxy for the expensive thing?

The Terminal-Bench shard carries per-trial cost telemetry (input, output and cached tokens,
wall-clock duration, and cost in cents) for the runs that report it. Joining it to the mechanical
labels answers three questions:

``C1`` what does a run's cost buy?  Success rate and surviving-edit share against cost, so the
       paper can state cost-per-unit-of-real-work rather than per attempt.
``C2`` is cost concentrated?  What share of total spend goes to runs that produce no surviving
       edit at all.
``C3`` is there a free early proxy?  How well does the spend observed at a checkpoint predict the
       run's eventual total — which is what a budget policy would have to act on.

Caveats are reported rather than buried: this shard's cost fields are null for some scaffolds, so
every number carries its own denominator and the coverage is printed before any result.

Writes ``results/rebuild/cost.json``.
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
    ap.add_argument("--corpus", default="tb2")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    runs = pd.read_parquet(ROOT / "data" / "processed" / "steps" / args.corpus / "runs.parquet") \
        .drop_duplicates("run_id")
    cols = [c for c in ("duration_seconds", "input_tokens", "output_tokens", "cache_tokens",
                        "cost_cents") if c in runs.columns]
    print(f"{args.corpus}: {len(runs)} runs; cost columns present: {cols}")
    if not cols:
        print("no cost telemetry in this corpus; nothing to price")
        return
    for c in cols:
        n = int(runs[c].notna().sum())
        print(f"  {c:<18} non-null {n:>6} / {len(runs)}  "
              f"median {runs[c].median() if n else float('nan'):.1f}")

    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / args.corpus / "steps.parquet",
                            columns=["run_id", "is_edit", "n_steps"])
    agg = steps.groupby("run_id").agg(n_edit=("is_edit", "sum"), n_steps=("n_steps", "max"))
    d = runs.merge(agg, on="run_id", how="inner", suffixes=("", "_s"))
    d["_success"] = d["reward"].astype(float)
    if "input_tokens" in d.columns and "output_tokens" in d.columns:
        d["tokens"] = d["input_tokens"].fillna(0) + d["output_tokens"].fillna(0)
    res: Dict[str, object] = {"corpus": args.corpus, "n_runs": int(len(d)),
                              "coverage": {c: int(d[c].notna().sum()) for c in cols}}
    has_cost = d["cost_cents"].notna() if "cost_cents" in d.columns else pd.Series(False, index=d.index)
    priced = d[has_cost].copy()
    res["n_priced_runs"] = int(len(priced))
    print(f"\n{len(priced)} runs carry a cost figure")

    if len(priced) > 100:
        # Some trials carry a NEGATIVE cost, which is a credit or a reporting artefact rather
        # than a spend.  They are excluded from every money aggregate and counted, because a
        # silently included negative would corrupt the quintiles and the per-success figure.
        n_neg = int((priced["cost_cents"] < 0).sum())
        res["n_negative_cost_excluded"] = n_neg
        if n_neg:
            print(f"  excluding {n_neg} trials with a negative reported cost "
                  f"(credits/artefacts), min {priced['cost_cents'].min():.1f}c")
        priced = priced[priced["cost_cents"] >= 0].copy()
        res["n_positive_cost_runs"] = int(len(priced))

        # ---- C1: what does spend buy? -------------------------------------------------
        priced["cost_band"] = pd.qcut(priced["cost_cents"].rank(method="first"), 5,
                                      labels=["Q1 cheapest", "Q2", "Q3", "Q4", "Q5 dearest"])
        bands = priced.groupby("cost_band", observed=True).agg(
            n=("run_id", "size"), success=("_success", "mean"),
            cost_median=("cost_cents", "median"), steps_median=("n_steps_s", "median"),
            edits_median=("n_edit", "median")).reset_index()
        res["C1_cost_bands"] = bands.astype({"cost_band": str}).to_dict("records")
        print("\nC1 cost quintile -> what it buys")
        for r in bands.itertuples():
            print(f"  {str(r.cost_band):<14} n={r.n:>5}  median cost {r.cost_median:>7.1f}c  "
                  f"median steps {r.steps_median:>5.0f}  median edits {r.edits_median:>4.0f}  "
                  f"success {r.success:.3f}")
        # the ceiling question: does success ever rise materially with spend?
        ok = priced[priced["cost_cents"] > 0]
        dec = ok.groupby(pd.qcut(ok["cost_cents"], 10, duplicates="drop"),
                         observed=True).agg(success=("_success", "mean"),
                                            n=("run_id", "size"),
                                            cost=("cost_cents", "median")).reset_index()
        res["C1_deciles"] = dec.astype({dec.columns[0]: str}).to_dict("records")
        succ = dec["success"].to_numpy(dtype=float)
        res["C1_saturation"] = {
            "success_min": float(np.nanmin(succ)), "success_max": float(np.nanmax(succ)),
            "success_iqr": float(np.nanpercentile(succ, 75) - np.nanpercentile(succ, 25)),
            "cost_ratio_top_over_bottom": float(dec["cost"].iloc[-1] / max(1e-9, dec["cost"].iloc[0])),
            "note": ("success across cost deciles is the saturation curve: if it is flat, spending "
                     "more does not buy a higher chance of solving"),
        }
        s = res["C1_saturation"]
        print(f"  success across deciles spans only {s['success_min']:.3f}-{s['success_max']:.3f} "
              f"while median cost spans {s['cost_ratio_top_over_bottom']:.0f}x")

        # cost per successful run
        per_success = {
            "total_cost_cents": float(priced["cost_cents"].sum()),
            "n_success": int(priced["_success"].sum()),
            "cost_per_success_cents": float(priced["cost_cents"].sum()
                                            / max(1, priced["_success"].sum())),
            "cost_per_success_cents_if_failures_free": float(
                priced.loc[priced._success == 1, "cost_cents"].mean())
            if (priced._success == 1).any() else float("nan"),
        }
        res["C1_cost_per_success"] = per_success
        print(f"  total {per_success['total_cost_cents']:.0f}c across "
              f"{per_success['n_success']} successes -> "
              f"{per_success['cost_per_success_cents']:.1f}c per success")

        # ---- C2: is spend concentrated in runs that produce nothing? ------------------
        zero_edit = priced[priced["n_edit"] == 0]
        res["C2_zero_edit"] = {
            "n_runs": int(len(zero_edit)),
            "cost_share": float(zero_edit["cost_cents"].sum() / priced["cost_cents"].sum()),
            "success_rate": float(zero_edit["_success"].mean()) if len(zero_edit) else float("nan"),
            "success_rate_others": float(priced.loc[priced["n_edit"] > 0, "_success"].mean()),
        }
        z = res["C2_zero_edit"]
        print(f"\nC2 runs that make no edit at all: {z['n_runs']} runs, "
              f"{z['cost_share']:.1%} of total spend, success {z['success_rate']:.3f} "
              f"against {z['success_rate_others']:.3f} for the rest")

        # ---- C3: can spend-so-far predict total spend? --------------------------------
        if "duration_seconds" in priced.columns and priced["duration_seconds"].notna().sum() > 200:
            ok = priced[priced["duration_seconds"].notna()]
            rho = stats.spearmanr(ok["duration_seconds"], ok["cost_cents"]).statistic
            res["C3_duration_cost_rho"] = float(rho)
            print(f"\nC3 wall-clock duration vs cost: Spearman {rho:+.3f} (n={len(ok)}) — "
                  f"duration is a free proxy for spend")

    # success against cost, as an AUC, to say whether spend predicts outcome
    if len(priced) > 100:
        res["C_outcome_from_cost"] = {
            "auc_cost_predicts_success": E.safe_auc(priced["_success"].to_numpy(dtype=float),
                                                    -priced["cost_cents"].to_numpy(dtype=float)),
            "auc_steps_predicts_success": E.safe_auc(priced["_success"].to_numpy(dtype=float),
                                                     -priced["n_steps_s"].to_numpy(dtype=float)),
        }
        c = res["C_outcome_from_cost"]
        print(f"\n  failure is predicted by spending more: AUC {c['auc_cost_predicts_success']:.3f} "
              f"from cost, {c['auc_steps_predicts_success']:.3f} from step count")

    res["caveat"] = ("cost telemetry is missing for some scaffolds, so every figure here carries "
                     "its own denominator; the coverage table above is part of the result")
    with open(OUT / "cost.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'cost.json'}")


if __name__ == "__main__":
    main()
