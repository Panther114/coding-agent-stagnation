"""Does *when* a run dead-ends matter, or only how much?

    python scripts/analyse_dead_end_timing.py

§2.19 found success falls monotonically with the number of dead-end edits. A natural refinement:
a dead end early in a run (a wrong foundation) should cost more than one late (tail churn), and the
raw numbers look like they agree — runs whose first dead end falls in the first quarter succeed
**11.3%** of the time against **17.6%** for runs whose first dead end is later.

That comparison is confounded twice over, so it is tested properly here:

``L`` **length** — an early dead end is partly a *short run* wearing a different name, and short runs
       fail more often. Controlled by matching on run length.
``T`` **task** — dead-end timing varies by issue. Controlled by matching within task.

The result reported by the artifact is the paired difference after both controls, which is the
quantity the paper may quote.

Writes ``results/rebuild/dead_end_timing.json``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "results" / "rebuild"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut", type=float, default=0.25)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    st = pd.read_parquet(OUT / "alignment_steps.parquet")
    s = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet",
                        columns=["run_id", "step", "file_shown"])
    d = st.merge(s, on=["run_id", "step"], how="left").sort_values(["run_id", "step"])
    later = {}
    for _rid, g in d.groupby("run_id", sort=False):
        files = g["file_shown"].astype(str).to_numpy()
        idx = g.index.to_numpy()
        for k in range(len(idx) - 1):
            cur = files[k]
            later[idx[k]] = bool(cur) and (files[k + 1:] == cur).any()
    d["revisited_later"] = d.index.map(lambda i: later.get(i, False))
    d["dead"] = (d["hit"] == 0) & (~d["revisited_later"])

    rows: List[Dict[str, object]] = []
    for rid, g in d.groupby("run_id", sort=False):
        idx = np.nonzero(g["dead"].to_numpy())[0]
        n = len(g)
        rows.append({
            "run_id": rid, "task": g["task"].iloc[0], "reward": int(g["reward"].max()),
            "n_edit": n, "n_dead": int(g["dead"].sum()),
            "first_pos": float(idx[0] / max(1, n - 1)) if len(idx) else float("nan"),
        })
    r = pd.DataFrame(rows)
    sub = r[(r.n_dead > 0) & (r.n_edit >= 6)].copy()
    sub["early"] = sub.first_pos <= args.cut
    print(f"{len(r)} runs; {len(sub)} with a dead end and >=6 edits")
    print(f"  naive: runs with a dead end in the first {args.cut:.0%} succeed "
          f"{sub.loc[sub.early, 'reward'].mean():.3f} ({int(sub.early.sum())} runs) vs "
          f"{sub.loc[~sub.early, 'reward'].mean():.3f} ({int((~sub.early).sum())} runs)")

    res: Dict[str, object] = {
        "n_runs": int(len(r)), "n_analysed": int(len(sub)), "cut": args.cut,
        "naive": {
            "success_early": float(sub.loc[sub.early, "reward"].mean()),
            "success_late": float(sub.loc[~sub.early, "reward"].mean()),
            "n_early": int(sub.early.sum()), "n_late": int((~sub.early).sum()),
        },
    }

    # ---- task-and-length matched pairs ------------------------------------------------
    pairs: List[Tuple[float, float]] = []
    for _task, g in sub.groupby("task"):
        e = g[g.early]
        l = g[~g.early]
        if len(e) < 3 or len(l) < 3:
            continue
        for _i, row in e.iterrows():
            cand = l[(l.n_edit >= row.n_edit * 0.8) & (l.n_edit <= row.n_edit * 1.25)]
            if len(cand):
                pairs.append((float(row.reward), float(cand.reward.mean())))
    res["matched"] = {"n_pairs": len(pairs)}
    if len(pairs) > 20:
        a = np.array([p[0] for p in pairs])
        b = np.array([p[1] for p in pairs])
        w = stats.wilcoxon(a, b)
        res["matched"].update({
            "success_early": float(a.mean()), "success_matched_late": float(b.mean()),
            "paired_difference": float((a - b).mean()), "wilcoxon_p": float(w.pvalue),
        })
        m = res["matched"]
        print(f"  matched on task and run length: early {m['success_early']:.3f} vs matched late "
              f"{m['success_matched_late']:.3f}  difference {m['paired_difference']:+.3f} "
              f"({m['n_pairs']} pairs, p={m['wilcoxon_p']:.3f})")
        res["verdict"] = (
            "The naive timing effect does not survive the controls: once the run's task and length "
            "are held fixed, a dead end in the first quarter is indistinguishable from one later "
            "on. What matters is how much a run wastes, not when." if w.pvalue > 0.05 else
            "The timing effect survives the controls, so early waste is worse than late waste.")
    else:
        res["verdict"] = "too few matched pairs to test"
    print(f"\n  {res['verdict']}")

    # ---- and the mechanism the naive result actually measures -------------------------
    res["length_confound"] = {
        "median_edits_early": float(sub.loc[sub.early, "n_edit"].median()),
        "median_edits_late": float(sub.loc[~sub.early, "n_edit"].median()),
    }
    print(f"  the naive comparison was partly measuring run length: median edits "
          f"{res['length_confound']['median_edits_early']:.0f} for early-dead-end runs vs "
          f"{res['length_confound']['median_edits_late']:.0f} for late ones")

    with open(OUT / "dead_end_timing.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'dead_end_timing.json'}")


if __name__ == "__main__":
    main()
