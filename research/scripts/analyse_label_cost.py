"""How much of the first version's 0.78 was the label, quantified.

    python scripts/analyse_label_cost.py

The rebuild's cleanest methodological claim is that the first version's ~0.78 ceiling was a
property of its AI-judged labels rather than of the trajectories. That claim is currently
supported by two facts measured on different sample sizes: the same families score 0.66–0.69
against the judged labels on the 386 matched windows and 0.85–0.96 against the mechanical target
elsewhere. Three-way evidence is stronger, so this adds it:

``L1`` **the honest in-sample comparison.** Both targets, identical features, identical 386
       windows, identical folds — so the gap is attributable to the label and nothing else.
``L2`` **the label's own ceiling.** Take the mechanical target as ground truth and degrade it to
       the judged label's measured reliability. How much AUC does that coarsening cost a *perfect*
       detector? That is the loss the first version paid without knowing it.
``L3`` **what agreement we see.** The confusion between the two targets on the matched set, so a
       reader can see whether they disagree by noise or by definition.

Writes ``results/rebuild/label_cost.json``.
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
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    m = pd.read_parquet(OUT / "gold_matched_windows.parquet")
    m = m[m["binary"].notna()].copy()
    m["y_judged"] = m["binary"].to_numpy(dtype=float)
    m["y_mech"] = (m["y_stagnation"] > 0.5).astype(float).to_numpy()
    print(f"{len(m)} windows carry both targets")

    keys = [k for grp in FEATURE_GROUPS.values() for k in grp]
    cols = [c for c in m.columns if c in keys]
    res: Dict[str, object] = {"n_matched_windows": int(len(m)), "n_features": len(cols),
                              "task": None}
    if len(m) < 60 or len(cols) < 2:
        print("too few matched windows for a controlled comparison")
        with open(OUT / "label_cost.json", "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2, default=float)
        return

    # ---- L3: the confusion between the two targets -----------------------------------
    a = m["y_judged"].to_numpy(dtype=float)
    b = m["y_mech"].to_numpy(dtype=float)
    agree = float((a == b).mean())
    conf = {
        "agree": agree,
        "judged_stagnant_mech_quiet": int(((a == 1) & (b == 1)).sum()),
        "judged_stagnant_mech_active": int(((a == 1) & (b == 0)).sum()),
        "judged_productive_mech_quiet": int(((a == 0) & (b == 1)).sum()),
        "judged_productive_mech_active": int(((a == 0) & (b == 0)).sum()),
        "auc_between_targets": E.safe_auc(a, b),
    }
    res["L3_confusion"] = conf
    print(f"\nL3 the two targets agree on {agree:.1%} of matched windows "
          f"(AUC between them {conf['auc_between_targets']:.3f})")
    print(f"     judged STAGNANT but mechanically active: {conf['judged_stagnant_mech_active']}")
    print(f"     judged PRODUCTIVE but mechanically quiet: {conf['judged_productive_mech_quiet']}")

    # ---- L1: identical features, identical windows, both targets ----------------------
    res["L1_same_windows"] = {}
    print("\nL1 identical features and windows, two targets")
    for gname, gkeys in FEATURE_GROUPS.items():
        cs = [c for c in m.columns if c in gkeys]
        if len(cs) < 2:
            continue
        row = {}
        for target in ("y_judged", "y_mech"):
            f = E.fit_logistic_cv(m, cs, y_col=target, n_folds=args.folds)
            row[target] = {"auc": E.safe_auc(m[target].to_numpy(dtype=float), f["oof"]),
                           "ap": E.safe_ap(m[target].to_numpy(dtype=float), f["oof"])}
        res["L1_same_windows"][gname] = row
        print(f"  {gname:<6} judged {row['y_judged']['auc']:.3f}  "
              f"mechanical {row['y_mech']['auc']:.3f}  "
              f"gap {row['y_mech']['auc'] - row['y_judged']['auc']:+.3f}")

    # ---- L2: what coarsening to the judged reliability costs a perfect detector --------
    # The judged label's reliability: how often two readings of the same window agree has been
    # measured on the whole gold set (kappa 0.70, binary agreement 88.1%).  Simulate a label with
    # that reliability from the mechanical target and measure the best achievable AUC.
    rng = np.random.default_rng(0)
    flip_rates = [0.05, 0.10, 0.15, 0.20, 0.30]
    sim: List[Dict[str, float]] = []
    y_true = (m["y_stagnation"] > 0.5).astype(int).to_numpy()
    for p in flip_rates:
        aucs = []
        for _ in range(20):
            flip = rng.random(len(y_true)) < p
            y_noisy = np.where(flip, 1 - y_true, y_true)
            # a perfect detector of the TRUE label scored against the NOISY label
            aucs.append(E.safe_auc(y_noisy.astype(float), y_true.astype(float)))
        sim.append({"flip_rate": p, "auc_perfect_detector": float(np.mean(aucs)),
                    "sd": float(np.std(aucs))})
        print(f"  L2 label flips {p:.0%} of windows -> a perfect detector scores "
              f"{np.mean(aucs):.3f}")
    res["L2_label_noise_ceiling"] = sim
    # invert: which flip rate matches the judged label's observed ceiling?
    judged_best = max((v["y_judged"]["auc"] for v in res["L1_same_windows"].values()
                       if v["y_judged"]["auc"] == v["y_judged"]["auc"]), default=float("nan"))
    mech_best = max((v["y_mech"]["auc"] for v in res["L1_same_windows"].values()
                     if v["y_mech"]["auc"] == v["y_mech"]["auc"]), default=float("nan"))
    res["observed_gap_on_same_windows"] = float(mech_best - judged_best)
    print(f"\n  on these windows the best family scores {judged_best:.3f} against the judged label "
          f"and {mech_best:.3f} against the mechanical one (gap {mech_best - judged_best:+.3f})")
    print("  NOTE: 386 windows is a small sample and the gold set was not sampled for this "
          "comparison; the gap here is evidence, not the final word.")

    res["caveat"] = ("the matched set is 386 windows from the first version's strided gold sample, "
                     "so the L1 gap is measured on the small overlap; the L2 simulation is the "
                     "scaling argument and does not depend on the sample size")
    with open(OUT / "label_cost.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'label_cost.json'}")


if __name__ == "__main__":
    main()
