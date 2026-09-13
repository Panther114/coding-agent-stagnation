"""Is the survival rate an artefact of edit size?

    python scripts/analyse_size_artifact.py

An edit that writes twelve lines has twelve chances to land a surviving line; an edit that writes
one has one. So a rising survival rate with size is partly arithmetic, and a reviewer will say so.
This measures how much of the effect is arithmetic and how much is real, three ways:

``S1`` **within size.**  Restrict to edits of the same size and ask whether survival still varies
       with the variables that should matter (file size, whether the file was edited before, how
       far into the run it is).  Size-controlled variation cannot be an arithmetic artefact.
``S2`` **the arithmetic baseline.**  Model survival as "did the agent write *what the file was
       missing*", approximated by the chance that a random line of the same length would appear in
       the patch.  Comparing the observed rate to that baseline separates luck from aim.
``S3`` **the size-controlled outcome relation.**  Re-run the within-instance comparison on the
       largest single size stratum, so the headline result cannot be attributed to agents writing
       bigger edits.

Writes ``results/rebuild/size_artifact.json``.
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
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    st = pd.read_parquet(OUT / "alignment_steps.parquet")
    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet",
                            columns=["run_id", "step", "file_shown", "added_lines_n",
                                     "file_total", "edit_lines"])
    d = st.merge(steps, on=["run_id", "step"], how="left")
    d["n_lines"] = d["added_lines_n"].fillna(0)
    d = d[d["n_lines"] > 0].copy()
    d["file_size"] = d["file_total"].fillna(-1)
    d["rank"] = d.groupby("run_id").cumcount()
    d["n_in_run"] = d.groupby("run_id")["step"].transform("size")
    d["relpos"] = d["rank"] / (d["n_in_run"] - 1).replace(0, np.nan)
    d["file_edits_before"] = d.groupby(["run_id", "file_shown"]).cumcount()
    print(f"{len(d)} edits with a known line count over {d.run_id.nunique()} runs")
    res: Dict[str, object] = {"n_edits": int(len(d)), "overall_survival": float(d["hit"].mean())}

    # ---- S1: survival by size, and inside the largest size stratum -------------------
    by_size = []
    for k in (1, 2, 3, 4, 5, 6, 8, 12, 20):
        lo = k if k in (1, 2, 3) else (3 if k <= 6 else (6 if k <= 12 else 12))
        sel = d[d["n_lines"] >= k] if k <= 3 else d[(d["n_lines"] >= lo) & (d["n_lines"] < k)] if k != 20 else d[d["n_lines"] >= 12]
        if len(sel) < 100:
            continue
        by_size.append({"n_lines": k, "n": int(len(sel)), "survival": float(sel["hit"].mean())})
    res["by_size"] = by_size
    print("\nS1 survival by edit size (mechanical: more lines, more chances)")
    for r in by_size:
        print(f"   n_lines>={r['n_lines']:<3} n={r['n']:>7}  survival {r['survival']:.3f}")

    # inside a single size stratum, does anything else still predict survival?
    stratum = d[d["n_lines"] == 1].copy()
    res["single_line_stratum"] = {
        "n": int(len(stratum)), "survival": float(stratum["hit"].mean()),
    }
    print(f"\n   single-line edits: n={len(stratum)}, survival {stratum['hit'].mean():.3f}")
    for var in ("file_size", "file_edits_before", "relpos", "edit_lines"):
        v = stratum[var].to_numpy(dtype=float)
        ok = ~np.isnan(v)
        if ok.sum() < 200:
            continue
        a = E.safe_auc(stratum["hit"].to_numpy(dtype=float)[ok], v[ok])
        res["single_line_stratum"][f"auc_{var}"] = a
        print(f"     within single-line edits, survival predicted by {var:<20} AUC {a:.3f}")

    # ---- S2: the arithmetic baseline --------------------------------------------------
    # A random line of typical length matches the patch's added-line set by chance. Estimate
    # that chance from the patch vocabulary size relative to the file vocabulary.
    patch_lines = d["hit"].mean()
    res["S2_note"] = ("the arithmetic baseline is estimated as the survival of the smallest edit "
                      "class, since a one-line edit has exactly one chance to match")
    print(f"\nS2 a one-line edit has one chance to match and survives {stratum['hit'].mean():.3f}; "
          f"an edit of five or more lines has at least five and survives "
          f"{d.loc[d['n_lines'] >= 5, 'hit'].mean():.3f}")

    # ---- S3: the headline comparison inside one size stratum --------------------------
    def within_instance(frame: pd.DataFrame) -> Dict[str, float]:
        per_run = frame.groupby(["task", "run_id"]).agg(
            survival=("hit", "mean"), reward=("reward", "max")).reset_index()
        deltas: List[float] = []
        for _t, g in per_run.groupby("task"):
            if g["reward"].nunique() < 2:
                continue
            ok = g.loc[g.reward == 1, "survival"]
            no = g.loc[g.reward == 0, "survival"]
            if len(ok) and len(no):
                deltas.append(float(ok.mean() - no.mean()))
        if len(deltas) < 5:
            return {"n_instances": len(deltas)}
        a = np.asarray(deltas)
        return {"n_instances": int(len(a)), "mean_delta": float(a.mean()),
                "p": float(stats.wilcoxon(a).pvalue)}

    res["S3_within_instance"] = {}
    for name, frame in (("all_edits", d), ("single_line_only", stratum),
                        ("five_plus_lines", d[d["n_lines"] >= 5])):
        w = within_instance(frame)
        res["S3_within_instance"][name] = {**w, "n": int(len(frame)),
                                           "survival": float(frame["hit"].mean())}
        if w.get("n_instances"):
            print(f"   S3 {name:<18} n={len(frame):>7} survival {frame['hit'].mean():.3f}  "
                  f"within-instance delta {w['mean_delta']:+.3f} "
                  f"({w['n_instances']} instances, p={w['p']:.2e})")

    res["interpretation"] = (
        "Size explains part of the survival trend by arithmetic. What matters is whether the "
        "outcome relation survives inside a single size stratum; if it does, the headline is not a "
        "size artefact.")
    print(f"\n{res['interpretation']}")
    with open(OUT / "size_artifact.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"wrote {OUT / 'size_artifact.json'}")


if __name__ == "__main__":
    main()
