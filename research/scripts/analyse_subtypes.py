"""Feature profiles by stagnation subtype.

The aggregate comparisons hide a real split: a window can be stagnant because nothing new is
happening (a verification loop) or because plenty is happening that is not about the task
(irrelevant exploration, post-completion churn).  This script reports the mean value of the
main features per subtype, next to productive windows, so the two failure modes are visible.

Usage: python scripts/analyse_subtypes.py --run results/final/tb2_final --corpus tb2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import numpy as np  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

import paths  # noqa: E402

FEATURES = ["ev_new_relevant_rate", "ev_new_highrel_rate", "ev_rel_weighted_novelty",
            "nov_new_entity_rate", "nov_distinct_sig_frac", "sem_novelty_rate",
            "rep_exact_frac", "rep_global_recurrence", "ver_progress", "ver_stall_len",
            "wk_n_edit", "wk_churn_rate", "ev_relevance_mean"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    rows = pq.read_table(os.path.join(args.run, "window_features.parquet")).to_pylist()
    rows = [r for r in rows if r["w"] == args.w and r["binary"] is not None]
    groups: Dict[str, List[Dict]] = defaultdict(list)
    for r in rows:
        if r["binary"] == 1:
            groups[r["detail"] or "stagnant_other"].append(r)
        elif r["binary"] == 0:
            groups["productive"].append(r)

    order = ["productive", "no_new_information", "repeat_verify", "no_tool_text_loop",
             "repeat_search", "repeat_read", "edit_revert", "post_completion",
             "irrelevant_exploration", "stagnant_other"]
    order = [g for g in order if g in groups]
    print(f"{'group':24}{'n':>5}" + "".join(f"{f[:13]:>15}" for f in FEATURES))
    prof: Dict[str, Dict[str, float]] = {}
    for g in order:
        vals = {f: float(np.nanmean([r.get(f, np.nan) for r in groups[g]])) for f in FEATURES}
        prof[g] = {"n": len(groups[g]), **vals}
        print(f"{g:24}{len(groups[g]):5d}" + "".join(f"{vals[f]:>15.3f}" for f in FEATURES))

    # significance of the key contrast: nothing-new vs something-new-but-irrelevant
    def m(g, f):
        v = [r.get(f, np.nan) for r in groups.get(g, [])]
        v = [x for x in v if x == x]
        return (float(np.mean(v)) if v else float("nan"), len(v))
    print("\nkey contrast (mean over windows):")
    for f in ("nov_new_entity_rate", "sem_novelty_rate", "ev_new_relevant_rate"):
        a, na = m("no_new_information", f)
        b, nb = m("irrelevant_exploration", f)
        c, nc = m("post_completion", f)
        p, np_ = m("productive", f)
        print(f"  {f:26} productive={p:.3f}(n={np_})  no-new-info={a:.3f}(n={na})  "
              f"irrelevant={b:.3f}(n={nb})  post-completion={c:.3f}(n={nc})")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(prof, fh, indent=2)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
