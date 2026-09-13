"""An edit-admission policy: refuse the edit, not the run.

    python scripts/analyse_admission.py

The rebuild's leading new direction.  Whether an edit's lines survive is predictable from the
**edit's own structure** (AUC 0.732) but not from its context (0.60–0.69).  That changes what
the intervention should be: instead of watching a trajectory and stopping a run, a runtime
could look at an edit *before applying it* and decline the ones that are almost certainly
discarded.

This script measures that policy honestly, including its limits.

What is measured
----------------
* **Pooled survival** — the share of applied edits that land a surviving line — as the
  threshold rises, computed out of fold so no admitted edit was scored by a model that saw it.
* **Admission rate** — how much of the agent's writing the policy would refuse.
* **The counterfactual that cannot be measured.** A refused edit is not simply deleted: the
  agent would react to the refusal and might write something better, worse, or the same. Offline
  replay cannot observe that, so every number here is an *upper bound on the information
  available*, not a promise about outcomes. This is stated in the artifact and the findings.
* **Where refused edits sit.** If the edits a policy refuses are concentrated in runs that fail
  anyway, refusing them is close to free. Reported as the failure rate of the runs the refusals
  fall in, against the base rate.
* **The free baseline.** The strongest single structural predictor is how much the edit writes,
  so a policy that simply refuses edits below an N-line threshold is compared against the
  learned one.  If the learned model does not beat the free rule, the honest recommendation is
  the free rule.

Writes ``results/rebuild/admission.json``.
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
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    es = json.loads((OUT / "edit_structure.json").read_text(encoding="utf-8"))
    struct_cols: List[str] = es["features"]

    st = pd.read_parquet(OUT / "alignment_steps.parquet")
    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet",
                            columns=["run_id", "step", "is_edit", "file_total", "file_shown",
                                     "added_lines_n", "edit_lines", "tool", "n_cmds", "obs_chars"])
    d = st.merge(steps, on=["run_id", "step"], how="left")
    d = d[d["is_edit"].fillna(0) > 0].copy()
    print(f"{len(d)} edit steps over {d.run_id.nunique()} runs")

    d["n_added"] = d["n_added"].fillna(0.0)
    d["file_size"] = d["file_total"].fillna(-1.0)
    d["edit_lines"] = d["edit_lines"].fillna(0.0)
    d["n_cmds"] = d["n_cmds"].fillna(0.0)
    d["obs_chars"] = d["obs_chars"].fillna(0.0)
    g = d.groupby("run_id")
    d["edit_rank"] = g.cumcount().astype(float)
    d["n_edits_run"] = g["step"].transform("size").astype(float)
    d["file_edits_before"] = g.apply(
        lambda x: x.groupby("file_shown").cumcount(), include_groups=False
    ).reset_index(level=0, drop=True).astype(float)
    dist: List[float] = []
    for _rid, grp in d.groupby("run_id", sort=False):
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
    d["_survives"] = d["hit"].astype(float)

    # out-of-fold scored admission model (fitted on survival; no admitted row saw its own fold)
    oof = E.fit_logistic_cv(d, struct_cols, y_col="_survives", n_folds=args.folds, seed=args.seed)["oof"]
    d["p_survive"] = oof
    print(f"admission model out-of-fold AUC (survival direction) "
          f"{E.safe_auc(d['_survives'].to_numpy(dtype=float), oof):.3f}")

    res: Dict[str, object] = {
        "n_edits": int(len(d)), "n_runs": int(d.run_id.nunique()),
        "base_survival": float(d["_survives"].mean()),
        "base_run_failure_rate": float((1 - d["reward"]).mean()),
        "note": ("Counters are approximate: r counts edits whose *hashes survived*. For a "
                 "range edit the count includes anchored lines, so it over-counts genuine "
                 "survival uniformly; it cannot inflate the size trend, only shift the level."),
        "curve": [],
    }

    # ---- the learned policy, swept over the admission threshold ----------------------
    for q in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
        thr = float(np.quantile(d["p_survive"], q)) if q > 0 else -np.inf
        admit = d[d["p_survive"] > thr]
        refused = d[d["p_survive"] <= thr]
        if not len(admit):
            continue
        cell = {
            "refuse_bottom_quantile": q,
            "admit_rate": float(len(admit) / len(d)),
            "survival_of_admitted": float(admit["_survives"].mean()),
            "survival_lift": float(admit["_survives"].mean() - d["_survives"].mean()),
            "n_refused": int(len(refused)),
            "refused_run_failure_rate": float((1 - refused["reward"]).mean()) if len(refused) else float("nan"),
        }
        res["curve"].append(cell)
        print(f"  refuse lowest {q:.0%}: admit {cell['admit_rate']:.1%} of edits, "
              f"survival {cell['survival_of_admitted']:.3f} (base {res['base_survival']:.3f}, "
              f"lift {cell['survival_lift']:+.3f}), refused edits sit in runs failing "
              f"{cell['refused_run_failure_rate']:.3f} of the time")

    # ---- the free rule: refuse small edits -------------------------------------------
    free = []
    for k in (1, 2, 3, 5, 8):
        admit = d[d["n_added"] >= k]
        if not len(admit):
            continue
        free.append({
            "refuse_edits_under_n_lines": k,
            "admit_rate": float(len(admit) / len(d)),
            "survival_of_admitted": float(admit["_survives"].mean()),
            "survival_lift": float(admit["_survives"].mean() - d["_survives"].mean()),
        })
    res["free_rule"] = free
    print("\nfree rule (refuse edits writing fewer than N lines):")
    for c in free:
        print(f"  N={c['refuse_edits_under_n_lines']}: admit {c['admit_rate']:.1%}, "
              f"survival {c['survival_of_admitted']:.3f} (lift {c['survival_lift']:+.3f})")

    # matched comparison at the same admission rate
    if res["curve"]:
        target = next((c for c in res["curve"] if c["admit_rate"] <= 0.60), res["curve"][-1])
        best_free = min(free, key=lambda c: abs(c["admit_rate"] - target["admit_rate"]))
        res["matched_comparison"] = {
            "learned": {"admit_rate": target["admit_rate"],
                        "survival_of_admitted": target["survival_of_admitted"]},
            "free_rule": {"admit_rate": best_free["admit_rate"],
                          "survival_of_admitted": best_free["survival_of_admitted"],
                          "n_lines": best_free["refuse_edits_under_n_lines"]},
            "difference": float(target["survival_of_admitted"] - best_free["survival_of_admitted"]),
        }
        m = res["matched_comparison"]
        print(f"\nmatched at ~{m['learned']['admit_rate']:.0%} admission: learned "
              f"{m['learned']['survival_of_admitted']:.3f} vs free rule "
              f"{m['free_rule']['survival_of_admitted']:.3f} "
              f"(difference {m['difference']:+.3f})")

    with open(OUT / "admission.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'admission.json'}")


if __name__ == "__main__":
    main()
