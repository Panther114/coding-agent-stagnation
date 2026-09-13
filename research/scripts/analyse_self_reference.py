"""Does the waste measure confuse *revision* with *waste*?

    python scripts/analyse_self_reference.py

The waste label is defined against the agent's **own final patch**: an edit is "wasted" if none
of its lines appear there.  A reviewer's first objection is that this counts legitimate
iteration as waste — an agent that writes a function, tries it, and rewrites it has not wasted
the first attempt, it has revised it.  If that confound is large, the headline number (80% of
edits wasted) is inflated by bookkeeping.

Three tests separate revision from waste, none of which needs a reference patch:

``T1`` **Single-edit runs.**  In a run whose final patch contains exactly one edit, there is no
       later edit that could supersede an earlier one.  So "wasted" there cannot mean revised.
       If single-edit runs waste at the same rate as multi-edit runs, iteration is not the
       explanation; if they waste far less, it is.

``T2`` **Supersession.**  For each wasted edit, does a *later* edit touch the same file?  That is
       the mechanism revision would use.  Reported as the share of wasted edits followed by a
       same-file edit.  For contrast, the same share is computed for surviving edits — the
       difference is the part of the waste that revision could account for.

``T3`` **Outcome signalling without supersession.**  Re-run the within-instance comparison on
       the subset of wasted edits that are *not* followed by a same-file edit.  If the
       successful-vs-failed gap survives there, the result does not rest on revisions.

Writes ``results/rebuild/self_reference.json``.
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
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    st = pd.read_parquet(OUT / "alignment_steps.parquet")
    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet",
                            columns=["run_id", "step", "file_shown", "is_edit"])
    d = st.merge(steps, on=["run_id", "step"], how="left")
    d = d.sort_values(["run_id", "step"]).reset_index(drop=True)
    d["_wasted"] = (1 - d["hit"]).astype(float)
    print(f"{len(d)} edit steps over {d.run_id.nunique()} runs; "
          f"pooled wasted {d['_wasted'].mean():.3f}")

    res: Dict[str, object] = {"n_edit_steps": int(len(d)),
                              "n_runs": int(d.run_id.nunique()),
                              "pooled_wasted": float(d["_wasted"].mean())}

    # ---- T1: single-edit runs cannot be revisions ------------------------------------
    n_edit = d.groupby("run_id")["step"].size()
    one = set(n_edit[n_edit == 1].index)
    few = set(n_edit[(n_edit >= 2) & (n_edit <= 3)].index)
    many = set(n_edit[n_edit >= 8].index)
    t1 = {}
    for name, keys in (("single_edit_runs", one), ("two_to_three_edits", few),
                       ("eight_or_more_edits", many)):
        sub = d[d.run_id.isin(keys)]
        if not len(sub):
            continue
        t1[name] = {"n_runs": int(sub.run_id.nunique()), "n_edits": int(len(sub)),
                    "wasted": float(sub["_wasted"].mean()),
                    "resolve_rate": float(sub["reward"].mean())}
        print(f"  T1 {name:<20} runs={t1[name]['n_runs']:>5} edits={len(sub):>7} "
              f"wasted {t1[name]['wasted']:.3f}  resolve {t1[name]['resolve_rate']:.3f}")
    res["T1_single_edit"] = t1

    # ---- T2: is a wasted edit followed by a later edit to the same file? -------------
    later_same = np.zeros(len(d), dtype=bool)
    for _rid, g in d.groupby("run_id", sort=False):
        idx = g.index.to_numpy()
        files = g["file_shown"].astype(str).to_numpy()
        for k in range(len(idx) - 1):
            cur = files[k]
            later_same[idx[k]] = bool(cur) and (files[k + 1:] == cur).any()
    d["later_same_file"] = later_same
    waste = d[d["_wasted"] == 1]
    surv = d[d["_wasted"] == 0]
    res["T2_supersession"] = {
        "wasted_followed_by_same_file": float(waste["later_same_file"].mean()),
        "surviving_followed_by_same_file": float(surv["later_same_file"].mean()),
        "difference": float(waste["later_same_file"].mean() - surv["later_same_file"].mean()),
        "share_of_waste_revision_could_explain": float(waste["later_same_file"].mean()),
        "n_wasted": int(len(waste)), "n_surviving": int(len(surv)),
    }
    t2 = res["T2_supersession"]
    print(f"\n  T2 a later edit touches the same file: wasted {t2['wasted_followed_by_same_file']:.3f}"
          f"  surviving {t2['surviving_followed_by_same_file']:.3f}  "
          f"(difference {t2['difference']:+.3f})")
    print("     -> revision could account for at most "
          f"{t2['share_of_waste_revision_could_explain']:.1%} of the waste, and it cannot explain"
          " the rest")

    # ---- T3: is the outcome gap present without supersession? -----------------------
    def within_instance(frame: pd.DataFrame, label: str) -> Dict[str, float]:
        """Compare survival rate between solved and failed runs *on the same instance*."""
        per_run = frame.groupby(["task", "run_id"]).agg(
            survival=("hit", "mean"), reward=("reward", "max")).reset_index()
        per_inst = []
        for task, g in per_run.groupby("task"):
            if g["reward"].nunique() < 2 or len(g) < 2:
                continue
            ok = g.loc[g.reward == 1, "survival"]
            no = g.loc[g.reward == 0, "survival"]
            if len(ok) and len(no):
                per_inst.append(float(ok.mean() - no.mean()))
        if not per_inst:
            return {"n_instances": 0}
        a = np.asarray(per_inst)
        return {"n_instances": int(len(a)), "mean_delta": float(a.mean()),
                "p": float(stats.wilcoxon(a).pvalue)}

    subsets = {
        "all_edits": d,
        "only_non_superseded": d[~d["later_same_file"]],
        "only_superseded": d[d["later_same_file"]],
        "only_single_file_runs": d[d.run_id.isin(
            d.groupby("run_id")["file_shown"].nunique().pipe(lambda s: s[s == 1]).index)],
    }
    res["T3_within_instance"] = {}
    for name, sub in subsets.items():
        r = within_instance(sub, name)
        res["T3_within_instance"][name] = {
            **r, "n_edits": int(len(sub)), "n_runs": int(sub.run_id.nunique()),
            "pooled_survival": float(sub["hit"].mean()) if len(sub) else float("nan"),
            "pooled_wasted": float(1 - sub["hit"].mean()) if len(sub) else float("nan"),
        }
        c = res["T3_within_instance"][name]
        print(f"  T3 {name:<22} edits={c['n_edits']:>7} wasted {c['pooled_wasted']:.3f}  "
              f"within-instance delta {c.get('mean_delta', float('nan')):+.3f} "
              f"({c['n_instances']} instances, p={c.get('p', float('nan')):.2e})")

    # ---- the honest bound ------------------------------------------------------------
    keep = d[~d["later_same_file"]]
    res["revision_upper_bound"] = {
        "pooled_wasted_all": float(d["_wasted"].mean()),
        "pooled_wasted_excluding_all_superseded": float(1 - keep["hit"].mean()),
        "note": ("Even if every superseded edit were relabelled as progress, the waste rate would "
                 "fall only to the second number; the third possibility -- that a superseded edit "
                 "was genuinely useful and simply rewritten -- cannot be separated offline and is "
                 "stated as a limitation"),
    }
    print(f"\n  bound: pooled waste {res['revision_upper_bound']['pooled_wasted_all']:.3f} -> "
          f"{res['revision_upper_bound']['pooled_wasted_excluding_all_superseded']:.3f} if every "
          f"superseded edit were counted as progress")

    with open(OUT / "self_reference.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'self_reference.json'}")


if __name__ == "__main__":
    main()
