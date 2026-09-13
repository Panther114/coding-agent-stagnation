"""Separating the two things the word "waste" has been covering.

    python scripts/analyse_dead_end.py

The pooled rate (80% of edits do not reach the final patch) is honest but too coarse to carry a
paper, because it puts two different events in one bucket:

* **revision** — the edit touched a file the agent kept working on and later replaced. Calling
  this waste is arguable: the agent was iterating, and its next attempt may have been better
  *because* of this one.
* **dead end** — the edit touched nothing the agent ever revisited, and nothing of it shipped.
  No later action of the run ever depends on it.

Only the second is unambiguously wasted effort, and only the second should carry the headline.
This script computes the two rates separately, checks how each relates to the outcome, and
states which number the paper should quote.

Classification, all mechanical:

``kept``        at least one introduced line survives into the final patch
``revised``     nothing survives, but a later edit touches the same file
``dead_end``    nothing survives, and no later edit ever touches that file again

Writes ``results/rebuild/dead_end.json``.
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


def within_instance(d: pd.DataFrame, label: str = "kept") -> Dict[str, float]:
    per_run = d.groupby(["task", "run_id"]).agg(
        rate=(label, "mean"), reward=("reward", "max")).reset_index()
    per_inst: List[float] = []
    for _task, g in per_run.groupby("task"):
        if g["reward"].nunique() < 2:
            continue
        ok = g.loc[g.reward == 1, "rate"]
        no = g.loc[g.reward == 0, "rate"]
        if len(ok) and len(no):
            per_inst.append(float(ok.mean() - no.mean()))
    if len(per_inst) < 5:
        return {"n_instances": len(per_inst)}
    a = np.asarray(per_inst)
    return {"n_instances": int(len(a)), "mean_delta": float(a.mean()),
            "median_delta": float(np.median(a)),
            "frac_positive": float((a > 0).mean()),
            "p": float(stats.wilcoxon(a).pvalue)}


def main() -> None:
    ap = argparse.ArgumentParser()
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    st = pd.read_parquet(OUT / "alignment_steps.parquet")
    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet",
                            columns=["run_id", "step", "file_shown"])
    d = st.merge(steps, on=["run_id", "step"], how="left")
    d = d.sort_values(["run_id", "step"]).reset_index(drop=True)
    d["kept"] = d["hit"].astype(float)

    # does any *later* edit in the same run touch this file?
    later = np.zeros(len(d), dtype=bool)
    for _rid, g in d.groupby("run_id", sort=False):
        idx = g.index.to_numpy()
        files = g["file_shown"].astype(str).to_numpy()
        for k in range(len(idx) - 1):
            cur = files[k]
            later[idx[k]] = bool(cur) and (files[k + 1:] == cur).any()
    d["revisited_later"] = later
    d["revised"] = ((d["kept"] == 0) & d["revisited_later"]).astype(float)
    d["dead_end"] = ((d["kept"] == 0) & ~d["revisited_later"]).astype(float)

    n = len(d)
    res: Dict[str, object] = {
        "n_edits": n, "n_runs": int(d.run_id.nunique()),
        "kept_rate": float(d["kept"].mean()),
        "revised_rate": float(d["revised"].mean()),
        "dead_end_rate": float(d["dead_end"].mean()),
        "wasted_pooled": float(1 - d["kept"].mean()),
        "decomposition_check": float(d["kept"].mean() + d["revised"].mean()
                                     + d["dead_end"].mean()),
    }
    r = res
    print(f"{n} edits over {r['n_runs']} runs")
    print(f"  kept     {r['kept_rate']:.3f}   (a surviving line reaches the final patch)")
    print(f"  revised  {r['revised_rate']:.3f}   (nothing survived, but the file was edited again)")
    print(f"  dead end {r['dead_end_rate']:.3f}   (nothing survived, and the file was never touched again)")
    print(f"  -> the coarse 'wasted' figure of {r['wasted_pooled']:.3f} splits into "
          f"{r['revised_rate']:.3f} arguable + {r['dead_end_rate']:.3f} unambiguous")

    # outcome relation for each class, within instance
    res["within_instance"] = {}
    for cls in ("kept", "revised", "dead_end"):
        w = within_instance(d, cls)
        res["within_instance"][cls] = w
        if w["n_instances"]:
            print(f"  within-instance delta in {cls:<9} rate: {w['mean_delta']:+.3f} "
                  f"({w['n_instances']} instances, p={w['p']:.2e}, "
                  f"{w['frac_positive']:.0%} of instances positive)")
        else:
            print(f"  within-instance delta in {cls:<9} rate: too few instances")

    # how much dead-end work is there, in absolute terms?
    res["volume"] = {
        "dead_end_edits": int(d["dead_end"].sum()),
        "revised_edits": int(d["revised"].sum()),
        "kept_edits": int(d["kept"].sum()),
        "mean_dead_end_per_run": float(d.groupby("run_id")["dead_end"].sum().mean()),
        "frac_runs_with_no_dead_end": float((d.groupby("run_id")["dead_end"].sum() == 0).mean()),
    }
    v = res["volume"]
    print(f"\n  {v['dead_end_edits']} dead-end edits ({v['mean_dead_end_per_run']:.1f} per run); "
          f"{v['frac_runs_with_no_dead_end']:.1%} of runs have none")

    # can a structure-only model tell a dead end from a kept edit on an *unsuperseded* edit?
    # This is the sharpest version of the admission question: among edits nothing revisits,
    # which ones will turn out to have been needed?
    sub = d[~d["revisited_later"]].copy()
    if len(sub) > 500:
        res["unsuperseded_subset"] = {
            "n": int(len(sub)), "kept_rate": float(sub["kept"].mean()),
            "note": ("within edits nothing revisits, the question 'will this turn out to have been "
                     "needed' has a directly measurable answer, and it is the decision a refusal "
                     "policy actually faces"),
        }
        print(f"  unsuperseded edits: n={len(sub)}, of which {res['unsuperseded_subset']['kept_rate']:.3f} "
              f"turned out to be needed")

    # which number should the paper quote
    res["recommendation"] = {
        "headline": ("quote the dead-end rate as the unambiguous measure of wasted work, and the "
                     "coarse rate only as context: the coarse rate counts revision, which a "
                     "reviewer will (correctly) argue is not waste"),
        "coarse_rate": float(1 - d["kept"].mean()),
        "unambiguous_rate": float(d["dead_end"].mean()),
    }
    print(f"\n  recommendation: headline {res['recommendation']['unambiguous_rate']:.3f} "
          f"(dead end), context {res['recommendation']['coarse_rate']:.3f} (coarse)")

    with open(OUT / "dead_end.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'dead_end.json'}")


if __name__ == "__main__":
    main()
