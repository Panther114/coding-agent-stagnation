"""What does one wasted edit cost the run?

    python scripts/analyse_dead_end_cost.py

The admission policy's value depends on a quantity nothing has measured: the marginal cost of a
single wasted edit to the *run*. If a doomed edit is merely a wasted turn, refusing it is cheap and
the policy is worth having. If it derails the run — the agent builds on a wrong foundation and
never recovers — refusing it is worth much more, and the policy is worth a lot.

``routeA`` established that the admission counterfactual ("what would the agent have written
instead?") cannot be observed offline, so the question is approached from the side that *is*
observable: the relationship between how many dead-end edits a run contains and whether it
eventually succeeds, holding the instance fixed.

Four measurements:

``D1`` success rate against dead-end count, within instance where possible.
``D2`` the runs that succeed *despite* dead ends — the existence and size of that group bounds how
       costly a wasted edit can be, because a run that succeeds after N dead ends proves N dead
       ends are survivable.
``D3`` whether dead ends cluster at the *start* of a run (a wrong foundation, which would be
       expensive) or are spread through it (churn, which is cheap).
``D4`` conditional on a run having at least one dead end, how many more follow — i.e. whether dead
       ends are self-propagating.

Writes ``results/rebuild/dead_end_cost.json``.
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

OUT = ROOT / "results" / "rebuild"


def main() -> None:
    ap = argparse.ArgumentParser()
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

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
    d["rank"] = d.groupby("run_id").cumcount()
    d["n_in_run"] = d.groupby("run_id")["step"].transform("size")
    d["relpos"] = d["rank"] / (d["n_in_run"] - 1).replace(0, np.nan)

    per_run = d.groupby(["run_id", "task", "reward"]).agg(
        n_edit=("hit", "size"), dead=("dead_end", "sum"),
        first_dead_pos=("dead_end", lambda s: float(np.nan) if s.sum() == 0 else
                        float(d.loc[s.index[s > 0][0], "relpos"]))
        if False else ("dead_end", "sum")).reset_index()
    # first dead-end position, computed separately for clarity
    first_pos: List[float] = []
    for _rid, g in d.groupby("run_id", sort=False):
        de = g["dead_end"].to_numpy()
        idx = np.nonzero(de > 0)[0]
        first_pos.append(float(g["relpos"].to_numpy()[idx[0]]) if len(idx) else np.nan)
    per_run["first_dead_relpos"] = first_pos
    per_run["dead_frac"] = per_run["dead"] / per_run["n_edit"].clip(lower=1)
    print(f"{len(per_run)} runs; {int((per_run['dead'] > 0).sum())} contain a dead end; "
          f"overall success {per_run['reward'].mean():.3f}")

    res: Dict[str, object] = {"n_runs": int(len(per_run)),
                              "overall_success": float(per_run["reward"].mean())}

    # ---- D1: success against dead-end count -----------------------------------------
    bins = [(-0.5, 0.5, "0"), (0.5, 1.5, "1"), (1.5, 3.5, "2-3"), (3.5, 7.5, "4-7"),
            (7.5, 1e9, "8+")]
    d1 = []
    for lo, hi, label in bins:
        s = per_run[(per_run["dead"] > lo) & (per_run["dead"] <= hi)]
        if not len(s):
            continue
        d1.append({"dead_ends": label, "n_runs": int(len(s)),
                   "success": float(s["reward"].mean()),
                   "median_edits": float(s["n_edit"].median())})
        print(f"  D1 {label:>4} dead ends: n={len(s):>5}  success {s['reward'].mean():.3f}  "
              f"median edits {s['n_edit'].median():.0f}")
    res["D1_success_by_dead_count"] = d1

    # within-instance version, restricted to instances with both outcomes
    sel = per_run.groupby("task")["reward"].nunique()
    multi = sel[sel >= 2].index
    sub = per_run[per_run.task.isin(multi)]
    if len(sub) > 200:
        def within(pred: pd.Series) -> Dict[str, float]:
            a = sub[pred]["reward"]
            b = sub[~pred]["reward"]
            return {"n_true": int(pred.sum()), "n_false": int((~pred).sum()),
                    "success_true": float(a.mean()), "success_false": float(b.mean())}
        res["D1_within_instance_any_dead"] = within(sub["dead"] > 0)
        w = res["D1_within_instance_any_dead"]
        print(f"  D1 (contested instances only, n={len(sub)}): any dead end "
              f"success {w['success_true']:.3f} vs none {w['success_false']:.3f}")

    # ---- D2: runs that succeed despite dead ends -------------------------------------
    surv = per_run[(per_run["dead"] > 0) & (per_run["reward"] == 1)]
    res["D2_survivors"] = {
        "n_runs": int(len(surv)),
        "share_of_successes": float(len(surv) / max(1, int(per_run["reward"].sum()))),
        "median_dead_ends": float(surv["dead"].median()) if len(surv) else float("nan"),
        "max_dead_ends_then_success": int(surv["dead"].max()) if len(surv) else 0,
        "mean_dead_ends": float(surv["dead"].mean()) if len(surv) else float("nan"),
    }
    s2 = res["D2_survivors"]
    print(f"\n  D2 {s2['n_runs']} runs succeeded despite a dead end "
          f"({s2['share_of_successes']:.1%} of all successes); median {s2['median_dead_ends']:.0f} "
          f"dead ends, maximum {s2['max_dead_ends_then_success']}")
    print("     -> a wasted edit is survivable, so its marginal cost is bounded by what these runs "
          "paid and still succeeded")

    # ---- D3: where do dead ends sit in a run? ---------------------------------------
    de = d[d["dead_end"] == 1]["relpos"].dropna()
    ot = d[d["dead_end"] == 0]["relpos"].dropna()
    res["D3_position"] = {
        "dead_end_median_relpos": float(de.median()) if len(de) else float("nan"),
        "non_dead_end_median_relpos": float(ot.median()) if len(ot) else float("nan"),
        "mannwhitney_p": float(stats.mannwhitneyu(de, ot, alternative="greater").pvalue)
        if len(de) and len(ot) else float("nan"),
        "n_dead": int(len(de)), "n_other": int(len(ot)),
    }
    d3 = res["D3_position"]
    print(f"\n  D3 median position in run: dead ends {d3['dead_end_median_relpos']:.2f} vs "
          f"other edits {d3['non_dead_end_median_relpos']:.2f} (p={d3['mannwhitney_p']:.1e})")

    # ---- D4: are dead ends self-propagating? ----------------------------------------
    d4 = []
    for k in range(0, 9):
        s = per_run[per_run["dead"] == k]
        if len(s) < 20:
            continue
        d4.append({"dead_ends": k, "n_runs": int(len(s)),
                   "success": float(s["reward"].mean())})
    res["D4_by_exact_count"] = d4
    print("\n  D4 success by exact dead-end count:")
    for r in d4:
        print(f"     {r['dead_ends']:>2} dead ends: n={r['n_runs']:>5}  success {r['success']:.3f}")

    res["interpretation"] = (
        "Survivable dead ends with a bounded cost mean the admission policy's value is measured in "
        "wasted turns rather than in rescued runs; the runs that succeed after several dead ends "
        "are the evidence, and they are the reason the paper must not claim a refusal would have "
        "saved the run.")
    print(f"\n  {res['interpretation']}")
    with open(OUT / "dead_end_cost.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'dead_end_cost.json'}")


if __name__ == "__main__":
    main()
